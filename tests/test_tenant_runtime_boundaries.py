"""Real A/B isolation at cached UI reads, local adapters and generation state."""
from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

import armazenamento
import asset_library as assets
import book_doctor as doctor
import controle_geracao as generation
import painel_projetos as projects
import saas_access as access
import storage_backend as storage


@pytest.fixture
def tenants(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://identity.example")
    monkeypatch.delenv("FAITHBLOOM_ACCESS_ROLES", raising=False)
    actors = [access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": sub})
              for sub in ("account-a", "account-b")]
    raw = storage.LocalStorageBackend(str(tmp_path / "private-data"))
    backend = storage.TenantStorageBackend(raw)
    for module in (storage, armazenamento, assets, doctor, projects):
        monkeypatch.setattr(module, "BACKEND", backend)
    monkeypatch.setattr(storage, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(doctor, "ROOT", tmp_path / "pilot-projects")
    monkeypatch.setattr(generation, "LOG_PATH", tmp_path / "pilot-generations.jsonl")
    monkeypatch.setattr(generation, "_IN_FLIGHT", set())
    monkeypatch.setattr(generation, "_RECENT", {})
    monkeypatch.setattr(generation, "_EXECUTIONS", {})
    projects._cached_project_snapshot.clear()
    yield (*actors, raw, backend)
    projects._cached_project_snapshot.clear()


def test_project_cache_hits_authorize_and_separate_logical_paths(tenants, monkeypatch):
    a, b, _, backend = tenants
    with access.access_context(a):
        backend.put_json("livros/same.json", {"private": "A"})
        uri_a = storage.storage_uri("livros/same.json")
        assert projects.project_snapshot("livros/same.json") == {"private": "A"}
    with access.access_context(b):
        backend.put_json("livros/same.json", {"private": "B"})
        assert projects.project_snapshot("livros/same.json") == {"private": "B"}
        with pytest.raises(access.AccessDenied):
            projects.project_snapshot(uri_a)
    # A real cache hit must still execute the public authorization wrapper.
    monkeypatch.setattr(backend, "get_json", lambda *_: pytest.fail("unexpected cache miss"))
    with access.access_context(a):
        assert projects.project_snapshot(uri_a) == {"private": "A"}
    with pytest.raises(access.AccessDenied):
        projects.project_snapshot(uri_a)


@pytest.mark.parametrize("kind,path,state_key,saved_key", [
    ("story", "livros/same.json", "state_r", "caminho_salvo_r"),
    ("coloring", "livros_colorir/same.json", "state_c", "caminho_salvo_c"),
])
def test_project_activation_reuses_only_current_accounts_qualified_draft(
        tenants, monkeypatch, kind, path, state_key, saved_key):
    a, b, _, backend = tenants
    session = {}
    monkeypatch.setattr(projects.st, "session_state", session)
    card = {"kind": kind, "storage_path": path}
    with access.access_context(a):
        backend.put_json(path, {"titulo": "A saved", "private_text": "A only"})
        projects.activate_project(card)
        qualified_a = storage.uri_to_path(storage.storage_uri(path))
        assert session[saved_key] == qualified_a
        assert session[projects.PROJECT_CONTEXT_KEY]["storage_path"] == qualified_a
        assert projects.get_active_project([card]) == card
        session[state_key]["titulo"] = "A unsaved edit"
        assert projects.activate_project({**card, "storage_path": "fb://" + qualified_a})["titulo"] == "A unsaved edit"
    with access.access_context(b):
        backend.put_json(path, {"titulo": "B saved", "private_text": "B only"})
        assert projects.get_active_project([card]) is None
        loaded = projects.activate_project(card)
        assert loaded["private_text"] == "B only"
        assert loaded["titulo"] == "B saved"
        qualified_b = storage.uri_to_path(storage.storage_uri(path))
        assert session[saved_key] == qualified_b != qualified_a
        assert session[projects.PROJECT_CONTEXT_KEY]["storage_path"] == qualified_b
        assert projects.get_active_project([card]) == card
    with access.access_context(a):
        assert projects.activate_project(card)["private_text"] == "A only"
        assert session[state_key]["titulo"] == "A saved"


@pytest.mark.parametrize("kind,path", [("story", "livros/same.json"), ("coloring", "livros_colorir/same.json")])
def test_project_activation_authorizes_before_reading_or_mutating_session(tenants, monkeypatch, kind, path):
    a, b, _, backend = tenants
    session = {}
    monkeypatch.setattr(projects.st, "session_state", session)
    card = {"kind": kind, "storage_path": path}
    with access.access_context(a):
        backend.put_json(path, {"titulo": "A private draft"})
        projects.activate_project(card)
        foreign = storage.storage_uri(path)
    before = deepcopy(session)

    class UnreadableSession(dict):
        def get(self, *_args, **_kwargs):
            pytest.fail("session cache inspected before authorization")

    guarded = UnreadableSession(session)
    monkeypatch.setattr(projects.st, "session_state", guarded)
    with pytest.raises(access.AccessDenied):
        projects.activate_project(card)
    with access.access_context(b):
        for reference in (foreign, foreign.removeprefix("fb://")):
            with pytest.raises(access.AccessDenied):
                projects.activate_project({**card, "storage_path": reference})
    assert guarded == before


@pytest.mark.parametrize("stale_reference", ["logical", "foreign", "old-pilot"])
def test_project_activation_reloads_stale_session_identity(tenants, monkeypatch, stale_reference):
    a, b, _, backend = tenants
    path = "livros/same.json"
    card = {"kind": "story", "storage_path": path}
    with access.access_context(a):
        foreign = storage.uri_to_path(storage.storage_uri(path))
    with access.access_context(b):
        backend.put_json(path, {"titulo": "B durable", "private_text": "B only"})
        own = storage.uri_to_path(storage.storage_uri(path))
        stale_path = {"logical": path, "foreign": foreign, "old-pilot": own}[stale_reference]
        stale = {"titulo": "A stale private draft", "private_text": "A only"}
        session = {
            projects.PROJECT_CONTEXT_KEY: {"storage_path": stale_path, "kind": "story"},
            "state": stale, "state_r": stale, "caminho_salvo_r": stale_path,
        }
        monkeypatch.setattr(projects.st, "session_state", session)
        assert projects.activate_project(card)["private_text"] == "B only"
        assert session["caminho_salvo_r"] == own
        assert session[projects.PROJECT_CONTEXT_KEY]["storage_access_mode"] == "multi_tenant"


def test_project_activation_never_substitutes_cached_draft_for_missing_own_book(tenants, monkeypatch):
    a, b, _, backend = tenants
    session = {}
    monkeypatch.setattr(projects.st, "session_state", session)
    card = {"kind": "story", "storage_path": "livros/same.json"}
    with access.access_context(a):
        backend.put_json("livros/same.json", {"titulo": "A private draft", "private_text": "A only"})
        projects.activate_project(card)
    with access.access_context(b):
        # The legacy loader supplies an empty schema for a missing saved book.
        loaded = projects.activate_project(card)
        assert "private_text" not in loaded
        assert loaded.get("titulo") != "A private draft"
        assert session["caminho_salvo_r"] == storage.uri_to_path(storage.storage_uri(card["storage_path"]))


def test_project_activation_keeps_unrelated_open_book_in_current_account(tenants, monkeypatch):
    a, _, _, backend = tenants
    session = {}
    monkeypatch.setattr(projects.st, "session_state", session)
    with access.access_context(a):
        backend.put_json("livros/story.json", {"titulo": "Story"})
        backend.put_json("livros_colorir/color.json", {"titulo": "Color"})
        projects.activate_project({"kind": "story", "storage_path": "livros/story.json"})
        story = session["state_r"]
        story["titulo"] = "Unsaved story edit"
        saved_story = session["caminho_salvo_r"]
        projects.activate_project({"kind": "coloring", "storage_path": "livros_colorir/color.json"})
        assert session["state_r"] is story
        assert session["state_r"]["titulo"] == "Unsaved story edit"
        assert session["caminho_salvo_r"] == saved_story
        assert session["state"] is session["state_c"]


def test_book_doctor_never_lists_pilot_or_other_tenant_cache(tenants):
    a, b, _, _ = tenants
    pilot = doctor.ROOT / "original"
    pilot.mkdir(parents=True)
    (pilot / "projeto.json").write_text(json.dumps({"id": "pilot", "titulo": "Pilot private"}))
    with access.access_context(a):
        pa = doctor.criar_projeto("Same title")
        assert [p["id"] for p in doctor.listar_projetos()] == [pa["id"]]
    with access.access_context(b):
        assert doctor.listar_projetos() == []
        pb = doctor.criar_projeto("Same title")
        assert [p["id"] for p in doctor.listar_projetos()] == [pb["id"]]
        assert a.tenant_id not in pb["pasta"]
    with pytest.raises(access.AccessDenied):
        doctor.listar_projetos()


def test_book_doctor_rehydrates_in_own_root_and_rejects_foreign_cache_before_read(tenants, monkeypatch):
    a, b, _, backend = tenants
    with access.access_context(a):
        project = doctor.criar_projeto("Book")
        source = storage.tenant_local_directory("outputs") / "source.pdf"
        source.write_bytes(b"original-pdf")
        original = doctor.preservar_original(project, str(source), "miolo")
        doctor.gerar_relatorio(project)
        shutil.rmtree(project["pasta"])
        restored = doctor.carregar_projeto(project["id"])
        assert doctor.carregar_relatorio(restored)["projeto_id"] == project["id"]
        assert Path(original).read_bytes() == b"original-pdf"
        # An old durable folder/path field never selects a filesystem destination.
        payload = backend.get_json(f"book_doctor_projects/{project['id']}/projeto.json")
        payload.update(storage_folder="../../pilot-projects", pasta="/untrusted/project")
        backend.put_json(f"book_doctor_projects/{project['id']}/projeto.json", payload)
        assert doctor.carregar_projeto(project["id"])["pasta"] == project["pasta"]
    foreign = Path(project["pasta"]) / "relatorios/book_doctor_report.json"
    original_read = Path.read_text
    def guarded_read(path, *args, **kwargs):
        if path == foreign:
            pytest.fail("foreign cache was read before authorization")
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    with access.access_context(b), pytest.raises(access.AccessDenied):
        doctor._restore_json(project, "relatorios/book_doctor_report.json", foreign)


def test_book_doctor_rejects_viewer_mutations_and_symlink_cache(tenants):
    a, b, _, _ = tenants
    with access.access_context(b):
        foreign = Path(doctor.criar_projeto("Foreign")["pasta"])
    with access.access_context(a):
        root = doctor._local_root()
        root.mkdir(parents=True, exist_ok=True)
        (root / "linked").symlink_to(foreign, target_is_directory=True)
        with pytest.raises(access.AccessDenied):
            doctor.listar_projetos()
    with access.access_context(replace(a, role="viewer")), pytest.raises(access.AccessDenied):
        doctor.criar_projeto("Denied")


def test_generation_histories_budgets_and_identical_requests_are_isolated(tenants):
    a, b, _, _ = tenants
    with access.access_context(a):
        first = generation.iniciar_requisicao("texto", "model", "same request", 0.25)
        with pytest.raises(generation.GeracaoBloqueada):
            generation.iniciar_requisicao("texto", "model", "same request", 0.25)
    with access.access_context(b):
        second = generation.iniciar_requisicao("texto", "model", "same request", 0.5)
        assert first[1] != second[1]
        # Knowing A's signature cannot mutate A's running state.
        generation.liberar_requisicao(first[1])
        generation.finalizar_requisicao(second[0], second[1], "texto", "model", second[2], second[3], "sucesso")
        assert generation.custo_hoje_usd() == 0.5
        assert [r["request_id"] for r in generation.ler_registros()] == [second[0]]
    with access.access_context(a):
        with pytest.raises(generation.GeracaoBloqueada):
            generation.iniciar_requisicao("texto", "model", "same request", 0.25)
        assert generation.custo_hoje_usd() == 0
        generation.finalizar_requisicao(first[0], first[1], "texto", "model", first[2], first[3], "sucesso")
        assert generation.custo_hoje_usd() == 0.25
        assert [r["request_id"] for r in generation.ler_registros()] == [first[0]]
    assert not generation.LOG_PATH.exists()
    assert not generation._IN_FLIGHT


def test_generation_guards_reads_mutations_and_cached_execution_state(tenants):
    a, _, _, _ = tenants
    with pytest.raises(access.AccessDenied):
        generation.ler_registros()
    with access.access_context(replace(a, role="viewer")):
        assert generation.ler_registros() == []
        for operation in (
            lambda: generation.iniciar_requisicao("texto", "model", "denied", 0),
            lambda: generation.liberar_requisicao("known-signature"),
            lambda: generation.atualizar_etapa("known-signature", "aguardando OpenRouter"),
        ):
            with pytest.raises(access.AccessDenied):
                operation()


@pytest.mark.parametrize("operation", ["metadata", "thumbnail", "get_asset", "backfill"])
def test_asset_fallbacks_deny_foreign_local_paths_before_io(tenants, monkeypatch, operation):
    a, b, _, _ = tenants
    with access.access_context(a):
        foreign = storage.tenant_local_directory("outputs") / "private.png"
        foreign.write_bytes(b"must-never-be-read")
    item = {"id": "imported", "nome": "Imported", "media_kind": "image", "caminho_arquivo": str(foreign)}
    monkeypatch.setattr(assets, "_all_assets", lambda *args, **kwargs: [dict(item)])
    original_read = Path.read_bytes
    def guarded_read(path):
        if path == foreign:
            pytest.fail("foreign asset was read before authorization")
        return original_read(path)
    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with access.access_context(b), pytest.raises(access.AccessDenied):
        if operation == "metadata":
            assets._technical_metadata(item, compute_hash=True)
        elif operation == "thumbnail":
            assets.get_thumbnail("imported")
        elif operation == "get_asset":
            assets.get_asset("imported")
        else:
            assets.backfill_technical_metadata()


def test_pilot_log_and_request_signature_keep_existing_contract(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    monkeypatch.setattr(generation, "LOG_PATH", tmp_path / "legacy.jsonl")
    monkeypatch.setattr(generation, "_IN_FLIGHT", set())
    monkeypatch.setattr(generation, "_RECENT", {})
    monkeypatch.setattr(generation, "_EXECUTIONS", {})
    assert generation.assinatura_requisicao("texto", "model", "content") == hashlib.sha256(b"texto|model|content").hexdigest()[:24]
    request = generation.iniciar_requisicao("texto", "model", "content", 0)
    assert request[1] in generation._IN_FLIGHT
    generation.finalizar_requisicao(request[0], request[1], "texto", "model", 0, request[3], "sucesso")
    assert generation.LOG_PATH.exists()
    assert "tenant_id" not in generation.ler_registros()[0]


def test_asset_own_local_fallback_still_produces_metadata_and_thumbnail(tenants, monkeypatch):
    from PIL import Image
    a, _, _, _ = tenants
    with access.access_context(a):
        own = storage.tenant_local_directory("outputs") / "own.png"
        Image.new("RGB", (32, 48), "green").save(own)
        item = {"id": "own", "nome": "Own", "media_kind": "image", "caminho_arquivo": str(own)}
        monkeypatch.setattr(assets, "_all_assets", lambda *args, **kwargs: [dict(item)])
        metadata = assets._technical_metadata(item, compute_hash=True)
        assert (metadata["width_px"], metadata["height_px"]) == (32, 48)
        thumbnail = assets.get_thumbnail("own")
        assert Path(thumbnail).is_file()
        assert a.tenant_id in thumbnail


def test_generation_log_symlink_is_denied_before_reading_or_appending(tenants):
    a, b, _, _ = tenants
    with access.access_context(a):
        foreign = generation._log_path(action="storage.write")
        foreign.parent.mkdir(parents=True)
        foreign.write_text("private-log")
    with access.access_context(b):
        local = generation._log_path(action="storage.write")
        local.parent.mkdir(parents=True)
        local.symlink_to(foreign)
        with pytest.raises(access.AccessDenied):
            generation.ler_registros()
        record = generation.RegistroGeracao("id", "now", "texto", "model", "sucesso", "sig", 0)
        with pytest.raises(access.AccessDenied):
            generation._gravar(record)
    assert foreign.read_text() == "private-log"

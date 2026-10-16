"""Exact-source HQ, paid gates, human review, durable media and real layouts."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import zipfile

from PIL import Image
from pypdf import PdfReader
import pytest
from streamlit.testing.v1 import AppTest

import armazenamento
import asset_library
import comic_studio as studio
import orchestrator_visual as ov
import storage_backend as storage
import visual_execution as ve


PAGE = Path(__file__).resolve().parents[1] / "pages/58_🗯️_Quadrinhos.py"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    import painel_visual
    # Page-as-entrypoint AppTest has no app.py navigation registry. Exercise all
    # page controls while omitting only shared sidebar navigation links.
    monkeypatch.setattr(painel_visual, "_sidebar_page_link", lambda *_a, **_kw: None)
    backend = storage.LocalStorageBackend(str(tmp_path / "durable"))
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setattr(asset_library, "BACKEND", backend)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    monkeypatch.setattr(ve, "validar_orcamento", lambda _: None)
    monkeypatch.chdir(tmp_path)
    return backend


@pytest.fixture
def source(isolated, tmp_path):
    master = tmp_path / "green-eyes-master.png"
    Image.new("RGB", (400, 300), "green").save(master)
    source = {"book_id": "source-exact-123", "titulo": "Mel aprende a esperar", "colecao": "Jardim",
              "faixa_etaria": "6-8", "idioma_original": "pt-BR", "versiculo_referencia": "Salmo 27:14",
              "personagens": {"Mel": {"descricao_fixa": "Gatinha creme, olhos verdes com brilho e estrelas.", "imagem_referencia": str(master)}},
              "cenas_texto": [{"numero": 1, "texto": "Mel observa uma semente no jardim."},
                             {"numero": 2, "texto": "Mel espera com esperança e cuida da planta."}]}
    source["storage_path"] = armazenamento.salvar_livro(source)
    armazenamento.atualizar_livro_salvo(source["storage_path"], source)
    return source


def script():
    return {"titulo": "A semente", "paginas": [{"numero": 1, "paineis": [
        {"numero": 1, "acao_visual": "Mel observa a semente em um canteiro do jardim.",
         "dialogos": [{"personagem": "Mel", "fala": "Vou cuidar de você!"}], "narracao": "No jardim, Mel aprende a esperar.",
         "sfx": "Plim!", "emocao": "curiosidade", "personagem_foco": "Mel"},
        {"numero": 2, "acao_visual": "Mel rega uma pequena planta sorrindo.", "dialogos": [],
         "narracao": "A paciência também é cuidado.", "sfx": "", "emocao": "alegria", "personagem_foco": "Mel"}]}]}


def comic(source):
    return studio.create_comic(source, source["storage_path"], script=script())


def reviewed(source):
    project = comic(source)
    studio.approve_script(project, "Erica", reviewed=True)
    return project


def candidate(project, tmp_path, panel_id="1:1", color="orange"):
    path = tmp_path / f"panel-{panel_id.replace(':', '-')}-{color}.png"
    Image.new("RGB", (600, 450), color).save(path)
    return studio.attach_panel_image(project, panel_id, str(path))


def complete(source, tmp_path):
    project = reviewed(source)
    for panel_id, color in (("1:1", "orange"), ("1:2", "blue")):
        result = candidate(project, tmp_path, panel_id, color)
        studio.approve_panel_image(project, panel_id, result["asset_id"], "Erica")
    return project


def button(app, label):
    return next(item for item in app.button if item.label == label)


def test_derived_book_preserves_exact_source_masters_and_legacy_library(source, isolated):
    source_path = source["storage_path"].removeprefix("fb://")
    before = isolated.get_bytes(source_path)
    library_before = isolated.get_bytes("bibliotecas_personagens/jardim.json")
    project = comic(source)
    studio.save_comic(project)
    assert project["book_id"] != source["book_id"]
    assert project["storage_path"] != source["storage_path"]
    assert isolated.get_bytes(source_path) == before
    assert isolated.get_bytes("bibliotecas_personagens/jardim.json") == library_before
    assert project["comic_product"]["source_ref"] == source["storage_path"]
    assert project["cenas_texto"] == source["cenas_texto"]
    assert not project["revisao_aprovada"] and not project["pacote_pronto"]
    reopened = studio.load_comic(project["storage_path"])
    assert reopened["book_id"] == project["book_id"]
    assert studio.source_status(reopened)["ok"]
    assert studio.list_comics()[0]["storage_path"] == project["storage_path"]


def test_duplicate_title_does_not_resolve_to_wrong_source(source, isolated):
    other = deepcopy(source)
    other.update(book_id="other-exact-456", storage_path="fb://livros/jardim/other.json")
    other["cenas_texto"][0]["texto"] = "Outra obra com o mesmo título."
    isolated.put_json(other["storage_path"].removeprefix("fb://"), other)
    with pytest.raises(ValueError, match="referência canônica"):
        studio.create_comic(source, other["storage_path"])
    project = comic(source)
    with pytest.raises(ValueError, match="origem canônica"):
        studio.source_status(project, other)


def test_source_overwrite_and_silent_source_mutation_are_blocked(source, isolated):
    project = comic(source)
    before = isolated.get_bytes(source["storage_path"].removeprefix("fb://"))
    project["storage_path"] = source["storage_path"]
    with pytest.raises(ValueError, match="projeto próprio"):
        studio.save_comic(project)
    assert isolated.get_bytes(source["storage_path"].removeprefix("fb://")) == before
    project.pop("storage_path")
    project["personagens"]["Mel"]["descricao_fixa"] = "Olhos azuis diferentes."
    with pytest.raises(ValueError, match="origem desta HQ foram alterados"):
        studio.approve_script(project, "Erica", reviewed=True)


def test_source_status_detects_revised_canonical_story(source):
    project = comic(source)
    source["cenas_texto"][0]["texto"] = "Nova revisão."
    with pytest.raises(ValueError, match="origem foi revisada"):
        studio.source_status(project, source)


@pytest.mark.parametrize("invalid", [None, {}, {"paginas": []}, {"paginas": [{"numero": True, "paineis": []}]},
    {"paginas": [{"numero": 1, "paineis": [{"numero": 1, "acao_visual": ""}]}]}])
def test_invalid_scripts_do_not_destroy_work(source, invalid):
    project = comic(source)
    prior = deepcopy(project["comic_product"])
    with pytest.raises(ValueError):
        studio.set_script(project, invalid)
    assert project["comic_product"] == prior


def test_bad_dialogues_and_duplicate_numbers_are_rejected():
    bad = script()
    bad["paginas"][0]["paineis"][0]["dialogos"] = ["silently dropped dialogue"]
    with pytest.raises(ValueError, match="Cada diálogo"):
        studio.validate_script(bad)
    bad = script()
    bad["paginas"][0]["paineis"][1]["numero"] = 1
    with pytest.raises(ValueError, match="duplicados"):
        studio.validate_script(bad)


def test_default_script_provider_is_single_attempt_no_fallback_and_preserves_source(source, monkeypatch, isolated):
    import openrouter_client
    calls = []
    def provider(system, instruction, **kwargs):
        calls.append(kwargs)
        assert source["cenas_texto"][0]["texto"] in instruction
        return script()
    monkeypatch.setattr(openrouter_client, "chamar_llm", provider)
    monkeypatch.setattr(openrouter_client, "texto_provedor_ativo", lambda: "gemini")
    project = studio.create_comic(source, source["storage_path"])
    before = isolated.get_bytes(source["storage_path"].removeprefix("fb://"))
    with pytest.raises(PermissionError, match="Confirme"):
        studio.generate_script(project)
    studio.generate_script(project, confirmed=True)
    assert calls == [{"no_paid_fallback": True, "no_retries": True}]
    assert project["comic_product"]["script"]["paginas"]
    assert isolated.get_bytes(source["storage_path"].removeprefix("fb://")) == before
    studio.generate_script(project, confirmed=False)
    assert len(calls) == 1


def test_script_provider_is_not_called_if_initial_save_fails(source):
    project = studio.create_comic(source)
    def cannot_save(_):
        raise OSError("storage offline")
    with pytest.raises(OSError, match="storage offline"):
        studio.generate_script(project, lambda **_: pytest.fail("No paid call before checkpoint"), confirmed=True, checkpoint=cannot_save)


def test_script_output_survives_final_save_failure_without_rebuy(source):
    project = studio.create_comic(source)
    calls = []
    def checkpoint(state):
        if state["comic_product"]["script"]:
            raise OSError("final storage unavailable")
        studio.save_comic(state)
    with pytest.raises(OSError, match="final storage"):
        studio.generate_script(project, lambda **_: calls.append(1) or script(), confirmed=True, checkpoint=checkpoint)
    assert project["comic_product"]["script"]
    studio.generate_script(project, lambda **_: pytest.fail("Must not buy the saved result twice"))
    assert len(calls) == 1
    assert studio.load_comic(project["storage_path"])["comic_product"]["script"]


def test_human_review_required_before_final_or_ai_images(source, monkeypatch):
    project = comic(source)
    monkeypatch.setattr(ve, "generate_scene_options", lambda *_a, **_kw: pytest.fail("No provider before review"))
    with pytest.raises(PermissionError, match="Revise e aprove"):
        studio.generate_panel_options(project, "1:1", confirmed=True)
    with pytest.raises(PermissionError, match="Revise e aprove"):
        studio.export_comic(project, "pdf")
    with pytest.raises(ValueError, match="Confirme a revisão"):
        studio.approve_script(project, "Erica")


def test_revision_preserves_history_and_invalidates_candidate_for_changed_panel(source, tmp_path):
    project = complete(source, tmp_path)
    candidate_id = project["comic_product"]["panels"]["1:1"]["candidates"][0]["asset_id"]
    revised = deepcopy(project["comic_product"]["script"]["paginas"][0]["paineis"][0])
    revised["acao_visual"] = "Mel observa a semente em outra pose."
    studio.revise_panel(project, "1:1", revised)
    assert len(project["comic_product"]["script_versions"]) == 1
    assert project["comic_product"]["script_approval"] is None
    assert project["comic_product"]["panels"]["1:1"]["approval"] is None
    assert project["comic_product"]["panels"]["1:2"]["approval"]
    studio.approve_script(project, "Erica", reviewed=True)
    with pytest.raises(ValueError, match="versão anterior"):
        studio.approve_panel_image(project, "1:1", candidate_id, "Erica")


def test_image_import_and_review_never_promote_master(source, tmp_path):
    project = reviewed(source)
    image_path = source["personagens"]["Mel"]["imagem_referencia"]
    original = armazenamento.salvar_na_galeria(image_path, "Official eyes", metadata={"visual_status": "COLOR_MASTER"})
    asset_library.update_asset(original["id"], approved=True, master_roles=["character_master"], visual_status="COLOR_MASTER")
    before = asset_library.get_asset(original["id"], materialize_file=False)
    result = studio.attach_panel_image(project, "1:1", original["storage_uri"])
    assert result["asset_id"] != original["id"]
    assert not asset_library.get_asset(result["asset_id"], materialize_file=False)["approved"]
    with pytest.raises(ValueError, match="Responsável"):
        studio.approve_panel_image(project, "1:1", result["asset_id"], " ")
    assert not asset_library.get_asset(result["asset_id"], materialize_file=False)["approved"]
    studio.approve_panel_image(project, "1:1", result["asset_id"], "Erica")
    assert asset_library.get_asset(original["id"], materialize_file=False) == before
    approved = asset_library.get_asset(result["asset_id"], materialize_file=False)
    assert approved["approved"] and not approved["master_roles"]
    assert project["comic_product"]["panels"]["1:1"]["approval"]["asset_digest"] == sha256(Path(image_path).read_bytes()).hexdigest()


def test_archived_or_replaced_approved_art_cannot_export(source, tmp_path):
    project = complete(source, tmp_path)
    approved = project["comic_product"]["panels"]["1:1"]["approval"]
    asset_library.update_asset(approved["asset_id"], status="archived")
    assert not studio.comic_readiness(project)["ok"]
    with pytest.raises(ValueError, match="não está disponível"):
        studio.export_comic(project, "pdf")
    asset_library.update_asset(approved["asset_id"], status="active", storage_uri="fb://assets/another.png")
    with pytest.raises(ValueError, match="referência da imagem"):
        studio.export_comic(project, "pdf")


def test_preflight_is_bound_to_exact_project_story_and_source(source, isolated):
    project = reviewed(source)
    plan = studio.prepare_visual_plan(project, ["Jardim"], budget_limit_usd=1)
    assert plan["project_id"] == project["book_id"]
    assert plan["source_ref"] == project["storage_path"]
    assert plan["comic_source_ref"] == source["storage_path"]
    from editorial_dispatch import content_fingerprint
    assert plan["source_fingerprint"] == content_fingerprint(isolated.get_json(project["storage_path"].removeprefix("fb://")))
    assert not ov.visual_preflight_status(plan)["ready_for_scene_generation"]
    other = ov.create_visual_plan("another-book", source["titulo"], plan["story_text"])
    with pytest.raises(ValueError, match="pertencer"):
        studio.link_visual_plan(project, other["id"])
    other = ov.create_visual_plan(source["book_id"], source["titulo"], "Different version of the story")
    with pytest.raises(ValueError, match="outra versão"):
        studio.link_visual_plan(project, other["id"])


def test_changed_or_deleted_plan_blocks_before_paid_calls(source, monkeypatch):
    project = reviewed(source)
    plan = studio.prepare_visual_plan(project, ["Jardim"])
    plan["project_id"] = "forged-book"
    ov.save_visual_plan(plan)
    monkeypatch.setattr(ve, "generate_scene_options", lambda *_a, **_kw: pytest.fail("No provider for wrong source"))
    with pytest.raises(ValueError, match="identidade e ao conteúdo"):
        studio.generate_panel_options(project, "1:1", confirmed=True)


def central_preflight(source):
    import editorial_dispatch as dispatch
    run = dispatch.create_editorial_run("children_story", source["titulo"], "Cuidar da semente")
    run.update(source=deepcopy(source), source_ref=source["storage_path"])
    dispatch.save_run(run)
    return dispatch.bind_visual_plan_to_run(run["id"], characters=[], locations=[])


def test_exact_central_run_preflight_reopens_and_passes_hq_gate_without_network(source, isolated, monkeypatch):
    import requests
    monkeypatch.setattr(requests.Session, "request", lambda *_a, **_kw: pytest.fail("HQ binding must stay offline"))
    original = isolated.get_bytes(source["storage_path"].removeprefix("fb://"))
    project = reviewed(source)
    plan = central_preflight(source)
    assert plan["project_id"] not in {project["book_id"], source["book_id"]}
    assert "\n\n" in plan["story_text"]
    studio.link_visual_plan(project, plan["id"])
    # Existing author approval of the script does not approve the visual plan.
    with pytest.raises(PermissionError, match="história não aprovada"):
        studio._visual_gate(project)
    plan = ov.approve_style(ov.approve_story(plan), {"name": "Pastel"})
    reopened = studio.load_comic(project["storage_path"])
    assert studio._visual_gate(reopened) == plan["id"]
    assert isolated.get_bytes(source["storage_path"].removeprefix("fb://")) == original


@pytest.mark.parametrize("mismatch", ["same_title_other_reference", "wrong_hash", "missing_hash", "forged_run", "revised_text", "replaced_identity"])
def test_central_plan_requires_exact_source_hash_and_identity(source, isolated, monkeypatch, mismatch):
    import requests
    import editorial_dispatch as dispatch
    monkeypatch.setattr(requests.Session, "request", lambda *_a, **_kw: pytest.fail("Rejected HQ must stay offline"))
    project = reviewed(source)
    before = isolated.get_bytes(project["storage_path"].removeprefix("fb://"))
    plan = central_preflight(source)
    if mismatch == "same_title_other_reference":
        other = deepcopy(source)
        other.update(book_id="another-edition", storage_path="fb://livros/other.json")
        isolated.put_json("livros/other.json", other)
        plan.update(source_ref=other["storage_path"], source_fingerprint=dispatch.content_fingerprint(other))
    elif mismatch == "wrong_hash":
        plan["source_fingerprint"] = "0" * 64
    elif mismatch == "missing_hash":
        plan.pop("source_fingerprint")
    elif mismatch == "forged_run":
        plan["project_id"] = "forged-project"
    else:
        current = isolated.get_json(source["storage_path"].removeprefix("fb://"))
        if mismatch == "revised_text":
            current["cenas_texto"][0]["texto"] = "Outra edição da história."
        else:
            # A content hash alone does not include the immutable book ID.
            current["book_id"] = "replacement-book"
        isolated.put_json(source["storage_path"].removeprefix("fb://"), current)
    ov.save_visual_plan(plan)
    with pytest.raises((ValueError, PermissionError)):
        studio.link_visual_plan(project, plan["id"])
    assert not project["comic_product"]["visual_plan_id"]
    assert isolated.get_bytes(project["storage_path"].removeprefix("fb://")) == before


def test_linked_central_plan_rechecks_persisted_source_before_paid_panel_options(source, isolated, monkeypatch):
    project = reviewed(source)
    plan = central_preflight(source)
    plan = ov.approve_style(ov.approve_story(plan), {"name": "Pastel"})
    studio.link_visual_plan(project, plan["id"])
    current = isolated.get_json(source["storage_path"].removeprefix("fb://"))
    current["personagens"]["Mel"]["descricao_fixa"] = "Outra cor de olhos."
    isolated.put_json(source["storage_path"].removeprefix("fb://"), current)
    monkeypatch.setattr(ve, "generate_scene_options", lambda *_a, **_kw: pytest.fail("No provider for stale source"))
    with pytest.raises(ValueError, match="identidade e ao conteúdo"):
        studio.generate_panel_options(project, "1:1", confirmed=True)


@pytest.mark.parametrize("format", ["pdf", "epub"])
def test_real_export_contains_reviewed_art_dialogues_narration_and_sfx(source, isolated, tmp_path, format):
    project = complete(source, tmp_path)
    report = studio.comic_readiness(project)
    assert report["ok"] and not report["publication_ready"]
    result = studio.export_comic(project, format, output_path=str(tmp_path / ("hq." + format)))
    assert result["pages"] == 1 and not result["draft"]
    assert not result["publication_ready"] and not result["print_ready"] and not result["epubcheck_passed"]
    if format == "pdf":
        pdf = PdfReader(result["path"])
        assert len(pdf.pages) == 1 and len(pdf.pages[0].images) == 2
        text = pdf.pages[0].extract_text()
        assert "Mel: Vou cuidar de você!" in text and "Plim!" in text and "paciência" in text
    else:
        with zipfile.ZipFile(result["path"]) as archive:
            assert archive.namelist()[0] == "mimetype"
            assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
            page = archive.read("EPUB/page_001.xhtml").decode()
            assert page.count('<section class="panel"') == 2
            assert "Vou cuidar de você!" in page and "Plim!" in page and "narration" in page
            assert len([name for name in archive.namelist() if name.startswith("EPUB/images/")]) == 2
            assert "rendition:layout" in archive.read("EPUB/package.opf").decode()
    reopened = studio.load_comic(project["storage_path"])
    assert reopened["comic_product"]["exports"][-1]["storage_ref"] == result["storage_ref"]
    assert Path(storage.materializar(result["storage_ref"])).read_bytes() == Path(result["path"]).read_bytes()


def test_draft_export_has_explicit_placeholders_and_cannot_claim_ready(source, tmp_path):
    project = comic(source)
    result = studio.export_comic(project, "pdf", output_path=str(tmp_path / "draft.pdf"), draft=True)
    text = PdfReader(result["path"]).pages[0].extract_text()
    assert "RASCUNHO" in text and "Ilustração pendente" in text
    assert result["draft"] and not result["publication_ready"]


def test_excess_text_fails_instead_of_clipping_over_panel(source, tmp_path):
    project = comic(source)
    project["comic_product"]["script"]["paginas"][0]["paineis"][0]["narracao"] = "Fala muito extensa. " * 400
    with pytest.raises(ValueError, match="não cabe com legibilidade"):
        studio.export_comic(project, "pdf", output_path=str(tmp_path / "clipped.pdf"), panels_per_page=6, draft=True)


def test_ui_creates_from_canonical_source_and_reopens_same_project(source, isolated, monkeypatch):
    monkeypatch.setattr(ve.client, "chamar_llm", lambda *_a, **_kw: pytest.fail("UI create must not call AI"))
    app = AppTest.from_file(str(PAGE), default_timeout=30)
    app.session_state["comic_source_ref"] = source["storage_path"]
    app.run()
    assert not app.exception
    button(app, "Criar HQ sem alterar a história").click().run()
    assert not app.exception
    project = app.session_state["comic_project_state"]
    assert project["comic_product"]["source_ref"] == source["storage_path"]
    assert "Roteiro em JSON" in [item.label for item in app.text_area]
    again = AppTest.from_file(str(PAGE), default_timeout=30)
    again.session_state["comic_project_id"] = project["storage_path"]
    again.run()
    assert not again.exception
    assert again.session_state["comic_project_state"]["book_id"] == project["book_id"]


def test_ui_manual_script_review_and_real_draft_export_without_network(source, isolated, monkeypatch):
    import requests
    monkeypatch.setattr(requests.Session, "request", lambda *_a, **_kw: pytest.fail("No network in manual HQ flow"))
    project = comic(source)
    studio.save_comic(project)
    app = AppTest.from_file(str(PAGE), default_timeout=30)
    app.session_state["comic_project_id"] = project["storage_path"]
    app.run()
    assert not app.exception
    next(item for item in app.text_input if item.label == "Responsável pela revisão e aprovação").set_value("Erica").run()
    next(item for item in app.checkbox if item.label.startswith("Revisei o roteiro")).check().run()
    button(app, "Aprovar esta versão do roteiro").click().run()
    assert not app.exception
    assert app.session_state["comic_project_state"]["comic_product"]["script_approval"]["reviewer"] == "Erica"
    button(app, "Preparar arquivo da HQ").click().run()
    assert not app.exception
    result = app.session_state["comic_project_state"]["comic_product"]["exports"][-1]
    assert result["draft"] and Path(storage.materializar(result["storage_ref"])).read_bytes().startswith(b"%PDF")


def test_ui_wrong_requested_hq_does_not_fall_back_to_old_project(source):
    app = AppTest.from_file(str(PAGE), default_timeout=30)
    app.session_state["comic_project_state"] = comic(source)
    app.session_state["comic_project_id"] = "fb://livros/missing.json"
    app.run()
    assert not app.exception
    assert any("Não foi possível abrir a HQ solicitada" in item.value for item in app.error)
    assert not any(item.label == "Preparar arquivo da HQ" for item in app.button)


def visual_project(source, tmp_path, monkeypatch, *, budget=3):
    import character_universe
    project = reviewed(source)
    plan = studio.prepare_visual_plan(project, ["Jardim"], budget_limit_usd=budget)
    master_file = source["personagens"]["Mel"]["imagem_referencia"]
    master_asset = armazenamento.salvar_na_galeria(master_file, "Master de Mel")
    asset_library.update_asset(master_asset["id"], approved=True, visual_status="COLOR_MASTER")
    official = character_universe.criar_personagem_oficial("Jardim", "Mel", {
        "descricao_master": "Gatinha creme com olhos verdes brilhantes e estrelas na íris",
        "campos_bloqueados": {"olhos": "verde com brilho e estrelas", "pelagem": "creme"},
        "variaveis_permitidas": ["pose", "acao", "emocao", "cenario"]},
        color_master=master_asset["storage_uri"], metadata={"usos_permitidos": ["story"]})
    world_path = tmp_path / "jardim-master.png"
    Image.new("RGB", (500, 350), "pink").save(world_path)
    world_asset = armazenamento.salvar_na_galeria(str(world_path), "Jardim", tipo="cenario")
    world = ov.create_world_master("Jardim", "Jardim", "Canteiro de flores junto à cerca", [world_asset["storage_uri"]])
    world = ov.approve_world_master(world["id"])
    plan = ov.approve_story(plan)
    plan = ov.approve_character_candidate(plan, "Mel", f"official:{official['id']}", master_asset["storage_uri"])
    plan = ov.link_location_approval(plan, "Jardim", world["id"])
    plan = ov.approve_style(plan, {"name": "3D suave, cores pastel"})
    monkeypatch.setattr(ve.client.gemini_client, "GEMINI_API_KEY", "fake-test-only")
    monkeypatch.setattr(ve.client, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(ve.client, "PROVEDOR_TEXTO", "auto")
    calls = {"text": [], "images": []}
    def options(*args, **kwargs):
        calls["text"].append((args, kwargs))
        return {"ideas": [{"id": key, "titulo": f"Ideia {key}", "cenario": f"jardim {key}", "acao": "Mel observa a semente",
                            "poses": {"Mel": "sentada"}, "emocao": "curiosa", "psicologia_cores": "verde pastel", "iluminacao": "manhã",
                            "camera": key, "por_que_funciona": "Foco na ação"} for key in "ABC"]}
    def image(*args, **kwargs):
        n = len(calls["images"])
        calls["images"].append((args, kwargs))
        path = tmp_path / f"generated-panel-{n}.png"
        Image.new("RGB", (500, 350), (30 + n * 20, 100, 150)).save(path)
        return str(path)
    monkeypatch.setattr(ve.client, "chamar_llm", options)
    monkeypatch.setattr(ve.client, "gerar_imagem", image)
    return project, plan, calls, master_asset


def test_real_panel_director_ledger_strict_provider_recovery_and_human_selection(source, isolated, tmp_path, monkeypatch):
    project, plan, calls, master = visual_project(source, tmp_path, monkeypatch)
    original = deepcopy(asset_library.get_asset(master["id"], materialize_file=False))
    with pytest.raises(PermissionError, match="Confirme"):
        studio.generate_panel_options(project, "1:1")
    assert not calls["text"]
    options = studio.generate_panel_options(project, "1:1", confirmed=True)
    assert len(project["comic_product"]["panels"]["1:1"]["options"]) == 3
    assert calls["text"][0][1]["no_paid_fallback"] and calls["text"][0][1]["no_retries"]
    studio.select_panel_direction(project, "1:1", "B", adjustment="Preservar o brilho verde e as estrelas dos olhos.")
    with pytest.raises(PermissionError, match="Confirme"):
        studio.generate_panel_images(project, "1:1")
    assert not calls["images"]
    result = studio.generate_panel_images(project, "1:1", confirmed=True)
    assert len(result["results"]) == 1
    args, kwargs = calls["images"][0]
    assert "verde com brilho e estrelas" in args[0] and "Preservar o brilho verde" in args[0]
    assert kwargs["no_paid_fallback"] and kwargs["no_retries"] and kwargs["strict_provider"] == "gemini"
    assert not project["comic_product"]["panels"]["1:1"]["approval"]
    # A retry reattaches the durable result without a second paid call.
    studio.generate_panel_images(project, "1:1")
    assert len(calls["images"]) == 1
    assert len(project["comic_product"]["panels"]["1:1"]["candidates"]) == 1
    fresh = studio.load_comic(project["storage_path"])
    candidate_id = fresh["comic_product"]["panels"]["1:1"]["candidates"][0]["asset_id"]
    studio.approve_panel_image(fresh, "1:1", candidate_id, "Erica")
    assert fresh["comic_product"]["panels"]["1:1"]["approval"]["reviewer"] == "Erica"
    assert asset_library.get_asset(master["id"], materialize_file=False) == original
    stored_plan = ov.load_visual_plan(plan["id"])
    assert stored_plan["budget_spent_usd"] > 0
    assert stored_plan["budget_actual_usd"] is None
    assert result["governance_receipt"]["allowed_for_mode"]


def test_zero_visual_budget_blocks_all_paid_panel_generation(source, isolated, tmp_path, monkeypatch):
    project, plan, calls, _master = visual_project(source, tmp_path, monkeypatch, budget=0)
    with pytest.raises(PermissionError, match="orçamento"):
        studio.generate_panel_options(project, "1:1", confirmed=True)
    assert not calls["text"] and not calls["images"]


@pytest.mark.parametrize("historical_consent", [False, True])
def test_private_origin_reopens_without_raw_brief_and_needs_fresh_script_consent(source, isolated, historical_consent):
    from governance_runtime import GovernanceBlocked
    source["real_experience"] = {"original_account": "PRIVATE-RAW-NOT-COPIED", "consent_confirmed": historical_consent}
    source["real_life_brief"] = {"raw_experience": "PRIVATE-RAW-NOT-COPIED", "consent_reviewed": historical_consent}
    armazenamento.atualizar_livro_salvo(source["storage_path"], source)
    before = isolated.get_bytes(source["storage_path"].removeprefix("fb://"))
    project = studio.create_comic(source, source["storage_path"])
    studio.save_comic(project)
    project = studio.load_comic(project["storage_path"])
    assert project["comic_product"]["source_data"] == {"origin": "real_experience", "uses_personal_data": True}
    assert "PRIVATE-RAW-NOT-COPIED" not in json.dumps(project)
    calls = []
    provider = lambda **_: calls.append(1) or script()
    with pytest.raises(GovernanceBlocked):
        studio.generate_script(project, provider, confirmed=True)
    assert not calls
    studio.generate_script(project, provider, confirmed=True, consent_confirmed=True)
    assert calls == [1]
    # The first action's consent and receipt are not authority for a new version.
    with pytest.raises(GovernanceBlocked):
        studio.generate_script(project, provider, confirmed=True, new_version=True)
    assert calls == [1]
    assert isolated.get_bytes(source["storage_path"].removeprefix("fb://")) == before
    assert all("PRIVATE-RAW-NOT-COPIED" not in isolated.get_bytes(path).decode()
               for path in isolated.list("governance/") if path.endswith(".json"))


def test_legacy_private_comic_recovers_origin_flag_and_missing_origin_never_allows_ai(source, isolated):
    from governance_runtime import GovernanceBlocked
    project = studio.create_comic(source, source["storage_path"])
    project["comic_product"].pop("source_data")
    studio.save_comic(project)
    source["real_experience"] = {"consent_confirmed": True}
    armazenamento.atualizar_livro_salvo(source["storage_path"], source)
    project = studio.load_comic(project["storage_path"])
    assert studio.uses_personal_data(project)
    with pytest.raises(GovernanceBlocked):
        studio.generate_script(project, lambda **_: pytest.fail("Legacy story consent is insufficient"), confirmed=True)
    isolated.delete(source["storage_path"].removeprefix("fb://"))
    with pytest.raises(ValueError, match="Recupere a história de origem"):
        studio.generate_script(project, lambda **_: pytest.fail("Unknown origin cannot go to AI"), confirmed=True)


def test_private_panel_options_and_images_each_require_current_consent(source, isolated, tmp_path, monkeypatch):
    from governance_runtime import GovernanceBlocked
    source["real_experience"] = {"original_account": "PRIVATE-PANEL-BRIEF", "consent_confirmed": True}
    armazenamento.atualizar_livro_salvo(source["storage_path"], source)
    project, _plan, calls, _master = visual_project(source, tmp_path, monkeypatch)
    with pytest.raises(GovernanceBlocked):
        studio.generate_panel_options(project, "1:1", confirmed=True)
    assert not calls["text"] and not calls["images"]
    studio.generate_panel_options(project, "1:1", confirmed=True, consent_confirmed=True)
    assert len(calls["text"]) == 1
    studio.select_panel_direction(project, "1:1", "A")
    with pytest.raises(GovernanceBlocked):
        studio.generate_panel_images(project, "1:1", confirmed=True)
    assert not calls["images"]
    result = studio.generate_panel_images(project, "1:1", confirmed=True, consent_confirmed=True)
    assert len(calls["images"]) == 1 and result["results"]
    fresh = studio.load_comic(project["storage_path"])
    assert studio.uses_personal_data(fresh)
    with pytest.raises(GovernanceBlocked):
        studio.generate_panel_options(fresh, "1:2", confirmed=True)
    assert len(calls["text"]) == 1
    assert all("PRIVATE-PANEL-BRIEF" not in isolated.get_bytes(path).decode()
               for path in isolated.list("governance/") if path.endswith(".json"))


def test_private_panel_save_failure_prevents_provider_send(source, isolated, tmp_path, monkeypatch):
    source["uses_personal_data"] = True
    armazenamento.atualizar_livro_salvo(source["storage_path"], source)
    project, _plan, calls, _master = visual_project(source, tmp_path, monkeypatch)
    def no_save(_):
        raise OSError("private receipt save unavailable")
    with pytest.raises(OSError, match="receipt save"):
        studio.generate_panel_options(project, "1:1", confirmed=True, consent_confirmed=True, checkpoint=no_save)
    assert not calls["text"] and not calls["images"]


def test_ui_private_script_consent_is_separate_and_consumed_for_one_action(source, monkeypatch):
    import openrouter_client
    source["real_experience"] = {"consent_confirmed": True}
    armazenamento.atualizar_livro_salvo(source["storage_path"], source)
    project = studio.create_comic(source, source["storage_path"])
    studio.save_comic(project)
    calls = []
    monkeypatch.setattr(openrouter_client, "texto_provedor_ativo", lambda: "gemini")
    monkeypatch.setattr(openrouter_client, "chamar_llm", lambda *_a, **_kw: calls.append(1) or script())
    app = AppTest.from_file(str(PAGE), default_timeout=30)
    app.session_state["comic_project_id"] = project["storage_path"]
    app.run()
    assert not app.exception
    next(item for item in app.checkbox if item.label.startswith("Confirmo adaptar")).check().run()
    assert button(app, "Gerar roteiro da HQ").disabled
    consent = next(item for item in app.checkbox if item.label.startswith("Autorizo enviar os dados pessoais desta história"))
    assert not consent.value
    consent.check().run()
    assert not button(app, "Gerar roteiro da HQ").disabled
    button(app, "Gerar roteiro da HQ").click().run()
    assert not app.exception and calls == [1]
    assert not next(item for item in app.checkbox if item.label.startswith("Autorizo enviar os dados pessoais desta história")).value
    next(item for item in app.checkbox if item.label == "Criar outra versão do roteiro com IA").check().run()
    assert button(app, "Gerar roteiro da HQ").disabled
    assert calls == [1]


def test_missing_governance_evidence_blocks_script_provider(source, isolated, monkeypatch):
    import governance_runtime
    def fail_evidence(*_a, **_kw):
        raise PermissionError("governance evidence unavailable")
    monkeypatch.setattr(governance_runtime, "authorize_generation", fail_evidence)
    project = studio.create_comic(source)
    with pytest.raises(PermissionError, match="governance evidence"):
        studio.generate_script(project, lambda **_: pytest.fail("Cannot buy a call without governance evidence"), confirmed=True)

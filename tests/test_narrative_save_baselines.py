"""Narrative edits and received generations survive real competing readers."""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
import json
import multiprocessing
from pathlib import Path

import pytest

import armazenamento as books
import generation_autosave as autosave
import saas_access as access
import storage_backend as storage
import agents.roteirista_autoral as storyteller


PATH = "livros/audit/narrative.json"


@pytest.fixture
def backend(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    value = storage.LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage, "BACKEND", value)
    monkeypatch.setattr(books, "BACKEND", value)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    monkeypatch.chdir(tmp_path)
    return value


def seed(backend, **changes):
    value = {"book_id": "narrative-id", "titulo": "Livro em edição", "colecao": "Audit",
             "faixa_etaria": "6-8", "annotations": {"author": "original", "reviewer": "original"},
             "revisao_aprovada": True, **changes}
    backend.put_json(PATH, value)
    return storage.storage_uri(PATH)


def load(reference):
    return books.carregar_livro("", reference)


def assert_durable_payload_has_no_working_context(backend):
    value = backend.get_json(PATH)
    text = json.dumps(value, ensure_ascii=False)
    assert books.BOOK_SAVE_CONTEXT_KEY not in text
    assert "autosave_pending" not in text


def test_two_editors_merge_different_nested_notes_and_refresh_their_working_copy(backend):
    reference = seed(backend)
    author, reviewer = load(reference), load(reference)
    author["annotations"]["author"] = "A new observation"
    reviewer["annotations"]["reviewer"] = "An independent review"
    books.atualizar_livro_salvo(reference, author)
    books.atualizar_livro_salvo(reference, reviewer)
    expected = {"author": "A new observation", "reviewer": "An independent review"}
    assert backend.get_json(PATH)["annotations"] == expected
    assert reviewer["annotations"] == expected
    assert reviewer["revisao_aprovada"] is True
    assert_durable_payload_has_no_working_context(backend)


def test_same_field_conflict_preserves_edit_and_rejects_before_assets(backend, monkeypatch):
    reference = seed(backend)
    first, second = load(reference), load(reference)
    first["annotations"]["author"] = "Published edit"
    second["annotations"]["author"] = "Unsaved received draft"
    books.atualizar_livro_salvo(reference, first)
    before = backend.get_bytes(PATH)
    monkeypatch.setattr(books, "persistir_assets_em_objeto",
                        lambda *_: pytest.fail("conflicting draft must not inspect/upload media"))
    with pytest.raises(books.BookSaveConflict) as rejected:
        books.atualizar_livro_salvo(reference, second)
    assert "annotations.author" in rejected.value.fields
    assert backend.get_bytes(PATH) == before
    assert second["annotations"]["author"] == "Unsaved received draft"


def test_changed_parent_shape_cannot_be_replaced_by_an_old_nested_edit(backend, monkeypatch):
    reference = seed(backend)
    first, second = load(reference), load(reference)
    first["annotations"] = "A deliberately changed annotation format"
    books.atualizar_livro_salvo(reference, first)
    second["annotations"]["author"] = "An edit using the previous format"
    before = backend.get_bytes(PATH)
    monkeypatch.setattr(books, "persistir_assets_em_objeto",
                        lambda *_: pytest.fail("structural conflict must fail before assets"))
    with pytest.raises(books.BookSaveConflict):
        books.atualizar_livro_salvo(reference, second)
    assert backend.get_bytes(PATH) == before


def test_a_copied_state_without_a_read_baseline_cannot_authorize_replacement(backend, monkeypatch):
    reference = seed(backend)
    snapshot = deepcopy(backend.get_json(PATH))
    snapshot.update(storage_path=reference, titulo="A stale whole snapshot")
    before = backend.get_bytes(PATH)
    monkeypatch.setattr(books, "persistir_assets_em_objeto",
                        lambda *_: pytest.fail("a missing baseline must fail before asset preparation"))
    with pytest.raises(books.BookSaveConflict) as rejected:
        books.atualizar_livro_salvo(reference, snapshot)
    assert rejected.value.missing_baseline is True
    assert backend.get_bytes(PATH) == before


def test_working_handle_is_opaque_and_resolver_copies_cannot_change_the_baseline(backend):
    reference = seed(backend, private_editorial_note="Saved editorial annotation")
    state = load(reference)
    carrier = state[books.BOOK_SAVE_CONTEXT_KEY]
    assert set(carrier) == {"schema", "path", "token"}
    assert "Saved editorial annotation" not in json.dumps(carrier)
    copied = books.get_book_read_context(state, reference)
    copied["raw"]["annotations"]["author"] = "Forged expected value"
    assert books.get_book_read_context(state, reference)["raw"]["annotations"]["author"] == "original"
    state["annotations"]["author"] = "A legitimate edit"
    books.atualizar_livro_salvo(reference, state)
    assert backend.get_json(PATH)["annotations"]["author"] == "A legitimate edit"


def test_evicted_read_context_preserves_received_output_and_requires_explicit_review(backend, monkeypatch):
    reference = seed(backend, licao_final="Original lesson")
    state = load(reference)
    token = state[books.BOOK_SAVE_CONTEXT_KEY]["token"]
    with books._BOOK_READ_LOCK:
        books._BOOK_READ_CONTEXTS.pop(token)
    before = backend.get_bytes(PATH)
    with monkeypatch.context() as guarded:
        guarded.setattr(books, "persistir_assets_em_objeto",
                        lambda *_: pytest.fail("expired baseline must reject before media preparation"))
        with pytest.raises(books.BookSaveConflict) as rejected:
            autosave.persist_generation_snapshot(state, reason="received", updates={"licao_final": "Received lesson"})
    assert rejected.value.missing_baseline is True
    assert state["autosave_pending"]["draft"]["licao_final"] == "Received lesson"
    assert backend.get_bytes(PATH) == before
    autosave.reload_pending_generation_source(state)
    with pytest.raises(PermissionError):
        autosave.retry_pending_generation_save(state)
    autosave.apply_pending_generation_result(state, confirmed=True)
    assert backend.get_json(PATH)["licao_final"] == "Received lesson"


def test_bounded_read_registry_fails_closed_for_the_evicted_oldest_handle(backend, monkeypatch):
    reference = seed(backend)
    monkeypatch.setattr(books, "_BOOK_READ_CONTEXTS", books.OrderedDict())
    monkeypatch.setattr(books, "_BOOK_READ_MAX_CONTEXTS", 2)
    oldest = load(reference)
    recent = load(reference)
    newest = load(reference)
    assert len(books._BOOK_READ_CONTEXTS) == 2
    with pytest.raises(books.BookSaveConflict):
        books.get_book_read_context(oldest, reference)
    assert books.get_book_read_context(recent, reference)["raw"]["book_id"] == "narrative-id"
    assert books.get_book_read_context(newest, reference)["raw"]["book_id"] == "narrative-id"


def test_legacy_schema_defaults_from_two_reads_do_not_conflict_or_erase_notes(backend, monkeypatch):
    import stable_hardening
    reference = seed(backend)
    monkeypatch.setattr(stable_hardening, "_now", lambda: "first-read")
    first = load(reference)
    monkeypatch.setattr(stable_hardening, "_now", lambda: "second-read")
    second = load(reference)
    first["annotations"]["author"] = "Author note"
    second["annotations"]["reviewer"] = "Reviewer note"
    books.atualizar_livro_salvo(reference, first)
    books.atualizar_livro_salvo(reference, second)
    saved = backend.get_json(PATH)
    assert saved["annotations"] == {"author": "Author note", "reviewer": "Reviewer note"}
    assert saved["authorship"]["updated_at"] == "first-read"


def test_unchanged_materialized_media_keeps_its_uri_without_reupload(backend, monkeypatch):
    backend.put_bytes("assets/reference.png", b"original master bytes", "image/png")
    reference = seed(backend, imagem_capa="fb://assets/reference.png")
    state = load(reference)
    assert Path(state["imagem_capa"]).read_bytes() == b"original master bytes"
    uploads = []
    put = backend.put_bytes

    def counted(path, data, content_type=None):
        uploads.append(path)
        return put(path, data, content_type)

    monkeypatch.setattr(backend, "put_bytes", counted)
    state["annotations"]["author"] = "Text-only change"
    books.atualizar_livro_salvo(reference, state)
    assert backend.get_json(PATH)["imagem_capa"] == "fb://assets/reference.png"
    assert uploads == []
    assert Path(state["imagem_capa"]).read_bytes() == b"original master bytes"


def test_lost_commit_ack_retries_only_persistence_of_the_received_storyteller_output(backend, monkeypatch):
    reference = seed(backend)
    state = load(reference)
    calls = []
    update = backend.update_json
    lose_ack = [True]

    def commit_then_timeout(path, mutator, default=None, **kwargs):
        result = update(path, mutator, default, **kwargs)
        if lose_ack and lose_ack.pop():
            raise storage.StorageUnavailable("acknowledgement lost after commit")
        return result

    monkeypatch.setattr(backend, "update_json", commit_then_timeout)

    def provider(**kwargs):
        calls.append(kwargs)
        return {"direcao_narrativa": "A received paid proposal", "estilo_recomendado": "misto"}

    result = storyteller.gerar_proposta_roteirista(state, provider)
    assert len(calls) == 1
    assert state["proposta_roteirista"] == result
    assert state["autosave_pending"]["draft"]["proposta_roteirista"] == result
    assert backend.get_json(PATH)["proposta_roteirista"] == result
    assert autosave.retry_pending_generation_save(state) == reference
    assert len(calls) == 1
    assert state["proposta_roteirista"] == result
    assert "autosave_pending" not in state
    assert_durable_payload_has_no_working_context(backend)


def test_review_confirmation_cannot_launder_a_newer_conflict_after_reopening(backend):
    reference = seed(backend, proposta_roteirista={"direcao_narrativa": "Original"})
    state, editor = load(reference), load(reference)
    editor["proposta_roteirista"]["direcao_narrativa"] = "First concurrent edit"
    books.atualizar_livro_salvo(reference, editor)
    calls = []

    def provider(**kwargs):
        calls.append(kwargs)
        return {"direcao_narrativa": "Received proposal", "estilo_recomendado": "misto"}

    received = storyteller.gerar_proposta_roteirista(state, provider)
    assert state["autosave_status"] == "error" or state["autosave_status"] == "conflict"
    assert state["autosave_pending"]["draft"]["proposta_roteirista"] == received
    autosave.reload_pending_generation_source(state)
    assert state["autosave_status"] == "needs_review"
    assert state["proposta_roteirista"]["direcao_narrativa"] == "First concurrent edit"
    late_editor = load(reference)
    late_editor["proposta_roteirista"]["direcao_narrativa"] = "Another edit after review opened"
    books.atualizar_livro_salvo(reference, late_editor)
    with pytest.raises(books.BookSaveConflict):
        autosave.apply_pending_generation_result(state, confirmed=True)
    assert len(calls) == 1
    assert backend.get_json(PATH)["proposta_roteirista"]["direcao_narrativa"] == "Another edit after review opened"
    assert state["autosave_pending"]["draft"]["proposta_roteirista"] == received


def test_explicit_review_applies_received_fields_and_keeps_unrelated_current_notes(backend):
    reference = seed(backend, proposta_roteirista={"direcao_narrativa": "Original"})
    state, editor = load(reference), load(reference)
    editor["proposta_roteirista"]["direcao_narrativa"] = "Concurrent direction"
    editor["annotations"]["reviewer"] = "Keep this human review"
    books.atualizar_livro_salvo(reference, editor)
    with pytest.raises(books.BookSaveConflict):
        autosave.persist_generation_snapshot(state, reason="received", updates={
            "proposta_roteirista": {"direcao_narrativa": "Received output"}})
    with pytest.raises(PermissionError):
        autosave.apply_pending_generation_result(state, confirmed=True)
    autosave.reload_pending_generation_source(state)
    with pytest.raises(PermissionError):
        autosave.apply_pending_generation_result(state)
    assert autosave.apply_pending_generation_result(state, confirmed=True) == reference
    saved = backend.get_json(PATH)
    assert saved["proposta_roteirista"]["direcao_narrativa"] == "Received output"
    assert saved["annotations"]["reviewer"] == "Keep this human review"
    assert state["annotations"]["reviewer"] == "Keep this human review"
    assert "autosave_pending" not in state
    assert_durable_payload_has_no_working_context(backend)


def test_plain_retry_after_reopening_requires_review_and_keeps_the_received_draft(backend):
    reference = seed(backend, licao_final="Original lesson")
    state, editor = load(reference), load(reference)
    editor["licao_final"] = "A newer human lesson"
    books.atualizar_livro_salvo(reference, editor)
    with pytest.raises(books.BookSaveConflict):
        autosave.persist_generation_snapshot(state, reason="received", updates={"licao_final": "A paid received lesson"})
    autosave.reload_pending_generation_source(state)
    pending = deepcopy(state["autosave_pending"])
    before = backend.get_bytes(PATH)
    with pytest.raises(PermissionError):
        autosave.retry_pending_generation_save(state)
    assert backend.get_bytes(PATH) == before
    assert state["autosave_pending"] == pending
    assert pending["draft"]["licao_final"] == "A paid received lesson"


def test_callback_replay_merges_latest_fields_and_never_uploads_inside_callback(backend, monkeypatch):
    reference = seed(backend)
    state = load(reference)
    state["annotations"]["author"] = "Generated checkpoint"
    update = backend.update_json
    invocations, preparations = [], []
    prepare = books.persistir_assets_em_objeto

    def prepare_once(value, prefix):
        preparations.append(1)
        return prepare(value, prefix)

    def conflicted(path, mutator, default=None, **kwargs):
        invocations.append(deepcopy(mutator(backend.get_json(path, default))))
        update(path, lambda book: {**book, "annotations": {**book["annotations"], "reviewer": "Arrived during CAS retry"}}, default)

        def replay(current):
            result = mutator(current)
            invocations.append(deepcopy(result))
            return result

        return update(path, replay, default, **kwargs)

    monkeypatch.setattr(books, "persistir_assets_em_objeto", prepare_once)
    monkeypatch.setattr(backend, "update_json", conflicted)
    books.atualizar_livro_salvo(reference, state)
    assert len(invocations) == 2
    assert len(preparations) == 1
    assert state["annotations"] == {"author": "Generated checkpoint", "reviewer": "Arrived during CAS retry"}
    assert_durable_payload_has_no_working_context(backend)


def _edit_process(root, cache, reference, barrier, field, result):
    try:
        value = storage.LocalStorageBackend(root)
        storage.BACKEND = books.BACKEND = value
        storage.CACHE_DIR = Path(cache)
        storage.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        state = load(reference)
        state["annotations"][field] = "Saved by " + field
        barrier.wait(10)
        books.atualizar_livro_salvo(reference, state)
        result.put((field, "saved"))
    except BaseException as exc:
        result.put((field, type(exc).__name__ + ": " + str(exc)))
        raise


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="Linux file-lock workers")
def test_independent_processes_with_the_same_read_keep_both_edits(backend, tmp_path):
    reference = seed(backend)
    context = multiprocessing.get_context("fork")
    barrier, results = context.Barrier(2), context.Queue()
    processes = [context.Process(target=_edit_process,
        args=(str(backend.root), str(tmp_path / ("cache-" + field)), reference, barrier, field, results))
        for field in ("author", "reviewer")]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(15)
        assert all(not process.is_alive() and process.exitcode == 0 for process in processes)
        assert sorted(results.get(timeout=3) for _ in processes) == [("author", "saved"), ("reviewer", "saved")]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(3)
    assert backend.get_json(PATH)["annotations"] == {"author": "Saved by author", "reviewer": "Saved by reviewer"}


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://identity.example")
    monkeypatch.delenv("FAITHBLOOM_ACCESS_ROLES", raising=False)
    a, b = [access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": name})
            for name in ("narrative-a", "narrative-b")]
    raw = storage.LocalStorageBackend(str(tmp_path / "private"))
    value = storage.TenantStorageBackend(raw)
    monkeypatch.setattr(storage, "BACKEND", value)
    monkeypatch.setattr(books, "BACKEND", value)
    monkeypatch.setattr(storage, "CACHE_DIR", tmp_path / "cache")
    return a, b, raw, value


@pytest.mark.parametrize("who", ["other", "missing", "viewer"])
def test_foreign_or_unauthenticated_baseline_never_reaches_document_or_assets(accounts, monkeypatch, who):
    a, b, raw, backend = accounts
    with access.access_context(a):
        reference = seed(backend)
        state = load(reference)
        before = backend.get_bytes(PATH)
    actor = {"other": b, "missing": None, "viewer": replace(a, role="viewer")}[who]
    state["annotations"]["author"] = "Must not be written"
    with monkeypatch.context() as guarded:
        guarded.setattr(raw, "get_bytes", lambda *_: pytest.fail("rejected reference must authorize before document IO"))
        guarded.setattr(books, "persistir_assets_em_objeto", lambda *_: pytest.fail("rejected reference must not inspect assets"))
        with access.access_context(actor) if actor is not None else nullcontext():
            with pytest.raises(access.AccessDenied):
                books.atualizar_livro_salvo(reference, state)
    with access.access_context(a):
        assert backend.get_bytes(PATH) == before


def test_same_logical_path_in_another_account_cannot_adopt_the_old_context(accounts):
    a, b, _, backend = accounts
    with access.access_context(a):
        reference_a = seed(backend)
        stale_a = load(reference_a)
    with access.access_context(b):
        reference_b = seed(backend, titulo="B's book")
        before = backend.get_bytes(PATH)
        stale_a["storage_path"] = reference_b
        with pytest.raises(books.BookSaveConflict):
            books.atualizar_livro_salvo(reference_b, stale_a)
        assert backend.get_bytes(PATH) == before


def test_new_draft_receives_a_real_context_then_reopens_and_continues_same_book(backend):
    state = {"book_id": "new-narrative", "titulo": "A new draft", "colecao": "Audit"}
    reference = autosave.persist_generation_snapshot(state, reason="initial received", updates={"cenas_texto": [{"numero": 1, "texto": "First received scene"}]})
    assert books.BOOK_SAVE_CONTEXT_KEY in state
    assert "autosave_pending" not in state
    assert state["storage_path"] == reference
    assert len(backend.list("livros")) == 1
    reopened = load(reference)
    autosave.persist_generation_snapshot(reopened, reason="continued", updates={"licao_final": "A received final lesson"})
    autosave.persist_generation_snapshot(reopened, reason="next checkpoint", updates={"sinopse_poetica": "A received synopsis"})
    assert reopened["storage_path"] == reference
    assert len(backend.list("livros")) == 1
    raw = backend.get_json(storage.uri_to_path(reference))
    assert raw["book_id"] == "new-narrative"
    assert raw["licao_final"] == "A received final lesson"
    assert raw["cenas_texto"][0]["texto"] == "First received scene"
    encoded = json.dumps(raw)
    assert books.BOOK_SAVE_CONTEXT_KEY not in encoded and "autosave_pending" not in encoded


def test_compiled_pipeline_checkpoint_retains_saved_metadata_outside_the_state_schema(backend, monkeypatch):
    import graph
    import emotional_visual_binding
    reference = seed(backend, private_editorial_note="Keep this saved annotation")
    state = load(reference)
    monkeypatch.setattr(graph, "curador_tema_node", lambda state, *_: state)
    monkeypatch.setattr(graph, "roteirista_node", lambda state, *_: state)

    def reviewed(state, *_):
        state["revisao_aprovada"] = True
        state["licao_final"] = "A checkpoint received from the reviewed pipeline"
        return state

    monkeypatch.setattr(graph, "revisor_node", reviewed)
    monkeypatch.setattr(emotional_visual_binding, "require_book_emotional_map", lambda _: {"approved": True})
    stages = ["_complementos_node", "ilustrador_node", "atividades_colorir_node", "audiobook_node",
              "narracao_node", "dedicatoria_node", "tradutor_node", "sinopse_node",
              "pesquisa_palavras_chave_node", "pesquisa_categorias_node", "diagramador_node",
              "capa_node", "marketing_lancamento_node"]
    for stage in stages:
        monkeypatch.setattr(graph, stage, lambda state, *_: state)
    result = graph.construir_grafo(None, None, None).invoke(state)
    assert result.get("pipeline_status") != "awaiting_generation_save"
    saved = backend.get_json(PATH)
    assert saved["licao_final"] == "A checkpoint received from the reviewed pipeline"
    assert saved["private_editorial_note"] == "Keep this saved annotation"
    assert saved["annotations"] == {"author": "original", "reviewer": "original"}
    assert_durable_payload_has_no_working_context(backend)


def test_compiled_pipeline_pauses_after_received_checkpoint_fails_without_buying_next_stage(backend, monkeypatch):
    import graph
    reference = seed(backend)
    state = load(reference)
    events = []
    monkeypatch.setattr(graph, "curador_tema_node", lambda state, *_: state)

    def received(state, *_):
        events.append("received")
        autosave.persist_generation_snapshot(state, reason="story_received",
            updates={"cenas_texto": [{"numero": 1, "texto": "An already received scene"}]})
        return state

    monkeypatch.setattr(graph, "roteirista_node", received)
    monkeypatch.setattr(graph, "revisor_node", lambda *_: pytest.fail("must not buy the next stage"))
    monkeypatch.setattr(backend, "update_json", lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(storage.StorageUnavailable("Storage temporarily unavailable")))
    result = graph.construir_grafo(None, None, None).invoke(state)
    assert result["pipeline_status"] == "awaiting_generation_save"
    assert result["autosave_pending"]["draft"]["cenas_texto"][0]["texto"] == "An already received scene"
    assert events == ["received"]


def test_compiled_pipeline_rejects_an_expired_handle_before_any_provider_stage(backend, monkeypatch):
    import graph
    reference = seed(backend)
    state = load(reference)
    with books._BOOK_READ_LOCK:
        books._BOOK_READ_CONTEXTS.pop(state[books.BOOK_SAVE_CONTEXT_KEY]["token"])
    monkeypatch.setattr(graph, "curador_tema_node", lambda *_: pytest.fail("expired handle before provider"))
    with pytest.raises(books.BookSaveConflict):
        graph.construir_grafo(None, None, None).invoke(state)

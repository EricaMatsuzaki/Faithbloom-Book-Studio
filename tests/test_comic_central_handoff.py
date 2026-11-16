"""Central HQ handoff preserves exact sources and the existing user's projects."""
from copy import deepcopy

import pytest

import armazenamento
import editorial_dispatch as dispatch
import storage_backend as storage


@pytest.fixture
def durable(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    return backend


def saved_run(kind="comic", audience="3_8", text="A história escolhida."):
    run = dispatch.create_editorial_run(kind, "Mesmo título", "Uma ideia", collection="Coleção", audience=audience)
    run = dispatch.initialize_specialist(run["id"])
    source = run["source"]
    source["cenas_texto"] = [{"numero": 1, "texto": text}] if text else []
    source["personagens"] = {"Mel": {"descricao_fixa": "Olhos verdes com brilho próprio."}}
    armazenamento.atualizar_livro_salvo(run["source_ref"], source)
    return dispatch.sync_source(run["id"])


def test_same_title_handoff_uses_exact_saved_source_and_clears_only_hq_context(durable):
    first = saved_run(text="Fonte A.")
    second = saved_run(text="Fonte B.")
    untouched = durable.get_bytes(first["source_ref"].removeprefix("fb://"))
    old_state = {"titulo": "Livro que estava aberto", "storage_path": first["source_ref"]}
    session = {"state": old_state, "comic_project_id": "previous", "comic_project_state": {"old": True}, "comic_source_opened_ref": first["source_ref"]}
    result = dispatch.prepare_comic_handoff(session, second["id"])
    assert result["id"] == second["id"]
    assert session["comic_source_ref"] == second["source_ref"]
    assert session["comic_source_state"]["cenas_texto"][0]["texto"] == "Fonte B."
    assert session["state"] is old_state
    assert "comic_project_state" not in session and "comic_project_id" not in session
    assert durable.get_bytes(first["source_ref"].removeprefix("fb://")) == untouched


def test_empty_story_cannot_replace_a_previous_hq_context(durable):
    run = saved_run(text="")
    session = {"comic_project_id": "previous"}
    with pytest.raises(ValueError, match="história-base"):
        dispatch.prepare_comic_handoff(session, run["id"])
    assert session == {"comic_project_id": "previous"}


def test_adult_comic_cannot_silently_enter_a_child_story_pipeline(durable):
    run = saved_run(audience="adult")
    with pytest.raises(ValueError, match="infantis"):
        dispatch.studio_session_context(run)
    with pytest.raises(ValueError):
        dispatch.prepare_comic_handoff({}, run["id"])


def test_real_experience_markers_reach_hq_without_automatic_consent(durable):
    run = saved_run(kind="real_life_story")
    session = {}
    dispatch.prepare_comic_handoff(session, run["id"])
    source = session["comic_source_state"]
    assert source["real_experience"]["consent_confirmed"] is False
    assert source["storage_path"] == run["source_ref"]
    assert source["personagens"] == run["source"]["personagens"]

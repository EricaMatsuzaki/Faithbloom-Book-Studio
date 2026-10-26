"""Saved-book screens keep exact identities and received results through I/O failure."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import armazenamento as books
import generation_autosave as autosave
import storage_backend as storage


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def backend(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    value = storage.LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage, "BACKEND", value)
    monkeypatch.setattr(books, "BACKEND", value)
    monkeypatch.setattr(storage, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr("estilo.aplicar_estilo", lambda: None)
    monkeypatch.setattr("estilo.hero", lambda *_args, **_kwargs: None)
    monkeypatch.chdir(tmp_path)
    for suffix in ("a", "b"):
        value.put_json(f"livros/audit/{suffix}.json", {
            "book_id": suffix, "titulo": "Mesmo título", "colecao": "Audit", "faixa_etaria": "6-8",
            "private_note": f"Original {suffix}", "cenas_texto": []})
    return value


def button(app, label):
    return next(item for item in app.button if item.label == label)


def test_launch_save_updates_exact_selected_book_without_duplicating_homonymous_projects(backend):
    first_before = backend.get_bytes("livros/audit/a.json")
    app = AppTest.from_file(str(ROOT / "app.py")).switch_page("pages/7_🚀_Lançamento.py").run(timeout=20)
    assert not app.exception
    assert len(app.selectbox[0].options) == 2
    app.selectbox[0].set_value("livros/audit/b.json").run(timeout=20)
    next(item for item in app.text_input if item.label == "Subtítulo").set_value("Revisão do livro B")
    button(app, "💾 Salvar alterações neste livro").click().run(timeout=20)
    assert not app.exception
    assert len(backend.list("livros")) == 2
    assert backend.get_bytes("livros/audit/a.json") == first_before
    saved = backend.get_json("livros/audit/b.json")
    assert saved["book_id"] == "b"
    assert saved["subtitulo"] == "Revisão do livro B"
    assert app.session_state["state_lancamento"]["storage_path"] == "fb://livros/audit/b.json"
    assert books.BOOK_SAVE_CONTEXT_KEY in app.session_state["state_lancamento"]


def test_direct_stage_keeps_received_result_and_retries_only_the_save(backend, monkeypatch):
    provider = Mock(return_value="Uma cena já recebida")

    def received(state, _llm):
        result = provider()
        autosave.persist_generation_snapshot(state, reason="received", updates={
            "cenas_texto": [{"numero": 1, "texto": result}]})
        return state

    monkeypatch.setattr("agents.roteirista.roteirista_node", received)
    app = AppTest.from_file(str(ROOT / "pages/4_🎯_Ir_Direto_para_Etapa.py")).run(timeout=20)
    assert not app.exception
    with monkeypatch.context() as guarded:
        guarded.setattr(backend, "update_json", lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(storage.StorageUnavailable("Não foi possível salvar agora")))
        button(app, "▶️ Rodar: Roteirista (reescreve a história)").click().run(timeout=20)
    assert not app.exception
    provider.assert_called_once()
    state = app.session_state["state_etapa"]
    assert state["autosave_pending"]["draft"]["cenas_texto"][0]["texto"] == "Uma cena já recebida"
    app.run(timeout=20)
    assert not app.exception
    assert not any(item.label.startswith("▶️ Rodar:") for item in app.button)
    button(app, "Tentar salvar resultado recebido").click().run(timeout=20)
    assert not app.exception
    provider.assert_called_once()
    assert "autosave_pending" not in app.session_state["state_etapa"]
    path = storage.uri_to_path(app.session_state["state_etapa"]["storage_path"])
    assert backend.get_json(path)["cenas_texto"][0]["texto"] == "Uma cena já recebida"

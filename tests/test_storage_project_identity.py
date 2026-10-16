from pathlib import Path
import pytest

import generation_autosave
import storage_backend as storage
import armazenamento


def test_loading_autosaved_story_preserves_project_uri_and_updates_same_book(monkeypatch, tmp_path):
    backend = storage.LocalStorageBackend(tmp_path / "backend")
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    image = tmp_path / "master.png"
    image.write_bytes(b"original test image bytes")
    original = {"colecao": "Audit", "titulo": "Book A", "cenas_imagem": [{"numero": 1, "caminho_arquivo": str(image)}]}
    target = armazenamento.salvar_livro(original)
    original["storage_path"] = target
    original["autosave_last_path"] = target
    original["source_ref"] = target
    armazenamento.atualizar_livro_salvo(target, original)

    loaded = armazenamento.carregar_livro("Audit", target.removeprefix("fb://"))
    assert loaded["storage_path"] == target
    assert loaded["autosave_last_path"] == target
    assert loaded["source_ref"] == target
    assert Path(loaded["cenas_imagem"][0]["caminho_arquivo"]).read_bytes() == image.read_bytes()
    before = backend.list("livros")
    generation_autosave.persist_generation_snapshot(loaded, reason="resume", updates={"licao_final": "Updated in the same book."})
    assert backend.list("livros") == before
    assert backend.get_json(target.removeprefix("fb://"))["licao_final"] == "Updated in the same book."


def test_recursive_materialization_preserves_json_identity_but_loads_pdf(monkeypatch):
    calls = []
    monkeypatch.setattr(storage, "materializar", lambda value: calls.append(value) or "local.pdf")
    identity = "fb://translation_studio/edition.json"
    values = {"source_ref": identity, "links": [identity], "pdf": "fb://assets/book.pdf"}
    assert storage.materializar_assets_em_objeto(values) == {"source_ref": identity, "links": [identity], "pdf": "local.pdf"}
    assert calls == ["fb://assets/book.pdf"]


@pytest.mark.parametrize("save,prefix", [("salvar_livro", "livros"), ("salvar_livro_colorir", "livros_colorir")])
def test_new_projects_saved_in_the_same_second_do_not_overwrite_each_other(monkeypatch, tmp_path, save, prefix):
    backend = storage.LocalStorageBackend(tmp_path / "backend")
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setattr(armazenamento.time, "strftime", lambda *args: "20261013-120000")
    first = getattr(armazenamento, save)({"titulo": "Mesmo título", "colecao": "Audit", "note": "First project"})
    second = getattr(armazenamento, save)({"titulo": "Mesmo título", "colecao": "Audit", "note": "Second project"})
    assert first != second
    assert len(backend.list(prefix)) == 2
    assert backend.get_json(first.removeprefix("fb://"))["note"] == "First project"
    assert backend.get_json(second.removeprefix("fb://"))["note"] == "Second project"


def test_autosave_with_ambiguous_title_preserves_both_existing_books(monkeypatch, tmp_path):
    backend = storage.LocalStorageBackend(tmp_path / "backend")
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    first = armazenamento.salvar_livro({"titulo": "Mesmo título", "colecao": "Audit", "note": "First"})
    second = armazenamento.salvar_livro({"titulo": "Mesmo título", "colecao": "Audit", "note": "Second"})
    state = {"titulo": "Mesmo título", "colecao": "Audit", "note": "New work without a selected source"}
    saved = generation_autosave.persist_generation_snapshot(state, reason="new draft")
    assert saved not in {first, second}
    assert len(backend.list("livros")) == 3
    assert backend.get_json(first.removeprefix("fb://"))["note"] == "First"
    assert backend.get_json(second.removeprefix("fb://"))["note"] == "Second"

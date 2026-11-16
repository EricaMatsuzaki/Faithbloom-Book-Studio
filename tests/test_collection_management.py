import pytest

import collection_management as cm


def test_filter_active_collection_names_hides_archived(monkeypatch):
    monkeypatch.setattr(cm, "_registry", lambda: {"QA STORAGE": {"status": "archived"}})
    result = cm.filter_active_collection_names([
        "Pequenas Histórias, Grandes Lições",
        "QA STORAGE",
        "Mel",
        "Mel",
    ])
    assert "QA STORAGE" not in result
    assert result.count("Mel") == 1
    assert "Pequenas Histórias, Grandes Lições" in result


def test_archive_collection_refuses_canonical_collection():
    with pytest.raises(PermissionError):
        cm.archive_collection(cm.MEL_CANONICAL_COLLECTION, confirmed=True)


def test_archive_collection_archives_active_characters_without_deleting_assets(monkeypatch):
    saved = {}
    archived_ids = []
    monkeypatch.setattr(cm, "_registry", lambda: {})
    monkeypatch.setattr(
        cm,
        "listar_personagens_oficiais",
        lambda collection, incluir_arquivados=False: [
            {"id": "mel-old", "nome": "Mel", "colecao": collection, "status": "oficial"},
            {"id": "old-2", "nome": "Teste", "colecao": collection, "status": "oficial"},
        ],
    )
    monkeypatch.setattr(cm, "arquivar_personagem", lambda pid: archived_ids.append(pid))
    monkeypatch.setattr(cm, "_save_json", lambda path, data: saved.update({"path": path, "data": data}))

    result = cm.archive_collection("Mel", confirmed=True)

    assert result["non_destructive"] is True
    assert archived_ids == ["mel-old", "old-2"]
    assert saved["path"] == cm.ARCHIVED_COLLECTIONS_PATH
    assert "Mel" in saved["data"]

from copy import deepcopy

import pytest

import armazenamento
import asset_library
import storage_backend
import visual_master_manager as manager
from storage_backend import LocalStorageBackend


@pytest.fixture()
def isolated_library(tmp_path, monkeypatch):
    backend = LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage_backend, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setattr(asset_library, "BACKEND", backend)
    return backend


def test_persisted_master_candidate_can_be_approved_later_without_replacement(isolated_library, monkeypatch):
    backend = isolated_library
    def forbidden(*_args, **_kwargs):
        raise AssertionError("A aprovação não deve criar imagens, promover Master ou alterar o Reference Pack")

    monkeypatch.setattr(manager, "create_version", forbidden)
    monkeypatch.setattr(manager, "set_master_role", forbidden)
    monkeypatch.setattr(manager, "adicionar_referencia", forbidden)
    original_bytes = b"existing-image-must-not-change"
    uri = "fb://assets/visual_master/candidate-b.png"
    backend.put_bytes("assets/visual_master/candidate-b.png", original_bytes, "image/png")
    candidate = {
        "id": "3fd68a26-full-id",
        "nome": "Mel",
        "storage_uri": uri,
        "visual_status": "MASTER_CANDIDATE",
        "approved": False,
        "parent_asset_id": "mel-original",
        "version_group": "mel-versions",
        "version_label": "B",
        "master_roles": [],
        "history": [{"status": "MASTER_CANDIDATE"}],
        "metadata": {
            "visual_status": "MASTER_CANDIDATE",
            "origin_asset_id": "mel-original",
            "prompt": "Preserve exatamente a identidade da Mel",
            "history": [{"event": "generated"}],
        },
    }
    backend.put_json("galeria/index.json", [candidate])

    located = asset_library.list_assets({"media_kind": "image"}, page_size=100)["items"]
    before = deepcopy(next(asset for asset in located if asset["id"] == candidate["id"]))
    approved = manager.approve_candidate(candidate["id"])

    assert approved["id"] == before["id"]
    assert approved["storage_uri"] == before["storage_uri"]
    assert approved["parent_asset_id"] == before["parent_asset_id"]
    assert approved["version_group"] == before["version_group"]
    assert approved["version_label"] == before["version_label"]
    assert approved["history"] == before["history"]
    assert approved["metadata"]["origin_asset_id"] == before["metadata"]["origin_asset_id"]
    assert approved["metadata"]["prompt"] == before["metadata"]["prompt"]
    assert approved["metadata"]["history"] == before["metadata"]["history"]
    assert approved["visual_status"] == "APPROVED_VARIATION"
    assert approved["approved"] is True
    assert approved["metadata"]["approval"] == "human"
    assert isinstance(approved["metadata"]["approved_at"], int)
    assert approved["master_roles"] == []
    assert backend.get_bytes("assets/visual_master/candidate-b.png") == original_bytes

    reloaded = asset_library.get_asset(candidate["id"], materialize_file=False)
    assert reloaded["visual_status"] == "APPROVED_VARIATION"
    assert reloaded["storage_uri"] == uri


def test_repeated_approval_is_idempotent_and_does_not_create_asset(isolated_library):
    backend = isolated_library
    candidate = {
        "id": "persisted-candidate",
        "nome": "Mel B",
        "storage_uri": "fb://assets/visual_master/mel-b.png",
        "visual_status": "MASTER_CANDIDATE",
        "parent_asset_id": "mel-original",
        "version_group": "mel-versions",
        "version_label": "B",
        "metadata": {"prompt": "Mel", "visual_status": "MASTER_CANDIDATE"},
    }
    backend.put_json("galeria/index.json", [candidate])

    first = manager.approve_candidate(candidate["id"])
    persisted_after_first = deepcopy(backend.get_json("galeria/index.json", []))
    second = manager.approve_candidate(candidate["id"])

    assert second == first
    assert backend.get_json("galeria/index.json", []) == persisted_after_first
    assert len(persisted_after_first) == 1
    assert persisted_after_first[0]["id"] == candidate["id"]
    assert persisted_after_first[0]["visual_status"] == "APPROVED_VARIATION"

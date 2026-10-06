from copy import deepcopy
from pathlib import Path

import visual_master_manager as manager


def test_late_approval_is_in_place_and_repeated_click_is_idempotent(monkeypatch, tmp_path):
    candidate_file = tmp_path / "candidate.png"
    candidate_file.write_bytes(b"unchanged candidate")
    original_bytes = candidate_file.read_bytes()
    asset = {
        "id": "candidate-1",
        "parent_asset_id": "source-1",
        "version_group": "group-1",
        "version_label": "B",
        "caminho_arquivo": str(candidate_file),
        "storage_uri": "fb://assets/visual_master/candidate.png",
        "visual_status": "MASTER_CANDIDATE",
        "approved": False,
        "master_roles": [],
        "metadata": {"prompt": "preserve identity", "custom": {"keep": True}},
    }
    assets = {asset["id"]: deepcopy(asset)}
    update_calls = []

    monkeypatch.setattr(manager, "get_asset", lambda asset_id, **_kwargs: deepcopy(assets.get(asset_id)))

    def update_asset(asset_id, **changes):
        update_calls.append((asset_id, deepcopy(changes)))
        current = assets[asset_id]
        metadata = {**current["metadata"], **changes.pop("metadata", {})}
        current.update(changes)
        current["metadata"] = metadata
        return deepcopy(current)

    monkeypatch.setattr(manager, "update_asset", update_asset)

    approved = manager.approve_candidate(asset["id"])
    approved_again = manager.approve_candidate(asset["id"])

    assert len(assets) == 1
    assert len(update_calls) == 1
    assert approved_again == assets[asset["id"]]
    assert approved["id"] == asset["id"]
    assert approved["visual_status"] == "APPROVED_VARIATION"
    for field in ("parent_asset_id", "version_group", "version_label", "caminho_arquivo", "storage_uri"):
        assert approved[field] == asset[field]
    assert approved["metadata"]["prompt"] == asset["metadata"]["prompt"]
    assert approved["metadata"]["custom"] == asset["metadata"]["custom"]
    assert approved["master_roles"] == []
    assert Path(approved["caminho_arquivo"]).read_bytes() == original_bytes


def test_asset_library_offers_late_approval_without_reference_pack_action():
    source = Path("pages/14_👥_Character_Universe.py").read_text(encoding="utf-8")

    approval_block = source[source.index("if chosen.get('visual_status') == 'MASTER_CANDIDATE':"):]
    approval_block = approval_block[:approval_block.index("if st.button('Adicionar como referência'")]

    assert "✅ Aprovar como variação" in approval_block
    assert "approve_candidate(chosen['id'])" in approval_block
    assert "st.rerun()" in approval_block
    assert "adicionar_referencia" not in approval_block
    assert "promote_master" not in approval_block

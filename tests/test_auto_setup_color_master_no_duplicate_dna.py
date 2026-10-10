import copy

import visual_master_manager as visual


def _asset():
    return {
        "id": "asset-manu",
        "approved": True,
        "storage_uri": "fb://manu.png",
        "metadata": {},
    }


def _character(*, auto_setup=True, has_master=False):
    metadata = {
        "current_master_asset_ids": {},
        "master_history": [],
    }
    if auto_setup:
        metadata["jarvis_auto_setup_last"] = {
            "handoff_id": "handoff-manu",
            "completed_at": 1,
            "reference_count": 4,
            "model": "openrouter/free",
        }
    return {
        "id": "manu-1",
        "nome": "Manu",
        "colecao": "Pequenas Histórias, Grandes Lições",
        "dna": {
            "campos_bloqueados": {"olhos": "verdes"},
            "auto_visual_analysis": {
                "source": "jarvis_character_auto_setup",
                "analyzed_at": 1,
                "model": "openrouter/free",
            },
        },
        "metadata": metadata,
        "color_master": "fb://old.png" if has_master else "",
    }


def _wire(monkeypatch, character, calls):
    asset = _asset()
    monkeypatch.setattr(visual, "get_asset", lambda asset_id, materialize_file=False: copy.deepcopy(asset))
    monkeypatch.setattr(visual, "get_asset_by_uri", lambda *args, **kwargs: None)
    monkeypatch.setattr(visual, "carregar_personagem_oficial", lambda pid: copy.deepcopy(character))
    monkeypatch.setattr(visual, "atualizar_personagem_oficial", lambda pid, values: {**copy.deepcopy(character), **copy.deepcopy(values)})
    monkeypatch.setattr(visual, "set_master_role", lambda *args, **kwargs: None)
    monkeypatch.setattr(visual, "update_asset", lambda asset_id, **kwargs: {**copy.deepcopy(asset), **kwargs})
    monkeypatch.setattr(visual, "_autofill_visual_dna_best_effort", lambda pid, asset_id: calls.append((pid, asset_id)))


def test_first_color_master_from_jarvis_auto_setup_does_not_reanalyze_dna(monkeypatch):
    calls = []
    character = _character(auto_setup=True, has_master=False)
    _wire(monkeypatch, character, calls)

    visual.promote_master("manu-1", "asset-manu", "color_master", confirmed=True)

    assert calls == []


def test_manual_first_color_master_still_autofills_dna(monkeypatch):
    calls = []
    character = _character(auto_setup=False, has_master=False)
    _wire(monkeypatch, character, calls)

    visual.promote_master("manu-1", "asset-manu", "color_master", confirmed=True)

    assert calls == [("manu-1", "asset-manu")]


def test_later_color_master_replacement_still_autofills_dna(monkeypatch):
    calls = []
    character = _character(auto_setup=True, has_master=True)
    character["metadata"]["current_master_asset_ids"]["color_master"] = "old-asset"
    _wire(monkeypatch, character, calls)
    monkeypatch.setattr(
        visual,
        "get_asset",
        lambda asset_id, materialize_file=False: (
            {"id": "old-asset", "approved": True, "storage_uri": "fb://old.png", "metadata": {}}
            if asset_id == "old-asset"
            else copy.deepcopy(_asset())
        ),
    )

    visual.promote_master("manu-1", "asset-manu", "color_master", confirmed=True)

    assert calls == [("manu-1", "asset-manu")]

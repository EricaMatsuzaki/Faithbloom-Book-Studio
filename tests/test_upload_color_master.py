from copy import deepcopy

import pytest
import visual_master_manager as manager


@pytest.fixture
def saved_reference(monkeypatch):
    asset = {'id': 'ref', 'storage_uri': 'fb://mel.jpg', 'visual_status': 'REFERENCE',
             'approved': False, 'metadata': {'audit': {'width_px': 4096}}}
    character = {'reference_pack': [{'metadata': {'asset_library_id': 'ref'}}],
                 'color_master': 'fb://old.jpg', 'metadata': {}}
    writes = []
    monkeypatch.setattr(manager, 'carregar_personagem_oficial', lambda _: deepcopy(character))
    monkeypatch.setattr(manager, 'get_asset', lambda aid, **kw: deepcopy(asset) if aid == 'ref' else None)
    monkeypatch.setattr(manager, 'get_asset_by_uri', lambda *a, **kw: None)
    monkeypatch.setattr(manager, 'set_master_role', lambda *a: writes.append(a))
    monkeypatch.setattr(manager, 'atualizar_personagem_oficial', lambda pid, changes: character.update(changes))
    def update(aid, **changes):
        writes.append(aid)
        asset['metadata'].update(changes.pop('metadata', {}))
        asset.update(changes)
        return deepcopy(asset)
    monkeypatch.setattr(manager, 'update_asset', update)
    return asset, character, writes


def test_upload_can_be_promoted_without_new_image_and_preserves_history(saved_reference):
    asset, character, writes = saved_reference
    result = manager.promote_reference_color_master('mel', 'ref', confirmed=True)
    assert result['id'] == 'ref'
    assert result['storage_uri'] == 'fb://mel.jpg'
    assert result['visual_status'] == 'COLOR_MASTER'
    assert result['metadata']['audit']['width_px'] == 4096
    assert character['color_master'] == 'fb://mel.jpg'
    assert character['metadata']['master_history'][0]['asset'] == 'fb://old.jpg'
    count = len(writes)
    manager.promote_reference_color_master('mel', 'ref', confirmed=True)
    assert len(writes) == count


@pytest.mark.parametrize('case', ['unconfirmed', 'unlinked', 'archived', 'rejected'])
def test_invalid_promotion_does_not_write(saved_reference, case):
    asset, character, writes = saved_reference
    if case == 'unlinked': character['reference_pack'] = []
    if case == 'archived': asset['status'] = 'archived'
    if case == 'rejected': asset['visual_status'] = 'REJECTED'
    with pytest.raises((PermissionError, ValueError)):
        manager.promote_reference_color_master('mel', 'ref', confirmed=case != 'unconfirmed')
    assert not writes

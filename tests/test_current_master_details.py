import pytest
import visual_master_manager as manager


@pytest.mark.parametrize('recorded_id,resolved,expected', [
    ('mel', {'id': 'mel', 'visual_status': 'REFERENCE'}, True),
    ('', {'id': 'mel'}, True),
    ('other', {'id': 'mel'}, False),
    ('mel', None, False),
])
def test_master_identity_comes_from_saved_uri(monkeypatch, recorded_id, resolved, expected):
    monkeypatch.setattr(manager, 'get_asset_by_uri', lambda uri, **kw: resolved if uri == 'fb://mel.png' else None)
    def forbidden(*args, **kwargs):
        raise AssertionError('Reading master details must not change saved data')
    monkeypatch.setattr(manager, 'update_asset', forbidden)
    result = manager.current_color_master_details({'color_master': 'fb://mel.png',
        'metadata': {'current_master_asset_ids': {'color_master': recorded_id}}})
    assert result['consistent'] is expected
    assert result['asset'] == resolved


def test_missing_master_path_is_not_confirmed():
    assert not manager.current_color_master_details({'metadata': {'current_master_asset_ids': {'color_master': 'mel'}}})['consistent']

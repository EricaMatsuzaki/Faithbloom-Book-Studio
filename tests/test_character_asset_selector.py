from character_asset_selector import asset_option_label, asset_preview_details, assets_by_id


def _asset(identifier, path, **changes):
    asset = {
        "id": identifier,
        "nome": "1",
        "visual_status": "APPROVED_VARIATION",
        "caminho_arquivo": path,
        "version_label": "B",
        "parent_asset_id": "original-mel",
        "metadata": {"colecao": "C", "origem": "restoration_studio"},
    }
    asset.update(changes)
    return asset


def test_same_name_and_status_assets_remain_individually_selectable():
    first = _asset("asset-11111111", "/images/first.png")
    second = _asset("asset-22222222", "/images/second.png")

    options = assets_by_id([first, second])

    assert list(options) == ["asset-11111111", "asset-22222222"]
    assert options["asset-11111111"]["caminho_arquivo"] == "/images/first.png"
    assert options["asset-22222222"]["caminho_arquivo"] == "/images/second.png"


def test_friendly_labels_include_distinct_short_ids():
    first = _asset("asset-11111111", "/images/first.png")
    second = _asset("asset-22222222", "/images/second.png")

    first_label = asset_option_label(first)
    second_label = asset_option_label(second)

    assert first_label == "1 · APPROVED_VARIATION · C · [asset-11]"
    assert second_label == "1 · APPROVED_VARIATION · C · [asset-22]"
    assert first_label != second_label


def test_preview_details_identify_exact_selected_asset():
    first = _asset("asset-11111111", "/images/first.png")
    second = _asset("asset-22222222", "/images/second.png")
    options = assets_by_id([first, second])

    details = asset_preview_details(options["asset-22222222"])

    assert "ID: asset-22" in details
    assert "Status: APPROVED_VARIATION" in details
    assert "Versão: B" in details
    assert "Origem: restoration_studio" in details
    assert "Parent asset: original-mel" in details

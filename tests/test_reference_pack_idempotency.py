from copy import deepcopy

import character_universe as universe


def _reference(number, *, path=None):
    return {
        "id": f"reference-{number}",
        "asset": path or f"fb://assets/mel-{number}.png",
        "metadata": {"asset_library_id": f"asset-{number}"},
    }


def _character(reference_pack=None):
    return {
        "id": "mel",
        "nome": "Mel",
        "colecao": "FaithBloom",
        "dna": {},
        "metadata": {"master_history": [{"asset_id": "old-master"}]},
        "color_master": "fb://masters/mel-color.png",
        "line_art_master": "fb://masters/mel-line.png",
        "reference_pack": reference_pack or [],
        "variacoes": [{"id": "variation-1"}],
        "versoes": [{"salvo_em": 1}],
    }


def _memory_store(monkeypatch, document):
    saved = deepcopy(document)

    monkeypatch.setattr(universe, "_json", lambda _path, _default: deepcopy(saved))

    def save(_path, value):
        nonlocal saved
        saved = deepcopy(value)

    monkeypatch.setattr(universe, "_save_json", save)
    monkeypatch.setattr(universe, "persistir_assets_em_objeto", lambda value, _prefix: value)
    monkeypatch.setattr(universe, "materializar_assets_em_objeto", lambda value: value)
    return lambda: deepcopy(saved)


def test_four_images_added_once_and_repeated_click_stays_four(monkeypatch):
    current = _memory_store(monkeypatch, _character())

    for number in range(4):
        ref = _reference(number)
        universe.adicionar_referencia("mel", ref["asset"], metadata=ref["metadata"])
    assert len(current()["reference_pack"]) == 4
    version_count = len(current()["versoes"])

    for number in range(4):
        ref = _reference(number)
        universe.adicionar_referencia("mel", ref["asset"], metadata=ref["metadata"])
    assert len(current()["reference_pack"]) == 4
    assert len(current()["versoes"]) == version_count


def test_legacy_document_with_eleven_entries_is_persisted_as_four(monkeypatch):
    four_legacy_refs = [
        {"id": f"legacy-{number}", "asset": f"fb://legacy/mel-{number}.png", "metadata": {}}
        for number in range(4)
    ]
    legacy_pack = [deepcopy(four_legacy_refs[number % 4]) for number in range(11)]
    original = _character(legacy_pack)
    current = _memory_store(monkeypatch, original)

    loaded = universe.carregar_personagem_oficial("mel")

    assert len(loaded["reference_pack"]) == 4
    assert len(current()["reference_pack"]) == 4
    assert current()["color_master"] == original["color_master"]
    assert current()["line_art_master"] == original["line_art_master"]
    assert current()["metadata"]["master_history"] == original["metadata"]["master_history"]
    assert current()["variacoes"] == original["variacoes"]
    assert current()["versoes"] == original["versoes"]


def test_four_distinct_physical_assets_remain_four():
    references = [
        {"id": f"legacy-{number}", "asset": f"fb://physical/mel-{number}.png", "metadata": {}}
        for number in range(4)
    ]

    assert universe.normalizar_reference_pack(references) == references
    assert len(universe.normalizar_reference_pack(references)) == 4

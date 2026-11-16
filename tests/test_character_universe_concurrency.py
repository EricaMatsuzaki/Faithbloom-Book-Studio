from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import armazenamento
import character_universe as cu
import storage_backend as storage


def _isolated_backend(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    return backend


def test_concurrent_character_creation_preserves_every_index_record(tmp_path, monkeypatch):
    backend = _isolated_backend(tmp_path, monkeypatch)

    def create(index):
        return cu.criar_personagem_oficial(
            "Colecao concorrente",
            f"Personagem {index}",
            {"descricao_master": f"DNA {index}"},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(create, range(20)))

    rows = backend.get_json(cu.INDEX, [])
    assert len(rows) == 20
    assert {row["id"] for row in rows} == {item["id"] for item in created}
    assert all(row.get("storage_revision") == 1 for row in rows)


def test_concurrent_character_updates_merge_independent_fields_and_index_does_not_regress(tmp_path, monkeypatch):
    backend = _isolated_backend(tmp_path, monkeypatch)
    character = cu.criar_personagem_oficial(
        "Colecao", "Téo", {"descricao_master": "Passarinho azul"}
    )
    pid = character["id"]
    ready = Barrier(2)

    def rename():
        ready.wait(timeout=5)
        return cu.atualizar_personagem_oficial(pid, {"nome": "Téo Oficial"})

    def add_line_master():
        ready.wait(timeout=5)
        return cu.atualizar_personagem_oficial(
            pid, {"line_art_master": "fb://masters/teo-line.png"}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(rename)
        second = pool.submit(add_line_master)
        first.result(timeout=10)
        second.result(timeout=10)

    final = cu.carregar_personagem_oficial(pid)
    assert final["nome"] == "Téo Oficial"
    assert final["line_art_master"] == "fb://masters/teo-line.png"
    assert final["storage_revision"] == 3
    assert len(final["versoes"]) == 2

    card = next(row for row in backend.get_json(cu.INDEX, []) if row["id"] == pid)
    assert card["nome"] == final["nome"]
    assert card["status"] == final["status"]
    assert card["storage_revision"] == final["storage_revision"]


def test_loading_reference_pack_normalization_does_not_write_character_document(tmp_path, monkeypatch):
    backend = _isolated_backend(tmp_path, monkeypatch)
    raw = {
        "id": "p1",
        "colecao": "C",
        "nome": "P1",
        "status": "oficial",
        "dna": {},
        "color_master": "",
        "line_art_master": "",
        "reference_pack": [
            {"asset": "fb://same.png"},
            {"asset": "fb://same.png"},
        ],
        "metadata": {},
        "variacoes": [],
        "versoes": [],
        "storage_revision": 4,
    }
    backend.put_json("character_universe/p1.json", raw)

    loaded = cu.carregar_personagem_oficial("p1")
    assert len(loaded["reference_pack"]) == 1
    persisted = backend.get_json("character_universe/p1.json", {})
    assert len(persisted["reference_pack"]) == 2
    assert persisted["storage_revision"] == 4

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import armazenamento
import storage_backend as storage
import style_dna


def _isolated_backend(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    return backend


def test_concurrent_style_creation_preserves_every_index_record(tmp_path, monkeypatch):
    backend = _isolated_backend(tmp_path, monkeypatch)

    def create(index):
        return style_dna.criar_style_dna(
            f"Style {index}", "Colecao concorrente", {"ordem": index}
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(create, range(24)))

    rows = backend.get_json(style_dna.INDEX, [])
    assert len(rows) == 24
    assert {row["id"] for row in rows} == {item["id"] for item in created}
    assert all(row.get("storage_revision") == 1 for row in rows)


def test_concurrent_style_updates_merge_fields_and_index_never_regresses(tmp_path, monkeypatch):
    backend = _isolated_backend(tmp_path, monkeypatch)
    style = style_dna.criar_style_dna(
        "Original", "Colecao", {"luz": "suave"}, modo="geral"
    )
    sid = style["id"]
    ready = Barrier(2)

    def rename():
        ready.wait(timeout=5)
        return style_dna.atualizar_style(sid, {"nome": "Nome atualizado"})

    def change_mode():
        ready.wait(timeout=5)
        return style_dna.atualizar_style(sid, {"modo": "editorial"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(rename)
        second = pool.submit(change_mode)
        first.result(timeout=10)
        second.result(timeout=10)

    final = style_dna.carregar_style(sid)
    assert final["nome"] == "Nome atualizado"
    assert final["modo"] == "editorial"
    assert final["storage_revision"] == 3
    assert len(final["versoes"]) == 2

    card = next(row for row in backend.get_json(style_dna.INDEX, []) if row["id"] == sid)
    assert card["nome"] == final["nome"]
    assert card["modo"] == final["modo"]
    assert card["storage_revision"] == final["storage_revision"]


def test_corrupt_style_index_is_not_silently_replaced(tmp_path, monkeypatch):
    backend = _isolated_backend(tmp_path, monkeypatch)
    backend.put_json(style_dna.INDEX, {"unexpected": "object"})

    try:
        style_dna.criar_style_dna("Novo", "Colecao", {"x": 1})
    except storage.StorageCorrupt:
        pass
    else:
        raise AssertionError("Índice corrompido deveria bloquear a gravação.")

    assert backend.get_json(style_dna.INDEX, None) == {"unexpected": "object"}

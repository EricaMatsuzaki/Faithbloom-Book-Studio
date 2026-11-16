"""Gerenciamento seguro de coleções visíveis no FaithBloom.

Arquivar uma coleção é não destrutivo: a coleção some dos seletores do
Character Universe e os Character Masters ativos daquela coleção são
arquivados com histórico preservado. Livros e assets não são apagados.
"""
from __future__ import annotations

import time
from copy import deepcopy

from armazenamento import _json, _save_json
from character_universe import (
    MEL_CANONICAL_COLLECTION,
    arquivar_personagem,
    listar_personagens_oficiais,
    restaurar_personagem,
)

ARCHIVED_COLLECTIONS_PATH = "collections/archived.json"


def _registry() -> dict:
    data = _json(ARCHIVED_COLLECTIONS_PATH, {}) or {}
    return data if isinstance(data, dict) else {}


def list_archived_collections() -> dict:
    return deepcopy(_registry())


def filter_active_collection_names(names: list[str]) -> list[str]:
    archived = {str(name).strip().casefold() for name in _registry()}
    clean = {str(name).strip() for name in names if str(name).strip()}
    return sorted(
        [name for name in clean if name.casefold() not in archived],
        key=str.casefold,
    )


def collection_summary(name: str) -> dict:
    wanted = str(name or "").strip()
    chars = [
        item for item in listar_personagens_oficiais(wanted, incluir_arquivados=True)
        if str(item.get("colecao") or "").strip() == wanted
    ]
    active = [item for item in chars if item.get("status", "oficial") != "arquivado"]
    return {
        "name": wanted,
        "characters_total": len(chars),
        "characters_active": len(active),
        "character_ids": [str(item.get("id") or "") for item in chars if item.get("id")],
    }


def archive_collection(name: str, *, confirmed: bool = False) -> dict:
    """Arquiva coleção sem apagar livros/assets e preserva Character Masters."""
    collection = str(name or "").strip()
    if not collection:
        raise ValueError("Selecione uma coleção.")
    if collection == MEL_CANONICAL_COLLECTION:
        raise PermissionError(
            "A coleção Pequenas Histórias, Grandes Lições é protegida porque contém a Mel canônica."
        )
    if not confirmed:
        raise PermissionError("Arquivar uma coleção exige confirmação explícita.")

    registry = _registry()
    if collection in registry:
        return deepcopy(registry[collection])

    archived_character_ids: list[str] = []
    for item in listar_personagens_oficiais(collection, incluir_arquivados=False):
        pid = str(item.get("id") or "")
        if not pid:
            continue
        arquivar_personagem(pid)
        archived_character_ids.append(pid)

    record = {
        "name": collection,
        "status": "archived",
        "archived_at": int(time.time()),
        "characters_archived_by_action": archived_character_ids,
        "non_destructive": True,
    }
    registry[collection] = record
    _save_json(ARCHIVED_COLLECTIONS_PATH, registry)
    return deepcopy(record)


def restore_collection(name: str, *, confirmed: bool = False) -> dict:
    collection = str(name or "").strip()
    if not collection:
        raise ValueError("Selecione uma coleção arquivada.")
    if not confirmed:
        raise PermissionError("Restaurar uma coleção exige confirmação explícita.")

    registry = _registry()
    record = registry.get(collection)
    if not isinstance(record, dict):
        raise KeyError(collection)

    restored_ids: list[str] = []
    for pid in record.get("characters_archived_by_action", []) or []:
        try:
            restaurar_personagem(str(pid))
        except KeyError:
            continue
        else:
            restored_ids.append(str(pid))

    registry.pop(collection, None)
    _save_json(ARCHIVED_COLLECTIONS_PATH, registry)
    return {
        "name": collection,
        "status": "active",
        "characters_restored": restored_ids,
        "non_destructive": True,
    }

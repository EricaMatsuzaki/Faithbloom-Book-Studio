"""Inbox compartilhada para handoffs confirmados do Jarvis.

A fila vive no session_state do Streamlit para atravessar páginas na mesma sessão.
Ela não promove nenhum arquivo a Master e preserva o pacote original até ação
humana explícita no módulo de destino.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, MutableMapping

INBOX_KEY = "jarvis_handoff_inbox"
LEGACY_PACKAGE_KEY = "jarvis_handoff_package"


def _route_id(package: dict[str, Any]) -> str:
    return str((package.get("route") or {}).get("id") or "")


def infer_character_name(package: dict[str, Any]) -> str:
    """Tenta inferir o nome sem inventar identidade; retorna vazio se ambíguo."""
    request = str(package.get("request") or "").strip()
    patterns = (
        r"(?:personagem\s+|imagem\s+d[oa]\s+|imagens\s+d[oa]\s+|d[oa]\s+)([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÀ-ÿ0-9_-]{1,40})",
        r"(?:chamad[oa]\s+|nome\s+)([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÀ-ÿ0-9_-]{1,40})",
    )
    for pattern in patterns:
        match = re.search(pattern, request)
        if match:
            candidate = match.group(1).strip(" _-.,;:!?()[]{}")
            if candidate.casefold() not in {"mel", "imagem", "personagem", "referência", "referencia"}:
                return candidate

    stems: list[str] = []
    for file in package.get("files") or []:
        if str(file.get("kind") or "") != "image":
            continue
        name = str(file.get("name") or "")
        stem = name.rsplit(".", 1)[0]
        stem = re.sub(r"[_\- ]?(?:img|image|foto|photo)?[_\- ]?\d+$", "", stem, flags=re.IGNORECASE)
        stem = re.sub(r"[_\- ]+(?:ref|reference|referencia|final|master)$", "", stem, flags=re.IGNORECASE)
        stem = stem.strip(" _-")
        if stem:
            stems.append(stem)
    if stems:
        first = stems[0].casefold()
        if all(s.casefold() == first for s in stems):
            return stems[0].replace("_", " ").replace("-", " ").strip().title()
    return ""


def enqueue_handoff(state: MutableMapping[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    """Adiciona de forma idempotente e mantém histórico na sessão."""
    if not package or not package.get("id"):
        raise ValueError("Pacote de handoff inválido.")
    inbox = list(state.get(INBOX_KEY) or [])
    package_id = str(package["id"])
    for existing in inbox:
        if str(existing.get("id") or "") == package_id:
            return existing
    entry = dict(package)
    entry.setdefault("status", "received")
    entry.setdefault("received_at", datetime.now(timezone.utc).isoformat())
    entry.setdefault("character_name", infer_character_name(entry))
    inbox.append(entry)
    state[INBOX_KEY] = inbox
    return entry


def capture_legacy_handoff(state: MutableMapping[str, Any], *, route_id: str | None = None) -> dict[str, Any] | None:
    """Migra o slot único antigo para a fila, evitando que o próximo pedido o apague."""
    package = state.get(LEGACY_PACKAGE_KEY)
    if not isinstance(package, dict) or not package:
        return None
    if route_id and _route_id(package) != route_id:
        return None
    entry = enqueue_handoff(state, package)
    state.pop(LEGACY_PACKAGE_KEY, None)
    return entry


def list_handoffs(state: MutableMapping[str, Any], *, route_id: str | None = None, include_done: bool = True) -> list[dict[str, Any]]:
    items = [dict(item) for item in list(state.get(INBOX_KEY) or []) if isinstance(item, dict)]
    if route_id:
        items = [item for item in items if _route_id(item) == route_id]
    if not include_done:
        items = [item for item in items if str(item.get("status") or "") not in {"completed", "archived"}]
    return items


def update_handoff(state: MutableMapping[str, Any], package_id: str, **changes: Any) -> dict[str, Any]:
    inbox = list(state.get(INBOX_KEY) or [])
    for index, item in enumerate(inbox):
        if str(item.get("id") or "") == str(package_id):
            updated = dict(item)
            updated.update(changes)
            inbox[index] = updated
            state[INBOX_KEY] = inbox
            return updated
    raise KeyError(f"Handoff não encontrado: {package_id}")

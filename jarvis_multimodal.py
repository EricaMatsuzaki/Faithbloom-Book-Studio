"""Jarvis Multimodal Intake & Agent Handoff.

Centraliza anexos enviados ao Jarvis e os encaminha para módulos já existentes.
Regra anti-duplicação: verificar -> reutilizar -> estender. Este módulo NÃO cria
novos estúdios editoriais; apenas classifica, prepara contexto e aponta a rota
correta. Nenhum upload vira Master automaticamente.
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import uuid
from typing import Any, Iterable

SUPPORTED_UPLOAD_TYPES = (
    "pdf", "doc", "docx", "txt", "md", "rtf",
    "png", "jpg", "jpeg", "webp",
    "mp3", "wav", "m4a", "aac", "ogg", "webm",
)
MAX_FILE_BYTES = int(os.environ.get("JARVIS_MAX_UPLOAD_MB", "20")) * 1024 * 1024
MAX_PACKAGE_BYTES = int(os.environ.get("JARVIS_MAX_PACKAGE_MB", "50")) * 1024 * 1024

ROUTES: dict[str, dict[str, Any]] = {
    "story_create": {
        "label": "Criação de história",
        "page": "pages/1_📖_Criar_do_Zero.py",
        "agents": ["Orquestrador Editorial", "Roteirista"],
        "purpose": "criar ou desenvolver uma nova história usando os módulos editoriais existentes",
    },
    "story_review": {
        "label": "Book Doctor",
        "page": "pages/16_🩺_Book_Doctor.py",
        "agents": ["Book Doctor", "Editor de História", "Revisor"],
        "purpose": "analisar, revisar e diagnosticar uma história ou manuscrito",
    },
    "image_restore": {
        "label": "Restoration Studio",
        "page": "pages/19_✨_Restoration_Studio.py",
        "agents": ["Restoration Studio", "Ilustrador"],
        "purpose": "melhorar, restaurar ou editar uma imagem já existente",
    },
    "character_reference": {
        "label": "Character Universe",
        "page": "pages/14_👥_Character_Universe.py",
        "agents": ["Character Universe", "Criador de Personagem"],
        "purpose": "usar imagem como referência de personagem sem promover automaticamente a Master",
    },
    "audiobook": {
        "label": "Audiobook Studio",
        "page": "pages/24_🎧_Audiobook_Studio.py",
        "agents": ["Audiobook", "Narrador"],
        "purpose": "trabalhar com narração, áudio ou produção de audiobook",
    },
    "asset_library": {
        "label": "Asset Library",
        "page": "pages/31_🖼️_Asset_Library_Media_Manager.py",
        "agents": ["Asset Library / Media Manager"],
        "purpose": "organizar mídia recebida sem tratá-la como Master",
    },
    "orchestrator": {
        "label": "Orquestrador FaithBloom",
        "page": "pages/0_🤖_Orquestrador_FaithBloom.py",
        "agents": ["Orquestrador FaithBloom"],
        "purpose": "decidir a próxima rota usando os recursos já existentes",
    },
}


def _clean_filename(name: str) -> str:
    value = os.path.basename(str(name or "arquivo"))
    value = re.sub(r"[^\w.()\- À-ÿ]", "_", value, flags=re.UNICODE)
    return value[:160] or "arquivo"


def classify_attachment(name: str, mime_type: str | None = None) -> str:
    """Classifica anexo por tipo de uso; nunca por conteúdo sensível."""
    filename = _clean_filename(name)
    mime = (mime_type or mimetypes.guess_type(filename)[0] or "").casefold()
    ext = filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
    if mime.startswith("image/") or ext in {"png", "jpg", "jpeg", "webp"}:
        return "image"
    if mime.startswith("audio/") or ext in {"mp3", "wav", "m4a", "aac", "ogg", "webm"}:
        return "audio"
    if ext == "pdf" or mime == "application/pdf":
        return "pdf"
    if ext in {"doc", "docx", "txt", "md", "rtf"} or mime.startswith("text/"):
        return "document"
    return "other"


def normalize_attachment(name: str, mime_type: str | None, data: bytes) -> dict[str, Any]:
    raw = bytes(data or b"")
    if not raw:
        raise ValueError(f"O arquivo {_clean_filename(name)} está vazio.")
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"O arquivo {_clean_filename(name)} excede o limite de {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    clean_name = _clean_filename(name)
    kind = classify_attachment(clean_name, mime_type)
    if kind == "other":
        raise ValueError(f"Formato não suportado: {clean_name}.")
    return {
        "name": clean_name,
        "mime_type": str(mime_type or mimetypes.guess_type(clean_name)[0] or "application/octet-stream"),
        "kind": kind,
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "data": raw,
    }


def _text_has(text: str, *terms: str) -> bool:
    """Procura termos/frases completos para evitar colisões como Mel x melhore."""
    value = (text or "").casefold()
    return any(
        re.search(rf"(?<!\w){re.escape(term.casefold())}(?!\w)", value) is not None
        for term in terms
    )


def choose_route(request: str, attachments: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    files = list(attachments or [])
    kinds = {str(f.get("kind") or "") for f in files}
    text = (request or "").strip()

    # Intenção explícita tem prioridade sobre o tipo do arquivo.
    if _text_has(text, "crie uma história", "criar uma história", "nova história", "escreva uma história", "crie história"):
        route_id = "story_create"
    elif _text_has(text, "revise", "revisar", "analise", "analisar", "corrija o texto", "book doctor") and kinds & {"pdf", "document"}:
        route_id = "story_review"
    elif _text_has(text, "personagem", "referência", "referencia", "character", "mel") and "image" in kinds:
        route_id = "character_reference"
    elif _text_has(text, "melhore", "melhorar", "restaure", "restaurar", "edite", "editar", "corrija a imagem", "capa") and "image" in kinds:
        route_id = "image_restore"
    elif _text_has(text, "audiobook", "narração", "narracao", "voz", "áudio", "audio") and "audio" in kinds:
        route_id = "audiobook"
    elif kinds & {"pdf", "document"}:
        route_id = "story_review"
    elif "image" in kinds:
        route_id = "image_restore"
    elif "audio" in kinds:
        route_id = "audiobook"
    elif files:
        route_id = "asset_library"
    elif text:
        route_id = "orchestrator"
    else:
        route_id = "orchestrator"

    route = dict(ROUTES[route_id])
    route["id"] = route_id
    return route


def build_handoff_package(request: str, attachments: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    files = list(attachments or [])
    total = sum(int(f.get("size") or 0) for f in files)
    if total > MAX_PACKAGE_BYTES:
        raise ValueError(f"O conjunto de anexos excede o limite de {MAX_PACKAGE_BYTES // (1024 * 1024)} MB.")
    route = choose_route(request, files)
    package_id = f"handoff-{uuid.uuid4().hex[:12]}"
    names = ", ".join(f.get("name", "arquivo") for f in files) or "nenhum anexo"
    agents = ", ".join(route.get("agents") or [])
    spoken = (
        f"Entendi. Vou encaminhar este pedido para {route['label']}. "
        f"Os especialistas responsáveis são {agents}."
    )
    if files:
        spoken += f" Recebi {len(files)} arquivo{'s' if len(files) != 1 else ''}."
    spoken += " Vou manter os originais preservados e não promover nenhum arquivo a Master sem sua aprovação."
    return {
        "id": package_id,
        "request": (request or "").strip(),
        "route": route,
        "files": files,
        "file_names": names,
        "total_bytes": total,
        "requires_confirmation": True,
        "master_promotion_allowed": False,
        "spoken": spoken,
    }


def handoff_summary(package: dict[str, Any]) -> str:
    route = package.get("route") or {}
    files = package.get("files") or []
    file_text = ", ".join(str(f.get("name") or "arquivo") for f in files) if files else "sem anexos"
    return f"{route.get('label', 'Orquestrador FaithBloom')} · {file_text}"

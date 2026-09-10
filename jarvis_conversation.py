"""Camada conversacional leve do Jarvis FaithBloom.

Inspirada em padrões comuns de assistentes de voz (wake word, contexto curto,
follow-up e proteção contra eco), sem copiar código externo e sem duplicar o
orquestrador editorial. O estado continua sendo mantido pela sessão do app.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

WAKE_WORDS = ("jarvis",)
MAX_HISTORY_ITEMS = 12

SAFE_DESTINATIONS = {
    "characters": {
        "page": "pages/14_👥_Character_Universe.py",
        "label": "Personagens",
        "hints": ("personagens", "character universe", "character master"),
    },
    "library": {
        "page": "pages/15_📚_Biblioteca_Editorial.py",
        "label": "Biblioteca Editorial",
        "hints": ("biblioteca", "versões", "versoes", "biblioteca editorial"),
    },
    "story": {
        "page": "pages/39_✍️_Historia_4_Estilos.py",
        "label": "Criação de História",
        "hints": ("criar história", "criar historia", "nova história", "nova historia"),
    },
    "orchestrator": {
        "page": "pages/0_🤖_Orquestrador_FaithBloom.py",
        "label": "Orquestrador FaithBloom",
        "hints": ("orquestrador", "orquestrador faithbloom"),
    },
}


def _norm(text: str) -> str:
    value = (text or "").casefold().strip()
    value = re.sub(r"[^\wÀ-ÿ]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def strip_wake_word(text: str) -> str:
    """Remove 'Jarvis' de qualquer posição sem alterar o restante do pedido."""
    value = (text or "").strip()
    if not value:
        return ""
    for word in WAKE_WORDS:
        value = re.sub(rf"\b{re.escape(word)}\b[,:;.!?\-]*", " ", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip(" ,;:-")


def looks_like_echo(transcript: str, last_reply: str | None, *, threshold: float = 0.84) -> bool:
    """Evita que o Jarvis processe a própria fala capturada pelo microfone."""
    heard = _norm(transcript)
    spoken = _norm(last_reply or "")
    if not heard or not spoken:
        return False
    if heard == spoken:
        return True
    if len(heard) >= 18 and (heard in spoken or spoken in heard):
        return True
    return SequenceMatcher(None, heard, spoken).ratio() >= threshold


def append_turn(
    history: list[dict[str, Any]] | None,
    role: str,
    text: str,
    *,
    intent: str | None = None,
    metadata: dict[str, Any] | None = None,
    max_items: int = MAX_HISTORY_ITEMS,
) -> list[dict[str, Any]]:
    """Mantém uma memória curta e controlada da conversa atual."""
    items = list(history or [])
    clean = (text or "").strip()
    if clean:
        item: dict[str, Any] = {"role": role, "text": clean}
        if intent:
            item["intent"] = intent
        if metadata:
            item["metadata"] = dict(metadata)
        items.append(item)
    return items[-max(2, int(max_items)):]


def last_context(history: list[dict[str, Any]] | None, intent: str) -> dict[str, Any] | None:
    for item in reversed(history or []):
        if item.get("intent") == intent:
            return item
    return None


def enrich_follow_up(text: str, history: list[dict[str, Any]] | None, *, default_weather_location: str = "") -> str:
    """Resolve follow-ups curtos usando somente o contexto recente conhecido.

    Ex.: depois de perguntar o clima de Toyohashi, 'e amanhã?' continua no mesmo
    assunto sem obrigar a usuária a repetir cidade e intenção.
    """
    clean = strip_wake_word(text)
    normalized = _norm(clean)
    if not normalized:
        return clean

    weather_context = last_context(history, "weather")
    is_short_followup = len(normalized.split()) <= 5
    followup_weather_terms = {
        "e amanhã", "e amanha", "amanhã", "amanha", "e hoje", "hoje",
        "e depois", "e mais tarde", "mais tarde", "e a chuva", "e chuva",
    }
    if is_short_followup and normalized in followup_weather_terms and weather_context:
        meta = weather_context.get("metadata") or {}
        location = str(meta.get("location") or default_weather_location or "").strip()
        if location:
            when = "amanhã" if "amanh" in normalized else "hoje" if "hoje" in normalized else "mais tarde"
            return f"previsão do tempo {when} em {location}"
    return clean


def detect_general_intent(text: str) -> str | None:
    value = _norm(text)
    if not value:
        return None
    if any(x in value for x in ("o que você pode fazer", "o que voce pode fazer", "como você pode me ajudar", "como voce pode me ajudar", "quem é você", "quem e voce")):
        return "help"
    if any(x in value for x in ("obrigada", "obrigado", "valeu", "thanks", "thank you")):
        return "thanks"
    if any(x in value for x in ("meu projeto", "projeto atual", "o que está pendente", "o que esta pendente", "pendências", "pendencias", "status do projeto")):
        return "project_status"
    return None


def detect_safe_navigation(text: str) -> dict[str, str] | None:
    """Detecta apenas navegação reversível para páginas que já existem."""
    value = _norm(text)
    verbs = ("abra", "abrir", "vá", "va", "ir para", "mostre", "mostrar", "leve me", "me leve")
    if not any(v in value for v in verbs):
        return None
    for key, destination in SAFE_DESTINATIONS.items():
        if any(_norm(hint) in value for hint in destination["hints"]):
            return {"key": key, "page": destination["page"], "label": destination["label"]}
    return None


def help_reply() -> str:
    return (
        "Posso conversar com você, consultar o clima, acompanhar o projeto atual, "
        "entender pedidos de criação e encaminhar você para os módulos certos do FaithBloom. "
        "Ações importantes, como publicar, apagar ou alterar um Master oficial, continuam pedindo sua aprovação."
    )


def thanks_reply() -> str:
    return "Sempre às ordens. Se quiser, pode continuar falando comigo sem repetir tudo do começo."

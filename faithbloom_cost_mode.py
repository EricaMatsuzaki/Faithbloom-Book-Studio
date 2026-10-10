"""FaithBloom AI Cost Modes.

Centraliza a escolha de modelos para reduzir consumo de créditos sem duplicar
clientes de IA. O modo é por sessão Streamlit quando disponível e cai para a
variável de ambiente ``FAITHBLOOM_COST_MODE`` fora da UI.
"""
from __future__ import annotations

import os
from typing import Any

DEFAULT_COST_MODE = "economico"
SESSION_KEY = "faithbloom_cost_mode"

COST_MODES: dict[str, dict[str, Any]] = {
    "economico": {
        "label": "💚 Econômico",
        "dialogue_model": "openrouter/free",
        "vision_model": "openrouter/free",
        "description": "Prioriza modelos gratuitos. Ideal para Jarvis, roteamento, classificação, DNA visual e tarefas administrativas.",
        "ideal_for": "Uso diário, organização, perguntas curtas, Character DNA, classificação e testes.",
        "tradeoff": "Pode variar de modelo entre chamadas e ter disponibilidade/limites do roteador gratuito.",
        "auto_briefing": False,
        "auto_voice": False,
    },
    "balanceado": {
        "label": "⚖️ Balanceado",
        "dialogue_model": "google/gemini-2.5-flash-lite",
        "vision_model": "google/gemini-2.5-flash-lite",
        "description": "Usa um modelo barato e rápido com entrada de texto e imagem quando estabilidade importa mais que custo zero.",
        "ideal_for": "DNA visual consistente, análise multimodal, respostas mais previsíveis e trabalho editorial intermediário.",
        "tradeoff": "Tem custo baixo, mas não é gratuito.",
        "auto_briefing": False,
        "auto_voice": False,
    },
    "premium": {
        "label": "✨ Premium",
        "dialogue_model": os.environ.get("OPENROUTER_MODELO_TEXTO", "anthropic/claude-sonnet-4-6"),
        "vision_model": os.environ.get("OPENROUTER_MODELO_CHARACTER_VISION_PREMIUM", os.environ.get("OPENROUTER_MODELO_TEXTO", "anthropic/claude-sonnet-4-6")),
        "description": "Reserva modelos mais fortes para tarefas em que qualidade e raciocínio justificam o custo.",
        "ideal_for": "Revisão editorial importante, decisões complexas, texto final e casos multimodais difíceis.",
        "tradeoff": "Consome mais créditos; não deve ser o padrão para tarefas simples.",
        "auto_briefing": False,
        "auto_voice": True,
    },
}


def normalize_cost_mode(value: str | None) -> str:
    key = str(value or "").strip().casefold()
    aliases = {
        "econômico": "economico",
        "economico": "economico",
        "cheap": "economico",
        "free": "economico",
        "balanceado": "balanceado",
        "balanced": "balanceado",
        "premium": "premium",
    }
    resolved = aliases.get(key, key)
    return resolved if resolved in COST_MODES else DEFAULT_COST_MODE


def current_cost_mode() -> str:
    """Resolve o modo sem exigir Streamlit em testes/CLI."""
    try:
        import streamlit as st  # import tardio para não acoplar módulos puros
        if SESSION_KEY in st.session_state:
            return normalize_cost_mode(st.session_state.get(SESSION_KEY))
    except Exception:
        pass
    return normalize_cost_mode(os.environ.get("FAITHBLOOM_COST_MODE", DEFAULT_COST_MODE))


def set_cost_mode(value: str) -> str:
    mode = normalize_cost_mode(value)
    try:
        import streamlit as st
        st.session_state[SESSION_KEY] = mode
    except Exception:
        pass
    return mode


def mode_config(mode: str | None = None) -> dict[str, Any]:
    return dict(COST_MODES[normalize_cost_mode(mode) if mode else current_cost_mode()])


def model_for(task: str, mode: str | None = None) -> str:
    config = mode_config(mode)
    key = str(task or "dialogue").strip().casefold()
    if key in {"vision", "character_vision", "dna", "multimodal"}:
        return str(config["vision_model"])
    return str(config["dialogue_model"])


def mode_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key in ("economico", "balanceado", "premium"):
        cfg = COST_MODES[key]
        rows.append({
            "mode": key,
            "label": str(cfg["label"]),
            "dialogue_model": str(cfg["dialogue_model"]),
            "vision_model": str(cfg["vision_model"]),
            "ideal_for": str(cfg["ideal_for"]),
            "tradeoff": str(cfg["tradeoff"]),
        })
    return rows

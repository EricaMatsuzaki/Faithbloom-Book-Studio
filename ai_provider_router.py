"""FaithBloom AI provider router for editorial text tasks.

Primary text provider: Google Gemini Developer API (Free Tier compatible).
Optional fallbacks: Groq, then the legacy OpenRouter client.

Image/audio generation remain on their existing dedicated clients for now.
"""
from __future__ import annotations

import json
import os
from typing import Any

import requests


class AIProviderError(RuntimeError):
    pass


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.6-flash").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_TEXT_MODEL = os.environ.get("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile").strip()


def _strip_json_fences(text: str) -> str:
    return (
        str(text or "").strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )


def _parse_json(text: str, provider: str) -> dict | list:
    raw = _strip_json_fences(text)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AIProviderError(f"{provider} não retornou JSON válido para o FaithBloom.") from exc
    if not isinstance(parsed, (dict, list)):
        raise AIProviderError(f"{provider} retornou um formato JSON inesperado.")
    return parsed


def _gemini(sistema: str, instrucao: str) -> dict | list:
    if not GEMINI_API_KEY:
        raise AIProviderError("GEMINI_API_KEY não configurada.")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_TEXT_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "systemInstruction": {
            "parts": [{"text": sistema + "\n\nResponda APENAS em JSON válido, sem markdown."}]
        },
        "contents": [{"role": "user", "parts": [{"text": instrucao}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    response = requests.post(url, json=payload, timeout=120)
    if response.status_code in {429, 500, 502, 503, 504}:
        raise AIProviderError(f"Gemini indisponível temporariamente (HTTP {response.status_code}).")
    if response.status_code in {401, 403}:
        raise AIProviderError("Gemini recusou a autenticação/permissão da API key.")
    if response.status_code == 404:
        raise AIProviderError(f"Modelo Gemini '{GEMINI_TEXT_MODEL}' não disponível.")
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AIProviderError(f"Falha na Gemini API (HTTP {response.status_code}).") from exc
    data: dict[str, Any] = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise AIProviderError("Gemini não retornou candidata de texto.")
    parts = (((candidates[0] or {}).get("content") or {}).get("parts") or [])
    text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
    if not text.strip():
        raise AIProviderError("Gemini retornou resposta vazia.")
    return _parse_json(text, "Gemini")


def _groq(sistema: str, instrucao: str) -> dict | list:
    if not GROQ_API_KEY:
        raise AIProviderError("GROQ_API_KEY não configurada.")
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": GROQ_TEXT_MODEL,
            "messages": [
                {"role": "system", "content": sistema + "\n\nResponda APENAS em JSON válido, sem markdown."},
                {"role": "user", "content": instrucao},
            ],
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    if response.status_code in {429, 500, 502, 503, 504}:
        raise AIProviderError(f"Groq indisponível temporariamente (HTTP {response.status_code}).")
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AIProviderError(f"Falha na Groq API (HTTP {response.status_code}).") from exc
    data = response.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderError("Groq retornou resposta em formato inesperado.") from exc
    return _parse_json(text, "Groq")


def provider_status() -> dict:
    return {
        "gemini": bool(GEMINI_API_KEY),
        "groq": bool(GROQ_API_KEY),
        "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
        "primary": "gemini" if GEMINI_API_KEY else ("groq" if GROQ_API_KEY else "openrouter"),
    }


def chamar_llm(sistema: str, instrucao: str) -> dict | list:
    """Call the first available text provider and fail over automatically.

    Gemini is deliberately first so the editorial Autopilot no longer depends on
    OpenRouter credit. OpenRouter is retained only as a last-resort compatibility
    fallback while other parts of the app migrate.
    """
    errors: list[str] = []

    if GEMINI_API_KEY:
        try:
            return _gemini(sistema, instrucao)
        except Exception as exc:
            errors.append(f"Gemini: {exc}")

    if GROQ_API_KEY:
        try:
            return _groq(sistema, instrucao)
        except Exception as exc:
            errors.append(f"Groq: {exc}")

    if os.environ.get("OPENROUTER_API_KEY"):
        try:
            from openrouter_client import chamar_llm as chamar_openrouter
            return chamar_openrouter(sistema, instrucao)
        except Exception as exc:
            errors.append(f"OpenRouter: {exc}")

    if not errors:
        raise AIProviderError(
            "Nenhum provedor de texto está configurado. Defina GEMINI_API_KEY no Streamlit Secrets; "
            "GROQ_API_KEY pode ser usado como fallback opcional."
        )
    raise AIProviderError("Todos os provedores de texto falharam: " + " | ".join(errors))

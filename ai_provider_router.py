"""FaithBloom AI provider router for editorial text tasks.

Primary text provider: Google Gemini Developer API.
Optional fallbacks: Groq, then the legacy OpenRouter client.

Reliability rules:
- discover models actually exposed to the configured Gemini API key;
- only call models that advertise generateContent support;
- prefer configured/Flash text models, never image/embedding-only models;
- cache discovery briefly and remember models that are invalid in this runtime;
- retry temporary 429/5xx responses with backoff;
- preserve Groq/OpenRouter as fallbacks without wasting calls on known 402 billing failures.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

import requests


class AIProviderError(RuntimeError):
    pass


class AIProviderTemporaryError(AIProviderError):
    """Transient provider failure that can be safely retried later."""


class AIProviderPermanentError(AIProviderError):
    """Permanent/configuration/billing failure for the current runtime."""


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.6-flash").strip()
GEMINI_FALLBACK_MODELS = [
    x.strip()
    for x in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash-lite,gemini-2.5-flash").split(",")
    if x.strip()
]
GEMINI_MAX_ATTEMPTS = max(1, int(os.environ.get("GEMINI_MAX_ATTEMPTS", "3")))
GEMINI_DISCOVERY_TTL_SECONDS = max(30, int(os.environ.get("GEMINI_DISCOVERY_TTL_SECONDS", "300")))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_TEXT_MODEL = os.environ.get("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile").strip()
GROQ_MAX_ATTEMPTS = max(1, int(os.environ.get("GROQ_MAX_ATTEMPTS", "2")))

_OPENROUTER_DISABLED_REASON = ""
_GEMINI_MODEL_CACHE: dict[str, Any] = {"at": 0.0, "models": []}
_GEMINI_INVALID_MODELS: set[str] = set()
_GEMINI_LAST_SELECTED_MODEL = ""


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


def _retry_after_seconds(response: requests.Response, attempt: int) -> float:
    raw = str(response.headers.get("Retry-After") or "").strip()
    try:
        if raw:
            return min(60.0, max(1.0, float(raw)))
    except ValueError:
        pass
    return min(20.0, 2.0 ** max(0, attempt))


def _post_with_retry(
    request_fn: Callable[[], requests.Response],
    *,
    provider: str,
    max_attempts: int,
) -> requests.Response:
    last: requests.Response | None = None
    for attempt in range(max_attempts):
        response = request_fn()
        last = response
        if response.status_code not in {429, 500, 502, 503, 504}:
            return response
        if attempt + 1 < max_attempts:
            time.sleep(_retry_after_seconds(response, attempt))
    assert last is not None
    raise AIProviderTemporaryError(
        f"{provider} indisponível temporariamente após {max_attempts} tentativa(s) "
        f"(HTTP {last.status_code}). Aguarde a janela de quota e retome do checkpoint."
    )


def _normalize_model_name(value: str) -> str:
    name = str(value or "").strip()
    if name.startswith("models/"):
        name = name.split("/", 1)[1]
    return name


def _is_text_generation_model(item: dict[str, Any]) -> bool:
    name = _normalize_model_name(str(item.get("name") or ""))
    low = name.casefold()
    methods = {str(x).casefold() for x in (item.get("supportedGenerationMethods") or [])}
    if not name or "generatecontent" not in methods:
        return False
    excluded = ("embedding", "aqa", "imagen", "veo", "tts", "image-generation", "robotics")
    return not any(token in low for token in excluded)


def _discover_gemini_models(*, force: bool = False) -> list[str]:
    """Return generateContent-capable Gemini models visible to this API key.

    Discovery is best-effort. If the models endpoint is temporarily unavailable,
    callers still retain their configured model list as a fallback.
    """
    if not GEMINI_API_KEY:
        return []
    now = time.time()
    cached = list(_GEMINI_MODEL_CACHE.get("models") or [])
    cached_at = float(_GEMINI_MODEL_CACHE.get("at") or 0.0)
    if cached and not force and (now - cached_at) < GEMINI_DISCOVERY_TTL_SECONDS:
        return cached

    response = requests.get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}",
        timeout=30,
    )
    if response.status_code in {401, 403}:
        raise AIProviderPermanentError("Gemini recusou a autenticação/permissão da API key ao listar modelos.")
    if response.status_code in {429, 500, 502, 503, 504}:
        return cached
    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return cached

    discovered = [
        _normalize_model_name(str(item.get("name") or ""))
        for item in (payload.get("models") or [])
        if isinstance(item, dict) and _is_text_generation_model(item)
    ]
    discovered = [m for m in discovered if m and m not in _GEMINI_INVALID_MODELS]
    _GEMINI_MODEL_CACHE["at"] = now
    _GEMINI_MODEL_CACHE["models"] = list(dict.fromkeys(discovered))
    return list(_GEMINI_MODEL_CACHE["models"])


def _model_rank(model: str) -> tuple[int, str]:
    low = model.casefold()
    configured = [_normalize_model_name(GEMINI_TEXT_MODEL), *map(_normalize_model_name, GEMINI_FALLBACK_MODELS)]
    if model == _GEMINI_LAST_SELECTED_MODEL:
        return (0, model)
    if model in configured:
        return (1 + configured.index(model), model)
    if "flash-lite" in low:
        return (20, model)
    if "flash" in low:
        return (21, model)
    if "pro" in low:
        return (30, model)
    return (40, model)


def _gemini_candidate_models() -> list[str]:
    configured: list[str] = []
    for raw in [GEMINI_TEXT_MODEL, *GEMINI_FALLBACK_MODELS]:
        model = _normalize_model_name(raw)
        if model and model not in configured and model not in _GEMINI_INVALID_MODELS:
            configured.append(model)

    discovered = _discover_gemini_models()
    if discovered:
        # Discovery is authoritative for availability. Keep configured preference
        # only when the configured model is actually visible to this key.
        visible = set(discovered)
        candidates = [m for m in configured if m in visible]
        candidates.extend(m for m in sorted(discovered, key=_model_rank) if m not in candidates)
        return candidates
    return configured


def _gemini_model(model: str, sistema: str, instrucao: str) -> dict | list:
    global _GEMINI_LAST_SELECTED_MODEL
    if not GEMINI_API_KEY:
        raise AIProviderPermanentError("GEMINI_API_KEY não configurada.")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "systemInstruction": {
            "parts": [{"text": sistema + "\n\nResponda APENAS em JSON válido, sem markdown."}]
        },
        "contents": [{"role": "user", "parts": [{"text": instrucao}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    response = _post_with_retry(
        lambda: requests.post(url, json=payload, timeout=120),
        provider=f"Gemini/{model}",
        max_attempts=GEMINI_MAX_ATTEMPTS,
    )
    if response.status_code in {401, 403}:
        raise AIProviderPermanentError("Gemini recusou a autenticação/permissão da API key.")
    if response.status_code == 404:
        _GEMINI_INVALID_MODELS.add(model)
        _GEMINI_MODEL_CACHE["models"] = [m for m in (_GEMINI_MODEL_CACHE.get("models") or []) if m != model]
        raise AIProviderPermanentError(f"Modelo Gemini '{model}' não disponível.")
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
    _GEMINI_LAST_SELECTED_MODEL = model
    return _parse_json(text, f"Gemini/{model}")


def _gemini(sistema: str, instrucao: str) -> dict | list:
    errors: list[str] = []
    models = _gemini_candidate_models()
    if not models:
        raise AIProviderTemporaryError(
            "Gemini não expôs nenhum modelo de texto com generateContent para esta API key neste momento."
        )

    for model in models:
        try:
            return _gemini_model(model, sistema, instrucao)
        except AIProviderPermanentError as exc:
            errors.append(str(exc))
            low = str(exc).casefold()
            if "autenticação" in low or "api key" in low:
                raise
        except AIProviderTemporaryError as exc:
            errors.append(str(exc))
        except AIProviderError as exc:
            errors.append(str(exc))

    # Refresh discovery once after all candidates fail. This catches model-list
    # changes without requiring a deploy or editing Streamlit Secrets.
    refreshed = _discover_gemini_models(force=True)
    attempted = set(models)
    for model in sorted(refreshed, key=_model_rank):
        if model in attempted or model in _GEMINI_INVALID_MODELS:
            continue
        try:
            return _gemini_model(model, sistema, instrucao)
        except AIProviderError as exc:
            errors.append(str(exc))

    raise AIProviderTemporaryError(
        "Gemini sem capacidade/modelo utilizável agora: " + " | ".join(errors)
    )


def _groq(sistema: str, instrucao: str) -> dict | list:
    if not GROQ_API_KEY:
        raise AIProviderPermanentError("GROQ_API_KEY não configurada.")

    def _request() -> requests.Response:
        return requests.post(
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

    response = _post_with_retry(_request, provider="Groq", max_attempts=GROQ_MAX_ATTEMPTS)
    if response.status_code in {401, 403}:
        raise AIProviderPermanentError("Groq recusou a autenticação/permissão da API key.")
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
        "gemini_selected_model": _GEMINI_LAST_SELECTED_MODEL,
        "groq": bool(GROQ_API_KEY),
        "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")) and not bool(_OPENROUTER_DISABLED_REASON),
        "openrouter_disabled_reason": _OPENROUTER_DISABLED_REASON,
        "primary": "gemini" if GEMINI_API_KEY else ("groq" if GROQ_API_KEY else "openrouter"),
    }


def _openrouter(sistema: str, instrucao: str) -> dict | list:
    global _OPENROUTER_DISABLED_REASON
    if _OPENROUTER_DISABLED_REASON:
        raise AIProviderPermanentError(_OPENROUTER_DISABLED_REASON)
    from openrouter_client import chamar_llm as chamar_openrouter
    try:
        return chamar_openrouter(sistema, instrucao)
    except Exception as exc:
        text = str(exc)
        low = text.casefold()
        if "402" in low or "insufficient" in low or "crédito" in low or "credito" in low:
            _OPENROUTER_DISABLED_REASON = "OpenRouter indisponível por saldo/créditos insuficientes (HTTP 402)."
            raise AIProviderPermanentError(_OPENROUTER_DISABLED_REASON) from exc
        raise


def chamar_llm(sistema: str, instrucao: str) -> dict | list:
    """Call providers in order, with resilient failover and clear transient status."""
    errors: list[str] = []
    temporary = False

    if GEMINI_API_KEY:
        try:
            return _gemini(sistema, instrucao)
        except AIProviderTemporaryError as exc:
            temporary = True
            errors.append(f"Gemini: {exc}")
        except Exception as exc:
            errors.append(f"Gemini: {exc}")

    if GROQ_API_KEY:
        try:
            return _groq(sistema, instrucao)
        except AIProviderTemporaryError as exc:
            temporary = True
            errors.append(f"Groq: {exc}")
        except Exception as exc:
            errors.append(f"Groq: {exc}")

    if os.environ.get("OPENROUTER_API_KEY") and not _OPENROUTER_DISABLED_REASON:
        try:
            return _openrouter(sistema, instrucao)
        except AIProviderPermanentError as exc:
            errors.append(f"OpenRouter: {exc}")
        except Exception as exc:
            errors.append(f"OpenRouter: {exc}")

    if not errors:
        raise AIProviderPermanentError(
            "Nenhum provedor de texto está configurado. Defina GEMINI_API_KEY no Streamlit Secrets; "
            "GROQ_API_KEY pode ser usado como fallback opcional."
        )
    message = "Todos os provedores de texto estão indisponíveis: " + " | ".join(errors)
    if temporary:
        raise AIProviderTemporaryError(message + " | Progresso preservado; retome do checkpoint após a janela de quota.")
    raise AIProviderPermanentError(message)

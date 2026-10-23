"""Action-scoped callbacks for legacy Studio clicks, without global monkeypatches.

Create these callbacks inside the confirmed button handler. The callback is a
bounded capability for that action, not an approval inferred from a prompt,
saved project, agent profile or browser session flag. Governance evidence is
durable before the provider is invoked; the provider keeps its existing meter.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Callable, Mapping
from uuid import uuid4

import controle_geracao as costs
from governance_runtime import GovernanceBlocked, authorize_generation


def _fingerprint(value) -> str:
    try:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        raise GovernanceBlocked("Não foi possível identificar os dados desta ação.") from None
    return sha256(serialized.encode("utf-8")).hexdigest()


def source_uses_personal_data(source: Mapping | None) -> bool:
    """Read classification markers only; never mistake old consent for consent.

    This is not an NLP detector. Free-form material still requires classification
    by its author. Nested source metadata is retained across derived Studios.
    """
    def marked(value, depth=0):
        if depth > 12:
            raise GovernanceBlocked("Os metadados da fonte precisam de revisão antes do envio.")
        if isinstance(value, Mapping):
            personal_origins = {"real_experience", "real_life_story", "real_life", "experiencia_real"}
            if (any(isinstance(label, str) and label in personal_origins for label in (value.get("origin"), value.get("origem")))
                    or bool(value.get("real_life_brief")) or bool(value.get("real_experience")) or value.get("uses_personal_data") is True
                    or value.get("contains_personal_data") is True):
                return True
            return any(marked(child, depth + 1) for child in value.values() if isinstance(child, (Mapping, list, tuple)))
        if isinstance(value, (list, tuple)):
            return any(marked(child, depth + 1) for child in value if isinstance(child, (Mapping, list, tuple)))
        return False
    return marked(source or {})


def source_with_linked_book(project: Mapping) -> dict:
    """Recover exact saved source classification for an older derived project.

    Older audiobook projects omit real-experience markers. Do not silently treat
    those projects as anonymous: read their exact durable source, fail closed on
    missing/unreadable data and let the storage access layer enforce its scope.
    """
    result = {"project": deepcopy(dict(project))}
    reference = project.get("source_ref")
    if not reference:
        return result
    if not isinstance(reference, str):
        raise GovernanceBlocked("A fonte vinculada precisa de revisão antes do envio.")
    import storage_backend as storage
    try:
        path = storage.uri_to_path(reference if storage.is_storage_uri(reference) else storage.storage_uri(reference))
        source = storage.BACKEND.get_json(path, None)
    except Exception:
        raise GovernanceBlocked("Não foi possível verificar a fonte vinculada antes do envio.") from None
    if not isinstance(source, dict) or not source:
        raise GovernanceBlocked("A fonte vinculada não está disponível para conferir o consentimento.")
    result.update({"source_ref": reference, "source": source})
    return result


def render_personal_consent(st, source: Mapping, *, action: str) -> bool:
    """Render an action/source-specific opt-in only for classified personal data."""
    if not source_uses_personal_data(source):
        return False
    key = "governance_data_consent_" + _fingerprint({"action": action, "source": source})
    return st.checkbox("Autorizo o envio dos dados desta experiência real ao provedor para esta ação.",
        value=False, key=key)


def text_route_configuration() -> dict:
    """Inspect the exact shared text adapter, not unrelated Groq credentials."""
    import openrouter_client as client
    active = client.texto_provedor_ativo()
    configured = ((active == "gemini" and client.gemini_client.gemini_disponivel())
        or (active == "openrouter" and bool(client.OPENROUTER_API_KEY)))
    return {"provider": active if active in {"gemini", "openrouter"} else "",
        "configured": bool(configured), "live_access_verified": False}


class GovernedTextCallback:
    def __init__(self, action: str, source: Mapping, *, confirmed: bool,
                 consent_confirmed: bool = False, max_calls: int = 1,
                 provider: Callable | None = None, provider_configured: bool | None = None,
                 checkpoint: Callable | None = None):
        if isinstance(max_calls, bool) or not isinstance(max_calls, int) or not 1 <= max_calls <= 10:
            raise ValueError("O limite de chamadas desta ação deve estar entre 1 e 10.")
        self.action = action
        self.source = deepcopy(dict(source))
        self.confirmed = confirmed
        self.consent_confirmed = consent_confirmed
        self.max_calls = max_calls
        self.provider = provider
        self.provider_configured = provider_configured
        self.checkpoint = checkpoint
        self.governance_receipts = []
        self.operation_id = uuid4().hex
        self.calls = 0

    def __call__(self, sistema: str, instrucao: str):
        if self.calls >= self.max_calls:
            raise GovernanceBlocked("O limite desta ação foi atingido. Confirme uma nova ação antes de gerar novamente.")
        if not isinstance(sistema, str) or not isinstance(instrucao, str):
            raise GovernanceBlocked("A entrada desta ação de texto é inválida.")
        self.calls += 1
        route = text_route_configuration() if self.provider is None else {
            "configured": self.provider_configured is True, "provider": "injected_adapter"}
        receipt = authorize_generation(self.action, confirmed=self.confirmed,
            projected_cost=costs.estimar_custo("texto"), provider_configured=route["configured"],
            operation_id=f"{self.operation_id}:{self.calls}", source_module="governance_callbacks.py",
            state={"source": self.source, "provider": route["provider"],
                "request_sha256": _fingerprint({"sistema": sistema, "instrucao": instrucao})},
            uses_personal_data=source_uses_personal_data(self.source),
            consent_confirmed=self.consent_confirmed)
        self.governance_receipts.append(deepcopy(receipt))
        if self.checkpoint is not None:
            self.checkpoint(deepcopy(receipt))
        if self.provider is not None:
            return self.provider(sistema=sistema, instrucao=instrucao)
        import openrouter_client as client
        return client.chamar_llm(sistema=sistema, instrucao=instrucao,
            strict_provider=route["provider"], no_paid_fallback=True, no_retries=True)


def governed_text_callback(action: str, source: Mapping, *, confirmed: bool,
                          consent_confirmed: bool = False, max_calls: int = 1,
                          provider: Callable | None = None, provider_configured: bool | None = None,
                          checkpoint: Callable | None = None) -> GovernedTextCallback:
    return GovernedTextCallback(action, source, confirmed=confirmed,
        consent_confirmed=consent_confirmed, max_calls=max_calls, provider=provider,
        provider_configured=provider_configured, checkpoint=checkpoint)

"""Governance at paid-action boundaries, with durable, scoped evidence.

This adapter does not certify the SaaS or create an authenticated pilot tenant.
The private author's pilot may execute an explicitly confirmed action while its
commercial controls remain UNKNOWN. Customer mode keeps the existing fail-closed
access/readiness checks. The daily meter and project ledger remain authoritative;
this module observes their balance and never records another charge.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

import controle_geracao as costs
import governance
import saas_access as access


class GovernanceBlocked(PermissionError):
    """An action was not started; the message contains no provider/user payload."""


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _source_artifacts(source_module: str) -> list[dict]:
    root = Path(__file__).resolve().parent
    artifacts = []
    for name in dict.fromkeys(("governance_runtime.py", "governance.py", "saas_access.py", source_module)):
        if not re.fullmatch(r"[a-z_][a-z_0-9]*\.py", name):
            raise GovernanceBlocked("A versão da implementação não pôde ser identificada.")
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise GovernanceBlocked("A versão da implementação não pôde ser identificada.")
        artifacts.append({"kind": "source", "path": name, "sha256": sha256(path.read_bytes()).hexdigest()})
    return artifacts


def text_provider_configuration() -> dict:
    """Inspect presence only; never discover models or call a provider."""
    import ai_provider_router as router
    status = router.provider_status()
    configured = [name for name in ("gemini", "groq", "openrouter") if status.get(name) is True]
    return {"configured": bool(configured), "providers": configured,
            "live_access_verified": False}


def _resource_scope(state: Mapping | None, resource_tenant_id: str) -> str:
    """Use only explicit durable identities, never a title/profile as a tenant."""
    tenant = str(resource_tenant_id or "")
    for name in ("storage_path", "source_ref"):
        reference = (state or {}).get(name)
        if not isinstance(reference, str):
            continue
        path = reference[len("fb://"):] if reference.startswith("fb://") else reference
        if not path.startswith("tenants/"):
            continue
        qualified = path.split("/", 2)
        if len(qualified) != 3 or not qualified[1]:
            raise GovernanceBlocked("A identidade persistente do recurso é inválida.")
        if tenant and tenant != qualified[1]:
            raise GovernanceBlocked("As identidades do recurso são incompatíveis.")
        tenant = qualified[1]
    return tenant


def authorize_generation(
    action: str, *, confirmed: bool, projected_cost: float,
    provider_configured: bool, operation_id: str, source_module: str,
    state: Mapping | None = None, budget_remaining: float | None = None,
    resource_tenant_id: str = "", uses_personal_data: bool = False,
    consent_confirmed: bool = False, consent: Mapping | None = None,
) -> dict:
    """Persist policy + all four specialists before a new paid operation.

    ``confirmed`` and ``consent_confirmed`` must come from the actual action's
    server-side UI/worker boundary, not a saved project flag. State is hashed in
    memory; titles, text, account IDs, prompts and credentials are never copied
    into the evidence. Missing evidence or a failed report write prevents the
    caller from reaching its provider. The receipt is for this operation only.
    """
    if not isinstance(action, str) or not re.fullmatch(r"[a-z][a-z0-9_.:-]{1,100}", action):
        raise GovernanceBlocked("Informe uma ação de geração identificada.")
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise GovernanceBlocked("Informe a identidade da operação antes de gerar.")
    mode = access.access_mode()
    resource_scope = _resource_scope(state, resource_tenant_id)
    actor = access.require_action("storage.write", resource_tenant_id=resource_scope)
    if mode == "pilot" and resource_scope:
        raise GovernanceBlocked("Um recurso de cliente não pode ser usado na sessão privada do piloto.")
    now = datetime.now(timezone.utc).isoformat()
    operation_sha = _digest({"action": action, "operation_id": str(operation_id)})
    event_ref = f"runtime:action:{operation_sha}"
    approval = {"approved": confirmed is True, "action": action, "actor_type": "human",
                "actor_id": actor.subject if actor else "private_pilot_operator",
                "approved_at": now, "evidence_ref": event_ref + ":confirmation"}
    tenant_evidence = None
    if actor is not None:
        tenant_evidence = {"verified": True, "tenant_id": actor.tenant_id,
                           "resource_tenant_id": resource_scope or actor.tenant_id,
                           "observed_at": now, "evidence_ref": event_ref + ":access.require_action"}
    if consent is None and consent_confirmed is True:
        consent = {"granted": True, "scope": action,
                   "subject_id": actor.subject if actor else "private_pilot_operator",
                   "observed_at": now, "evidence_ref": event_ref + ":data-consent"}
    try:
        if isinstance(projected_cost, bool) or isinstance(budget_remaining, bool):
            raise ValueError("Boolean is not a budget")
        projected = float(projected_cost)
        daily_limit = float(costs.POLITICA.orcamento_diario_usd)
        daily_spent = float(costs.custo_hoje_usd())
        remaining = daily_limit - daily_spent
        if budget_remaining is not None:
            remaining = min(remaining, float(budget_remaining))
        finite = all(math.isfinite(x) and x >= 0 for x in (projected, daily_limit, daily_spent, remaining))
    except (ValueError, TypeError, OverflowError):
        projected, remaining, finite = None, None, False
    policy = governance.preflight_action(
        action, approval=approval, paid=True,
        projected_cost=projected if finite else None, budget_remaining=remaining if finite else None,
        currency="USD", budget_currency="USD",
        tenant_id=actor.tenant_id if actor else None,
        resource_tenant_id=(resource_scope or actor.tenant_id) if actor else None,
        tenant_evidence=tenant_evidence, uses_personal_data=uses_personal_data, consent=consent,
    )
    findings = list(policy["findings"])
    findings.append(governance.finding(
        "provider_configuration", "PASS" if provider_configured is True else "FAIL",
        "Adaptador de provedor configurado para esta ação", [event_ref + ":provider-presence"],
        "Configuração não comprova acesso, saldo nem qualidade do resultado no provedor.",
    ))
    readiness = access.access_readiness()
    findings.append(governance.finding(
        "commercial_readiness", "UNKNOWN" if mode == "pilot" else "PASS" if readiness["customer_ready"] else "FAIL",
        "Prontidão do modo comercial", ["runtime:saas_access.access_readiness"],
        "O piloto privado não comprova autenticação, isolamento ou prontidão para clientes.",
    ))
    artifacts = _source_artifacts(source_module)
    if state is not None:
        try:
            artifacts.append({"kind": "input_state", "sha256": _digest(state)})
        except (TypeError, ValueError, OverflowError):
            raise GovernanceBlocked("Não foi possível registrar a identidade da entrada antes da geração.") from None
    operation_version = _digest([item for item in artifacts if item["kind"] == "source"])
    excluded = {"tenant_scope", "commercial_readiness"} if mode == "pilot" else set()
    allowed = all(item["status"] == "PASS" for item in findings if item["code"] not in excluded)
    metadata = {"action": action, "operation_sha256": operation_sha,
                "operation_version_sha256": operation_version, "artifacts": artifacts,
                "mode": mode, "observed_at": now, "provider_live_verified": False,
                "execution_decision": {"allowed": allowed, "mode": mode,
                                       "excluded_controls": sorted(excluded),
                                       "customer_ready": readiness["customer_ready"]},
                "budget_basis": "existing_daily_meter_and_optional_project_ledger_estimates"}
    report = governance.build_report("governance_runtime", "Controles da ação de geração", findings,
                                     scope="single_paid_action", metadata=metadata)
    # Keep strict policy result honest, even when the explicit private-pilot
    # applicability decision permits execution. Never forge tenant PASS.
    report["allowed"] = all(item["status"] == "PASS" for item in findings)
    # Match the existing governance history page. "pilot" is a local history
    # namespace, never tenant evidence or an authentication claim.
    workspace = actor.tenant_id if actor else "pilot"
    try:
        policy_ref = governance.save_report(report, workspace_id=workspace)
        diagnostic_reports = governance.run_all_diagnostics()
        if len(diagnostic_reports) != 4:
            raise ValueError("Specialist evidence unavailable")
        specialist_refs = []
        role_controls = {
            "ai_governance": {"human_approval", "budget", "provider_configuration"},
            "data_governance": {"tenant_scope", "personal_consent"},
            "it_governance": {"commercial_readiness", "provider_configuration"},
            "cybersecurity": {"tenant_scope", "human_approval", "personal_consent"},
        }
        for diagnostic in diagnostic_reports:
            role = diagnostic["role_id"]
            if role not in role_controls:
                raise ValueError("Unexpected specialist")
            runtime_findings = [dict(item, code="runtime_" + item["code"],
                                     title="Nesta ação: " + item["title"])
                                for item in findings if item["code"] in role_controls[role]]
            scoped = governance.build_report(role, diagnostic["name"],
                [*diagnostic["findings"], *runtime_findings],
                scope="single_paid_action_and_local_source_inspection",
                metadata={**metadata, "policy_ref": policy_ref})
            specialist_refs.append(governance.save_report(scoped, workspace_id=workspace))
    except Exception:
        raise GovernanceBlocked("Não foi possível salvar as evidências de governança. Nenhuma nova chamada foi autorizada.") from None
    if not allowed:
        raise GovernanceBlocked("Geração bloqueada: confira confirmação, orçamento, consentimento, provedor e controles de acesso.")
    # Preserve the existing meter's own fail-closed validation too. This is a
    # read-only guard; reservations and accounting belong to their current owners.
    costs.validar_orcamento(projected)
    return {"policy_ref": policy_ref, "specialist_refs": specialist_refs,
            "operation_sha256": operation_sha, "operation_version_sha256": operation_version,
            "allowed_for_mode": True, "mode": mode, "customer_ready": readiness["customer_ready"]}

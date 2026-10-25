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
    if not re.fullmatch(r"[a-z_][a-z_0-9]*\.py", source_module):
        raise GovernanceBlocked("A versão da implementação não pôde ser identificada.")
    specialist_sources = [f"agents/{module_name}.py"
        for module_name, _ in governance.SPECIALIST_ACTION_CHECKS.values()]
    for name in dict.fromkeys(("governance_runtime.py", "governance.py", "saas_access.py", source_module, *specialist_sources)):
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise GovernanceBlocked("A versão da implementação não pôde ser identificada.")
        artifacts.append({"kind": "source", "path": name, "sha256": sha256(path.read_bytes()).hexdigest()})
    return artifacts


def text_provider_configuration(*, strict: bool = False) -> dict:
    """Inspect presence only; never discover models or call a provider."""
    import ai_provider_router as router
    status = router.provider_status(strict=True) if strict else router.provider_status()
    configured = [name for name in ("gemini", "groq", "openrouter") if status.get(name) is True]
    return {"configured": bool(configured), "providers": configured,
            "live_access_verified": False}


def _resource_scope(state: Mapping | None, resource_tenant_id: str) -> str:
    """Use only explicit durable identities, never a title/profile as a tenant."""
    tenant = str(resource_tenant_id or "")
    def references(value: Mapping, depth: int = 0):
        if depth > 8:
            raise GovernanceBlocked("A identidade persistente do recurso é inválida.")
        for name, child in value.items():
            if name in {"storage_path", "source_ref", "source_storage_path", "canonical_source_ref", "resource_ref", "asset_ref"}:
                yield child
            elif isinstance(child, Mapping):
                yield from references(child, depth + 1)
            elif isinstance(child, (list, tuple)):
                for entry in child:
                    if isinstance(entry, Mapping):
                        yield from references(entry, depth + 1)
    if state is not None and not isinstance(state, Mapping):
        raise GovernanceBlocked("A identidade persistente do recurso é inválida.")
    for reference in references(state or {}):
        if not isinstance(reference, str):
            continue
        path = reference[len("fb://"):] if reference.startswith("fb://") else reference
        if not path.startswith("tenants/"):
            continue
        qualified = path.split("/", 2)
        if (len(qualified) != 3 or not qualified[1] or not qualified[2]
                or any(part in {"", ".", ".."} for part in path.split("/"))):
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
    return _authorize_action(action, confirmed=confirmed, projected_cost=projected_cost,
        provider_configured=provider_configured, operation_id=operation_id,
        source_module=source_module, state=state, budget_remaining=budget_remaining,
        resource_tenant_id=resource_tenant_id, uses_personal_data=uses_personal_data,
        consent_confirmed=consent_confirmed, consent=consent, paid=True)


def authorize_external_action(
    action: str, *, confirmed: bool, provider_configured: bool,
    operation_id: str, source_module: str, state: Mapping | None = None,
    uses_personal_data: bool = True, consent_confirmed: bool = False,
    consent: Mapping | None = None, paid: bool | None = None,
    projected_cost: float | None = None, budget_remaining: float | None = None,
    resource_tenant_id: str = "",
) -> dict:
    """Authorize one confirmed external action, including explicitly free sends.

    A free action still needs specific human approval and current data consent.
    ``paid=False`` is a trusted adapter classification, not an inference that a
    configured service is free. No meter/reservation/charge is written here.
    Invoke only for a genuinely new action, before its dispatch checkpoint or
    OAuth/provider request; the adapter retains its own idempotency guarantees.
    """
    return _authorize_action(action, confirmed=confirmed, projected_cost=projected_cost,
        provider_configured=provider_configured, operation_id=operation_id,
        source_module=source_module, state=state, budget_remaining=budget_remaining,
        resource_tenant_id=resource_tenant_id, uses_personal_data=uses_personal_data,
        consent_confirmed=consent_confirmed, consent=consent, paid=paid)


def _save_verified_report(report: Mapping, workspace: str) -> str:
    reference = governance.save_report(report, workspace_id=workspace)
    persisted = governance.load_report(reference, workspace_id=workspace)
    if (persisted.get("report_id") != report.get("report_id")
            or persisted.get("role_id") != report.get("role_id")
            or persisted.get("metadata") != governance.redact_sensitive(report.get("metadata", {}))
            or persisted.get("findings") != governance.redact_sensitive(report.get("findings", []))):
        raise ValueError("A evidência persistida não corresponde à ação atual.")
    return reference


def _authorize_action(
    action: str, *, confirmed: bool, projected_cost: float | None,
    provider_configured: bool, operation_id: str, source_module: str,
    state: Mapping | None, budget_remaining: float | None,
    resource_tenant_id: str, uses_personal_data: bool,
    consent_confirmed: bool, consent: Mapping | None, paid: bool | None,
) -> dict:
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
        if not isinstance(paid, bool):
            raise ValueError("A paid classification must be explicit")
        if isinstance(projected_cost, bool) or isinstance(budget_remaining, bool):
            raise ValueError("Boolean is not a budget")
        if paid:
            projected = float(projected_cost)
            daily_limit = float(costs.POLITICA.orcamento_diario_usd)
            daily_spent = float(costs.custo_hoje_usd())
            remaining = daily_limit - daily_spent
            if budget_remaining is not None:
                remaining = min(remaining, float(budget_remaining))
            finite = all(math.isfinite(x) and x >= 0 for x in (projected, daily_limit, daily_spent, remaining))
        else:
            projected = 0.0 if projected_cost is None else float(projected_cost)
            remaining = None
            finite = math.isfinite(projected) and projected == 0
    except (ValueError, TypeError, OverflowError):
        projected, remaining, finite = None, None, False
    policy_kwargs = dict(approval=approval, paid=paid,
        projected_cost=projected if finite else None, budget_remaining=remaining if finite else None,
        currency="USD", budget_currency="USD",
        tenant_id=actor.tenant_id if actor else None,
        resource_tenant_id=(resource_scope or actor.tenant_id) if actor else None,
        tenant_evidence=tenant_evidence, uses_personal_data=uses_personal_data, consent=consent,
        requires_confirmation=True)
    policy = governance.preflight_action(action, **policy_kwargs)
    findings = list(policy["findings"])
    findings.append(governance.finding("cost_classification", "PASS" if finite else "FAIL",
        "Classificação explícita de custo da ação", [event_ref + ":cost-classification"],
        "Envios não pagos devem ser declarados pelo adaptador; ações pagas exigem estimativa e saldo conhecidos."))
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
                "budget_basis": "existing_daily_meter_and_optional_project_ledger_estimates" if paid else "adapter_explicit_unpaid_action",
                "paid": paid}
    # Match the existing governance history page. "pilot" is a local history
    # namespace, never tenant evidence or an authentication claim.
    workspace = actor.tenant_id if actor else "pilot"
    try:
        diagnostic_reports = governance.run_all_diagnostics()
        expected_roles = set(governance.SPECIALIST_ACTION_CHECKS)
        if (len(diagnostic_reports) != 4
                or {item.get("role_id") for item in diagnostic_reports} != expected_roles):
            raise ValueError("Specialist evidence unavailable")
        specialist_refs = []
        role_controls = {
            "ai_governance": {"human_approval", "budget", "cost_classification", "provider_configuration"},
            "data_governance": {"tenant_scope", "personal_consent"},
            "it_governance": {"commercial_readiness", "provider_configuration"},
            "cybersecurity": {"tenant_scope", "human_approval", "personal_consent"},
        }
        specialist_actions = {}
        specialists_allowed = True
        for diagnostic in diagnostic_reports:
            role = diagnostic["role_id"]
            if (role not in role_controls or diagnostic.get("schema_version") != governance.SCHEMA_VERSION
                    or any(item.get("code") == "diagnostic_unavailable" for item in diagnostic.get("findings", []))):
                raise ValueError("Unexpected specialist")
            # Invoke each specialist's actual action checker, rather than using
            # the presence of its profile/source as permission to spend or send.
            specialist_action = governance.evaluate_specialist_action(role, action, **policy_kwargs)
            specialist_actions[role] = specialist_action
            specialist_findings = {item["code"]: item for item in specialist_action["findings"]}
            for code in role_controls[role] - {"provider_configuration", "commercial_readiness", "cost_classification"}:
                if code not in specialist_findings:
                    raise ValueError("Specialist action control unavailable")
            # Every new action-specific control is binding. A role's predefined
            # display group must never discard its own additional privacy,
            # safety or operational vetoes. Only the named pilot exclusions
            # above can be inapplicable; static diagnostic UNKNOWNs stay separate.
            for item in specialist_action["findings"]:
                if item["code"] not in excluded and item["status"] != "PASS":
                    allowed = False
                    specialists_allowed = False
        findings.append(governance.finding("specialist_action_checks", "PASS" if specialists_allowed else "FAIL",
            "Os quatro agentes avaliaram os controles aplicáveis desta ação",
            [event_ref + ":specialist-check:" + role for role in sorted(expected_roles)],
            "A decisão específica dos agentes não certifica prontidão comercial nem teste real do provedor."))
        metadata["execution_decision"]["allowed"] = allowed
        report = governance.build_report("governance_runtime", "Controles da ação de geração", findings,
            scope="single_paid_action" if paid else "single_external_action", metadata=metadata)
        # Keep strict policy honest even when pilot applicability permits execution.
        report["allowed"] = all(item["status"] == "PASS" for item in findings)
        policy_ref = _save_verified_report(report, workspace)
        for diagnostic in diagnostic_reports:
            role = diagnostic["role_id"]
            specialist_action = specialist_actions[role]
            runtime_findings = [dict(item, code="runtime_" + item["code"],
                                     title="Nesta ação: " + item["title"])
                                for item in [*[item for item in findings if item["code"] in role_controls[role]],
                                             *specialist_action["findings"]]]
            runtime_findings = list({item["code"]: item for item in runtime_findings}.values())
            scoped = governance.build_report(role, diagnostic["name"],
                [*diagnostic["findings"], *runtime_findings],
                scope="single_paid_action_and_local_source_inspection",
                metadata={**metadata, "policy_ref": policy_ref})
            specialist_refs.append(_save_verified_report(scoped, workspace))
    except Exception:
        raise GovernanceBlocked("Não foi possível salvar as evidências de governança. Nenhuma nova chamada foi autorizada.") from None
    if not allowed:
        raise GovernanceBlocked("Geração bloqueada: confira confirmação, orçamento, consentimento, provedor e controles de acesso.")
    # Preserve the existing meter's own fail-closed validation too. This is a
    # read-only guard; reservations and accounting belong to their current owners.
    if paid:
        costs.validar_orcamento(projected)
    return {"policy_ref": policy_ref, "specialist_refs": specialist_refs,
            "operation_sha256": operation_sha, "operation_version_sha256": operation_version,
            "allowed_for_mode": True, "mode": mode, "customer_ready": readiness["customer_ready"]}

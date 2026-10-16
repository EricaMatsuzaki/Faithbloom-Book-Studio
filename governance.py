"""Local governance evidence and policy checks, without provider or project writes.

These deterministic checks inspect evidence supplied by their caller. They do not
authenticate a user, verify an external audit system, certify compliance, or grant
access to another workspace. A caller must obtain evidence from its trusted
authentication/consent/approval layer before executing an action.
"""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import importlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
import unicodedata
import uuid

import storage_backend as storage

SCHEMA_VERSION = "faithbloom.governance.v1"
STATUSES = ("PASS", "WARN", "FAIL", "UNKNOWN")
REDACTED = "[REDACTED]"
EVIDENCE_MAX_AGE = timedelta(hours=24)
LIMITATIONS = [
    "Verificação local de evidências; não é certificação de conformidade.",
    "Sem evidência verificável, o controle permanece UNKNOWN.",
    "As evidências fornecidas devem ter origem validada pelo chamador; estes relatórios não substituem autenticação ou autorização.",
]


def _token(value: str) -> str:
    clean = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", clean.casefold()).strip("_")


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _recent_timestamp(value: Any) -> bool:
    if not _present(value):
        return False
    try:
        observed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return False
        age = _utcnow() - observed.astimezone(timezone.utc)
        return -timedelta(minutes=5) <= age <= EVIDENCE_MAX_AGE
    except (ValueError, OverflowError):
        return False


_SENSITIVE_KEYS = {
    "api_key", "apikey", "api_keys", "secret", "secrets", "secret_key",
    "password", "senha", "token", "access_token", "refresh_token", "id_token",
    "authorization", "cookie", "cookies", "credential", "credentials",
    "client_secret", "private_key", "service_role_key", "supabase_secret_key",
    "supabase_service_role_key", "openai_api_key", "openrouter_api_key", "gemini_api_key",
    "email", "phone", "telefone", "address", "endereco", "cpf", "birth_date",
    "date_of_birth", "data_nascimento", "full_name", "nome_completo", "personal_data",
    "actor_id", "subject_id", "user_id", "prompt", "raw_prompt", "messages",
    "message", "transcript", "transcricao", "content", "raw_content", "body",
}
_SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.S),
    re.compile(r"\b(?:sk-(?:or-v1-)?|sb_secret_|sb_publishable_|AIza)[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
    re.compile(r"(?i)\b(?:Bearer|Basic)\s+[^\s,;\"']+"),
    re.compile(r"(?i)\b(?:[\w.+\-]+)@[a-z0-9.\-]+\.[a-z]{2,}\b"),
    re.compile(r"(?i)(?:api[_-]?key|password|senha|secret|(?:access|refresh)[_-]?token|authorization)[\"']?\s*[=:]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"),
    re.compile(r"(?i)([?&](?:token|key|api_key|access_token|secret)=)[^&#\s]+"),
]


def redact_sensitive(value: Any) -> Any:
    """Return a JSON-safe copy with secrets, personal payloads and contacts removed.

    Evidence should contain artifact references rather than full prompts, customer
    records or provider responses. Redaction is a second guard, not a PII detector
    or an authorization system.
    """
    if isinstance(value, Mapping):
        result = {}
        for key, child in value.items():
            label = key if isinstance(key, str) else str(key) if isinstance(key, (int, float, bool)) else "[UNSUPPORTED KEY]"
            normalized = _token(label)
            sensitive = normalized in _SENSITIVE_KEYS or any(
                normalized.endswith("_" + suffix)
                for suffix in ("api_key", "password", "secret", "token", "private_key", "email", "phone", "address", "prompt", "content")
            )
            safe_key = redact_sensitive(label)
            result[safe_key] = REDACTED if sensitive else redact_sensitive(child)
        return result
    if isinstance(value, (list, tuple)):
        return [redact_sensitive(child) for child in value]
    if isinstance(value, str):
        result = value
        for pattern in _SECRET_PATTERNS:
            result = pattern.sub(REDACTED, result)
        return result
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else None
    if isinstance(value, Decimal):
        return str(value) if value.is_finite() else None
    # Never stringify an arbitrary SDK object: repr may expose credentials.
    return "[UNSUPPORTED VALUE]"


def finding(code: str, status: str, title: str, evidence: Iterable[str], recommendation: str = "") -> dict:
    normalized = str(status).strip().upper()
    if normalized not in STATUSES:
        raise ValueError("Status de governança inválido.")
    if not _present(code) or not _present(title):
        raise ValueError("Um controle precisa de código e título.")
    if isinstance(evidence, str):
        raise TypeError("Evidências devem ser uma lista de referências.")
    references = [item.strip() for item in evidence if _present(item)]
    if normalized == "PASS" and not references:
        normalized = "UNKNOWN"
        recommendation = recommendation or "Forneça uma referência verificável para confirmar este controle."
    return redact_sensitive({
        "code": code.strip(), "status": normalized, "title": title.strip(),
        "evidence": list(dict.fromkeys(references)), "recommendation": str(recommendation or ""),
    })


def _summarize(findings: list[dict]) -> tuple[str, dict]:
    counts = {status: sum(item["status"] == status for item in findings) for status in STATUSES}
    counts["total"] = len(findings)
    status = next((item for item in ("FAIL", "UNKNOWN", "WARN") if counts[item]), "PASS" if findings else "UNKNOWN")
    return status, counts


def build_report(role_id: str, name: str, findings: Iterable[dict], scope: str = "projeto", metadata: Any = None) -> dict:
    if not _present(role_id) or not _present(name):
        raise ValueError("Um relatório precisa do identificador e nome do agente.")
    normalized = [finding(item["code"], item["status"], item["title"], item.get("evidence", []), item.get("recommendation", "")) for item in findings]
    status, counts = _summarize(normalized)
    return redact_sensitive({
        "schema_version": SCHEMA_VERSION, "report_id": str(uuid.uuid4()),
        "created_at": _utcnow().isoformat(), "role_id": role_id.strip(), "name": name.strip(),
        "scope": str(scope), "status": status, "counts": counts, "findings": normalized,
        "metadata": redact_sensitive(metadata) if metadata is not None else {},
        "limitations": list(LIMITATIONS),
    })


def run_all_diagnostics(root: str | Path | None = None, state: dict | None = None, context: dict | None = None) -> list[dict]:
    """Run each read-only specialist independently; retain unavailable evidence."""
    source_root = Path(root).resolve() if root is not None else Path(__file__).resolve().parent
    reports = []
    for role_id in ("governanca_ia", "governanca_dados", "governanca_ti", "ciberseguranca"):
        try:
            module = importlib.import_module(f"agents.{role_id}")
            report = module.run_diagnostic(source_root, state=state, context=context)
            if not isinstance(report, dict) or report.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("Invalid specialist report")
        except Exception:
            # Do not leak exception messages: SDK/storage errors may carry keys.
            report = build_report(role_id, f"Diagnóstico {role_id}", [finding(
                "diagnostic_unavailable", "UNKNOWN", "Diagnóstico indisponível",
                [f"module:agents.{role_id}"], "Verifique o módulo local; nenhum controle foi certificado.",
            )])
        reports.append(redact_sensitive(report))
    return reports


def verify_control(context: Mapping, name: str) -> tuple[str, list[str]]:
    """Require explicit evidence and observation time, rather than a truthy flag."""
    controls = context.get("controls", context) if isinstance(context, Mapping) else {}
    item = controls.get(name) if isinstance(controls, Mapping) else None
    if not isinstance(item, Mapping):
        return "UNKNOWN", []
    reference = item.get("evidence_ref")
    refs = [redact_sensitive(reference.strip())] if _present(reference) else []
    status = str(item.get("status", "UNKNOWN")).upper()
    if item.get("verified") is not True or not refs or not _recent_timestamp(item.get("observed_at")):
        return "UNKNOWN", refs
    return (status, refs) if status in STATUSES else ("UNKNOWN", refs)


def inspect_source(root: str | Path, file: str | Path, symbol: str | None = None) -> list[str]:
    """Locate source evidence inside a repository; expose only file:line references."""
    base = Path(root).resolve()
    target = (base / file).resolve()
    if target == base or base not in target.parents or not target.is_file() or target.stat().st_size > 2_000_000:
        return []
    relative = target.relative_to(base).as_posix()
    if symbol is None:
        return [f"{relative}:1"]
    if target.suffix != ".py" or not _present(symbol):
        return []
    try:
        tree = ast.parse(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return []
    matches = []

    def visit(node: ast.AST, parents: tuple[str, ...] = ()) -> None:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [child.id for target_node in targets for child in ast.walk(target_node) if isinstance(child, ast.Name)]
        for name in names:
            if symbol == name or symbol == ".".join((*parents, name)):
                matches.append(f"{relative}:{node.lineno}")
        child_scope = (*parents, node.name) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else parents
        for child in ast.iter_child_nodes(node):
            visit(child, child_scope)

    visit(tree)
    return list(dict.fromkeys(matches))


_APPROVAL_TERMS = {
    "delete", "remove", "destroy", "purge", "erase", "discard", "overwrite",
    "excluir", "apagar", "destruir", "remover", "sobrescrever", "descartar",
    "publish", "publishing", "publication", "publicar", "publicacao", "master",
    "deploy", "deployment", "merge", "release", "promote", "promover",
}


def _amount(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
        return amount if amount.is_finite() and amount >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def preflight_action(
    action: str, *, approval: Mapping | None = None, paid: bool = False,
    projected_cost: Any = None, budget_remaining: Any = None, currency: str = "USD",
    budget_currency: str | None = None, tenant_id: str | None = None,
    resource_tenant_id: str | None = None, tenant_evidence: Mapping | None = None,
    uses_personal_data: bool = False, consent: Mapping | None = None,
) -> dict:
    """Evaluate scoped approval, cost, tenant and consent gates; execute nothing.

    UNKNOWN, WARN and FAIL all deny execution. Evidence references are assertions
    from the trusted caller, not externally authenticated by this module.
    """
    controls = []
    action_valid = _present(action)
    controls.append(finding("action", "PASS" if action_valid else "FAIL", "Ação identificada", [f"policy:action:{_token(action)}"] if action_valid else [], "Informe a ação exata."))
    projected = _amount(projected_cost)
    remaining = _amount(budget_remaining)
    paid_required = paid is True or (projected is not None and projected > 0)
    requires_approval = paid_required or bool(set(_token(action).split("_")) & _APPROVAL_TERMS)
    if requires_approval:
        approval = approval if isinstance(approval, Mapping) else {}
        valid = (
            approval.get("approved") is True and approval.get("action") == action
            and approval.get("actor_type") == "human" and _present(approval.get("actor_id"))
            and _present(approval.get("evidence_ref")) and _recent_timestamp(approval.get("approved_at"))
        )
        explicit_deny = approval.get("approved") is False
        controls.append(finding("human_approval", "PASS" if valid else "FAIL" if explicit_deny else "UNKNOWN", "Aprovação humana específica", [approval["evidence_ref"]] if _present(approval.get("evidence_ref")) else [], "Obtenha aprovação humana recente e vinculada à ação antes de executar."))
    else:
        controls.append(finding("human_approval", "PASS", "Ação sem aprovação especial obrigatória", ["policy:approval:not-required"]))

    if not isinstance(paid, bool):
        controls.append(finding("budget", "UNKNOWN", "Classificação de custo inválida", [], "Classifique explicitamente a ação paga."))
    elif paid_required:
        currency_valid = _present(currency) and bool(re.fullmatch(r"[A-Za-z]{3}", currency.strip()))
        currency_matches = budget_currency is None or (_present(budget_currency) and budget_currency.strip().upper() == str(currency).strip().upper())
        if not currency_matches:
            budget_status = "FAIL"
        elif projected is None or remaining is None or not currency_valid:
            budget_status = "UNKNOWN"
        else:
            budget_status = "PASS" if projected <= remaining else "FAIL"
        refs = [f"policy:budget:{str(currency).upper()}:projected={projected}:remaining={remaining}"] if projected is not None and remaining is not None else []
        controls.append(finding("budget", budget_status, "Custo previsto dentro do orçamento", refs, "Informe custo e saldo confirmados na mesma moeda antes da chamada paga."))
    else:
        controls.append(finding("budget", "PASS", "Ação declarada sem chamada paga", ["policy:budget:unpaid"]))

    tenant_evidence = tenant_evidence if isinstance(tenant_evidence, Mapping) else {}
    tenant_known = _present(tenant_id) and _present(resource_tenant_id)
    tenant_matches = tenant_known and tenant_id == resource_tenant_id
    tenant_verified = (
        tenant_matches and tenant_evidence.get("verified") is True
        and tenant_evidence.get("tenant_id") == tenant_id
        and tenant_evidence.get("resource_tenant_id") == resource_tenant_id
        and _present(tenant_evidence.get("evidence_ref"))
        and _recent_timestamp(tenant_evidence.get("observed_at"))
    )
    tenant_status = "PASS" if tenant_verified else "FAIL" if tenant_known and not tenant_matches else "UNKNOWN"
    controls.append(finding("tenant_scope", tenant_status, "Recurso pertence ao tenant autenticado", [tenant_evidence["evidence_ref"]] if _present(tenant_evidence.get("evidence_ref")) else [], "Valide identidade e escopo no controle de acesso antes da ação."))

    if not isinstance(uses_personal_data, bool):
        controls.append(finding("personal_consent", "UNKNOWN", "Classificação de dados pessoais inválida", [], "Classifique o uso de dados pessoais explicitamente."))
    elif uses_personal_data:
        consent = consent if isinstance(consent, Mapping) else {}
        valid = (
            consent.get("granted") is True and consent.get("scope") == action
            and _present(consent.get("subject_id")) and _present(consent.get("evidence_ref"))
            and _recent_timestamp(consent.get("observed_at")) and consent.get("revoked") is not True
        )
        denied = consent.get("granted") is False or consent.get("revoked") is True
        controls.append(finding("personal_consent", "PASS" if valid else "FAIL" if denied else "UNKNOWN", "Consentimento específico para dados pessoais", [consent["evidence_ref"]] if _present(consent.get("evidence_ref")) else [], "Obtenha consentimento vigente e específico antes de processar dados pessoais."))
    else:
        controls.append(finding("personal_consent", "PASS", "Ação declarada sem dados pessoais", ["policy:consent:not-required"]))
    report = build_report("governance_policy", "Pré-validação de governança", controls, scope="action", metadata={"action": action, "currency": currency})
    report["allowed"] = all(item["status"] == "PASS" for item in controls)
    return report


def _workspace_prefix(workspace_id: str) -> str:
    if not _present(workspace_id) or len(workspace_id) > 256:
        raise ValueError("Workspace inválido para relatório de governança.")
    digest = hashlib.sha256(workspace_id.strip().encode("utf-8")).hexdigest()
    return f"governance/{digest}/reports"


def _report_id(value: Any) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError):
        raise ValueError("Identidade de relatório de governança inválida.") from None


def save_report(report: Mapping, workspace_id: str = "local") -> str:
    """Persist a redacted immutable snapshot; preserve logical ID and old versions."""
    prefix = _workspace_prefix(workspace_id)
    identifier = _report_id(report.get("report_id"))
    normalized = build_report(report["role_id"], report["name"], report.get("findings", []), report.get("scope", "projeto"), report.get("metadata", {}))
    normalized["report_id"] = identifier
    normalized["created_at"] = str(report.get("created_at") or normalized["created_at"])
    if "allowed" in report:
        normalized["allowed"] = bool(normalized["findings"]) and all(item["status"] == "PASS" for item in normalized["findings"])
    normalized["saved_at"] = _utcnow().isoformat()
    normalized["snapshot_id"] = str(uuid.uuid4())
    path = f"{prefix}/{identifier}/{normalized['snapshot_id']}.json"
    safe = redact_sensitive(normalized)
    storage.BACKEND.put_json(path, safe)
    return storage.storage_uri(path)


def _validate_report_path(path: str, workspace_id: str) -> tuple[str, str, str]:
    if not isinstance(path, str) or not path:
        raise storage.StorageError("Caminho de relatório de governança inválido.")
    # Canonical storage helpers authorize a qualified URI before we inspect it.
    # Never strip an attacker-selected tenant prefix to turn it into a local path.
    raw = storage.uri_to_path(path) if storage.is_storage_uri(path) else storage.uri_to_path(storage.storage_uri(path))
    logical = raw
    from saas_access import access_mode, current_actor
    if access_mode() == "multi_tenant":
        actor = current_actor()
        tenant_prefix = f"tenants/{actor.tenant_id}/" if actor is not None else ""
        if not tenant_prefix or not raw.startswith(tenant_prefix):
            raise storage.StorageError("Relatório fora do tenant autenticado.")
        logical = raw[len(tenant_prefix):]
    prefix = _workspace_prefix(workspace_id) + "/"
    if not logical.startswith(prefix):
        raise storage.StorageError("Relatório fora do workspace solicitado.")
    suffix = logical[len(prefix):].split("/")
    if len(suffix) != 2 or not suffix[1].endswith(".json"):
        raise storage.StorageError("Caminho de relatório de governança inválido.")
    try:
        identifier = _report_id(suffix[0])
        snapshot = _report_id(suffix[1][:-5])
    except ValueError:
        raise storage.StorageError("Identidade no caminho de relatório inválida.") from None
    if suffix != [identifier, snapshot + ".json"]:
        raise storage.StorageError("Caminho de relatório de governança não canônico.")
    return raw, identifier, snapshot


def load_report(path: str, workspace_id: str = "local") -> dict:
    raw, identifier, snapshot = _validate_report_path(path, workspace_id)
    try:
        report = json.loads(storage.BACKEND.get_bytes(raw).decode("utf-8"))
    except (ValueError, UnicodeError):
        raise storage.StorageError("Relatório de governança ilegível.") from None
    if not isinstance(report, dict) or report.get("schema_version") != SCHEMA_VERSION or report.get("report_id") != identifier or report.get("snapshot_id") != snapshot:
        raise storage.StorageError("Identidade ou versão do relatório de governança inválida.")
    try:
        findings = [finding(item["code"], item["status"], item["title"], item.get("evidence", []), item.get("recommendation", "")) for item in report["findings"]]
    except (KeyError, ValueError, TypeError):
        raise storage.StorageError("Controles do relatório de governança inválidos.") from None
    report["findings"] = findings
    report["status"], report["counts"] = _summarize(findings)
    if "allowed" in report:
        report["allowed"] = bool(findings) and all(item["status"] == "PASS" for item in findings)
    return redact_sensitive(report)


def list_reports(workspace_id: str = "local") -> list[dict]:
    """List redacted snapshot metadata only within the explicitly selected scope."""
    prefix = _workspace_prefix(workspace_id)
    reports = []
    for path in storage.BACKEND.list(prefix):
        try:
            report = load_report(path, workspace_id)
        except (storage.StorageError, OSError):
            continue
        reports.append({
            "path": storage.storage_uri(path), "report_id": report["report_id"],
            "snapshot_id": report["snapshot_id"], "created_at": report["created_at"],
            "saved_at": report.get("saved_at", report["created_at"]),
            "status": report["status"], "role_id": report.get("role_id", ""),
            "name": report.get("name", ""), "counts": report["counts"],
        })
    return sorted(reports, key=lambda item: (item["saved_at"], item["path"]), reverse=True)

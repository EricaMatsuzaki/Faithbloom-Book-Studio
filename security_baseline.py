"""Security-by-Default baseline for FaithBloom SaaS and digital products.

This module centralizes reusable production-security gates without replacing the
existing hardening, storage, audit or release modules. It is intentionally
provider-neutral: auth/RLS/secrets controls can be satisfied by Supabase or an
alternative provider, but production is BLOCKED until evidence is supplied.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import PurePath
from typing import Any

SCHEMA = "faithbloom.security-baseline.v1"

SECURITY_DOMAINS: dict[str, tuple[str, ...]] = {
    "access": (
        "authentication", "authorization", "session_security", "logout",
        "password_recovery", "rbac", "least_privilege",
    ),
    "tenant_isolation": (
        "tenant_isolation", "resource_ownership_checks", "cross_tenant_denied",
    ),
    "data": (
        "persistent_storage", "row_level_security", "encryption_in_transit",
        "data_validation", "backup", "restore_tested", "retention_policy",
    ),
    "secrets": (
        "secrets_outside_git", "secrets_not_logged", "key_rotation_plan",
    ),
    "api": (
        "api_authentication", "endpoint_authorization", "payload_validation",
        "rate_limiting", "timeouts", "safe_error_messages",
    ),
    "web": (
        "xss_protection", "csrf_when_applicable", "injection_protection",
        "secure_cookies_when_applicable", "cors_restricted_when_applicable",
        "security_headers",
    ),
    "uploads": (
        "upload_type_validation", "upload_size_limit", "safe_filenames",
        "private_storage_by_default", "malicious_file_controls",
    ),
    "audit": (
        "audit_log", "critical_action_log", "auth_event_log", "secret_redaction",
    ),
    "recovery": (
        "rollback_plan", "recovery_point", "migration_backup", "disaster_recovery_plan",
    ),
    "supply_chain": (
        "dependency_review", "vulnerability_scan", "pinned_or_bounded_dependencies",
    ),
    "operations": (
        "ci_green", "security_tests", "health_checks", "monitoring", "alerting",
    ),
    "privacy": (
        "privacy_by_design", "data_minimization", "sensitive_data_access_control",
    ),
}

PRODUCTION_REQUIRED = tuple(
    control for controls in SECURITY_DOMAINS.values() for control in controls
)

# MFA is risk-based rather than mandatory for every low-risk prototype. For privileged
# production accounts it becomes mandatory via the privileged_access flag in the gate.
PRIVILEGED_REQUIRED = ("mfa_for_privileged_users", "recent_reauth_for_critical_actions")

DEFAULT_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=(self)",
    "Content-Security-Policy": "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'",
}

ALLOWED_UPLOAD_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".pdf", ".mp3", ".wav", ".m4a", ".ogg", ".txt", ".json"
}
DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def security_control_catalog() -> dict[str, list[str]]:
    return {domain: list(controls) for domain, controls in SECURITY_DOMAINS.items()}


def security_by_default_gate(
    controls: dict[str, Any] | None,
    *,
    production: bool = True,
    privileged_access: bool = False,
) -> dict[str, Any]:
    """Fail-closed production gate.

    Values must be explicitly True. Missing/unknown evidence never becomes a PASS.
    In development the gate still reports gaps, but `ready_for_environment` can remain
    true so local work is not blocked. Production always requires the complete baseline.
    """
    supplied = dict(controls or {})
    required = list(PRODUCTION_REQUIRED)
    if privileged_access:
        required.extend(PRIVILEGED_REQUIRED)
    missing = [name for name in required if supplied.get(name) is not True]
    passed = [name for name in required if supplied.get(name) is True]
    ready = not missing
    return {
        "schema": SCHEMA,
        "environment": "production" if production else "development",
        "policy": "security_by_default_fail_closed",
        "ready": ready,
        "ready_for_environment": ready if production else True,
        "status": "PASS" if ready else "BLOCKED",
        "required_total": len(required),
        "passed_total": len(passed),
        "missing": missing,
        "passed": passed,
        "privileged_access": bool(privileged_access),
        "notice": "Produção permanece bloqueada enquanto qualquer controle obrigatório não tiver evidência explícita.",
    }


def authorize_action(
    *,
    authenticated: bool,
    role: str,
    action: str,
    permissions: dict[str, set[str] | list[str] | tuple[str, ...]],
    actor_tenant_id: str = "",
    resource_tenant_id: str = "",
) -> dict[str, Any]:
    """Provider-neutral authorization/tenant-isolation check for sensitive actions."""
    normalized_role = (role or "viewer").strip().lower()
    allowed_actions = set(permissions.get(normalized_role, ()))
    same_tenant = not resource_tenant_id or (
        bool(actor_tenant_id) and actor_tenant_id == resource_tenant_id
    )
    reasons: list[str] = []
    if not authenticated:
        reasons.append("authentication_required")
    if action not in allowed_actions:
        reasons.append("permission_denied")
    if not same_tenant:
        reasons.append("cross_tenant_access_denied")
    return {
        "allowed": not reasons,
        "reasons": reasons,
        "role": normalized_role,
        "action": action,
        "tenant_isolation_ok": same_tenant,
    }


def validate_upload(
    filename: str,
    *,
    size_bytes: int,
    content_type: str = "",
    allowed_extensions: set[str] | None = None,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> dict[str, Any]:
    """Conservative upload preflight. Content inspection/antimalware remains provider-specific."""
    raw_name = str(filename or "").strip()
    safe_name = PurePath(raw_name).name
    extension = PurePath(safe_name).suffix.casefold()
    allowed = allowed_extensions or ALLOWED_UPLOAD_EXTENSIONS
    blockers: list[str] = []
    if not raw_name or safe_name != raw_name or raw_name in {".", ".."}:
        blockers.append("unsafe_filename")
    if extension not in allowed:
        blockers.append("extension_not_allowed")
    if int(size_bytes or 0) <= 0:
        blockers.append("empty_upload")
    if int(size_bytes or 0) > int(max_bytes):
        blockers.append("upload_too_large")
    if "html" in (content_type or "").casefold() or "javascript" in (content_type or "").casefold():
        blockers.append("active_content_not_allowed")
    return {
        "ok": not blockers,
        "filename": safe_name,
        "extension": extension,
        "size_bytes": int(size_bytes or 0),
        "blockers": blockers,
        "requires_malware_scan_before_publication": True,
        "storage_visibility": "private_by_default",
    }


def production_security_profile(*, provider: str = "provider-neutral") -> dict[str, Any]:
    """Template to be filled with real evidence by each SaaS/product deployment."""
    controls = {name: False for name in PRODUCTION_REQUIRED}
    return {
        "schema": SCHEMA,
        "provider": provider,
        "controls": controls,
        "privileged_controls": {name: False for name in PRIVILEGED_REQUIRED},
        "headers": deepcopy(DEFAULT_SECURITY_HEADERS),
        "policy": {
            "private_by_default": True,
            "deny_cross_tenant_by_default": True,
            "secrets_in_runtime_only": True,
            "human_approval_for_destructive_external_paid_actions": True,
            "production_requires_security_gate_pass": True,
        },
    }


def security_summary(controls: dict[str, Any] | None, *, privileged_access: bool = False) -> dict[str, Any]:
    gate = security_by_default_gate(controls, production=True, privileged_access=privileged_access)
    return {
        "schema": gate["schema"],
        "status": gate["status"],
        "passed": gate["passed_total"],
        "required": gate["required_total"],
        "missing": list(gate["missing"]),
    }

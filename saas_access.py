"""Server-side access boundaries for the private pilot and future customer SaaS.

The pilot preserves the author's existing namespace. Customer mode is explicit
and fail-closed: only Streamlit's verified OIDC user can establish an actor.
Editorial profiles, headers, query parameters and session-state fields are never
authentication. Tenant-aware storage can be tested independently, but the whole
customer UI remains blocked while legacy filesystem/export boundaries are open.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
import os
import re
from typing import Any, Iterator, Mapping

from security_baseline import authorize_action


class AccessDenied(PermissionError):
    """Safe access error; contains no claims, credentials or filesystem paths."""


@dataclass(frozen=True)
class AccessActor:
    subject: str
    issuer: str
    tenant_id: str
    role: str = "member"
    authenticated: bool = True


_ACTOR: ContextVar[AccessActor | None] = ContextVar("faithbloom_verified_actor", default=None)
PERMISSIONS = {
    "viewer": {"view", "storage.read", "storage.list"},
    "member": {"view", "storage.read", "storage.list", "storage.write", "storage.delete"},
    "admin": {"view", "storage.read", "storage.list", "storage.write", "storage.delete"},
}
# These are concrete open boundaries, not configuration toggles that an operator
# can waive. A later implementation must replace the affected I/O and its tests.
CUSTOMER_BLOCKERS = (
    "legacy_filesystem_exports_not_tenant_isolated",
    "shared_runtime_state_not_tenant_isolated",
    "cloud_index_updates_without_compare_and_swap",
)


def access_mode(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    value = str(env.get("FAITHBLOOM_ACCESS_MODE", "pilot")).strip().lower()
    if value not in {"pilot", "multi_tenant"}:
        raise AccessDenied("Modo de acesso inválido; acesso bloqueado.")
    return value


def _trusted_issuers(environ: Mapping[str, str] | None = None) -> set[str]:
    env = os.environ if environ is None else environ
    return {item.strip() for item in str(env.get("FAITHBLOOM_OIDC_ISSUERS", "")).split(",") if item.strip()}


def access_readiness(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Configuration/implementation readiness only, never a live OIDC certificate."""
    env = os.environ if environ is None else environ
    try:
        mode = access_mode(env)
    except AccessDenied:
        return {"mode": "invalid", "ready": False, "status": "BLOCKED", "blockers": ["invalid_access_mode"], "customer_ready": False}
    if mode == "pilot":
        return {"mode": mode, "ready": True, "status": "PILOT", "blockers": [], "customer_ready": False}
    blockers = list(CUSTOMER_BLOCKERS)
    if not _trusted_issuers(env):
        blockers.insert(0, "oidc_issuer_allowlist_not_configured")
    return {"mode": mode, "ready": False, "status": "BLOCKED", "blockers": blockers, "customer_ready": False}


def _server_role(tenant_id: str, environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    raw = str(env.get("FAITHBLOOM_ACCESS_ROLES", "")).strip()
    if not raw:
        return "member"
    try:
        configured = json.loads(raw)
        if not isinstance(configured, dict):
            raise ValueError
        role = configured.get(tenant_id, "member")
        if role not in PERMISSIONS:
            raise ValueError
        return role
    except (ValueError, TypeError):
        raise AccessDenied("Configuração de permissões inválida; acesso bloqueado.") from None


def actor_from_trusted_claims(claims: Mapping[str, Any], *, environ: Mapping[str, str] | None = None) -> AccessActor:
    """Only for a server-verified OIDC claim set, never an editable user payload."""
    subject = claims.get("sub")
    issuer = claims.get("iss")
    if claims.get("authenticated") is not True or not isinstance(subject, str) or not subject.strip() or not isinstance(issuer, str):
        raise AccessDenied("Identidade OIDC verificada necessária.")
    if issuer not in _trusted_issuers(environ):
        raise AccessDenied("Emissor OIDC não autorizado.")
    # Hash a structured tuple: delimiting strings by ':' can alias identities.
    canonical = json.dumps([issuer, subject], ensure_ascii=False, separators=(",", ":"))
    tenant_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return AccessActor(subject, issuer, tenant_id, _server_role(tenant_id, environ))


def current_actor() -> AccessActor | None:
    return _ACTOR.get()


@contextmanager
def access_context(trusted_actor: AccessActor | Mapping[str, Any]) -> Iterator[AccessActor]:
    """Scoped trusted-server injection for workers and isolated integration tests."""
    actor = trusted_actor if isinstance(trusted_actor, AccessActor) else actor_from_trusted_claims(trusted_actor)
    if actor.authenticated is not True or not re.fullmatch(r"[a-f0-9]{64}", actor.tenant_id) or actor.role not in PERMISSIONS:
        raise AccessDenied("Identidade autenticada e permissões válidas necessárias.")
    token = _ACTOR.set(actor)
    try:
        yield actor
    finally:
        _ACTOR.reset(token)


def require_action(action: str, *, resource_tenant_id: str = "") -> AccessActor | None:
    """Real authorization call used at each tenant-storage boundary."""
    if access_mode() == "pilot":
        return None
    actor = current_actor()
    decision = authorize_action(
        authenticated=bool(actor and actor.authenticated),
        role=actor.role if actor else "viewer",
        action=action,
        permissions=PERMISSIONS,
        actor_tenant_id=actor.tenant_id if actor else "",
        resource_tenant_id=resource_tenant_id,
    )
    if not decision["allowed"] or actor is None:
        raise AccessDenied("Acesso não autorizado a este recurso.")
    return actor


def _streamlit_actor(st_module: Any) -> AccessActor:
    user = getattr(st_module, "user", None)
    # is_logged_in is supplied by the Streamlit user object, not session_state.
    if user is None or getattr(user, "is_logged_in", False) is not True:
        raise AccessDenied("Entre com a conta autorizada para continuar.")
    def claim(key: str) -> Any:
        try:
            value = getattr(user, key, None)
            if value is None:
                value = user.get(key) if hasattr(user, "get") else None
            return value
        except Exception:
            return None
    return actor_from_trusted_claims({"authenticated": True, "sub": claim("sub"), "iss": claim("iss")})


def require_streamlit_access(st_module: Any) -> AccessActor | None:
    """Call before any page reads data; always clear a previous run's identity."""
    _ACTOR.set(None)
    try:
        if access_mode() == "pilot":
            return None
        actor = _streamlit_actor(st_module)
        # Do not enable a customer session merely because its OIDC login works.
        readiness = access_readiness()
        if not readiness["ready"]:
            raise AccessDenied(
                "O acesso para clientes está bloqueado enquanto o isolamento dos "
                "arquivos, do estado compartilhado e dos índices não estiver concluído."
            )
        _ACTOR.set(actor)
        require_action("view")
        return actor
    except AccessDenied as exc:
        _ACTOR.set(None)
        st_module.error(str(exc))
        st_module.stop()
        # Defensive for test doubles or UI adapters whose stop() returns.
        raise AccessDenied(str(exc)) from None

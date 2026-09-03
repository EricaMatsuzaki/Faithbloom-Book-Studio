"""FaithBloom 2.0 — Refinamento 13: Stable Release Hardening.

Camada offline/operacional para preparar o SaaS para uma release estável sem
misturar responsabilidades editoriais com infraestrutura. Este módulo oferece:
- schema de dados versionado e migrações idempotentes;
- recovery points imutáveis de estado (cópias de trabalho, nunca overwrite silencioso);
- configurações globais sem armazenar secrets;
- onboarding verificável;
- política de papéis/permissões (não substitui autenticação);
- audit log sanitizado;
- diagnóstico de ambiente e Stable Gate.

Nenhuma função deste módulo chama modelos de IA nem gasta créditos.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage_backend import BACKEND, backend_status

SCHEMA_NAME = "faithbloom.project-state"
CURRENT_DATA_SCHEMA = 4
SETTINGS_SCHEMA = "faithbloom.settings.v1"
SETTINGS_PATH = "system/settings.json"
AUDIT_PATH = "system/audit-log.json"
RECOVERY_PREFIX = "recovery"

DEFAULT_SETTINGS = {
    "schema": SETTINGS_SCHEMA,
    "author_name": "",
    "default_author_profile_id": "",
    "default_locale": "pt-BR",
    "default_age_profile": "3-8",
    "default_trim": "8.5x8.5",
    "autosave_enabled": True,
    "recovery_before_major_change": True,
    "bible_guard_required": True,
    "onboarding_completed": False,
    "deployment_mode": "development",
}

ROLE_PERMISSIONS = {
    "owner": {
        "view", "edit_content", "generate_ai", "approve_editorial", "approve_quality",
        "publish", "manage_platforms", "manage_users", "restore_backup", "change_settings",
    },
    "editor": {"view", "edit_content", "generate_ai", "approve_editorial", "manage_platforms"},
    "reviewer": {"view", "approve_editorial", "approve_quality"},
    "viewer": {"view"},
}

_SECRET_KEY_RE = re.compile(r"(?i)(secret|token|password|api[_-]?key|service[_-]?role|authorization)")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").casefold()).strip("-")
    return s or "sem-titulo"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def state_fingerprint(state: dict) -> str:
    return hashlib.sha256(_canonical(state or {}).encode("utf-8")).hexdigest()


def sanitize_for_log(value: Any) -> Any:
    """Remove valores de campos com aparência de segredo antes de persistir logs."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            out[k] = "[REDACTED]" if _SECRET_KEY_RE.search(str(k)) else sanitize_for_log(v)
        return out
    if isinstance(value, list):
        return [sanitize_for_log(v) for v in value]
    if isinstance(value, tuple):
        return [sanitize_for_log(v) for v in value]
    if isinstance(value, str) and (value.startswith("sk-") or value.startswith("Bearer ")):
        return "[REDACTED]"
    return value


def detect_project_schema(state: dict) -> int:
    try:
        return int((state or {}).get("_faithbloom_schema_version") or 0)
    except Exception:
        return 0


def _append_migration(state: dict, from_version: int, to_version: int, note: str) -> None:
    history = state.setdefault("_faithbloom_migrations", [])
    marker = f"{from_version}->{to_version}"
    if any(x.get("migration") == marker for x in history if isinstance(x, dict)):
        return
    history.append({"migration": marker, "at": _now(), "note": note})


def migrate_project_state(state: dict, target_version: int = CURRENT_DATA_SCHEMA) -> dict:
    """Migra uma CÓPIA do estado. É idempotente e nunca persiste automaticamente."""
    original = copy.deepcopy(state or {})
    work = copy.deepcopy(original)
    start = detect_project_schema(work)
    if start > target_version:
        return {
            "state": work, "from_version": start, "to_version": start, "changed": False,
            "changes": [], "warning": f"Projeto usa schema {start}, superior ao suportado ({target_version}).",
            "fingerprint_before": state_fingerprint(original), "fingerprint_after": state_fingerprint(work),
        }

    changes: list[str] = []
    version = start
    if version < 1 and target_version >= 1:
        work.setdefault("project_meta", {})
        work["project_meta"].setdefault("title", work.get("titulo", ""))
        work["project_meta"].setdefault("collection", work.get("colecao", ""))
        work["project_meta"].setdefault("original_locale", work.get("idioma_original", "pt-BR"))
        work["project_meta"].setdefault("created_with", "FaithBloom Book Studio")
        _append_migration(work, version, 1, "Metadados de projeto normalizados sem alterar conteúdo editorial.")
        version = 1; changes.append("project_meta")

    if version < 2 and target_version >= 2:
        work.setdefault("workflow", {})
        work["workflow"].setdefault("human_approval_required", True)
        work["workflow"].setdefault("no_silent_overwrite", True)
        work.setdefault("content_protection", {})
        work["content_protection"]["bible_guard_required"] = True
        work["content_protection"].setdefault("original_preserved", True)
        _append_migration(work, version, 2, "Proteções de aprovação humana e Bible Guard registradas.")
        version = 2; changes.append("workflow/content_protection")

    if version < 3 and target_version >= 3:
        work.setdefault("stable_release", {})
        work["stable_release"].setdefault("migration_ready", True)
        work["stable_release"].setdefault("last_recovery_point", "")
        work["stable_release"].setdefault("last_stable_gate", "")
        _append_migration(work, version, 3, "Campos operacionais de recovery/stable gate adicionados.")
        version = 3; changes.append("stable_release")

    if version < 4 and target_version >= 4:
        auth = work.get("authorship") if isinstance(work.get("authorship"), dict) else {}
        authors = auth.get("authors") if isinstance(auth.get("authors"), list) else []
        if not authors and str(work.get("autora") or "").strip():
            name = str(work.get("autora") or "").strip()
            authors = [{"profile_id":"", "role":"author", "order":1, "credit_as":name, "display_name_snapshot":name, "profile_version_snapshot":0, "legacy_snapshot":True}]
        work["authorship"] = {
            "schema": "faithbloom.project-authorship.v1",
            "authors": authors,
            "contributors": auth.get("contributors") if isinstance(auth.get("contributors"), list) else [],
            "cover_credit_override": str(auth.get("cover_credit_override") or "").strip(),
            "updated_at": auth.get("updated_at") or _now(),
        }
        _append_migration(work, version, 4, "Autoria estruturada adicionada; crédito legado preservado como snapshot quando existente.")
        version = 4; changes.append("authorship")

    work["_faithbloom_schema"] = SCHEMA_NAME
    work["_faithbloom_schema_version"] = version
    return {
        "state": work, "from_version": start, "to_version": version,
        "changed": state_fingerprint(original) != state_fingerprint(work),
        "changes": changes, "warning": "",
        "fingerprint_before": state_fingerprint(original), "fingerprint_after": state_fingerprint(work),
    }


def ensure_project_schema(state: dict) -> dict:
    return migrate_project_state(state)["state"]


def migration_preview(state: dict) -> dict:
    r = migrate_project_state(state)
    return {k: v for k, v in r.items() if k != "state"}


def load_settings() -> dict:
    raw = BACKEND.get_json(SETTINGS_PATH, {}) or {}
    out = copy.deepcopy(DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        out.update({k: v for k, v in raw.items() if k in out or not str(k).startswith("_")})
    out["schema"] = SETTINGS_SCHEMA
    out["bible_guard_required"] = True
    return out


def save_settings(settings: dict, *, actor: str = "owner") -> dict:
    clean = copy.deepcopy(DEFAULT_SETTINGS)
    clean.update({k: v for k, v in (settings or {}).items() if not _SECRET_KEY_RE.search(str(k))})
    clean["schema"] = SETTINGS_SCHEMA
    clean["bible_guard_required"] = True
    clean["updated_at"] = _now()
    BACKEND.put_json(SETTINGS_PATH, clean)
    record_audit_event("settings.updated", actor=actor, details={"changed_fields": sorted(clean.keys())})
    return clean


def can(role: str, action: str) -> bool:
    return action in ROLE_PERMISSIONS.get((role or "viewer").lower(), set())


def identity_from_environment() -> dict:
    role = os.environ.get("FAITHBLOOM_USER_ROLE", "owner").strip().lower() or "owner"
    if role not in ROLE_PERMISSIONS:
        role = "viewer"
    return {
        "name": os.environ.get("FAITHBLOOM_USER_NAME", "Autora").strip() or "Autora",
        "role": role,
        "auth_mode": os.environ.get("FAITHBLOOM_AUTH_MODE", "none").strip().lower() or "none",
        "authenticated": os.environ.get("FAITHBLOOM_AUTHENTICATED", "").strip().lower() in {"1", "true", "yes"},
    }


def permission_matrix() -> list[dict]:
    actions = [
        "view", "edit_content", "generate_ai", "approve_editorial", "approve_quality",
        "publish", "manage_platforms", "manage_users", "restore_backup", "change_settings",
    ]
    return [{"action": a, **{r: can(r, a) for r in ROLE_PERMISSIONS}} for a in actions]


def record_audit_event(action: str, *, actor: str = "system", role: str = "", project: dict | None = None,
                       details: dict | None = None, status: str = "ok") -> dict:
    events = BACKEND.get_json(AUDIT_PATH, []) or []
    if not isinstance(events, list):
        events = []
    event = {
        "event_id": uuid.uuid4().hex,
        "at": _now(), "actor": actor, "role": role, "action": action, "status": status,
        "project": {
            "title": (project or {}).get("titulo", ""), "collection": (project or {}).get("colecao", ""),
            "fingerprint": state_fingerprint(project or {}) if project else "",
        },
        "details": sanitize_for_log(details or {}),
    }
    events.append(event)
    BACKEND.put_json(AUDIT_PATH, events[-1000:])
    return event


def list_audit_events(limit: int = 100) -> list[dict]:
    events = BACKEND.get_json(AUDIT_PATH, []) or []
    return list(reversed(events[-max(1, int(limit)):])) if isinstance(events, list) else []


def create_recovery_point(state: dict, *, label: str = "manual", actor: str = "autora", role: str = "owner") -> dict:
    if not state:
        raise ValueError("Estado do projeto vazio")
    migrated = ensure_project_schema(state)
    fp = state_fingerprint(migrated)
    title = migrated.get("titulo", "sem-titulo")
    collection = migrated.get("colecao", "")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rid = f"{stamp}-{fp[:12]}-{uuid.uuid4().hex[:6]}"
    path = f"{RECOVERY_PREFIX}/{_slug(collection)}/{_slug(title)}/{rid}.json"
    payload = {
        "schema": "faithbloom.recovery-point.v1", "recovery_id": rid, "created_at": _now(),
        "label": label or "manual", "actor": actor, "role": role,
        "project": {"title": title, "collection": collection, "fingerprint": fp},
        "state": migrated,
        "policy": {"immutable_snapshot": True, "restore_creates_working_copy": True},
    }
    BACKEND.put_json(path, payload)
    record_audit_event("recovery.created", actor=actor, role=role, project=migrated, details={"path": path, "label": label})
    return {**payload, "storage_path": path}


def list_recovery_points(title: str = "", collection: str = "") -> list[dict]:
    prefix = RECOVERY_PREFIX
    if collection:
        prefix += f"/{_slug(collection)}"
        if title:
            prefix += f"/{_slug(title)}"
    out = []
    for path in reversed(BACKEND.list(prefix)):
        if not path.endswith(".json"):
            continue
        item = BACKEND.get_json(path, {}) or {}
        if item.get("schema") != "faithbloom.recovery-point.v1":
            continue
        if title and (item.get("project") or {}).get("title", "").casefold() != title.casefold():
            continue
        out.append({**item, "storage_path": path})
    return out


def load_recovery_point(storage_path: str) -> dict:
    item = BACKEND.get_json(storage_path, {}) or {}
    if item.get("schema") != "faithbloom.recovery-point.v1":
        raise ValueError("Recovery point inválido")
    return item


def prepare_restore_working_copy(current_state: dict, recovery_point: dict) -> dict:
    restored = ensure_project_schema(copy.deepcopy((recovery_point or {}).get("state") or {}))
    if not restored:
        raise ValueError("Recovery point sem state")
    return {
        "working_copy": restored,
        "current_fingerprint": state_fingerprint(current_state or {}),
        "recovery_fingerprint": state_fingerprint(restored),
        "same_content": state_fingerprint(current_state or {}) == state_fingerprint(restored),
        "notice": "A restauração produz uma cópia de trabalho; o original atual não é sobrescrito silenciosamente.",
    }


def environment_diagnostics(environ: dict | None = None) -> dict:
    env = dict(os.environ if environ is None else environ)
    storage = backend_status()
    deployment = (env.get("FAITHBLOOM_DEPLOYMENT_MODE") or "development").strip().lower()
    auth_mode = (env.get("FAITHBLOOM_AUTH_MODE") or "none").strip().lower()
    openrouter = bool((env.get("OPENROUTER_API_KEY") or "").strip())
    persistent = bool(storage.get("persistente_cloud"))
    ffmpeg = bool(shutil.which("ffmpeg"))
    checks = [
        {"id": "python", "ok": sys.version_info >= (3, 10), "level": "blocker", "detail": f"Python {sys.version.split()[0]}"},
        {"id": "storage", "ok": persistent, "level": "blocker" if deployment == "production" else "warning",
         "detail": f"Storage={storage.get('modo')}; produção deve usar persistência externa."},
        {"id": "openrouter", "ok": openrouter, "level": "blocker" if deployment == "production" else "warning",
         "detail": "OPENROUTER_API_KEY configurada" if openrouter else "OPENROUTER_API_KEY ausente; recursos de IA ficarão indisponíveis."},
        {"id": "auth", "ok": auth_mode in {"oidc", "external"}, "level": "blocker" if deployment == "production" else "warning",
         "detail": f"Auth mode={auth_mode}. Perfis de papel internos não substituem login/autenticação."},
        {"id": "ffmpeg", "ok": ffmpeg, "level": "warning", "detail": "FFmpeg disponível" if ffmpeg else "FFmpeg ausente; mix/QA avançado de áudio fica limitado."},
    ]
    blockers = [x for x in checks if not x["ok"] and x["level"] == "blocker"]
    warnings = [x for x in checks if not x["ok"] and x["level"] == "warning"]
    return {
        "deployment_mode": deployment, "storage": storage, "auth_mode": auth_mode,
        "checks": checks, "blockers": blockers, "warnings": warnings, "ok_for_production": not blockers,
    }


def storage_roundtrip_probe() -> dict:
    """Teste pequeno de write/read/delete; não toca em projetos."""
    pid = uuid.uuid4().hex
    path = f"system/probes/{pid}.json"
    payload = {"probe": pid, "at": _now()}
    try:
        BACKEND.put_json(path, payload)
        got = BACKEND.get_json(path, {})
        ok = got == payload
        try:
            BACKEND.delete(path)
        except Exception:
            pass
        return {"ok": ok, "detail": "write/read/delete OK" if ok else "conteúdo lido divergiu", "path": path}
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}", "path": path}


def onboarding_status(settings: dict | None = None, environ: dict | None = None) -> dict:
    s = settings or load_settings()
    env = environment_diagnostics(environ)
    items = [
        {"id": "author", "done": bool((s.get("default_author_profile_id") or s.get("author_name") or "").strip()), "label": "Perfil/nome editorial padrão definido"},
        {"id": "locale", "done": bool((s.get("default_locale") or "").strip()), "label": "Locale padrão definido"},
        {"id": "bible", "done": s.get("bible_guard_required") is True, "label": "Bible Guard obrigatório"},
        {"id": "storage", "done": env["storage"].get("modo") in {"local", "supabase"}, "label": "Storage reconhecido"},
        {"id": "production", "done": env["ok_for_production"] if env["deployment_mode"] == "production" else True,
         "label": "Ambiente de produção sem bloqueadores"},
    ]
    done = sum(1 for x in items if x["done"])
    return {"items": items, "done": done, "total": len(items), "complete": done == len(items)}


def stable_release_gate(*, settings: dict | None = None, include_storage_probe: bool = False,
                        environ: dict | None = None) -> dict:
    env = environment_diagnostics(environ)
    onboarding = onboarding_status(settings, environ)
    smoke = run_offline_stable_smoke()
    checks = [
        {"id": "schema", "ok": CURRENT_DATA_SCHEMA >= 3, "level": "blocker", "detail": f"Project schema v{CURRENT_DATA_SCHEMA}"},
        {"id": "bible_guard", "ok": (settings or load_settings()).get("bible_guard_required") is True, "level": "blocker", "detail": "Bible Guard locked ON"},
        {"id": "offline_smoke", "ok": smoke["ok"], "level": "blocker", "detail": f"{sum(1 for x in smoke['checks'] if x['ok'])}/{len(smoke['checks'])} checks internos"},
        {"id": "onboarding", "ok": onboarding["complete"], "level": "warning", "detail": f"{onboarding['done']}/{onboarding['total']} itens"},
    ]
    checks.extend(env["checks"])
    probe = storage_roundtrip_probe() if include_storage_probe else None
    if probe is not None:
        checks.append({"id": "storage_probe", "ok": probe["ok"], "level": "blocker", "detail": probe["detail"]})
    blockers = [x for x in checks if not x["ok"] and x["level"] == "blocker"]
    warnings = [x for x in checks if not x["ok"] and x["level"] == "warning"]
    return {
        "generated_at": _now(), "status": "PASS" if not blockers else "BLOCKED",
        "ready_for_stable_tag": not blockers, "blockers": blockers, "warnings": warnings,
        "checks": checks, "storage_probe": probe,
        "notice": "PASS é um gate interno do FaithBloom; não substitui smoke test real no Streamlit Cloud nem validações das plataformas.",
    }


def record_incident(context: str, exc: Exception | str, *, project: dict | None = None, actor: str = "system") -> dict:
    incident_id = uuid.uuid4().hex
    detail = str(exc)
    event = record_audit_event(
        "runtime.incident", actor=actor, project=project, status="error",
        details={"incident_id": incident_id, "context": context, "error_type": type(exc).__name__ if isinstance(exc, Exception) else "message", "message": detail[:600]},
    )
    return {"incident_id": incident_id, "event": event}


def run_offline_stable_smoke() -> dict:
    sample = {"titulo": "Smoke Test", "colecao": "QA", "idioma_original": "pt-BR", "cenas_texto": [{"numero": 1, "texto": "Teste."}]}
    mig1 = migrate_project_state(sample)
    mig2 = migrate_project_state(mig1["state"])
    checks = [
        {"name": "migration", "ok": mig1["to_version"] == CURRENT_DATA_SCHEMA},
        {"name": "migration_idempotent", "ok": not mig2["changed"]},
        {"name": "bible_guard", "ok": mig1["state"].get("content_protection", {}).get("bible_guard_required") is True},
        {"name": "owner_publish", "ok": can("owner", "publish")},
        {"name": "viewer_cannot_publish", "ok": not can("viewer", "publish")},
        {"name": "secret_sanitization", "ok": sanitize_for_log({"api_key": "abc"})["api_key"] == "[REDACTED]"},
    ]
    return {"ok": all(x["ok"] for x in checks), "checks": checks}

"""FaithBloom 2.0 — Refinamento 14: Production Deployment & Real E2E.

Ferramentas de implantação que NÃO chamam IA por padrão:
- diagnóstico de configuração de produção;
- adapter de identidade para Streamlit OIDC (quando disponível);
- inventário/migração controlada de storage local -> backend externo;
- health checks e snapshots sanitizados;
- checklist de deploy e smoke E2E rastreável.

Nenhuma função deste módulo considera um deploy "validado em nuvem" sem um probe
real executado no ambiente de destino.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage_backend import (
    BACKEND,
    LocalStorageBackend,
    StorageBackend,
    StorageError,
    backend_status,
)
from stable_hardening import (
    CURRENT_DATA_SCHEMA,
    environment_diagnostics,
    load_settings,
    run_offline_stable_smoke,
    sanitize_for_log,
    stable_release_gate,
    storage_roundtrip_probe,
)

DEPLOY_SCHEMA = "faithbloom.production-deployment.v1"
DEPLOY_HISTORY_PATH = "system/deployment-history.json"
MIGRATION_HISTORY_PATH = "system/storage-migrations.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deployment_config_snapshot(environ: dict | None = None) -> dict:
    """Retorna apenas presença/estado; nunca devolve valores de secrets."""
    env = dict(os.environ if environ is None else environ)
    keys = [
        "OPENROUTER_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "FAITHBLOOM_SUPABASE_BUCKET",
        "FAITHBLOOM_STORAGE_MODE",
        "FAITHBLOOM_DEPLOYMENT_MODE",
        "FAITHBLOOM_AUTH_MODE",
    ]
    present = {k: bool(str(env.get(k, "")).strip()) for k in keys}
    return {
        "schema": DEPLOY_SCHEMA,
        "generated_at": _now(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "storage": backend_status(),
        "settings": {k: v for k, v in load_settings().items() if "key" not in k.casefold() and "secret" not in k.casefold()},
        "env_present": present,
    }


def streamlit_oidc_identity(st_module: Any) -> dict:
    """Lê st.user quando a autenticação OIDC nativa do Streamlit estiver ativa.

    Não autentica por conta própria e não confia em headers arbitrários do usuário.
    """
    user = getattr(st_module, "user", None)
    if user is None:
        return {"authenticated": False, "mode": "unavailable", "name": "", "email": "", "subject": ""}
    try:
        logged = bool(getattr(user, "is_logged_in", False))
    except Exception:
        logged = False
    if not logged:
        return {"authenticated": False, "mode": "streamlit-oidc", "name": "", "email": "", "subject": ""}

    def _get(name: str) -> str:
        try:
            value = getattr(user, name, "")
            if not value and isinstance(user, dict):
                value = user.get(name, "")
            return str(value or "")
        except Exception:
            return ""

    return {
        "authenticated": True,
        "mode": "streamlit-oidc",
        "name": _get("name") or _get("given_name"),
        "email": _get("email"),
        "subject": _get("sub"),
    }


def local_storage_inventory(root: str | None = None) -> dict:
    source = LocalStorageBackend(root)
    items = []
    total = 0
    for rel in source.list(""):
        try:
            data = source.get_bytes(rel)
        except Exception:
            continue
        total += len(data)
        items.append({"path": rel, "bytes": len(data), "sha256": _sha(data)})
    return {"root": str(source.root), "count": len(items), "bytes": total, "items": items}


def plan_storage_migration(source: StorageBackend, target: StorageBackend, prefix: str = "") -> dict:
    planned, identical, conflicts = [], [], []
    for path in source.list(prefix):
        data = source.get_bytes(path)
        src_sha = _sha(data)
        if not target.exists(path):
            planned.append({"path": path, "bytes": len(data), "sha256": src_sha, "action": "copy"})
            continue
        target_data = target.get_bytes(path)
        dst_sha = _sha(target_data)
        if src_sha == dst_sha:
            identical.append({"path": path, "sha256": src_sha, "action": "skip-identical"})
        else:
            conflicts.append({"path": path, "source_sha256": src_sha, "target_sha256": dst_sha, "action": "conflict"})
    return {
        "generated_at": _now(),
        "source": getattr(source, "name", type(source).__name__),
        "target": getattr(target, "name", type(target).__name__),
        "prefix": prefix,
        "copy": planned,
        "identical": identical,
        "conflicts": conflicts,
        "safe_to_run_without_overwrite": not conflicts,
    }


def execute_storage_migration(source: StorageBackend, target: StorageBackend, *, prefix: str = "", allow_overwrite: bool = False) -> dict:
    """Copia byte-a-byte e verifica hash. Conflitos não são sobrescritos por padrão."""
    plan = plan_storage_migration(source, target, prefix)
    copied, skipped, failed = [], list(plan["identical"]), []
    conflict_paths = {x["path"] for x in plan["conflicts"]}

    for item in plan["copy"]:
        path = item["path"]
        try:
            data = source.get_bytes(path)
            target.put_bytes(path, data)
            got = target.get_bytes(path)
            if _sha(got) != item["sha256"]:
                raise StorageError("hash de verificação divergiu após cópia")
            copied.append({**item, "verified": True})
        except Exception as exc:
            failed.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})

    if allow_overwrite:
        for item in plan["conflicts"]:
            path = item["path"]
            try:
                data = source.get_bytes(path)
                target.put_bytes(path, data)
                got = target.get_bytes(path)
                if _sha(got) != _sha(data):
                    raise StorageError("hash de verificação divergiu após overwrite")
                copied.append({"path": path, "bytes": len(data), "sha256": _sha(data), "action": "overwrite", "verified": True})
                conflict_paths.discard(path)
            except Exception as exc:
                failed.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})

    unresolved = [x for x in plan["conflicts"] if x["path"] in conflict_paths]
    result = {
        "schema": "faithbloom.storage-migration-result.v1",
        "migration_id": uuid.uuid4().hex,
        "finished_at": _now(),
        "copied": copied,
        "skipped": skipped,
        "conflicts": unresolved,
        "failed": failed,
        "ok": not failed and not unresolved,
        "notice": "Origem não é apagada. Conflitos só são sobrescritos quando allow_overwrite=True.",
    }
    return result


def production_health(*, include_storage_probe: bool = False, environ: dict | None = None) -> dict:
    start = time.monotonic()
    env = environment_diagnostics(environ)
    smoke = run_offline_stable_smoke()
    gate = stable_release_gate(settings=load_settings(), include_storage_probe=include_storage_probe, environ=environ)
    checks = [
        {"id": "environment", "ok": env["ok_for_production"], "detail": f"{len(env['blockers'])} bloqueadores de ambiente"},
        {"id": "offline_smoke", "ok": smoke["ok"], "detail": f"{sum(1 for x in smoke['checks'] if x['ok'])}/{len(smoke['checks'])} checks"},
        {"id": "stable_gate", "ok": gate["ready_for_stable_tag"], "detail": gate["status"]},
    ]
    blockers = [x for x in checks if not x["ok"]]
    return {
        "schema": "faithbloom.health.v1",
        "generated_at": _now(),
        "status": "healthy" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
        "elapsed_ms": round((time.monotonic() - start) * 1000, 2),
        "storage_probe": gate.get("storage_probe"),
        "notice": "Este health check valida o processo em que foi executado; não prova disponibilidade externa contínua.",
    }


def real_e2e_checklist() -> list[dict]:
    return [
        {"id": "boot", "label": "Aplicação inicia no Streamlit Cloud sem traceback", "required": True},
        {"id": "auth", "label": "Login real/OIDC validado com usuário autorizado", "required": True},
        {"id": "storage", "label": "Write/read/delete real no storage persistente", "required": True},
        {"id": "migration", "label": "Projetos existentes inventariados e migrados com hashes verificados", "required": True},
        {"id": "openrouter_text", "label": "Uma chamada mínima de texto à OpenRouter foi validada manualmente", "required": True},
        {"id": "image_preview", "label": "Uma geração/preview de imagem foi validada manualmente", "required": False},
        {"id": "audio_preview", "label": "Um preview de voz foi validado manualmente", "required": False},
        {"id": "project_roundtrip", "label": "Criar → salvar → recarregar um projeto real sem perda", "required": True},
        {"id": "quality_gate", "label": "Quality Guardian executado num projeto de teste", "required": True},
        {"id": "distribution_package", "label": "Pacote de distribuição de teste gerado e reaberto", "required": True},
        {"id": "restart", "label": "Após reboot/redeploy, projeto continua disponível no storage externo", "required": True},
    ]


def evaluate_real_e2e(evidence: dict[str, bool]) -> dict:
    items = []
    for spec in real_e2e_checklist():
        done = bool(evidence.get(spec["id"], False))
        items.append({**spec, "done": done})
    missing_required = [x for x in items if x["required"] and not x["done"]]
    return {
        "items": items,
        "required_total": sum(1 for x in items if x["required"]),
        "required_done": sum(1 for x in items if x["required"] and x["done"]),
        "cloud_e2e_passed": not missing_required,
        "missing_required": missing_required,
        "notice": "Itens devem ser marcados somente após evidência real no ambiente de produção.",
    }


def append_deployment_record(record: dict) -> dict:
    history = BACKEND.get_json(DEPLOY_HISTORY_PATH, []) or []
    if not isinstance(history, list):
        history = []
    clean = sanitize_for_log(copy.deepcopy(record or {}))
    clean.setdefault("deployment_id", uuid.uuid4().hex)
    clean.setdefault("at", _now())
    history.append(clean)
    BACKEND.put_json(DEPLOY_HISTORY_PATH, history[-200:])
    return clean


def deployment_readiness(environ: dict | None = None) -> dict:
    config = deployment_config_snapshot(environ)
    health = production_health(include_storage_probe=False, environ=environ)
    deployment_mode = (dict(os.environ if environ is None else environ).get("FAITHBLOOM_DEPLOYMENT_MODE") or "development").lower()
    checks = [
        {"id": "production_mode", "ok": deployment_mode == "production", "level": "blocker", "detail": f"mode={deployment_mode}"},
        {"id": "external_storage", "ok": bool(config["storage"].get("persistente_cloud")), "level": "blocker", "detail": f"storage={config['storage'].get('modo')}"},
        {"id": "health", "ok": health["status"] == "healthy", "level": "blocker", "detail": health["status"]},
    ]
    blockers = [x for x in checks if not x["ok"] and x["level"] == "blocker"]
    return {
        "ready_for_cloud_validation": not blockers,
        "checks": checks,
        "blockers": blockers,
        "notice": "Ready for cloud validation não significa Stable. O Real E2E ainda precisa ser executado no Streamlit Cloud.",
    }

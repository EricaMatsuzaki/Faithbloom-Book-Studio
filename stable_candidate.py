"""FaithBloom 2.0 — Refinamento 15: Stable Candidate & Cloud Launch Checklist.

Camada final antes da tag Stable. Este módulo não publica, não cria tags Git e não
considera checkboxes sem evidência como prova suficiente. Ele consolida:
- fingerprint do código/configuração que compõe a candidata;
- checklist cloud com evidências registráveis;
- gate de Release Candidate (RC) independente do gate Stable;
- plano de rollback não destrutivo;
- registro persistente da candidata;
- pacote ZIP de evidências para auditoria/lançamento;
- sign-off humano final sem promover automaticamente a release.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from production_deployment import (
    deployment_config_snapshot,
    deployment_readiness,
    evaluate_real_e2e,
    production_health,
    real_e2e_checklist,
)
from stable_hardening import sanitize_for_log
from storage_backend import BACKEND

ROOT = Path(__file__).resolve().parent
SCHEMA = "faithbloom.stable-candidate.v1"
EVIDENCE_SCHEMA = "faithbloom.cloud-launch-evidence.v1"
CANDIDATE_PREFIX = "system/release-candidates"
EVIDENCE_DRAFT_PATH = "system/release-candidates/cloud-evidence-draft.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str).encode("utf-8")


def _source_files(root: Path | None = None) -> list[Path]:
    """Arquivos que definem funcionalmente a candidata.

    Relatórios gerados, caches e dados runtime ficam fora do fingerprint para que a
    criação do próprio pacote de evidências não invalide a candidata.
    """
    base = (root or ROOT).resolve()
    ignored_parts = {
        ".git", ".pytest_cache", "__pycache__", ".faithbloom_cache", ".faithbloom_data",
        "saida_audio", "saida_imagens", "saida_publicacao", "livros_salvos",
        "livros_colorir_salvos", "bibliotecas_personagens", "galeria_imagens",
    }
    files: list[Path] = []
    for p in base.rglob("*.py"):
        if not any(part in ignored_parts for part in p.relative_to(base).parts):
            files.append(p)
    for rel in ["requirements.txt", ".streamlit/config.toml", ".gitignore"]:
        p = base / rel
        if p.exists() and p.is_file():
            files.append(p)
    return sorted(set(files), key=lambda p: str(p.relative_to(base)))


def source_release_manifest(root: str | Path | None = None) -> dict:
    base = Path(root).resolve() if root else ROOT
    items = []
    total = 0
    for p in _source_files(base):
        data = p.read_bytes()
        total += len(data)
        items.append({
            "path": str(p.relative_to(base)).replace(os.sep, "/"),
            "bytes": len(data),
            "sha256": _sha(data),
        })
    digest = _sha(_json_bytes(items))
    return {
        "schema": "faithbloom.source-manifest.v1",
        "generated_at": _now(),
        "file_count": len(items),
        "bytes": total,
        "source_fingerprint": digest,
        "files": items,
    }


def cloud_launch_checklist() -> list[dict]:
    """Checklist da candidata: reaproveita o E2E real e adiciona resiliência."""
    base = [dict(x) for x in real_e2e_checklist()]
    extras = [
        {"id": "recovery", "label": "Recovery point real criado e restauração em cópia de trabalho validada", "required": True},
        {"id": "rollback", "label": "Plano de rollback revisado e dry-run não destrutivo validado", "required": True},
        {"id": "incident", "label": "Registro de incidente/audit log validado sem expor Secrets", "required": True},
        {"id": "image_preview", "label": "Uma geração/preview de imagem foi validada manualmente", "required": False},
        {"id": "audio_preview", "label": "Um preview de voz foi validado manualmente", "required": False},
    ]
    by_id = {x["id"]: x for x in base}
    for x in extras:
        by_id[x["id"]] = x
    # ordem: checklist original, depois extras realmente novas
    ordered = []
    seen = set()
    for x in base + extras:
        if x["id"] not in seen:
            ordered.append(by_id[x["id"]]); seen.add(x["id"])
    return ordered


def normalize_evidence(evidence: dict | None, *, actor: str = "") -> dict:
    evidence = copy.deepcopy(evidence or {})
    normalized: dict[str, dict] = {}
    for spec in cloud_launch_checklist():
        raw = evidence.get(spec["id"], {})
        if isinstance(raw, bool):
            raw = {"done": raw}
        if not isinstance(raw, dict):
            raw = {}
        normalized[spec["id"]] = {
            "done": bool(raw.get("done", False)),
            "note": str(raw.get("note", "") or "").strip(),
            "reference": str(raw.get("reference", "") or "").strip(),
            "actor": str(raw.get("actor", actor) or actor or "").strip(),
            "at": str(raw.get("at", "") or "").strip(),
        }
    return {"schema": EVIDENCE_SCHEMA, "updated_at": _now(), "items": normalized}


def evidence_to_legacy_bool(evidence: dict | None) -> dict[str, bool]:
    normalized = normalize_evidence((evidence or {}).get("items") if (evidence or {}).get("schema") == EVIDENCE_SCHEMA else evidence)
    return {k: bool(v.get("done")) for k, v in normalized["items"].items()}


def evaluate_cloud_launch_evidence(evidence: dict | None, *, require_note_or_reference: bool = True) -> dict:
    raw_items = (evidence or {}).get("items") if (evidence or {}).get("schema") == EVIDENCE_SCHEMA else evidence
    normalized = normalize_evidence(raw_items)
    legacy = evaluate_real_e2e(evidence_to_legacy_bool(normalized))
    rows = []
    missing_required = []
    weak_required = []
    for spec in cloud_launch_checklist():
        ev = normalized["items"][spec["id"]]
        evidence_detail = bool(ev["note"] or ev["reference"])
        row = {**spec, **ev, "has_evidence_detail": evidence_detail}
        rows.append(row)
        if spec["required"] and not ev["done"]:
            missing_required.append(row)
        elif spec["required"] and require_note_or_reference and not evidence_detail:
            weak_required.append(row)
    passed = not missing_required and not weak_required
    return {
        "schema": "faithbloom.cloud-launch-evaluation.v1",
        "generated_at": _now(),
        "items": rows,
        "required_total": sum(1 for x in rows if x["required"]),
        "required_done": sum(1 for x in rows if x["required"] and x["done"]),
        "missing_required": missing_required,
        "required_without_detail": weak_required,
        "cloud_launch_evidence_passed": passed,
        "legacy_real_e2e_passed": legacy["cloud_e2e_passed"],
        "notice": "Uma candidata exige evidência registrável nos itens obrigatórios; checkbox sozinho não é prova suficiente.",
    }


def save_evidence_draft(evidence: dict, *, actor: str = "") -> dict:
    normalized = normalize_evidence((evidence or {}).get("items") if (evidence or {}).get("schema") == EVIDENCE_SCHEMA else evidence, actor=actor)
    BACKEND.put_json(EVIDENCE_DRAFT_PATH, sanitize_for_log(normalized))
    return normalized


def load_evidence_draft() -> dict:
    value = BACKEND.get_json(EVIDENCE_DRAFT_PATH, {}) or {}
    if value.get("schema") == EVIDENCE_SCHEMA:
        return normalize_evidence(value.get("items") or {})
    return normalize_evidence({})


def build_rollback_plan(*, candidate_version: str, previous_version: str = "2.0.0-rc1", source_manifest: dict | None = None) -> dict:
    manifest = source_manifest or source_release_manifest()
    return {
        "schema": "faithbloom.rollback-plan.v1",
        "generated_at": _now(),
        "candidate_version": candidate_version,
        "previous_version": previous_version,
        "candidate_source_fingerprint": manifest.get("source_fingerprint", ""),
        "principles": [
            "Não apagar a versão anterior durante o lançamento.",
            "Não sobrescrever storage persistente para executar rollback.",
            "Manter recovery points e inventário/migração com hashes.",
            "Rollback de código e rollback de dados são decisões separadas.",
        ],
        "steps": [
            "Preservar o ZIP/commit da versão anterior e a candidata.",
            "Antes do deploy, confirmar recovery points e inventário do storage persistente.",
            "Executar deploy da candidata sem excluir objetos antigos do storage.",
            "Se houver falha bloqueante, reverter o código para a versão anterior.",
            "Validar health check, autenticação e leitura dos projetos após a reversão.",
            "Somente restaurar dados a partir de recovery point quando houver evidência de corrupção/migração incorreta; restaurar primeiro como cópia de trabalho.",
            "Registrar incidente, decisão e fingerprints antes/depois.",
        ],
        "destructive_actions_automatic": False,
    }


def release_candidate_gate(
    evidence: dict | None,
    *,
    deployment_ready: bool | None = None,
    deployment_detail: dict | None = None,
    qa_ok: bool = True,
    source_manifest: dict | None = None,
    require_evidence_detail: bool = True,
) -> dict:
    manifest = source_manifest or source_release_manifest()
    ev = evaluate_cloud_launch_evidence(evidence, require_note_or_reference=require_evidence_detail)
    if deployment_ready is None:
        dep = deployment_readiness()
        deployment_ready = bool(dep.get("ready_for_cloud_validation"))
        deployment_detail = dep
    checks = [
        {"id": "source_manifest", "ok": bool(manifest.get("source_fingerprint")) and manifest.get("file_count", 0) > 0, "level": "blocker", "detail": f"{manifest.get('file_count',0)} arquivos · {manifest.get('source_fingerprint','')[:12]}"},
        {"id": "offline_qa", "ok": bool(qa_ok), "level": "blocker", "detail": "QA offline aprovado" if qa_ok else "QA offline ainda possui falhas"},
        {"id": "deployment_readiness", "ok": bool(deployment_ready), "level": "blocker", "detail": "Ambiente pronto para validação cloud" if deployment_ready else "Readiness de produção bloqueada"},
        {"id": "cloud_evidence", "ok": bool(ev["cloud_launch_evidence_passed"]), "level": "blocker", "detail": f"{ev['required_done']}/{ev['required_total']} obrigatórios marcados; {len(ev['required_without_detail'])} sem detalhe"},
    ]
    blockers = [x for x in checks if not x["ok"] and x["level"] == "blocker"]
    return {
        "schema": "faithbloom.release-candidate-gate.v1",
        "generated_at": _now(),
        "status": "PASS" if not blockers else "BLOCKED",
        "candidate_ready": not blockers,
        "checks": checks,
        "blockers": blockers,
        "source_manifest": manifest,
        "evidence_evaluation": ev,
        "deployment_detail": sanitize_for_log(deployment_detail or {}),
        "notice": "PASS libera a criação de uma Release Candidate registrada; não cria tag Stable, não publica e não prova aprovação por terceiros.",
    }


def create_release_candidate(
    *,
    version: str,
    evidence: dict,
    qa_report: dict | None = None,
    deployment_ready: bool | None = None,
    deployment_detail: dict | None = None,
    actor: str = "owner",
    previous_version: str = "2.0.0-rc1",
    notes: str = "",
) -> dict:
    manifest = source_release_manifest()
    qa_ok = True if qa_report is None else bool(qa_report.get("ok"))
    gate = release_candidate_gate(
        evidence,
        deployment_ready=deployment_ready,
        deployment_detail=deployment_detail,
        qa_ok=qa_ok,
        source_manifest=manifest,
        require_evidence_detail=True,
    )
    if not gate["candidate_ready"]:
        raise ValueError("Release Candidate bloqueada: conclua o gate e as evidências obrigatórias.")
    cid = f"{version.replace('/', '-')}-{uuid.uuid4().hex[:10]}"
    record = {
        "schema": SCHEMA,
        "candidate_id": cid,
        "version": version,
        "created_at": _now(),
        "created_by": actor,
        "status": "candidate",
        "notes": notes,
        "source_manifest": manifest,
        "deployment_snapshot": deployment_config_snapshot(),
        "gate": gate,
        "evidence": normalize_evidence((evidence or {}).get("items") if (evidence or {}).get("schema") == EVIDENCE_SCHEMA else evidence, actor=actor),
        "qa_report": sanitize_for_log(qa_report or {"ok": True, "note": "QA report não anexado ao registro."}),
        "rollback_plan": build_rollback_plan(candidate_version=version, previous_version=previous_version, source_manifest=manifest),
        "manual_signoff": {"approved": False, "actor": "", "at": "", "note": ""},
        "policy": {
            "does_not_create_git_tag": True,
            "does_not_publish": True,
            "stable_requires_current_source": True,
            "stable_requires_manual_signoff": True,
        },
    }
    BACKEND.put_json(f"{CANDIDATE_PREFIX}/{cid}.json", sanitize_for_log(record))
    return record


def list_release_candidates(limit: int = 50) -> list[dict]:
    out = []
    for path in reversed(BACKEND.list(CANDIDATE_PREFIX)):
        if not path.endswith(".json") or path.endswith("cloud-evidence-draft.json"):
            continue
        item = BACKEND.get_json(path, {}) or {}
        if item.get("schema") != SCHEMA:
            continue
        out.append({**item, "storage_path": path})
        if len(out) >= max(1, int(limit)):
            break
    return out


def load_release_candidate(candidate_id: str) -> dict:
    item = BACKEND.get_json(f"{CANDIDATE_PREFIX}/{candidate_id}.json", {}) or {}
    if item.get("schema") != SCHEMA:
        raise ValueError("Release Candidate não encontrada ou inválida")
    return item


def candidate_is_current(candidate: dict, current_manifest: dict | None = None) -> dict:
    current = current_manifest or source_release_manifest()
    expected = ((candidate or {}).get("source_manifest") or {}).get("source_fingerprint", "")
    got = current.get("source_fingerprint", "")
    return {
        "current": bool(expected) and expected == got,
        "candidate_fingerprint": expected,
        "current_fingerprint": got,
        "notice": "Qualquer mudança em código/configuração após a criação da candidata exige uma nova candidata ou revalidação.",
    }


def record_manual_signoff(candidate_id: str, *, approved: bool, actor: str, note: str = "") -> dict:
    record = load_release_candidate(candidate_id)
    record["manual_signoff"] = {"approved": bool(approved), "actor": actor, "at": _now(), "note": note}
    record["status"] = "signed-off" if approved else "candidate"
    BACKEND.put_json(f"{CANDIDATE_PREFIX}/{candidate_id}.json", sanitize_for_log(record))
    return record


def stable_promotion_gate(candidate: dict, *, current_manifest: dict | None = None) -> dict:
    freshness = candidate_is_current(candidate, current_manifest)
    signoff = (candidate or {}).get("manual_signoff") or {}
    gate = (candidate or {}).get("gate") or {}
    checks = [
        {"id": "candidate_gate", "ok": gate.get("status") == "PASS", "detail": gate.get("status", "missing")},
        {"id": "source_current", "ok": freshness["current"], "detail": "source fingerprint vigente" if freshness["current"] else "código/configuração mudou após a candidata"},
        {"id": "manual_signoff", "ok": bool(signoff.get("approved")), "detail": f"sign-off por {signoff.get('actor') or '—'}"},
    ]
    blockers = [x for x in checks if not x["ok"]]
    return {
        "schema": "faithbloom.stable-promotion-gate.v1",
        "status": "PASS" if not blockers else "BLOCKED",
        "ready_to_tag_stable_manually": not blockers,
        "checks": checks,
        "blockers": blockers,
        "freshness": freshness,
        "notice": "PASS significa que a equipe pode criar manualmente a tag Stable após revisar o pacote. O FaithBloom não cria a tag nem publica automaticamente.",
    }


def build_evidence_bundle_bytes(candidate: dict) -> bytes:
    if (candidate or {}).get("schema") != SCHEMA:
        raise ValueError("Registro de candidata inválido")
    payloads = {
        "candidate.json": candidate,
        "source-manifest.json": candidate.get("source_manifest", {}),
        "cloud-evidence.json": candidate.get("evidence", {}),
        "candidate-gate.json": candidate.get("gate", {}),
        "deployment-snapshot.json": candidate.get("deployment_snapshot", {}),
        "qa-report.json": candidate.get("qa_report", {}),
        "rollback-plan.json": candidate.get("rollback_plan", {}),
        "promotion-gate.json": stable_promotion_gate(candidate),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in payloads.items():
            zf.writestr(name, _json_bytes(sanitize_for_log(data)))
        zf.writestr(
            "README.txt",
            (
                "FaithBloom Stable Candidate Evidence Bundle\n"
                "Este pacote registra evidências internas da candidata.\n"
                "Não é certificação da Amazon, Apple, Kobo, Streamlit ou qualquer terceiro.\n"
                "A tag Stable continua sendo uma decisão manual após o promotion gate.\n"
            ).encode("utf-8"),
        )
    return buf.getvalue()

"""FaithBloom 2.0 — Refinamento 20: Stable Candidate RC4 & Final Pre-Launch Gate.

Esta camada reúne os gates que já existiam sem fingir que validações offline equivalem
a um deploy real. O objetivo é deixar a candidata pronta para ser validada no
Streamlit Cloud e impedir a promoção para Stable enquanto faltarem evidências reais.
"""
from __future__ import annotations

import copy
import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

from real_pilot import pilot_readiness
from stable_candidate import (
    EVIDENCE_SCHEMA,
    build_evidence_bundle_bytes,
    candidate_is_current,
    cloud_launch_checklist,
    evaluate_cloud_launch_evidence,
    normalize_evidence,
    source_release_manifest,
    stable_promotion_gate,
)
from stable_hardening import sanitize_for_log
from storage_backend import BACKEND

RC4_SCHEMA = "faithbloom.final-prelaunch.v1"
RC4_PREFIX = "system/final-prelaunch"
RC4_DRAFT = f"{RC4_PREFIX}/evidence-draft.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_prelaunch_test_plan() -> list[dict]:
    """Plano executável no ambiente real; não marca nada automaticamente."""
    base = []
    for item in cloud_launch_checklist():
        base.append({
            **item,
            "environment": "production-cloud",
            "evidence_required": bool(item.get("required")),
            "how_to_validate": {
                "boot": "Abrir o app publicado e confirmar ausência de traceback na interface e nos logs.",
                "auth": "Entrar com um usuário autorizado e confirmar que um usuário não autorizado não obtém o mesmo acesso.",
                "storage": "Criar arquivo/projeto de teste, ler, atualizar e remover o objeto de teste no storage persistente.",
                "migration": "Comparar inventário e SHA-256 de projetos migrados antes/depois sem apagar a origem.",
                "openrouter_text": "Executar uma chamada mínima de texto com a chave configurada somente em Secrets.",
                "image_preview": "Gerar um preview de imagem de baixo custo e registrar aprovação/rejeição manual.",
                "audio_preview": "Gerar um preview curto de voz e registrar aprovação/rejeição manual.",
                "project_roundtrip": "Criar → salvar → fechar/recarregar → comparar conteúdo e fingerprint do projeto.",
                "quality_gate": "Executar Quality Guardian em projeto de teste e registrar o resultado.",
                "distribution_package": "Gerar pacote de uma edição de teste, baixar/reabrir e conferir manifest/preflight.",
                "restart": "Fazer reboot/redeploy e confirmar que o projeto salvo permanece disponível.",
                "recovery": "Criar recovery point, restaurar como working copy e comparar o conteúdo.",
                "rollback": "Revisar o plano e simular rollback de código sem rollback destrutivo de dados.",
                "incident": "Registrar incidente de teste e confirmar sanitização de token/chave/senha no audit log.",
            }.get(item["id"], "Validar manualmente no ambiente de produção e registrar evidência verificável."),
        })
    return base


def final_prelaunch_gate(
    evidence: dict | None,
    *,
    qa_ok: bool,
    deployment_ready: bool,
    pilot_status: dict | None = None,
    source_manifest: dict | None = None,
) -> dict:
    """Gate final antes de criar a RC4.

    Importante: `deployment_ready` é readiness para validar na nuvem; as evidências de
    Cloud E2E continuam obrigatórias e impedem PASS quando não existem.
    """
    manifest = source_manifest or source_release_manifest()
    pilots = copy.deepcopy(pilot_status or pilot_readiness())
    cloud = evaluate_cloud_launch_evidence(evidence, require_note_or_reference=True)
    checks = [
        {
            "id": "source_manifest",
            "ok": bool(manifest.get("source_fingerprint")) and int(manifest.get("file_count", 0) or 0) > 0,
            "detail": f"{manifest.get('file_count', 0)} arquivos · {manifest.get('source_fingerprint', '')[:12]}",
        },
        {"id": "offline_qa", "ok": bool(qa_ok), "detail": "QA offline aprovado" if qa_ok else "QA offline com falhas"},
        {
            "id": "real_pilots",
            "ok": bool(pilots.get("ready_for_next_candidate")),
            "detail": f"{len(pilots.get('profiles_completed') or [])}/{len(pilots.get('profiles_required') or [])} pilotos · {len(pilots.get('open_blocking_bugs') or [])} bugs blocker/high",
        },
        {
            "id": "deployment_readiness",
            "ok": bool(deployment_ready),
            "detail": "Ambiente preparado para validação cloud" if deployment_ready else "Configuração de produção ainda não está pronta",
        },
        {
            "id": "real_cloud_e2e",
            "ok": bool(cloud.get("cloud_launch_evidence_passed")),
            "detail": f"{cloud.get('required_done', 0)}/{cloud.get('required_total', 0)} evidências obrigatórias; {len(cloud.get('required_without_detail') or [])} sem nota/referência",
        },
    ]
    blockers = [x for x in checks if not x["ok"]]
    return {
        "schema": "faithbloom.final-prelaunch-gate.v1",
        "generated_at": _now(),
        "status": "PASS" if not blockers else "BLOCKED",
        "ready_to_create_rc4": not blockers,
        "checks": checks,
        "blockers": blockers,
        "pilot_readiness": sanitize_for_log(pilots),
        "cloud_evidence": cloud,
        "source_manifest": manifest,
        "notice": (
            "PASS autoriza registrar uma Release Candidate final. Não significa Stable nem aprovação por Amazon, Apple, Kobo ou outra plataforma."
        ),
    }


def save_prelaunch_evidence(evidence: dict | None, *, actor: str = "") -> dict:
    raw = (evidence or {}).get("items") if (evidence or {}).get("schema") == EVIDENCE_SCHEMA else evidence
    value = normalize_evidence(raw or {}, actor=actor)
    BACKEND.put_json(RC4_DRAFT, sanitize_for_log(value))
    return value


def load_prelaunch_evidence() -> dict:
    value = BACKEND.get_json(RC4_DRAFT, {}) or {}
    raw = value.get("items") if value.get("schema") == EVIDENCE_SCHEMA else value
    return normalize_evidence(raw or {})


def create_final_candidate_record(
    *,
    version: str,
    evidence: dict,
    qa_report: dict,
    deployment_ready: bool,
    actor: str,
    previous_version: str,
    notes: str = "",
) -> dict:
    gate = final_prelaunch_gate(
        evidence,
        qa_ok=bool((qa_report or {}).get("ok")),
        deployment_ready=deployment_ready,
    )
    if not gate["ready_to_create_rc4"]:
        raise ValueError("RC4 bloqueada: conclua pilotos, QA, configuração de produção e evidências reais do Cloud E2E.")
    cid = f"{version.replace('/', '-')}-{uuid.uuid4().hex[:10]}"
    record = {
        "schema": RC4_SCHEMA,
        "candidate_id": cid,
        "version": version,
        "previous_version": previous_version,
        "created_at": _now(),
        "created_by": actor,
        "status": "final-candidate",
        "notes": str(notes or "").strip(),
        "source_manifest": gate["source_manifest"],
        "gate": gate,
        "evidence": normalize_evidence((evidence or {}).get("items") if (evidence or {}).get("schema") == EVIDENCE_SCHEMA else evidence, actor=actor),
        "qa_report": sanitize_for_log(qa_report or {}),
        "manual_signoff": {"approved": False, "actor": "", "at": "", "note": ""},
        "policy": {
            "cloud_e2e_mandatory": True,
            "pilot_gate_mandatory": True,
            "does_not_auto_deploy": True,
            "does_not_auto_tag_stable": True,
            "does_not_publish_books": True,
        },
    }
    BACKEND.put_json(f"{RC4_PREFIX}/{cid}.json", sanitize_for_log(record))
    return record


def record_final_signoff(candidate_id: str, *, approved: bool, actor: str, note: str = "") -> dict:
    path = f"{RC4_PREFIX}/{candidate_id}.json"
    record = BACKEND.get_json(path, {}) or {}
    if record.get("schema") != RC4_SCHEMA:
        raise ValueError("Candidata final não encontrada.")
    if approved and not str(actor or "").strip():
        raise ValueError("Informe quem está aprovando o sign-off.")
    record["manual_signoff"] = {
        "approved": bool(approved), "actor": str(actor or "").strip(), "at": _now(), "note": str(note or "").strip()
    }
    record["status"] = "signed-off" if approved else "final-candidate"
    BACKEND.put_json(path, sanitize_for_log(record))
    return record


def list_final_candidates(limit: int = 50) -> list[dict]:
    out = []
    for path in reversed(BACKEND.list(RC4_PREFIX)):
        if not path.endswith(".json") or path.endswith("evidence-draft.json"):
            continue
        value = BACKEND.get_json(path, {}) or {}
        if value.get("schema") == RC4_SCHEMA:
            out.append({**value, "storage_path": path})
        if len(out) >= max(1, int(limit)):
            break
    return out


def final_stable_promotion_gate(candidate: dict, *, current_manifest: dict | None = None) -> dict:
    manifest = current_manifest or source_release_manifest()
    current = candidate_is_current({"source_manifest": candidate.get("source_manifest") or {}}, manifest)
    signoff = candidate.get("manual_signoff") or {}
    gate = candidate.get("gate") or {}
    checks = [
        {"id": "final_gate", "ok": gate.get("status") == "PASS", "detail": gate.get("status", "missing")},
        {"id": "source_current", "ok": bool(current.get("current")), "detail": "fingerprint vigente" if current.get("current") else "fonte mudou após a RC4"},
        {"id": "manual_signoff", "ok": bool(signoff.get("approved")), "detail": f"sign-off por {signoff.get('actor') or '—'}"},
    ]
    blockers = [x for x in checks if not x["ok"]]
    return {
        "schema": "faithbloom.final-stable-promotion-gate.v1",
        "status": "PASS" if not blockers else "BLOCKED",
        "ready_to_tag_stable_manually": not blockers,
        "checks": checks,
        "blockers": blockers,
        "freshness": current,
        "notice": "Mesmo com PASS, a tag/deploy Stable é uma ação humana externa ao FaithBloom.",
    }


def build_final_evidence_bundle_bytes(candidate: dict) -> bytes:
    if candidate.get("schema") != RC4_SCHEMA:
        raise ValueError("Registro RC4 inválido.")
    # Reusa o formato conhecido do bundle de Stable Candidate, além do gate RC4.
    shim = {
        "schema": "faithbloom.stable-candidate.v1",
        **candidate,
        "gate": candidate.get("gate") or {},
        "rollback_plan": {
            "candidate_version": candidate.get("version"),
            "previous_version": candidate.get("previous_version"),
            "principles": ["Rollback de código e dados são separados", "Não sobrescrever storage para reverter código"],
        },
    }
    base_zip = build_evidence_bundle_bytes(shim)
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base_zip), "r") as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr("final-prelaunch-gate.json", json.dumps(sanitize_for_log(candidate.get("gate") or {}), ensure_ascii=False, indent=2))
        target.writestr("final-stable-promotion-gate.json", json.dumps(final_stable_promotion_gate(candidate), ensure_ascii=False, indent=2))
        target.writestr("cloud-test-plan.json", json.dumps(build_prelaunch_test_plan(), ensure_ascii=False, indent=2))
    return out.getvalue()

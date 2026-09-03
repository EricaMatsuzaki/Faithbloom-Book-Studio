"""FaithBloom Refinamento 21 — Biblical/Theological Reference Validator.

O LLM pode SUGERIR uma referência, mas a referência só recebe status VALIDATED
quando existe fonte aprovada, contexto conferido e aprovação humana. Este módulo
não traduz nem fornece texto bíblico.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

SCHEMA = "faithbloom.biblical-reference-validation.v1"

# Aceita referências como João 3:16, 1 João 4:8, Salmo 27:14, Lucas 2:11-14.
REFERENCE_RE = re.compile(r"^\s*(?:[1-3]\s+)?[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{1,40}\s+\d{1,3}:\d{1,3}(?:[-–]\d{1,3})?\s*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reference_syntax_ok(reference: str) -> bool:
    return bool(REFERENCE_RE.match(str(reference or "")))


def create_reference_candidate(reference: str, *, reason: str = "", suggested_by: str = "ai") -> dict:
    payload = {
        "schema": SCHEMA,
        "reference": str(reference or "").strip(),
        "reason": str(reason or "").strip(),
        "suggested_by": suggested_by,
        "status": "candidate_unverified",
        "source_name": "",
        "source_reference": "",
        "context_note": "",
        "context_verified": False,
        "human_approved": False,
        "approved_by": "",
        "validated_at": "",
        "scripture_text_stored_here": False,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    payload["candidate_id"] = sha256(raw).hexdigest()[:16]
    return payload


def validate_reference_candidate(candidate: dict, *, source_name: str, source_reference: str,
                                 context_note: str, context_verified: bool,
                                 human_approved: bool, approved_by: str = "") -> dict:
    ref = str((candidate or {}).get("reference") or "").strip()
    checks = [
        {"id": "reference_syntax", "ok": reference_syntax_ok(ref), "detail": ref or "referência ausente"},
        {"id": "approved_source", "ok": bool(str(source_name or "").strip() and str(source_reference or "").strip()), "detail": str(source_name or "")},
        {"id": "context_verified", "ok": bool(context_verified and str(context_note or "").strip()), "detail": "contexto conferido" if context_verified else "contexto ainda não conferido"},
        {"id": "human_approval", "ok": bool(human_approved), "detail": f"aprovado por {approved_by or 'responsável'}" if human_approved else "aprovação humana pendente"},
    ]
    blockers = [x for x in checks if not x["ok"]]
    return {
        **dict(candidate or {}),
        "schema": SCHEMA,
        "reference": ref,
        "source_name": str(source_name or "").strip(),
        "source_reference": str(source_reference or "").strip(),
        "context_note": str(context_note or "").strip(),
        "context_verified": bool(context_verified),
        "human_approved": bool(human_approved),
        "approved_by": str(approved_by or "").strip(),
        "checks": checks,
        "status": "validated" if not blockers else "candidate_unverified",
        "validated_at": _now() if not blockers else "",
        "scripture_text_stored_here": False,
        "notice": "Validação refere-se à referência/contexto. Texto bíblico completo continua protegido no Bible Guard e não é traduzido pela IA.",
    }


def reference_gate(state: dict) -> dict:
    record = state.get("bible_reference_validation") or state.get("bible_reference_candidate") or {}
    ref = str(state.get("versiculo_referencia") or record.get("reference") or "").strip()
    if not ref:
        return {"status": "MISSING", "ok": False, "reference": "", "reason": "Referência bíblica ausente."}
    if record.get("status") == "validated" and record.get("reference") == ref:
        return {"status": "PASS", "ok": True, "reference": ref, "reason": "Referência/contexto validados com fonte e aprovação humana."}
    return {"status": "NEEDS_VALIDATION", "ok": False, "reference": ref, "reason": "Referência existe, mas ainda não possui validação completa de fonte/contexto/aprovação humana."}

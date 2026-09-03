"""FaithBloom Refinamento 21 — Market & Bestseller Intelligence.

A camada separa estritamente:
- evidência observada/importada (fonte + data + mercado), e
- inferência/sugestão produzida por modelo.

Nunca estima volume, demanda, competição ou probabilidade de best-seller sem
dados observados que sustentem a afirmação.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

EVIDENCE_SCHEMA = "faithbloom.market-evidence.v1"
BRIEF_SCHEMA = "faithbloom.market-intelligence-brief.v1"

OBSERVED_SOURCE_TYPES = {
    "official_platform", "author_dashboard", "third_party_research_tool",
    "retailer_observation", "survey", "manual_competitor_review", "web_research",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def make_market_evidence(*, source_type: str, source_name: str, market: str,
                         observation: str, source_url: str = "", observed_at: str = "",
                         metric_name: str = "", metric_value: Any = None,
                         notes: str = "", verified_by_human: bool = False) -> dict:
    payload = {
        "schema": EVIDENCE_SCHEMA,
        "source_type": _norm(source_type),
        "source_name": _norm(source_name),
        "source_url": _norm(source_url),
        "market": _norm(market),
        "observation": _norm(observation),
        "observed_at": _norm(observed_at) or _now(),
        "metric_name": _norm(metric_name),
        "metric_value": metric_value,
        "notes": _norm(notes),
        "verified_by_human": bool(verified_by_human),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    payload["evidence_id"] = sha256(raw).hexdigest()[:16]
    return payload


def validate_market_evidence(item: dict) -> dict:
    issues = []
    if not isinstance(item, dict):
        return {"ok": False, "issues": ["evidência não é objeto"]}
    if item.get("source_type") not in OBSERVED_SOURCE_TYPES:
        issues.append("source_type não é uma fonte observável reconhecida")
    for field in ("source_name", "market", "observation", "observed_at"):
        if not _norm(item.get(field)):
            issues.append(f"{field} ausente")
    # Uma fonte sem URL ainda pode ser dashboard/observação manual, mas precisa de verificação humana.
    if not _norm(item.get("source_url")) and not item.get("verified_by_human"):
        issues.append("fonte sem URL/referência exige confirmação humana")
    return {"ok": not issues, "issues": issues, "evidence_id": item.get("evidence_id", "")}


def classify_market_mode(evidence: list[dict] | None) -> dict:
    rows = [x for x in (evidence or []) if isinstance(x, dict)]
    valid = [x for x in rows if validate_market_evidence(x)["ok"]]
    if valid:
        return {
            "mode": "observed_evidence",
            "label": "Evidência observada disponível",
            "valid_evidence_count": len(valid),
            "can_make_observed_market_claims": True,
        }
    return {
        "mode": "model_inference_only",
        "label": "Somente inferência de IA — sem dados observados de mercado",
        "valid_evidence_count": 0,
        "can_make_observed_market_claims": False,
    }


def evidence_prompt(evidence: list[dict] | None) -> str:
    mode = classify_market_mode(evidence)
    if mode["mode"] != "observed_evidence":
        return (
            "MODO DE MERCADO: MODEL_INFERENCE_ONLY. Não há evidência observada suficiente. "
            "Você pode sugerir hipóteses/keywords/posicionamento, mas NÃO pode afirmar volume, demanda, "
            "competição, ranking, tendência atual ou chance de best-seller como fato. Rotule conclusões como hipótese."
        )
    valid = [x for x in (evidence or []) if validate_market_evidence(x)["ok"]]
    compact = [
        {
            "id": x.get("evidence_id"), "market": x.get("market"),
            "source": x.get("source_name"), "observed_at": x.get("observed_at"),
            "observation": x.get("observation"), "metric": x.get("metric_name"),
            "value": x.get("metric_value"),
        }
        for x in valid
    ]
    return (
        "MODO DE MERCADO: OBSERVED_EVIDENCE. Baseie alegações atuais SOMENTE nas evidências abaixo e cite os IDs. "
        "Não generalize além do que as fontes sustentam.\nEVIDÊNCIAS:\n" + json.dumps(compact, ensure_ascii=False, indent=2)
    )


def build_market_brief(state: dict, *, evidence: list[dict] | None = None,
                       hypotheses: list[str] | None = None) -> dict:
    rows = deepcopy(evidence if evidence is not None else state.get("market_evidence") or [])
    validations = [{"item": x, "validation": validate_market_evidence(x)} for x in rows if isinstance(x, dict)]
    valid = [x["item"] for x in validations if x["validation"]["ok"]]
    mode = classify_market_mode(valid)
    return {
        "schema": BRIEF_SCHEMA,
        "generated_at": _now(),
        "title": state.get("titulo", ""),
        "market_mode": mode,
        "evidence": valid,
        "invalid_evidence": [x for x in validations if not x["validation"]["ok"]],
        "hypotheses": [_norm(x) for x in (hypotheses or []) if _norm(x)],
        "claims_policy": {
            "can_claim_observed_demand": bool(valid),
            "can_claim_search_volume": any(_norm(x.get("metric_name")).lower() in {"search_volume", "volume de busca"} and x.get("metric_value") is not None for x in valid),
            "can_claim_competition_metric": any("compet" in _norm(x.get("metric_name")).lower() and x.get("metric_value") is not None for x in valid),
            "bestseller_probability_allowed": False,
        },
        "notice": "O brief mede evidência disponível; não prevê sucesso comercial nem garante best-seller.",
    }

"""FaithBloom Refinamento 19 — Real Pilot & Bug Fix.

Auditoria rápida e conservadora para projetos-piloto reais antes da Stable.
Não chama IA, não altera PDFs de origem e não decodifica todas as imagens do PDF
só para levantar metadados. O objetivo é detectar regressões/inconsistências e
registrar evidências reproduzíveis para correção.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import uuid
from typing import Any

from pypdf import PdfReader

from storage_backend import BACKEND

PILOT_RUN_PREFIX = "pilot/runs"
BUG_INDEX_PATH = "pilot/bugs/index.json"

PILOT_PROFILES = {
    "mel_master": {
        "label": "🌷 Quando Mel Aprendeu a Esperar — Master",
        "kind": "story",
        "expected_reference": "Eclesiastes 3:1",
        "focus": [
            "Book Doctor", "Character Universe", "Emotional & Color Director",
            "Translation & Localization", "Cover Master", "Quality Guardian", "Publishing",
        ],
        "notes": "Usar como referência visual/editorial da coleção; não remasterizar silenciosamente.",
    },
    "mel_natal": {
        "label": "🎄 Quando Mel Aprendeu o Verdadeiro Sentido do Natal — Remaster",
        "kind": "story",
        "expected_reference": "Lucas 2:11",
        "focus": [
            "Book Doctor", "Character Universe", "Restoration Studio",
            "Emotional & Color Director", "Quality Guardian", "Publishing",
        ],
        "notes": "Validar consistência de Mel/Manu e repetições editoriais antes do Remastered.",
    },
    "bolufinhas": {
        "label": "🖍️ Bolufinhas / Cute Friends — Coloring Pilot",
        "kind": "coloring",
        "expected_reference": "",
        "focus": [
            "Coloring Book Doctor", "Style DNA", "Asset Library", "Character Universe",
            "Cover Master", "Activity Book Studio", "Quality Guardian", "Publishing",
        ],
        "notes": "Validar line art, múltiplas propostas de capa, biblioteca de personagens e fluxo de reutilização.",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _compact_text(text: str) -> str:
    """Normaliza texto para comparar PDFs que espaçam cada letra graficamente."""
    return "".join(ch.casefold() for ch in str(text or "") if ch.isalnum())


def _status_ppi(ppi: float) -> str:
    if ppi >= 300:
        return "excellent"
    if ppi >= 200:
        return "attention"
    return "low"


def _walk_xobjects(resources: Any, *, page_number: int, page_w_in: float, page_h_in: float) -> list[dict]:
    """Lê metadados de XObjects recursivamente sem decodificar pixels."""
    out: list[dict] = []
    visited: set[tuple[Any, Any] | int] = set()

    def visit_dict(xobjects: Any):
        if not xobjects:
            return
        try:
            items = xobjects.items()
        except Exception:
            return
        for name, ref in items:
            try:
                key = (getattr(ref, "idnum", None), getattr(ref, "generation", None))
                if key == (None, None):
                    key = id(ref)
                if key in visited:
                    continue
                visited.add(key)
                obj = ref.get_object() if hasattr(ref, "get_object") else ref
                subtype = str(obj.get("/Subtype") or "")
                if subtype == "/Image":
                    w = int(obj.get("/Width") or 0)
                    h = int(obj.get("/Height") or 0)
                    ppi = min(w / page_w_in, h / page_h_in) if w and h and page_w_in and page_h_in else 0.0
                    out.append({
                        "page": page_number,
                        "name": str(name),
                        "width_px": w,
                        "height_px": h,
                        "filter": str(obj.get("/Filter") or ""),
                        "ppi_estimated_full_page": round(ppi, 1) if ppi else None,
                        "ppi_status": _status_ppi(ppi) if ppi else "indeterminate",
                        "estimate": True,
                    })
                elif subtype == "/Form":
                    nested = (obj.get("/Resources") or {}).get("/XObject") if obj.get("/Resources") else None
                    visit_dict(nested)
            except Exception:
                continue

    try:
        visit_dict((resources or {}).get("/XObject"))
    except Exception:
        pass
    return out


def fast_pdf_audit(path: str | Path, *, expected_reference: str = "", include_text_checks: bool = True) -> dict:
    """Audita um PDF real sem extrair/decodificar todas as imagens.

    PPI é conservador assumindo uso em página inteira, exatamente como sinalizado
    no Book Doctor. Para PPI efetivo, o layout/tamanho de colocação ainda precisa
    ser interpretado pelo módulo de impressão.
    """
    p = Path(path)
    reader = PdfReader(str(p))
    pages: list[dict] = []
    images: list[dict] = []
    texts: list[str] = []

    for number, page in enumerate(reader.pages, 1):
        mb = page.mediabox
        w_in = float(mb.width) / 72.0
        h_in = float(mb.height) / 72.0
        page_images = _walk_xobjects(page.get("/Resources") or {}, page_number=number, page_w_in=w_in, page_h_in=h_in)
        images.extend(page_images)
        raw_text = ""
        if include_text_checks:
            try:
                raw_text = page.extract_text() or ""
            except Exception:
                raw_text = ""
        texts.append(raw_text)
        pages.append({
            "page": number,
            "width_in": round(w_in, 4),
            "height_in": round(h_in, 4),
            "image_xobjects": len(page_images),
            "text_chars": len(raw_text),
        })

    sizes = sorted({(x["width_in"], x["height_in"]) for x in pages})
    compact = [_compact_text(x) for x in texts]
    overlaps: list[dict] = []
    if include_text_checks:
        for i in range(len(compact) - 1):
            a, b = compact[i], compact[i + 1]
            if min(len(a), len(b)) < 60:
                continue
            ratio = SequenceMatcher(None, a, b).ratio()
            contained = (a in b or b in a)
            containment = min(len(a), len(b)) / max(len(a), len(b)) if contained else 0.0
            if ratio >= 0.82 or containment >= 0.70:
                overlaps.append({
                    "page_a": i + 1,
                    "page_b": i + 2,
                    "similarity": round(ratio, 3),
                    "contained": contained,
                    "containment": round(containment, 3),
                    "note": "Possível repetição editorial ou duplicação da camada textual; confirmar visualmente antes de corrigir.",
                })

    repeated_reference: list[dict] = []
    ref_compact = _compact_text(expected_reference)
    if ref_compact:
        for i, text in enumerate(compact, 1):
            count = text.count(ref_compact)
            if count >= 2:
                repeated_reference.append({"page": i, "reference": expected_reference, "occurrences": count})

    ppi_counts = Counter(x["ppi_status"] for x in images)
    blank_text_pages = [i + 1 for i, x in enumerate(compact) if not x]
    alerts: list[dict] = []
    if len(sizes) > 1:
        alerts.append({"severity": "blocker", "area": "layout", "message": "O PDF contém tamanhos de página diferentes."})
    if ppi_counts.get("low"):
        alerts.append({
            "severity": "attention", "area": "images",
            "message": f"{ppi_counts['low']} imagem(ns) XObject ficam abaixo de 200 PPI na estimativa conservadora de página inteira; confirme o tamanho real de colocação antes de reilustrar.",
        })
    if overlaps:
        alerts.append({
            "severity": "attention", "area": "editorial",
            "message": f"{len(overlaps)} par(es) de páginas adjacentes com forte sobreposição textual foram detectados. A ferramenta não altera nada automaticamente.",
        })
    if repeated_reference:
        alerts.append({
            "severity": "attention", "area": "bible-guard",
            "message": "A referência bíblica aparece repetida na camada textual de pelo menos uma página; inspecione visualmente. O Bible Guard não corrige nem traduz o versículo automaticamente.",
        })

    return {
        "schema": "faithbloom.real-pilot.pdf-audit.v1",
        "file_name": p.name,
        "file_size_bytes": p.stat().st_size,
        "sha256": _sha256(p),
        "pages_total": len(pages),
        "page_sizes_in": sizes,
        "uniform_page_size": len(sizes) <= 1,
        "pages_with_text": sum(bool(x) for x in compact),
        "blank_text_pages": blank_text_pages,
        "image_xobjects_total": len(images),
        "image_ppi_status_counts": dict(ppi_counts),
        "images": images,
        "adjacent_text_overlap": overlaps,
        "repeated_bible_reference": repeated_reference,
        "alerts": alerts,
        "ppi_note": "Estimativa conservadora de XObjects assumindo página inteira; PPI efetivo depende do tamanho real de colocação.",
        "source_unchanged": True,
    }


def run_pilot(path: str | Path, profile_id: str, *, cover_path: str | Path | None = None, save: bool = True) -> dict:
    if profile_id not in PILOT_PROFILES:
        raise KeyError(f"Perfil de piloto desconhecido: {profile_id}")
    profile = deepcopy(PILOT_PROFILES[profile_id])
    audit = fast_pdf_audit(path, expected_reference=profile.get("expected_reference", ""))
    cover_audit = fast_pdf_audit(cover_path, include_text_checks=True) if cover_path else None
    run_id = uuid.uuid4().hex
    blockers = [x for x in audit.get("alerts", []) if x.get("severity") == "blocker"]
    attentions = [x for x in audit.get("alerts", []) if x.get("severity") == "attention"]
    report = {
        "schema": "faithbloom.real-pilot.run.v1",
        "id": run_id,
        "profile_id": profile_id,
        "profile": profile,
        "created_at": _now(),
        "interior": audit,
        "cover": cover_audit,
        "focus_modules": profile.get("focus", []),
        "gate": {
            "status": "blocked" if blockers else ("manual-review" if attentions else "technical-pass"),
            "blockers": len(blockers),
            "attentions": len(attentions),
            "meaning": "technical-pass não significa publicação aprovada; ainda exige revisão visual/humana e os gates dos Studios aplicáveis.",
        },
        "policy": "Piloto mede e registra evidências; não sobrescreve originais e não aplica correções silenciosas.",
    }
    if save:
        BACKEND.put_json(f"{PILOT_RUN_PREFIX}/{run_id}.json", report)
    return report


def list_pilot_runs() -> list[dict]:
    out: list[dict] = []
    for path in BACKEND.list(PILOT_RUN_PREFIX):
        if path.endswith(".json"):
            value = BACKEND.get_json(path, None)
            if isinstance(value, dict):
                out.append(value)
    return sorted(out, key=lambda x: x.get("created_at", ""), reverse=True)


def register_bug(
    title: str, *, module: str, severity: str = "medium", reproduction: str = "",
    evidence: str = "", pilot_run_id: str = "", status: str = "open",
) -> dict:
    sev = severity if severity in {"blocker", "high", "medium", "low"} else "medium"
    stat = status if status in {"open", "investigating", "fixed", "verified", "wont-fix"} else "open"
    rows = BACKEND.get_json(BUG_INDEX_PATH, []) or []
    if not isinstance(rows, list):
        rows = []
    bug = {
        "id": uuid.uuid4().hex,
        "title": re.sub(r"\s+", " ", str(title or "")).strip(),
        "module": re.sub(r"\s+", " ", str(module or "")).strip(),
        "severity": sev,
        "status": stat,
        "reproduction": str(reproduction or "").strip(),
        "evidence": str(evidence or "").strip(),
        "pilot_run_id": str(pilot_run_id or "").strip(),
        "created_at": _now(),
        "updated_at": _now(),
    }
    if not bug["title"]:
        raise ValueError("Informe um título para o bug.")
    rows.append(bug)
    BACKEND.put_json(BUG_INDEX_PATH, rows)
    return bug


def list_bugs(*, include_closed: bool = True) -> list[dict]:
    rows = BACKEND.get_json(BUG_INDEX_PATH, []) or []
    if not isinstance(rows, list):
        return []
    if not include_closed:
        rows = [x for x in rows if x.get("status") not in {"verified", "wont-fix"}]
    order = {"blocker": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(rows, key=lambda x: (order.get(x.get("severity"), 9), x.get("created_at", "")))


def update_bug_status(bug_id: str, status: str, *, evidence: str = "") -> dict:
    if status not in {"open", "investigating", "fixed", "verified", "wont-fix"}:
        raise ValueError("Status de bug inválido.")
    rows = BACKEND.get_json(BUG_INDEX_PATH, []) or []
    if not isinstance(rows, list):
        rows = []
    bug = next((x for x in rows if x.get("id") == bug_id), None)
    if not bug:
        raise KeyError("Bug não encontrado.")
    # fixed ainda não é verified: exige evidência de reteste para fechar o gate.
    if status == "verified" and not (str(evidence or "").strip() or str(bug.get("evidence") or "").strip()):
        raise ValueError("Para marcar como verified, registre evidência do reteste.")
    bug["status"] = status
    if evidence:
        bug["evidence"] = str(evidence).strip()
    bug["updated_at"] = _now()
    BACKEND.put_json(BUG_INDEX_PATH, rows)
    return bug


def pilot_readiness() -> dict:
    runs = list_pilot_runs()
    latest_by_profile: dict[str, dict] = {}
    for run in runs:
        latest_by_profile.setdefault(run.get("profile_id", ""), run)
    missing = [pid for pid in PILOT_PROFILES if pid not in latest_by_profile]
    bugs = list_bugs(include_closed=False)
    blocking_bugs = [x for x in bugs if x.get("severity") in {"blocker", "high"}]
    pilot_blockers = [
        {"profile_id": pid, "run_id": run.get("id"), "blockers": run.get("gate", {}).get("blockers", 0)}
        for pid, run in latest_by_profile.items() if int(run.get("gate", {}).get("blockers", 0) or 0) > 0
    ]
    ready = not missing and not blocking_bugs and not pilot_blockers
    return {
        "schema": "faithbloom.real-pilot.readiness.v1",
        "ready_for_next_candidate": ready,
        "profiles_required": list(PILOT_PROFILES),
        "profiles_completed": sorted(latest_by_profile),
        "profiles_missing": missing,
        "open_blocking_bugs": blocking_bugs,
        "pilot_blockers": pilot_blockers,
        "note": "Este gate prepara a próxima candidata; não substitui o Real E2E no Streamlit Cloud nem validações das plataformas.",
    }

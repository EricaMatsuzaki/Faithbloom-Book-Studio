"""FaithBloom Refinamento 21 — Bestseller Readiness System.

Avalia fatores CONTROLÁVEIS de competitividade editorial/comercial sem gerar
probabilidade de best-seller e sem transformar inferência em dado de mercado.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Callable

from biblical_reference_validator import reference_gate
from market_intelligence import classify_market_mode

SCHEMA = "faithbloom.bestseller-readiness.v1"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _scenes(state):
    rows = state.get("cenas_texto") or []
    return [x if isinstance(x, dict) else {"texto": str(x)} for x in rows]


def _words(text):
    return re.findall(r"\b[\wÀ-ÿ'-]+\b", str(text or ""), flags=re.UNICODE)


def _result(cid, domain, label, status, detail, action="", evidence=None, blocker=False):
    return {
        "id": cid, "domain": domain, "label": label, "status": status,
        "detail": detail, "action": action, "evidence": evidence or {},
        "blocker": bool(blocker),
    }


def evaluate_bestseller_readiness(state: dict, *, market_evidence: list[dict] | None = None) -> dict:
    scenes = _scenes(state)
    title = str(state.get("titulo") or "").strip()
    audience = str(state.get("faixa_etaria") or "3–8").strip()
    checks = []

    checks.append(_result(
        "audience_defined", "editorial", "Público definido",
        "PASS" if audience else "NEEDS_WORK",
        f"Faixa/público: {audience or 'não definido'}.",
        "Definir público primário e mercado antes de posicionar o livro.", blocker=True,
    ))

    first = " ".join(str(x.get("texto") or "") for x in scenes[:2]).strip()
    hook_ok = bool(first and len(_words(first)) >= 5)
    checks.append(_result(
        "opening_hook", "story", "Gancho inicial",
        "PASS" if hook_ok else "NEEDS_REVIEW",
        "Há conteúdo narrativo suficiente nas primeiras cenas para revisão do gancho." if hook_ok else "Não há abertura suficiente para avaliar o gancho.",
        "Revisar se as primeiras páginas despertam curiosidade/emoção rapidamente.",
        {"opening_excerpt": first[:280]},
    ))

    emotion_rows = [x for x in scenes if str(x.get("emocao") or "").strip()]
    checks.append(_result(
        "emotional_arc", "story", "Arco emocional explícito",
        "PASS" if len(emotion_rows) >= max(3, len(scenes)//2) else "NEEDS_REVIEW",
        f"{len(emotion_rows)}/{len(scenes)} cenas possuem emoção registrada.",
        "Completar/validar o mapa emocional e a progressão da transformação.",
        {"scenes_with_emotion": len(emotion_rows), "scene_count": len(scenes)},
    ))

    action_rows = [x for x in scenes if str(x.get("contexto_visual") or "").strip()]
    checks.append(_result(
        "visual_page_turns", "story", "Ação visual / page-turn",
        "PASS" if len(action_rows) >= max(3, len(scenes)//2) else "NEEDS_REVIEW",
        f"{len(action_rows)}/{len(scenes)} cenas possuem direção/contexto visual registrado.",
        "Revisar se cada virada de página acrescenta ação, reação, descoberta ou mudança visual.",
    ))

    readability_ok = state.get("revisao_aprovada") is True
    checks.append(_result(
        "read_aloud", "editorial", "Leitura em voz alta",
        "PASS" if readability_ok else "NEEDS_WORK",
        "Revisão editorial aprovada." if readability_ok else "Revisão editorial ainda não aprovada.",
        "Concluir revisão de ritmo, frases, repetição suave e naturalidade oral.", blocker=True,
    ))

    bible = reference_gate(state)
    checks.append(_result(
        "christian_reference", "faith", "Referência bíblica/contexto",
        "PASS" if bible["ok"] else "NEEDS_EVIDENCE",
        bible["reason"],
        "Validar referência e contexto com fonte aprovada; não traduzir versículo pela IA.",
        {"reference": bible.get("reference", "")}, blocker=True,
    ))

    characters = state.get("personagens") or {}
    approved_chars = [p for p in characters.values() if isinstance(p, dict) and p.get("aparencia_aprovada")]
    char_status = "PASS" if characters and len(approved_chars) == len(characters) else "NEEDS_REVIEW"
    checks.append(_result(
        "character_memorability", "visual", "Personagens oficiais e consistentes",
        char_status,
        f"{len(approved_chars)}/{len(characters)} personagens com aparência aprovada.",
        "Aprovar Character Masters e executar consistência visual antes de considerar a edição pronta.",
    ))

    images = state.get("cenas_imagem") or []
    approved_images = [x for x in images if isinstance(x, dict) and x.get("aprovado")]
    checks.append(_result(
        "visual_consistency", "visual", "Ilustrações aprovadas",
        "PASS" if images and len(approved_images) == len(images) else "NEEDS_REVIEW",
        f"{len(approved_images)}/{len(images)} imagens de cena aprovadas.",
        "Revisar consistência, narrativa visual, cor e impressão cena por cena.",
    ))

    cover_ready = bool(state.get("arte_capa_frontal") or state.get("capa_ebook") or state.get("capa_fisica_pdf"))
    cover_preflight = state.get("capa_fisica_preflight") or {}
    checks.append(_result(
        "cover_thumbnail", "commercial", "Capa / leitura em thumbnail",
        "NEEDS_REVIEW" if cover_ready else "NEEDS_WORK",
        "Há arte/capa para avaliação de thumbnail e posicionamento." if cover_ready else "Capa ainda não disponível.",
        "Executar revisão de thumbnail, hierarquia, legibilidade e genre fit; não assumir conversão sem teste/evidência.",
        {"cover_preflight": cover_preflight},
    ))

    synopsis = str(state.get("sinopse_vendas_curta") or "").strip()
    keywords = state.get("palavras_chave_kdp") or []
    categories = state.get("categorias_sugeridas") or []
    metadata_ok = bool(title and synopsis and len(keywords) >= 3 and len(categories) >= 1)
    checks.append(_result(
        "metadata_positioning", "commercial", "Metadados e posicionamento",
        "PASS" if metadata_ok else "NEEDS_WORK",
        f"Título={'sim' if title else 'não'}, sinopse={'sim' if synopsis else 'não'}, keywords={len(keywords)}, categorias={len(categories)}.",
        "Completar metadados e revisar relevância por marketplace.",
    ))

    evidence = market_evidence if market_evidence is not None else state.get("market_evidence") or []
    market_mode = classify_market_mode(evidence)
    checks.append(_result(
        "market_evidence", "market", "Evidência de mercado",
        "PASS" if market_mode["can_make_observed_market_claims"] else "NEEDS_EVIDENCE",
        market_mode["label"],
        "Adicionar pesquisa observada com fonte/data/mercado para validar diferenciação, demanda ou competição.",
        market_mode,
    ))

    launch = state.get("material_lancamento") or {}
    checks.append(_result(
        "launch_plan", "commercial", "Materiais de lançamento",
        "PASS" if isinstance(launch, dict) and len(launch) >= 3 else "NEEDS_WORK",
        f"{len(launch) if isinstance(launch, dict) else 0} materiais de lançamento registrados.",
        "Preparar mensagem, canais, calendário e acompanhamento sem prometer ranking.",
    ))

    qcert = state.get("quality_guardian_certificate") or {}
    qpass = bool(qcert and (qcert.get("status") in {"passed", "PASS", "approved", "INTERNAL_QUALITY_GATE_PASSED"} or qcert.get("passed") is True))
    checks.append(_result(
        "quality_gate", "quality", "Quality Guardian vigente",
        "PASS" if qpass else "NEEDS_WORK",
        "Quality Gate interno registrado." if qpass else "Quality Gate final ainda não comprovado neste estado.",
        "Executar/reexecutar o Quality Guardian para a versão atual.", blocker=True,
    ))

    preflight = state.get("preflight_impressao") or {}
    print_ready = bool(state.get("pdf_miolo_print_ready") or preflight.get("ok") is True)
    checks.append(_result(
        "production_readiness", "production", "Arquivo tecnicamente publicável",
        "PASS" if print_ready else "NEEDS_WORK",
        "Há evidência de print-ready/preflight." if print_ready else "Print-ready/preflight final ainda não está comprovado.",
        "Concluir preflight específico da plataforma e prova/preview oficial quando aplicável.", blocker=True,
    ))

    blockers = [x for x in checks if x["blocker"] and x["status"] != "PASS"]
    evidence_gaps = [x for x in checks if x["status"] == "NEEDS_EVIDENCE"]
    needs_work = [x for x in checks if x["status"] in {"NEEDS_WORK", "NEEDS_REVIEW"}]
    if blockers:
        status = "BLOCKED"
    elif evidence_gaps:
        status = "NEEDS_EVIDENCE"
    elif needs_work:
        status = "READY_FOR_HUMAN_REVIEW"
    else:
        status = "CONTROLLED_FACTORS_READY"

    return {
        "schema": SCHEMA,
        "generated_at": _now(),
        "title": title,
        "status": status,
        "criteria": checks,
        "counts": {
            "total": len(checks),
            "pass": sum(1 for x in checks if x["status"] == "PASS"),
            "needs_review": len(needs_work),
            "needs_evidence": len(evidence_gaps),
            "blockers": len(blockers),
        },
        "blockers": blockers,
        "evidence_gaps": evidence_gaps,
        "policy": {
            "bestseller_probability_generated": False,
            "sales_guarantee": False,
            "fake_market_metrics_forbidden": True,
            "human_editorial_decision_required": True,
        },
        "notice": (
            "Bestseller Readiness mede fatores controláveis de qualidade/competitividade. "
            "Não prevê vendas, ranking, demanda futura nem garante best-seller."
        ),
    }

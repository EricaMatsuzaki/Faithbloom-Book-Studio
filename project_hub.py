"""FaithBloom Refinamento 12 — Production Release & Project Hub.

Camada agregadora e read-only por padrão: reúne evidências já salvas pelos
Studios sem inventar percentuais de qualidade e sem marcar etapas como prontas
apenas porque um módulo existe.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json

from quality_guardian import project_fingerprint

STATUS_META = {
    "complete": ("🟢", "Concluído"),
    "attention": ("🟡", "Revisar"),
    "blocked": ("🔴", "Bloqueado"),
    "in_progress": ("🟠", "Em andamento"),
    "not_started": ("⚪", "Não iniciado"),
    "optional": ("🔵", "Opcional"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def same_project(title: str, collection: str, other_title: str, other_collection: str = "") -> bool:
    """Combina por título; coleção só restringe quando ambos os lados a informam."""
    if not _norm(title) or _norm(title) != _norm(other_title):
        return False
    a, b = _norm(collection), _norm(other_collection)
    return not (a and b) or a == b


def status_card(stage_id: str, title: str, status: str, detail: str, *, evidence=None,
                action_page: str = "", action_label: str = "Abrir") -> dict:
    icon, label = STATUS_META[status]
    return {
        "id": stage_id, "title": title, "status": status, "icon": icon,
        "status_label": label, "detail": detail, "evidence": evidence or [],
        "action_page": action_page, "action_label": action_label,
    }


def _approved_illustrations(state: dict) -> tuple[int, int]:
    candidates = state.get("ilustracoes") or state.get("imagens_cenas") or state.get("imagens") or []
    if isinstance(candidates, dict):
        candidates = list(candidates.values())
    if not isinstance(candidates, list):
        return 0, 0
    total = len(candidates)
    approved = 0
    for item in candidates:
        if isinstance(item, dict):
            if item.get("aprovada") is True or item.get("approved") is True or item.get("status") in {"approved", "aprovada"}:
                approved += 1
    return approved, total


def _translation_summary(projects: list[dict]) -> dict:
    locales, versions, approved = set(), 0, 0
    for p in projects:
        for locale, ed in (p.get("edicoes") or {}).items():
            locales.add(locale)
            versions += len((ed or {}).get("versoes") or [])
            if (ed or {}).get("aprovada_id"):
                approved += 1
    return {"projects": len(projects), "locales": sorted(locales), "versions": versions, "approved_locales": approved}


def _activity_summary(projects: list[dict]) -> dict:
    pages = approved = qa_ready = 0
    for p in projects:
        plist = p.get("pages") or []
        pages += len(plist)
        approved += sum(1 for x in plist if x.get("status") == "approved")
        qa_ready += sum(1 for x in plist if (x.get("qa") or {}).get("ready") is True or x.get("qa_ready") is True)
    return {"projects": len(projects), "pages": pages, "approved_pages": approved, "qa_ready_pages": qa_ready}


def _audio_summary(projects: list[dict]) -> dict:
    approved_projects = sum(1 for p in projects if p.get("status") == "approved" and (p.get("final_author_approval") or {}).get("approved"))
    locales = sorted({p.get("locale") for p in projects if p.get("locale")})
    return {"projects": len(projects), "approved_projects": approved_projects, "locales": locales}


def _guardian_summary(state: dict, reports: list[dict]) -> dict:
    fp = project_fingerprint(state)
    current = [r for r in reports if r.get("project_fingerprint") == fp]
    latest = (current or reports or [None])[0]
    if not latest:
        return {"exists": False, "current": False, "passed": False, "report": None, "fingerprint": fp}
    cert = latest.get("certificate") or {}
    cert_status = str(cert.get("status") or "").strip().upper()
    passed = cert_status == "INTERNAL_QUALITY_GATE_PASSED" and bool((latest.get("author_final_approval") or {}).get("approved"))
    return {"exists": True, "current": latest.get("project_fingerprint") == fp, "passed": passed, "report": latest, "fingerprint": fp}


def _distribution_summary(state: dict, plans: list[dict]) -> dict:
    fp = project_fingerprint(state)
    current = [p for p in plans if p.get("project_fingerprint") == fp]
    latest = (current or plans or [None])[0]
    if not latest:
        return {"exists": False, "current": False, "plan": None, "total": 0, "ready": 0, "blocked": 0, "live": 0}
    s = latest.get("summary") or {}
    return {
        "exists": True, "current": latest.get("project_fingerprint") == fp, "plan": latest,
        "total": s.get("total", len(latest.get("editions") or [])), "ready": s.get("ready", 0),
        "blocked": s.get("blocked", 0), "live": s.get("live", 0),
    }


def build_project_overview(state: dict, *, translations=None, activities=None, audiobooks=None,
                           guardian_reports=None, distribution_plans=None) -> dict:
    """Cria visão consolidada somente a partir de evidências observáveis."""
    state = deepcopy(state or {})
    translations = deepcopy(translations or [])
    activities = deepcopy(activities or [])
    audiobooks = deepcopy(audiobooks or [])
    guardian_reports = deepcopy(guardian_reports or [])
    distribution_plans = deepcopy(distribution_plans or [])

    title = state.get("titulo") or "Projeto sem título"
    collection = state.get("colecao", "")
    scenes = state.get("cenas_texto") or []
    chars = state.get("personagens") or {}
    approved_ill, total_ill = _approved_illustrations(state)
    tr = _translation_summary(translations)
    act = _activity_summary(activities)
    aud = _audio_summary(audiobooks)
    qg = _guardian_summary(state, guardian_reports)
    dist = _distribution_summary(state, distribution_plans)

    stages = []
    stages.append(status_card("master", "Book Master", "complete", "Projeto salvo e disponível como fonte das edições derivadas.", evidence=[f"Título: {title}", f"Idioma Master: {state.get('idioma_original') or 'não informado'}"], action_page="pages/15_📚_Biblioteca_Editorial.py", action_label="Abrir Biblioteca Editorial"))

    try:
        from author_profiles import authorship_summary
        auth = authorship_summary(state)
    except Exception:
        auth = {"has_primary_author": bool(str(state.get("autora") or "").strip()), "author_display": str(state.get("autora") or ""), "contributors": []}
    astatus = "complete" if auth.get("has_primary_author") else "attention"
    adetail = (f"Autoria: {auth.get('author_display')}. {len(auth.get('contributors') or [])} colaborador(es) adicional(is)." if auth.get("has_primary_author") else "Nenhum autor principal estruturado foi definido para esta obra.")
    stages.append(status_card("authorship", "Autoria & Créditos", astatus, adetail, action_page="pages/32_✍️_Autores_e_Colaboradores.py", action_label="Gerenciar créditos"))

    if scenes and state.get("revisao_aprovada") is True:
        editorial_status, editorial_detail = "complete", f"{len(scenes)} cena(s) com revisão editorial aprovada."
    elif scenes:
        editorial_status, editorial_detail = "attention", f"{len(scenes)} cena(s) encontradas; a aprovação editorial ainda não está registrada."
    else:
        editorial_status, editorial_detail = "not_started", "Ainda não encontrei cenas de história neste Book Master."
    stages.append(status_card("editorial", "História & Editorial", editorial_status, editorial_detail, action_page="pages/5_#L01f50d_Analisar_Livro.py", action_label="Revisar livro"))

    br = state.get("bestseller_readiness_report") or {}
    if not br:
        br_status, br_detail = "optional", "Bestseller Readiness ainda não executado. Ele avalia fatores controláveis e não prevê vendas."
    elif br.get("status") == "CONTROLLED_FACTORS_READY":
        br_status, br_detail = "complete", "Fatores controláveis do Bestseller Readiness passaram; sucesso comercial continua não garantido."
    elif br.get("status") == "BLOCKED":
        br_status, br_detail = "attention", f"Readiness possui {((br.get('counts') or {}).get('blockers',0))} bloqueio(s) controlável(is)."
    else:
        br_status, br_detail = "attention", f"Readiness: {br.get('status','revisar')}."
    stages.append(status_card("bestseller_readiness", "Agent Skills & Bestseller Readiness", br_status, br_detail, action_page="pages/37_🧠_Agent_Skills_Bestseller_Readiness.py", action_label="Abrir Readiness"))

    if chars:
        cdetail = f"{len(chars)} personagem(ns) vinculado(s) ao projeto. A consistência visual final continua sendo validada pelo Character Guardian."
        cstatus = "complete"
    else:
        cdetail, cstatus = "Nenhum personagem vinculado ao Book Master.", "attention" if scenes else "not_started"
    stages.append(status_card("characters", "Personagens", cstatus, cdetail, action_page="pages/14_👥_Character_Universe.py", action_label="Abrir Character Universe"))

    if total_ill:
        vstatus = "complete" if approved_ill == total_ill else "in_progress"
        vdetail = f"{approved_ill}/{total_ill} ilustração(ões) registradas como aprovadas."
    else:
        vstatus, vdetail = "not_started", "Nenhuma lista estruturada de ilustrações foi encontrada neste Master; o Hub não presume aprovação visual."
    stages.append(status_card("visual", "Ilustrações & Visual", vstatus, vdetail, action_page="pages/19_✨_Restoration_Studio.py", action_label="Abrir Restoration Studio"))

    if tr["projects"]:
        tstatus = "complete" if tr["approved_locales"] and tr["approved_locales"] == len(tr["locales"]) else "in_progress"
        tdetail = f"{tr['approved_locales']}/{len(tr['locales'])} locale(s) com versão aprovada; {tr['versions']} versão(ões) preservadas."
    else:
        tstatus, tdetail = "optional", "Nenhuma edição traduzida vinculada; tradução é opcional conforme a estratégia de publicação."
    stages.append(status_card("translation", "Tradução & Localização", tstatus, tdetail, action_page="pages/21_Translation_Localization_Studio.py", action_label="Abrir Translation Studio"))

    if act["projects"]:
        astatus = "complete" if act["pages"] and act["approved_pages"] == act["pages"] else "in_progress"
        adetail = f"{act['approved_pages']}/{act['pages']} folha(s) aprovadas em {act['projects']} projeto(s) de atividades."
    else:
        astatus, adetail = "optional", "Nenhum Activity Book vinculado; este formato é opcional."
    stages.append(status_card("activities", "Activity Books", astatus, adetail, action_page="pages/23_🧩_Activity_Book_Studio.py", action_label="Abrir Activity Studio"))

    if aud["projects"]:
        astatus = "complete" if aud["approved_projects"] == aud["projects"] else "in_progress"
        adetail = f"{aud['approved_projects']}/{aud['projects']} projeto(s) com mix final ouvido/aprovado."
    else:
        astatus, adetail = "optional", "Nenhum audiobook vinculado; áudio é opcional conforme a edição."
    stages.append(status_card("audio", "Audiobook", astatus, adetail, action_page="pages/24_🎧_Audiobook_Studio.py", action_label="Abrir Audiobook Studio"))

    if not qg["exists"]:
        qstatus, qdetail = "not_started", "Quality Guardian ainda não foi executado para este título."
    elif not qg["current"]:
        qstatus, qdetail = "blocked", "Existe relatório anterior, mas ele não corresponde ao fingerprint da versão atual. Execute o Guardian novamente."
    elif qg["passed"]:
        qstatus, qdetail = "complete", "Quality Gate interno vigente para a versão atual."
    else:
        open_b = ((qg["report"].get("summary") or {}).get("open_blockers", 0)) if qg["report"] else 0
        qstatus, qdetail = "blocked", f"Quality Guardian atual ainda não liberou a obra. Bloqueios abertos: {open_b}."
    stages.append(status_card("quality", "Quality Guardian", qstatus, qdetail, action_page="pages/25_🛡️_Quality_Guardian.py", action_label="Executar Quality Guardian"))

    if not dist["exists"]:
        dstatus, ddetail = "not_started", "Nenhum plano de distribuição vinculado a este título."
    elif not dist["current"]:
        dstatus, ddetail = "blocked", "O plano encontrado pertence a uma versão anterior do Book Master. Recalcule antes de distribuir."
    elif dist["blocked"]:
        dstatus, ddetail = "blocked", f"{dist['ready']} edição(ões) prontas e {dist['blocked']} bloqueada(s) no plano atual."
    elif dist["total"]:
        dstatus, ddetail = "complete", f"{dist['ready']}/{dist['total']} edição(ões) internamente prontas; {dist['live']} marcada(s) como Live por registro humano."
    else:
        dstatus, ddetail = "in_progress", "Plano existe, mas ainda não possui edições configuradas."
    stages.append(status_card("distribution", "Publicação & Distribuição", dstatus, ddetail, action_page="pages/26_🌐_Publishing_Distribution_Center.py", action_label="Abrir Distribution Center"))

    blocking = [s for s in stages if s["status"] == "blocked"]
    pending_core = [s for s in stages if s["id"] in {"authorship", "editorial", "characters", "visual", "quality", "distribution"} and s["status"] in {"attention", "in_progress", "not_started", "blocked"}]
    completed = [s for s in stages if s["status"] == "complete"]

    if blocking:
        next_action = {"title": blocking[0]["title"], "message": blocking[0]["detail"], "page": blocking[0]["action_page"]}
    elif pending_core:
        next_action = {"title": pending_core[0]["title"], "message": pending_core[0]["detail"], "page": pending_core[0]["action_page"]}
    elif dist["live"]:
        next_action = {"title": "Acompanhar lançamento", "message": "Há edição Live registrada. Acompanhe links, status e futuras revisões sem alterar o Master silenciosamente.", "page": "pages/26_🌐_Publishing_Distribution_Center.py"}
    else:
        next_action = {"title": "Revisar estratégia de distribuição", "message": "As etapas centrais registradas estão concluídas; revise os destinos e pacotes finais.", "page": "pages/26_🌐_Publishing_Distribution_Center.py"}

    release_ready = bool(qg["current"] and qg["passed"] and dist["exists"] and dist["current"] and dist["total"] > 0 and dist["blocked"] == 0)
    release_reason = (
        "Quality Gate vigente e todas as edições do plano atual estão internamente prontas para gerar/usar pacotes de canal."
        if release_ready else
        "Ainda existem etapas obrigatórias, Quality Gate pendente/obsoleto ou edições bloqueadas no plano de distribuição."
    )

    return {
        "generated_at": _now(), "title": title, "collection": collection,
        "project_fingerprint": project_fingerprint(state), "stages": stages,
        "counts": {"complete": len(completed), "blocked": len(blocking), "tracked": len(stages)},
        "translations": tr, "activities": act, "audiobooks": aud,
        "quality": {k: v for k, v in qg.items() if k != "report"},
        "distribution": {k: v for k, v in dist.items() if k != "plan"},
        "release": {"ready_for_channel_packages": release_ready, "reason": release_reason},
        "next_action": next_action,
        "policy": {"no_fake_quality_score": True, "no_auto_approval": True, "book_master_preserved": True},
    }


def build_edition_matrix(state: dict, *, translations=None, distribution_plans=None, audiobooks=None) -> list[dict]:
    """Matriz compacta por locale sem confundir tradução com distribuição efetiva."""
    translations = translations or []
    distribution_plans = distribution_plans or []
    audiobooks = audiobooks or []
    locales = {state.get("idioma_original") or "pt-BR"}
    approved = set()
    for p in translations:
        for loc, ed in (p.get("edicoes") or {}).items():
            locales.add(loc)
            if (ed or {}).get("aprovada_id"): approved.add(loc)
    audio_by_locale = {}
    for a in audiobooks:
        loc = a.get("locale") or ""
        if loc:
            audio_by_locale.setdefault(loc, []).append(a)
            locales.add(loc)
    dist_rows = []
    for p in distribution_plans:
        for e in p.get("editions") or []:
            dist_rows.append(e); locales.add(e.get("locale") or state.get("idioma_original") or "pt-BR")
    rows = []
    master_locale = state.get("idioma_original") or "pt-BR"
    for loc in sorted(x for x in locales if x):
        ds = [e for e in dist_rows if e.get("locale") == loc]
        rows.append({
            "locale": loc,
            "text_status": "Master" if loc == master_locale else ("Aprovada" if loc in approved else "Em revisão"),
            "audiobook": "Aprovado" if any(a.get("status") == "approved" for a in audio_by_locale.get(loc, [])) else ("Em produção" if audio_by_locale.get(loc) else "—"),
            "distribution_editions": len(ds),
            "ready": sum(1 for e in ds if e.get("readiness") == "ready"),
            "live": sum(1 for e in ds if (e.get("submission") or {}).get("status") == "live"),
        })
    return rows


def build_project_snapshot(state: dict, overview: dict, edition_matrix: list[dict]) -> str:
    safe = {
        "schema": "faithbloom.project-hub.snapshot.v1",
        "generated_at": _now(),
        "project": {"title": state.get("titulo"), "collection": state.get("colecao"), "language": state.get("idioma_original")},
        "fingerprint": overview.get("project_fingerprint"),
        "overview": overview,
        "edition_matrix": edition_matrix,
    }
    return json.dumps(safe, ensure_ascii=False, indent=2)

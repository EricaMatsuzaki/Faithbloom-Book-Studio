"""Refinamento 17 — contratos leves de integração/UX entre Studios.

Não depende de Streamlit: padroniza contexto de projeto/asset e registra quais
rotas aceitam handoff. A UI apenas coloca o payload em ``st.session_state``.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
import hashlib, json

PROJECT_CONTEXT_KEY = "faithbloom_active_project"
ASSET_CONTEXT_KEY = "faithbloom_selected_asset"
HANDOFF_KEY = "faithbloom_handoff"
WORKSPACE_PROFILE_KEY = "faithbloom_workspace_profile_id"

STUDIOS = {
    "project_hub": {"page":"pages/27_🚀_Project_Hub.py","label":"Project Hub","accepts":["project"]},
    "workspace_profiles": {"page":"pages/34_🏠_Perfis_e_Dashboard.py","label":"Perfis & Dashboard","accepts":["project"]},
    "real_pilot": {"page":"pages/35_🧪_Real_Pilot_Bug_Fix.py","label":"Real Pilot & Bug Fix","accepts":["project"]},
    "authors": {"page":"pages/32_✍️_Autores_e_Colaboradores.py","label":"Autores & Créditos","accepts":["project"]},
    "asset_library": {"page":"pages/31_🖼️_Asset_Library_Media_Manager.py","label":"Asset Library","accepts":["project","asset"]},
    "character_universe": {"page":"pages/14_👥_Character_Universe.py","label":"Character Universe","accepts":["asset"]},
    "emotional": {"page":"pages/17_🎭_Emotional_Color_Director.py","label":"Emotional & Color Director","accepts":["project"]},
    "restoration": {"page":"pages/19_✨_Restoration_Studio.py","label":"Restoration Studio","accepts":["project","asset"]},
    "coloring": {"page":"pages/3_#L01f58d#Ufe0f_Livros_de_Colorir.py","label":"Coloring Studio","accepts":["asset"]},
    "translation": {"page":"pages/21_Translation_Localization_Studio.py","label":"Translation Studio","accepts":["project"]},
    "activity": {"page":"pages/23_🧩_Activity_Book_Studio.py","label":"Activity Book Studio","accepts":["project","asset"]},
    "audiobook": {"page":"pages/24_🎧_Audiobook_Studio.py","label":"Audiobook Studio","accepts":["project"]},
    "quality": {"page":"pages/25_🛡️_Quality_Guardian.py","label":"Quality Guardian","accepts":["project"]},
    "publishing": {"page":"pages/26_🌐_Publishing_Distribution_Center.py","label":"Publishing & Distribution","accepts":["project"]},
}


def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _hash(value):
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()


def make_project_context(card: dict | None, state: dict | None = None) -> dict:
    c=card or {}; s=state or {}
    payload={
        "title": s.get("titulo") or s.get("title") or c.get("titulo") or c.get("title") or "",
        "collection": s.get("colecao") or s.get("collection") or c.get("colecao") or c.get("collection") or "",
        "storage_path": c.get("storage_path") or c.get("arquivo") or "",
        "language": s.get("idioma_original") or s.get("language") or c.get("idioma_original") or c.get("language") or "",
    }
    payload["context_id"]=_hash(payload)[:20]
    payload["selected_at"]=_now()
    return payload


def make_asset_context(asset: dict | None) -> dict:
    a=asset or {}
    payload={"asset_id":a.get("id") or "","name":a.get("nome") or a.get("name") or "","path":a.get("caminho_arquivo") or a.get("storage_uri") or "","media_kind":a.get("media_kind") or a.get("tipo") or ""}
    payload["context_id"]=_hash(payload)[:20]; payload["selected_at"]=_now(); return payload


def make_handoff(source: str, target: str, *, project: dict | None = None, asset: dict | None = None, intent: str = "reuse") -> dict:
    if target not in STUDIOS: raise KeyError(f"Studio desconhecido: {target}")
    accepted=set(STUDIOS[target]["accepts"])
    p=make_project_context(project) if project else {}
    a=make_asset_context(asset) if asset else {}
    warnings=[]
    if p and "project" not in accepted: warnings.append("O destino não declara consumo de contexto de projeto.")
    if a and "asset" not in accepted: warnings.append("O destino não declara consumo de asset.")
    return {"schema":"faithbloom.handoff.v1","source":source,"target":target,"intent":intent,"project":p,"asset":a,"warnings":warnings,"created_at":_now()}


def validate_handoff(payload: dict | None) -> dict:
    h=payload or {}; errors=[]
    target=h.get("target")
    if h.get("schema") != "faithbloom.handoff.v1": errors.append("schema")
    if target not in STUDIOS: errors.append("target")
    if target in STUDIOS:
        accepted=set(STUDIOS[target]["accepts"])
        if h.get("asset") and "asset" not in accepted: errors.append("asset_not_supported")
        if h.get("project") and "project" not in accepted: errors.append("project_not_supported")
    return {"valid":not errors,"errors":errors,"target_page":STUDIOS.get(target,{}).get("page","")}


def studio_registry() -> list[dict]:
    return [{"id":k,**deepcopy(v)} for k,v in STUDIOS.items()]

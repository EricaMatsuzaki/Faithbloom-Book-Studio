"""Ponte Full Editorial Remaster -> Restoration Studio.

Não gera imagens automaticamente. Congela um handoff editorial por cena/página
com texto revisado e direção emocional e injeta esse contexto no plano existente
do Restoration Studio, preservando decisões e versões já registradas.

Antes do handoff, o Autopilot Compliance Core valida estrutura canônica, execução
do Heart Arc, Prompt-Mestre, moral, Bíblia e mapa emocional. Assim uma etapa não
fica "verde" só porque rodou: precisa provar conformidade editorial.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256 as _sha256
import json

from autopilot_compliance_core import assert_autopilot_compliance
from book_doctor import sha256
from restoration_studio import criar_plano_restauracao, carregar_plano_restauracao, salvar_vinculos


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return _sha256(raw).hexdigest()


def preparar_handoff_visual(state: dict, projeto: dict) -> dict:
    """Prepara contexto visual somente quando texto e contratos editoriais passaram."""
    original = state.get("original") or {}
    caminho = str(original.get("arquivo") or "")
    esperado = str(original.get("sha256") or "")
    if not caminho or not esperado or sha256(caminho) != esperado:
        raise ValueError("Original preservado não passou na verificação de integridade.")
    if not state.get("revisao_aprovada"):
        raise ValueError("O Revisor Editorial ainda não aprovou a versão textual.")
    compliance = state.get("prompt_master_compliance_remaster") or {}
    if not compliance.get("ok_para_finalizar"):
        raise ValueError("Prompt-Mestre ainda possui bloqueio para a versão revisada.")
    if not state.get("metadata_emocional_confirmada"):
        raise ValueError("O mapa emocional ainda não foi confirmado cena por cena pela autora.")

    compliance_report = assert_autopilot_compliance(state)

    cenas = [deepcopy(x) for x in (state.get("cenas_texto") or []) if isinstance(x, dict)]
    mapa = [deepcopy(x) for x in (state.get("mapa_emocional") or []) if isinstance(x, dict)]
    if not cenas:
        raise ValueError("Nenhuma cena revisada disponível para o handoff visual.")
    if len(mapa) != len(cenas):
        raise ValueError("Mapa emocional não está alinhado às cenas revisadas.")

    mapa_num = {int(x.get("numero") or i + 1): x for i, x in enumerate(mapa)}
    scene_rows = []
    for i, cena in enumerate(cenas, 1):
        numero = int(cena.get("numero") or i)
        scene_rows.append({
            "numero": numero,
            "numero_origem": cena.get("numero_origem"),
            "pagina_origem": cena.get("pagina_origem"),
            "texto_revisado": cena.get("texto", ""),
            "personagem_principal": cena.get("personagem_principal", ""),
            "figurino": cena.get("figurino", ""),
            "contexto_visual": cena.get("contexto_visual", ""),
            "expressao": cena.get("expressao", ""),
            "emocao": cena.get("emocao", ""),
            "emocao_secundaria": cena.get("emocao_secundaria", ""),
            "intensidade_emocional": cena.get("intensidade_emocional"),
            "transicao_emocional": cena.get("transicao_emocional", ""),
            "direcao_cor": deepcopy(mapa_num.get(numero) or {}),
        })

    snapshot = {
        "schema": "faithbloom.editorial-visual-handoff.v2",
        "remaster_id": state.get("remaster_id", ""),
        "projeto_book_doctor_id": state.get("projeto_book_doctor_id", ""),
        "titulo": state.get("titulo", ""),
        "colecao": state.get("colecao", ""),
        "faixa_etaria": state.get("faixa_etaria", ""),
        "versiculo_referencia": state.get("versiculo_referencia", ""),
        "licao_final": state.get("licao_final", ""),
        "original_sha256": esperado,
        "cenas": scene_rows,
        "autopilot_compliance": deepcopy(compliance_report),
        "heart_arc_scene_map": deepcopy(state.get("heart_arc_scene_map") or {}),
        "criado_em": _now_iso(),
        "policy": {
            "canonical_story_lock": True,
            "heart_arc_execution_gate": True,
            "prompt_master_required": True,
            "use_official_character_masters": True,
            "preserve_original_asset": True,
            "create_derived_versions_only": True,
            "human_approval_each_visual_version": True,
            "emotional_map_human_confirmed": True,
        },
    }
    snapshot["fingerprint"] = _fingerprint(snapshot)

    plan = carregar_plano_restauracao(projeto) or criar_plano_restauracao(
        projeto,
        tipo_projeto=projeto.get("tipo_projeto", "story"),
        status_publicacao=projeto.get("status_publicacao", "em_desenvolvimento"),
        colecao=projeto.get("colecao", ""),
    )
    updated = deepcopy(plan)
    previous = updated.get("editorial_remaster_handoff") or {}
    if previous and previous.get("fingerprint") != snapshot["fingerprint"]:
        updated.setdefault("editorial_remaster_handoff_history", []).append(previous)
    updated["editorial_remaster_handoff"] = snapshot
    updated = salvar_vinculos(projeto, updated)
    return {"handoff": snapshot, "restoration_plan": updated}


def contexto_cena_para_asset(plan: dict, pagina: int | None) -> dict:
    """Retorna o contexto editorial revisado associado à página do asset."""
    handoff = plan.get("editorial_remaster_handoff") or {}
    if pagina is None:
        return {}
    for row in handoff.get("cenas") or []:
        if row.get("pagina_origem") is not None and int(row.get("pagina_origem")) == int(pagina):
            return deepcopy(row)
    return {}

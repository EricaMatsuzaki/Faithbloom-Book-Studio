"""FaithBloom Full Editorial Remaster — mesa de revisão textual controlada.

Reutiliza Editor de História, Revisor, Prompt-Mestre, Emotional & Color Director
sem duplicar suas regras. Toda alteração textual nasce como PROPOSTA e só entra
na versão remasterizada após aprovação humana explícita.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from book_doctor import sha256


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _verify_original(state: dict) -> None:
    original = state.get("original") or {}
    path = Path(str(original.get("arquivo") or ""))
    expected = str(original.get("sha256") or "")
    if not path.exists():
        raise ValueError("Original preservado não encontrado. Revisão bloqueada.")
    if expected and sha256(str(path)) != expected:
        raise ValueError("SHA-256 do original divergiu. Revisão bloqueada.")


def _state_path(state: dict) -> Path:
    raw = str(state.get("arquivo_estado") or "").strip()
    if not raw:
        raise ValueError("Estado do remaster não possui arquivo_estado para persistência segura.")
    return Path(raw)


def salvar_estado_remaster(state: dict) -> dict:
    """Persiste apenas a versão derivada; o PDF original nunca é tocado."""
    _verify_original(state)
    path = _state_path(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(state)
    payload["atualizado_em"] = _now_iso()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def carregar_dossie(state: dict) -> dict:
    path = _state_path(state).parent / "editorial_dossier.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def aprovar_dossie_para_edicao(state: dict, dossie: dict, *, aprovado: bool) -> dict:
    """Libera o Editor somente após decisão humana explícita sobre o diagnóstico."""
    _verify_original(state)
    if not dossie or dossie.get("remaster_id") != state.get("remaster_id"):
        raise ValueError("Dossiê ausente ou não pertence a este remaster.")
    novo = deepcopy(state)
    novo["dossie_editorial_aprovado_para_edicao"] = bool(aprovado)
    novo["dossie_editorial_decidido_em"] = _now_iso()
    novo["status"] = "edicao_textual_liberada" if aprovado else "dossie_rejeitado_ou_pendente"
    return salvar_estado_remaster(novo)


def _scene_index(state: dict, numero_cena: int) -> int:
    for idx, cena in enumerate(state.get("cenas_texto") or []):
        if int(cena.get("numero") or idx + 1) == int(numero_cena):
            return idx
    raise ValueError(f"Cena {numero_cena} não encontrada.")


def gerar_proposta_edicao_cena(
    state: dict,
    numero_cena: int,
    instrucao: str,
    chamar_llm: Callable,
) -> dict:
    """Gera BEFORE/AFTER sem aplicar a mudança ao livro."""
    _verify_original(state)
    if not state.get("dossie_editorial_aprovado_para_edicao"):
        raise ValueError("Aprove o Dossiê Editorial antes de gerar propostas de edição.")
    pedido = str(instrucao or "").strip()
    if not pedido:
        raise ValueError("Informe o que deve ser melhorado nesta cena.")

    idx = _scene_index(state, numero_cena)
    antes = deepcopy((state.get("cenas_texto") or [])[idx])

    from agents.editor_historia import editar_cena

    depois = editar_cena(antes, pedido, deepcopy(state), chamar_llm)
    if not isinstance(depois, dict):
        raise RuntimeError("Editor de História não retornou uma cena estruturada.")
    if int(depois.get("numero") or numero_cena) != int(numero_cena):
        raise RuntimeError("Editor tentou alterar a identidade/numeração da cena. Proposta bloqueada.")

    proposal = {
        "schema": "faithbloom.editorial-remaster-scene-proposal.v1",
        "remaster_id": state.get("remaster_id", ""),
        "numero_cena": int(numero_cena),
        "pagina_origem": antes.get("pagina_origem"),
        "instrucao": pedido,
        "antes": antes,
        "depois": depois,
        "status": "aguardando_aprovacao",
        "gerado_em": _now_iso(),
        "aplicado": False,
    }
    proposals = _state_path(state).parent / "propostas"
    proposals.mkdir(parents=True, exist_ok=True)
    path = proposals / f"cena_{int(numero_cena):03d}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    proposal["arquivo_proposta"] = str(path)
    return proposal


def aplicar_proposta_edicao(state: dict, proposta: dict, *, aprovado: bool) -> dict:
    """Aplica somente proposta aprovada; rejeição não altera cenas."""
    _verify_original(state)
    if not proposta or proposta.get("remaster_id") != state.get("remaster_id"):
        raise ValueError("Proposta ausente ou pertence a outro remaster.")
    novo = deepcopy(state)
    historico = list(novo.get("historico_revisao_textual") or [])
    registro = {
        "numero_cena": int(proposta.get("numero_cena") or 0),
        "decidido_em": _now_iso(),
        "aprovado": bool(aprovado),
        "antes": deepcopy(proposta.get("antes") or {}),
        "depois": deepcopy(proposta.get("depois") or {}),
        "instrucao": proposta.get("instrucao", ""),
    }
    if aprovado:
        idx = _scene_index(novo, registro["numero_cena"])
        atual = deepcopy((novo.get("cenas_texto") or [])[idx])
        esperado = proposta.get("antes") or {}
        if atual != esperado:
            raise ValueError("A cena mudou desde que a proposta foi gerada. Gere uma nova proposta antes de aplicar.")
        nova_cena = deepcopy(proposta.get("depois") or {})
        nova_cena["numero"] = atual.get("numero", registro["numero_cena"])
        nova_cena["pagina_origem"] = atual.get("pagina_origem")
        nova_cena["origem"] = "editorial_remaster_aprovado"
        novo["cenas_texto"][idx] = nova_cena
        novo["revisao_aprovada"] = False
        novo["status"] = "texto_em_revisao"
    historico.append(registro)
    novo["historico_revisao_textual"] = historico
    return salvar_estado_remaster(novo)


def rodar_revisao_final_textual(state: dict, chamar_llm: Callable) -> dict:
    """Revisor + especialista emocional + Psicologia das Cores, em fluxo automático.

    Se o Revisor já devolveu metadados emocionais válidos, eles são reutilizados
    diretamente. Só quando faltam emoção/intensidade o especialista emocional é
    chamado. Em ambos os casos, as cores vêm do motor canônico determinístico.
    """
    _verify_original(state)
    if not state.get("dossie_editorial_aprovado_para_edicao"):
        raise ValueError("Dossiê Editorial ainda não foi aprovado para edição.")

    from agents.revisor import revisor_node
    from editorial_remaster_emotional import analisar_emocoes_automaticamente, metadata_emocional_completa
    from emotional_color_director import construir_mapa_emocional
    from prompt_master_compliance import avaliar_prompt_mestre
    from biblical_reference_validator import reference_gate

    work = deepcopy(state)
    revisado = revisor_node(work, chamar_llm)
    aprovado = bool(revisado.get("revisao_aprovada"))

    if aprovado:
        emocional = metadata_emocional_completa(revisado)
        if emocional.get("ok"):
            revisado = deepcopy(revisado)
            revisado["mapa_emocional"] = construir_mapa_emocional(revisado.get("cenas_texto") or [])
            revisado["metadata_emocional_confirmada"] = True
            revisado.setdefault("metadata_emocional_modo", "reutilizado_do_revisor")
        else:
            revisado = analisar_emocoes_automaticamente(revisado, chamar_llm)
    mapa = deepcopy(revisado.get("mapa_emocional") or []) if aprovado else []

    compliance = avaliar_prompt_mestre(dict(revisado))
    bible = reference_gate(dict(revisado))

    novo = deepcopy(state)
    novo["revisao_aprovada"] = aprovado
    novo["notas_revisor"] = deepcopy(revisado.get("notas_revisor") or [])
    if aprovado:
        novo["cenas_texto"] = deepcopy(revisado.get("cenas_texto") or [])
        novo["mapa_emocional"] = mapa
        novo["metadata_emocional_confirmada"] = True
        novo["metadata_emocional_modo"] = revisado.get("metadata_emocional_modo", "automatico_com_override_humano")
        novo["analise_emocional_automatica"] = deepcopy(revisado.get("analise_emocional_automatica") or {})
    novo["prompt_master_compliance_remaster"] = compliance
    novo["bible_reference_gate_remaster"] = bible
    novo["necessita_intervencao_estrutural_roteirista"] = not aprovado
    novo["status"] = "texto_aprovado_pronto_para_visual" if aprovado and compliance.get("ok_para_finalizar") else "texto_ainda_em_revisao"
    novo = salvar_estado_remaster(novo)

    return {
        "aprovado": aprovado,
        "notas": deepcopy(novo.get("notas_revisor") or []),
        "mapa_emocional": deepcopy(novo.get("mapa_emocional") or []),
        "analise_emocional_automatica": deepcopy(novo.get("analise_emocional_automatica") or {}),
        "prompt_mestre": compliance,
        "bible_reference": bible,
        "necessita_roteirista": not aprovado,
        "pronto_para_visual": bool(aprovado and compliance.get("ok_para_finalizar")),
        "estado": novo,
    }

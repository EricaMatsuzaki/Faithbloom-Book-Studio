"""Agente de Capa - FaithBloom 2.0 Fase 7.

Mudança principal: a IA NÃO gera mais o wraparound inteiro.
Ela gera duas artes sem texto (frente e contracapa) e o FaithBloom monta
matematicamente contracapa + lombada + capa frontal em capa_profissional.py.
"""
from __future__ import annotations

from author_profiles import cover_credit_from_state
from agent_skills import skill_contract

from state import LivroState
from agents.ilustrador import ESTILO_VISUAL_FIXO
from kdp_rules import dimensoes_capa_ebook_px
from marca import aplicar_faixa_colecao
from armazenamento import carregar_asset_marca
from capa_profissional import gerar_capa_print_ready

TRIM_LARGURA_IN_PADRAO=8.5
TRIM_ALTURA_IN_PADRAO=8.5


def _trim(state: LivroState):
    return (float(state.get("trim_largura_in") or TRIM_LARGURA_IN_PADRAO),float(state.get("trim_altura_in") or TRIM_ALTURA_IN_PADRAO))


def _personagens_str(personagens: dict) -> str:
    return ", ".join(f"{p.get('nome','')} ({p.get('descricao_fixa','')})" for p in personagens.values())


def prompt_arte_capa_frontal(state: LivroState) -> str:
    return (
        f"{ESTILO_VISUAL_FIXO}\n"
        "ARTE FRONTAL de capa de livro infantil. Gere SOMENTE ilustração, sem letras, sem título, sem logo, sem moldura tipográfica. "
        "Composição editorial premium, foco claro nos protagonistas e espaço visual respirável no terço superior e inferior para tipografia posterior. "
        f"Personagens: {_personagens_str(state.get('personagens',{}))}. Tema do livro: {state.get('titulo','')}."
    ) + skill_contract("cover_specialist", compact=True)


def prompt_arte_contracapa(state: LivroState) -> str:
    return (
        f"{ESTILO_VISUAL_FIXO}\n"
        "ARTE DE CONTRACAPA combinando perfeitamente com a capa frontal: mesma paleta, luz, época, cenário e acabamento. "
        "Sem texto, sem letras, sem logotipo, sem código de barras. Fundo mais calmo e menos carregado que a capa. "
        "Deixar áreas visuais tranquilas para sinopse e para barcode no canto inferior direito da contracapa."
    ) + skill_contract("cover_specialist", compact=True)


def gerar_artes_capa(state: LivroState, gerar_imagem) -> LivroState:
    protagonista=next((p for p in state.get("personagens",{}).values() if p.get("papel")=="protagonista"),None)
    ref=protagonista.get("imagem_referencia") if protagonista else None
    if not state.get("arte_capa_frontal"):
        state["arte_capa_frontal"]=gerar_imagem(prompt_arte_capa_frontal(state),imagem_base=ref)
    if not state.get("arte_contracapa"):
        state["arte_contracapa"]=gerar_imagem(prompt_arte_contracapa(state),imagem_base=ref)
    return state


def gerar_capa_ebook(state: LivroState, gerar_imagem) -> str:
    if not state.get("arte_capa_frontal"):
        gerar_artes_capa(state,gerar_imagem)
    faixa=carregar_asset_marca(state.get("colecao",""),"faixa")
    return aplicar_faixa_colecao(state["arte_capa_frontal"],state.get("colecao",""),faixa)


def montar_capa_fisica(state: LivroState, paginas_fisicas: int, papel: str="cor_premium", pasta_saida: str="saida_capas") -> dict:
    if not state.get("arte_capa_frontal") or not state.get("arte_contracapa"):
        raise RuntimeError("Gere ou envie primeiro as artes de capa frontal e contracapa.")
    trim_w,trim_h=_trim(state)
    spine_text=state.get("titulo","")
    result=gerar_capa_print_ready(
        state["arte_capa_frontal"],state["arte_contracapa"],pasta_saida,
        trim_w=trim_w,trim_h=trim_h,paginas=int(paginas_fisicas),papel=papel,
        titulo=state.get("titulo",""),subtitulo=state.get("subtitulo",""),autora=cover_credit_from_state(state),
        colecao=state.get("colecao",""),sinopse=state.get("sinopse_contracapa","") or state.get("sinopse_vendas_curta",""),
        spine_text=spine_text,reservar_barcode=True,
    )
    state["capa_fisica_wrap"]=result["caminho_png"]
    state["capa_fisica_pdf"]=result["caminho_pdf"]
    state["capa_fisica_preview"]=result["caminho_preview"]
    state["capa_fisica_dimensoes"]=result
    state["capa_fisica_preflight"]=result["pdf_preflight"]
    return result


def capa_node(state: LivroState, gerar_imagem) -> LivroState:
    paginas=int(state.get("pdf_miolo_config",{}).get("paginas") or (state.get("layout_paginas") or [{"pagina":24}])[-1].get("pagina",24))
    gerar_artes_capa(state,gerar_imagem)
    state["capa_ebook"]=gerar_capa_ebook(state,gerar_imagem)
    montar_capa_fisica(state,paginas,papel=state.get("tipo_papel_capa","cor_premium"))
    if "checklist_kdp" in state:
        state["checklist_kdp"]["capa_ebook_gerada"]=bool(state.get("capa_ebook"))
        state["checklist_kdp"]["capa_fisica_wrap_gerada"]=bool(state.get("capa_fisica_pdf"))
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('cover_specialist',)

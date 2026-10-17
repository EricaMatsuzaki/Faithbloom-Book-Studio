"""Agente de Capa - FaithBloom 2.0 Fase 7.

Mudança principal: a IA NÃO gera mais o wraparound inteiro.
Ela gera duas artes sem texto (frente e contracapa) e o FaithBloom monta
matematicamente contracapa + lombada + capa frontal em capa_profissional.py.
"""
from __future__ import annotations

import inspect
import json

from author_profiles import cover_credit_from_state
from agent_skills import skill_contract

from state import LivroState
from agents.ilustrador import ESTILO_VISUAL_FIXO
from emotional_visual_binding import book_visual_style
from kdp_rules import dimensoes_capa_ebook_px
from marca import aplicar_faixa_colecao
from armazenamento import carregar_asset_marca
from capa_profissional import gerar_capa_print_ready

TRIM_LARGURA_IN_PADRAO=8.5
TRIM_ALTURA_IN_PADRAO=8.5


def _trim(state: LivroState):
    return (float(state.get("trim_largura_in") or TRIM_LARGURA_IN_PADRAO),float(state.get("trim_altura_in") or TRIM_ALTURA_IN_PADRAO))


def _personagens_str(personagens: dict) -> str:
    descricoes = []
    for chave, personagem in personagens.items():
        identidade = str(personagem.get("descricao_fixa") or "").strip()
        if personagem.get("dna"):
            identidade += "\nCHARACTER DNA CANÔNICO: " + json.dumps(personagem["dna"], ensure_ascii=False, sort_keys=True)
        if personagem.get("character_dna_prompt"):
            identidade += "\n" + str(personagem["character_dna_prompt"])
        descricoes.append(f"{personagem.get('nome') or chave} ({identidade})")
    return "\n".join(descricoes)


def _style_prompt(state: LivroState) -> str:
    style = book_visual_style(state)
    if not style:
        return ESTILO_VISUAL_FIXO
    return (
        "STYLE DNA APROVADO DESTA OBRA: " + json.dumps(style, ensure_ascii=False, sort_keys=True)
        + ". Aplicar estas regras de renderização na capa e contracapa sem alterar a identidade do Character Master. "
        "Luz e temperatura seguem a direção emocional aprovada; personagens e cenários originais, sem copiar estúdios."
    )


def _contrato_identidade(state: LivroState) -> str:
    return (
        "DIREÇÃO DE IDENTIDADE CANÔNICA — prevalece sobre proporções e estilo genéricos: "
        "o DNA e os Masters originais definem a identidade dos personagens. Preserve rigorosamente rosto, "
        "espécie, proporções fundamentais, cores canônicas dos olhos, cabelo, pele, pelagem e marcas; "
        "preserve formato dos olhos, cílios, posição, número e formato dos brilhos/reflexos, incluindo "
        "estrelas e corações quando presentes. Não substitua esses detalhes por pontos genéricos. "
        "A emoção e a paleta do ambiente podem mudar luz, atmosfera, pose e expressão, sem recolorir "
        "a identidade dos personagens. Se houver personagens na arte, siga estas identidades:\n"
        + _personagens_str(state.get("personagens", {}))
    )


def _referencias_originais(state: LivroState, gerar_imagem) -> dict:
    personagens = list(state.get("personagens", {}).values())
    personagens.sort(key=lambda personagem: personagem.get("papel") != "protagonista")
    refs = list(dict.fromkeys(personagem["imagem_referencia"] for personagem in personagens
                             if personagem.get("imagem_referencia")))
    kwargs = {"imagem_base": refs[0] if refs else None}
    if len(refs) > 1:
        # Inspect before invoking: retrying on TypeError could duplicate a paid
        # request if the provider itself raised it after submitting the image.
        try:
            parametros = inspect.signature(gerar_imagem).parameters
        except (TypeError, ValueError):
            parametros = {}
        suporte_multiplo = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parametros.values())
        suporte_multiplo = suporte_multiplo or ("imagens_referencia" in parametros
            and parametros["imagens_referencia"].kind in {
                inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY})
        if suporte_multiplo:
            kwargs["imagens_referencia"] = refs[1:]
    return kwargs


def prompt_arte_capa_frontal(state: LivroState) -> str:
    return (
        f"{_style_prompt(state)}\n"
        "ARTE FRONTAL de capa de livro infantil. Gere SOMENTE ilustração, sem letras, sem título, sem logo, sem moldura tipográfica. "
        "Composição editorial premium, foco claro nos protagonistas e espaço visual respirável no terço superior e inferior para tipografia posterior. "
        f"Tema do livro: {state.get('titulo','')}.\n"
        + _contrato_identidade(state)
    ) + skill_contract("cover_specialist", compact=True)


def prompt_arte_contracapa(state: LivroState) -> str:
    return (
        f"{_style_prompt(state)}\n"
        "ARTE DE CONTRACAPA combinando perfeitamente com a capa frontal: mesma paleta, luz, época, cenário e acabamento. "
        "Sem texto, sem letras, sem logotipo, sem código de barras. Fundo mais calmo e menos carregado que a capa. "
        "Deixar áreas visuais tranquilas para sinopse e para barcode no canto inferior direito da contracapa.\n"
        + _contrato_identidade(state)
    ) + skill_contract("cover_specialist", compact=True)


def gerar_artes_capa(state: LivroState, gerar_imagem) -> LivroState:
    referencias = _referencias_originais(state, gerar_imagem)
    if not state.get("arte_capa_frontal"):
        caminho=gerar_imagem(prompt_arte_capa_frontal(state), **referencias)
        if not isinstance(caminho,str) or not caminho.strip():
            raise ValueError("O gerador não retornou arte frontal utilizável; nenhuma capa foi substituída.")
        state["arte_capa_frontal"]=caminho
    if not state.get("arte_contracapa"):
        caminho=gerar_imagem(prompt_arte_contracapa(state), **referencias)
        if not isinstance(caminho,str) or not caminho.strip():
            raise ValueError("O gerador não retornou contracapa utilizável; a arte frontal foi preservada.")
        state["arte_contracapa"]=caminho
    return state


def gerar_capa_ebook(state: LivroState, gerar_imagem) -> str:
    if not state.get("arte_capa_frontal"):
        gerar_artes_capa(state,gerar_imagem)
    faixa=carregar_asset_marca(state.get("colecao",""),"faixa")
    return aplicar_faixa_colecao(state["arte_capa_frontal"],state.get("colecao",""),faixa)


def montar_capa_fisica(state: LivroState, paginas_fisicas: int, papel: str="cor_premium", pasta_saida: str="saida_capas") -> dict:
    from agent_skills import require_role_ready
    require_role_ready("cover_specialist")
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

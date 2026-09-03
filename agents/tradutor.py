"""Agente Tradutor/Localizador — Refinamento 06.

Compatível com o pipeline legado, mas agora delega ao Translation & Localization
Studio. A Bíblia é protegida: o LLM nunca recebe instrução para traduzir o texto
do versículo por conta própria.
"""
from __future__ import annotations

from state import LivroState
from agent_skills import skill_contract
from kdp_rules import idioma_elegivel_paperback
from translation_localization import (
    normalize_locale,
    localizar_livro,
    criar_registro_biblico,
    revisar_localizacao_estrutural,
)


def _perfil_para_locale(state: dict, locale: str) -> dict:
    perfis=state.get("translation_profiles",{}) or {}
    p=dict(perfis.get(locale,{}) or {})
    p.setdefault("modo",state.get("translation_mode","natural_infantil"))
    p.setdefault("faixa_etaria",state.get("faixa_etaria","3–8"))
    p.setdefault("intensidade_sons",state.get("onomatopoeia_intensity","equilibrada"))
    return p


def _bible_record(state: dict, locale: str) -> dict:
    registros=state.get("bible_records",{}) or {}
    if locale in registros:
        return registros[locale]
    # Sem texto aprovado: somente referência. Nunca inventar tradução bíblica.
    return criar_registro_biblico(state.get("versiculo_referencia",""),locale)


def tradutor_node(state: LivroState, chamar_llm) -> LivroState:
    traducoes=dict(state.get("traducoes",{}) or {})
    reviews=dict(state.get("linguistic_reviews",{}) or {})
    glossario=state.get("glossario_colecao",{}) or {}

    for idioma in state.get("idiomas_alvo",[]) or []:
        locale=normalize_locale(idioma)
        lang_code=locale.split("-")[0]
        if not idioma_elegivel_paperback(lang_code):
            traducoes[locale]={"status":"eBook apenas - paperback não suportado pela KDP para este idioma no momento","locale":locale,"bible_ai_translation_allowed":False}
            continue
        perfil=_perfil_para_locale(state,locale)
        bible=_bible_record(state,locale)
        resultado=localizar_livro(
            dict(state),chamar_llm,locale,
            modo=perfil["modo"],faixa_etaria=perfil["faixa_etaria"],
            intensidade_sons=perfil["intensidade_sons"],
            glossario=glossario,bible_record=bible,
            instrucoes=(perfil.get("instrucoes","") + skill_contract("translator_localizer"))
        )
        traducoes[locale]=resultado
        reviews[locale]=revisar_localizacao_estrutural(dict(state),resultado,bible_record=bible,glossario=glossario)

    state["traducoes"]=traducoes
    state["linguistic_reviews"]=reviews
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('translator_localizer',)

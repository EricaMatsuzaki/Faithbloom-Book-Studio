"""Agente Tradutor/Localizador — Refinamento 06 + Localization Excellence.

Compatível com o pipeline legado, mas agora delega ao Translation & Localization
Studio e recebe uma camada de excelência por locale. A Bíblia é protegida: o
LLM nunca recebe instrução para traduzir o texto do versículo por conta própria.
A faixa etária oficial, o FaithBloom Heart Arc™, humor, musicalidade e
naturalidade infantil do mercado-alvo também devem ser preservados.
"""
from __future__ import annotations

from state import LivroState
from agent_skills import skill_contract
from kdp_rules import idioma_elegivel_paperback
from age_profiles import normalizar_faixa_etaria, perfil_etario, instrucao_faixa_etaria
from localization_excellence import (
    localization_excellence_contract,
    locale_specialist_profile,
)
from translation_localization import (
    normalize_locale,
    localizar_livro,
    criar_registro_biblico,
    revisar_localizacao_estrutural,
)


def _perfil_para_locale(state: dict, locale: str) -> dict:
    perfis = state.get("translation_profiles", {}) or {}
    p = dict(perfis.get(locale, {}) or {})
    p.setdefault("modo", state.get("translation_mode", "natural_infantil"))
    faixa = normalizar_faixa_etaria(p.get("faixa_etaria") or state.get("faixa_etaria"))
    p["faixa_etaria"] = faixa
    p["faixa_etaria_label"] = perfil_etario(faixa)["short_label"]
    p.setdefault("intensidade_sons", state.get("onomatopoeia_intensity", "equilibrada"))
    p["localization_excellence"] = locale_specialist_profile(locale, p["faixa_etaria_label"])
    return p


def _bible_record(state: dict, locale: str) -> dict:
    registros = state.get("bible_records", {}) or {}
    if locale in registros:
        return registros[locale]
    # Sem texto aprovado: somente referência. Nunca inventar tradução bíblica.
    return criar_registro_biblico(state.get("versiculo_referencia", ""), locale)


def tradutor_node(state: LivroState, chamar_llm) -> LivroState:
    faixa_master = normalizar_faixa_etaria(state.get("faixa_etaria"))
    state["faixa_etaria"] = faixa_master
    state["age_profile_id"] = faixa_master

    traducoes = dict(state.get("traducoes", {}) or {})
    reviews = dict(state.get("linguistic_reviews", {}) or {})
    glossario = state.get("glossario_colecao", {}) or {}
    quality_profiles = dict(state.get("localization_quality_profiles", {}) or {})

    for idioma in state.get("idiomas_alvo", []) or []:
        locale = normalize_locale(idioma)
        lang_code = locale.split("-")[0]
        if not idioma_elegivel_paperback(lang_code):
            traducoes[locale] = {
                "status": "eBook apenas - paperback não suportado pela KDP para este idioma no momento",
                "locale": locale,
                "bible_ai_translation_allowed": False,
            }
            continue

        perfil = _perfil_para_locale(state, locale)
        bible = _bible_record(state, locale)
        instrucoes_perfil = (
            instrucao_faixa_etaria(perfil["faixa_etaria"])
            + "\nPreserve na localização o mesmo nível de maturidade, densidade, humor, tensão, musicalidade e uso de onomatopeias do perfil etário do Master."
            + "\nPreserve o FaithBloom Heart Arc™: encantamento → emoção → experiência → descoberta → transformação → fé."
            + "\nA tradução deve reproduzir o efeito infantil da obra — humor, ternura, curiosidade, refrões, ritmo e recompensa emocional — e não apenas equivalência lexical."
        )
        instrucoes_livres = str(perfil.get("instrucoes", "") or "").strip()
        instrucoes = instrucoes_perfil + ("\n" + instrucoes_livres if instrucoes_livres else "")
        instrucoes += localization_excellence_contract(locale, perfil["faixa_etaria_label"])
        instrucoes += skill_contract("translator_localizer")

        resultado = localizar_livro(
            dict(state),
            chamar_llm,
            locale,
            modo=perfil["modo"],
            faixa_etaria=perfil["faixa_etaria_label"],
            intensidade_sons=perfil["intensidade_sons"],
            glossario=glossario,
            bible_record=bible,
            instrucoes=instrucoes,
        )
        resultado["faixa_etaria"] = perfil["faixa_etaria"]
        resultado["faixa_etaria_label"] = perfil["faixa_etaria_label"]
        resultado["localization_excellence_profile"] = perfil["localization_excellence"]
        traducoes[locale] = resultado
        quality_profiles[locale] = perfil["localization_excellence"]
        reviews[locale] = revisar_localizacao_estrutural(
            dict(state), resultado, bible_record=bible, glossario=glossario
        )

    state["traducoes"] = traducoes
    state["linguistic_reviews"] = reviews
    state["localization_quality_profiles"] = quality_profiles
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('translator_localizer',)

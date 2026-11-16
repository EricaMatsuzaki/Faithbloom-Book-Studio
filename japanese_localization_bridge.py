"""Thin bridge for MEXT-aware Japanese child localization.

Reuses the existing Translation & Localization Studio and only adds Japanese
reading-level guidance plus furigana metadata. It never replaces the Master and
never translates Bible text.
"""
from __future__ import annotations

from copy import deepcopy

from japanese_reading_level import japanese_reading_contract, japanese_reading_profile
from translation_localization import (
    normalize_locale,
    localizar_livro,
    revisar_localizacao_com_llm,
)


def localizar_livro_com_reading_guard(
    state: dict,
    chamar_llm,
    locale: str,
    *,
    modo: str = "natural_infantil",
    faixa_etaria: str = "3–8",
    intensidade_sons: str = "equilibrada",
    glossario: dict | None = None,
    bible_record: dict | None = None,
    instrucoes: str = "",
) -> dict:
    loc = normalize_locale(locale)
    extras = str(instrucoes or "").strip()
    if loc == "ja-JP":
        extras = (extras + "\n" + japanese_reading_contract(faixa_etaria)).strip()

    resultado = localizar_livro(
        state,
        chamar_llm,
        loc,
        modo=modo,
        faixa_etaria=faixa_etaria,
        intensidade_sons=intensidade_sons,
        glossario=glossario,
        bible_record=bible_record,
        instrucoes=extras,
    )
    if loc == "ja-JP":
        resultado = deepcopy(resultado)
        resultado["japanese_reading_profile"] = japanese_reading_profile(faixa_etaria)
        resultado["furigana_metadata_supported"] = True
        resultado["furigana_rendering_note"] = (
            "furigana_annotations devem ser renderizadas como ruby/furigana pela camada de diagramação; "
            "não inserir leituras repetidas como prosa entre parênteses no texto final."
        )
    return resultado


def revisar_localizacao_com_reading_guard(
    master: dict,
    traducao: dict,
    chamar_llm,
    locale: str,
    faixa_etaria: str = "3–8",
) -> dict:
    """Runs the existing independent review and, for ja-JP, a focused reading audit."""
    loc = normalize_locale(locale)
    base = revisar_localizacao_com_llm(master, traducao, chamar_llm, loc, faixa_etaria)
    if loc != "ja-JP":
        return base

    reading_prompt = japanese_reading_contract(faixa_etaria) + """
Você é também um revisor de legibilidade infantil japonesa.
Audite a LOCALIZAÇÃO japonesa cena por cena. Não reescreva o livro inteiro.
Verifique:
- carga de kanji apropriada à faixa;
- palavras naturais que devem ser preservadas mesmo contendo kanji mais avançado;
- necessidade de furigana/ruby para reduzir a carga de leitura;
- furigana excessivo ou desnecessário;
- leitura em voz alta, ritmo e naturalidade de 絵本;
- se `furigana_annotations` possui surface + reading em hiragana + reason quando necessário.
Não altere nomes protegidos, moral, Character DNA ou referência bíblica.
Retorne JSON com: veredito, alertas, furigana_sugerido_por_cena.
"""
    audit = chamar_llm(
        sistema=reading_prompt,
        instrucao="Audite esta localização japonesa sem traduzir nem completar texto bíblico. LOCALIZACAO=" + repr(traducao),
    )
    return {
        "veredito": base.get("veredito", "revisar") if isinstance(base, dict) else "revisar",
        "revisao_linguistica": base,
        "japanese_reading_review": audit,
        "japanese_reading_profile": japanese_reading_profile(faixa_etaria),
    }

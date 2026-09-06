"""Versão autoral do Roteirista para comparação editorial.

Diferente do Comparative Story Director, este módulo usa a skill formal
`storyteller` e permite ao Roteirista escolher a melhor estratégia narrativa
para a premissa, sem ficar preso a um dos quatro estilos formais.
"""
from __future__ import annotations

from typing import Any

from agent_skills import skill_contract
from age_profiles import normalizar_faixa_etaria, perfil_etario, instrucao_faixa_etaria
from emotion_colors import EMOCOES, EMOCOES_COMPLEMENTARES
from agents.estilos_narrativos import ESTILOS_NARRATIVOS, normalizar_licao_final

LABEL_ROTEIRISTA = "⭐ Versão do Roteirista"


def _personagens_resumo(state: dict) -> str:
    partes: list[str] = []
    for nome, dados in (state.get("personagens") or {}).items():
        if isinstance(dados, dict):
            papel = str(dados.get("papel") or "").strip()
            descricao = str(dados.get("descricao_fixa") or "").strip()
            rotulo = f"{nome} ({papel})" if papel else str(nome)
            partes.append(f"{rotulo}: {descricao}".strip())
        else:
            partes.append(str(nome))
    brief = str(state.get("personagens_historia_brief") or "").strip()
    if brief:
        partes.append("Briefing narrativo da autora:\n" + brief)
    return "\n".join(partes) or "Preserve os personagens já descritos na premissa."


def _base_sistema(state: dict) -> str:
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    perfil = perfil_etario(faixa)
    min_cenas = max(12, int(state.get("paginas_minimas") or 24) // 2)
    return f"""
Você é o ROTEIRISTA PRINCIPAL do FaithBloom Book Studio.
Esta é uma proposta AUTORAL sua, usando sua skill formal de storyteller.

Você NÃO está obrigado a imitar isoladamente Estilo 1, 2, 3 ou Misto.
Use seu melhor julgamento narrativo para tornar esta premissa memorável,
visual, agradável em voz alta e emocionalmente satisfatória. Você pode combinar
recursos dos quatro estilos quando isso melhorar a história, mas preserve a
unidade de voz.

NÃO mude os elementos editoriais já decididos pela autora:
- premissa/fatos centrais;
- personagens, nomes, relações e papéis;
- faixa etária;
- lição cristã;
- referência bíblica.

FAIXA ETÁRIA OBRIGATÓRIA:
{instrucao_faixa_etaria(faixa)}

DADOS DO PROJETO:
Título atual: {state.get('titulo', '')}
Premissa: {state.get('_entrada_tema_livre') or state.get('titulo') or ''}
Emoção central: {state.get('emocao_central', '')}
Lição cristã: {state.get('aprendizado_cristao') or state.get('licao_final') or ''}
Referência bíblica: {state.get('versiculo_referencia', '')}
Faixa: {perfil['short_label']}
Personagens:
{_personagens_resumo(state)}

DNA NARRATIVO FAITHBLOOM:
- gancho claro nas cenas iniciais;
- progressão que faça a criança querer virar a página;
- ação visual em cada cena;
- musicalidade natural e repetição suave;
- onomatopeias somente quando ajudam ação, humor ou surpresa;
- humor adequado à idade, sem forçar comédia;
- tensão segura, nunca medo excessivo ou culpa religiosa;
- emoções concretas/coerentes com a idade;
- descoberta, transformação emocional, fé e recompensa/celebração;
- mensagem cristã amorosa, integrada à ação e não como sermão;
- fechamento memorável;
- não invente texto bíblico completo: preserve apenas a referência fornecida.

Para história completa, gere no mínimo {min_cenas} cenas e use como tetos
heurísticos aproximadamente {perfil['max_words_sentence']} palavras por frase e
{perfil['max_words_scene']} por cena, sem usar os tetos como meta.

Mapa emocional por cena: emoção principal entre {', '.join(EMOCOES.keys())};
subemoção opcional entre {', '.join(EMOCOES_COMPLEMENTARES.keys())}; intensidade
1–5 e transição emocional coerente. Não escolha cores: o Emotional & Color
Director fará isso depois.
""".strip() + "\n\n" + skill_contract("storyteller")


def _normalizar_estilo_recomendado(valor: Any) -> str:
    if valor in ESTILOS_NARRATIVOS:
        return str(valor)
    texto = str(valor or "").lower()
    if "poét" in texto or "poet" in texto or "rim" in texto:
        return "estilo_2"
    if "fáb" in texto or "fab" in texto:
        return "estilo_3"
    if "mist" in texto or "híbrid" in texto or "hibrid" in texto:
        return "misto"
    return "estilo_1"


def gerar_proposta_roteirista(state: dict, chamar_llm) -> dict:
    """Retorna a visão criativa do Roteirista sem escrever o livro inteiro."""
    resposta = chamar_llm(
        sistema=_base_sistema(state),
        instrucao=(
            "Antes de escrever a história, apresente sua VISÃO DE ROTEIRISTA para esta premissa. "
            "Não reescreva o briefing e não gere cenas completas. Retorne JSON com: "
            "titulo_alternativo, gancho, direcao_narrativa, arco_emocional, momento_de_virada, "
            "final_sugerido, estilo_recomendado (estilo_1|estilo_2|estilo_3|misto) e justificativa_criativa."
        ),
    )
    if not isinstance(resposta, dict):
        resposta = {"direcao_narrativa": str(resposta or "")}
    resposta = dict(resposta)
    resposta["estilo_recomendado"] = _normalizar_estilo_recomendado(resposta.get("estilo_recomendado"))
    resposta["label"] = "✍️ Proposta do Roteirista"
    resposta["origem"] = "storyteller_skill"
    return resposta


def gerar_versao_autoral_roteirista(state: dict, chamar_llm) -> dict:
    """Gera uma quinta versão completa usando a skill real do Roteirista."""
    resposta = chamar_llm(
        sistema=_base_sistema(state),
        instrucao=(
            "Escreva sua MELHOR VERSÃO AUTORAL COMPLETA desta história. Não fique preso a um estilo formal: "
            "use a estratégia narrativa que julgar mais forte para este livro, sempre respeitando a faixa e o Prompt-Mestre. "
            "Retorne JSON com titulo, sinopse_poetica, cenas_texto, licao_final, "
            "estilo_recomendado (estilo_1|estilo_2|estilo_3|misto) e justificativa_criativa. "
            "Cada cena deve conter numero, texto, emocao, emocao_secundaria, intensidade_emocional (1-5), "
            "transicao_emocional, figurino, contexto_visual, personagem_principal e expressao."
        ),
    )
    if not isinstance(resposta, dict):
        resposta = {"sinopse_poetica": str(resposta or "")}
    cenas = resposta.get("cenas_texto") or resposta.get("cenas") or []
    if not isinstance(cenas, list):
        cenas = []
    return {
        "estilo": "roteirista_autoral",
        "label": LABEL_ROTEIRISTA,
        "modo": "completa",
        "origem": "storyteller_skill",
        "titulo": resposta.get("titulo") or state.get("titulo") or "",
        "sinopse_poetica": resposta.get("sinopse_poetica") or resposta.get("sinopse") or "",
        "cenas_texto": cenas,
        "licao_final": normalizar_licao_final(resposta.get("licao_final")),
        "estilo_recomendado": _normalizar_estilo_recomendado(resposta.get("estilo_recomendado")),
        "justificativa_criativa": str(resposta.get("justificativa_criativa") or "").strip(),
    }


SKILL_PROFILE_IDS = ("storyteller",)

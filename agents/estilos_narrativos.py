"""Refinamento 24 — estilos narrativos formais do Prompt-Mestre FaithBloom.

Mantém a mesma premissa, personagens, lição cristã e referência bíblica,
variando somente a forma narrativa. A autora pode comparar os quatro estilos
antes de escolher qual seguirá para o livro final.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from emotion_colors import EMOCOES, EMOCOES_COMPLEMENTARES
from age_profiles import normalizar_faixa_etaria, perfil_etario, instrucao_faixa_etaria

ESTILOS_NARRATIVOS = {
    "estilo_1": {
        "label": "Estilo 1 — Aventura",
        "descricao": "Aventura + emoção + superação, com ação visual, humor leve e transformação clara.",
        "instrucao": (
            "Use aventura, emoção e superação. Estruture problema -> tentativas -> "
            "descoberta -> ação -> transformação -> vitória espiritual. Priorize ação "
            "visual, diálogos naturais, pequenas surpresas e humor leve quando couber."
        ),
    },
    "estilo_2": {
        "label": "Estilo 2 — Poético/Rimado",
        "descricao": "Musicalidade, repetição e rimas naturais sem perder clareza para a faixa escolhida.",
        "instrucao": (
            "Use linguagem poética adequada à idade, musicalidade, repetição suave e rimas naturais. "
            "Nunca force rimas nem sacrifique clareza; ajuste a intensidade da repetição à faixa etária."
        ),
    },
    "estilo_3": {
        "label": "Estilo 3 — Fábula cristã",
        "descricao": "Fábula cristã com simbolismo compatível com a maturidade da faixa etária.",
        "instrucao": (
            "Use estrutura de fábula cristã. Símbolos e metáforas, se usados, devem ser simples o suficiente "
            "para a faixa escolhida e nunca virar abstração teológica. A personagem precisa viver a lição, "
            "não apenas ouvi-la."
        ),
    },
    "misto": {
        "label": "Estilo misto",
        "descricao": "Combina aventura, emoção, musicalidade e fábula cristã sem perder unidade.",
        "instrucao": (
            "Combine aventura e emoção do Estilo 1, musicalidade/repetição do Estilo 2 e a "
            "clareza moral da fábula cristã do Estilo 3. Preserve uma voz narrativa única e "
            "compatível com a faixa etária escolhida."
        ),
    },
}

ORDEM_ESTILOS = tuple(ESTILOS_NARRATIVOS.keys())


def normalizar_estilo(estilo: str | None) -> str:
    return estilo if estilo in ESTILOS_NARRATIVOS else "estilo_1"


def instrucao_estilo(estilo: str | None) -> str:
    chave = normalizar_estilo(estilo)
    dados = ESTILOS_NARRATIVOS[chave]
    return f"{dados['label']}: {dados['instrucao']}"


def _personagens_resumo(state: dict) -> str:
    """Combina Character DNA já formalizado com o briefing livre da autora."""
    personagens = state.get("personagens") or {}
    partes = []
    for nome, dados in personagens.items():
        if isinstance(dados, dict):
            descricao = dados.get("descricao_fixa", "")
            papel = dados.get("papel", "")
            rotulo = f"{nome} ({papel})" if papel else str(nome)
            partes.append(f"{rotulo}: {descricao}".strip())
        else:
            partes.append(str(nome))

    brief = str(state.get("personagens_historia_brief") or "").strip()
    if brief:
        partes.append("Briefing narrativo informado pela autora:\n" + brief)

    return "\n".join(partes) or (
        "Ainda não há personagens formalizados. Preserve exatamente os personagens "
        "descritos na premissa e não invente substitutos sem necessidade."
    )


def _normalizar_resultado(resposta: Any, estilo: str, modo: str) -> dict:
    if not isinstance(resposta, dict):
        resposta = {"amostra": str(resposta or "")}
    cenas = resposta.get("cenas") or resposta.get("cenas_texto") or []
    if not isinstance(cenas, list):
        cenas = []
    amostra = resposta.get("amostra") or resposta.get("preview") or ""
    if not amostra and cenas:
        amostra = "\n\n".join(str(c.get("texto", "")) for c in cenas[:4] if isinstance(c, dict))
    return {
        "estilo": estilo,
        "label": ESTILOS_NARRATIVOS[estilo]["label"],
        "modo": modo,
        "titulo": resposta.get("titulo") or "",
        "sinopse_poetica": resposta.get("sinopse_poetica") or resposta.get("sinopse") or "",
        "amostra": str(amostra or ""),
        "cenas_texto": cenas,
        "licao_final": resposta.get("licao_final") or "",
    }


def gerar_comparativo_estilos(state: dict, chamar_llm, modo: str = "amostra") -> dict[str, dict]:
    """Gera a mesma história/premissa nos quatro estilos e na mesma faixa etária."""
    modo = "completa" if modo == "completa" else "amostra"
    min_cenas = max(12, int(state.get("paginas_minimas") or 24) // 2)
    emocoes_validas = ", ".join(EMOCOES.keys())
    subemocoes_validas = ", ".join(EMOCOES_COMPLEMENTARES.keys())
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    perfil = perfil_etario(faixa)
    base = f"""
PREMISSA/TEMA:
{state.get('_entrada_tema_livre') or state.get('titulo') or ''}

Título atual: {state.get('titulo','')}
Emoção central: {state.get('emocao_central','')}
Lição cristã: {state.get('aprendizado_cristao') or state.get('licao_final') or ''}
Referência bíblica: {state.get('versiculo_referencia','')}
Faixa etária oficial: {perfil['short_label']}

{instrucao_faixa_etaria(faixa)}

PERSONAGENS — identidade, nomes, papéis e características pedidas devem permanecer iguais em todas as versões:
{_personagens_resumo(state)}
""".strip()

    resultados: dict[str, dict] = {}
    for estilo in ORDEM_ESTILOS:
        spec = ESTILOS_NARRATIVOS[estilo]
        if modo == "amostra":
            instrucao_saida = (
                "Crie uma AMOSTRA REPRESENTATIVA da história nesse estilo: 4 a 6 pequenos blocos/cenas, "
                "suficientes para a autora sentir ritmo, linguagem e atmosfera. Não precisa escrever o livro inteiro. "
                "Retorne JSON com titulo, sinopse_poetica, amostra e licao_final."
            )
        else:
            instrucao_saida = (
                f"Crie a HISTÓRIA COMPLETA nesse estilo, com no mínimo {min_cenas} cenas. "
                "Retorne JSON com titulo, sinopse_poetica, cenas_texto e licao_final. "
                "Cada cena deve conter numero, texto, emocao, emocao_secundaria, "
                "intensidade_emocional (1-5), transicao_emocional, figurino, "
                "contexto_visual, personagem_principal e expressao. "
                f"A emoção principal deve ser uma destas chaves canônicas: {emocoes_validas}. "
                f"A subemoção opcional pode ser uma destas: {subemocoes_validas}. "
                f"Use até aproximadamente {perfil['max_words_sentence']} palavras por frase e "
                f"{perfil['max_words_scene']} palavras por cena como TETOS heurísticos de revisão, nunca como meta. "
                "Não escolha cores no texto da história: o Emotional & Color Director aplicará a tabela canônica "
                "do Prompt-Mestre depois."
            )

        sistema = f"""
Você é o Comparative Story Director do FaithBloom Book Studio.
Gere UMA versão da MESMA história, sem mudar fatos centrais, personagens, lição cristã,
referência bíblica OU faixa etária. Varie somente o ESTILO NARRATIVO.

FAIXA ETÁRIA OBRIGATÓRIA:
{instrucao_faixa_etaria(faixa)}

ESTILO OBRIGATÓRIO:
{spec['label']}
{spec['instrucao']}

Regras invariáveis:
- linguagem, densidade, humor, tensão, musicalidade e onomatopeias seguem a faixa etária;
- frases claras e agradáveis de ler/ouvir;
- musicalidade natural em todos os estilos; no Estilo 2 ela pode ser mais intensa;
- repetição e onomatopeias somente na intensidade apropriada para a idade;
- emoções compreensíveis e coerentes com a maturidade do público;
- ação visual e movimento;
- humor quando couber, sem infantilizar leitores maiores;
- tensão segura e adequada à idade, nunca medo excessivo ou sofrimento pesado;
- transformação emocional, descoberta espiritual e recompensa/celebração;
- mensagem cristã amorosa, sem culpa religiosa, ameaça ou sermão longo;
- a personagem vive a lição;
- não invente o texto completo do versículo: preserve somente a referência fornecida;
- não altere Character DNA;
- não troque nomes, relações ou papéis informados pela autora;
- quando gerar história completa, registre emoção principal, subemoção opcional,
  intensidade 1–5 e transição emocional coerentes com cada cena;
- a psicologia das cores será aplicada depois pelo Emotional & Color Director com a
  tabela canônica FaithBloom, portanto não transforme a narrativa em instruções cromáticas.
""".strip()
        resposta = chamar_llm(sistema=sistema, instrucao=f"{base}\n\n{instrucao_saida}")
        resultados[estilo] = _normalizar_resultado(resposta, estilo, modo)

    return resultados


def aplicar_estilo_ao_state(state: dict, estilo: str, versao: dict | None = None) -> dict:
    novo = deepcopy(state)
    chave = normalizar_estilo(estilo)
    novo["estilo_narrativo"] = chave
    novo["estilo_narrativo_label"] = ESTILOS_NARRATIVOS[chave]["label"]
    novo["faixa_etaria"] = normalizar_faixa_etaria(novo.get("faixa_etaria"))
    novo["age_profile_id"] = novo["faixa_etaria"]

    # Amostra serve apenas para escolher o estilo; não altera título, moral nem cenas.
    if not versao or versao.get("modo") != "completa":
        novo["historia_escolhida_preservar"] = False
        return novo

    if versao.get("titulo"):
        novo["titulo"] = versao["titulo"]
    if versao.get("sinopse_poetica"):
        novo["sinopse_poetica"] = versao["sinopse_poetica"]
    if versao.get("licao_final"):
        novo["licao_final"] = versao["licao_final"]
    if versao.get("cenas_texto"):
        novo["cenas_texto"] = versao["cenas_texto"]
        novo["revisao_aprovada"] = False
        novo["historia_escolhida_preservar"] = True
    return novo

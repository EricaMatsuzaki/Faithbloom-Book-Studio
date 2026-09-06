"""Refinamento 24/25 — estilos narrativos formais e adicionais do FaithBloom.

Mantém a mesma premissa, personagens, lição cristã e referência bíblica,
variando somente a forma narrativa. Todos os estilos herdam a skill
`storyteller` do Roteirista e acrescentam sua especialização própria.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from agent_skills import skill_contract
from emotion_colors import EMOCOES, EMOCOES_COMPLEMENTARES
from age_profiles import normalizar_faixa_etaria, perfil_etario, instrucao_faixa_etaria

# Núcleo histórico e oficial do Prompt-Mestre. Deve permanecer com quatro estilos.
ESTILOS_NARRATIVOS = {
    "estilo_1": {
        "label": "Estilo 1 — Aventura",
        "skill_base": "storyteller",
        "descricao": "Roteirista + especialização Aventura: emoção, superação, ação visual, humor leve e transformação clara.",
        "instrucao": (
            "Use aventura, emoção e superação. Estruture problema -> tentativas -> "
            "descoberta -> ação -> transformação -> vitória espiritual. Priorize ação "
            "visual, diálogos naturais, pequenas surpresas e humor leve quando couber."
        ),
    },
    "estilo_2": {
        "label": "Estilo 2 — Poético/Rimado",
        "skill_base": "storyteller",
        "descricao": "Roteirista + especialização Poética: musicalidade, repetição e rimas naturais sem perder clareza.",
        "instrucao": (
            "Use linguagem poética adequada à idade, musicalidade, repetição suave e rimas naturais. "
            "Nunca force rimas nem sacrifique clareza; ajuste a intensidade da repetição à faixa etária."
        ),
    },
    "estilo_3": {
        "label": "Estilo 3 — Fábula cristã",
        "skill_base": "storyteller",
        "descricao": "Roteirista + especialização Fábula cristã, com simbolismo compatível com a maturidade da faixa etária.",
        "instrucao": (
            "Use estrutura de fábula cristã. Símbolos e metáforas, se usados, devem ser simples o suficiente "
            "para a faixa escolhida e nunca virar abstração teológica. A personagem precisa viver a lição, "
            "não apenas ouvi-la."
        ),
    },
    "misto": {
        "label": "Estilo misto",
        "skill_base": "storyteller",
        "descricao": "Roteirista + especialização Mista: aventura, emoção, musicalidade e fábula cristã com unidade.",
        "instrucao": (
            "Combine aventura e emoção do Estilo 1, musicalidade/repetição do Estilo 2 e a "
            "clareza moral da fábula cristã do Estilo 3. Preserve uma voz narrativa única e "
            "compatível com a faixa etária escolhida."
        ),
    },
}

# Biblioteca opcional: não entra automaticamente nas quatro chamadas principais.
ESTILOS_ADICIONAIS = {
    "cumulativo_lengalenga": {
        "label": "🔁 Cumulativo / Lengalenga",
        "skill_base": "storyteller",
        "descricao": (
            "Roteirista + especialização Cumulativa/Lengalenga: progressão por acumulação, refrão memorável, "
            "musicalidade, antecipação, participação e humor crescente."
        ),
        "instrucao": (
            "Use uma estrutura cumulativa original: a cada nova passagem acrescente personagem, ação, objeto, "
            "som, tentativa ou consequência, retomando de modo intencional parte do padrão anterior. Crie um "
            "refrão curto, original e fácil de antecipar, sem copiar frases de obras existentes. Use cadência, "
            "sons, contagem ou pequenas variações quando combinarem com a premissa. A repetição deve produzir "
            "prazer de antecipação e releitura, não enchimento. Faça o humor crescer pela progressão das situações, "
            "reações e pequenas surpresas visuais, sem humilhar personagens. Conduza a acumulação até um clímax "
            "claro e encerre o padrão com uma resolução satisfatória, transformação emocional e lição cristã natural. "
            "Para 3–5, privilegie simplicidade, refrão e participação; para 6–8, acrescente variações e causa-consequência; "
            "para 9–12, só use se a estrutura puder ganhar sofisticação suficiente para não infantilizar."
        ),
    },
}

ORDEM_ESTILOS = tuple(ESTILOS_NARRATIVOS.keys())
ORDEM_ESTILOS_ADICIONAIS = tuple(ESTILOS_ADICIONAIS.keys())
TODOS_ESTILOS = {**ESTILOS_NARRATIVOS, **ESTILOS_ADICIONAIS}


def normalizar_estilo(estilo: str | None) -> str:
    return estilo if estilo in TODOS_ESTILOS else "estilo_1"


def _spec_estilo(estilo: str | None) -> dict:
    return TODOS_ESTILOS[normalizar_estilo(estilo)]


def instrucao_estilo(estilo: str | None) -> str:
    dados = _spec_estilo(estilo)
    return f"{dados['label']}: {dados['instrucao']}"


def normalizar_licao_final(valor: Any) -> str:
    """Converte moral textual ou estruturada em texto editorial limpo para UI/PDF."""
    if isinstance(valor, dict):
        texto = str(
            valor.get("texto")
            or valor.get("licao")
            or valor.get("moral")
            or valor.get("mensagem")
            or ""
        ).strip()
        versiculo = str(valor.get("versiculo") or valor.get("referencia") or "").strip()
        reflexao = str(valor.get("reflexao_extra") or valor.get("reflexao") or "").strip()
        partes = [x for x in (texto, reflexao) if x]
        if versiculo and versiculo.lower() not in " ".join(partes).lower():
            partes.append(f"Referência bíblica: {versiculo}.")
        return " ".join(partes).strip()
    if isinstance(valor, (list, tuple)):
        return " ".join(str(x).strip() for x in valor if str(x).strip()).strip()
    return str(valor or "").strip()


def _personagens_resumo(state: dict) -> str:
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
        "label": TODOS_ESTILOS[estilo]["label"],
        "modo": modo,
        "titulo": resposta.get("titulo") or "",
        "sinopse_poetica": resposta.get("sinopse_poetica") or resposta.get("sinopse") or "",
        "amostra": str(amostra or ""),
        "cenas_texto": cenas,
        "licao_final": normalizar_licao_final(resposta.get("licao_final")),
    }


def _gerar_um_estilo(state: dict, chamar_llm, estilo: str, modo: str) -> dict:
    chave = normalizar_estilo(estilo)
    spec = TODOS_ESTILOS[chave]
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

    if modo == "amostra":
        instrucao_saida = (
            "Crie uma AMOSTRA REPRESENTATIVA da história nesse estilo: 4 a 6 pequenos blocos/cenas, "
            "suficientes para a autora sentir ritmo, linguagem, mecanismo narrativo e atmosfera. "
            "Não precisa escrever o livro inteiro. Retorne JSON com titulo, sinopse_poetica, amostra e licao_final."
        )
    else:
        instrucao_saida = (
            f"Crie a HISTÓRIA COMPLETA nesse estilo, com no mínimo {min_cenas} cenas. "
            "Retorne JSON com titulo, sinopse_poetica, cenas_texto e licao_final. "
            "Cada cena deve conter numero, texto, emocao, emocao_secundaria, intensidade_emocional (1-5), "
            "transicao_emocional, figurino, contexto_visual, personagem_principal e expressao. "
            f"A emoção principal deve ser uma destas chaves canônicas: {emocoes_validas}. "
            f"A subemoção opcional pode ser uma destas: {subemocoes_validas}. "
            f"Use até aproximadamente {perfil['max_words_sentence']} palavras por frase e "
            f"{perfil['max_words_scene']} palavras por cena como tetos heurísticos, nunca como meta. "
            "Não escolha cores no texto: o Emotional & Color Director fará isso depois."
        )

    sistema = f"""
Você é o Comparative Story Director do FaithBloom Book Studio.
Você HERDA integralmente a skill formal `storyteller` do Roteirista e, sobre essa
base profissional comum, aplica a especialização narrativa indicada abaixo.
Todos os estilos precisam ter a mesma qualidade de storytelling; o que muda é a forma de contar.

Gere UMA versão da MESMA história, sem mudar fatos centrais, personagens, lição cristã,
referência bíblica OU faixa etária. Varie somente o ESTILO NARRATIVO.

FAIXA ETÁRIA OBRIGATÓRIA:
{instrucao_faixa_etaria(faixa)}

ESPECIALIZAÇÃO NARRATIVA OBRIGATÓRIA:
{spec['label']}
{spec['instrucao']}

Regras invariáveis:
- linguagem, densidade, humor, tensão, musicalidade e onomatopeias seguem a faixa etária;
- frases claras e agradáveis de ler/ouvir;
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
- não copie frases, refrões, estruturas textuais distintivas ou personagens de livros existentes;
- quando gerar história completa, registre emoção principal, subemoção opcional,
  intensidade 1–5 e transição emocional coerentes com cada cena;
- a psicologia das cores será aplicada depois pelo Emotional & Color Director.
""".strip() + "\n\n" + skill_contract("storyteller")

    resposta = chamar_llm(sistema=sistema, instrucao=f"{base}\n\n{instrucao_saida}")
    return _normalizar_resultado(resposta, chave, modo)


def gerar_comparativo_estilos(state: dict, chamar_llm, modo: str = "amostra") -> dict[str, dict]:
    """Gera o núcleo de quatro estilos do Prompt-Mestre, todos com skill-base do Roteirista."""
    return {estilo: _gerar_um_estilo(state, chamar_llm, estilo, modo) for estilo in ORDEM_ESTILOS}


def gerar_estilo_adicional(state: dict, chamar_llm, estilo: str, modo: str = "amostra") -> dict:
    """Gera sob demanda um estilo da biblioteca opcional, sem aumentar o comparador principal."""
    if estilo not in ESTILOS_ADICIONAIS:
        raise ValueError(f"Estilo adicional não registrado: {estilo}")
    return _gerar_um_estilo(state, chamar_llm, estilo, modo)


def aplicar_estilo_ao_state(state: dict, estilo: str, versao: dict | None = None) -> dict:
    novo = deepcopy(state)
    chave = normalizar_estilo(estilo)
    novo["estilo_narrativo"] = chave
    novo["estilo_narrativo_label"] = TODOS_ESTILOS[chave]["label"]
    novo["faixa_etaria"] = normalizar_faixa_etaria(novo.get("faixa_etaria"))
    novo["age_profile_id"] = novo["faixa_etaria"]

    if not versao or versao.get("modo") != "completa":
        novo["historia_escolhida_preservar"] = False
        return novo

    if versao.get("titulo"):
        novo["titulo"] = versao["titulo"]
    if versao.get("sinopse_poetica"):
        novo["sinopse_poetica"] = versao["sinopse_poetica"]
    if versao.get("licao_final"):
        novo["licao_final"] = normalizar_licao_final(versao["licao_final"])
    if versao.get("cenas_texto"):
        novo["cenas_texto"] = versao["cenas_texto"]
        novo["revisao_aprovada"] = False
        novo["historia_escolhida_preservar"] = True
    return novo


SKILL_PROFILE_IDS = ("storyteller",)

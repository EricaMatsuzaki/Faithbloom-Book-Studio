"""FaithBloom Emotional & Color Director.

Transforma emoção narrativa em direção visual editável, sem alterar o
Character DNA. O módulo é determinístico e não gera imagens sozinho: ele
produz mapas/prompt directives que podem ser aprovados antes do Ilustrador.

Arquitetura emocional em três camadas:
1. Plutchik = mapa de família, intensidade e combinações emocionais;
2. Prompt-Mestre Erica Matsuzaki = tabela CANÔNICA de cor-base, atmosfera e
   intenção espiritual;
3. nuances complementares = cores de apoio/transições para evitar cenas
   monocromáticas e deixar o arco visual mais natural.

Importante: as cores publicadas na roda de Plutchik não são usadas como regra
cromática científica. No FaithBloom, a fonte cromática oficial é a tabela do
Prompt-Mestre em ``emotion_colors.py``.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Iterable
import unicodedata

from emotion_colors import (
    EMOCOES,
    EMOCOES_COMPLEMENTARES,
    REGRA_CHARACTER_DNA,
    REGRA_NAO_MONOCROMATICA,
)

# Presets editoriais. São direções de atmosfera, nunca cores obrigatórias do personagem.
PALETAS_PRESET: dict[str, dict] = {
    "Erica Matsuzaki · Pastel Faith": {
        "saturacao": "pastel suave",
        "luz_base": "dourada, acolhedora e delicada",
        "contraste": "baixo a moderado",
        "notas": "rosa, amarelo, azul, verde e lilás em equilíbrio; preservar cores canônicas dos personagens",
    },
    "Erica Matsuzaki · Christmas Faith": {
        "saturacao": "rica, porém infantil e suave",
        "luz_base": "contraste entre azul noturno e luzes douradas quentes",
        "contraste": "moderado",
        "notas": "vermelho, verde, dourado, azul profundo e branco-neve; final progressivamente mais quente e luminoso",
    },
    "Bedtime · Calm Faith": {
        "saturacao": "baixa e calmante",
        "luz_base": "azul suave com pontos quentes",
        "contraste": "baixo",
        "notas": "evitar estímulo visual excessivo; manter leitura emocional clara",
    },
    "Cute Friends · Coloring Color Master": {
        "saturacao": "alegre e limpa",
        "luz_base": "clara e uniforme",
        "contraste": "moderado",
        "notas": "cores alegres para capas/previews, sem modificar o desenho-base do Line Art Master",
    },
}


# ---------------------------------------------------------------------------
# PLUTCHIK — taxonomia emocional (não é a fonte canônica de cores)
# ---------------------------------------------------------------------------
PLUTCHIK_FAMILIAS: dict[str, tuple[str, str, str]] = {
    "alegria": ("serenidade", "alegria", "êxtase"),
    "confianca": ("aceitação", "confiança", "admiração"),
    "medo": ("apreensão", "medo", "terror"),
    "surpresa": ("distração", "surpresa", "espanto"),
    "tristeza": ("pensatividade", "tristeza", "pesar"),
    "nojo": ("tédio", "nojo", "aversão"),
    "raiva": ("irritação", "raiva", "fúria"),
    "antecipacao": ("interesse", "antecipação", "vigilância"),
}

PLUTCHIK_COMBINACOES: dict[frozenset[str], str] = {
    frozenset(("alegria", "confianca")): "amor",
    frozenset(("antecipacao", "alegria")): "otimismo",
    frozenset(("confianca", "medo")): "submissão",
    frozenset(("medo", "surpresa")): "espanto/admiração",
    frozenset(("surpresa", "tristeza")): "desaprovação",
    frozenset(("tristeza", "nojo")): "remorso",
    frozenset(("nojo", "raiva")): "desprezo",
    frozenset(("raiva", "antecipacao")): "agressividade",
}

# Emoção narrativa -> (família Plutchik principal, família secundária opcional)
PLUTCHIK_POR_EMOCAO: dict[str, tuple[str, str]] = {
    "alegria": ("alegria", ""),
    "tristeza": ("tristeza", ""),
    "medo": ("medo", ""),
    "raiva": ("raiva", ""),
    "nojo": ("nojo", ""),
    "ansiedade": ("medo", "antecipacao"),
    "vergonha": ("tristeza", "confianca"),
    "inveja": ("raiva", "tristeza"),
    "tedio": ("nojo", ""),
    "esperanca": ("antecipacao", "alegria"),
    "curiosidade": ("antecipacao", ""),
    "inseguranca": ("medo", ""),
    "coragem": ("confianca", "antecipacao"),
    "fe": ("confianca", "alegria"),
    "gratidao": ("alegria", "confianca"),
    "expectativa": ("antecipacao", ""),
    "impaciencia": ("antecipacao", "raiva"),
    "frustracao": ("raiva", "tristeza"),
    "reflexao": ("tristeza", ""),
    "calma": ("alegria", "confianca"),
    "paz": ("alegria", "confianca"),
    "perda": ("tristeza", ""),
    "acolhimento": ("confianca", "alegria"),
    "consolo": ("confianca", "tristeza"),
    "decepcao": ("tristeza", ""),
    "surpresa": ("surpresa", ""),
    "encantamento": ("surpresa", "alegria"),
    "humor": ("alegria", "surpresa"),
    "empatia": ("confianca", "tristeza"),
    "servico": ("confianca", "alegria"),
    "compaixao": ("confianca", "tristeza"),
    "descoberta_espiritual": ("confianca", "alegria"),
}


ARCOS_SUGERIDOS: dict[str, list[str]] = {
    "medo": ["curiosidade", "inseguranca", "medo", "ansiedade", "coragem", "fe", "esperanca", "alegria", "gratidao"],
    "ansiedade": ["curiosidade", "expectativa", "ansiedade", "frustracao", "reflexao", "fe", "esperanca", "calma", "gratidao"],
    "impaciencia": ["curiosidade", "alegria", "impaciencia", "frustracao", "tristeza", "reflexao", "fe", "esperanca", "alegria", "gratidao"],
    "tristeza": ["alegria", "perda", "tristeza", "acolhimento", "reflexao", "fe", "esperanca", "consolo", "gratidao"],
    "esperanca": ["curiosidade", "desafio", "incerteza", "reflexao", "fe", "esperanca", "alegria", "gratidao"],
    "natal": ["expectativa", "alegria", "decepcao", "surpresa", "humor", "empatia", "curiosidade", "fe", "servico", "compaixao", "alegria", "gratidao"],
}

# Emoções narrativas adicionais mapeiam para a emoção CROMÁTICA canônica.
EMOCAO_BASE: dict[str, str] = {
    "curiosidade": "esperanca",
    "inseguranca": "medo",
    "coragem": "esperanca",
    "fe": "esperanca",
    "gratidao": "alegria",
    "expectativa": "ansiedade",
    "impaciencia": "raiva",
    "frustracao": "tristeza",
    "reflexao": "tristeza",
    "calma": "esperanca",
    "paz": "esperanca",
    "perda": "tristeza",
    "acolhimento": "esperanca",
    "consolo": "esperanca",
    "decepcao": "tristeza",
    "surpresa": "alegria",
    "encantamento": "alegria",
    "humor": "alegria",
    "empatia": "tristeza",
    "servico": "esperanca",
    "compaixao": "esperanca",
    "descoberta_espiritual": "esperanca",
    "desafio": "ansiedade",
    "incerteza": "ansiedade",
}


def _slug_emocao(value: str) -> str:
    texto = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return texto.strip().lower().replace(" ", "_").replace("-", "_")


def normalizar_emocao(emocao: str) -> str:
    """Retorna a emoção CROMÁTICA canônica do Prompt-Mestre."""
    e = _slug_emocao(emocao or "esperanca")
    if e in EMOCOES:
        return e
    if e in EMOCOES_COMPLEMENTARES:
        return str(EMOCOES_COMPLEMENTARES[e]["base"])
    return EMOCAO_BASE.get(e, "esperanca")


def _nivel_plutchik(familia: str, intensidade: int) -> str:
    niveis = PLUTCHIK_FAMILIAS.get(familia)
    if not niveis:
        return ""
    idx = 0 if intensidade <= 2 else (1 if intensidade == 3 else 2)
    return niveis[idx]


def analisar_plutchik(emocao: str, intensidade: int = 3, subemocao: str = "") -> dict:
    """Classifica a cena na roda de Plutchik sem usar suas cores como regra visual."""
    intensidade = max(1, min(5, int(intensidade)))
    chave = _slug_emocao(emocao)
    principal, secundaria = PLUTCHIK_POR_EMOCAO.get(chave, ("antecipacao", "alegria"))

    # A subemoção pode refinar a família secundária, quando reconhecida.
    sub_chave = _slug_emocao(subemocao)
    if sub_chave:
        sub_principal, _ = PLUTCHIK_POR_EMOCAO.get(sub_chave, ("", ""))
        if sub_principal and sub_principal != principal:
            secundaria = sub_principal

    combinacao = ""
    if secundaria:
        combinacao = PLUTCHIK_COMBINACOES.get(frozenset((principal, secundaria)), "")
    return {
        "familia_principal": principal,
        "familia_secundaria": secundaria,
        "nivel": _nivel_plutchik(principal, intensidade),
        "combinacao": combinacao,
        "intensidade": intensidade,
        "nota": "Plutchik orienta família/intensidade emocional; a cor visual vem da tabela canônica FaithBloom.",
    }


def _nuance_para(emocao: str) -> dict:
    chave = _slug_emocao(emocao)
    return deepcopy(EMOCOES_COMPLEMENTARES.get(chave, {}))


def direcao_emocional(
    emocao: str,
    preset: str = "Erica Matsuzaki · Pastel Faith",
    intensidade: int = 3,
    subemocao: str = "",
    transicao: str = "",
) -> dict:
    """Cria direção emocional+cromática completa para uma cena."""
    base = normalizar_emocao(emocao)
    dados = deepcopy(EMOCOES[base])
    intensidade = max(1, min(5, int(intensidade)))
    nuance = _nuance_para(emocao)
    nuance_sub = _nuance_para(subemocao)

    cores_apoio: list[str] = []
    for fonte in (dados.get("cores_apoio", []), nuance.get("cores_apoio", []), nuance_sub.get("cores_apoio", [])):
        for cor in fonte or []:
            if str(cor) not in cores_apoio:
                cores_apoio.append(str(cor))

    atmosfera = str(nuance_sub.get("atmosfera") or nuance.get("atmosfera") or dados["atmosfera"])
    luz = str(nuance_sub.get("luz") or nuance.get("luz") or dados.get("luz", ""))
    preset_final = preset if preset in PALETAS_PRESET else "Erica Matsuzaki · Pastel Faith"
    plutchik = analisar_plutchik(emocao, intensidade, subemocao)

    return {
        "emocao_narrativa": emocao,
        "subemocao": subemocao,
        "transicao_emocional": transicao,
        "emocao_cromatica_base": base,
        "cor_principal": dados["cor"],
        "cores_apoio": cores_apoio,
        "atmosfera": atmosfera,
        "luz_emocional": luz,
        "uso": dados["uso"],
        "uso_espiritual": dados.get("uso_espiritual", dados.get("uso", "")),
        "intensidade": intensidade,
        "plutchik": plutchik,
        "preset": preset_final,
        "preset_visual": deepcopy(PALETAS_PRESET[preset_final]),
        "regra_nao_monocromatica": REGRA_NAO_MONOCROMATICA,
        "regra_character_dna": (
            "Nunca recolorir pele, pelagem, cabelo, olhos, marcas, acessórios canônicos ou outras cores bloqueadas do Character DNA. "
            + REGRA_CHARACTER_DNA
        ),
    }


def construir_mapa_emocional(cenas: Iterable[dict], preset: str = "Erica Matsuzaki · Pastel Faith") -> list[dict]:
    mapa = []
    for cena in cenas:
        d = direcao_emocional(
            cena.get("emocao", "esperanca"),
            preset,
            cena.get("intensidade_emocional", 3),
            cena.get("emocao_secundaria", cena.get("subemocao", "")),
            cena.get("transicao_emocional", ""),
        )
        mapa.append({
            "numero": int(cena.get("numero", len(mapa) + 1)),
            "texto": cena.get("texto", ""),
            "personagem_principal": cena.get("personagem_principal", ""),
            "expressao": cena.get("expressao", cena.get("emocao", "")),
            "figurino": cena.get("figurino", "padrão"),
            "cenario": cena.get("contexto_visual", ""),
            "direcao": d,
            "aprovado": bool(cena.get("mapa_emocional_aprovado", False)),
            "instrucao_autora": cena.get("instrucao_emocional", ""),
        })
    return mapa


def sugerir_arco(emocao_central: str, total_cenas: int) -> list[str]:
    chave = _slug_emocao(emocao_central or "esperanca")
    base = ARCOS_SUGERIDOS.get(chave)
    if not base:
        can = normalizar_emocao(chave)
        base = ARCOS_SUGERIDOS.get(can, ARCOS_SUGERIDOS["esperanca"])
    total = max(1, int(total_cenas))
    if total == 1:
        return [base[-1]]
    idxs = [round(i * (len(base) - 1) / (total - 1)) for i in range(total)]
    return [base[i] for i in idxs]


def aplicar_arco(cenas: list[dict], emocao_central: str) -> list[dict]:
    arco = sugerir_arco(emocao_central, len(cenas))
    saida = []
    for idx, (cena, emocao) in enumerate(zip(cenas, arco)):
        c = deepcopy(cena)
        if not c.get("emocao_travada"):
            anterior = c.get("emocao", "")
            c["emocao"] = emocao
            if anterior and anterior != emocao and not c.get("transicao_emocional"):
                c["transicao_emocional"] = f"{anterior} → {emocao}"
        saida.append(c)
    return saida


def prompt_direcao_visual(item_mapa: dict) -> str:
    d = item_mapa.get("direcao", {})
    preset = d.get("preset_visual", {})
    extra = item_mapa.get("instrucao_autora", "").strip()
    pl = d.get("plutchik", {})
    apoio = ", ".join(d.get("cores_apoio", []) or [])
    texto = (
        f"DIREÇÃO EMOCIONAL DA CENA: emoção principal={d.get('emocao_narrativa','')}; "
        f"subemoção={d.get('subemocao','') or 'não definida'}; transição={d.get('transicao_emocional','') or 'estável'}. "
        f"Intensidade {d.get('intensidade',3)}/5. "
        f"Mapa Plutchik: família={pl.get('familia_principal','')}, nível={pl.get('nivel','')}, "
        f"família secundária={pl.get('familia_secundaria','') or 'nenhuma'}, combinação={pl.get('combinacao','') or 'nenhuma'}. "
        f"A roda de Plutchik orienta emoção/intensidade, NÃO define a cor da cena. "
        f"TABELA CANÔNICA FAITHBLOOM: base cromática={d.get('cor_principal','')}; "
        f"cores de apoio={apoio}; atmosfera={d.get('atmosfera','')}; luz emocional={d.get('luz_emocional','')}. "
        f"Intenção espiritual editorial={d.get('uso_espiritual','')}. "
        f"Preset editorial={d.get('preset','')}; luz-base={preset.get('luz_base','')}; saturação={preset.get('saturacao','')}. "
        f"Expressão/linguagem corporal desejada={item_mapa.get('expressao','')}. "
        f"REGRA NÃO MONOCROMÁTICA: {d.get('regra_nao_monocromatica','')} "
        f"REGRA CRÍTICA DE IDENTIDADE: {d.get('regra_character_dna','')}"
    )
    if extra:
        texto += f" Instrução específica da autora: {extra}. Altere somente o solicitado."
    return texto

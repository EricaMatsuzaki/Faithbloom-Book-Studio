"""FaithBloom Emotional & Color Director.

Transforma emoção narrativa em direção visual editável, sem alterar o
Character DNA. O módulo é determinístico e não gera imagens sozinho: ele
produz mapas/prompt directives que podem ser aprovados antes do Ilustrador.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Iterable

from emotion_colors import EMOCOES

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

ARCOS_SUGERIDOS: dict[str, list[str]] = {
    "medo": ["curiosidade", "inseguranca", "medo", "ansiedade", "coragem", "fe", "esperanca", "alegria", "gratidao"],
    "ansiedade": ["curiosidade", "expectativa", "ansiedade", "frustracao", "reflexao", "fe", "esperanca", "calma", "gratidao"],
    "impaciencia": ["curiosidade", "alegria", "impaciencia", "frustracao", "tristeza", "reflexao", "fe", "esperanca", "alegria", "gratidao"],
    "tristeza": ["alegria", "perda", "tristeza", "acolhimento", "reflexao", "fe", "esperanca", "consolo", "gratidao"],
    "esperanca": ["curiosidade", "desafio", "incerteza", "reflexao", "fe", "esperanca", "alegria", "gratidao"],
    "natal": ["expectativa", "alegria", "decepcao", "surpresa", "humor", "empatia", "curiosidade", "fe", "servico", "compaixao", "alegria", "gratidao"],
}

# Emoções narrativas adicionais mapeiam para uma emoção cromática-base.
EMOCAO_BASE: dict[str, str] = {
    "curiosidade": "esperanca",
    "inseguranca": "medo",
    "coragem": "esperanca",
    "fe": "esperanca",
    "fé": "esperanca",
    "gratidao": "alegria",
    "gratidão": "alegria",
    "expectativa": "ansiedade",
    "impaciencia": "raiva",
    "impaciência": "raiva",
    "frustracao": "raiva",
    "frustração": "raiva",
    "reflexao": "tristeza",
    "reflexão": "tristeza",
    "calma": "tristeza",
    "perda": "tristeza",
    "acolhimento": "esperanca",
    "consolo": "esperanca",
    "decepcao": "tristeza",
    "decepção": "tristeza",
    "surpresa": "alegria",
    "humor": "alegria",
    "empatia": "tristeza",
    "servico": "esperanca",
    "serviço": "esperanca",
    "compaixao": "esperanca",
    "compaixão": "esperanca",
}


def normalizar_emocao(emocao: str) -> str:
    e = (emocao or "esperanca").strip().lower()
    return EMOCAO_BASE.get(e, e if e in EMOCOES else "esperanca")


def direcao_emocional(emocao: str, preset: str = "Erica Matsuzaki · Pastel Faith", intensidade: int = 3) -> dict:
    base = normalizar_emocao(emocao)
    dados = deepcopy(EMOCOES[base])
    intensidade = max(1, min(5, int(intensidade)))
    return {
        "emocao_narrativa": emocao,
        "emocao_cromatica_base": base,
        "cor_principal": dados["cor"],
        "atmosfera": dados["atmosfera"],
        "uso": dados["uso"],
        "intensidade": intensidade,
        "preset": preset if preset in PALETAS_PRESET else "Erica Matsuzaki · Pastel Faith",
        "preset_visual": deepcopy(PALETAS_PRESET.get(preset, PALETAS_PRESET["Erica Matsuzaki · Pastel Faith"])),
        "regra_character_dna": "A paleta atua em luz, fundo, atmosfera e elementos secundários. Nunca recolorir pelagem, pele, cabelo, olhos, roupas canônicas ou marcas bloqueadas do personagem.",
    }


def construir_mapa_emocional(cenas: Iterable[dict], preset: str = "Erica Matsuzaki · Pastel Faith") -> list[dict]:
    mapa = []
    for cena in cenas:
        d = direcao_emocional(cena.get("emocao", "esperanca"), preset, cena.get("intensidade_emocional", 3))
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
    chave = (emocao_central or "esperanca").strip().lower()
    base = ARCOS_SUGERIDOS.get(chave, ARCOS_SUGERIDOS[normalizar_emocao(chave)] if normalizar_emocao(chave) in ARCOS_SUGERIDOS else ARCOS_SUGERIDOS["esperanca"])
    total = max(1, int(total_cenas))
    if total == 1:
        return [base[-1]]
    # Distribui o arco inteiro pelo número desejado sem perder início/fim.
    idxs = [round(i * (len(base) - 1) / (total - 1)) for i in range(total)]
    return [base[i] for i in idxs]


def aplicar_arco(cenas: list[dict], emocao_central: str) -> list[dict]:
    arco = sugerir_arco(emocao_central, len(cenas))
    saida = []
    for cena, emocao in zip(cenas, arco):
        c = deepcopy(cena)
        if not c.get("emocao_travada"):
            c["emocao"] = emocao
        saida.append(c)
    return saida


def prompt_direcao_visual(item_mapa: dict) -> str:
    d = item_mapa.get("direcao", {})
    preset = d.get("preset_visual", {})
    extra = item_mapa.get("instrucao_autora", "").strip()
    texto = (
        f"DIREÇÃO EMOCIONAL DA CENA: {d.get('emocao_narrativa','')}. "
        f"Base cromática: {d.get('cor_principal','')}; atmosfera: {d.get('atmosfera','')}; intensidade {d.get('intensidade',3)}/5. "
        f"Preset editorial: {d.get('preset','')}; luz-base: {preset.get('luz_base','')}; saturação: {preset.get('saturacao','')}. "
        f"Expressão/linguagem corporal desejada: {item_mapa.get('expressao','')}. "
        f"REGRA CRÍTICA: {d.get('regra_character_dna','')}"
    )
    if extra:
        texto += f" Instrução específica da autora: {extra}. Altere somente o solicitado."
    return texto

"""
Regra fixa do agente Ilustrador: psicologia das cores aplicada à emoção
de cada cena. O Ilustrador NUNCA escolhe cor no chute - a emoção da cena
(definida pelo Roteirista) dita a paleta automaticamente.

Importante: isso descreve ATMOSFERA DE CENA (luz, cor de fundo, tom geral),
nunca personifica a emoção como um personagem à parte - isso preserva o
valor pedagógico da ideia sem esbarrar em direito autoral de nenhum estúdio.
"""

EMOCOES: dict[str, dict[str, str]] = {
    "alegria": {
        "cor": "amarelo-dourado",
        "atmosfera": "brilhante e leve",
        "uso": "momentos de vitória, fé e amizade",
    },
    "tristeza": {
        "cor": "azul-claro",
        "atmosfera": "suave e calma",
        "uso": "reflexão e empatia",
    },
    "medo": {
        "cor": "roxo-escuro",
        "atmosfera": "luz fria e contraste",
        "uso": "dúvidas e incerteza, antes de encontrar coragem",
    },
    "raiva": {
        "cor": "vermelho e laranja",
        "atmosfera": "forte e intensa",
        "uso": "conflito e impaciência, antes do aprendizado sobre autocontrole",
    },
    "nojo": {
        "cor": "verde-claro",
        "atmosfera": "sutil e difusa",
        "uso": "situação desconfortável antes de uma escolha positiva",
    },
    "ansiedade": {
        "cor": "rosa e lilás",
        "atmosfera": "névoa suave",
        "uso": "expectativa e incerteza",
    },
    "vergonha": {
        "cor": "pêssego e bege",
        "atmosfera": "doce e suave",
        "uso": "vulnerabilidade antes da aceitação",
    },
    "inveja": {
        "cor": "verde-musgo",
        "atmosfera": "luz difusa e fria",
        "uso": "desejo pelo que o outro tem, antes do contentamento",
    },
    "tedio": {
        "cor": "cinza-claro e azul pálido",
        "atmosfera": "lenta",
        "uso": "desânimo antes de redescobrir o propósito",
    },
    "esperanca": {
        "cor": "dourado e azul-celeste",
        "atmosfera": "luminosa e quente",
        "uso": "clímax espiritual e final feliz",
    },
}


def paleta_para_prompt(emocao: str) -> str:
    """Traduz a emoção da cena numa instrução de paleta pro prompt de imagem."""
    dados = EMOCOES.get(emocao.lower())
    if not dados:
        raise ValueError(
            f"Emoção '{emocao}' não está no dicionário fixo. "
            f"Opções válidas: {list(EMOCOES)}"
        )
    return (
        f"Paleta de cor dominante: {dados['cor']}. "
        f"Atmosfera de luz e cena: {dados['atmosfera']}. "
        "A emoção deve se expressar através da atmosfera da cena "
        "(cor de fundo, luz, expressão facial do personagem) - "
        "NUNCA personificar a emoção como um personagem à parte."
    )

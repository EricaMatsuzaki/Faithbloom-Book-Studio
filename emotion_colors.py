"""FaithBloom — Psicologia das Cores e Emoções.

A tabela canônica abaixo vem do Prompt-Mestre editorial da coleção.
Ela é aplicada página por página como DIREÇÃO VISUAL DA CENA, não como
recoloração do personagem.

Princípios obrigatórios:
- a emoção narrativa define uma cor-base, atmosfera e intenção espiritual;
- cores de apoio refinam a cena sem torná-la monocromática;
- luz, fundo, contraste, saturação e elementos secundários podem acompanhar
  a emoção;
- pele, pelagem, cabelo, olhos, marcas e demais cores canônicas do Character
  DNA nunca são recoloridas pela psicologia das cores.

A roda de Plutchik é tratada em ``emotional_color_director.py`` como mapa de
famílias/intensidade/combinações emocionais. As cores da roda NÃO substituem
esta tabela canônica do FaithBloom.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# TABELA CANÔNICA — PROMPT-MESTRE ERICA MATSUZAKI
# ---------------------------------------------------------------------------
EMOCOES: dict[str, dict[str, object]] = {
    "alegria": {
        "label": "Alegria",
        "cor": "amarelo-dourado",
        "atmosfera": "brilho leve",
        "uso_espiritual": "Amor de Deus e gratidão",
        "uso": "Amor de Deus e gratidão",
        "cores_apoio": ["pêssego", "azul-claro", "verde-claro"],
        "luz": "quente, leve e brilhante",
    },
    "tristeza": {
        "label": "Tristeza",
        "cor": "azul-claro",
        "atmosfera": "suave e reflexiva",
        "uso_espiritual": "Deus consola corações",
        "uso": "Deus consola corações",
        "cores_apoio": ["lilás acinzentado", "cinza-azulado", "creme frio suave"],
        "luz": "difusa e delicada",
    },
    "medo": {
        "label": "Medo",
        "cor": "roxo-escuro",
        "atmosfera": "fria e contrastada",
        "uso_espiritual": "Confiar em Deus",
        "uso": "Confiar em Deus",
        "cores_apoio": ["azul-noturno suave", "cinza-azulado", "lavanda fria"],
        "luz": "fria, com sombras suaves e contraste infantil controlado",
    },
    "raiva": {
        "label": "Raiva",
        "cor": "vermelho/laranja",
        "atmosfera": "forte",
        "uso_espiritual": "Perdão e domínio próprio",
        "uso": "Perdão e domínio próprio",
        "cores_apoio": ["ocre quente", "coral", "dourado queimado suave"],
        "luz": "mais intensa, sem agressividade visual excessiva",
    },
    "nojo": {
        "label": "Nojo",
        "cor": "verde-claro",
        "atmosfera": "difusa e sutil",
        "uso_espiritual": "Escolher o que é puro",
        "uso": "Escolher o que é puro",
        "cores_apoio": ["amarelo-esverdeado suave", "creme", "cinza-claro"],
        "luz": "difusa e controlada",
    },
    "ansiedade": {
        "label": "Ansiedade",
        "cor": "rosa/lilás",
        "atmosfera": "névoa suave",
        "uso_espiritual": "Entregar preocupações",
        "uso": "Entregar preocupações",
        "cores_apoio": ["lavanda", "azul pálido", "rosa-claro"],
        "luz": "suave, levemente enevoada",
    },
    "vergonha": {
        "label": "Vergonha",
        "cor": "pêssego",
        "atmosfera": "doce e vulnerável",
        "uso_espiritual": "Somos amados",
        "uso": "Somos amados",
        "cores_apoio": ["bege quente", "rosa antigo suave", "creme"],
        "luz": "macia e acolhedora",
    },
    "inveja": {
        "label": "Inveja",
        "cor": "verde-musgo",
        "atmosfera": "luz fria",
        "uso_espiritual": "Contentamento",
        "uso": "Contentamento",
        "cores_apoio": ["verde sálvia", "cinza azulado", "bege frio"],
        "luz": "fria e levemente dessaturada",
    },
    "tedio": {
        "label": "Tédio",
        "cor": "cinza-azulado",
        "atmosfera": "lenta",
        "uso_espiritual": "Redescobrir propósito",
        "uso": "Redescobrir propósito",
        "cores_apoio": ["azul pálido", "cinza-claro", "bege suave"],
        "luz": "plana e calma, pronta para ganhar vida quando a história mudar",
    },
    "esperanca": {
        "label": "Esperança/Fé",
        "cor": "dourado + azul-celeste",
        "atmosfera": "luminosa",
        "uso_espiritual": "Clímax espiritual/final",
        "uso": "Clímax espiritual/final",
        "cores_apoio": ["creme luminoso", "pêssego claro", "verde renovação", "branco quente"],
        "luz": "luminosa, acolhedora e progressivamente quente",
    },
}


# Emoções/subemoções complementares. Elas NÃO substituem a tabela acima:
# apontam para uma base canônica e acrescentam nuances visuais.
EMOCOES_COMPLEMENTARES: dict[str, dict[str, object]] = {
    "curiosidade": {
        "base": "esperanca",
        "cores_apoio": ["verde fresco", "amarelo clarinho", "azul céu"],
        "atmosfera": "descoberta, frescor e atenção",
        "luz": "limpa e clara",
    },
    "frustracao": {
        "base": "tristeza",
        "cores_apoio": ["azul frio", "cinza-claro", "lavanda suave"],
        "atmosfera": "contida e silenciosa",
        "luz": "difusa, com contraste reduzido",
    },
    "decepcao": {
        "base": "tristeza",
        "cores_apoio": ["azul suave", "lavanda", "cinza azulado"],
        "atmosfera": "suave e reflexiva",
        "luz": "difusa",
    },
    "inseguranca": {
        "base": "medo",
        "cores_apoio": ["azul-noturno suave", "roxo macio", "cinza azulado"],
        "atmosfera": "cautelosa, nunca assustadora demais",
        "luz": "sombras suaves",
    },
    "acolhimento": {
        "base": "esperanca",
        "cores_apoio": ["rosa suave", "dourado", "bege quente", "verde macio"],
        "atmosfera": "protetora e carinhosa",
        "luz": "quente e macia",
    },
    "gratidao": {
        "base": "alegria",
        "cores_apoio": ["dourado suave", "rosa suave", "bege quente", "verde macio"],
        "atmosfera": "carinhosa e luminosa",
        "luz": "quente com brilho delicado",
    },
    "descoberta_espiritual": {
        "base": "esperanca",
        "cores_apoio": ["dourado delicado", "branco quente", "pêssego luminoso", "azul-celeste"],
        "atmosfera": "serena, acolhedora e luminosa",
        "luz": "amanhecer/luz suave, sem efeitos sobrenaturais exagerados",
    },
    "paz": {
        "base": "esperanca",
        "cores_apoio": ["azul-celeste", "creme", "verde sálvia", "dourado muito suave"],
        "atmosfera": "serena e segura",
        "luz": "macia e uniforme",
    },
    "encantamento": {
        "base": "alegria",
        "cores_apoio": ["amarelo suave", "pêssego", "azul claro", "lavanda clara"],
        "atmosfera": "leve, curiosa e mágica sem excesso",
        "luz": "brilho delicado",
    },
}


REGRA_NAO_MONOCROMATICA = (
    "As cores emocionais devem APOIAR a emoção, nunca transformar toda a cena em monocromática. "
    "Use a cor-base como direção dominante e combine cores de apoio coerentes, mantendo variedade natural no cenário."
)

REGRA_CHARACTER_DNA = (
    "A paleta emocional atua em luz, fundo, atmosfera, contraste, saturação e elementos secundários. "
    "NUNCA recolorir pele, pelagem, cabelo, olhos, marcas, acessórios canônicos ou outras cores bloqueadas do Character DNA."
)


def paleta_para_prompt(emocao: str) -> str:
    """Traduz uma emoção canônica em instrução de paleta para geração visual."""
    chave = (emocao or "esperanca").strip().lower()
    dados = EMOCOES.get(chave)
    if not dados:
        complemento = EMOCOES_COMPLEMENTARES.get(chave)
        if complemento:
            dados = EMOCOES[str(complemento["base"])]
        else:
            raise ValueError(
                f"Emoção '{emocao}' não está no dicionário FaithBloom. "
                f"Opções canônicas: {list(EMOCOES)}"
            )
    apoio = ", ".join(str(x) for x in dados.get("cores_apoio", []))
    return (
        f"PSICOLOGIA DAS CORES — base FaithBloom: {dados['cor']}. "
        f"Cores de apoio sugeridas: {apoio}. "
        f"Atmosfera: {dados['atmosfera']}. Luz: {dados.get('luz','')}. "
        f"Intenção espiritual editorial: {dados.get('uso_espiritual','')}. "
        f"{REGRA_NAO_MONOCROMATICA} {REGRA_CHARACTER_DNA}"
    )

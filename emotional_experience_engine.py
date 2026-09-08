"""FaithBloom Emotional Experience Engine™.

Camada editorial compartilhada que orienta como sentimentos e emoções são
VIVIDOS dentro das histórias. Não copia personagens, cenas, diálogos ou
estruturas de obras existentes: trabalha apenas mecanismos gerais de narrativa
emocional.

Princípio central:
    acontecimento concreto -> emoção/sensação -> reação -> escolha/tentativa ->
    consequência -> descoberta/aprendizado -> transformação

Os perfis etários são heurísticas editoriais, não regras universais de
desenvolvimento infantil nem diagnóstico psicológico.
"""
from __future__ import annotations

from copy import deepcopy

SCHEMA = "faithbloom.emotional-experience.v1"

EMOTIONAL_EXPERIENCE_PRINCIPLES = [
    "emoções nascem de acontecimentos concretos e afetam reação, escolha, tentativa ou consequência",
    "emoções não são classificadas como boas ou más; a história mostra respostas saudáveis, morais e adequadas à idade",
    "a personagem pode sentir emoções contraditórias ao mesmo tempo quando isso for compatível com a maturidade da faixa etária",
    "momentos alegres também ensinam; aprendizado não precisa nascer apenas de dor, erro ou conflito",
    "frustração, tristeza, perda, saudade, rejeição, vergonha, medo, raiva, nojo, inveja, ansiedade, timidez e solidão podem existir sem serem apagados artificialmente",
    "alegria, curiosidade, amor, amizade, alívio, pertencimento, coragem, esperança, gratidão, paz e celebração também devem ter função narrativa real",
    "uma emoção importante deve aparecer no corpo, pensamento, fala, comportamento ou escolha da personagem, não apenas ser nomeada",
    "a descoberta deve nascer da experiência; evitar adulto/mentor explicando toda a lição antes de a criança-personagem vivê-la",
    "a fé acompanha a emoção em vez de negá-la: a personagem pode continuar triste, com medo ou ansiosa e ainda assim encontrar consolo, ajuda, coragem e confiança em Deus",
    "perdas e decepções não precisam ser magicamente desfeitas para existir esperança; a transformação pode ser aprender a lembrar, receber apoio, aceitar, perdoar, recomeçar ou seguir em frente",
    "humor pode coexistir com vulnerabilidade sem ridicularizar sofrimento nem humilhar personagens",
    "não inventar uma emoção nova em toda cena; usar transições coerentes e dar tempo para sentimentos importantes respirarem",
]

EMOTIONAL_EXPERIENCE_CYCLE = [
    "acontecimento",
    "sentimento/emoção",
    "sensação corporal ou interpretação",
    "reação",
    "escolha/tentativa",
    "consequência",
    "descoberta/aprendizado",
    "transformação",
]

AGE_EMOTIONAL_PROFILES: dict[str, dict] = {
    "3-5": {
        "complexidade": "emoções predominantemente concretas, imediatas e ligadas a situações visíveis",
        "foco": [
            "alegria", "tristeza", "medo", "raiva", "surpresa", "frustração",
            "ciúme simples", "vergonha simples", "curiosidade", "carinho", "alívio",
        ],
        "mistura": "uma emoção dominante por momento; emoções misturadas podem aparecer de forma muito simples e concreta",
        "interioridade": "mostrar principalmente por ação, expressão, corpo, fala curta e repetição; evitar longas explicações internas",
        "aprendizado": "nomear de modo simples o que aconteceu e mostrar uma resposta concreta: pedir ajuda, esperar, compartilhar, tentar novamente, pedir desculpas, receber consolo",
    },
    "3-8": {
        "complexidade": "emoções concretas com espaço para frustração, insegurança, vergonha, ciúme, preocupação e pequenas contradições emocionais",
        "foco": [
            "alegria", "tristeza", "medo", "raiva", "frustração", "vergonha",
            "inveja", "ansiedade leve", "curiosidade", "coragem", "esperança", "gratidão",
        ],
        "mistura": "permitir duas emoções coexistindo quando a situação deixar isso compreensível pela ação e pelo contexto",
        "interioridade": "combinar expressão corporal, diálogo, pequenos pensamentos e consequência visível",
        "aprendizado": "a personagem percebe gradualmente o que sentiu, o que fez com isso e como poderia responder de modo mais sábio",
    },
    "6-8": {
        "complexidade": "emoções sociais e autoconscientes mais ricas, com comparação, pertencimento, medo de falhar, culpa por uma ação, orgulho, inveja, preocupação e insegurança",
        "foco": [
            "frustração", "vergonha", "timidez", "insegurança", "inveja", "ciúme",
            "ansiedade antecipatória leve", "culpa ligada ao comportamento", "orgulho saudável",
            "pertencimento", "alívio", "coragem", "esperança", "gratidão",
        ],
        "mistura": "usar emoções simultâneas de maneira clara — por exemplo, feliz pela amiga e decepcionada consigo; com medo e curiosa ao mesmo tempo",
        "interioridade": "usar pensamentos curtos, interpretação social, diálogos e sinais corporais sem transformar a história em análise psicológica",
        "aprendizado": "ligar emoção a escolhas e consequências; mostrar reparação, reconciliação, pedir ajuda, tentar novamente, contentamento, coragem ou mudança de perspectiva",
    },
    "9-12": {
        "complexidade": "emoções e sentimentos mais nuançados, ambivalentes e ligados a identidade, autoestima, autonomia, lealdade, comparação, pressão social, injustiça e antecipação",
        "foco": [
            "ansiedade antecipatória", "medo de julgamento", "exclusão", "solidão", "saudade",
            "luto/perda em abordagem segura", "ambivalência", "culpa", "responsabilidade",
            "orgulho", "inveja", "pertencimento", "lealdade", "esperança", "coragem", "paz",
        ],
        "mistura": "permitir sentimentos contraditórios e mudanças menos imediatas; a personagem pode não entender de primeira tudo o que sente",
        "interioridade": "pensamentos e motivações podem ser mais desenvolvidos, ainda com cenas concretas, diálogo e ação como motor principal",
        "aprendizado": "permitir que a transformação envolva responsabilidade, limites, perdão, aceitação, identidade, amizade, fé, propósito ou convivência com algo que não pode ser simplesmente desfeito",
    },
}


def perfil_emocional_etario(age_profile_id: str | None) -> dict:
    key = str(age_profile_id or "3-8").strip()
    if key not in AGE_EMOTIONAL_PROFILES:
        key = "3-8"
    return deepcopy({"id": key, **AGE_EMOTIONAL_PROFILES[key]})


def instrucao_experiencia_emocional(age_profile_id: str | None) -> str:
    """Retorna instrução de prompt compartilhada por Roteirista e Revisor."""
    p = perfil_emocional_etario(age_profile_id)
    principles = "\n- ".join(EMOTIONAL_EXPERIENCE_PRINCIPLES)
    focus = ", ".join(p["foco"])
    cycle = " -> ".join(EMOTIONAL_EXPERIENCE_CYCLE)
    return (
        "FAITHBLOOM EMOTIONAL EXPERIENCE ENGINE™:\n"
        f"Perfil emocional para {p['id']}: {p['complexidade']}.\n"
        f"Experiências possíveis (não obrigatórias): {focus}.\n"
        f"Emoções mistas: {p['mistura']}.\n"
        f"Interioridade: {p['interioridade']}.\n"
        f"Aprendizado emocional: {p['aprendizado']}.\n"
        f"Ciclo causal de referência: {cycle}.\n"
        "Princípios obrigatórios:\n- " + principles
    )

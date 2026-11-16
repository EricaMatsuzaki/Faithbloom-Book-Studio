"""FaithBloom Localization Excellence Layer.

Camada transversal para transformar tradução em edição localizada infantil.
Preserva o Master, o FaithBloom Heart Arc™, a faixa etária e o Bible Guard,
enquanto adapta naturalidade, humor, musicalidade, onomatopeias e convenções
culturais do mercado-alvo. Não substitui revisão humana nativa.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


HEART_ARC_LOCALIZATION = [
    "preservar o encantamento e a curiosidade que puxam a leitura",
    "preservar a emoção sentida, não apenas o sentido literal das frases",
    "manter causas, tentativas, consequências e vulnerabilidade do personagem",
    "manter a descoberta e a transformação como experiência vivida",
    "preservar a fé de modo natural, amoroso e não coercitivo",
    "preservar humor, recompensa emocional, gratidão e fechamento memorável",
]

CULTURAL_LOCALIZATION_GUARD = [
    "não transplantar automaticamente a história para o país de destino",
    "adaptar referências culturais somente quando a compreensão ou naturalidade realmente exigirem",
    "não inventar costumes, rituais, comidas, escola, família ou religião para parecer local",
    "não caricaturar sotaques, dialetos, costumes ou grupos sociais",
    "preservar fatos, cenário, relações, Character DNA e identidade da coleção",
    "quando houver adaptação cultural relevante, torná-la rastreável para revisão da autora",
]

TRANSCREATION_RULES = [
    "piadas e trocadilhos podem ser recriados funcionalmente quando a tradução literal perder o efeito",
    "refrões e repetições podem ser ajustados para recuperar ritmo e memorização sem copiar obras existentes",
    "onomatopeias devem ser localizadas pelo evento, intensidade, emoção e idade, não por tabela 1:1",
    "preservar intenção, personalidade e efeito emocional acima da ordem sintática do Master",
    "qualquer transcriação não deve mudar fatos centrais, moral, arco, nomes protegidos ou referência bíblica",
]

LOCALE_SPECIALISTS: dict[str, dict[str, Any]] = {
    "en-US": {
        "specialty": "US Children's Literature Localization",
        "guidance": "Use natural American child language, dialogue and read-aloud rhythm; avoid forced slang and adult marketing language.",
    },
    "en-GB": {
        "specialty": "UK Children's Literature Localization",
        "guidance": "Use natural British spelling and child vocabulary; preserve warmth and rhythm without inserting stereotyped slang.",
    },
    "en-CA": {
        "specialty": "Canadian Children's Literature Localization",
        "guidance": "Use natural Canadian conventions and child vocabulary rather than copying US or UK wording mechanically.",
    },
    "en-AU": {
        "specialty": "Australian Children's Literature Localization",
        "guidance": "Use natural Australian conventions while avoiding exaggerated local slang or stereotypes.",
    },
    "en-INT": {
        "specialty": "International English Children's Localization",
        "guidance": "Prefer globally understandable child language and minimize region-specific wording unless required by story context.",
    },
    "pt-BR": {
        "specialty": "Literatura Infantil Brasileira",
        "guidance": "Use português brasileiro infantil natural, oralidade apropriada à idade, musicalidade e diálogos que soem espontâneos.",
    },
    "pt-PT": {
        "specialty": "Literatura Infantil Portuguesa",
        "guidance": "Use português europeu natural para crianças, sem importar automaticamente escolhas do português brasileiro.",
    },
    "es-ES": {
        "specialty": "Literatura Infantil de España",
        "guidance": "Use español de España natural para niños, con diálogo y vocabulario adecuados a la edad, sin coloquialismos forzados.",
    },
    "es-MX": {
        "specialty": "Literatura Infantil de México",
        "guidance": "Use español mexicano infantil natural y comprensible, evitando exagerar regionalismos.",
    },
    "es-LATAM": {
        "specialty": "Literatura Infantil Latinoamericana Neutra",
        "guidance": "Prefer broadly understandable Latin American child language while preserving warmth, humor and oral rhythm.",
    },
    "fr-FR": {
        "specialty": "Littérature Jeunesse France",
        "guidance": "Use natural French child language, age-appropriate syntax and read-aloud musicality; avoid calques from the source language.",
    },
    "fr-CA": {
        "specialty": "Littérature Jeunesse Canada francophone",
        "guidance": "Use natural Canadian French suitable for children without caricaturing regional speech.",
    },
    "it-IT": {
        "specialty": "Letteratura per l'infanzia italiana",
        "guidance": "Use natural Italian child language, smooth dialogue and oral rhythm appropriate to the target age.",
    },
    "de-DE": {
        "specialty": "Deutschsprachige Kinderliteratur",
        "guidance": "Use natural German child language, age-appropriate sentence structure and idiomatic sound symbolism without literal calques.",
    },
    "ja-JP": {
        "specialty": "日本の児童文学・絵本ローカライゼーション",
        "guidance": "日本の子どもが自然に読める語彙・語順・会話・オノマトペを優先し、翻訳調を避ける。物語の舞台や文化を勝手に日本化しない。",
    },
}

JAPANESE_AGE_GUIDES = {
    "3-5": [
        "ひらがな中心。漢字は必要最小限にし、読字負荷を下げる",
        "短い文、繰り返し、呼びかけ、リズムを活かす",
        "擬音語・擬声語・擬態語を自然に使い、読み聞かせの楽しさを高める",
        "説明より動作・表情・音で理解できる文章を優先する",
    ],
    "3-8": [
        "読みやすいかな中心の文に、年齢相応の基本漢字を慎重に混ぜる",
        "読み聞かせと初期自読の両方で自然なテンポを保つ",
        "オノマトペは場面、感情、動きに合わせて機能的に使う",
    ],
    "6-8": [
        "初期読者として自然な漢字・かなバランスを使い、幼児向けに単純化しすぎない",
        "会話、因果関係、感情の変化を少し豊かにしつつ、文は明快に保つ",
        "擬音語・擬声語・擬態語を動き、ユーモア、感情、雰囲気に合わせて使う",
        "兄弟、友だち、先生、大人との話し方の違いを自然に反映する",
    ],
    "9-12": [
        "児童読み物として自然な漢字と語彙を使い、幼すぎる表現を避ける",
        "内面、関係性、ユーモアのニュアンスを保ちながら読みやすさを維持する",
        "オノマトペは幼児的に過剰使用せず、文体と人物の声に合わせる",
    ],
}

JAPANESE_MIMESIS_TAXONOMY = {
    "giongo": {
        "label": "擬音語",
        "purpose": "sons de fenômenos/objetos reais",
        "examples": ["コンコン", "ざあざあ", "ぽつぽつ"],
    },
    "giseigo": {
        "label": "擬声語",
        "purpose": "vozes e sons de seres vivos",
        "examples": ["わんわん", "にゃあにゃあ", "はくしょん"],
    },
    "gitaigo": {
        "label": "擬態語",
        "purpose": "estado, emoção, maneira ou movimento sem som literal",
        "examples": ["わくわく", "どきどき", "にこにこ", "くすくす", "そわそわ", "ふわふわ", "きらきら"],
    },
}


def _age_key(faixa_etaria: str) -> str:
    raw = str(faixa_etaria or "3-8").replace("–", "-").strip()
    for key in ("3-5", "6-8", "9-12", "3-8"):
        if key in raw:
            return key
    return "3-8"


def locale_specialist_profile(locale: str, faixa_etaria: str = "3–8") -> dict:
    loc = str(locale or "").strip()
    profile = deepcopy(LOCALE_SPECIALISTS.get(loc, {
        "specialty": "Children's Literature Localization",
        "guidance": "Use native, age-appropriate child language for the target locale and avoid literal calques.",
    }))
    profile["locale"] = loc
    profile["age_key"] = _age_key(faixa_etaria)
    profile["heart_arc"] = list(HEART_ARC_LOCALIZATION)
    profile["cultural_guard"] = list(CULTURAL_LOCALIZATION_GUARD)
    profile["transcreation_rules"] = list(TRANSCREATION_RULES)
    if loc == "ja-JP":
        profile["japanese_age_guide"] = list(JAPANESE_AGE_GUIDES[profile["age_key"]])
        profile["mimesis_taxonomy"] = deepcopy(JAPANESE_MIMESIS_TAXONOMY)
        profile["format_note"] = (
            "Para edição tipo 絵本 (ehon), trate ritmo, repetição, espaço de respiração, "
            "linguagem sonora e legibilidade como parte da experiência literária; não imite obra ou editora específica."
        )
    return profile


def localization_excellence_contract(locale: str, faixa_etaria: str = "3–8") -> str:
    p = locale_specialist_profile(locale, faixa_etaria)
    parts = [
        "\n=== FAITHBLOOM LOCALIZATION EXCELLENCE CONTRACT ===",
        f"Especialização local: {p['specialty']}.",
        f"Guia: {p['guidance']}",
        "HEART ARC NA LOCALIZAÇÃO: " + "; ".join(p["heart_arc"]) + ".",
        "CULTURAL GUARD: " + "; ".join(p["cultural_guard"]) + ".",
        "TRANSCREAÇÃO CONTROLADA: " + "; ".join(p["transcreation_rules"]) + ".",
        "A tradução deve soar como literatura infantil originalmente natural no locale, sem apagar a identidade do Master.",
        "Não trate correção gramatical como prova de naturalidade nativa; edição final importante exige revisão humana competente no locale.",
    ]
    if p["locale"] == "ja-JP":
        parts += [
            "JAPANESE EHON / CHILD-LANGUAGE SPECIALIST:",
            *[f"- {x}" for x in p["japanese_age_guide"]],
            "- Diferencie 擬音語 (giongo), 擬声語 (giseigo) e 擬態語 (gitaigo); escolha pelo efeito narrativo e contexto, nunca por tradução 1:1.",
            "- Preserve diferenças naturais de registro entre irmãos, amigos, professores, familiares e outros adultos.",
            "- Evite japonês gramaticalmente correto porém com cheiro de tradução; priorize cadência e escolhas lexicais naturais para crianças japonesas.",
            f"- {p['format_note']}",
        ]
    return "\n".join(parts) + "\n"


def native_child_language_review_prompt(locale: str, faixa_etaria: str = "3–8") -> str:
    p = locale_specialist_profile(locale, faixa_etaria)
    checks = [
        "naturalidade infantil real no mercado-alvo",
        "adequação da voz e do registro social dos personagens",
        "ritmo de leitura em voz alta e musicalidade",
        "humor, refrões, repetições e trocadilhos com efeito equivalente",
        "onomatopeias/miméticos naturais ao locale e proporcionais à idade",
        "preservação do Heart Arc e da transformação emocional/espiritual",
        "ausência de calques, estrangeirismos desnecessários e caricatura cultural",
        "preservação de nomes, fatos, Character DNA, moral e referência bíblica",
    ]
    if p["locale"] == "ja-JP":
        checks += [
            "equilíbrio kanji/kana apropriado à faixa",
            "uso natural de 擬音語・擬声語・擬態語",
            "texto com cadência de literatura infantil japonesa, não tradução mecânica",
        ]
    return (
        f"Você é um Native Child-Language Reviewer independente para {p['locale']} ({p['specialty']}).\n"
        f"Faixa etária: {faixa_etaria}.\n"
        "Avalie criticamente: " + "; ".join(checks) + ".\n"
        "Não reescreva silenciosamente; reporte problemas localizados e sugestões. "
        "Não traduza nem complete texto bíblico."
    )

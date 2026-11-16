"""FaithBloom — histórias inspiradas em experiências reais.

Esta camada trata a ORIGEM da história, não o estilo narrativo. Depois de
preparado, o mesmo relato pode seguir para Aventura, Poético/Rimado, Fábula,
Misto, Versão do Roteirista, estilos adicionais ou IA externa.

Objetivos editoriais:
- preservar o coração emocional de experiências verdadeiras;
- distinguir fatos fornecidos de dramatização literária;
- proteger dignidade, privacidade e consentimento;
- nunca inventar trauma/sensibilidade para tornar a história mais dramática;
- permitir ficcionalização responsável de nomes e detalhes identificáveis;
- manter Heart Arc™ e Emotional Experience Engine™ sem transformar memória em sermão.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

REAL_EXPERIENCE_CATEGORY_ID = "inspirada_em_experiencia_real"
REAL_EXPERIENCE_CATEGORY_LABEL = "🌿 Inspirada em uma experiência real"

FIDELITY_FAITHFUL = "fiel_aos_fatos"
FIDELITY_INSPIRED = "inspiracao_literaria"
FIDELITY_MODES = {
    FIDELITY_FAITHFUL: "📜 Fiel aos fatos principais",
    FIDELITY_INSPIRED: "✨ Inspirada livremente na experiência",
}

PRIVACY_FICTIONALIZE = "ficcionalizar_identificadores"
PRIVACY_AUTHORIZED_NAMES = "nomes_reais_autorizados"
PRIVACY_MODES = {
    PRIVACY_FICTIONALIZE: "🛡️ Ficcionalizar nomes e detalhes identificáveis — recomendado",
    PRIVACY_AUTHORIZED_NAMES: "✅ Manter nomes reais autorizados",
}

RELATION_OPTIONS = {
    "propria": "Minha própria história",
    "menor_responsavel": "Filho(a)/menor sob minha responsabilidade",
    "adulto_autorizado": "Familiar/adulto com autorização",
    "outra_pessoa_autorizada": "Outra pessoa com autorização",
    "composta_anonima": "História composta/anônima baseada em experiências reais",
}

REAL_EXPERIENCE_PRINCIPLES = [
    "preserve os fatos centrais explicitamente fornecidos; não invente acontecimentos reais ausentes",
    "não atribua fala inventada como citação literal; diálogos dramatizados devem funcionar como reconstrução literária",
    "não acrescente doença, diagnóstico, abuso, crime, morte, violência, abandono, trauma ou outro evento sensível que não tenha sido fornecido",
    "não intensifique sofrimento apenas para criar impacto dramático",
    "preserve dignidade: não humilhe, ridicularize nem transforme uma pessoa real em vilão simplista",
    "emoções podem ser inferidas literariamente somente quando coerentes com os fatos e sem apresentá-las como diagnóstico ou certeza histórica",
    "a transformação precisa nascer da experiência vivida e das escolhas, não de uma moral colocada artificialmente sobre a memória",
    "fé pode oferecer consolo, coragem, sentido, gratidão ou esperança sem negar tristeza, medo, perda, frustração ou ambivalência",
    "quando houver terceiros, minimize dados identificáveis e detalhes privados que não sejam necessários à história",
    "quando houver menores, prefira ficcionalização de identificadores salvo decisão autoral consciente e autorização adequada",
    "preserve o Heart Arc™ e o Emotional Experience Engine™ sem copiar a estrutura distintiva de obras de terceiros",
]


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_real_experience_brief(
    account: str,
    *,
    fidelity_mode: str = FIDELITY_FAITHFUL,
    privacy_mode: str = PRIVACY_FICTIONALIZE,
    relation: str = "propria",
    consent_confirmed: bool = False,
) -> str:
    """Transforma um relato autoral em briefing seguro para todos os Roteiristas."""
    account = _text(account)
    if not account:
        raise ValueError("Conte a experiência real antes de preparar esta categoria.")
    if not consent_confirmed:
        raise ValueError(
            "Confirme que você tem direito/consentimento adequado para usar este relato antes de continuar."
        )
    if fidelity_mode not in FIDELITY_MODES:
        fidelity_mode = FIDELITY_FAITHFUL
    if privacy_mode not in PRIVACY_MODES:
        privacy_mode = PRIVACY_FICTIONALIZE
    if relation not in RELATION_OPTIONS:
        relation = "propria"

    if fidelity_mode == FIDELITY_FAITHFUL:
        fidelity_instruction = (
            "Mantenha cronologia, relações, acontecimentos e desfecho principais fiéis ao relato. "
            "Pode melhorar ritmo, seleção de cenas, transições e linguagem, mas não mude o que aconteceu."
        )
    else:
        fidelity_instruction = (
            "Use a experiência como semente emocional e factual. Pode condensar tempo, trocar cenário não essencial, "
            "criar personagem ficcional composto e reorganizar momentos para qualidade literária, mas nunca atribua "
            "a uma pessoa real fatos sensíveis inventados nem apresente dramatização como registro histórico literal."
        )

    if privacy_mode == PRIVACY_FICTIONALIZE:
        privacy_instruction = (
            "Ficcionalize nomes, escola/empresa, endereço, datas exatas e outros identificadores quando não forem essenciais. "
            "Preserve o significado emocional e os fatos centrais sem expor desnecessariamente pessoas reais."
        )
    else:
        privacy_instruction = (
            "Nomes reais foram marcados como autorizados pela autora. Mesmo assim, não acrescente dados privados, "
            "identificadores desnecessários ou fatos sensíveis ausentes do relato."
        )

    principles = "\n- ".join(REAL_EXPERIENCE_PRINCIPLES)
    return f"""CATEGORIA FAITHBLOOM: {REAL_EXPERIENCE_CATEGORY_LABEL}
Esta é uma origem narrativa baseada em vida real; NÃO é um estilo narrativo.

RELAÇÃO COM A EXPERIÊNCIA: {RELATION_OPTIONS[relation]}
FIDELIDADE: {FIDELITY_MODES[fidelity_mode]}
PRIVACIDADE: {PRIVACY_MODES[privacy_mode]}

RELATO FORNECIDO PELA AUTORA:
{account}

CONTRATO DE ADAPTAÇÃO:
{fidelity_instruction}
{privacy_instruction}

PRINCÍPIOS OBRIGATÓRIOS:
- {principles}

OBJETIVO:
Transforme a experiência em literatura infantil emocionalmente verdadeira, visual, adequada à idade e prazerosa de ler. Mostre acontecimentos, reações, escolhas, consequências, descobertas e transformação. Não reduza a experiência a uma lição pronta. A moral e a fé devem emergir organicamente do que foi vivido.
""".strip()


def apply_real_experience_to_state(
    state: dict,
    *,
    account: str,
    fidelity_mode: str = FIDELITY_FAITHFUL,
    privacy_mode: str = PRIVACY_FICTIONALIZE,
    relation: str = "propria",
    consent_confirmed: bool = False,
) -> dict:
    """Registra a categoria no projeto e prepara o briefing para o pipeline existente."""
    brief = build_real_experience_brief(
        account,
        fidelity_mode=fidelity_mode,
        privacy_mode=privacy_mode,
        relation=relation,
        consent_confirmed=consent_confirmed,
    )
    new_state = deepcopy(state or {})
    new_state["story_category"] = REAL_EXPERIENCE_CATEGORY_ID
    new_state["story_category_label"] = REAL_EXPERIENCE_CATEGORY_LABEL
    new_state["real_experience"] = {
        "schema": "faithbloom.real-experience.v1",
        "relation": relation,
        "relation_label": RELATION_OPTIONS.get(relation, RELATION_OPTIONS["propria"]),
        "fidelity_mode": fidelity_mode,
        "fidelity_label": FIDELITY_MODES.get(fidelity_mode, FIDELITY_MODES[FIDELITY_FAITHFUL]),
        "privacy_mode": privacy_mode,
        "privacy_label": PRIVACY_MODES.get(privacy_mode, PRIVACY_MODES[PRIVACY_FICTIONALIZE]),
        "consent_confirmed": True,
        "original_account": _text(account),
    }
    # O pipeline atual usa este campo como premissa. Colocamos o contrato junto
    # do relato para que Curador, Roteiristas e IA externa recebam as mesmas regras.
    new_state["_entrada_tema_livre"] = brief
    new_state["origem_ideia"] = "projeto"
    new_state["revisao_aprovada"] = False
    new_state["pacote_pronto"] = False
    return new_state


def is_real_experience_story(state: dict | None) -> bool:
    return bool((state or {}).get("story_category") == REAL_EXPERIENCE_CATEGORY_ID)

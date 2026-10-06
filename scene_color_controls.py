"""Controles e prompts seguros para cena, cor, luz e edicao localizada."""
from __future__ import annotations

PROTECTED_TRAITS = (
    "identidade", "especie", "formato do rosto", "olhos", "pelagem/cabelo",
    "proporcoes", "marcas permanentes", "acessorios permanentes", "Style DNA",
)
SCENE_PRESETS = ("Primavera", "Inverno", "Natal", "Escola", "Quarto", "Parque", "Igreja", "Floresta", "Noite", "Fundo neutro", "Fundo transparente")
COLOR_TREATMENTS = ("Manter original", "Correcao natural", "Pastel suave", "Quente e acolhedor", "Mais luminoso", "Mais vibrante", "Editorial infantil", "Harmonizar com colecao", "Emotional Color Director", "Personalizado")
LIGHTING = ("Manter original", "Natural suave", "Golden hour", "Editorial", "Clara e alegre", "Aconchegante", "Noturna suave", "Natalina", "Difusa de estudio")


def identity_lock(character_dna: dict | None = None) -> dict:
    dna = character_dna or {}
    fields = dict(dna.get("campos_bloqueados") or {})
    return {
        "enabled": True,
        "protected": list(PROTECTED_TRAITS),
        "canonical_values": fields,
        "visual_prompt_master": str(dna.get("visual_prompt_master") or "").strip(),
        "variable_rules": dict(dna.get("regras_variaveis") or {}),
    }


def build_restoration_prompt(action: str, *, dna: dict | None = None, request: str = "", scene: str = "", color: str = "Manter original", lighting: str = "Manter original") -> str:
    lock = identity_lock(dna)
    canonical = lock["canonical_values"]
    allowed = {
        "neutral_master": (
            "Prepare uma candidata a Color Master de alta qualidade usando a PRIMEIRA imagem como base. "
            "Preserve a mesma personagem, rosto, olhos, expressão, pose, proporções e acessórios identitários permanentes, incluindo qualquer laço permanente definido no DNA. "
            "Use fundo neutro branco ou creme claro uniforme, sem cenário ou objetos. "
            "Remova acessórios sazonais, incluindo cachecol; preserve acessórios permanentes do DNA. "
            "Melhore nitidez e acabamento sem mudar a identidade. Não oficialize a candidata."
        ),
        "light": "Melhore apenas nitidez, limpeza, pequenos artefatos, resolucao e exposicao leve; nao redesenhe.",
        "controlled_remaster": "Melhore acabamento editorial e somente os elementos autorizados.",
        "dna_reconstruction": "Reconstrua a partir das referencias e DNA; a saida e apenas MASTER_CANDIDATE.",
        "improve_scene": "Preserve o personagem e o conceito do cenario; melhore acabamento, composicao, profundidade, luz e harmonia.",
        "replace_scene": f"Preserve o personagem e troque somente o cenario por: {scene or request}.",
        "modify_only": f"MODIFICAR SOMENTE ISTO: {request}. Preserve tudo que nao foi solicitado: personagem, rosto, olhos, pose, expressao, enquadramento, cenario restante, composicao, iluminacao se nao solicitada e cores se nao solicitadas.",
        "line_art": "Crie LINE ART CANDIDATE a partir do Color Master; nao promova automaticamente.",
    }
    if action not in allowed:
        raise ValueError("Acao visual invalida.")
    from character_guide import artwork_text_policy
    visual_master = lock.get("visual_prompt_master") or ""
    visual_master_block = (
        f" PROMPT MESTRE VISUAL OFICIAL DO PERSONAGEM: {visual_master}"
        if visual_master else ""
    )
    variable_rules = lock.get("variable_rules") or {}
    variable_rules_block = (
        f" REGRAS DE VARIÁVEIS CONTEXTUAIS: {variable_rules}."
        if variable_rules else ""
    )
    return (
        f"{allowed[action]} IDENTITY LOCK ATIVO. Preserve: {', '.join(lock['protected'])}. "
        f"Valores canonicos que jamais podem receber recoloracao: {canonical}. "
        f"Tratamento de cor: {color}; aplique apenas em luz, atmosfera, fundo e elementos secundarios. "
        f"Iluminacao: {lighting}. Pedido adicional: {request or 'nenhum'}. "
        "Nao altere traits canonicos mesmo que a direcao cromatica sugira outra cor. "
        "Exceção à mudança somente de cenário: alterações adicionais explicitamente pedidas em acessórios temporários ou em variáveis contextuais autorizadas pelo DNA são permitidas. "
        + visual_master_block
        + variable_rules_block
        + " "
        + artwork_text_policy()
    )

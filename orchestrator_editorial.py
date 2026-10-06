"""FaithBloom Orchestrator — generic editorial routing without duplicating specialist studios.

This module is intentionally provider-neutral. It defines project intent, origin,
audience/editorial line and maps them to capabilities that already exist in the
FaithBloom repository. New project types should extend this registry instead of
creating parallel translation, publishing, character, QA or cost pipelines.
"""
from __future__ import annotations

from copy import deepcopy

SCHEMA = "faithbloom.orchestrator-editorial.v1"

PROJECT_TYPES = {
    "children_story": {"label": "📖 História Infantil", "visual": True, "narrative": True},
    "real_life_story": {"label": "🌿 História Inspirada na Vida Real", "visual": True, "narrative": True},
    "children_advice": {"label": "🧒 Conselhos para Crianças", "visual": False, "narrative": False},
    "teen_advice": {"label": "🧑‍🎓 Conselhos para Adolescentes", "visual": False, "narrative": False},
    "children_devotional": {"label": "🙏 Devocional Infantil", "visual": False, "narrative": False},
    "teen_devotional": {"label": "🙏 Devocional para Adolescentes", "visual": False, "narrative": False},
    "personal_development": {"label": "🌱 Desenvolvimento Pessoal / Educativo", "visual": False, "narrative": False},
    "study_book": {"label": "📚 Livro de Estudos / Apostila", "visual": False, "narrative": False},
    "exam_prep": {"label": "🎓 Preparatório para Provas e Certificações", "visual": False, "narrative": False},
    "workbook": {"label": "✍️ Workbook / Caderno de Exercícios", "visual": False, "narrative": False},
    "study_guide": {"label": "🧠 Guia de Estudos", "visual": False, "narrative": False},
    "flashcards": {"label": "🃏 Flashcards / Material de Memorização", "visual": False, "narrative": False},
    "activity_book": {"label": "🧩 Livro de Atividades", "visual": True, "narrative": False},
    "coloring_book": {"label": "🖍️ Livro de Colorir / Line Art", "visual": True, "narrative": False},
    "comic": {"label": "🗯️ HQ / História em Quadrinhos", "visual": True, "narrative": True},
    "other": {"label": "✨ Outro tipo de projeto", "visual": False, "narrative": False},
}

ORIGINS = {
    "bible": "📖 Bíblia / versículo",
    "inspiring_work": "🎬 Filme / obra inspiradora",
    "real_experience": "❤️ Experiência real",
    "own_idea": "💡 Ideia própria",
    "image": "🖼️ Imagem",
    "document": "📎 PDF / documento",
    "own_text": "✍️ Texto seu",
    "theme": "🎯 Tema / lição",
    "emotion": "😊 Emoção",
    "ai_suggestion": "🤖 Sugestão da IA",
}

EDITORIAL_LINES = {
    "christian": "✝️ Cristã",
    "universal_educational": "🌱 Valores universais / educativa",
    "custom": "✨ Outra linha configurada",
}

AUDIENCES = {
    "3_5": "3–5 anos",
    "3_8": "3–8 anos",
    "6_8": "6–8 anos",
    "9_12": "9–12 anos",
    "teen": "Adolescentes",
    "adult": "Adultos",
    "custom": "Outro / personalizado",
}

# Canonical capabilities already present in FaithBloom. The orchestrator routes to
# these; it must not reimplement them under a new name.
CAPABILITIES = {
    "storyteller": {"status": "existing", "kind": "editorial_skill"},
    "heart_arc": {"status": "existing", "kind": "editorial_skill"},
    "emotional_experience_engine": {"status": "existing", "kind": "editorial_skill"},
    "bible_guard": {"status": "existing", "kind": "guardian"},
    "originality_guard": {"status": "existing", "kind": "guardian"},
    "character_universe": {"status": "existing", "kind": "master_registry"},
    "world_masters": {"status": "existing", "kind": "master_registry"},
    "visual_preflight": {"status": "existing", "kind": "orchestration"},
    "translation_localization": {"status": "existing", "kind": "studio"},
    "publishing_platform_engine": {"status": "existing", "kind": "engine"},
    "publishing_distribution_center": {"status": "existing", "kind": "center"},
    "activity_book_studio": {"status": "existing", "kind": "studio"},
    "coloring_book_studio": {"status": "existing", "kind": "studio"},
    "audiobook_studio": {"status": "existing", "kind": "derived_output"},
    "quality_guardian": {"status": "existing", "kind": "guardian"},
    "cost_gate": {"status": "existing", "kind": "guardrail"},
    "asset_library": {"status": "existing", "kind": "storage"},
    "idea_vault": {"status": "foundation_ready", "kind": "creative_studio"},
    "animation_video": {"status": "provider_integration_pending", "kind": "creative_studio"},
    "music": {"status": "provider_integration_pending", "kind": "creative_studio"},
}

BASE_ROUTE = ["quality_guardian", "translation_localization", "publishing_platform_engine", "publishing_distribution_center"]

TYPE_ROUTES = {
    "children_story": ["storyteller", "heart_arc", "emotional_experience_engine", "originality_guard", "character_universe", "world_masters", "visual_preflight"],
    "real_life_story": ["storyteller", "heart_arc", "emotional_experience_engine", "originality_guard", "character_universe", "world_masters", "visual_preflight"],
    "children_advice": ["originality_guard"],
    "teen_advice": ["originality_guard"],
    "children_devotional": ["bible_guard", "originality_guard"],
    "teen_devotional": ["bible_guard", "originality_guard"],
    "personal_development": ["originality_guard"],
    "study_book": ["originality_guard"],
    "exam_prep": ["originality_guard"],
    "workbook": ["originality_guard"],
    "study_guide": ["originality_guard"],
    "flashcards": ["originality_guard"],
    "activity_book": ["activity_book_studio", "originality_guard"],
    "coloring_book": ["coloring_book_studio", "originality_guard"],
    "comic": ["storyteller", "heart_arc", "emotional_experience_engine", "originality_guard", "character_universe", "world_masters", "visual_preflight"],
    "other": ["originality_guard"],
}

DERIVED_OUTPUTS = {
    "audiobook": ["audiobook_studio"],
    "animation": ["animation_video"],
    "music": ["music"],
}


def list_project_types() -> list[tuple[str, str]]:
    return [(key, data["label"]) for key, data in PROJECT_TYPES.items()]


def get_capability(capability_id: str) -> dict:
    if capability_id not in CAPABILITIES:
        raise KeyError(f"Unknown FaithBloom capability: {capability_id}")
    return deepcopy(CAPABILITIES[capability_id])


def build_editorial_route(
    project_type: str,
    *,
    origin: str = "own_idea",
    audience: str = "3_8",
    editorial_line: str = "christian",
    derived_outputs: list[str] | None = None,
) -> dict:
    """Build a routing plan that reuses existing capabilities.

    The returned route contains each capability at most once. Bible Guard is added
    when the project is Christian or explicitly originates from a Bible reference.
    Translation and distribution are shared terminal capabilities rather than
    per-project copies.
    """
    if project_type not in PROJECT_TYPES:
        raise KeyError(f"Unknown project type: {project_type}")
    if origin not in ORIGINS:
        raise KeyError(f"Unknown origin: {origin}")
    if audience not in AUDIENCES:
        raise KeyError(f"Unknown audience: {audience}")
    if editorial_line not in EDITORIAL_LINES:
        raise KeyError(f"Unknown editorial line: {editorial_line}")

    route: list[str] = []

    def add(capability_id: str) -> None:
        if capability_id not in CAPABILITIES:
            raise KeyError(f"Capability is not registered: {capability_id}")
        if capability_id not in route:
            route.append(capability_id)

    for capability_id in TYPE_ROUTES[project_type]:
        add(capability_id)

    if origin == "bible" or editorial_line == "christian":
        add("bible_guard")

    for output in derived_outputs or []:
        if output not in DERIVED_OUTPUTS:
            raise KeyError(f"Unknown derived output: {output}")
        for capability_id in DERIVED_OUTPUTS[output]:
            add(capability_id)

    for capability_id in BASE_ROUTE:
        add(capability_id)

    return {
        "schema": SCHEMA,
        "project_type": project_type,
        "project_label": PROJECT_TYPES[project_type]["label"],
        "origin": origin,
        "origin_label": ORIGINS[origin],
        "audience": audience,
        "audience_label": AUDIENCES[audience],
        "editorial_line": editorial_line,
        "editorial_line_label": EDITORIAL_LINES[editorial_line],
        "route": route,
        "capabilities": {capability_id: get_capability(capability_id) for capability_id in route},
        "reuse_policy": "reuse_existing_before_extend_before_create",
        "duplicate_capabilities": len(route) != len(set(route)),
        "auto_publish": False,
        "requires_human_approval": True,
    }


def anti_duplication_report(route_plan: dict) -> dict:
    route = list(route_plan.get("route") or [])
    duplicates = sorted({item for item in route if route.count(item) > 1})
    unknown = sorted({item for item in route if item not in CAPABILITIES})
    return {
        "ok": not duplicates and not unknown,
        "duplicates": duplicates,
        "unknown": unknown,
        "policy": "verify -> reuse -> extend -> create only if absent",
    }

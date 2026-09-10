"""FaithBloom Jarvis — MVP conversational layer over the existing orchestrator.

Jarvis does not duplicate specialist studios. It interprets a simple author request,
builds a generic editorial route and reports what should happen next. High-impact
actions remain behind human approval.
"""
from __future__ import annotations

import re
from copy import deepcopy

from orchestrator_editorial import build_editorial_route, anti_duplication_report

SCHEMA = "faithbloom.jarvis.v1"

AUTONOMY_MODES = {
    "assistant": "Assistente",
    "copilot": "Copiloto",
    "manager": "Gerente",
}

PROJECT_HINTS = [
    ("coloring_book", ("colorir", "pintar", "line art")),
    ("activity_book", ("atividade", "atividades", "labirinto", "caça-palavras")),
    ("comic", ("hq", "quadrinho", "quadrinhos", "gibi")),
    ("flashcards", ("flashcard", "flashcards", "memorização")),
    ("study_book", ("apostila", "livro de estudos", "material de estudo")),
    ("study_guide", ("guia de estudos", "plano de estudos")),
    ("workbook", ("workbook", "caderno de exercícios")),
    ("exam_prep", ("prova", "certificação", "preparatório", "jlpt", "eiken", "ielts")),
    ("teen_devotional", ("devocional adolescente", "devocional para adolescente")),
    ("children_devotional", ("devocional infantil", "devocional para criança")),
    ("teen_advice", ("conselhos para adolescente", "conselho para adolescente")),
    ("children_advice", ("conselhos para criança", "conselho para criança")),
    ("real_life_story", ("história real", "vida real", "experiência real")),
    ("children_story", ("história infantil", "livro infantil", "história para criança", "história")),
]

# Canonical existing pages. Jarvis only points to them; it does not clone their logic.
PROJECT_START_PAGES = {
    "children_story": "pages/39_✍️_Historia_4_Estilos.py",
    "real_life_story": "pages/42_🌿_Historias_Inspiradas_na_Vida_Real.py",
    "activity_book": "pages/23_🧩_Activity_Book_Studio.py",
    "coloring_book": "pages/3_🖍️_Livros_de_Colorir.py",
    "comic": "pages/40_➕_Explorar_outros_estilos.py",
}
DEFAULT_START_PAGE = "pages/0_🤖_Orquestrador_FaithBloom.py"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


def infer_project_type(text: str) -> str:
    value = _norm(text)
    for project_type, hints in PROJECT_HINTS:
        if any(hint in value for hint in hints):
            return project_type
    return "children_story"


def infer_origin(text: str) -> str:
    value = _norm(text)
    if any(x in value for x in ("versículo", "versiculo", "bíblia", "biblia", "salmo", "provérbios", "proverbios", "filipenses", "lucas", "joão", "joao")):
        return "bible"
    if any(x in value for x in ("minha vida", "aconteceu comigo", "experiência real", "história real")):
        return "real_experience"
    if any(x in value for x in ("pdf", "documento", "arquivo")):
        return "document"
    if any(x in value for x in ("imagem", "foto", "ilustração")):
        return "image"
    if any(x in value for x in ("filme", "obra", "livro que gostei")):
        return "inspiring_work"
    return "own_idea"


def infer_audience(text: str) -> str:
    value = _norm(text)
    if any(x in value for x in ("adolescente", "teen", "15 anos", "16 anos", "17 anos")):
        return "teen"
    if any(x in value for x in ("adulto", "adultos")):
        return "adult"
    if any(x in value for x in ("9 a 12", "9–12", "10 anos", "11 anos", "12 anos")):
        return "9_12"
    if any(x in value for x in ("3 a 5", "3–5")):
        return "3_5"
    return "3_8"


def infer_editorial_line(text: str) -> str:
    value = _norm(text)
    if any(x in value for x in ("bíblia", "biblia", "versículo", "versiculo", "deus", "jesus", "cristã", "cristão", "devocional")):
        return "christian"
    return "universal_educational"


def infer_derived_outputs(text: str) -> list[str]:
    """Infer explicit derived outputs only.

    A protected/inspiring work mentioned as an origin (for example, "inspirado em
    um filme") must not silently become a request to produce a film. Video output
    therefore requires an explicit production verb/format signal.
    """
    value = _norm(text)
    outputs = []
    if any(x in value for x in ("audiobook", "áudio livro", "audio livro", "narração")):
        outputs.append("audiobook")
    if any(x in value for x in ("animação", "animacao", "desenho animado", "vídeo", "video")) or re.search(r"\b(faça|fazer|produza|produzir|crie|criar)\s+(um\s+)?filme\b", value):
        outputs.append("animation")
    if any(x in value for x in ("música", "musica", "canção", "cancao", "trilha sonora")):
        outputs.append("music")
    return outputs


def next_page_for_project(project_type: str) -> str:
    """Return an existing FaithBloom page instead of creating parallel flows."""
    return PROJECT_START_PAGES.get(project_type, DEFAULT_START_PAGE)


def interpret_request(text: str) -> dict:
    """Turn one author sentence into an explicit, inspectable routing proposal."""
    if not (text or "").strip():
        raise ValueError("Conte sua ideia em uma frase para o Jarvis.")
    project_type = infer_project_type(text)
    origin = infer_origin(text)
    audience = infer_audience(text)
    editorial_line = "christian" if origin == "bible" else infer_editorial_line(text)
    derived_outputs = infer_derived_outputs(text)
    route = build_editorial_route(
        project_type,
        origin=origin,
        audience=audience,
        editorial_line=editorial_line,
        derived_outputs=derived_outputs,
    )
    audit = anti_duplication_report(route)
    return {
        "schema": SCHEMA,
        "request": text.strip(),
        "project_type": project_type,
        "origin": origin,
        "audience": audience,
        "editorial_line": editorial_line,
        "derived_outputs": derived_outputs,
        "route_plan": route,
        "anti_duplication": audit,
        "requires_author_approval": True,
        "next_action": "review_and_approve_route",
        "next_page": next_page_for_project(project_type),
    }


def build_status_cards(result: dict) -> list[dict]:
    plan = result.get("route_plan") or {}
    return [
        {"label": "Projeto", "value": plan.get("project_label", "—")},
        {"label": "Origem", "value": plan.get("origin_label", "—")},
        {"label": "Público", "value": plan.get("audience_label", "—")},
        {"label": "Linha editorial", "value": plan.get("editorial_line_label", "—")},
    ]


def safe_summary(result: dict) -> dict:
    """Small serializable summary suitable for session state or future persistence."""
    return deepcopy({
        "schema": result.get("schema"),
        "request": result.get("request"),
        "project_type": result.get("project_type"),
        "origin": result.get("origin"),
        "audience": result.get("audience"),
        "editorial_line": result.get("editorial_line"),
        "derived_outputs": result.get("derived_outputs", []),
        "next_action": result.get("next_action"),
        "next_page": result.get("next_page"),
    })

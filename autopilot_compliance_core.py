"""FaithBloom Autopilot Compliance Core.

Camada determinística que transforma regras editoriais já programadas em gates
obrigatórios do Autopilot. O objetivo é impedir que uma etapa de IA seja marcada
como concluída apenas porque citou Heart Arc/Prompt-Mestre: a estrutura canônica
precisa sobreviver e cada fase do Heart Arc precisa estar mapeada para cenas reais.
"""
from __future__ import annotations

from copy import deepcopy
import unicodedata

HEART_ARC_STAGES = (
    "encantamento",
    "emoção",
    "experiência",
    "descoberta",
    "transformação",
    "fé",
)


def _norm(value: object) -> str:
    text = str(value or "").strip().casefold()
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _scene_number(scene: dict, fallback: int) -> int:
    try:
        return int(scene.get("numero") or fallback)
    except (TypeError, ValueError):
        return fallback


def _origin_number(scene: dict, fallback: int) -> int | None:
    raw = scene.get("numero_origem")
    if raw in (None, ""):
        raw = scene.get("numero")
    try:
        return int(raw) if raw not in (None, "") else fallback
    except (TypeError, ValueError):
        return None


def canonical_scenes_from_state(state: dict) -> list[dict]:
    """Retorna a estrutura anterior ao primeiro enriquecimento aplicado.

    O histórico do Storyteller registra BEFORE/AFTER; o primeiro BEFORE é a
    melhor fonte determinística para a estrutura que entrou no enriquecimento.
    """
    for record in state.get("historico_storyteller") or []:
        before = record.get("antes") if isinstance(record, dict) else None
        if isinstance(before, list) and before:
            return deepcopy([x for x in before if isinstance(x, dict)])
    return deepcopy([x for x in (state.get("cenas_texto") or []) if isinstance(x, dict)])


def validate_canonical_structure(canonical: list[dict], candidate: list[dict]) -> dict:
    canonical = [x for x in (canonical or []) if isinstance(x, dict)]
    candidate = [x for x in (candidate or []) if isinstance(x, dict)]
    expected = [_scene_number(scene, i) for i, scene in enumerate(canonical, 1)]
    candidate_origins = [_origin_number(scene, i) for i, scene in enumerate(candidate, 1)]
    filtered = [x for x in candidate_origins if x in expected]
    missing = [x for x in expected if x not in filtered]
    duplicates = sorted({x for x in filtered if filtered.count(x) > 1})
    order_preserved = filtered == expected
    reduced = len(candidate) < len(canonical)
    ok = bool(canonical) and not missing and not duplicates and order_preserved and not reduced
    return {
        "ok": ok,
        "canonical_count": len(canonical),
        "candidate_count": len(candidate),
        "missing_canonical_scenes": missing,
        "duplicated_canonical_origins": duplicates,
        "canonical_order_preserved": order_preserved,
        "scene_count_reduced": reduced,
        "coverage_percent": round(100 * (len(expected) - len(missing)) / len(expected), 1) if expected else 0.0,
    }


def validate_heart_arc_scene_map(heart_arc_scene_map: object, candidate: list[dict]) -> dict:
    candidate = [x for x in (candidate or []) if isinstance(x, dict)]
    valid_scene_numbers = {_scene_number(scene, i) for i, scene in enumerate(candidate, 1)}
    raw = heart_arc_scene_map if isinstance(heart_arc_scene_map, dict) else {}
    normalized = {_norm(k): v for k, v in raw.items()}
    stage_rows = {}
    missing_stages = []
    invalid_refs = []
    used = []

    for stage in HEART_ARC_STAGES:
        key = _norm(stage)
        value = normalized.get(key)
        refs = value if isinstance(value, list) else [value] if value not in (None, "") else []
        clean = []
        for ref in refs:
            try:
                number = int(ref)
            except (TypeError, ValueError):
                continue
            if number in valid_scene_numbers and number not in clean:
                clean.append(number)
            elif number not in valid_scene_numbers:
                invalid_refs.append({"stage": stage, "scene": number})
        if not clean:
            missing_stages.append(stage)
        stage_rows[stage] = clean
        used.extend(clean)

    distinct = sorted(set(used))
    discovery = set(stage_rows.get("descoberta") or [])
    transformation = set(stage_rows.get("transformação") or [])
    faith = set(stage_rows.get("fé") or [])
    late_arc_not_flattened = len(discovery | transformation | faith) >= 2
    minimum_breathing_room = len(distinct) >= min(4, len(valid_scene_numbers)) if valid_scene_numbers else False
    ok = not missing_stages and not invalid_refs and late_arc_not_flattened and minimum_breathing_room
    return {
        "ok": ok,
        "stages": stage_rows,
        "missing_stages": missing_stages,
        "invalid_scene_references": invalid_refs,
        "distinct_scenes_used": distinct,
        "late_arc_not_flattened": late_arc_not_flattened,
        "minimum_breathing_room": minimum_breathing_room,
    }


def validate_storyteller_candidate(
    canonical: list[dict],
    candidate: list[dict],
    heart_arc_scene_map: object,
) -> dict:
    structure = validate_canonical_structure(canonical, candidate)
    heart_arc = validate_heart_arc_scene_map(heart_arc_scene_map, candidate)
    return {
        "ok": bool(structure.get("ok") and heart_arc.get("ok")),
        "canonical_structure": structure,
        "heart_arc_execution": heart_arc,
    }


def evaluate_autopilot_compliance(state: dict) -> dict:
    """Matriz final de compliance editorial do Autopilot.

    Falha fechada: se uma regra obrigatória não puder ser provada, não libera o
    handoff visual/final. Isso evita o falso positivo de "tudo verde".
    """
    current = [deepcopy(x) for x in (state.get("cenas_texto") or []) if isinstance(x, dict)]
    canonical = canonical_scenes_from_state(state)
    history = [x for x in (state.get("historico_storyteller") or []) if isinstance(x, dict)]
    latest_analysis = deepcopy((history[-1].get("analise") or {})) if history else {}
    heart_map = latest_analysis.get("heart_arc_scene_map") or state.get("heart_arc_scene_map") or {}

    structure = validate_canonical_structure(canonical, current)
    heart_arc = validate_heart_arc_scene_map(heart_map, current)
    prompt_master = bool((state.get("prompt_master_compliance_remaster") or {}).get("ok_para_finalizar"))
    moral = bool(str(state.get("licao_final") or "").strip())
    bible = bool(str(state.get("versiculo_referencia") or "").strip())
    emotional_map = [x for x in (state.get("mapa_emocional") or []) if isinstance(x, dict)]
    emotional_ok = bool(state.get("metadata_emocional_confirmada") and len(emotional_map) == len(current) and current)

    checks = {
        "canonical_story_lock": structure,
        "heart_arc_execution_gate": heart_arc,
        "prompt_master_gate": {"ok": prompt_master},
        "moral_gate": {"ok": moral},
        "bible_reference_gate": {"ok": bible},
        "emotional_map_gate": {"ok": emotional_ok, "scene_count": len(current), "map_count": len(emotional_map)},
    }
    failures = [name for name, result in checks.items() if not result.get("ok")]
    return {
        "schema": "faithbloom.autopilot-compliance-core.v1",
        "ok": not failures,
        "checks": checks,
        "failures": failures,
        "policy": "Verificar → Reutilizar → Preservar → Enriquecer → Validar → Concluir",
    }


def assert_autopilot_compliance(state: dict) -> dict:
    report = evaluate_autopilot_compliance(state)
    if not report["ok"]:
        labels = ", ".join(report["failures"])
        raise RuntimeError(
            "Autopilot Compliance Core bloqueou o avanço: " + labels + ". "
            "A versão derivada precisa preservar a estrutura canônica e executar o Heart Arc cena por cena."
        )
    return report

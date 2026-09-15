from autopilot_compliance_core import (
    evaluate_autopilot_compliance,
    validate_canonical_structure,
    validate_heart_arc_scene_map,
    validate_storyteller_candidate,
)


def _scenes(n):
    return [
        {"numero": i, "numero_origem": i, "pagina_origem": i * 2 + 3, "texto": f"Cena {i}"}
        for i in range(1, n + 1)
    ]


def _heart_map():
    return {
        "encantamento": [1],
        "emoção": [2, 3],
        "experiência": [4, 5],
        "descoberta": [6],
        "transformação": [7],
        "fé": [8],
    }


def test_canonical_structure_rejects_scene_reduction():
    canonical = _scenes(11)
    candidate = _scenes(9)
    result = validate_canonical_structure(canonical, candidate)
    assert result["ok"] is False
    assert result["scene_count_reduced"] is True
    assert result["missing_canonical_scenes"] == [10, 11]


def test_canonical_structure_allows_extra_scene_without_losing_canonical_beats():
    canonical = _scenes(3)
    candidate = _scenes(3) + [{"numero": 4, "numero_origem": None, "texto": "Nova cena"}]
    result = validate_canonical_structure(canonical, candidate)
    assert result["ok"] is True
    assert result["coverage_percent"] == 100.0


def test_heart_arc_requires_real_scene_mapping_and_breathing_room():
    candidate = _scenes(8)
    good = validate_heart_arc_scene_map(_heart_map(), candidate)
    assert good["ok"] is True

    flattened = {
        "encantamento": [1],
        "emoção": [2],
        "experiência": [3],
        "descoberta": [6],
        "transformação": [6],
        "fé": [6],
    }
    bad = validate_heart_arc_scene_map(flattened, candidate)
    assert bad["ok"] is False
    assert bad["late_arc_not_flattened"] is False


def test_storyteller_candidate_must_pass_structure_and_heart_arc():
    canonical = _scenes(8)
    assert validate_storyteller_candidate(canonical, _scenes(8), _heart_map())["ok"] is True
    assert validate_storyteller_candidate(canonical, _scenes(6), _heart_map())["ok"] is False


def test_final_compliance_matrix_fails_closed_when_storyteller_dropped_scenes():
    canonical = _scenes(11)
    current = _scenes(9)
    state = {
        "cenas_texto": current,
        "historico_storyteller": [{
            "antes": canonical,
            "depois": current,
            "analise": {"heart_arc_scene_map": _heart_map()},
        }],
        "heart_arc_scene_map": _heart_map(),
        "prompt_master_compliance_remaster": {"ok_para_finalizar": True},
        "licao_final": "Cuidar. Confiar. Esperar.",
        "versiculo_referencia": "Eclesiastes 3:1",
        "metadata_emocional_confirmada": True,
        "mapa_emocional": [{"numero": i} for i in range(1, 10)],
    }
    report = evaluate_autopilot_compliance(state)
    assert report["ok"] is False
    assert "canonical_story_lock" in report["failures"]


def test_final_compliance_matrix_passes_when_all_contracts_hold():
    scenes = _scenes(8)
    state = {
        "cenas_texto": scenes,
        "historico_storyteller": [{
            "antes": scenes,
            "depois": scenes,
            "analise": {"heart_arc_scene_map": _heart_map()},
        }],
        "heart_arc_scene_map": _heart_map(),
        "prompt_master_compliance_remaster": {"ok_para_finalizar": True},
        "licao_final": "Cuidar. Confiar. Esperar.",
        "versiculo_referencia": "Eclesiastes 3:1",
        "metadata_emocional_confirmada": True,
        "mapa_emocional": [{"numero": i} for i in range(1, 9)],
    }
    report = evaluate_autopilot_compliance(state)
    assert report["ok"] is True
    assert report["failures"] == []

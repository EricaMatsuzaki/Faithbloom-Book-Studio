from story_experience_biblical_harmony import (
    bible_final_text_gate,
    deterministic_story_experience_gate,
    review_story_experience_harmony,
)


def _state():
    scenes = [
        {"numero": 1, "texto": "Lia entrou na escola nova curiosa.", "emocao": "curiosidade"},
        {"numero": 2, "texto": "Ela ficou com medo de não fazer amigos.", "emocao": "medo"},
        {"numero": 3, "texto": "Tropeçou no cadarço, riu de si mesma e uma menina a ajudou.", "emocao": "alegria"},
        {"numero": 4, "texto": "Lia decidiu tentar conversar com a turma.", "emocao": "coragem"},
        {"numero": 5, "texto": "Ela descobriu que pedir ajuda também é coragem.", "emocao": "esperança"},
        {"numero": 6, "texto": "No fim, agradeceu a Deus por não ter enfrentado tudo sozinha.", "emocao": "gratidao"},
    ]
    return {
        "titulo": "Lia e a Escola Nova",
        "faixa_etaria": "3-8",
        "cenas_texto": scenes,
        "mapa_emocional": [{"numero": i} for i in range(1, 7)],
        "heart_arc_scene_map": {
            "encantamento": [1],
            "emoção": [2],
            "experiência": [2, 3, 4],
            "descoberta": [5],
            "transformação": [5],
            "fé": [6],
        },
        "licao_final": "Coragem também é pedir ajuda e continuar tentando.",
        "aprendizado_cristao": "Deus pode nos dar coragem e colocar pessoas ao nosso lado.",
        "versiculo_referencia": "Isaías 41:10",
        "bible_records": {
            "pt-BR": {
                "referencia": "Isaías 41:10",
                "status": "approved_text",
                "texto_aprovado": "Não temas, porque eu sou contigo.",
                "versao": "versão aprovada",
                "aprovado_pela_autora": True,
            }
        },
    }


def _semantic_pass():
    keys = [
        "story_first_not_sermon",
        "experience_before_explanation",
        "emotional_journey_coherent",
        "transformation_earned",
        "moral_emerges_from_journey",
        "moral_explicit_at_end",
        "faith_natural_and_age_appropriate",
        "biblical_truth_harmonizes_with_journey",
        "no_false_guarantee_of_outcome",
        "no_artificial_erasure_of_difficult_emotion",
        "opening_does_not_spoil_core_discovery",
        "humor_or_lightness_when_appropriate",
        "emotional_contrast_when_appropriate",
        "memorable_delight_or_wonder",
    ]
    return {
        "checks": {k: {"ok": True, "evidence": "evidência suficiente", "scenes": [1]} for k in keys},
        "blockers": [],
        "strengths": ["jornada vivida"],
        "recommendations": [],
        "summary": "História, moral e verdade bíblica em harmonia.",
    }


def test_bible_final_text_requires_approved_word_of_god():
    state = _state()
    assert bible_final_text_gate(state)["ok"] is True

    missing = dict(state)
    missing["bible_records"] = {}
    assert bible_final_text_gate(missing)["ok"] is False
    assert bible_final_text_gate(missing)["status"] == "TEXT_APPROVAL_REQUIRED"


def test_semantic_guardian_requires_all_core_checks():
    state = _state()
    result = review_story_experience_harmony(state, lambda **_: _semantic_pass())
    assert result["ok"] is True
    assert result["rewrote_story"] is False

    bad = _semantic_pass()
    bad["checks"]["moral_emerges_from_journey"]["ok"] = False
    result = review_story_experience_harmony(state, lambda **_: bad)
    assert result["ok"] is False
    assert "moral_emerges_from_journey" in result["blockers"]


def test_deterministic_gate_requires_semantic_review_and_emotional_rhythm():
    state = _state()
    state["story_experience_biblical_harmony"] = review_story_experience_harmony(
        state, lambda **_: _semantic_pass()
    )
    result = deterministic_story_experience_gate(state)
    assert result["ok"] is True

    flat = _state()
    for scene in flat["cenas_texto"]:
        scene["emocao"] = "alegria"
    flat["story_experience_biblical_harmony"] = review_story_experience_harmony(
        flat, lambda **_: _semantic_pass()
    )
    result = deterministic_story_experience_gate(flat)
    assert result["ok"] is False
    assert "emotional_rhythm_evidence" in result["failures"]

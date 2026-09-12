import faithbloom_cost_mode as cost


def test_economic_mode_is_default_and_free():
    assert cost.DEFAULT_COST_MODE == "economico"
    cfg = cost.mode_config("economico")
    assert cfg["dialogue_model"] == "openrouter/free"
    assert cfg["vision_model"] == "openrouter/free"
    assert cfg["auto_briefing"] is False
    assert cfg["auto_voice"] is False


def test_balanced_mode_uses_low_cost_multimodal_model():
    cfg = cost.mode_config("balanceado")
    assert cfg["dialogue_model"] == "google/gemini-2.5-flash-lite"
    assert cfg["vision_model"] == "google/gemini-2.5-flash-lite"


def test_model_for_routes_dialogue_and_vision():
    assert cost.model_for("dialogue", "economico") == "openrouter/free"
    assert cost.model_for("character_vision", "economico") == "openrouter/free"
    assert cost.model_for("vision", "balanceado") == "google/gemini-2.5-flash-lite"


def test_mode_aliases_are_normalized():
    assert cost.normalize_cost_mode("Econômico") == "economico"
    assert cost.normalize_cost_mode("balanced") == "balanceado"
    assert cost.normalize_cost_mode("premium") == "premium"

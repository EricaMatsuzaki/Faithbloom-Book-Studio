import jarvis_conversation as conv


def test_strip_wake_word_anywhere_in_sentence():
    assert conv.strip_wake_word("Abra meus personagens, Jarvis.") == "Abra meus personagens"
    assert conv.strip_wake_word("Jarvis, como está o tempo?") == "como está o tempo?"


def test_echo_guard_blocks_near_identical_spoken_reply():
    reply = "Entendi. Vou organizar a rota usando os especialistas que já existem no FaithBloom."
    assert conv.looks_like_echo(reply, reply)
    assert conv.looks_like_echo("Vou organizar a rota usando os especialistas que já existem no FaithBloom", reply)
    assert not conv.looks_like_echo("Como está o tempo em Toyohashi?", reply)


def test_history_is_rolling_and_keeps_metadata():
    history = []
    for i in range(20):
        history = conv.append_turn(history, "user", f"mensagem {i}", intent="editorial", metadata={"i": i})
    assert len(history) == conv.MAX_HISTORY_ITEMS
    assert history[-1]["metadata"]["i"] == 19
    assert history[0]["text"] == "mensagem 8"


def test_weather_followup_reuses_last_known_location():
    history = conv.append_turn([], "user", "Como está o tempo em Toyohashi?", intent="weather", metadata={"location": "Toyohashi"})
    enriched = conv.enrich_follow_up("E amanhã?", history)
    assert enriched == "previsão do tempo em Toyohashi amanhã"


def test_weather_followup_does_not_invent_location_without_context():
    assert conv.enrich_follow_up("E amanhã?", []) == "E amanhã?"


def test_general_help_is_not_forced_into_editorial_story_intent():
    assert conv.detect_general_intent("Jarvis, o que você pode fazer?") == "help"
    assert conv.detect_general_intent("Obrigado, Jarvis") == "thanks"


def test_safe_navigation_only_matches_existing_reversible_destinations():
    action = conv.detect_safe_navigation("Jarvis, abra meus personagens")
    assert action["page"] == "pages/14_👥_Character_Universe.py"
    assert conv.detect_safe_navigation("publique meu livro") is None

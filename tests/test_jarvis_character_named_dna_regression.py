import jarvis_assistant as assistant
import jarvis_dialogue as dialogue


QUESTIONS = (
    "Por que você ainda não preencheu o DNA do Téo?",
    "Você já criou o DNA do Téo?",
    "Confira o DNA da Manu.",
    "Complete o DNA de Mel sem criar outro personagem.",
)


def test_named_character_dna_phrases_route_to_character_universe():
    for text in QUESTIONS:
        result = assistant.interpret_request(text)
        assert result["project_type"] == "character_universe"
        assert result["origin"] == "existing_character"
        assert result["next_page"] == assistant.CHARACTER_UNIVERSE_PAGE


def test_exact_runtime_question_never_falls_back_to_children_story_or_llm(monkeypatch):
    text = "Por que você ainda não preencheu o DNA do Téo?"
    result = assistant.interpret_request(text)

    def should_not_call_model(*args, **kwargs):
        raise AssertionError("Named Character Universe request must not depend on generic dialogue routing.")

    monkeypatch.setattr(dialogue, "_post_com_retry", should_not_call_model)
    reply = dialogue.build_natural_reply(text, history=[], route_result=result)
    folded = reply.casefold()

    assert "téo" in folded
    assert "não posso afirmar" in folded
    assert "character universe" in folded
    assert "história infantil" not in folded
    assert "3–8" not in reply


def test_named_character_reply_is_not_hardcoded_to_teo(monkeypatch):
    text = "Complete o DNA da Manu sem alterar o que já estiver aprovado."
    result = assistant.interpret_request(text)
    monkeypatch.setattr(
        dialogue,
        "_post_com_retry",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network should not run")),
    )
    reply = dialogue.build_natural_reply(text, history=[], route_result=result)
    folded = reply.casefold()

    assert "manu" in folded
    assert "téo" not in folded
    assert "sem criar outro personagem" in folded

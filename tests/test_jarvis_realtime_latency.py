import jarvis_dialogue as dialogue
import jarvis_voice as voice


def _route():
    return {
        "route_plan": {"project_label": "livro infantil", "audience_label": "3–8 anos"},
        "anti_duplication": {"ok": True},
        "project_type": "children_story",
        "origin": "own_idea",
        "audience": "3_8",
        "editorial_line": "christian",
        "requires_author_approval": True,
        "next_action": "review_and_approve_route",
        "next_page": "pages/39_✍️_Historia_4_Estilos.py",
    }


def test_jarvis_chat_uses_dedicated_low_latency_nitro_model():
    assert dialogue.JARVIS_DIALOGUE_MODEL == "google/gemini-2.5-flash-lite:nitro"
    assert "flash-lite" in dialogue.JARVIS_DIALOGUE_MODEL
    assert dialogue.JARVIS_DIALOGUE_MODEL.endswith(":nitro")


def test_date_time_request_is_local_and_never_calls_llm(monkeypatch):
    def fail_dialogue(*args, **kwargs):
        raise AssertionError("date/time must not call the LLM")

    monkeypatch.setattr(voice, "build_natural_reply", fail_dialogue)
    reply = voice.build_spoken_reply("qual a data de hoje?", natural=True)
    assert reply.startswith("Hoje é ")
    assert "Agora são" in reply


def test_direct_editorial_command_skips_llm_even_in_natural_mode(monkeypatch):
    def fail_dialogue(*args, **kwargs):
        raise AssertionError("direct editorial commands must use the local route")

    monkeypatch.setattr(voice, "build_natural_reply", fail_dialogue)
    reply = voice.build_spoken_reply(
        "Crie um livro infantil cristão sobre paciência",
        result=_route(),
        natural=True,
    )
    assert "livro infantil" in reply
    assert "3–8 anos" in reply
    assert "confirmação" in reply


def test_open_conversation_still_uses_natural_fast_dialogue(monkeypatch):
    called = {}

    def fake_dialogue(text, **kwargs):
        called["text"] = text
        return "Claro. Posso pensar nisso com você."

    monkeypatch.setattr(voice, "build_natural_reply", fake_dialogue)
    reply = voice.build_spoken_reply(
        "O que você acha que deixaria essa história mais emocionante?",
        result=_route(),
        natural=True,
    )
    assert reply == "Claro. Posso pensar nisso com você."
    assert called["text"].startswith("O que você acha")


def test_simple_greeting_is_local_and_short(monkeypatch):
    def fail_dialogue(*args, **kwargs):
        raise AssertionError("simple greeting must not call the LLM")

    monkeypatch.setattr(voice, "build_natural_reply", fail_dialogue)
    reply = voice.build_spoken_reply("Bom dia", natural=True)
    assert "Erica" in reply
    assert len(reply.split()) < 15

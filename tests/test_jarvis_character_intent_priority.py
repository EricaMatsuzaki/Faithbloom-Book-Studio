import jarvis_assistant as assistant
import jarvis_dialogue as dialogue


REQUEST = (
    "Complete o DNA visual do Téo usando o Color Master e as referências já cadastradas. "
    "Não crie outro personagem e não altere o que já estiver aprovado."
)


def test_explicit_character_dna_request_routes_to_existing_character_universe():
    result = assistant.interpret_request(REQUEST)

    assert result["project_type"] == "character_universe"
    assert result["origin"] == "existing_character"
    assert result["anti_duplication"]["ok"] is True
    assert result["next_action"] == "review_and_complete_missing_character_dna"
    assert result["next_page"] == assistant.CHARACTER_UNIVERSE_PAGE
    assert "Character Universe" in result["route_plan"]["project_label"]


def test_character_request_ignores_incompatible_old_exam_context(monkeypatch):
    result = assistant.interpret_request(REQUEST)
    history = [
        {
            "role": "assistant",
            "text": "Você quer um Preparatório para Provas e Certificações para 3–8 anos.",
            "intent": "editorial",
        }
    ]

    def should_not_call_model(*args, **kwargs):
        raise AssertionError("Character Universe explícito não deve depender do diálogo LLM com histórico antigo.")

    monkeypatch.setattr(dialogue, "_post_com_retry", should_not_call_model)
    reply = dialogue.build_natural_reply(REQUEST, history=history, route_result=result)
    folded = reply.casefold()

    assert "téo" in folded
    assert "dna visual" in folded
    assert "color master" in folded
    assert "campos faltantes" in folded
    assert "sem criar outro personagem" in folded
    assert "preparatório" not in folded
    assert "certifica" not in folded
    assert "3–8" not in reply

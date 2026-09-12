import jarvis_dialogue as jd


def test_internal_reasoning_is_blocked_for_teo_dna_request():
    leaked_page = "pages" + "/0_Orquestrador_FaithBloom.py"
    leaked = (
        "Jarvis: Okay, let's see. I need to check the operational context. "
        f"The route_plan has run_id abc and next_page {leaked_page}."
    )
    safe = jd._public_answer(
        leaked,
        "Complete o DNA visual do Téo usando o Color Master e as referências já cadastradas.",
        {},
    )

    assert "Okay, let's see" not in safe
    assert "operational context" not in safe
    assert "run_id" not in safe
    assert "pages/" not in safe
    assert "Téo" in safe
    assert "sem criar outro personagem" in safe


def test_normal_public_reply_is_preserved():
    answer = "Encontrei o Téo e vou completar apenas os campos faltantes do DNA."
    assert jd._public_answer(answer, "Complete o DNA do Téo", {}) == answer


def test_route_fallback_uses_human_next_step_without_internal_metadata():
    internal_page = "pages" + "/14_Character_Universe.py"
    context = {
        "rota_editorial": {
            "tipo": "character",
            "rotulo_projeto": "Téo",
            "proximo_passo": "revisar e aprovar o DNA visual",
            "pagina_sugerida": internal_page,
        }
    }
    safe = jd._public_answer(
        "I need to check the operational context and route_plan.",
        "Continue",
        context,
    )

    assert safe == "Entendi o pedido do projeto Téo. O próximo passo é revisar e aprovar o DNA visual."
    assert "pagina" not in safe.casefold()
    assert "route" not in safe.casefold()

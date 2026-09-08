from age_profiles import instrucao_faixa_etaria
from emotional_experience_engine import (
    EMOTIONAL_EXPERIENCE_PRINCIPLES,
    instrucao_experiencia_emocional,
    perfil_emocional_etario,
)
from agents.estilos_narrativos import gerar_comparativo_estilos
from agents.roteirista_autoral import _base_sistema
from agents.revisor import montar_prompt_revisor
from external_ai_bridge import build_external_authoring_prompt, SOURCE_IDEA


def _state(age="6-8"):
    return {
        "colecao": "Coleção Teste",
        "titulo": "Clara e a Noite",
        "faixa_etaria": age,
        "age_profile_id": age,
        "paginas_minimas": 24,
        "_entrada_tema_livre": "Clara precisa atravessar um corredor escuro para buscar o brinquedo da irmã.",
        "emocao_central": "medo",
        "aprendizado_cristao": "Podemos pedir ajuda e confiar que Deus está conosco.",
        "versiculo_referencia": "Salmos 56:3",
        "personagens_historia_brief": "Clara — protagonista.\nSofia — irmã mais nova.",
        "personagens": {},
        "versoes_narrativas_salvas": {},
    }


def test_profiles_are_age_specific_and_allow_mixed_emotions():
    p35 = perfil_emocional_etario("3-5")
    p68 = perfil_emocional_etario("6-8")
    p912 = perfil_emocional_etario("9-12")

    assert "concretas" in p35["complexidade"]
    assert "duas emoções" in p68["mistura"] or "simultâneas" in p68["mistura"]
    assert "ambival" in p912["complexidade"]
    assert p35 != p68 != p912


def test_engine_does_not_label_emotions_good_or_bad_and_faith_does_not_erase_them():
    text = " ".join(EMOTIONAL_EXPERIENCE_PRINCIPLES).lower()
    assert "boas ou más" in text
    assert "fé acompanha a emoção" in text
    assert "continuar triste" in text
    assert "perdas" in text


def test_age_instruction_includes_emotional_engine():
    text = instrucao_faixa_etaria("6-8")
    assert "FAITHBLOOM EMOTIONAL EXPERIENCE ENGINE™" in text
    assert "feliz pela amiga" in text
    assert "ansiedade antecipatória" in text


def test_storyteller_styles_receive_engine_through_age_profile():
    captured = []

    def fake_llm(*, sistema, instrucao):
        captured.append((sistema, instrucao))
        return {
            "titulo": "Teste",
            "sinopse_poetica": "Teste",
            "amostra": "Uma pequena amostra.",
            "licao_final": "Aprender a pedir ajuda também é coragem.",
        }

    gerar_comparativo_estilos(_state(), fake_llm, modo="amostra")
    assert len(captured) == 4
    assert all("FAITHBLOOM EMOTIONAL EXPERIENCE ENGINE™" in system for system, _ in captured)


def test_authorial_external_and_reviewer_all_receive_same_engine():
    state = _state()
    authorial = _base_sistema(state)
    external = build_external_authoring_prompt(state, source_mode=SOURCE_IDEA)
    reviewer = montar_prompt_revisor(state)

    for text in (authorial, external, reviewer):
        assert "FAITHBLOOM EMOTIONAL EXPERIENCE ENGINE™" in text
        assert "emoções" in text.lower()


def test_fallback_profile_is_broad_collection_profile():
    text = instrucao_experiencia_emocional("idade-inexistente")
    assert "Perfil emocional para 3-8" in text

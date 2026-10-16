import pytest

from real_experience_story import (
    FIDELITY_FAITHFUL,
    FIDELITY_INSPIRED,
    PRIVACY_AUTHORIZED_NAMES,
    PRIVACY_FICTIONALIZE,
    REAL_EXPERIENCE_CATEGORY_ID,
    REAL_EXPERIENCE_CATEGORY_LABEL,
    apply_real_experience_to_state,
    build_real_experience_brief,
    is_real_experience_story,
)


def test_real_experience_requires_account_and_consent():
    with pytest.raises(ValueError):
        build_real_experience_brief("", consent_confirmed=True)
    with pytest.raises(ValueError):
        build_real_experience_brief("Uma mudança de país.", consent_confirmed=False)


def test_faithful_mode_protects_facts_and_sensitive_events():
    brief = build_real_experience_brief(
        "Uma menina mudou de país e enfrentou uma nova escola.",
        fidelity_mode=FIDELITY_FAITHFUL,
        privacy_mode=PRIVACY_FICTIONALIZE,
        relation="menor_responsavel",
        consent_confirmed=True,
    )
    assert REAL_EXPERIENCE_CATEGORY_LABEL in brief
    assert "não mude o que aconteceu" in brief
    assert "não acrescente doença, diagnóstico, abuso, crime, morte" in brief
    assert "Ficcionalize nomes" in brief


def test_inspired_mode_allows_literary_fictionalization_without_false_attribution():
    brief = build_real_experience_brief(
        "Uma família começou de novo em outra cidade.",
        fidelity_mode=FIDELITY_INSPIRED,
        privacy_mode=PRIVACY_AUTHORIZED_NAMES,
        relation="adulto_autorizado",
        consent_confirmed=True,
    )
    assert "Pode condensar tempo" in brief
    assert "nunca atribua" in brief
    assert "Nomes reais foram marcados como autorizados" in brief


def test_apply_real_experience_sets_origin_metadata_and_pipeline_brief():
    state = {"colecao": "Coleção Teste", "faixa_etaria": "6-8"}
    prepared = apply_real_experience_to_state(
        state,
        account="Uma criança precisou aprender um novo idioma.",
        relation="menor_responsavel",
        consent_confirmed=True,
    )
    assert prepared["story_category"] == REAL_EXPERIENCE_CATEGORY_ID
    assert prepared["real_experience"]["consent_confirmed"] is True
    assert prepared["real_experience"]["original_account"].startswith("Uma criança")
    assert prepared["origem_ideia"] == "projeto"
    assert REAL_EXPERIENCE_CATEGORY_LABEL in prepared["_entrada_tema_livre"]
    assert prepared["revisao_aprovada"] is False
    assert prepared["pacote_pronto"] is False
    assert is_real_experience_story(prepared)


def test_real_experience_page_routes_to_existing_story_and_external_ai_flows():
    from pathlib import Path

    text = Path("pages/42_🌿_Historias_Inspiradas_na_Vida_Real.py").read_text(encoding="utf-8")
    assert "Origem da história — não estilo narrativo" in text
    assert 'st.switch_page("pages/39_✍️_Historia_4_Estilos.py")' in text
    assert 'st.switch_page("pages/41_🤖_IA_Externa_sem_OpenRouter.py")' in text
    assert "0 créditos" in text

from localization_excellence import (
    JAPANESE_MIMESIS_TAXONOMY,
    locale_specialist_profile,
    localization_excellence_contract,
    native_child_language_review_prompt,
)
from agents.tradutor import tradutor_node


def test_ja_jp_tem_especializacao_ehon_por_idade():
    p = locale_specialist_profile("ja-JP", "6–8")
    assert p["locale"] == "ja-JP"
    assert p["age_key"] == "6-8"
    assert p["japanese_age_guide"]
    assert "絵本" in p["format_note"]
    assert any("漢字" in x for x in p["japanese_age_guide"])


def test_taxonomia_japonesa_distingue_som_voz_e_estado():
    assert set(JAPANESE_MIMESIS_TAXONOMY) == {"giongo", "giseigo", "gitaigo"}
    assert "わくわく" in JAPANESE_MIMESIS_TAXONOMY["gitaigo"]["examples"]
    assert "コンコン" in JAPANESE_MIMESIS_TAXONOMY["giongo"]["examples"]


def test_contrato_preserva_heart_arc_e_transcriacao_controlada():
    c = localization_excellence_contract("ja-JP", "6–8")
    assert "HEART ARC" in c
    assert "TRANSCREAÇÃO CONTROLADA" in c
    assert "擬音語" in c
    assert "擬声語" in c
    assert "擬態語" in c
    assert "não imite obra ou editora específica" in c


def test_revisor_nativo_japones_verifica_kanji_kana_e_naturalidade():
    p = native_child_language_review_prompt("ja-JP", "6–8")
    assert "kanji/kana" in p
    assert "擬音語・擬声語・擬態語" in p
    assert "tradução mecânica" in p


def test_tradutor_injeta_excellence_contract_e_salva_perfil():
    state = {
        "titulo": "Clara e o corredor",
        "faixa_etaria": "6–8",
        "idiomas_alvo": ["ja-JP"],
        "translation_profiles": {},
        "translation_mode": "natural_infantil",
        "onomatopoeia_intensity": "equilibrada",
        "glossario_colecao": {},
        "bible_records": {},
        "versiculo_referencia": "Salmos 56:3",
        "personagens": {"Clara": {"nome": "Clara"}},
        "cenas_texto": [{"numero": 1, "texto": "Clara respirou fundo."}],
        "licao_final": "Coragem também é seguir em frente com medo.",
    }
    calls = []

    def fake_llm(sistema, instrucao):
        calls.append((sistema, instrucao))
        return {
            "titulo": "クララと廊下",
            "cenas_texto": [{"numero": 1, "texto": "クララは、すうっと息をすった。"}],
            "licao_final": "こわくても、一歩ずつ進める。",
        }

    result = tradutor_node(state, fake_llm)
    assert calls
    joined = calls[0][0] + calls[0][1]
    assert "FAITHBLOOM LOCALIZATION EXCELLENCE CONTRACT" in joined
    assert "Heart Arc" in joined or "HEART ARC" in joined
    assert "擬音語" in joined
    assert result["localization_quality_profiles"]["ja-JP"]["age_key"] == "6-8"
    assert result["traducoes"]["ja-JP"]["localization_excellence_profile"]["locale"] == "ja-JP"

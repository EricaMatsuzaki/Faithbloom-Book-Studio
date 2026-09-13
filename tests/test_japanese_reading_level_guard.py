from japanese_reading_level import (
    MEXT_ELEMENTARY_KANJI_COUNTS,
    MEXT_ELEMENTARY_TOTAL,
    japanese_reading_contract,
    japanese_reading_profile,
)
from japanese_localization_bridge import (
    localizar_livro_com_reading_guard,
    revisar_localizacao_com_reading_guard,
)


def test_mext_counts_match_elementary_total():
    assert MEXT_ELEMENTARY_KANJI_COUNTS == {1: 80, 2: 160, 3: 200, 4: 202, 5: 193, 6: 191}
    assert MEXT_ELEMENTARY_TOTAL == 1026


def test_6_8_preserves_good_word_and_uses_furigana_support():
    profile = japanese_reading_profile("6–8")
    assert profile["school_grade_reference"] == "grade-1-to-grade-2"
    assert profile["furigana_policy"]["prefer_natural_word"] is True
    assert profile["furigana_policy"]["support_advanced_kanji"] is True
    contract = japanese_reading_contract("6–8")
    assert "ふりがな" in contract
    assert "furigana_annotations" in contract
    assert "weaker expression" in contract


def test_broad_9_12_is_adaptive_not_fake_exact_grade():
    profile = japanese_reading_profile("9–12")
    assert profile["school_grade_reference"] == "grade-3-to-grade-6 adaptive"
    assert profile["kanji_policy"] == "adaptive-upper-elementary"


def test_bridge_injects_reading_guard_only_for_japanese():
    calls = []

    def fake_llm(sistema, instrucao):
        calls.append((sistema, instrucao))
        return {
            "titulo": "メルは待つことを学びました",
            "cenas_texto": [
                {
                    "numero": 1,
                    "texto": "メルは種を見つめました。",
                    "furigana_annotations": [
                        {"surface": "種", "reading": "たね", "reason": "reading_support"}
                    ],
                }
            ],
        }

    result = localizar_livro_com_reading_guard(
        {"titulo": "Mel", "cenas_texto": [{"numero": 1, "texto": "Mel olhou para a semente."}]},
        fake_llm,
        "ja-JP",
        faixa_etaria="6–8",
    )
    assert calls
    assert "JAPANESE CHILD READING LEVEL GUARD" in calls[0][1]
    assert result["furigana_metadata_supported"] is True
    assert result["japanese_reading_profile"]["age_key"] == "6-8"


def test_non_japanese_does_not_get_japanese_profile():
    def fake_llm(sistema, instrucao):
        return {"titulo": "Mel", "cenas_texto": [{"numero": 1, "texto": "Mel waited."}]}

    result = localizar_livro_com_reading_guard(
        {"titulo": "Mel", "cenas_texto": [{"numero": 1, "texto": "Mel esperou."}]},
        fake_llm,
        "en-US",
        faixa_etaria="6–8",
    )
    assert "japanese_reading_profile" not in result
    assert "furigana_metadata_supported" not in result


def test_independent_review_adds_japanese_reading_audit():
    calls = []

    def fake_llm(sistema, instrucao):
        calls.append((sistema, instrucao))
        if "JAPANESE CHILD READING LEVEL GUARD" in sistema:
            return {"veredito": "aprovado", "alertas": [], "furigana_sugerido_por_cena": []}
        return {"veredito": "aprovado", "alertas": []}

    result = revisar_localizacao_com_reading_guard(
        {"titulo": "Mel", "cenas_texto": [{"numero": 1, "texto": "Mel esperou."}]},
        {"titulo": "メル", "cenas_texto": [{"numero": 1, "texto": "メルは待ちました。"}]},
        fake_llm,
        "ja-JP",
        "6–8",
    )
    assert len(calls) == 2
    assert result["revisao_linguistica"]["veredito"] == "aprovado"
    assert result["japanese_reading_review"]["veredito"] == "aprovado"

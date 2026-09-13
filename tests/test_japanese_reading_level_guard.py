from japanese_reading_level import (
    MEXT_ELEMENTARY_KANJI_COUNTS,
    MEXT_ELEMENTARY_TOTAL,
    MEXT_KANJI_BY_GRADE,
    audit_kanji_for_grade,
    cumulative_kanji_through_grade,
    grade_for_kanji,
    japanese_reading_contract,
    japanese_reading_profile,
    validate_exact_mext_allocations,
)
from japanese_localization_bridge import (
    localizar_livro_com_reading_guard,
    revisar_localizacao_com_reading_guard,
)


def test_mext_counts_match_elementary_total():
    assert MEXT_ELEMENTARY_KANJI_COUNTS == {1: 80, 2: 160, 3: 200, 4: 202, 5: 193, 6: 191}
    assert MEXT_ELEMENTARY_TOTAL == 1026
    assert {grade: len(chars) for grade, chars in MEXT_KANJI_BY_GRADE.items()} == MEXT_ELEMENTARY_KANJI_COUNTS
    assert validate_exact_mext_allocations() is True


def test_current_mext_reallocation_is_present():
    # Current 平成29年告示 allocation, not the older 1006-character table.
    assert grade_for_kanji("茨") == 4
    assert grade_for_kanji("媛") == 4
    assert grade_for_kanji("城") == 4
    assert grade_for_kanji("囲") == 5
    assert grade_for_kanji("胃") == 6
    assert grade_for_kanji("恩") == 6


def test_cumulative_counts_follow_school_reading_progression():
    assert len(cumulative_kanji_through_grade(1)) == 80
    assert len(cumulative_kanji_through_grade(2)) == 240
    assert len(cumulative_kanji_through_grade(3)) == 440
    assert len(cumulative_kanji_through_grade(4)) == 642
    assert len(cumulative_kanji_through_grade(5)) == 835
    assert len(cumulative_kanji_through_grade(6)) == 1026


def test_character_audit_flags_advanced_kanji_without_deleting_it():
    # 花 is grade 1; 種 is grade 4. Grade-1 text may keep 種, but it needs support.
    audit = audit_kanji_for_grade("花の種", 1)
    assert {x["kanji"] for x in audit["within_target"]} == {"花"}
    assert {x["kanji"] for x in audit["above_target"]} == {"種"}
    assert audit["needs_reading_support"]
    assert audit["ok_without_support"] is False


def test_6_8_preserves_good_word_and_uses_furigana_support():
    profile = japanese_reading_profile("6–8")
    assert profile["school_grade_reference"] == "grade-1-to-grade-2"
    assert profile["furigana_policy"]["prefer_natural_word"] is True
    assert profile["furigana_policy"]["support_advanced_kanji"] is True
    assert profile["exact_grade_lists_loaded"] is True
    contract = japanese_reading_contract("6–8")
    assert "ふりがな" in contract
    assert "furigana_annotations" in contract
    assert "weaker expression" in contract
    assert "character-by-character" in contract


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

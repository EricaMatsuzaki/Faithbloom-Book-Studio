"""Japanese child-reading policy for FaithBloom localizations.

This module does not try to replace Japanese editorial judgement. It converts the
FaithBloom age profile into a conservative reading policy inspired by MEXT's
学年別漢字配当表 and explicitly allows later-grade kanji when they improve the
story, provided reading support (furigana/ruby) is supplied.

Official elementary-school allocation counts (MEXT):
1st: 80, 2nd: 160, 3rd: 200, 4th: 202, 5th: 193, 6th: 191 = 1,026.

Important: broad FaithBloom bands (for example 3–8 or 9–12) are not identical to
a Japanese school grade. Therefore this policy is deliberately adaptive rather
than pretending an exact school-year mapping when the reader's exact age is not
known.
"""
from __future__ import annotations

from copy import deepcopy

MEXT_ELEMENTARY_KANJI_COUNTS = {
    1: 80,
    2: 160,
    3: 200,
    4: 202,
    5: 193,
    6: 191,
}

MEXT_ELEMENTARY_TOTAL = sum(MEXT_ELEMENTARY_KANJI_COUNTS.values())

MEXT_SOURCE = {
    "authority": "MEXT / 文部科学省",
    "document": "小学校学習指導要領（平成29年告示）解説 国語編",
    "principle": (
        "Later-grade or non-allocation kanji may be presented when needed, while "
        "reducing reading burden by adding furigana or equivalent support."
    ),
}

JAPANESE_READING_POLICIES = {
    "3-5": {
        "reader_stage": "未就学・読み聞かせ中心",
        "school_grade_reference": "preschool",
        "kanji_policy": "hiragana-first",
        "guidance": [
            "ひらがなを基本にし、カタカナは自然な語だけに使う",
            "漢字は物語上の価値がある場合に限定し、原則として読みを付ける",
            "読み聞かせのリズム、反復、音の楽しさを優先する",
        ],
    },
    "3-8": {
        "reader_stage": "読み聞かせ＋初期自読",
        "school_grade_reference": "preschool-to-grade-2 adaptive",
        "kanji_policy": "adaptive-low-elementary",
        "guidance": [
            "未就学児にも追いやすいかな中心の読みやすさを保つ",
            "小学校低学年で自然な基本漢字は文脈に応じて使える",
            "読者に難しい可能性がある漢字は、語を不自然に言い換える前にふりがなを検討する",
            "年齢が特定されていない場合は読み負荷を低めに保つ",
        ],
    },
    "6-8": {
        "reader_stage": "小学校低学年・初期自読",
        "school_grade_reference": "grade-1-to-grade-2",
        "kanji_policy": "grade-aware-low-elementary",
        "guidance": [
            "第1・第2学年相当の読みやすさを基準にする",
            "その段階を超える漢字でも、語の自然さや文学的効果を守るため必要なら使用してよい",
            "未習の可能性がある漢字にはふりがなを付け、意味と読みの負担を下げる",
            "漢字を避けるために不自然な幼児語へ置き換えない",
        ],
    },
    "9-12": {
        "reader_stage": "小学校中・高学年",
        "school_grade_reference": "grade-3-to-grade-6 adaptive",
        "kanji_policy": "adaptive-upper-elementary",
        "guidance": [
            "第3〜第6学年の発達差を意識し、語彙と漢字の密度を場面に合わせる",
            "正確な年齢が不明な場合、難しい漢字を無注釈で多用しない",
            "物語に最適な語が学年を超える漢字を含む場合、ふりがなで読みを支援する",
            "ふりがなの過剰使用でページを騒がしくしない。必要性と再出現を考える",
        ],
    },
}


def _age_key(faixa_etaria: str) -> str:
    raw = str(faixa_etaria or "3-8").replace("–", "-").strip()
    for key in ("3-5", "3-8", "6-8", "9-12"):
        if key in raw:
            return key
    return "3-8"


def japanese_reading_profile(faixa_etaria: str = "3–8") -> dict:
    key = _age_key(faixa_etaria)
    out = deepcopy(JAPANESE_READING_POLICIES[key])
    out.update({
        "age_key": key,
        "mext_elementary_counts": deepcopy(MEXT_ELEMENTARY_KANJI_COUNTS),
        "mext_elementary_total": MEXT_ELEMENTARY_TOTAL,
        "source": deepcopy(MEXT_SOURCE),
        "furigana_policy": {
            "prefer_natural_word": True,
            "support_advanced_kanji": True,
            "do_not_replace_good_word_just_to_avoid_kanji": True,
            "avoid_excessive_ruby": True,
            "annotation_schema": {
                "surface": "kanji or word as printed",
                "reading": "hiragana reading",
                "reason": "reading_support|above_target_level|proper_name|editorial_clarity",
            },
        },
    })
    return out


def japanese_reading_contract(faixa_etaria: str = "3–8") -> str:
    p = japanese_reading_profile(faixa_etaria)
    return "\n".join([
        "=== JAPANESE CHILD READING LEVEL GUARD — MEXT-AWARE ===",
        f"FaithBloom age profile: {p['age_key']}.",
        f"Reader stage: {p['reader_stage']}.",
        f"School-grade reference: {p['school_grade_reference']}.",
        "MEXT elementary allocation counts: 1年80 / 2年160 / 3年200 / 4年202 / 5年193 / 6年191 (total 1,026).",
        "Apply grade awareness as a reading-support policy, not as a crude ban on expressive vocabulary.",
        *[f"- {x}" for x in p["guidance"]],
        "FURIGANA/RUBY RULE:",
        "- If the best natural child-language word contains a kanji that may be beyond the target reader, keep the good word and add reading support instead of automatically replacing it with a weaker expression.",
        "- Return scene-level `furigana_annotations` when reading support is useful. Each item must contain `surface`, `reading` in hiragana, and `reason`.",
        "- Keep the main Japanese sentence natural and clean; furigana annotations are metadata for typography/layout, not parenthetical prose inserted repeatedly into the story text.",
        "- Proper names may also receive reading support when needed, without changing their protected identity.",
        "- Do not add furigana mechanically to every kanji; preserve visual calm and age-appropriate readability.",
    ]) + "\n"

"""Japanese child-reading policy for FaithBloom localizations.

This module does not replace Japanese editorial judgement. It converts the
FaithBloom age profile into a conservative reading policy aligned with MEXT's
current 学年別漢字配当表 and explicitly allows later-grade kanji when they improve
the story, provided reading support (furigana/ruby) is supplied.

Current elementary-school allocation counts (MEXT, 平成29年告示):
1st: 80, 2nd: 160, 3rd: 200, 4th: 202, 5th: 193, 6th: 191 = 1,026.

Important: broad FaithBloom bands (for example 3–8 or 9–12) are not identical to
a Japanese school grade. Therefore this policy is adaptive rather than pretending
an exact school-year mapping when the reader's exact age is not known.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Iterable

MEXT_ELEMENTARY_KANJI_COUNTS = {
    1: 80,
    2: 160,
    3: 200,
    4: 202,
    5: 193,
    6: 191,
}

MEXT_ELEMENTARY_TOTAL = sum(MEXT_ELEMENTARY_KANJI_COUNTS.values())

# Exact current per-grade allocations. Membership matters; order does not.
MEXT_KANJI_BY_GRADE: dict[int, frozenset[str]] = {
    1: frozenset("一七三上下中九二五人休先入八六円出力十千口右名四土夕大天女子字学小山川左年手文日早月木本村林校森正気水火犬玉王生田男町白百目石空立竹糸耳花草虫見貝赤足車金雨青音"),
    2: frozenset("万丸交京今会体何作元兄光公内冬刀分切前北午半南原友古台合同回図国園地場声売夏外多夜太妹姉室家寺少岩工市帰広店弓引弟弱強当形後心思戸才教数新方明星春昼時晴曜書朝来東楽歌止歩母毎毛池汽活海点父牛理用画番直矢知社秋科答算米紙細組絵線羽考聞肉自船色茶行西親角言計記話語読谷買走近通週道遠里野長門間雪雲電頭顔風食首馬高魚鳥鳴麦黄黒"),
    3: frozenset("丁世両主乗予事仕他代住使係倍全具写列助勉動勝化区医去反取受号向君味命和品員商問坂央始委守安定実客宮宿寒対局屋岸島州帳平幸度庫庭式役待急息悪悲想意感所打投拾持指放整旅族昔昭暑暗曲有服期板柱根植業様横橋次歯死氷決油波注泳洋流消深温港湖湯漢炭物球由申界畑病発登皮皿相県真着短研礼神祭福秒究章童笛第筆等箱級終緑練羊美習者育苦荷落葉薬血表詩調談豆負起路身転軽農返追送速進遊運部都配酒重鉄銀開院陽階集面題飲館駅鼻"),
    4: frozenset("不争井付令以仲伝位低佐例便信倉候借健側働億兆児共兵典冷初別利刷副功加努労勇包卒協単博印参司各周唱器固城埼塩変夫失奈好媛季孫完官害富察岐岡崎巣差希席帯底府康建径徒徳必念愛成戦折挙改敗散料旗昨景最望未末札材束松果栃栄案梅梨械極標機欠残氏民求沖治法泣浅浴清満滋漁潟灯無然焼照熊熱牧特産的省祝票種積競笑管節約結給続縄置群老臣良芸芽英茨菜街衣要覚観訓試説課議貨賀軍輪辞辺連達選郡量録鏡関阜阪陸隊静順願類飛飯養香験鹿"),
    5: frozenset("久仏仮件任似余価保修個停備像再刊判制則効務勢厚句可史告喜営因団囲圧在均型基堂報境墓増士夢妻婦容寄導居属布師常幹序弁張往得復志応快性情態慣技招授採接提損支政故救断旧易暴条枝査格桜検構武歴殺毒比永河液混減測準演潔災燃版犯状独率現留略益眼破確示祖禁移程税築粉精紀素経統絶綿総編績織罪義耕職肥能脈興舎航術衛製複規解設許証評講謝識護豊象財貧責貯貸費貿資賛賞質輸述迷逆造過適酸鉱銅防限険際雑非領額飼"),
    6: frozenset("並乱乳亡仁供俳俵値傷優党冊処券刻割創劇勤危卵厳収后否吸呼善困垂域奏奮姿存孝宅宇宗宙宝宣密寸専射将尊就尺届展層己巻幕干幼庁座延律従忘忠恩憲我批承担拝拡捨探推揮操敬敵映晩暖暮朗机枚染株棒模権樹欲段沿泉洗派済源潮激灰熟片班異疑痛皇盛盟看砂磁私秘穀穴窓筋策簡糖系紅納純絹縦縮署翌聖肺胃背胸脳腸腹臓臨至舌若著蒸蔵蚕衆裁装裏補視覧討訪訳詞誌認誕誠誤論諸警貴賃退遺郵郷針銭鋼閉閣降陛除障難革頂預骨"),
}

MEXT_SOURCE = {
    "authority": "MEXT / 文部科学省",
    "document": "小学校学習指導要領（平成29年告示）解説 国語編",
    "principle": (
        "Later-grade or non-allocation kanji may be presented when needed, while "
        "reducing reading burden by adding furigana or equivalent support."
    ),
    "allocation_revision": (
        "Current 1,026-character allocation includes the 2017 revision, including "
        "prefecture-name kanji and grade reassignments."
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


def cumulative_kanji_through_grade(grade: int) -> frozenset[str]:
    """All kanji allocated from grade 1 through ``grade`` (inclusive)."""
    g = max(0, min(int(grade), 6))
    chars: set[str] = set()
    for level in range(1, g + 1):
        chars.update(MEXT_KANJI_BY_GRADE[level])
    return frozenset(chars)


def grade_for_kanji(char: str) -> int | None:
    """Return the elementary-school allocation grade, or None if not in the 1,026."""
    for grade, chars in MEXT_KANJI_BY_GRADE.items():
        if char in chars:
            return grade
    return None


def _is_cjk_ideograph(char: str) -> bool:
    if not char:
        return False
    cp = ord(char)
    return 0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF


def audit_kanji_for_grade(text: str, target_grade: int) -> dict:
    """Character-by-character reading audit for an exact Japanese school grade.

    Advanced/non-allocation kanji are not silently removed. They are surfaced as
    candidates for furigana or editorial review so literary quality can be kept.
    """
    target = max(1, min(int(target_grade), 6))
    permitted = cumulative_kanji_through_grade(target)
    seen: list[str] = []
    for char in str(text or ""):
        if _is_cjk_ideograph(char) and char not in seen:
            seen.append(char)

    within = []
    above = []
    outside = []
    for char in seen:
        grade = grade_for_kanji(char)
        item = {"kanji": char, "mext_grade": grade}
        if char in permitted:
            within.append(item)
        elif grade is None:
            outside.append(item)
        else:
            above.append(item)

    return {
        "target_grade": target,
        "allowed_cumulative_count": len(permitted),
        "within_target": within,
        "above_target": above,
        "outside_elementary_allocation": outside,
        "needs_reading_support": above + outside,
        "ok_without_support": not above and not outside,
    }


def validate_exact_mext_allocations() -> bool:
    """Fail closed if a future edit accidentally corrupts an official grade set."""
    if any(len(MEXT_KANJI_BY_GRADE[g]) != expected for g, expected in MEXT_ELEMENTARY_KANJI_COUNTS.items()):
        return False
    merged: set[str] = set()
    for chars in MEXT_KANJI_BY_GRADE.values():
        if merged.intersection(chars):
            return False
        merged.update(chars)
    return len(merged) == MEXT_ELEMENTARY_TOTAL


def japanese_reading_profile(faixa_etaria: str = "3–8") -> dict:
    key = _age_key(faixa_etaria)
    out = deepcopy(JAPANESE_READING_POLICIES[key])
    out.update({
        "age_key": key,
        "mext_elementary_counts": deepcopy(MEXT_ELEMENTARY_KANJI_COUNTS),
        "mext_elementary_total": MEXT_ELEMENTARY_TOTAL,
        "exact_grade_lists_loaded": validate_exact_mext_allocations(),
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
        "MEXT current elementary allocation: 1年80 / 2年160 / 3年200 / 4年202 / 5年193 / 6年191 (total 1,026).",
        "Exact current per-grade kanji sets are loaded for character-by-character audit.",
        "Apply grade awareness as a reading-support policy, not as a crude ban on expressive vocabulary.",
        *[f"- {x}" for x in p["guidance"]],
        "FURIGANA/RUBY RULE:",
        "- If the best natural child-language word contains a kanji that may be beyond the target reader, keep the good word and add reading support instead of automatically replacing it with a weaker expression.",
        "- Return scene-level `furigana_annotations` when reading support is useful. Each item must contain `surface`, `reading` in hiragana, and `reason`.",
        "- Keep the main Japanese sentence natural and clean; furigana annotations are metadata for typography/layout, not parenthetical prose inserted repeatedly into the story text.",
        "- Proper names may also receive reading support when needed, without changing their protected identity.",
        "- Do not add furigana mechanically to every kanji; preserve visual calm and age-appropriate readability.",
    ]) + "\n"

from ui_saved_choices import normalize_saved_choices


def test_normalize_saved_choices_removes_case_insensitive_duplicates_and_blanks():
    assert normalize_saved_choices([
        "Pequenas Histórias, Grandes Lições",
        " ",
        "pequenas histórias, grandes lições",
        "Natal",
    ]) == ["Pequenas Histórias, Grandes Lições", "Natal"]


def test_normalize_saved_choices_preserves_current_when_not_saved():
    assert normalize_saved_choices(["Coleção A"], current="Coleção B") == ["Coleção A", "Coleção B"]

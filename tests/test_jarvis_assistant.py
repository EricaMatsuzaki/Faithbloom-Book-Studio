import jarvis_assistant as jarvis


def test_jarvis_understands_bible_children_story():
    result = jarvis.interpret_request("Crie uma história infantil baseada em Filipenses 4:13 para 3–8 anos")
    assert result["project_type"] == "children_story"
    assert result["origin"] == "bible"
    assert result["editorial_line"] == "christian"
    assert "bible_guard" in result["route_plan"]["route"]


def test_jarvis_routes_coloring_without_duplicate_translation_or_distribution():
    result = jarvis.interpret_request("Quero um livro de colorir infantil")
    route = result["route_plan"]["route"]
    assert "coloring_book_studio" in route
    assert route.count("translation_localization") == 1
    assert route.count("publishing_distribution_center") == 1
    assert result["anti_duplication"]["ok"] is True


def test_jarvis_detects_teen_study_request():
    result = jarvis.interpret_request("Crie uma apostila para adolescente estudar para o JLPT")
    assert result["project_type"] == "study_book"
    assert result["audience"] == "teen"


def test_jarvis_can_request_existing_derived_studios():
    result = jarvis.interpret_request("Crie uma história infantil e depois faça audiobook, animação e música")
    route = result["route_plan"]["route"]
    assert "audiobook_studio" in route
    assert "animation_video" in route
    assert "music" in route


def test_jarvis_never_auto_publishes():
    result = jarvis.interpret_request("Crie uma história infantil")
    assert result["route_plan"]["auto_publish"] is False
    assert result["requires_author_approval"] is True

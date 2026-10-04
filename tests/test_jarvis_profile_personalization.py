from pathlib import Path


JARVIS_PAGE = Path("pages/00_🤖_Jarvis.py")


def test_jarvis_home_uses_active_workspace_profile_for_greeting():
    source = JARVIS_PAGE.read_text(encoding="utf-8")
    assert "list_workspace_profiles" in source
    assert "faithbloom_workspace_profile_id" in source
    assert "active_workspace_name" in source
    assert "Oi, Erica!" not in source


def test_jarvis_home_filters_recent_projects_by_active_workspace_profile():
    source = JARVIS_PAGE.read_text(encoding="utf-8")
    assert "visible_project_cards(all_home_catalog, active_workspace_profile_id)" in source

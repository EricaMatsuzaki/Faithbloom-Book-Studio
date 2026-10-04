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


def test_jarvis_home_uses_canonical_character_masters():
    source = JARVIS_PAGE.read_text(encoding="utf-8")
    assert 'CANONICAL_HOME_COLLECTION = "Pequenas Histórias, Grandes Lições"' in source
    assert '_character_master_path("Manu")' in source
    assert '_character_master_path("Mel")' in source
    assert '_character_master_path("Téo")' in source
    assert 'carregar_personagem_oficial' in source
    assert 'color_master' in source


def test_jarvis_home_keeps_jarvis_inside_approved_banner_layout():
    source = JARVIS_PAGE.read_text(encoding="utf-8")
    assert 'chars, copy, bot = st.columns([1.08, 1.65, .78]' in source
    assert 'Oi! Eu sou o Jarvis.' in source
    assert 'home_action_{key}' in source
    assert 'jarvis_compose' in source


def test_jarvis_home_uses_compact_interactive_jarvis_and_master_sidebar_card():
    source = JARVIS_PAGE.read_text(encoding="utf-8")
    assert "compact=True" in source
    assert "Manu Master" in source
    assert "Mel Master" in source
    assert "Plano Profissional" in source


def test_jarvis_home_has_mobile_specific_layout_contract():
    source = JARVIS_PAGE.read_text(encoding="utf-8")
    assert "@media(max-width:560px)" in source
    assert 'grid-template-areas:"chars copy" "bot bot"' in source
    assert 'active_workspace_name.split()[0]' in source
    assert "Diagnóstico de velocidade" in source

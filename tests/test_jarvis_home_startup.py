"""Exercise the real home while its profile/catalog storage is delayed."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from streamlit.testing.v1 import AppTest

import family_profiles
import jarvis_heart_mic
import painel_projetos
import painel_visual


ROOT = Path(__file__).resolve().parents[1]
PROFILES = [
    {"id": "owner", "display_name": "Erica"},
    {"id": "daughter", "display_name": "Larissa"},
]


@pytest.mark.parametrize("delayed_service", ["profiles", "projects"])
def test_home_emits_original_banner_and_real_heart_before_storage_finishes(monkeypatch, delayed_service):
    events = []
    entered = Event()
    release = Event()
    render_banner = painel_visual.render_banner
    heart_mic = jarvis_heart_mic.heart_mic

    def banner(*args, **kwargs):
        render_banner(*args, **kwargs)
        events.append("banner")

    def heart(*args, **kwargs):
        result = heart_mic(*args, **kwargs)
        events.append("heart")
        return result

    def pause(service):
        events.append(service)
        if service == delayed_service:
            entered.set()
            if not release.wait(timeout=10):
                raise TimeoutError("Test did not release its storage barrier")

    def profiles():
        pause("profiles")
        return PROFILES

    def projects(profile_id):
        pause("projects")
        assert profile_id == "owner"
        return []

    monkeypatch.setattr(painel_visual, "render_banner", banner)
    monkeypatch.setattr(jarvis_heart_mic, "heart_mic", heart)
    monkeypatch.setattr(family_profiles, "list_workspace_profiles", profiles)
    monkeypatch.setattr(painel_projetos, "available_projects", projects)

    app = AppTest.from_file(ROOT / "app.py")
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(app.run, timeout=15)
        try:
            assert entered.wait(timeout=10), "Home never reached the delayed storage service"
            assert not pending.done(), "Storage delay did not hold the page run"
            assert "banner" in events and "heart" in events
            assert events.index("banner") < events.index(delayed_service)
            assert events.index("heart") < events.index(delayed_service)
        finally:
            release.set()
        pending.result(timeout=15)

    assert not app.exception
    assert sum("fb-banner-frame" in item.value for item in app.markdown) == 1
    assert events.count("profiles") == 1
    assert events.count("projects") == 1
    assert app.selectbox(key="fb_home_profile").value == "owner"


def test_home_profile_switch_clears_previous_reply_before_loading_new_catalog(monkeypatch):
    catalog_profiles = []

    def projects(profile_id):
        catalog_profiles.append(profile_id)
        return []

    monkeypatch.setattr(family_profiles, "list_workspace_profiles", lambda: PROFILES)
    monkeypatch.setattr(painel_projetos, "available_projects", projects)
    app = AppTest.from_file(ROOT / "app.py")
    app.session_state["faithbloom_workspace_profile_id"] = "owner"
    app.session_state["jarvis_reply"] = "Owner's private reply"
    app.session_state["jarvis_conversation_history"] = [
        {"role": "assistant", "text": "Owner's private reply"},
    ]
    app.run(timeout=15)
    assert not app.exception
    assert app.chat_message

    app.selectbox(key="fb_home_profile").set_value("daughter").run(timeout=15)

    assert not app.exception
    assert catalog_profiles == ["owner", "daughter"]
    assert app.session_state["faithbloom_workspace_profile_id"] == "daughter"
    assert not app.session_state["jarvis_reply"]
    assert not app.chat_message
    assert all("Owner's private reply" not in item.value for item in app.markdown)
    assert any('Oi, Larissa!' in item.value for item in app.markdown)

"""Home contracts: personal workspace, supplied artwork and real Jarvis input."""
import ast
import base64
from contextlib import nullcontext
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

import painel_visual


ROOT = Path(__file__).resolve().parents[1]
JARVIS_PAGE = ROOT / "pages/00_🤖_Jarvis.py"


def _page_tree():
    return ast.parse(JARVIS_PAGE.read_text(encoding="utf-8"))


class _BannerUi:
    """Capture banner rendering without running the page or accessing services."""

    def __init__(self, motion):
        self.motion = motion
        self.session_state = {"fb_banner_motion": motion}
        self.markup = ""

    def container(self, **_kwargs):
        return nullcontext()

    def toggle(self, *_args, **_kwargs):
        return self.motion

    def markdown(self, markup, **_kwargs):
        self.markup += markup


class _BannerMarkup(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.frames = []
        self.images = []
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append(tag)
        if tag == "div" and "fb-banner-frame" in attributes.get("class", "").split():
            self.frames.append(attributes)
        elif tag == "img":
            self.images.append(attributes)


def _render_banner(monkeypatch, *, motion=True, name="Erica", compact=True, show_control=True):
    ui = _BannerUi(motion)
    monkeypatch.setattr(painel_visual, "st", ui)
    painel_visual.render_banner(name, compact_desktop=compact, show_motion_control=show_control)
    return ui.markup, _BannerMarkup(ui.markup)


@pytest.mark.parametrize("selected, expected", [("daughter", "daughter"), ("missing", "owner")])
def test_jarvis_home_resolves_active_workspace_profile(selected, expected):
    profiles = [{"id": "owner", "display_name": "Erica"}, {"id": "daughter", "display_name": "Larissa"}]
    session = {"faithbloom_workspace_profile_id": selected}
    namespace = {
        "st": SimpleNamespace(session_state=session),
        "list_workspace_profiles": lambda: profiles,
        "get_workspace_profile": lambda profile_id: next(p for p in profiles if p["id"] == profile_id),
    }
    resolver = next(node for node in _page_tree().body if isinstance(node, ast.FunctionDef) and node.name == "_active_workspace_profile")
    exec(compile(ast.Module(body=[resolver], type_ignores=[]), str(JARVIS_PAGE), "exec"), namespace)
    assert namespace["_active_workspace_profile"]()["id"] == expected
    assert session["faithbloom_workspace_profile_id"] == expected


def test_jarvis_home_passes_active_profile_to_project_catalog():
    calls = [node for node in ast.walk(_page_tree()) if isinstance(node, ast.Call)]
    assert any(
        isinstance(call.func, ast.Name) and call.func.id == "available_projects"
        and call.args and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "active_workspace_profile_id"
        for call in calls
    )


@pytest.mark.parametrize("name, dimensions", [
    ("faithbloom-welcome.jpg", (1280, 575)),
    ("faithbloom-dashboard-reference.jpg", (1280, 720)),
    ("faithbloom-mobile-reference.jpg", (720, 1280)),
])
def test_supplied_artwork_exists_at_original_dimensions(name, dimensions):
    with Image.open(ROOT / "assets" / name) as image:
        assert image.size == dimensions
        assert image.format == "JPEG"


@pytest.mark.parametrize("compact", [True, False])
def test_banner_embeds_one_complete_original_png_on_every_screen(monkeypatch, compact):
    _markup, banner = _render_banner(monkeypatch, compact=compact)
    assert len(banner.images) == len(banner.frames) == 1
    image = banner.images[0]
    assert image["src"].startswith("data:image/png;base64,")
    data = base64.b64decode(image["src"].split(",", 1)[1], validate=True)
    assert data == painel_visual.BANNER_PATH.read_bytes()
    with Image.open(BytesIO(data)) as artwork:
        assert artwork.format == "PNG"
        assert artwork.size == (1672, 941)
        assert (int(image["width"]), int(image["height"])) == artwork.size
    assert image["alt"]


@pytest.mark.parametrize("name, mime", [
    ("faithbloom-dashboard-reference.jpg", "image/jpeg"),
    ("faithbloom-studio-banner.png", "image/png"),
])
def test_artwork_embedding_uses_original_format_and_bytes(name, mime):
    embedded = painel_visual._asset(name)
    assert embedded.startswith(f"data:{mime};base64,")
    original = painel_visual.BANNER_PATH if name == "faithbloom-studio-banner.png" else ROOT / "assets" / name
    assert base64.b64decode(embedded.split(",", 1)[1], validate=True) == original.read_bytes()


def test_banner_personalizes_accessible_greeting_without_painting_over_art(monkeypatch):
    markup, banner = _render_banner(monkeypatch, name="Larissa <script>alert(1)</script>")
    assert "Oi, Larissa &lt;script&gt;alert(1)&lt;/script&gt;!" in markup
    assert "script" not in banner.tags
    assert '<h1 class="fb-sr-only"' in markup
    assert "fb-greeting" not in markup
    assert "svg" not in banner.tags
    assert "span" not in banner.tags


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("show_control", [True, False])
def test_banner_movement_can_be_paused_without_changing_original_art(monkeypatch, enabled, show_control):
    markup, banner = _render_banner(monkeypatch, motion=enabled, show_control=show_control)
    assert len(banner.images) == 1
    assert ("fb-banner-animated" in banner.frames[0]["class"].split()) is enabled
    data = base64.b64decode(banner.images[0]["src"].split(",", 1)[1], validate=True)
    assert data == painel_visual.BANNER_PATH.read_bytes()
    assert "fb-petal" not in markup
    assert "fb-butterfly" not in markup
    assert "fb-greeting" not in markup


def test_jarvis_home_keeps_one_real_heart_control_and_audio_fallback():
    calls = [node for node in ast.walk(_page_tree()) if isinstance(node, ast.Call)]
    hearts = [call for call in calls if isinstance(call.func, ast.Name) and call.func.id == "heart_mic"]
    assert len(hearts) == 1
    kwargs = {keyword.arg: keyword.value for keyword in hearts[0].keywords}
    assert isinstance(kwargs["key"], ast.Constant) and kwargs["key"].value == "jarvis_heart_control"
    assert isinstance(kwargs["compact"], ast.Constant) and kwargs["compact"].value is False
    assert any(isinstance(call.func, ast.Attribute) and call.func.attr == "audio_input" for call in calls)


def test_jarvis_home_keeps_multimodal_composer_and_real_request_dispatch():
    source = JARVIS_PAGE.read_text(encoding="utf-8")
    assert 'with st.popover("📎"' in source
    assert "SUPPORTED_UPLOAD_TYPES" in source
    assert "jarvis_multimodal_uploads" in source
    assert "jarvis_text_form" in source
    assert "Enviar para o Jarvis" in source
    assert "_prepare_multimodal_handoff(typed, list(uploads or []))" in source
    assert "_process_request(typed, project_progress=project_progress)" in source

from io import BytesIO

from PIL import Image

import editorial_remaster_visual_autopilot as visual_auto


class _ImageObject:
    def __init__(self, name: str, size: tuple[int, int]):
        self.name = name
        buf = BytesIO()
        Image.new("RGB", size).save(buf, format="PNG")
        self.data = buf.getvalue()


class _Page:
    def __init__(self, *images):
        self.images = list(images)


def test_dominant_page_image_chooses_largest_decodable_asset():
    page = _Page(
        _ImageObject("small.png", (100, 100)),
        _ImageObject("large.png", (900, 700)),
        _ImageObject("medium.png", (300, 400)),
    )
    selected = visual_auto._dominant_page_image(page)
    assert selected is not None
    _, name, size = selected
    assert name == "large.png"
    assert size == (900, 700)


def test_paid_generation_is_never_assumed_without_explicit_run_consent():
    result = visual_auto.generate_visual_candidates(
        {"id": "p1", "pasta": "/tmp/not-used"},
        {"run_id": "r1", "settings": {"allow_paid_image_generation": False}},
    )
    assert result["authorized"] is False
    assert result["generated"] == 0
    assert result["visual_candidates_auto_approved"] if "visual_candidates_auto_approved" in result else True


def test_missing_paid_consent_path_does_not_require_openrouter_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = visual_auto.generate_visual_candidates(
        {"id": "p1", "pasta": "/tmp/not-used"},
        {"run_id": "r1", "settings": {}},
    )
    assert result["authorized"] is False
    assert "não foi autorizada" in result["note"]

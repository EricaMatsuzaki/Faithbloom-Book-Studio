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


class _BrokenPage:
    @property
    def images(self):
        raise RuntimeError("Stream has ended unexpectedly")


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


def test_broken_embedded_stream_is_skipped_instead_of_raising():
    assert visual_auto._dominant_page_image(_BrokenPage()) is None


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


def test_paid_generation_without_runtime_key_becomes_safe_unresolved(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = visual_auto.generate_visual_candidates(
        {"id": "p1", "pasta": "/tmp/not-used"},
        {"run_id": "r1", "settings": {"allow_paid_image_generation": True}},
    )
    assert result["authorized"] is True
    assert result["generated"] == 0
    assert result["unresolved"][0]["motivo"] == "openrouter_key_indisponivel"


def test_generation_stream_failure_is_isolated_to_asset(monkeypatch, tmp_path):
    source = tmp_path / "page.png"
    Image.new("RGB", (32, 32)).save(source)
    master = tmp_path / "master.png"
    Image.new("RGB", (32, 32)).save(master)

    plan = {
        "vinculos": {"style_id": "style-1"},
        "assets_detectados": [{"id": "a1", "pagina": 5, "arquivo": str(source)}],
        "versoes_assets": [],
        "decisoes": [],
    }
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(visual_auto, "carregar_plano_restauracao", lambda project: plan)
    monkeypatch.setattr(visual_auto, "_existing_run_version", lambda *args: {})
    monkeypatch.setattr(
        visual_auto,
        "contexto_cena_para_asset",
        lambda *_: {"numero": 1, "personagem_principal": "Mel", "texto_revisado": "Texto"},
    )
    monkeypatch.setattr(visual_auto, "_characters_for_context", lambda *_: [{"id": "mel", "nome": "Mel"}])
    monkeypatch.setattr(visual_auto, "_master_refs", lambda *_: [str(master)])
    monkeypatch.setattr(visual_auto, "montar_prompt_restauracao", lambda *args, **kwargs: "prompt")
    monkeypatch.setattr(visual_auto, "registrar_decisao", lambda *args, **kwargs: {})

    def _broken_generation(*args, **kwargs):
        raise RuntimeError("Stream has ended unexpectedly")

    monkeypatch.setattr(visual_auto, "gerar_variacao_ia", _broken_generation)

    result = visual_auto.generate_visual_candidates(
        {"id": "p1", "pasta": str(tmp_path)},
        {"run_id": "r1", "settings": {"allow_paid_image_generation": True}},
    )
    assert result["generated"] == 0
    assert result["unresolved"][0]["motivo"] == "geracao_visual_indisponivel"
    assert "Stream has ended unexpectedly" in result["unresolved"][0]["error"]

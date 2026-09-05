from copy import deepcopy
from unittest.mock import Mock
import pytest
import character_guide as guide
import asset_library as library


def concepts():
    return [{"id": key, "cenario": f"jardim-{key}", "poses": {"Mel": f"pose-{key}"},
             "acao": "olhar vaso", "emocao": "curiosidade", "psicologia_cores": "verde suave",
             "iluminacao": f"luz-{key}", "camera": "plano aberto"} for key in "ABC"]


def test_mix_transmits_actual_fields_without_mutating_proposals():
    ideas = concepts()
    original = deepcopy(ideas)
    mixed = guide.combine_scene_concepts(ideas, "A", scenario_id="A", pose_id="C", lighting_id="B")
    prompt = guide.compose_scene_prompt(mixed, [{"nome": "Mel", "dna": {}, "metadata": {"usos_permitidos": ["story"]}}])
    assert all(detail in prompt for detail in ("jardim-A", "pose-C", "luz-B"))
    assert "pose-A" not in prompt and "luz-A" not in prompt
    assert ideas == original


@pytest.mark.parametrize("raw", [[{}, {}, {}], concepts()[:2], concepts()+[concepts()[0]],
    [dict(concepts()[0], iluminacao=" "), *concepts()[1:]],
    [dict(concepts()[0], id="B"), *concepts()[1:]],
    [dict(concepts()[0], poses={"Mel": " "}), *concepts()[1:]]])
def test_reject_incomplete_duplicate_or_wrong_count(raw):
    with pytest.raises(ValueError):
        guide._normalize_scene_ideas(raw, 3)


@pytest.mark.parametrize("usage,allowed", [("cover", ["story"]), ("marketing", ["cover"]),
    ("printable", ["activity"]), ("story", [])])
def test_denied_usage_never_calls_image_api(monkeypatch, usage, allowed):
    image_api = Mock()
    monkeypatch.setattr(guide, "gerar_imagem", image_api)
    character = {"nome": "Mel", "metadata": {"usos_permitidos": allowed}}
    with pytest.raises(ValueError):
        guide.generate_character_variations(character, "pedido", usage=usage)
    with pytest.raises(ValueError):
        guide.generate_scene_assets(concepts()[0], [character], usage=usage)
    image_api.assert_not_called()


def test_visual_status_filter_precedes_pagination(monkeypatch):
    assets = [{"id": str(i), "status": "active", "media_kind": "image", "criada_em": i,
               "visual_status": "APPROVED_VARIATION" if i < 80 else "VARIATION_CANDIDATE"}
              for i in range(200)]
    monkeypatch.setattr(library, "_all_assets", lambda: assets)
    first = library.list_assets({"visual_status": "APPROVED_VARIATION"}, page_size=72)
    second = library.list_assets({"visual_status": "APPROVED_VARIATION"}, page_size=72, page=2)
    assert first["total"] == 80 and first["pages"] == 2
    assert len(first["items"]) == 72 and len(second["items"]) == 8
    assert {x["id"] for x in first["items"]}.isdisjoint(x["id"] for x in second["items"])


def test_line_art_uses_selected_file_and_creates_unapproved_derivative(monkeypatch, tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    asset = {"id": "selected", "nome": "Mel no jardim", "caminho_arquivo": str(source),
             "metadata": {"personagens": ["Mel", "Manu"]}, "approved": True}
    monkeypatch.setattr(guide, "get_asset", lambda *a, **kw: deepcopy(asset))
    image_api = Mock(return_value="generated.png")
    monkeypatch.setattr(guide, "gerar_imagem", image_api)
    persist = Mock(return_value={"id": "new", "approved": False})
    monkeypatch.setattr(guide, "_persist_generated", persist)
    result = guide.generate_asset_line_art("selected")
    assert image_api.call_args.kwargs["imagem_base"] == str(source)
    saved = persist.call_args.kwargs
    assert saved["base_asset_id"] == "selected"
    assert saved["visual_status"] == guide.VARIATION_STATUS
    assert saved["metadata"]["transformation"] == "line_art"
    assert saved["metadata"]["personagens"] == ["Mel", "Manu"]
    assert result["id"] != asset["id"] and not result["approved"]
    assert source.read_bytes() == b"source"


def test_missing_line_art_source_does_not_generate(monkeypatch):
    monkeypatch.setattr(guide, "get_asset", lambda _: None)
    api = Mock()
    monkeypatch.setattr(guide, "gerar_imagem", api)
    with pytest.raises(ValueError):
        guide.generate_asset_line_art("missing")
    api.assert_not_called()


def test_quality_gate_runs_pytest_and_propagates_failure(monkeypatch):
    import qa_release
    run = Mock(return_value=Mock(stdout="1 failed", stderr="", returncode=1))
    monkeypatch.setattr(qa_release.subprocess, "run", run)
    assert not qa_release.rodar_unit_tests()["ok"]
    assert run.call_args.args[0][1:] == ["-m", "pytest", "tests", "-q"]


def test_line_art_page_accepts_gallery_selection_without_book(monkeypatch, tmp_path):
    from pathlib import Path
    from PIL import Image
    from streamlit.testing.v1 import AppTest
    import book_doctor
    source = tmp_path / "image.png"
    Image.new("RGB", (8, 8), "white").save(source)
    assets = {
        "selected": {"id": "selected", "nome": "Mel", "caminho_arquivo": str(source)},
        "candidate": {"id": "candidate", "nome": "Line Art", "caminho_arquivo": str(source), "approved": False},
    }
    monkeypatch.setattr(library, "get_asset", lambda aid: assets.get(aid))
    generate = Mock(return_value=assets["candidate"])
    monkeypatch.setattr(guide, "generate_asset_line_art", generate)
    monkeypatch.setattr(book_doctor, "listar_projetos", Mock(side_effect=AssertionError("No book required")))
    page = Path(__file__).resolve().parents[1] / "pages/20_🖍️_Coloring_Book_Doctor.py"
    app = AppTest.from_file(str(page))
    app.session_state["faithbloom_selected_asset_id"] = "selected"
    app.run()
    assert not app.exception
    generate.assert_not_called()
    app.button(key="selected_line_generate").click().run()
    assert not app.exception
    generate.assert_called_once_with("selected")
    assert app.session_state["line_result_selected"] == "candidate"
    assert app.button(key="selected_line_approve")

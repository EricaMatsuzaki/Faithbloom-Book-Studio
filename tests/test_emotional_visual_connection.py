"""Behavioral contracts: approved canonical emotion reaches actual visual calls."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

import orchestrator_visual as ov
import visual_execution as ve
import comic_studio as comics
from emotional_visual_binding import (
    prepare_emotional_binding, approve_emotional_binding, require_emotional_binding,
    source_for_plan, direction_prompt,
)
from test_visual_execution_integration import project, choose_scene, bind_book
from test_comic_studio import isolated, source, visual_project as comic_visual_project
from test_visual_execution_ui_workflow import visual_project


def approve(plan, emotion="tristeza", intensity=4):
    draft = prepare_emotional_binding(plan)
    rows = draft["emotional_binding"]["scenes"]
    rows[0]["direcao"].update(emocao_narrativa=emotion, subemocao="consolo", intensidade=intensity,
                               transicao_emocional="tristeza → esperança")
    rows[0]["instrucao_autora"] = "Azul suave no ambiente; preservar estrelas e verde dos olhos."
    return ov.save_visual_plan(approve_emotional_binding(plan, rows, reviewed=True, reviewer="Erica"))


def test_preparation_never_approves_or_spends_and_legacy_final_is_blocked(project):
    plan = ov.load_visual_plan(project["plan"]["id"])
    choose_scene(project)
    before = deepcopy(ve.list_visual_operations(plan["id"]))
    draft = ov.save_visual_plan(prepare_emotional_binding(plan))
    assert draft["emotional_binding"]["approval"] is None
    assert not any(item["aprovado"] for item in draft["emotional_binding"]["scenes"])
    for callback in (
        lambda: ve.generate_world_candidates(plan["id"], project["world"]["id"], confirmed=True),
        lambda: ve.generate_scene_options(plan["id"], "1", "Mel olha.", confirmed=True),
        lambda: ve.generate_selected_scene(plan["id"], "1", confirmed=True),
    ):
        with pytest.raises(PermissionError, match="mapa emocional"):
            callback()
    assert ve.list_visual_operations(plan["id"]) == before
    ve.client.gerar_imagem.assert_not_called()
    # Reading the saved legacy/draft plan still works.
    assert ov.load_visual_plan(plan["id"])["id"] == plan["id"]


def test_exact_emotion_reaches_real_director_and_final_image_over_llm_suggestions(project):
    plan = approve(ov.load_visual_plan(project["plan"]["id"]))
    original = Path(project["master"]).read_bytes()
    operation = ve.generate_scene_options(plan["id"], "opening", "Mel contempla o jardim.", confirmed=True, source_scene_number=1)
    args, _ = ve.client.chamar_llm.call_args
    for value in ("tristeza", "consolo", "Intensidade 4/5", "tristeza → esperança", "azul-claro", "Azul suave no ambiente"):
        assert value in args[0] + args[1]
    for option in operation["results"][0]["ideas"]:
        assert option["emocao"] == "tristeza"
        assert "azul-claro" in option["psicologia_cores"]
        assert option["iluminacao"] == plan["emotional_binding"]["scenes"][0]["direcao"]["luz_emocional"]
    ve.select_scene_option(plan["id"], "opening", "B")
    result = ve.generate_selected_scene(plan["id"], "opening", confirmed=True)
    prompt = ve.client.gerar_imagem.call_args.args[0]
    assert "Intensidade 4/5" in prompt and "consolo" in prompt and "tristeza → esperança" in prompt
    assert "verde com brilho e estrelas" in prompt
    assert "nunca a identidade" in prompt and "revisão visual humana" in prompt
    assert Path(project["master"]).read_bytes() == original
    reopened = ov.load_visual_plan(plan["id"])
    assert require_emotional_binding(reopened)["approval"]["reviewer"] == "Erica"
    assert reopened["scene_execution"]["opening"]["source_scene_number"] == 1
    assert result["results"]


@pytest.mark.parametrize("change", ["style", "map", "narrative", "character"])
def test_approved_direction_invalidates_before_any_new_provider_call(project, change):
    plan = approve(ov.load_visual_plan(project["plan"]["id"]))
    ve.generate_scene_options(plan["id"], "1", "Mel no jardim.", confirmed=True)
    ve.select_scene_option(plan["id"], "1", "A")
    plan = ov.load_visual_plan(plan["id"])
    if change == "style":
        plan["style_master"] = {"name": "Novo estilo"}
    elif change == "map":
        plan["emotional_binding"]["scenes"][0]["direcao"]["intensidade"] = 5
    elif change == "narrative":
        plan["story_text"] = "Outra narrativa."
    else:
        plan["characters"][0]["name"] = "Outro personagem"
    ov.save_visual_plan(plan)
    with pytest.raises(PermissionError):
        ve.generate_selected_scene(plan["id"], "1", confirmed=True)
    ve.client.gerar_imagem.assert_not_called()


def test_arbitrary_key_requires_explicit_exact_origin_scene(project):
    with pytest.raises(PermissionError, match="Vincule explicitamente"):
        ve.generate_scene_options(project["plan"]["id"], "unrelated", "Outro texto.", confirmed=True)
    with pytest.raises(PermissionError):
        ve.generate_scene_options(project["plan"]["id"], "unrelated", "Outro texto.", confirmed=True, source_scene_number=999)
    ve.client.chamar_llm.assert_not_called()


def test_other_same_title_source_cannot_inherit_emotional_approval(project):
    plan = approve(ov.load_visual_plan(project["plan"]["id"]))
    bind_book(project)
    moved = ov.load_visual_plan(plan["id"])
    with pytest.raises(PermissionError, match="origem mudou|identidade de origem"):
        require_emotional_binding(moved)
    with pytest.raises(PermissionError):
        ve.generate_world_candidates(plan["id"], project["world"]["id"], confirmed=True)
    ve.client.gerar_imagem.assert_not_called()


def test_world_direction_is_context_and_original_master_bytes_survive(project):
    plan = approve(ov.load_visual_plan(project["plan"]["id"]))
    original_world = deepcopy(ov.load_world_master(project["world"]["id"]))
    result = ve.generate_world_candidates(plan["id"], project["world"]["id"], confirmed=True)
    for call in ve.client.gerar_imagem.call_args_list:
        prompt = call.args[0]
        assert "azul-claro" in prompt and "não recolorir o Master canônico" in prompt
        assert "não aplicar todas as paletas ao mesmo tempo" in prompt
    current = ov.load_world_master(project["world"]["id"])
    assert current["reference_assets"] == original_world["reference_assets"]
    assert current["status"] == original_world["status"]
    assert len(result["results"]) == 3


def test_approval_requires_real_review_and_rejects_fake_palette_or_wrong_scene(project):
    plan = ov.load_visual_plan(project["plan"]["id"])
    rows = prepare_emotional_binding(plan)["emotional_binding"]["scenes"]
    with pytest.raises(PermissionError):
        approve_emotional_binding(plan, rows, reviewed=False, reviewer="Erica")
    with pytest.raises(PermissionError):
        approve_emotional_binding(plan, rows, reviewed=True, reviewer="")
    bad = deepcopy(rows)
    bad[0]["numero"] = 999
    with pytest.raises(ValueError):
        approve_emotional_binding(plan, bad, reviewed=True, reviewer="Erica")
    rows[0]["direcao"].update(cor_principal="PRETO INVENTADO", emocao_narrativa="tristeza")
    saved = approve_emotional_binding(plan, rows, reviewed=True, reviewer="Erica")
    assert saved["emotional_binding"]["scenes"][0]["direcao"]["cor_principal"] == "azul-claro"


def test_private_canonical_source_needs_current_consent_even_with_approved_map(project):
    from governance_runtime import GovernanceBlocked
    _, reference = bind_book(project)
    state = project["backend"].get_json(reference.removeprefix("fb://"))
    state["real_experience"] = {"consent_confirmed": True, "original_account": "PRIVATE-NOT-IN-BINDING"}
    project["backend"].put_json(reference.removeprefix("fb://"), state)
    plan = approve(ov.load_visual_plan(project["plan"]["id"]))
    assert "PRIVATE-NOT-IN-BINDING" not in json.dumps(plan["emotional_binding"])
    with pytest.raises(GovernanceBlocked):
        ve.generate_scene_options(plan["id"], "7", "Mel no jardim.", confirmed=True)
    ve.client.chamar_llm.assert_not_called()
    ve.generate_scene_options(plan["id"], "7", "Mel no jardim.", confirmed=True, consent_confirmed=True)
    assert ve.client.chamar_llm.call_count == 1


def test_comic_panel_inherits_selected_canonical_scene_and_changed_link_blocks_old_direction(source, isolated, tmp_path, monkeypatch):
    source["cenas_texto"][0].update(emocao="tristeza", intensidade_emocional=4, emocao_secundaria="consolo", transicao_emocional="tristeza → esperança", instrucao_emocional="Preservar o brilho verde.")
    import armazenamento
    armazenamento.atualizar_livro_salvo(source["storage_path"], source)
    project, plan, calls, _ = comic_visual_project(source, tmp_path, monkeypatch)
    result = comics.generate_panel_options(project, "1:1", confirmed=True)
    assert result["results"][0]["ideas"][0]["emocao"] == "tristeza"
    comics.select_panel_direction(project, "1:1", "A")
    comics.generate_panel_images(project, "1:1", confirmed=True)
    assert "azul-claro" in calls["images"][0][0][0]
    assert "Intensidade 4/5" in calls["images"][0][0][0]
    comics.link_panel_emotion(project, "1:1", 2, reviewed=True)
    with pytest.raises(PermissionError, match="Escolha e aprove"):
        comics.generate_panel_images(project, "1:1", confirmed=True)
    assert len(calls["images"]) == 1
    reopened = comics.load_comic(project["storage_path"])
    assert reopened["comic_product"]["panels"]["1:1"]["emotional_source"]["scene_number"] == 2


def test_emotional_review_ui_saves_explicit_approval_without_provider(visual_project):
    from test_visual_execution_ui_workflow import _app, _element
    p = visual_project
    plan = ov.load_visual_plan(p["plan"]["id"])
    plan["emotional_binding"]["approval"] = None
    ov.save_visual_plan(plan)
    app = _app(p)
    principal = next(widget for widget in app.text_input if widget.label == "Emoção principal")
    principal.set_value("tristeza")
    next(widget for widget in app.text_input if widget.label == "Subemoção").set_value("consolo")
    next(widget for widget in app.slider if widget.label == "Intensidade emocional").set_value(5)
    _element(app.text_input, "Responsável pela revisão emocional").set_value("Erica")
    _element(app.checkbox, "Revisei a direção emocional de todas as cenas e a preservação dos Masters").check().run(timeout=15)
    _element(app.button, "Aprovar e salvar este mapa emocional").click().run(timeout=15)
    assert not app.exception and not app.error
    saved = ov.load_visual_plan(plan["id"])
    first = require_emotional_binding(saved)["scenes"][0]
    assert first["direcao"]["emocao_narrativa"] == "tristeza"
    assert first["direcao"]["intensidade"] == 5 and first["direcao"]["cor_principal"] == "azul-claro"
    p["text_provider"].assert_not_called()
    p["image_provider"].assert_not_called()


def test_final_art_cannot_be_applied_to_another_emotional_scene(visual_project):
    p = visual_project
    result = ve.generate_selected_scene(p["plan"]["id"], "opening", confirmed=True)
    reference = p["reference"].removeprefix("fb://")
    before = p["backend"].get_bytes(reference)
    with pytest.raises(PermissionError, match="outra cena do mapa emocional"):
        ve.apply_scene_asset(p["plan"]["id"], "opening", result["results"][0]["asset_id"], scene_number=11, confirmed=True)
    assert p["backend"].get_bytes(reference) == before

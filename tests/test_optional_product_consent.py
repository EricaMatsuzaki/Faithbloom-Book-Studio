"""Optional product illustrations renew consent at the visual action boundary."""
import pytest
from streamlit.testing.v1 import AppTest

import editorial_dispatch as dispatch
import editorial_products as products
import orchestrator_visual as visual
import visual_execution as execution
from emotional_visual_binding import prepare_emotional_binding, approve_emotional_binding
from governance_runtime import GovernanceBlocked
from test_visual_execution_integration import project


@pytest.fixture
def private_product_plan(project):
    source = products.create_product("other", "Projeto pessoal adulto", "Refletir com cuidado",
        unit_count=1, custom_blocks=["Reflexão"], origin="real_experience", audience="adult")
    products.save_product(source)
    products.generate_product(source, lambda **_: {
        "title": "Um momento de cuidado", "objectives": ["Observar com atenção"], "source_refs": [],
        "blocks": [{"label": "Reflexão", "text": "Mel observa as flores e recorda um momento de cuidado."}]},
        confirmed=True, consent_confirmed=True)
    run = dispatch.attach_saved_product_run(source["storage_path"])
    original = project["plan"]
    plan = dispatch.bind_visual_plan_to_run(run["id"], characters=original["characters"],
        locations=original["locations"], optional_visual=True)
    dispatch.approve_run_content(run["id"])
    plan = visual.load_visual_plan(plan["id"])
    plan = visual.approve_character_candidate(plan, "mel", f"official:{project['character']['id']}",
        project["master_asset"]["storage_uri"])
    plan = visual.link_location_approval(plan, "garden", project["world"]["id"])
    plan = visual.approve_style(plan, {"name": "Arte editorial adulta com luz delicada"})
    prepared = prepare_emotional_binding(plan)
    plan = visual.save_visual_plan(approve_emotional_binding(plan,
        prepared["emotional_binding"]["scenes"], reviewed=True, reviewer="Responsável"))
    return source, plan


def test_specialized_personal_source_requires_new_consent_before_scene_provider(project, private_product_plan):
    source, plan = private_product_plan
    # Consent already given to the text product is deliberately not reused for
    # this separate visual action, even though both use the same saved source.
    with pytest.raises(GovernanceBlocked):
        execution.generate_scene_options(plan["id"], "1", "Mel observa as flores.",
            confirmed=True, source_scene_number=1)
    execution.client.chamar_llm.assert_not_called()
    assert execution.list_visual_operations(plan["id"]) == []
    result = execution.generate_scene_options(plan["id"], "1", "Mel observa as flores.",
        confirmed=True, source_scene_number=1, consent_confirmed=True)
    execution.client.chamar_llm.assert_called_once()
    assert result["status"] == "complete"
    assert products.load_product(source["storage_path"])["book_id"] == source["book_id"]


def test_specialized_personal_source_renders_action_consent_checkbox(private_product_plan):
    _, plan = private_product_plan
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from orchestrator_visual import load_visual_plan\n"
        "from visual_execution_ui import _visual_data_consent\n"
        f"plan = load_visual_plan({plan['id']!r})\n"
        "st.write(_visual_data_consent(plan, 'test_product_options'))\n")
    app.run(timeout=20)
    assert not app.exception
    matches = [widget for widget in app.checkbox
        if widget.label == "Autorizo enviar os dados pessoais desta obra à IA somente para esta ação"]
    assert len(matches) == 1 and not matches[0].value
    matches[0].check().run(timeout=20)
    assert not app.exception
    assert matches[0].value

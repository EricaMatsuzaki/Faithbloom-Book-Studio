"""Specialized products reach the shared visual workflow without another purchase."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import character_guide as guide
import editorial_dispatch as dispatch
import editorial_generation_runtime as runtime
import editorial_products as products
import orchestrator_visual as visual
import storage_backend as storage
from test_editorial_generation_atomic import durable, product, provider


ROOT = Path(__file__).resolve().parents[1]


def _completed():
    value = product()
    products.generate_product(value, provider, confirmed=True)
    return value


def _widget(app, kind, label):
    return next(item for item in getattr(app, kind) if item.label == label)


def test_saved_product_attach_reuses_exact_identity_and_requires_optional_consent(durable):
    value = _completed()
    before = durable.get_bytes(runtime._path(value["storage_path"]))
    first = dispatch.attach_saved_product_run(value["storage_path"])
    second = dispatch.attach_saved_product_run(value["storage_path"])
    assert first["id"] == second["id"]
    assert second["source"]["book_id"] == value["book_id"]
    assert second["source_ref"] == value["storage_path"]
    assert second["route_plan"]["audience"] == "adult"
    assert len(products.list_products()) == 1
    with pytest.raises(PermissionError, match="opcionais"):
        dispatch.bind_visual_plan_to_run(first["id"], characters=[], locations=[])
    plan = dispatch.bind_visual_plan_to_run(first["id"], characters=[], locations=[], optional_visual=True)
    assert plan["optional_visual"] and plan["source_book_id"] == value["book_id"]
    assert plan["faixa_etaria"] == plan["editorial_audience"] == "adult"
    assert dispatch.validate_visual_source(plan)["book_id"] == value["book_id"]
    assert not plan["approvals"]["story"]
    assert durable.get_bytes(runtime._path(value["storage_path"])) == before


@pytest.mark.parametrize("attempt_state,status", [("running", "running"), ("uncertain", "needs_reconciliation"), ("raw", "save_failed")])
def test_active_or_unresolved_product_cannot_open_new_visual_plan(durable, attempt_state, status):
    value = _completed()
    run = dispatch.attach_saved_product_run(value["storage_path"])
    plan = dispatch.bind_visual_plan_to_run(run["id"], characters=[], locations=[], optional_visual=True)
    path = runtime._path(value["storage_path"])
    current = durable.get_json(path)
    execution = current["editorial_product"]["execution"]
    execution["attempts"][0]["state"] = attempt_state
    execution["status"] = status
    if attempt_state == "running":
        execution["claim"] = {"token": "active", "host": "host", "pid": 123, "owner_active": True}
    if attempt_state == "raw":
        execution["attempts"][0]["response"] = {"received": True}
    durable.put_json(path, current)
    before = durable.get_bytes(path)
    with pytest.raises(PermissionError):
        dispatch.attach_saved_product_run(value["storage_path"])
    with pytest.raises(PermissionError):
        dispatch.bind_visual_plan_to_run(run["id"], characters=[], locations=[], optional_visual=True)
    with pytest.raises(PermissionError):
        dispatch.validate_visual_source(plan)
    assert durable.get_bytes(path) == before
    assert dispatch.load_run(run["id"])["visual_plan_id"] == plan["id"]


def test_native_product_screen_opens_same_saved_product_and_real_orchestrator_creates_plan(durable, monkeypatch):
    import estilo
    import streamlit as st
    import ai_provider_router
    monkeypatch.setattr(estilo, "aplicar_estilo", lambda: None)
    forbidden = Mock(side_effect=AssertionError("Visual handoff cannot generate content"))
    monkeypatch.setattr(ai_provider_router, "chamar_llm", forbidden)
    switched = Mock()
    monkeypatch.setattr(st, "switch_page", switched)
    # AppTest executes each page as an isolated entrypoint, without the app's
    # multipage navigation registry. Leave passive links out of this harness.
    monkeypatch.setattr(st, "page_link", lambda *_a, **_k: None)
    from streamlit.delta_generator import DeltaGenerator
    monkeypatch.setattr(DeltaGenerator, "page_link", lambda *_a, **_k: None)
    value = _completed()
    before = durable.get_bytes(runtime._path(value["storage_path"]))
    app = AppTest.from_file(str(ROOT / "pages/55_📚_Produtos_Editoriais.py"))
    app.session_state["editorial_product_state"] = deepcopy(value)
    app.run(timeout=20)
    assert not app.exception
    _widget(app, "button", "Planejar ilustrações no Orquestrador").click().run(timeout=20)
    assert not app.exception
    switched.assert_called_once_with("pages/0_🤖_Orquestrador_FaithBloom.py")
    run_id = app.session_state["editorial_run_id"]
    run = dispatch.load_run(run_id)
    assert run["source_ref"] == value["storage_path"]
    central = AppTest.from_file(str(ROOT / "pages/0_🤖_Orquestrador_FaithBloom.py"))
    for key in ("editorial_run_id", "orchestrator_project_type", "orchestrator_origin", "orchestrator_audience", "orchestrator_editorial_line", f"optional_visual_{run_id}"):
        central.session_state[key] = app.session_state[key]
    central.run(timeout=20)
    assert not central.exception
    assert _widget(central, "checkbox", "Planejar ilustrações para este produto (opcional)").value
    _widget(central, "button", "🌱 Criar pré-voo visual").click().run(timeout=20)
    assert not central.exception
    plan = visual.load_visual_plan(dispatch.load_run(run_id)["visual_plan_id"])
    assert plan["source_ref"] == value["storage_path"]
    assert plan["editorial_audience"] == "adult"
    assert dispatch.validate_visual_source(plan)["book_id"] == value["book_id"]
    assert durable.get_bytes(runtime._path(value["storage_path"])) == before
    assert len(products.list_products()) == 1
    forbidden.assert_not_called()


@pytest.mark.parametrize("audience", ["teen", "adult", "custom"])
def test_scene_director_preserves_nonchild_audience_and_eye_identity(audience):
    character = {"nome": "Ana", "dna": {"descricao_master": "Ana", "campos_bloqueados": {"olhos": "verdes brilhantes"}, "variaveis_permitidas": ["pose"]}}
    captured = []
    ideas = [{"cenario": f"Ambiente {i}", "acao": "Observa a paisagem", "poses": {"Ana": "em pé"},
              "emocao": "confiança", "psicologia_cores": "azul no ambiente", "iluminacao": "luz suave", "camera": f"ângulo {i}", "por_que_funciona": "Fiel ao trecho"} for i in range(3)]
    def generate(system, instruction):
        captured.append((system, instruction))
        return {"ideas": ideas}
    result = guide.suggest_scene_concepts("Ana encontra um lugar tranquilo.", [character],
        project_context={"faixa_etaria": audience, "editorial_audience": audience}, text_generator=generate)
    system, instruction = captured[0]
    assert "especialista em direção de arte para livros infantis" not in system
    assert "leitura visual infantil" not in system
    assert f"'faixa_etaria': '{audience}'" in instruction
    assert "verdes brilhantes" in instruction
    assert all(item["editorial_context"]["editorial_audience"] == audience for item in result)

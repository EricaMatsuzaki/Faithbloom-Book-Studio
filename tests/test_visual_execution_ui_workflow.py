"""Author selection through the real multipage app, backed by real JSON/assets."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

import armazenamento
import character_universe
import editorial_dispatch as dispatch
import orchestrator_visual as ov
import storage_backend as storage
import visual_execution as ve
from asset_library import get_asset, update_asset


ROOT = Path(__file__).resolve().parents[1]
PAGE = "pages/0_🤖_Orquestrador_FaithBloom.py"


def _image(path, color):
    Image.new("RGB", (48, 32), color).save(path)
    return str(path)


def _element(items, label):
    return next(item for item in items if item.label == label)


@pytest.fixture
def visual_project(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(str(tmp_path / "durable"))
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    monkeypatch.setattr(ve.client.gemini_client, "GEMINI_API_KEY", "never-sent-test-key")
    monkeypatch.setattr(ve.client, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(ve.client, "PROVEDOR_TEXTO", "auto")
    monkeypatch.setattr(ve, "validar_orcamento", lambda _amount: None)
    master_path = _image(tmp_path / "master.png", "green")
    master_asset = armazenamento.salvar_na_galeria(master_path, "Mel")
    update_asset(master_asset["id"], approved=True, visual_status="COLOR_MASTER")
    character = character_universe.criar_personagem_oficial(
        "Coleção", "Mel", {"descricao_master": "Olhos verdes com estrelas e brilho",
        "campos_bloqueados": {"olhos": "Verdes com estrelas e brilho"}}, color_master=master_asset["storage_uri"],
    )
    world_asset = armazenamento.salvar_na_galeria(_image(tmp_path / "world.png", "pink"), "Jardim", tipo="cenario")
    world = ov.create_world_master("Coleção", "Jardim", "Flores e fonte", [world_asset["storage_uri"]])
    ov.approve_world_master(world["id"])
    old = _image(tmp_path / "old.png", "yellow")
    source = {"titulo": "Mesmo título", "colecao": "Coleção", "book_id": "book-a",
              "cenas_texto": [{"numero": 7, "texto": "Mel observa a fonte."}, {"numero": 11, "texto": "Mel retorna ao jardim."}],
              "cenas_imagem": [{"numero": 7, "caminho_arquivo": old, "aprovado": True}],
              "cenas_imagem_aprovadas": [7]}
    reference = armazenamento.salvar_livro(source)
    source["storage_path"] = reference
    armazenamento.atualizar_livro_salvo(reference, source)
    source = backend.get_json(reference.removeprefix("fb://"))
    other = {**deepcopy(source), "book_id": "book-b", "storage_path": ""}
    other_ref = armazenamento.salvar_livro(other)
    other["storage_path"] = other_ref
    armazenamento.atualizar_livro_salvo(other_ref, other)
    other = backend.get_json(other_ref.removeprefix("fb://"))
    plan = ov.create_visual_plan("book-a", source["titulo"], "Mel observa e retorna.",
                                 characters=[{"id": "mel", "name": "Mel"}], locations=[{"id": "garden", "name": "Jardim"}],
                                 generation_mode="economy", budget_limit_usd=3)
    plan = ov.approve_story(plan)
    plan = ov.approve_character_candidate(plan, "mel", f"official:{character['id']}", master_asset["storage_uri"])
    plan = ov.link_location_approval(plan, "garden", world["id"])
    plan = ov.approve_style(plan, {"name": "3D suave"})
    plan.update(source_ref=reference, source_fingerprint=dispatch.content_fingerprint(source), source_book_id="book-a")
    plan = ov.save_visual_plan(plan)
    concepts = {"ideas": [{"id": label, "titulo": f"Direção {label}", "cenario": f"jardim {label}", "acao": "Mel observa",
                            "poses": {"Mel": "sentada"}, "emocao": "curiosa", "camera": f"ângulo {label}",
                            "psicologia_cores": "verde delicado", "iluminacao": "manhã", "por_que_funciona": "Leitura clara"} for label in "ABC"]}
    text_provider = Mock(return_value=concepts)
    image_provider = Mock(return_value=_image(tmp_path / "candidate.png", "blue"))
    monkeypatch.setattr(ve.client, "chamar_llm", text_provider)
    monkeypatch.setattr(ve.client, "gerar_imagem", image_provider)
    ve.generate_scene_options(plan["id"], "opening", "Mel observa a fonte.", confirmed=True)
    ve.select_scene_option(plan["id"], "opening", "B")
    text_provider.reset_mock()
    return {"backend": backend, "plan": plan, "source": source, "reference": reference, "other": other, "other_ref": other_ref,
            "text_provider": text_provider, "image_provider": image_provider, "master_asset": master_asset,
            "master_bytes": Path(master_path).read_bytes(), "character": character}


def _app(project, open_state=None):
    app = AppTest.from_file(ROOT / "app.py").switch_page(PAGE)
    app.session_state["orchestrator_visual_plan_id"] = project["plan"]["id"]
    if open_state is not None:
        app.session_state["state"] = deepcopy(open_state)
    app.run(timeout=15)
    assert not app.exception
    return app


def _generate(app, project):
    _element(app.checkbox, "Confirmo gerar a ilustração da direção escolhida").check().run(timeout=15)
    _element(app.button, "Gerar ilustração").click().run(timeout=15)
    assert not app.exception
    project["image_provider"].assert_called_once()
    return ov.load_visual_plan(project["plan"]["id"])["scene_execution"]["opening"]["assets"][0]["asset_id"]


def _select_scene(app, number):
    selector = _element(app.selectbox, "Cena do livro que receberá a ilustração")
    assert selector.options == ["Cena 7 · Mel observa a fonte.", "Cena 11 · Mel retorna ao jardim."]
    selector.set_value(number).run(timeout=15)
    assert _element(app.button, "Usar esta ilustração no livro").disabled
    _element(app.checkbox, "Confirmo usar esta ilustração na cena escolhida do livro vinculado").check().run(timeout=15)
    assert not _element(app.button, "Usar esta ilustração no livro").disabled


def test_real_orchestrator_author_applies_candidate_to_exact_book_with_duplicate_titles(visual_project):
    p = visual_project
    app = _app(p, p["other"])
    asset_id = _generate(app, p)
    assert _element(app.button, "Usar esta ilustração no livro").disabled
    _select_scene(app, 7)
    before_other = p["backend"].get_bytes(p["other_ref"].removeprefix("fb://"))
    original_image = p["source"]["cenas_imagem"][0]["caminho_arquivo"]
    _element(app.button, "Usar esta ilustração no livro").click().run(timeout=15)
    assert not app.exception and not app.error
    saved = p["backend"].get_json(p["reference"].removeprefix("fb://"))
    assert saved["cenas_imagem"][0]["visual_asset_id"] == asset_id
    assert saved["cenas_imagem"][0]["numero"] == 7
    assert saved["cenas_imagem_aprovadas"] == [7]
    assert saved["historico_imagens_cenas"]["7"][0]["caminho_arquivo"] == original_image
    assert p["backend"].get_bytes(p["other_ref"].removeprefix("fb://")) == before_other
    assert app.session_state["state"] == p["other"]
    assert get_asset(p["master_asset"]["id"])["visual_status"] == "COLOR_MASTER"
    assert Path(storage.materializar(p["master_asset"]["storage_uri"])).read_bytes() == p["master_bytes"]
    assert character_universe.carregar_personagem_oficial(p["character"]["id"])["dna"] == p["character"]["dna"]
    assert any("Ilustração salva e aprovada na cena 7" in item.value for item in app.success)
    app.run(timeout=15)
    assert any("Ilustração escolhida para a cena 7" in item.value for item in app.success)
    assert p["image_provider"].call_count == 1
    p["text_provider"].assert_not_called()


def test_selection_refreshes_only_matching_open_book_from_fresh_disk_state(visual_project):
    p = visual_project
    app = _app(p, p["source"])
    asset_id = _generate(app, p)
    _select_scene(app, 11)
    newer = deepcopy(p["source"])
    newer["editorial_notes"] = "Metadado salvo em outra tela."
    armazenamento.atualizar_livro_salvo(p["reference"], newer)
    _element(app.button, "Usar esta ilustração no livro").click().run(timeout=15)
    assert not app.exception and not app.error
    assert app.session_state["state"]["editorial_notes"] == newer["editorial_notes"]
    assert app.session_state["state"]["storage_path"] == p["reference"]
    selected = next(row for row in app.session_state["state"]["cenas_imagem"] if row["numero"] == 11)
    assert selected["visual_asset_id"] == asset_id and selected["aprovado"]
    assert Path(selected["caminho_arquivo"]).is_file()
    old = next(row for row in app.session_state["state"]["cenas_imagem"] if row["numero"] == 7)
    assert Path(old["caminho_arquivo"]).read_bytes() == Path(storage.materializar(p["source"]["cenas_imagem"][0]["caminho_arquivo"])).read_bytes()


def test_changing_target_scene_requires_new_explicit_confirmation(visual_project):
    app = _app(visual_project)
    _generate(app, visual_project)
    _select_scene(app, 7)
    _element(app.selectbox, "Cena do livro que receberá a ilustração").set_value(11).run(timeout=15)
    assert _element(app.button, "Usar esta ilustração no livro").disabled
    assert not _element(app.checkbox, "Confirmo usar esta ilustração na cena escolhida do livro vinculado").value


def test_unbound_manual_plan_keeps_candidate_in_gallery_without_book_apply(visual_project):
    p = visual_project
    plan = ov.load_visual_plan(p["plan"]["id"])
    for key in ("source_ref", "source_fingerprint", "source_book_id"):
        plan.pop(key, None)
    ov.save_visual_plan(plan)
    app = _app(p, p["source"])
    _generate(app, p)
    assert any("mantém as candidatas na galeria" in item.value for item in app.info)
    assert not any(item.label == "Usar esta ilustração no livro" for item in app.button)
    assert p["backend"].get_json(p["reference"].removeprefix("fb://")) == p["source"]


@pytest.mark.parametrize("changed", ["text", "identity", "unavailable"])
def test_changed_or_unavailable_canonical_source_blocks_visual_ui_and_provider(visual_project, changed):
    p = visual_project
    app = _app(p)
    _element(app.checkbox, "Confirmo gerar a ilustração da direção escolhida").check().run(timeout=15)
    pending_generate = _element(app.button, "Gerar ilustração")
    source = deepcopy(p["source"])
    if changed == "text":
        source["cenas_texto"][0]["texto"] = "Texto revisado pela autora."
        armazenamento.atualizar_livro_salvo(p["reference"], source)
    elif changed == "identity":
        source["book_id"] = "book-replaced"
        armazenamento.atualizar_livro_salvo(p["reference"], source)
    else:
        p["backend"].delete(p["reference"].removeprefix("fb://"))
    pending_generate.click().run(timeout=15)
    assert not app.exception
    assert app.warning if changed != "unavailable" else app.error
    assert not any(item.label in {"Gerar ilustração", "Usar esta ilustração no livro", "Preparar opções A/B/C"} for item in app.button)
    p["image_provider"].assert_not_called()
    p["text_provider"].assert_not_called()

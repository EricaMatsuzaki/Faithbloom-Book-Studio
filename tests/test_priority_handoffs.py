"""Persist/reopen real projects through Studio selectors, never title matching."""
from copy import deepcopy
from pathlib import Path
import uuid

import pytest
from streamlit.testing.v1 import AppTest

import armazenamento
import activity_studio
import audiobook_studio
import editorial_dispatch as dispatch
import estilo
import openrouter_client
import orchestrator_visual
import storage_backend
import translation_localization
from integration_ux import PROJECT_CONTEXT_KEY, make_project_context

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def durable(tmp_path, monkeypatch):
    backend = storage_backend.LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage_backend, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setattr(estilo, "aplicar_estilo", lambda: None)
    monkeypatch.setattr(openrouter_client, "chamar_llm", lambda *a, **kw: pytest.fail("No paid provider in a handoff test"))
    monkeypatch.setattr(openrouter_client, "gerar_audio", lambda *a, **kw: pytest.fail("No paid TTS in a handoff test"))
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage_backend, "CACHE_DIR", cache)
    return backend


def same_title_books():
    saved = []
    for mark, age, language in [("A", "3-5", "pt-BR"), ("B", "9-12", "ja-JP")]:
        state = {"titulo": "Mesmo título", "colecao": "Mesma coleção", "idioma_original": language,
                 "faixa_etaria": age, "cenas_texto": [{"numero": 1, "texto": f"Fonte exclusiva {mark}."}], "personagens": {}}
        ref = armazenamento.salvar_livro(state)
        saved.append((state, ref))
    return saved


def handoff(app, target, source, reference):
    context = make_project_context({"storage_path": reference}, source)
    app.session_state[PROJECT_CONTEXT_KEY] = context
    app.session_state["editorial_studio_handoff"] = {"target": target, "project": context, "token": uuid.uuid4().hex}


def widget(app, kind, label):
    return next(x for x in getattr(app, kind) if x.label == label)


def test_activity_canonical_reference_can_be_used_by_real_visual_preflight(durable):
    run = dispatch.create_editorial_run("activity_book", "Livro", "Atividades", audience="teen")
    run = dispatch.initialize_specialist(run["id"])
    ref = run["source_ref"]
    assert ref == f"fb://activity_studio/projects/{run['source']['id']}.json"
    source = activity_studio.load_activity_project(run["source"]["id"])
    source["pages"] = [{"id": "page1", "instruction": "Encontre a saída.", "content": {"grid": [[0]]}}]
    activity_studio.save_activity_project(source)
    plan = dispatch.bind_visual_plan_to_run(run["id"], characters=[], locations=[])
    persisted = dispatch.validate_visual_source(plan)
    assert persisted["audience_id"] == "teen"
    assert persisted["pages"] == source["pages"]
    source["pages"][0]["instruction"] = "Encontre outra saída."
    activity_studio.save_activity_project(source)
    with pytest.raises(PermissionError, match="conteúdo salvo mudou"):
        dispatch.validate_visual_source(plan)


def test_old_activity_reference_migrates_only_its_own_plan_without_losing_history(durable):
    run = dispatch.create_editorial_run("activity_book", "Livro", "Atividades")
    run = dispatch.initialize_specialist(run["id"])
    project = activity_studio.load_activity_project(run["source"]["id"])
    project["pages"] = [{"instruction": "Observe."}]
    activity_studio.save_activity_project(project)
    plan = dispatch.bind_visual_plan_to_run(run["id"], characters=[], locations=[])
    run = dispatch.load_run(run["id"])
    run["source_ref"] = f"activity:{project['id']}"
    dispatch.save_run(run)
    plan["source_ref"] = run["source_ref"]
    plan["approvals"]["story"] = True
    plan["history"] = [{"event": "previous_approval"}]
    orchestrator_visual.save_visual_plan(plan)
    migrated = dispatch.sync_source(run["id"])
    current_plan = orchestrator_visual.load_visual_plan(plan["id"])
    assert migrated["source_ref"].startswith("fb://activity_studio/projects/")
    assert current_plan["approvals"]["story"] is True
    assert current_plan["history"][0] == {"event": "previous_approval"}
    assert dispatch.validate_visual_source(current_plan)["id"] == project["id"]


@pytest.mark.parametrize("audience", ["teen", "adult", "custom"])
@pytest.mark.parametrize("kind", ["children_story", "real_life_story"])
def test_child_native_generation_never_silently_changes_nonchild_audience(durable, audience, kind):
    run = dispatch.create_editorial_run(kind, "Título", "Ideia", audience=audience)
    with pytest.raises(ValueError, match="apenas às faixas infantis"):
        dispatch.initialize_specialist(run["id"])
    reopened = dispatch.load_run(run["id"])
    assert reopened["route_plan"]["audience"] == audience
    assert not reopened["source"]
    assert not durable.list("livros")


@pytest.mark.parametrize("audience,public,age", [("teen", "Juvenil", "13+"), ("adult", "Adulto", "Adulto"), ("custom", "Personalizado", "Personalizado")])
def test_coloring_context_preserves_native_supported_audience(durable, audience, public, age):
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("coloring_book", "Colorir", "Flores", audience=audience)["id"])
    context = dispatch.studio_session_context(run)
    assert context["state_c"]["publico"] == public
    assert context["state_c"]["faixa_etaria"] == age
    assert context["caminho_salvo_c"] == run["source_ref"]
    assert context["preview_c_path"] is None


def test_translation_opens_exact_homonymous_source_and_its_age(durable):
    (_, _), (source_b, reference_b) = same_title_books()
    app = AppTest.from_file(ROOT / "pages/21_Translation_Localization_Studio.py")
    handoff(app, "translation", source_b, reference_b)
    app.run()
    assert not app.exception
    selected = widget(app, "selectbox", "📚 Livro Master").value
    assert reference_b.removeprefix("fb://") in selected
    assert widget(app, "selectbox", "Faixa de leitura").value.profile_id == "9-12"
    # Manual switching remains possible after the incoming request is consumed.
    other = next(value for value in widget(app, "selectbox", "📚 Livro Master").options if value != selected)
    widget(app, "selectbox", "📚 Livro Master").set_value(other).run()
    assert not app.exception
    assert widget(app, "selectbox", "Faixa de leitura").value.profile_id == "3-5"


@pytest.mark.parametrize("audience", ["teen", "adult"])
def test_translation_blocks_incompatible_reading_profile_before_generation(durable, audience):
    source = {"titulo": "Obra", "colecao": "Coleção", "faixa_etaria": audience, "cenas_texto": [{"numero": 1, "texto": "Texto preservado."}]}
    ref = armazenamento.salvar_livro(source)
    app = AppTest.from_file(ROOT / "pages/21_Translation_Localization_Studio.py")
    handoff(app, "translation", source, ref)
    app.run()
    assert not app.exception
    assert any("sem convertê-la para infantil" in x.value for x in app.error)
    assert not any(b.label == "🌍 Gerar localização" for b in app.button)
    assert durable.get_json(ref.removeprefix("fb://"))["faixa_etaria"] == audience


def test_audio_handoff_replaces_previous_project_and_persists_exact_source_language(durable):
    (source_a, reference_a), (source_b, reference_b) = same_title_books()
    project_a = audiobook_studio.save_audiobook_project(audiobook_studio.create_audiobook_project("Áudio A", source_state=source_a, source_ref=reference_a))
    app = AppTest.from_file(ROOT / "pages/24_🎧_Audiobook_Studio.py")
    app.session_state["r09_project_id"] = project_a["id"]
    app.session_state["r09_project_mode"] = "Abrir existente"
    handoff(app, "audiobook", source_b, reference_b)
    app.run()
    assert not app.exception
    assert reference_b.removeprefix("fb://") in widget(app, "selectbox", "Story Book de origem").value
    assert widget(app, "text_input", "Locale").value == "ja-JP"
    assert "r09_project_id" not in app.session_state
    widget(app, "button", "🎧 Criar projeto de audiobook").click().run()
    assert not app.exception
    project_b = audiobook_studio.load_audiobook_project(app.session_state["r09_project_id"])
    assert project_b["id"] != project_a["id"]
    assert dispatch.book_source_key(project_b["source_ref"]) == dispatch.book_source_key(reference_b)
    assert project_b["locale"] == "ja-JP"
    assert project_b["script_scenes"][0]["source_text"] == "Fonte exclusiva B."
    assert audiobook_studio.load_audiobook_project(project_a["id"])["script_scenes"][0]["source_text"] == "Fonte exclusiva A."


def test_missing_handoff_source_fails_closed_even_with_same_title_in_library(durable):
    (source_a, reference_a), _ = same_title_books()
    app = AppTest.from_file(ROOT / "pages/24_🎧_Audiobook_Studio.py")
    handoff(app, "audiobook", source_a, "fb://livros/missing.json")
    app.run()
    assert not app.exception
    assert any("Nenhum outro livro foi aberto" in x.value for x in app.error)
    assert not any(b.label == "🎧 Criar projeto de audiobook" for b in app.button)
    assert not audiobook_studio.list_audiobook_projects()


def test_activity_page_opens_exact_project_instead_of_stale_selector(durable):
    a = activity_studio.create_activity_project("Mesmo título", "adult")
    b = activity_studio.create_activity_project("Mesmo título", "teen")
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("activity_book", "Mesmo título", "Tema", audience="9_12")["id"])
    app = AppTest.from_file(ROOT / "pages/23_🧩_Activity_Book_Studio.py")
    app.session_state["r08_project_mode"] = "Abrir existente"
    app.session_state["r08_saved_selection"] = a["id"]
    for key,value in dispatch.studio_session_context(run).items():
        app.session_state[key]=value
    app.run()
    assert not app.exception
    assert widget(app, "selectbox", "Projeto salvo").value == run["source"]["id"]
    assert app.session_state["r08_project_id"] not in {a["id"], b["id"]}


def test_quality_handoff_never_shares_report_id_between_homonymous_sources(durable):
    (source_a, reference_a), (source_b, reference_b) = same_title_books()
    app = AppTest.from_file(ROOT / "pages/25_🛡️_Quality_Guardian.py")
    handoff(app, "quality", source_a, reference_a)
    app.run()
    widget(app, "button", "🛡️ Executar Quality Guardian").click().run()
    assert not app.exception
    report_a = deepcopy(app.session_state["r10_report"])
    assert dispatch.book_source_key(report_a["source_ref"]) == dispatch.book_source_key(reference_a)
    handoff(app, "quality", source_b, reference_b)
    app.run()
    assert not app.exception
    assert "r10_report" not in app.session_state
    widget(app, "button", "🛡️ Executar Quality Guardian").click().run()
    assert not app.exception
    report_b = app.session_state["r10_report"]
    assert report_b["id"] != report_a["id"]
    assert dispatch.book_source_key(report_b["source_ref"]) == dispatch.book_source_key(reference_b)
    assert not report_b.get("author_final_approval")


def test_missing_activity_source_does_not_replace_saved_run_snapshot(durable):
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("activity_book", "Livro", "Tema")["id"])
    durable.delete(run["source_ref"].removeprefix("fb://"))
    with pytest.raises(ValueError, match="referência foi preservada"):
        dispatch.sync_source(run["id"])
    assert dispatch.load_run(run["id"])["source"] == run["source"]


def test_native_context_owns_path_and_resets_previous_project_artifacts(durable):
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("children_story", "Nova obra", "Ideia")["id"])
    context = {"state": {"titulo": "Anterior"}, "historia4_storage_path": "fb://livros/old.json", "ideias_4_estilos": ["old"]}
    dispatch.apply_native_studio_context(context, run)
    assert context["state"]["storage_path"] == run["source_ref"]
    assert context["historia4_storage_path"] == run["source_ref"]
    assert context["ideias_4_estilos"] == []
    coloring = dispatch.initialize_specialist(dispatch.create_editorial_run("coloring_book", "Colorir", "Tema")["id"])
    context.update(coloring_authors=["old-author"], c_selo8="old-upload", capa_colorir_phase8={"caminho_pdf": "old.pdf"})
    dispatch.apply_native_studio_context(context, coloring)
    assert "coloring_authors" not in context
    assert "c_selo8" not in context
    assert context["capa_colorir_phase8"] is None


def test_real_experience_native_context_carries_account_without_granting_consent(durable):
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("real_life_story", "Memória", "Relato fornecido pela autora")["id"])
    context = dispatch.studio_session_context(run)
    assert context["state"]["real_experience"]["original_account"] == "Relato fornecido pela autora"
    assert context["state"]["real_experience"]["consent_confirmed"] is False


def test_quality_report_is_invalidated_when_only_approved_image_or_print_evidence_changes(durable):
    (source, reference), _ = same_title_books()
    app = AppTest.from_file(ROOT / "pages/25_🛡️_Quality_Guardian.py")
    handoff(app, "quality", source, reference)
    app.run()
    widget(app, "button", "🛡️ Executar Quality Guardian").click().run()
    assert not app.exception
    report_id = app.session_state["r10_report"]["id"]
    saved_source = durable.get_json(reference.removeprefix("fb://"))
    saved_source["cenas_imagem"] = [{"numero": 1, "caminho_arquivo": "fb://assets/scene-b.png", "aprovada": True}]
    saved_source["preflight_impressao"] = {"ok": False, "blocking": 1}
    durable.put_json(reference.removeprefix("fb://"), saved_source)
    app.run()
    assert not app.exception
    assert "r10_report" not in app.session_state
    assert durable.get_json(f"quality_guardian/reports/{report_id}.json")["id"] == report_id


def test_activity_visual_plan_rejects_audience_change_and_can_start_new_preflight(durable):
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("activity_book", "Título", "Tema", audience="teen")["id"])
    source = activity_studio.load_activity_project(run["source"]["id"])
    source["pages"] = [{"instruction": "Observe."}]
    activity_studio.save_activity_project(source)
    plan = dispatch.bind_visual_plan_to_run(run["id"], characters=[], locations=[])
    source["audience_id"] = "adult"
    activity_studio.save_activity_project(source)
    with pytest.raises(PermissionError):
        dispatch.validate_visual_source(plan)
    reopened = dispatch.sync_source(run["id"])
    assert reopened["visual_plan_id"] == ""
    assert reopened["source"]["audience_id"] == "adult"
    assert orchestrator_visual.load_visual_plan(plan["id"])["approvals"]["story"] is False
    replacement = dispatch.bind_visual_plan_to_run(run["id"], characters=[], locations=[])
    assert replacement["id"] != plan["id"]


def test_switching_translation_source_resets_bible_consent_and_scopes_glossary(durable):
    (source_a, ref_a), (source_b, ref_b) = same_title_books()
    app = AppTest.from_file(ROOT / "pages/21_Translation_Localization_Studio.py")
    handoff(app, "translation", source_a, ref_a)
    app.run()
    widget(app,"radio","Nesta edição").set_value("Usar texto bíblico aprovado").run()
    widget(app,"text_area","Texto exato do versículo aprovado").set_value("Texto previamente autorizado para a obra A.").run()
    widget(app,"checkbox","Confirmo que este é o texto bíblico que desejo usar nesta edição").check().run()
    app.session_state["r06_glossary"]={"Termo da obra A":"Forma aprovada A"}
    handoff(app,"translation",source_b,ref_b)
    app.run()
    assert not app.exception
    assert widget(app,"radio","Nesta edição").value == "Somente referência"
    assert widget(app,"text_area","Texto exato do versículo aprovado").value == ""
    assert not widget(app,"checkbox","Confirmo que este é o texto bíblico que desejo usar nesta edição").value
    assert app.session_state["r06_glossary"] == {}

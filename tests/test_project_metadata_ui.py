"""Real metadata pages preserve the observed project and paid execution record."""
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import armazenamento as books
import author_profiles as authors
import editorial_generation_runtime as runtime
import editorial_products as products
import estilo
import project_metadata_ui as metadata_ui
import saas_access as access
import storage_backend as storage
from emotional_visual_binding import require_book_emotional_map

ROOT = Path(__file__).resolve().parents[1]
AUTHOR_PAGE = ROOT / "pages/32_✍️_Autores_e_Colaboradores.py"
READINESS_PAGE = ROOT / "pages/37_🧠_Agent_Skills_Bestseller_Readiness.py"
EMOTION_PAGE = ROOT / "pages/17_🎭_Emotional_Color_Director.py"
NEW_BOOK_PAGE = ROOT / "pages/1_📖_Criar_do_Zero.py"
RESUME_BOOK_PAGE = ROOT / "pages/2_📚_Retomar_Livro.py"


def unit(**_):
    return {"title": "Cuidar com atenção", "objectives": ["Observar uma flor"], "source_refs": [],
            "blocks": [{"label": "Abertura", "text": "Observe uma flor e descreva como cuidar dela com atenção."}]}


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    monkeypatch.chdir(tmp_path)
    backend = storage.LocalStorageBackend(str(tmp_path / "data"))
    for module in (storage, books, authors):
        monkeypatch.setattr(module, "BACKEND", backend)
    cache = tmp_path / "cache"; cache.mkdir()
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    monkeypatch.setattr(estilo, "aplicar_estilo", lambda: None)
    import ai_provider_router
    import openrouter_client
    forbidden = Mock(side_effect=AssertionError("The metadata UI cannot buy a generation"))
    monkeypatch.setattr(ai_provider_router, "chamar_llm", forbidden)
    for name in ("chamar_llm", "gerar_imagem", "gerar_audio"):
        monkeypatch.setattr(openrouter_client, name, forbidden)
    source = products.create_product("other", "Obra especializada", "Cuidar das flores", unit_count=1, custom_blocks=["Abertura"])
    products.save_product(source)
    paid = Mock(side_effect=unit)
    products.generate_product(source, paid, confirmed=True)
    author = authors.create_author_profile("Autora escolhida")
    return {"backend": backend, "source": source, "reference": source["storage_path"],
            "paid": paid, "forbidden": forbidden, "author": author}


def widget(app, kind, label):
    return next(item for item in getattr(app, kind) if item.label == label)


def page(path, saved=None):
    app = AppTest.from_file(str(path))
    if path == EMOTION_PAGE:
        app.session_state["state"] = deepcopy(saved["source"])
    app.run(timeout=20)
    assert not app.exception
    return app


def raw(saved):
    return saved["backend"].get_json(runtime._path(saved["reference"]))


def assert_execution_intact(saved, before):
    current = raw(saved)
    assert current["book_id"] == before["book_id"]
    assert current["editorial_product"]["units"] == before["editorial_product"]["units"]
    for key in ("status", "attempts", "claim"):
        assert current["editorial_product"]["execution"].get(key) == before["editorial_product"]["execution"].get(key)
    assert current["editorial_product"]["execution"]["revision"] >= before["editorial_product"]["execution"]["revision"]
    saved["paid"].assert_called_once()
    saved["forbidden"].assert_not_called()
    return current


def test_author_page_assigns_completed_specialized_product_without_replacing_units_or_attempts(saved):
    before = raw(saved)
    app = page(AUTHOR_PAGE)
    widget(app, "button", "Salvar autoria deste projeto").click().run(timeout=20)
    assert not app.exception
    current = assert_execution_intact(saved, before)
    assert current["autora"] == "Autora escolhida"
    assert current["authorship"]["authors"][0]["profile_id"] == saved["author"]["id"]


def test_author_page_adds_contributor_and_cover_credit_to_exact_saved_product(saved):
    before = raw(saved)
    app = page(AUTHOR_PAGE)
    widget(app, "text_input", "Crédito como (opcional)").set_value("Revisora de conteúdo")
    widget(app, "button", "Adicionar colaborador").click().run(timeout=20)
    assert not app.exception
    current = assert_execution_intact(saved, before)
    assert current["authorship"]["contributors"][0]["credit_as"] == "Revisora de conteúdo"
    widget(app, "text_input", "Override opcional").set_value("Texto e carinho por Autora escolhida")
    widget(app, "button", "Salvar crédito de capa").click().run(timeout=20)
    assert not app.exception
    current = assert_execution_intact(saved, before)
    assert current["authorship"]["cover_credit_override"] == "Texto e carinho por Autora escolhida"


def test_readiness_page_saves_real_report_for_completed_product_without_paid_regeneration(saved):
    before = raw(saved)
    app = page(READINESS_PAGE)
    widget(app, "button", "💾 Salvar Bestseller Readiness neste projeto").click().run(timeout=20)
    assert not app.exception
    current = assert_execution_intact(saved, before)
    report = current["bestseller_readiness_report"]
    assert report["title"] == before["titulo"] and report["criteria"]
    assert current["agent_skill_audit"]["ok"]


def test_readiness_page_saves_reference_validation_to_observed_product(saved):
    before = raw(saved)
    app = page(READINESS_PAGE)
    widget(app, "text_input", "Referência").set_value("Lucas 2:11")
    widget(app, "text_input", "Fonte bíblica/consulta aprovada").set_value("Edição consultada pela revisora")
    widget(app, "text_input", "Referência da fonte (URL, ISBN ou identificação)").set_value("ISBN de exemplo para a conferência")
    widget(app, "text_area", "Nota de contexto").set_value("Conferi que a passagem trata do nascimento de Jesus e corresponde ao contexto escolhido.")
    widget(app, "checkbox", "Conferi o contexto da passagem na fonte indicada").check()
    widget(app, "checkbox", "Aprovo esta referência para esta história").check()
    widget(app, "text_input", "Aprovado por").set_value("Revisora responsável")
    widget(app, "button", "📖 Validar referência/contexto").click().run(timeout=20)
    assert not app.exception
    current = assert_execution_intact(saved, before)
    assert current["versiculo_referencia"] == "Lucas 2:11"
    assert current["bible_reference_validation"]["status"] == "validated"


def test_author_stale_widget_cannot_use_a_fresh_rerun_baseline_to_replace_new_credit(saved):
    app = page(AUTHOR_PAGE)
    widget(app, "text_input", "Override opcional").set_value("Minha intenção ainda não salva")
    path = runtime._path(saved["reference"])
    def concurrent(current):
        current["authorship"] = {"authors": [], "contributors": [], "cover_credit_override": "Crédito salvo em outra tela"}
        return current
    saved["backend"].update_json(path, concurrent)
    before = saved["backend"].get_bytes(path)
    widget(app, "button", "Salvar crédito de capa").click().run(timeout=20)
    assert not app.exception
    assert saved["backend"].get_bytes(path) == before
    assert widget(app, "button", "Salvar crédito de capa").disabled
    assert app.get("download_button")
    widget(app, "button", "Recarregar dados salvos do projeto").click().run(timeout=20)
    assert not app.exception
    assert widget(app, "text_input", "Override opcional").value == "Crédito salvo em outra tela"
    widget(app, "text_input", "Override opcional").set_value("Crédito revisado depois de recarregar")
    widget(app, "button", "Salvar crédito de capa").click().run(timeout=20)
    assert not app.exception
    assert raw(saved)["authorship"]["cover_credit_override"] == "Crédito revisado depois de recarregar"
    saved["forbidden"].assert_not_called()


def test_author_write_race_preserves_newer_credit_and_downloadable_intent(saved, monkeypatch):
    app = page(AUTHOR_PAGE)
    original = metadata_ui.update_metadata_fields
    def raced(snapshot, updates, **kwargs):
        def edit(current):
            current["autora"] = "Outra autoria confirmada"
            return current
        saved["backend"].update_json(runtime._path(saved["reference"]), edit)
        return original(snapshot, updates, **kwargs)
    monkeypatch.setattr(metadata_ui, "update_metadata_fields", raced)
    widget(app, "button", "Salvar autoria deste projeto").click().run(timeout=20)
    assert not app.exception
    assert raw(saved)["autora"] == "Outra autoria confirmada"
    assert app.get("download_button")
    assert any("alterado durante o salvamento" in item.value for item in app.warning)
    saved["forbidden"].assert_not_called()


@pytest.mark.parametrize("target", ["authors", "readiness", "emotions"])
@pytest.mark.parametrize("blocked", ["running", "uncertain", "raw"])
def test_all_metadata_pages_block_active_or_unresolved_paid_result_without_source_write(saved, target, blocked):
    def active(current):
        ex = current["editorial_product"]["execution"]
        ex["revision"] += 1
        ex["attempts"] = []
        if blocked == "running":
            ex.update(status="running",claim={"token": "active-owner-ui", "host": socket.gethostname(), "pid": os.getpid(), "owner_active": True})
        else:
            ex.pop("claim",None)
            ex["status"] = "needs_reconciliation" if blocked == "uncertain" else "save_failed"
            attempt = {"token": "unresolved-ui", "index": 0, "state": blocked, "estimated_usd": .01, "actual_usd": None}
            if blocked == "raw": attempt["response"] = unit()
            ex["attempts"] = [attempt]
        return current
    saved["backend"].update_json(runtime._path(saved["reference"]), active)
    saved["source"] = products.load_product(saved["reference"])
    before = saved["backend"].get_bytes(runtime._path(saved["reference"]))
    if target == "authors":
        app = page(AUTHOR_PAGE)
        assert widget(app,"button","Salvar autoria deste projeto").disabled
        assert widget(app,"button","Salvar crédito de capa").disabled
    elif target == "readiness":
        app = page(READINESS_PAGE)
        assert widget(app,"button","💾 Salvar Bestseller Readiness neste projeto").disabled
        assert widget(app,"button","📖 Validar referência/contexto").disabled
    else:
        app = page(EMOTION_PAGE,saved)
        widget(app,"text_input","Responsável pela revisão emocional").set_value("Revisora")
        widget(app,"checkbox","Revisei todas as cenas, a direção emocional e a preservação dos Masters").check().run(timeout=20)
        assert not app.exception
        assert widget(app,"button","💾 Aplicar e salvar este mapa no livro ativo").disabled
    assert saved["backend"].get_bytes(runtime._path(saved["reference"])) == before
    saved["forbidden"].assert_not_called()


def test_emotional_page_approves_and_persists_completed_specialized_product_with_exact_return(saved):
    before = raw(saved)
    app = page(EMOTION_PAGE,saved)
    widget(app,"text_input","Responsável pela revisão emocional").set_value("Revisora")
    widget(app,"checkbox","Revisei todas as cenas, a direção emocional e a preservação dos Masters").check().run(timeout=20)
    widget(app,"button","💾 Aplicar e salvar este mapa no livro ativo").click().run(timeout=20)
    assert not app.exception
    current = assert_execution_intact(saved,before)
    require_book_emotional_map(products.load_product(saved["reference"]))
    assert app.session_state["state"]["book_id"] == before["book_id"]
    assert any("revisado, aprovado e salvo" in item.value for item in app.success)
    assert current["emotional_book_binding"]["approval"]["reviewer"] == "Revisora"


def test_colorir_project_credits_use_same_safe_metadata_flow(saved):
    saved["backend"].put_json("livros_colorir/own.json",{"book_id":"coloring-own","titulo":"Colorir com amizade","tema_geral":"Flores","autora":"Crédito antigo"})
    app=page(AUTHOR_PAGE)
    widget(app,"selectbox","Projeto").set_value("livros_colorir/own.json").run(timeout=20)
    widget(app,"button","Salvar autoria deste projeto").click().run(timeout=20)
    assert not app.exception
    current=saved["backend"].get_json("livros_colorir/own.json")
    assert current["book_id"]=="coloring-own" and current["autora"]=="Autora escolhida"
    saved["forbidden"].assert_not_called()


@pytest.mark.parametrize("actor_after",["account-b",None])
def test_metadata_helper_reauthorizes_before_retained_other_accounts_snapshot(saved,monkeypatch,actor_after):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE","multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS","https://identity.example")
    monkeypatch.delenv("FAITHBLOOM_ACCESS_ROLES",raising=False)
    backend=storage.TenantStorageBackend(saved["backend"])
    monkeypatch.setattr(storage,"BACKEND",backend)
    actor=access.actor_from_trusted_claims({"authenticated":True,"iss":"https://identity.example","sub":"account-a"})
    with access.access_context(actor):
        backend.put_json("livros/private.json",{"book_id":"private-a","titulo":"TÍTULO PRIVADO A"})
        reference=storage.storage_uri("livros/private.json")
    script="""from contextlib import nullcontext
import streamlit as st
import saas_access as access
from project_metadata_ui import open_project_metadata
subject=st.session_state.get('actor_subject')
context=(access.access_context(access.actor_from_trusted_claims({'authenticated':True,'iss':'https://identity.example','sub':subject})) if subject else nullcontext())
with context:
    editor=open_project_metadata(st.session_state['project_ref'],namespace='private_test')
    st.write(editor.state['titulo'])
"""
    app=AppTest.from_string(script)
    app.session_state["actor_subject"]="account-a";app.session_state["project_ref"]=reference
    app.run(timeout=20);assert not app.exception
    assert any("TÍTULO PRIVADO A" in item.value for item in app.markdown)
    app.session_state["actor_subject"]=actor_after
    app.run(timeout=20);assert not app.exception
    visible="\n".join(str(item.value) for kind in ("markdown","caption","info","warning","error") for item in app.get(kind))
    assert "TÍTULO PRIVADO A" not in visible
    assert any("não tem acesso" in item.value for item in app.error)
    assert "project_metadata_editors" not in app.session_state


@pytest.mark.parametrize("target,state_key,stage_key,stage", [
    (NEW_BOOK_PAGE, "state", "etapa", "gerando"),
    (RESUME_BOOK_PAGE, "state_r", "etapa_r", "finalizar"),
])
def test_narrative_pages_pause_paid_actions_and_show_received_draft(saved, target, state_key, stage_key, stage):
    draft = {"titulo": "Resultado já recebido", "cenas_texto": [{"numero": 1, "texto": "Uma resposta que não deve ser comprada de novo."}]}
    state = {"titulo": "Livro em revisão", "autosave_status": "error", "autosave_error": "Há uma edição concorrente.",
             "autosave_pending": {"storage_path": saved["reference"], "draft": deepcopy(draft)}}
    before = saved["backend"].get_bytes(runtime._path(saved["reference"]))
    app = AppTest.from_file(str(target))
    app.session_state[state_key] = state
    app.session_state[stage_key] = stage
    app.run(timeout=20)
    assert not app.exception
    assert any("aguardando salvamento" in item.value for item in app.warning)
    assert app.get("download_button")
    assert "Uma resposta que não deve ser comprada de novo." in widget(app, "text_area", "Resultado recebido").value
    assert app.session_state[stage_key] == stage
    assert app.session_state[state_key]["autosave_pending"]["draft"] == draft
    assert saved["backend"].get_bytes(runtime._path(saved["reference"])) == before
    saved["forbidden"].assert_not_called()


def test_resume_pipeline_recovers_internal_autosave_without_rebuying_prior_steps_or_duplicating_book(saved, monkeypatch):
    import generation_autosave as autosave
    import retomar_fluxo as resume
    source = {"titulo": "Mesmo livro retomado", "colecao": "Teste de retomada", "book_id": "resume-exact-id",
              "cenas_texto": [{"numero": 1, "texto": "Uma flor cuidada com carinho."}], "personagens": {}}
    reference = books.salvar_livro(source)
    state = books.carregar_livro("", reference.removeprefix("fb://"))
    original_paths = saved["backend"].list("livros")
    calls = []
    names = ("atividades_colorir_node", "audiobook_node", "tradutor_node", "sinopse_node",
             "pesquisa_palavras_chave_node", "pesquisa_categorias_node", "diagramador_node", "capa_node", "marketing_lancamento_node")
    for name in names:
        def completed(current, *_args, _name=name, **_kwargs):
            calls.append(_name)
            current[_name + "_received"] = "Resultado preservado"
            return current
        monkeypatch.setattr(resume, name, completed)
    narration_calls = []
    def narration(current, *_):
        if current.get("narration_received"):
            return current
        narration_calls.append("paid-once")
        current["narration_received"] = "Áudio já recebido"
        autosave.persist_generation_snapshot(current, reason="audio_narrated:1")
        return current
    monkeypatch.setattr(resume, "narracao_node", narration)
    original_update = autosave.atualizar_livro_salvo
    failures = []
    def fail_received_audio_once(path, current):
        if current.get("narration_received") and not failures:
            failures.append("storage unavailable after response")
            raise storage.StorageError("Armazenamento indisponível durante a gravação.")
        return original_update(path, current)
    monkeypatch.setattr(autosave, "atualizar_livro_salvo", fail_received_audio_once)
    app = AppTest.from_file(str(RESUME_BOOK_PAGE))
    app.session_state["state_r"] = state
    app.session_state["etapa_r"] = "finalizar"
    app.run(timeout=20)
    assert not app.exception
    assert calls == ["atividades_colorir_node", "audiobook_node"]
    assert narration_calls == ["paid-once"]
    pending = app.session_state["state_r"]["autosave_pending"]
    assert pending["draft"]["narration_received"] == "Áudio já recebido"
    assert app.get("download_button")
    assert app.session_state["etapa_r"] == "finalizar"
    widget(app, "button", "Tentar salvar resultado recebido").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["etapa_r"] == "resultado", {"errors": [x.value for x in app.error], "status": app.session_state["state_r"].get("autosave_status"), "pending": app.session_state["state_r"].get("autosave_pending")}
    assert narration_calls == ["paid-once"]
    assert calls == list(names)
    assert app.session_state["caminho_salvo_r"] == reference
    assert app.session_state["state_r"]["storage_path"] == reference
    assert saved["backend"].list("livros") == original_paths
    committed = saved["backend"].get_json(reference.removeprefix("fb://"))
    assert committed["book_id"] == "resume-exact-id" and committed["narration_received"] == "Áudio já recebido"
    assert committed["generation_pipeline_checkpoint"]["completed"][-1] == "marketing"
    saved["forbidden"].assert_not_called()


def test_create_page_finishes_checkpointed_book_at_same_reference_without_repeating_paid_work(saved):
    source = {"titulo": "Livro finalizado uma vez", "colecao": "Teste de criação", "book_id": "new-exact-id",
              "pacote_pronto": False, "checklist_kdp": {}, "cenas_texto": [], "personagens": {},
              "generation_pipeline_checkpoint": {"flow": "new_book", "completed": [
                  "illustrations", "coloring", "audiobook_script", "narration", "dedication", "translation",
                  "synopsis", "keywords", "categories", "layout", "cover", "marketing"]}}
    reference = books.salvar_livro(source)
    original_paths = saved["backend"].list("livros")
    app = AppTest.from_file(str(NEW_BOOK_PAGE))
    app.session_state["state"] = books.carregar_livro("", reference.removeprefix("fb://"))
    app.session_state["etapa"] = "finalizando"
    app.run(timeout=20)
    assert not app.exception
    assert app.session_state["etapa"] == "resultado_zero"
    assert app.session_state["caminho_salvo"] == reference
    assert app.session_state["state"]["storage_path"] == reference
    assert app.session_state["state"]["book_id"] == "new-exact-id"
    assert saved["backend"].list("livros") == original_paths
    saved["forbidden"].assert_not_called()

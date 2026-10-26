"""Cross-studio acceptance with durable files and explicitly simulated providers.

These tests verify usable code paths, not a production-provider certification.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest
import zipfile
from PIL import Image
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

import armazenamento
import coloring_studio
import generation_autosave
import storage_backend as storage
from agents.diagramador import diagramador_node
from agents.estilos_narrativos import ORDEM_ESTILOS, aplicar_estilo_ao_state, gerar_comparativo_estilos
from agents.roteirista import roteirista_node
from agents.roteirista_autoral import gerar_versao_autoral_roteirista
from renderizador_editorial import renderizar_miolo_pdf
from test_editorial_generation_atomic import durable
from test_coloring_workflow_integration import (
    coloring_project, isolated_studio, official_master, open_draft, button, image_objects,
)

ROOT = Path(__file__).resolve().parents[1]


def control(app, kind, label):
    return next(item for item in getattr(app, kind) if item.label == label)


def _narrative_response(marker):
    return {
        "titulo": "Lia cuida do jardim",
        "sinopse_poetica": f"Uma descoberta {marker}.",
        "cenas_texto": [
            {"numero": number, "texto": f"Lia observa a flor {marker} na cena {number}.",
             "emocao": "alegria", "intensidade_emocional": 2}
            for number in range(1, 13)
        ],
        "licao_final": "Cuidar com amor transforma o nosso dia.",
    }


def _new_narrative(master=None):
    character = {"nome": "Lia", "papel": "protagonista",
                 "descricao_fixa": "Olhos verdes com estrelas e brilho; laço rosa."}
    if master is not None:
        character["imagem_referencia"] = str(master)
    return {"book_id": "pilot-narrative-master", "titulo": "Lia cuida do jardim", "colecao": "Aceitação do piloto",
            "faixa_etaria": "6-8", "paginas_minimas": 24,
            "emocao_central": "alegria", "aprendizado_cristao": "Cuidar com amor.",
            "versiculo_referencia": "Salmo 27:14", "autora": "Autora de aceitação",
            "personagens": {"Lia": character}}


def test_new_story_autosaves_all_versions_reopens_continues_and_exports(durable, tmp_path):
    master = tmp_path / "approved-original.png"
    Image.new("RGB", (3000, 3000), "lightgreen").save(master)
    original_bytes = master.read_bytes()
    state, calls = _new_narrative(master), []

    def comparison_provider(**request):
        marker = ORDEM_ESTILOS[len(calls)]
        calls.append(marker)
        assert "Olhos verdes com estrelas e brilho" in request["instrucao"]
        return _narrative_response(marker)

    versions = gerar_comparativo_estilos(state, comparison_provider, modo="completa")
    reference, identity = state["storage_path"], state["book_id"]
    assert calls == list(ORDEM_ESTILOS)
    assert state["autosave_status"] == "saved"
    assert len(durable.list("livros")) == 1
    saved = armazenamento.carregar_livro("", reference.removeprefix("fb://"))
    assert saved["book_id"] == identity
    assert set(saved["comparativo_estilos"]) == set(ORDEM_ESTILOS)

    selected = aplicar_estilo_ao_state(saved, "estilo_2", versions["estilo_2"])
    selected = roteirista_node(selected, lambda **_: pytest.fail("Selecting a complete story must not buy another story"))
    generation_autosave.persist_generation_snapshot(selected, reason="aceitacao_selecao_autora")
    reloaded = armazenamento.carregar_livro("", reference.removeprefix("fb://"))

    def authorial_provider(**_request):
        calls.append("authorial")
        def add_other_edit(document):
            document["editorial_note"] = "Nota recebida de outra editora durante a geração."
            return document
        durable.update_json(storage.uri_to_path(reference), add_other_edit)
        return _narrative_response("proposta_autoral")

    received = gerar_versao_autoral_roteirista(reloaded, authorial_provider)
    assert calls == [*ORDEM_ESTILOS, "authorial"]
    assert reloaded["autosave_status"] == "saved"
    final = armazenamento.carregar_livro("", reference.removeprefix("fb://"))
    assert final["book_id"] == identity and len(durable.list("livros")) == 1
    assert final["versao_roteirista_autoral"] == received
    assert final["editorial_note"] == "Nota recebida de outra editora durante a geração."
    assert final["cenas_texto"] == selected["cenas_texto"]  # The fifth proposal is not an automatic selection.
    assert final["personagens"]["Lia"]["descricao_fixa"] == state["personagens"]["Lia"]["descricao_fixa"]

    final["cenas_imagem"] = [{"numero": row["numero"], "caminho_arquivo": str(master), "aprovado": True}
                              for row in final["cenas_texto"]]
    rendered = renderizar_miolo_pdf(diagramador_node(final), str(tmp_path / "narrativa.pdf"), bleed=False)
    assert rendered["ok"] and not rendered["avisos"]
    reader = PdfReader(rendered["caminho"])
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "estilo_2 na cena 1" in text and "estilo_2 na cena 12" in text
    assert "proposta_autoral" not in text
    assert sum(bool(image_objects(page)) for page in reader.pages) == 12
    assert master.read_bytes() == original_bytes


def test_received_authorial_result_stays_recoverable_when_same_field_changed(durable):
    state = _new_narrative()
    generation_autosave.persist_generation_snapshot(state, reason="aceitacao_novo_projeto")
    reference, calls = state["storage_path"], []
    other_edit = {"titulo": "Escolha atual da editora", "cenas_texto": [{"numero": 1, "texto": "Texto atual preservado."}]}

    def provider(**_request):
        calls.append("paid-once")
        def another_editor(document):
            document["versao_roteirista_autoral"] = deepcopy(other_edit)
            return document
        durable.update_json(storage.uri_to_path(reference), another_editor)
        return _narrative_response("resposta_recebida")

    received = gerar_versao_autoral_roteirista(state, provider)
    assert calls == ["paid-once"] and state["autosave_status"] == "error"
    assert state["autosave_pending"]["draft"]["versao_roteirista_autoral"] == received
    assert durable.get_json(storage.uri_to_path(reference))["versao_roteirista_autoral"] == other_edit
    with pytest.raises(armazenamento.BookSaveConflict):
        generation_autosave.retry_pending_generation_save(state)
    assert calls == ["paid-once"]
    assert durable.get_json(storage.uri_to_path(reference))["versao_roteirista_autoral"] == other_edit
    assert state["autosave_pending"]["draft"]["versao_roteirista_autoral"] == received


def test_received_story_ui_reopens_and_explicitly_applies_without_another_provider(durable):
    state = _new_narrative()
    generation_autosave.persist_generation_snapshot(state, reason="aceitacao_recuperacao_ui")
    reference, calls = state["storage_path"], []

    def provider(**_request):
        calls.append("received-once")
        def competing_edit(current):
            current["versao_roteirista_autoral"] = _narrative_response("outra_editora")
            current["editorial_note"] = "A nota concorrente precisa permanecer."
            return current
        durable.update_json(storage.uri_to_path(reference), competing_edit)
        return _narrative_response("recebido_para_conferir")

    received = gerar_versao_autoral_roteirista(state, provider)
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from generation_save_ui import render_generation_save_recovery\n"
        "if render_generation_save_recovery(st.session_state['state']): st.stop()\n"
        "st.button('Pedir outra geração')\n"
    )
    app.session_state["state"] = deepcopy(state)
    app.run(timeout=15)
    assert not app.exception
    assert "Pedir outra geração" not in [item.label for item in app.button]
    assert app.get("download_button")
    button(app, "Tentar salvar resultado recebido").click().run(timeout=15)
    assert not app.exception and app.error
    assert calls == ["received-once"]
    button(app, "Reabrir livro para conferir").click().run(timeout=15)
    assert not app.exception and app.session_state["state"]["autosave_status"] == "needs_review"
    current = next(item for item in app.text_area if item.label == "Versão salva atual")
    assert "outra_editora" in current.value
    assert "recebido_para_conferir" in next(item for item in app.text_area if item.label == "Resultado recebido").value
    next(item for item in app.checkbox if item.label == "Conferi a versão atual e quero reaplicar o resultado recebido.").check().run(timeout=15)
    button(app, "Salvar o resultado conferido").click().run(timeout=15)
    assert not app.exception and not app.error
    assert calls == ["received-once"]
    saved = armazenamento.carregar_livro("", reference)
    assert saved["versao_roteirista_autoral"] == received
    assert saved["editorial_note"] == "A nota concorrente precisa permanecer."
    assert "autosave_pending" not in app.session_state["state"]
    assert "Pedir outra geração" in [item.label for item in app.button]


def test_coloring_master_generation_reopens_and_exports_without_another_image_call(
        isolated_studio, coloring_project, monkeypatch):
    state, original = coloring_project
    character, master = official_master(original)
    before = sha256(original.read_bytes()).hexdigest()
    master_document = isolated_studio.get_json(f"character_universe/{character['id']}.json")
    calls = []
    monkeypatch.setattr(coloring_studio, "obter_preset", lambda *_: None)
    monkeypatch.setattr(coloring_studio, "gerar_imagem", lambda **kwargs: calls.append(kwargs) or str(original))

    app = open_draft(deepcopy(state))
    next(w for w in app.selectbox if w.label == "Como você quer criar esta página?").select("👥 Personagem da Biblioteca → Line Art").run(timeout=15)
    next(w for w in app.text_input if w.label == "Nome da página").set_value("Lia com olhos de estrelas").run(timeout=15)
    button(app, "➕ Adicionar página ao projeto").click().run(timeout=15)
    button(app, "✨ Gerar").click().run(timeout=15)
    assert not app.exception and len(calls) == 1
    assert "verdes com estrelas brilhantes" in calls[0]["prompt"]
    assert "2 pontos de brilho" not in calls[0]["prompt"]
    app.button(key="ap_c_11").click().run(timeout=15)
    button(app, "📐 Diagramar projeto aprovado").click().run(timeout=15)
    assert not app.exception and app.session_state["etapa_c"] == "resultado"
    reference = app.session_state["caminho_salvo_c"]
    button(app, "📘 Gerar PDF do miolo de colorir").click().run(timeout=15)
    assert not app.exception and not app.error
    saved = armazenamento.carregar_livro_colorir(reference)
    generated = saved["paginas"][-1]
    assert generated["character_id"] == character["id"]
    assert generated["character_master_asset_id"] == master["id"]
    assert generated["aprovada"] is True
    reader = PdfReader(saved["pdf_miolo"])
    assert len(reader.pages) == 26
    assert sum(bool(image_objects(page)) for page in reader.pages) == 12
    assert len(calls) == 1
    assert sha256(original.read_bytes()).hexdigest() == before
    assert isolated_studio.get_json(f"character_universe/{character['id']}.json") == master_document
    assert len(isolated_studio.list("livros_colorir")) == 1


def test_teen_devotional_native_creation_metadata_review_exports_and_visual_handoff(
        durable, monkeypatch):
    import ai_provider_router
    import author_profiles
    import editorial_dispatch as dispatch
    import editorial_products as products
    import painel_visual
    import streamlit as st
    from emotional_visual_binding import require_book_emotional_map
    from test_editorial_products import unit_for

    monkeypatch.setattr(author_profiles, "BACKEND", durable)
    monkeypatch.setattr(painel_visual, "_sidebar_page_link", lambda *_a, **_k: None)
    monkeypatch.setattr(ai_provider_router, "provider_status", lambda **_: {"gemini": True, "groq": False, "openrouter": False})
    author = author_profiles.create_author_profile("Autora do devocional")
    native_page = ROOT / "pages/55_📚_Produtos_Editoriais.py"
    app = AppTest.from_file(str(native_page)).run(timeout=20)
    control(app, "selectbox", "Tipo de produto").set_value("teen_devotional").run(timeout=20)
    control(app, "text_input", "Título").set_value("Esperança na adolescência")
    control(app, "text_area", "O que este produto deve abordar?").set_value("Esperança e cuidado na rotina dos adolescentes.")
    control(app, "text_input", "Referência bíblica fornecida por você").set_value("Salmo 27:14")
    control(app, "number_input", "Unidades").set_value(1).run(timeout=20)
    button(app, "Criar e salvar projeto").click().run(timeout=20)
    assert not app.exception and not app.error
    source = deepcopy(app.session_state["editorial_product_state"])
    reference, identity = source["storage_path"], source["book_id"]
    audience = source["editorial_product"]["spec"]["audience"]
    assert audience == "teen"
    calls = []

    def provider(**_kwargs):
        calls.append("one-devotional-unit")
        value = unit_for(source)
        value["source_refs"] = []
        return value

    monkeypatch.setattr(ai_provider_router, "chamar_llm", provider)
    control(app, "checkbox", "Autorizo a geração das unidades pendentes e o custo do provedor").check().run(timeout=20)
    button(app, "Gerar / retomar unidades").click().run(timeout=20)
    assert not app.exception and not app.error
    assert calls == ["one-devotional-unit"]
    before = products.load_product(reference)
    attempts = deepcopy(before["editorial_product"]["execution"]["attempts"])
    units = deepcopy(before["editorial_product"]["units"])
    # All following actions must retain the received content without buying it again.
    monkeypatch.setattr(ai_provider_router, "chamar_llm", lambda **_: pytest.fail("Metadata/review/export/handoff cannot regenerate units"))

    authors = AppTest.from_file(str(ROOT / "pages/32_✍️_Autores_e_Colaboradores.py")).run(timeout=20)
    button(authors, "Salvar autoria deste projeto").click().run(timeout=20)
    assert not authors.exception and not authors.error
    readiness = AppTest.from_file(str(ROOT / "pages/37_🧠_Agent_Skills_Bestseller_Readiness.py")).run(timeout=20)
    button(readiness, "💾 Salvar Bestseller Readiness neste projeto").click().run(timeout=20)
    assert not readiness.exception
    assert [item.value for item in readiness.error] == ["Existem fatores controláveis bloqueantes."]
    assert any("Readiness e auditoria" in item.value for item in readiness.success)
    emotional = AppTest.from_file(str(ROOT / "pages/17_🎭_Emotional_Color_Director.py"))
    emotional.session_state["state"] = products.load_product(reference)
    emotional.run(timeout=20)
    control(emotional, "text_input", "Responsável pela revisão emocional").set_value("Revisora de aceitação")
    control(emotional, "checkbox", "Revisei todas as cenas, a direção emocional e a preservação dos Masters").check().run(timeout=20)
    button(emotional, "💾 Aplicar e salvar este mapa no livro ativo").click().run(timeout=20)
    assert not emotional.exception and not emotional.error
    current = products.load_product(reference)
    assert current["authorship"]["authors"][0]["profile_id"] == author["id"]
    assert current["agent_skill_audit"]["ok"] and current["bestseller_readiness_report"]["criteria"]
    require_book_emotional_map(current)
    assert current["editorial_product"]["units"] == units
    assert current["editorial_product"]["execution"]["attempts"] == attempts

    reviewed = AppTest.from_file(str(native_page))
    reviewed.session_state["editorial_product_id"] = reference
    reviewed.run(timeout=20)
    control(reviewed, "text_input", "Responsável pela revisão").set_value("Revisora do devocional")
    control(reviewed, "checkbox", "Revisei conteúdo, linguagem e adequação ao público").check()
    control(reviewed, "checkbox", "Conferi precisão, fontes, referências bíblicas e gabaritos aplicáveis").check().run(timeout=20)
    button(reviewed, "Aprovar esta versão").click().run(timeout=20)
    assert not reviewed.exception and not reviewed.error
    control(reviewed, "checkbox", "Exportar prévia de rascunho para revisão").uncheck().run(timeout=20)
    button(reviewed, "Preparar arquivo").click().run(timeout=20)
    assert not reviewed.exception and not reviewed.error
    control(reviewed, "selectbox", "Formato").set_value("epub").run(timeout=20)
    button(reviewed, "Preparar arquivo").click().run(timeout=20)
    assert not reviewed.exception and not reviewed.error
    final = products.load_product(reference)
    assert final["book_id"] == identity and final["editorial_product"]["spec"]["audience"] == audience
    artifacts = {item["format"]: item for item in final["editorial_product"]["exports"]}
    assert set(artifacts) == {"pdf", "epub"} and all(not item["draft"] for item in artifacts.values())
    pdf = PdfReader(storage.materializar(artifacts["pdf"]["storage_ref"]))
    assert "Salmo 27:14" in "\n".join(page.extract_text() for page in pdf.pages)
    with zipfile.ZipFile(storage.materializar(artifacts["epub"]["storage_ref"])) as archive:
        assert "Salmo 27:14" in archive.read("EPUB/book.xhtml").decode()
    # AppTest cannot navigate another registered page; capture only its navigation,
    # while executing the actual saved-product attachment and session handoff.
    navigated = []
    monkeypatch.setattr(st, "switch_page", lambda path: navigated.append(path))
    button(reviewed, "Planejar ilustrações no Orquestrador").click().run(timeout=20)
    assert not reviewed.exception and not reviewed.error
    assert navigated == ["pages/0_🤖_Orquestrador_FaithBloom.py"]
    run = dispatch.load_run(reviewed.session_state["editorial_run_id"])
    assert run["source_ref"] == reference and run["source"]["book_id"] == identity
    assert run["route_plan"]["audience"] == audience
    assert reviewed.session_state[f"optional_visual_{run['id']}"] is True
    assert calls == ["one-devotional-unit"] and len(durable.list("livros")) == 1

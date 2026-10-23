"""Family contracts, recovery, named review and real shared PDF/EPUB exports."""
from copy import deepcopy
from pathlib import Path
import json
import zipfile

import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

import armazenamento
import editorial_products as studio
import storage_backend
from storage_backend import LocalStorageBackend


SOURCES = [{"id": "material_1", "label": "Material fornecido pela autora", "content": "Uma semana tem sete dias. O primeiro número natural após zero é um.", "url": "https://example.org/material"}]


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    backend = LocalStorageBackend(str(tmp_path / "durable"))
    monkeypatch.setattr(storage_backend, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage_backend, "CACHE_DIR", cache)
    monkeypatch.chdir(tmp_path)
    return backend


def project(kind="study_book", count=2, **kwargs):
    return studio.create_product(kind, "Produto para revisão", "Aprender com clareza e acolhimento", unit_count=count,
                                 sources=deepcopy(SOURCES), bible_reference="Salmo 27:14",
                                 custom_blocks=["Abertura", "Prática"], **kwargs)


def unit_for(product, plan=None):
    plan = plan or product["editorial_product"]["unit_plan"][0]
    spec = product["editorial_product"]["spec"]
    family = plan["family"]
    unit = {"title": f"Unidade {plan['number']}", "objectives": ["Aprender a observar com atenção"],
            "source_refs": [SOURCES[0]["id"]]}
    if family == "advice":
        unit.update(situation="Uma pessoa espera a sua vez.", advice="Observe quem está falando e aguarde com calma.",
                    reflection="Como você se sente ao ser ouvido?", activity="Converse com alguém de confiança.")
    elif family == "devotional":
        unit.update(bible_reference=spec["bible_reference"], reflection="Esperar pode ser difícil e podemos pedir ajuda.",
                    application="Pratique uma espera pequena hoje.", prayer="Deus, ajuda-nos a agir com amor e calma.",
                    challenge="Ofereça um gesto de cuidado a alguém.")
    elif family == "development":
        unit.update(body="Observar a rotina pode revelar novas escolhas.", reflection="O que você deseja melhorar?",
                    action_plan=["Anote uma ação pequena para esta semana."], progress_question="O que mudou na sua rotina?")
    elif family in {"study", "workbook"}:
        unit.update(body="Uma semana tem sete dias.", questions=[{"question": "Quantos dias há em uma semana?", "answer": "Sete", "explanation": "O material fornecido informa que uma semana tem sete dias."}])
        if family == "workbook":
            unit.update(instructions="Leia o material e responda com suas palavras.", response_lines=3)
    elif family == "flashcards":
        unit.update(cards=[{"front": "Quantos dias há em uma semana?", "back": "Sete dias", "source_refs": [SOURCES[0]["id"]]}])
    else:
        unit.update(blocks=[{"label": label, "text": f"Conteúdo da seção {label} para revisão."} for label in spec["custom_blocks"]])
    return unit


def provider_for(product, calls=None):
    def provider(*, sistema, instrucao):
        request = json.loads(instrucao)
        if calls is not None:
            calls.append(request["unit_plan"]["number"])
        assert "somente JSON" in sistema
        assert "accuracy_verified_by_ai" not in request
        return unit_for(product, request["unit_plan"])
    return provider


@pytest.mark.parametrize("kind", list(studio.PRODUCT_DNAS))
def test_each_specialist_generates_valid_shared_state_and_reopens(isolated, kind):
    product = project(kind)
    calls = []
    studio.generate_product(product, provider_for(product, calls), confirmed=True)
    assert calls == [1, 2]
    assert len(product["editorial_product"]["units"]) == 2
    assert product["cenas_texto"] and all(scene["texto"].strip() for scene in product["cenas_texto"])
    assert not product["revisao_aprovada"]
    report = studio.validate_product(product)
    assert report["ok"] and not report["ready_for_final_export"] and not report["accuracy_verified_by_ai"]
    reopened = studio.load_product(product["storage_path"])
    assert reopened["book_id"] == product["book_id"]
    assert reopened["editorial_product"]["units"] == product["editorial_product"]["units"]
    assert studio.list_products()[0]["storage_path"] == product["storage_path"]
    # Reopening and pressing resume never buys a second complete version.
    studio.generate_product(reopened, lambda **_: pytest.fail("Completed units must not regenerate"))


def test_resume_provider_failure_retains_and_skips_successful_units(isolated):
    product = project(count=3)
    calls = []
    good = provider_for(product, calls)
    def fail_second(**kwargs):
        if len(calls) == 1:
            raise RuntimeError("provider temporarily offline")
        return good(**kwargs)
    with pytest.raises(RuntimeError, match="temporarily"):
        studio.generate_product(product, fail_second, confirmed=True)
    assert calls == [1]
    assert not product["editorial_product"]["units"]
    reopened = studio.load_product(product["storage_path"])
    assert len(reopened["editorial_product"]["draft"]["units"]) == 1
    studio.generate_product(reopened, provider_for(reopened, calls), confirmed=True)
    assert calls == [1, 2, 3]
    assert len(reopened["editorial_product"]["units"]) == 3


def test_storage_failure_preserves_paid_output_in_memory_before_next_call(isolated):
    product = project()
    calls = []
    def fail_after_first_unit(state):
        if len((state["editorial_product"].get("draft") or {}).get("units", [])) == 1:
            raise OSError("storage unavailable")
        studio.save_product(state)
    with pytest.raises(OSError):
        studio.generate_product(product, provider_for(product, calls), checkpoint=fail_after_first_unit, confirmed=True)
    assert calls == [1] and len(product["editorial_product"]["draft"]["units"]) == 1
    studio.generate_product(product, provider_for(product, calls), confirmed=True)
    assert calls == [1, 2]


def test_no_provider_called_if_initial_persistence_fails():
    product = project()
    def cannot_save(_):
        raise OSError("storage offline")
    with pytest.raises(OSError):
        studio.generate_product(product, lambda **_: pytest.fail("Must not spend before checkpoint"), checkpoint=cannot_save, confirmed=True)


def test_failed_final_save_retries_persistence_without_regenerating_or_duplication(isolated):
    product = project(count=1)
    calls = []
    def fail_on_final(state):
        if state["editorial_product"]["units"] and not state["editorial_product"].get("draft"):
            raise OSError("final save failed")
        studio.save_product(state)
    with pytest.raises(OSError, match="final save"):
        studio.generate_product(product, provider_for(product, calls), checkpoint=fail_on_final, confirmed=True)
    assert product["editorial_product"]["units"] and calls == [1]
    studio.generate_product(product, lambda **_: pytest.fail("Final output must not be bought again"))
    assert studio.load_product(product["storage_path"])["editorial_product"]["draft"] is None
    assert not product["editorial_product"]["versions"]


def test_shared_default_router_is_used_without_duplicate_provider_client(isolated, monkeypatch):
    import ai_provider_router
    product = project(count=1)
    calls = []
    monkeypatch.setattr(ai_provider_router, "chamar_llm", provider_for(product, calls))
    monkeypatch.setattr(ai_provider_router, "provider_status", lambda: {"gemini": True})
    studio.generate_product(product, confirmed=True)
    assert calls == [1]


def test_budget_failure_blocks_provider_before_first_unit(isolated, monkeypatch):
    import controle_geracao
    product = project(count=1)
    def over_budget(_):
        raise RuntimeError("daily budget exceeded")
    monkeypatch.setattr(controle_geracao, "validar_orcamento", over_budget)
    with pytest.raises(RuntimeError, match="daily budget"):
        studio.generate_product(product, lambda **_: pytest.fail("Must not call provider over budget"), confirmed=True)
    assert not product["editorial_product"]["draft"]["units"]


@pytest.mark.parametrize("invalid", [None, [], {}, {"title": ""}, {"unit": {"title": "No body"}}])
def test_invalid_output_does_not_activate_or_destroy_prior_version(isolated, invalid):
    product = project(count=1)
    studio.generate_product(product, provider_for(product), confirmed=True)
    prior = deepcopy(product["editorial_product"]["units"])
    with pytest.raises(ValueError):
        studio.generate_product(product, lambda **_: invalid, new_version=True, confirmed=True)
    assert product["editorial_product"]["units"] == prior
    assert not product["editorial_product"]["draft"]["units"]


@pytest.mark.parametrize("change", ["source", "answer", "explanation", "objectives"])
def test_educational_units_reject_invented_sources_empty_answers_and_objectives(change):
    product = project(count=1)
    unit = unit_for(product)
    if change == "source":
        unit["source_refs"] = ["invented_citation"]
    elif change in {"answer", "explanation"}:
        unit["questions"][0][change] = " "
    else:
        unit["objectives"] = []
    with pytest.raises(ValueError):
        studio.validate_unit(unit, product["editorial_product"]["unit_plan"][0], product["editorial_product"]["spec"])


def test_devotional_reference_is_exact_and_extra_scripture_field_is_rejected():
    product = project("teen_devotional", count=1)
    plan = product["editorial_product"]["unit_plan"][0]
    spec = product["editorial_product"]["spec"]
    unit = unit_for(product)
    unit["bible_reference"] = "Invented 1:1"
    with pytest.raises(ValueError, match="alterada"):
        studio.validate_unit(unit, plan, spec)
    unit = unit_for(product)
    unit["bible_text"] = "Invented quotation"
    with pytest.raises(ValueError, match="inesperados"):
        studio.validate_unit(unit, plan, spec)
    system, instruction = studio.build_generation_prompt(product, plan)
    assert "sem infantilização" in system and "somente a referência exata" in system


def test_custom_blocks_must_match_authors_names_and_order():
    product = project("other", count=1)
    unit = unit_for(product)
    unit["blocks"].reverse()
    with pytest.raises(ValueError, match="nomes e a ordem"):
        studio.validate_unit(unit, product["editorial_product"]["unit_plan"][0], product["editorial_product"]["spec"])


def test_provider_cannot_pass_schema_examples_as_generated_content():
    product = project(count=1)
    plan = product["editorial_product"]["unit_plan"][0]
    spec = product["editorial_product"]["spec"]
    with pytest.raises(ValueError, match="exemplos"):
        studio.validate_unit(studio._unit_schema(plan["family"], spec), plan, spec)


def test_flashcards_require_nonempty_back_and_source_for_each_card():
    product = project("flashcards", count=1)
    unit = unit_for(product)
    unit["cards"][0]["back"] = " "
    with pytest.raises(ValueError, match="Verso"):
        studio.validate_unit(unit, product["editorial_product"]["unit_plan"][0], product["editorial_product"]["spec"])
    unit = unit_for(product)
    unit["cards"][0]["source_refs"] = []
    with pytest.raises(ValueError, match="source_refs"):
        studio.validate_unit(unit, product["editorial_product"]["unit_plan"][0], product["editorial_product"]["spec"])


def test_hybrid_devotional_workbook_is_one_durable_exportable_product(isolated):
    product = project("children_devotional", count=4, hybrid_types=["workbook"])
    studio.generate_product(product, provider_for(product), confirmed=True)
    assert [unit["family"] for unit in product["editorial_product"]["units"]] == ["devotional", "workbook", "devotional", "workbook"]
    text = "\n".join(scene["texto"] for scene in product["cenas_texto"])
    assert "Salmo 27:14" in text and "Gabarito comentado" in text and "________________________" in text


def test_review_is_named_and_bound_to_version_then_revision_and_restore_preserve_history(isolated):
    product = project(count=1)
    studio.generate_product(product, provider_for(product), confirmed=True)
    original = deepcopy(product["editorial_product"]["units"])
    original_id = product["editorial_product"]["active_version"]
    with pytest.raises(ValueError, match="Confirme"):
        studio.approve_product(product, "Revisora", content_reviewed=True, accuracy_reviewed=False)
    with pytest.raises(ValueError, match="Responsável"):
        studio.approve_product(product, " ", content_reviewed=True, accuracy_reviewed=True)
    studio.approve_product(product, "Revisora", content_reviewed=True, accuracy_reviewed=True)
    assert studio.validate_product(product)["ready_for_final_export"]
    revised = deepcopy(original[0])
    revised["title"] = "Unidade revisada"
    studio.revise_unit(product, 1, revised)
    assert not studio.validate_product(product)["ready_for_final_export"]
    assert product["editorial_product"]["versions"][0]["units"] == original
    studio.restore_version(product, original_id)
    assert product["editorial_product"]["units"] == original
    assert not product["revisao_aprovada"]
    assert studio.load_product(product["storage_path"])["editorial_product"]["units"] == original


def test_mutating_content_or_source_after_approval_invalidates_final_export(isolated):
    product = project(count=1)
    studio.generate_product(product, provider_for(product), confirmed=True)
    studio.approve_product(product, "Revisora", content_reviewed=True, accuracy_reviewed=True)
    product["editorial_product"]["spec"]["sources"][0]["content"] = "Material novo não revisado"
    assert not studio.validate_product(product)["ready_for_final_export"]
    with pytest.raises(ValueError, match="Revise"):
        studio.build_export_state(product)


def test_new_version_preserves_old_until_complete_and_needs_fresh_review(isolated):
    product = project(count=1)
    studio.generate_product(product, provider_for(product), confirmed=True)
    studio.approve_product(product, "Revisora", content_reviewed=True, accuracy_reviewed=True)
    old = product["editorial_product"]["active_version"]
    studio.generate_product(product, provider_for(product), new_version=True, confirmed=True)
    assert product["editorial_product"]["active_version"] != old
    assert product["editorial_product"]["versions"][0]["id"] == old
    assert not studio.validate_product(product)["ready_for_final_export"]


def test_changed_brief_blocks_resume_before_another_provider_call(isolated):
    product = project(count=2)
    with pytest.raises(RuntimeError):
        studio.generate_product(product, lambda **_: (_ for _ in ()).throw(RuntimeError("offline")), confirmed=True)
    product["editorial_product"]["spec"]["brief"] = "Changed intent"
    with pytest.raises(ValueError, match="mudou"):
        studio.generate_product(product, lambda **_: pytest.fail("Changed context must not call provider"), confirmed=True)


@pytest.mark.parametrize("kind", ["study_book", "workbook", "flashcards", "teen_devotional", "other"])
def test_real_pdf_and_epub_preserve_family_content_and_durable_assets(isolated, tmp_path, kind):
    product = project(kind, count=1)
    studio.generate_product(product, provider_for(product), confirmed=True)
    with pytest.raises(ValueError, match="Revise"):
        studio.export_product(product, "pdf", output_path=str(tmp_path / "blocked.pdf"))
    assert not (tmp_path / "blocked.pdf").exists()
    pdf = studio.export_product(product, "pdf", output_path=str(tmp_path / "preview.pdf"), draft=True)
    reader = PdfReader(pdf["path"])
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "RASCUNHO" in text and "Unidade 1" in text
    assert len(reader.pages) >= 24 and not len(reader.pages) % 2
    assert not pdf["publication_ready"] and pdf["text_only_preflight"]
    studio.approve_product(product, "Revisora", content_reviewed=True, accuracy_reviewed=True)
    epub = studio.export_product(product, "epub", output_path=str(tmp_path / "reviewed.epub"))
    with zipfile.ZipFile(epub["path"]) as archive:
        body = archive.read("EPUB/book.xhtml").decode()
        assert "Unidade 1" in body and "RASCUNHO" not in body
        if kind == "workbook":
            assert "Gabarito comentado" in body and "Sete" in text
        if kind == "flashcards":
            assert "Frente" in body and "Verso" in body
        if kind == "teen_devotional":
            assert "Salmo 27:14" in body and "Oração" in body and "Desafio" in body
    assert not epub["epubcheck_passed"] and not epub["publication_ready"]
    reopened = studio.load_product(product["storage_path"])
    assert len(reopened["editorial_product"]["exports"]) == 2
    assert isolated.get_bytes(pdf["storage_ref"].replace("fb://", "", 1)).startswith(b"%PDF")


def test_long_text_paginates_without_losing_content(isolated, tmp_path):
    product = project(count=1)
    unit = unit_for(product)
    unit["body"] = " ".join(f"palavra{i}" for i in range(1500))
    studio.generate_product(product, lambda **_: unit, confirmed=True)
    state = studio.build_export_state(product, draft=True)
    combined = " ".join(scene["texto"] for scene in state["cenas_texto"])
    assert "palavra0" in combined and "palavra1499" in combined
    pdf = studio.export_product(product, "pdf", output_path=str(tmp_path / "long.pdf"), draft=True)
    text = " ".join(page.extract_text() for page in PdfReader(pdf["path"]).pages)
    assert all(f"palavra{i}" in text for i in range(1500))


def test_specialist_page_initial_open_and_dispatcher_saved_ref_render(isolated, monkeypatch):
    # AppTest uses the specialist file as entrypoint; shared sidebar paths belong
    # to the real app.py navigation context, so only those links are omitted.
    import painel_visual
    monkeypatch.setattr(painel_visual, "_sidebar_page_link", lambda *args, **kwargs: None)
    page = Path(studio.__file__).parent / "pages/55_📚_Produtos_Editoriais.py"
    app = AppTest.from_file(str(page)).run(timeout=15)
    assert not app.exception
    product = project("teen_advice", count=1)
    studio.generate_product(product, provider_for(product), confirmed=True)
    app = AppTest.from_file(str(page))
    app.session_state["editorial_product_id"] = product["storage_path"]
    app.run(timeout=15)
    assert not app.exception
    assert app.session_state["editorial_product_state"]["book_id"] == product["book_id"]


def test_human_ui_creates_generates_reviews_and_downloads_a_product(isolated, monkeypatch):
    import ai_provider_router
    import painel_visual
    monkeypatch.setattr(painel_visual, "_sidebar_page_link", lambda *args, **kwargs: None)
    monkeypatch.setattr(ai_provider_router, "provider_status", lambda: {"gemini": True, "groq": False, "openrouter": False})
    page = Path(studio.__file__).parent / "pages/55_📚_Produtos_Editoriais.py"
    def control(items, label):
        return next(item for item in items if item.label == label)
    app = AppTest.from_file(str(page)).run(timeout=15)
    control(app.selectbox, "Tipo de produto").set_value("children_advice").run()
    control(app.text_input, "Título").set_value("Conselhos para conversar")
    control(app.text_area, "O que este produto deve abordar?").set_value("Respeitar a vez de falar, acolher e ouvir o outro.")
    control(app.number_input, "Unidades").set_value(1).run()
    control(app.button, "Criar e salvar projeto").click().run()
    assert not app.exception
    product_state = app.session_state["editorial_product_state"]
    assert product_state["storage_path"] and not product_state["editorial_product"]["units"]
    def provider(**kwargs):
        request = json.loads(kwargs["instrucao"])
        output = unit_for(product_state, request["unit_plan"])
        output["source_refs"] = []
        return output
    monkeypatch.setattr(ai_provider_router, "chamar_llm", provider)
    control(app.checkbox, "Autorizo a geração das unidades pendentes e o custo do provedor").check().run()
    control(app.button, "Gerar / retomar unidades").click().run()
    assert not app.exception
    assert app.session_state["editorial_product_state"]["editorial_product"]["units"]
    control(app.text_input, "Responsável pela revisão").set_value("Revisora da equipe")
    control(app.checkbox, "Revisei conteúdo, linguagem e adequação ao público").check()
    control(app.checkbox, "Conferi precisão, fontes, referências bíblicas e gabaritos aplicáveis").check().run()
    control(app.button, "Aprovar esta versão").click().run()
    assert not app.exception
    assert studio.validate_product(app.session_state["editorial_product_state"])["ready_for_final_export"]
    control(app.checkbox, "Exportar prévia de rascunho para revisão").uncheck().run()
    control(app.selectbox, "Formato").set_value("epub").run()
    control(app.button, "Preparar arquivo").click().run()
    assert not app.exception
    artifact = app.session_state["editorial_product_state"]["editorial_product"]["exports"][0]
    assert not artifact["draft"] and artifact["format"] == "epub"
    assert isolated.get_bytes(artifact["storage_ref"].replace("fb://", "", 1)).startswith(b"PK")


@pytest.mark.parametrize("kind", ["study_book", "workbook", "flashcards"])
def test_educational_creation_requires_real_source_excerpt(kind):
    with pytest.raises(ValueError, match="fonte"):
        studio.create_product(kind, "Title", "Brief", sources=[])
    with pytest.raises(ValueError, match="Trecho"):
        studio.create_product(kind, "Title", "Brief", sources=[{"label": "Link only", "content": "", "url": "https://example.org"}])


@pytest.mark.parametrize("kind,audience", [("teen_advice", "3_8"), ("teen_devotional", "6_8"), ("children_advice", "teen"), ("children_devotional", "adult")])
def test_incompatible_audience_is_rejected_before_provider(kind, audience):
    with pytest.raises(ValueError, match="público"):
        project(kind, audience=audience)


@pytest.mark.parametrize("reference", ["", "tenha fé", "Salmo 0:14", "Salmo 27:0", "João 3:18-16"])
def test_devotional_requires_reference_shape_and_valid_positive_range(reference):
    with pytest.raises(ValueError):
        studio.create_product("teen_devotional", "Título", "Brief", bible_reference=reference)


def test_bible_guard_syntax_does_not_claim_reference_existence_or_theological_accuracy():
    report = studio.validate_bible_reference("João 3:16-18")
    assert report["syntax_valid"] and not report["canonical_existence_verified"]


@pytest.mark.parametrize("kind,audience", [("teen_advice", "teen"), ("study_book", "adult"), ("other", "custom")])
def test_canonical_reader_age_is_preserved_and_typography_fallback_is_separate(isolated, kind, audience):
    product = project(kind, count=1, audience=audience)
    studio.generate_product(product, provider_for(product), confirmed=True)
    assert product["faixa_etaria"] == product["age_profile_id"] == audience
    assert product["editorial_typography_age_profile"] == "9-12"
    exported = studio.build_export_state(product, draft=True)
    assert exported["editorial_audience"] == audience
    assert studio.load_product(product["storage_path"])["faixa_etaria"] == audience

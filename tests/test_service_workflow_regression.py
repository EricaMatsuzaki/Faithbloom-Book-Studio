"""Real Studio pages and source boundaries, with no paid provider calls."""
from copy import deepcopy
from pathlib import Path
import pickle

import pytest
from streamlit.testing.v1 import AppTest

import age_profiles
import armazenamento
import audiobook_studio as audio
import estilo
import fila_producao
import gemini_client
import google_cloud_tts
import japanese_localization_bridge
import openrouter_client
import streamlit as st
import translation_localization as translation
import publishing_distribution as distribution
from reportlab.pdfgen import canvas
from pypdf import PdfReader


ROOT=Path(__file__).resolve().parents[1]


def master(title="Livro A"):
    return {"titulo":title,"colecao":"Coleção","idioma_original":"pt-BR",
            "faixa_etaria":"3-8","cenas_texto":[{"numero":1,"texto":title+" português."}],
            "licao_final":"Uma lição em português."}


def localized(state,locale="en-US"):
    return {"titulo":state["titulo"]+" translated","locale":locale,"versao_id":"v1",
            "bible_ai_translation_allowed":False,"cenas_texto":[{"numero":1,"texto":"A translated story."}],
            "source_fingerprint":translation.translation_source_fingerprint(state)}


def button(app,label):
    return next(item for item in app.button if item.label==label)


def select(app,label):
    return next(item for item in app.selectbox if item.label==label)


def test_age_options_can_be_copied_and_pickled_for_real_streamlit_widgets():
    options=age_profiles.opcoes_faixa_etaria()
    for option in options:
        for copied in (deepcopy(option),pickle.loads(pickle.dumps(option))):
            assert copied.profile_id==option.profile_id
            assert copied.label==option.label
            assert copied==option.profile_id


def test_translation_page_preserves_pending_drafts_without_crossing_book_or_locale(monkeypatch):
    books=[{"titulo":"Livro A","colecao":"Coleção","arquivo":"a.json"},
           {"titulo":"Livro B","colecao":"Coleção","arquivo":"b.json"}]
    sources={"a.json":master("Livro A"),"b.json":master("Livro B")}
    projects={b["titulo"]:{"id":b["titulo"],"titulo":b["titulo"],"colecao":"Coleção","source_ref":b["arquivo"],"edicoes":{}} for b in books}
    saved=[]
    monkeypatch.setattr(estilo,"aplicar_estilo",lambda:None)
    monkeypatch.setattr(armazenamento,"listar_livros",lambda:books)
    monkeypatch.setattr(armazenamento,"carregar_livro",lambda _c,path:deepcopy(sources[path]))
    monkeypatch.setattr(translation,"listar_projetos_traducao",lambda:list(projects.values()))
    monkeypatch.setattr(translation,"carregar_projeto_traducao",lambda pid:deepcopy(projects[pid]))
    monkeypatch.setattr(translation,"salvar_projeto_traducao",lambda p:p)
    monkeypatch.setattr(translation,"adicionar_versao_localizada",lambda p,locale,draft,label:saved.append((p["titulo"],locale,draft["titulo"])) or p)
    monkeypatch.setattr(japanese_localization_bridge,"localizar_livro_com_reading_guard",lambda state,_llm,locale,**kwargs:localized(state,locale))
    app=AppTest.from_file(ROOT/"pages/21_Translation_Localization_Studio.py").run()
    assert not app.exception
    button(app,"🌍 Gerar localização").click().run()
    assert not app.exception
    select(app,"📚 Livro Master").set_value("Livro B · Coleção").run()
    assert not app.exception
    assert not any(b.label=="💾 Salvar esta versão" for b in app.button)
    select(app,"📚 Livro Master").set_value("Livro A · Coleção").run()
    assert app.session_state["r06_translation"]["titulo"]=="Livro A translated"
    select(app,"Idioma + mercado").set_value("ja-JP").run()
    assert not any(b.label=="💾 Salvar esta versão" for b in app.button)
    select(app,"Idioma + mercado").set_value("en-US").run()
    button(app,"💾 Salvar esta versão").click().run()
    assert not app.exception
    assert saved==[("Livro A","en-US","Livro A translated")]


@pytest.mark.parametrize("existing_b_project",[True,False])
def test_same_title_translation_books_and_projects_keep_distinct_source_paths(monkeypatch,existing_b_project):
    books=[{"titulo":"Mesmo título","colecao":"Coleção","arquivo":name+".json","storage_path":"books/"+name+".json"} for name in ("a","b")]
    sources={book["storage_path"]:{**master("Mesmo título"),"cenas_texto":[{"numero":1,"texto":book["arquivo"]}]} for book in books}
    projects=[{"id":"project-a","titulo":"Mesmo título","colecao":"Coleção","source_ref":"fb://books/a.json","edicoes":{}}]
    if existing_b_project:
        projects.append({"id":"project-b","titulo":"Mesmo título","colecao":"Coleção","source_ref":"books/b.json","edicoes":{}})
    saved=[]
    monkeypatch.setattr(estilo,"aplicar_estilo",lambda:None)
    monkeypatch.setattr(armazenamento,"listar_livros",lambda:books)
    monkeypatch.setattr(armazenamento,"carregar_livro",lambda _c,path:deepcopy(sources[path]))
    monkeypatch.setattr(translation,"listar_projetos_traducao",lambda:deepcopy(projects))
    monkeypatch.setattr(translation,"carregar_projeto_traducao",lambda pid:deepcopy(next(p for p in projects if p["id"]==pid)))
    monkeypatch.setattr(translation,"salvar_projeto_traducao",lambda p:p)
    monkeypatch.setattr(translation,"adicionar_versao_localizada",lambda p,locale,draft,label:saved.append((p["id"],p["source_ref"],draft["cenas_texto"][0]["texto"])) or p)
    def translate(state,_llm,locale,**kwargs):
        draft=localized(state,locale)
        draft["cenas_texto"][0]["texto"]="Translated "+state["cenas_texto"][0]["texto"]
        return draft
    def create(title,collection,language,source):
        project={"id":"new-project-b","titulo":title,"colecao":collection,"source_ref":source,"edicoes":{}}
        projects.append(project)
        return project
    monkeypatch.setattr(japanese_localization_bridge,"localizar_livro_com_reading_guard",translate)
    monkeypatch.setattr(translation,"criar_projeto_traducao",create)
    app=AppTest.from_file(ROOT/"pages/21_Translation_Localization_Studio.py").run()
    assert not app.exception
    assert len(select(app,"📚 Livro Master").options)==2
    select(app,"📚 Livro Master").set_value("Mesmo título · Coleção · books/b.json").run()
    button(app,"🌍 Gerar localização").click().run()
    assert not app.exception
    if not existing_b_project:
        assert not any(b.label=="💾 Salvar esta versão" for b in app.button)
        button(app,"Criar projeto de tradução para este Master").click().run()
    button(app,"💾 Salvar esta versão").click().run()
    assert not app.exception
    assert saved==[("project-b" if existing_b_project else "new-project-b","books/b.json","Translated b.json")]


def test_translation_backend_refuses_saving_draft_under_another_locale(monkeypatch):
    monkeypatch.setattr(translation,"_save_json",lambda *args:pytest.fail("A mismatched draft must not be persisted"))
    with pytest.raises(ValueError,match="idioma do rascunho"):
        translation.adicionar_versao_localizada({"id":"audit"},"ja-JP",{"locale":"en-US"})


@pytest.mark.parametrize("edition",[None,{"locale":"ja-JP","cenas_texto":[]},
    {"locale":"en-US","cenas_texto":[{"texto":"Wrong market."}]},
    {"locale":"ja-JP","source_fingerprint":"stale","cenas_texto":[{"texto":"Old source."}]}])
def test_audio_refuses_missing_wrong_or_stale_locale_text(edition):
    state=master()
    if edition is not None:state["traducoes"]={"ja-JP":edition}
    with pytest.raises(ValueError,match="Não há texto localizado em ja-JP"):
        audio.build_audio_source(state,"ja-JP")


def test_audio_keeps_valid_approved_translation_without_original_language_lesson():
    state=master(); draft=localized(state,"ja-JP")
    state["translation_versions"]={"ja-JP":[draft]}
    state["traducoes_aprovadas"]={"ja-JP":"v1"}
    before=deepcopy(state)
    source=audio.build_audio_source(state,"ja-JP")
    assert [s["texto"] for s in source["scenes"]]==["A translated story."]
    assert source["locale"]=="ja-JP"
    assert state==before


@pytest.mark.parametrize("validity",["approved","unapproved","other_source","stale","invalid_structure"])
def test_audio_reads_only_approved_studio_translation_for_its_source(monkeypatch,validity):
    state=master(); draft=localized(state,"ja-JP")
    project={"id":"translation-a","titulo":state["titulo"],"colecao":state["colecao"],
             "source_ref":"fb://books/a.json","edicoes":{"ja-JP":{"aprovada_id":"v1","versoes":[draft]}}}
    if validity=="unapproved":project["edicoes"]["ja-JP"]["aprovada_id"]=""
    if validity=="other_source":project["source_ref"]="books/b.json"
    if validity=="stale":draft["source_fingerprint"]="old"
    if validity=="invalid_structure":draft["cenas_texto"]=[]
    monkeypatch.setattr(translation,"listar_projetos_traducao",lambda:[project])
    monkeypatch.setattr(translation,"carregar_projeto_traducao",lambda _pid:deepcopy(project))
    before=deepcopy(state)
    source_state=audio.with_approved_audio_translation(state,"books/a.json","ja-JP")
    assert state==before
    if validity=="approved":
        assert audio.build_audio_source(source_state,"ja-JP")["scenes"][0]["texto"]=="A translated story."
    else:
        with pytest.raises(ValueError,match="Não há texto localizado"):
            audio.build_audio_source(source_state,"ja-JP")


def test_empty_embedded_translation_does_not_hide_approved_studio_edition(monkeypatch):
    state=master(); state["traducoes"]={"ja-JP":{"locale":"ja-JP","cenas_texto":[]}}
    draft=localized(state,"ja-JP")
    project={"id":"translation-a","titulo":state["titulo"],"colecao":state["colecao"],
             "source_ref":"books/a.json","edicoes":{"ja-JP":{"aprovada_id":"v1","versoes":[draft]}}}
    monkeypatch.setattr(translation,"listar_projetos_traducao",lambda:[project])
    monkeypatch.setattr(translation,"carregar_projeto_traducao",lambda _pid:deepcopy(project))
    source=audio.with_approved_audio_translation(state,"books/a.json","ja-JP")
    assert audio.build_audio_source(source,"ja-JP")["scenes"][0]["texto"]=="A translated story."


@pytest.mark.parametrize("provider,gemini,openrouter,enabled",[
    ("auto",True,False,True),("gemini",True,False,True),("openrouter",True,False,False),
    ("auto",False,True,True),("gemini",False,True,False),("auto",False,False,False),
])
def test_audiobook_page_renders_missing_audio_and_uses_configured_provider(monkeypatch,provider,gemini,openrouter,enabled):
    project=audio.create_audiobook_project("Audit",source_state=master())
    voice=audio.create_voice_profile("Narrador","pt-BR",provider_voice_id="Kore")
    project=audio.assign_voice(audio.upsert_project_voice(project,voice),"narrator",voice["id"])
    project["script_scenes"]=[audio.approve_script_scene(scene) for scene in project["script_scenes"]]
    job={"id":"audit-job","nome":"Audit","tipo":"audiobook_tts","metadata":{"project_id":project["id"]},"status":"fila","itens":[{"status":"pendente"}]}
    monkeypatch.setattr(estilo,"aplicar_estilo",lambda:None)
    monkeypatch.setattr(armazenamento,"listar_livros",lambda:[])
    monkeypatch.setattr(audio,"list_audiobook_projects",lambda:[])
    monkeypatch.setattr(audio,"load_audiobook_project",lambda _pid:deepcopy(project))
    monkeypatch.setattr(audio,"list_voice_profiles",lambda _locale:[])
    monkeypatch.setattr(fila_producao,"listar_jobs",lambda _limit:[job])
    monkeypatch.setattr(gemini_client,"gemini_disponivel",lambda:gemini)
    monkeypatch.setattr(openrouter_client,"PROVEDOR_TEXTO",provider)
    monkeypatch.setattr(openrouter_client,"OPENROUTER_API_KEY","audit-never-sent" if openrouter else "")
    app=AppTest.from_file(ROOT/"pages/24_🎧_Audiobook_Studio.py")
    app.session_state["r09_project_id"]=project["id"]
    app.run()
    assert not app.exception
    assert app.error  # Pending approval is shown instead of crashing the page.
    assert button(app,"▶️ Processar próximo").disabled is not enabled
    assert button(app,"⏩ Processar lote").disabled is not enabled
    assert button(app,"✨ Sugerir direção com AI Voice Director").disabled is not enabled


def test_audiobook_page_reports_untranslated_locale_without_creating_project(monkeypatch):
    monkeypatch.setattr(estilo,"aplicar_estilo",lambda:None)
    monkeypatch.setattr(armazenamento,"listar_livros",lambda:[{"titulo":"Livro A","colecao":"Coleção","arquivo":"a.json"}])
    monkeypatch.setattr(armazenamento,"carregar_livro",lambda _c,_p:master())
    monkeypatch.setattr(audio,"list_audiobook_projects",lambda:[])
    monkeypatch.setattr(translation,"listar_projetos_traducao",lambda:[])
    monkeypatch.setattr(audio,"save_audiobook_project",lambda *args:pytest.fail("An untranslated project must not be saved"))
    app=AppTest.from_file(ROOT/"pages/24_🎧_Audiobook_Studio.py").run()
    select(app,"Story Book de origem").set_value("Livro A · Coleção").run()
    next(item for item in app.text_input if item.label=="Locale").set_value("ja-JP").run()
    button(app,"🎧 Criar projeto de audiobook").click().run()
    assert not app.exception
    assert any("Não há texto localizado em ja-JP" in item.value for item in app.error)


def test_google_voice_lab_opens_without_credentials_or_provider_calls(monkeypatch):
    monkeypatch.setattr(estilo,"aplicar_estilo",lambda:None)
    monkeypatch.setattr(st,"secrets",{})
    monkeypatch.delenv(google_cloud_tts.GOOGLE_TTS_CREDENTIAL_ENV,raising=False)
    monkeypatch.setattr(google_cloud_tts,"synthesize_google_voice",lambda *args,**kwargs:pytest.fail("Opening the Lab must not generate paid audio"))
    app=AppTest.from_file(ROOT/"pages/44_🎙️_Jarvis_Voice_Lab.py").run()
    assert not app.exception
    assert select(app,"Voz Google para testar").options==[
        f"{label} · {google_cloud_tts.GOOGLE_PT_BR_VOICES[label]['family']} · masculino pt-BR"
        for label in google_cloud_tts.available_voice_labels()
    ]
    assert button(app,"▶️ Testar esta voz").disabled


def test_translation_draft_survives_non_editorial_migration_metadata_changes(monkeypatch):
    calls=[]
    monkeypatch.setattr(estilo,"aplicar_estilo",lambda:None)
    monkeypatch.setattr(armazenamento,"listar_livros",lambda:[{"titulo":"Livro A","colecao":"Coleção","arquivo":"a.json"}])

    def load(_collection,_path):
        calls.append(True)
        state=master()
        state["_faithbloom_migrations"]=[{"migration":"0->1","at":str(len(calls))}]
        state["authorship"]={"updated_at":str(len(calls)),"authors":[]}
        return state

    monkeypatch.setattr(armazenamento,"carregar_livro",load)
    monkeypatch.setattr(translation,"listar_projetos_traducao",lambda:[])
    monkeypatch.setattr(japanese_localization_bridge,"localizar_livro_com_reading_guard",lambda state,_llm,locale,**kwargs:localized(state,locale))
    app=AppTest.from_file(ROOT/"pages/21_Translation_Localization_Studio.py").run()
    button(app,"🌍 Gerar localização").click().run()
    assert not app.exception
    generated=deepcopy(app.session_state["r06_translation"])
    app.run()
    assert not app.exception
    assert app.session_state["r06_translation"]==generated


@pytest.fixture
def distribution_state(tmp_path):
    pdf=tmp_path/"portuguese.pdf"; cover=tmp_path/"cover.pdf"
    document=canvas.Canvas(str(pdf),pagesize=(612,612))
    for _ in range(24):
        document.drawString(30,550,"Esta história continua em português.")
        document.showPage()
    document.save()
    document=canvas.Canvas(str(cover)); document.drawString(30,550,"Capa portuguesa"); document.save()
    state={"titulo":"Audit distribution","autora":"Autora","idioma_original":"pt-BR","paginas_fisicas":24,
           "trim_largura_in":8.5,"trim_altura_in":8.5,"interior_publicacao":"preto_branco","usar_bleed":False,
           "pdf_miolo":str(pdf),"capa_fisica_pdf":str(cover),"cenas_texto":[{"numero":1,"texto":"Esta história continua em português."}]}
    report={"project_fingerprint":distribution.project_fingerprint(state),
            "certificate":{"status":"INTERNAL_QUALITY_GATE_PASSED"},"author_final_approval":{"approved":True}}
    return state,report


@pytest.mark.parametrize("requested_locale",["ja-JP","en-US"])
def test_distribution_blocks_relabeling_original_pdf_as_another_locale(distribution_state,tmp_path,requested_locale):
    state,report=distribution_state
    plan=distribution.create_distribution_plan(state,[{"platform_id":"amazon_kdp","product":"paperback","locale":requested_locale}],report)
    row=plan["editions"][0]
    assert row["readiness"]=="blocked"
    assert [blocker["code"] for blocker in row["blockers"]]==["edition_locale_mismatch"]
    with pytest.raises(ValueError,match="Edição bloqueada"):
        distribution.build_channel_package(state,plan,row["edition_id"],str(tmp_path/"packages"))
    assert not (tmp_path/"packages").exists()


@pytest.mark.parametrize("requested_locale",["pt-BR","pt"])
def test_distribution_preserves_valid_source_locale_and_exports_real_pdf(distribution_state,tmp_path,requested_locale):
    state,report=distribution_state
    plan=distribution.create_distribution_plan(state,[{"platform_id":"amazon_kdp","product":"paperback","locale":requested_locale}],report)
    row=plan["editions"][0]
    assert row["readiness"]=="ready"
    package=distribution.build_channel_package(state,plan,row["edition_id"],str(tmp_path/"packages"))
    assert "português" in PdfReader(Path(package["folder"])/"FILES/interior.pdf").pages[0].extract_text()


def test_distribution_language_override_cannot_relabel_master_or_bypass_old_plan_guard(distribution_state,tmp_path):
    state,report=distribution_state
    plan=distribution.create_distribution_plan(state,[{"platform_id":"amazon_kdp","product":"paperback","locale":"ja-JP"}],report,
        edition_overrides={"amazon_kdp:paperback":{"master":{"language":"ja-JP"}}})
    row=plan["editions"][0]
    assert row["readiness"]=="blocked"
    assert any(b["code"]=="edition_locale_mismatch" for b in row["blockers"])
    row["readiness"]="ready"  # Simulate an older saved plan without the locale check.
    with pytest.raises(ValueError,match="alterar somente o locale não traduz"):
        distribution.build_channel_package(state,plan,row["edition_id"],str(tmp_path/"packages"))
    assert not (tmp_path/"packages").exists()
    with pytest.raises(ValueError,match="alterar somente o locale não traduz"):
        distribution.update_submission(plan,row["edition_id"],"submitted")


def test_old_distribution_plan_rechecks_locale_readiness_without_rewriting_history(distribution_state,monkeypatch):
    state,report=distribution_state
    plan=distribution.create_distribution_plan(state,[{"platform_id":"amazon_kdp","product":"paperback","locale":"ja-JP"}],report)
    row=plan["editions"][0]
    row["readiness"]="ready"; row["blockers"]=[]
    row["submission"]["status"]="live"  # Preserve the user's historical confirmation.
    plan["summary"]=distribution.summarize_distribution(plan["editions"])
    before=deepcopy(plan)
    monkeypatch.setattr(distribution,"_read_json",lambda *args:plan)
    monkeypatch.setattr(distribution,"_save_json",lambda *args:pytest.fail("Readiness review must not rewrite the saved history"))
    loaded=distribution.load_distribution_plan(plan["id"])
    assert loaded["editions"][0]["readiness"]=="blocked"
    assert loaded["summary"]["ready"]==0
    assert loaded["editions"][0]["submission"]["status"]=="live"
    assert plan==before

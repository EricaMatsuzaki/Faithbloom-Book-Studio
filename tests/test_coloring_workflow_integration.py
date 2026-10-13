"""Exercise real coloring PDFs and durable UI output without contacting AI providers."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from streamlit.testing.v1 import AppTest

import armazenamento
import asset_library
import character_universe
import coloring_studio as studio
import storage_backend
from agents.diagramador_colorir import diagramador_colorir_node
from qualidade_impressao import preflight_livro
from renderizador_editorial import renderizar_miolo_pdf
from storage_backend import LocalStorageBackend, StorageError
from painel_projetos import load_project


@pytest.fixture
def coloring_project(tmp_path):
    image = tmp_path / "original-line.png"
    art = Image.new("RGB", (3000, 3000), "white")
    ImageDraw.Draw(art).ellipse((400, 400, 2500, 2500), outline="black", width=25)
    art.save(image)
    state = diagramador_colorir_node({
        "titulo": "Desenhos da auditoria", "tema_geral": "Flores", "autora": "Autora",
        "trim_largura_in": 8.5, "trim_altura_in": 8.5,
        "paginas": [{"nome": f"Desenho {i + 1}", "origem": "imagem_enviada",
                     "caminho_arquivo": str(image), "imagem_referencia": str(image), "aprovada": True}
                    for i in range(11)],
    })
    return state, image


def image_objects(page):
    objects = page["/Resources"].get("/XObject")
    return [value.get_object() for value in objects.values()
            if value.get_object().get("/Subtype") == "/Image"] if objects else []


@pytest.mark.parametrize("bleed", [False, True])
def test_coloring_pdf_contains_every_drawing_and_blank_reverse(coloring_project, tmp_path, bleed):
    state, image = coloring_project
    original_digest = sha256(image.read_bytes()).hexdigest()
    preflight = preflight_livro(state, bleed=bleed)
    assert not preflight["bloqueios"]
    assert len(preflight["assets"]) == 11
    assert all(asset["ppi_efetivo"] >= 300 for asset in preflight["assets"])

    result = renderizar_miolo_pdf(state, destino=str(tmp_path / "miolo.pdf"), bleed=bleed)
    assert result["ok"] and not result["avisos"]
    reader = PdfReader(result["caminho"])
    assert len(reader.pages) == 24
    assert "Este livro pertence a" in reader.pages[1].extract_text()
    for index in range(2, 24, 2):
        assert len(image_objects(reader.pages[index])) == 1
        assert not image_objects(reader.pages[index + 1])
        assert not reader.pages[index + 1].extract_text().strip()
    expected_size = (8.625, 8.75) if bleed else (8.5, 8.5)
    assert tuple(float(reader.pages[0].mediabox[key]) / 72 for key in (2, 3)) == expected_size
    assert sha256(image.read_bytes()).hexdigest() == original_digest


@pytest.mark.parametrize("bad_source", ["absent", "low_resolution"])
def test_coloring_preflight_rejects_missing_or_small_drawing(coloring_project, tmp_path, bad_source):
    state, _ = coloring_project
    state = deepcopy(state)
    bad = tmp_path / "bad.png"
    if bad_source == "low_resolution":
        Image.new("RGB", (100, 100), "white").save(bad)
    state["paginas"][0]["caminho_arquivo"] = str(bad)
    destination = tmp_path / "blocked.pdf"
    result = renderizar_miolo_pdf(state, destino=str(destination), bleed=False)
    assert not result["ok"]
    assert result["preflight"]["bloqueios"]
    assert not destination.exists()


@pytest.fixture
def isolated_studio(tmp_path, monkeypatch):
    backend = LocalStorageBackend(str(tmp_path / "durable"))
    monkeypatch.setattr(storage_backend, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage_backend, "CACHE_DIR", cache)
    monkeypatch.setattr(studio, "listar_presets", lambda: [])
    monkeypatch.setattr(studio, "list_author_profiles", lambda: [])
    monkeypatch.setattr(studio, "assign_saved_project_to_profile", lambda *_: None)
    monkeypatch.chdir(tmp_path)
    return backend


def open_result(backend, state):
    path = "livros_colorir/audit.json"
    backend.put_json(path, state)
    app = AppTest.from_string("from coloring_studio import render_coloring_studio\nrender_coloring_studio()")
    app.session_state["state_c"] = deepcopy(state)
    app.session_state["etapa_c"] = "resultado"
    app.session_state["caminho_salvo_c"] = path
    app.run(timeout=15)
    assert not app.exception
    return app, path


def button(app, label):
    return next(widget for widget in app.button if widget.label == label)


def test_coloring_studio_exports_and_reloads_durable_interior(isolated_studio, coloring_project):
    state, _ = coloring_project
    app, path = open_result(isolated_studio, state)
    button(app, "📘 Gerar PDF do miolo de colorir").click().run(timeout=15)
    assert not app.exception
    durable = isolated_studio.get_json(path)
    assert durable["pdf_miolo"].startswith("fb://assets/colorir/")
    assert durable["pdf_miolo_config"]["paginas"] == 24
    assert durable["pdf_miolo_preflight"]["page_size_correto"]
    reloaded = armazenamento.carregar_livro_colorir(path)
    reader = PdfReader(reloaded["pdf_miolo"])
    assert len(reader.pages) == 24
    assert sum(bool(image_objects(page)) for page in reader.pages) == 11
    assert "⬇️ Baixar miolo de colorir (PDF)" in [widget.label for widget in app.get("download_button")]
    assert isolated_studio.list("livros_colorir") == [path]


def test_interior_with_failed_pdf_inspection_is_not_saved_as_final(isolated_studio, coloring_project, monkeypatch):
    state, _ = coloring_project
    app, path = open_result(isolated_studio, state)
    monkeypatch.setattr(studio, "analisar_pdf_miolo", lambda *args, **kwargs: {"erros": ["Synthetic MediaBox mismatch"]})
    button(app, "📘 Gerar PDF do miolo de colorir").click().run(timeout=15)
    assert not app.exception
    assert not isolated_studio.get_json(path).get("pdf_miolo")
    assert not app.session_state["state_c"].get("pdf_miolo")
    assert any("precisa de revisão" in error.value for error in app.error)


@pytest.fixture
def fake_cover(coloring_project, tmp_path, monkeypatch):
    _, image = coloring_project
    pdf = tmp_path / "generated-cover.pdf"
    document = canvas.Canvas(str(pdf), pagesize=(144, 144))
    document.drawString(20, 100, "Synthetic cover")
    document.save()
    calls = []
    compositions = []
    cover = {"caminho_png": str(image), "caminho_preview": str(image), "caminho_pdf": str(pdf)}

    def generate(**kwargs):
        calls.append(kwargs)
        return str(image)

    def compose(*args, **kwargs):
        compositions.append(kwargs)
        return dict(cover)

    monkeypatch.setattr(studio, "gerar_imagem", generate)
    monkeypatch.setattr(studio, "gerar_capa_print_ready", compose)
    return cover, calls, compositions


def test_cover_is_saved_and_reloaded_from_current_project(isolated_studio, coloring_project, fake_cover):
    state, _ = coloring_project
    _, calls, compositions = fake_cover
    app, path = open_result(isolated_studio, state)
    button(app, "✨ Gerar artes e montar capa paperback").click().run(timeout=15)
    assert not app.exception and len(calls) == 2
    assert compositions[0]["papel"] == "branco"
    assert compositions[0]["paginas"] == 24
    durable = isolated_studio.get_json(path)
    assert durable["capa_fisica_pdf"].startswith("fb://assets/colorir/")
    assert durable["capa_fisica_wrap"].endswith(".png")
    reloaded = armazenamento.carregar_livro_colorir(path)
    for field in ("caminho_png", "caminho_preview", "caminho_pdf"):
        assert Path(reloaded["capa_fisica_dimensoes"][field]).is_file()
    assert PdfReader(reloaded["capa_fisica_pdf"]).pages
    assert isolated_studio.list("livros_colorir") == [path]


def test_failed_cover_save_has_retry_without_second_ai_charge(isolated_studio, coloring_project, fake_cover, monkeypatch):
    state, _ = coloring_project
    _, calls, _ = fake_cover
    app, path = open_result(isolated_studio, state)
    original_save = studio.atualizar_livro_colorir_salvo

    def unavailable(*args):
        raise StorageError("Synthetic storage unavailable")

    monkeypatch.setattr(studio, "atualizar_livro_colorir_salvo", unavailable)
    button(app, "✨ Gerar artes e montar capa paperback").click().run(timeout=15)
    assert not app.exception and len(calls) == 2
    assert not isolated_studio.get_json(path).get("capa_fisica_pdf")
    assert app.session_state["coloring_save_error"]
    assert any("ainda precisam ser salvos" in warning.value for warning in app.warning)
    assert not app.success

    monkeypatch.setattr(studio, "atualizar_livro_colorir_salvo", original_save)
    button(app, "💾 Tentar salvar novamente").click().run(timeout=15)
    assert not app.exception and len(calls) == 2
    assert isolated_studio.get_json(path)["capa_fisica_pdf"].startswith("fb://")
    assert "coloring_save_error" not in app.session_state


def test_new_coloring_book_clears_previous_cover_and_save_target(isolated_studio, coloring_project, fake_cover):
    state, _ = coloring_project
    app, path = open_result(isolated_studio, state)
    button(app, "✨ Gerar artes e montar capa paperback").click().run(timeout=15)
    button(app, "Novo Coloring Book").click().run(timeout=15)
    assert not app.exception
    assert "capa_colorir_phase8" not in app.session_state
    assert "caminho_salvo_c" not in app.session_state
    assert "coloring_pdf_bleed" not in app.session_state

    next_state = deepcopy(state)
    next_state["titulo"] = "Projeto seguinte"
    app.session_state["state_c"] = next_state
    app.session_state["etapa_c"] = "paginas"
    app.run(timeout=15)
    button(app, "📐 Diagramar projeto aprovado").click().run(timeout=15)
    assert not app.exception
    assert app.session_state["caminho_salvo_c"].removeprefix("fb://") != path
    assert isolated_studio.get_json(path)["titulo"] == state["titulo"]
    assert "⬇️ Baixar capa física Print Ready (PDF)" not in [widget.label for widget in app.get("download_button")]


def test_profile_link_failure_retries_existing_file_without_duplicate(isolated_studio, coloring_project, monkeypatch):
    state, _ = coloring_project
    profile_calls = []

    def link(profile_id, kind, path, saved_state):
        profile_calls.append((profile_id, kind, path))
        if len(profile_calls) == 1:
            raise StorageError("Synthetic profile storage unavailable")

    monkeypatch.setattr(studio, "assign_saved_project_to_profile", link)
    app = AppTest.from_string("from coloring_studio import render_coloring_studio\nrender_coloring_studio()")
    app.session_state["state_c"] = deepcopy(state)
    app.session_state["etapa_c"] = "paginas"
    app.session_state["faithbloom_workspace_profile_id"] = "original_owner"
    app.run(timeout=15)
    button(app, "📐 Diagramar projeto aprovado").click().run(timeout=15)
    assert not app.exception
    saved_path = app.session_state["caminho_salvo_c"]
    assert app.session_state["state_c"]["storage_path"] == saved_path
    assert isolated_studio.list("livros_colorir") == [saved_path.removeprefix("fb://")]
    assert any("vínculo com o perfil" in error.value for error in app.error)

    app.session_state["faithbloom_workspace_profile_id"] = "other_owner"
    button(app, "📐 Diagramar projeto aprovado").click().run(timeout=15)
    assert not app.exception
    assert app.session_state["etapa_c"] == "resultado"
    assert app.session_state["caminho_salvo_c"] == saved_path
    assert profile_calls == [("original_owner", "coloring", saved_path)] * 2
    assert isolated_studio.list("livros_colorir") == [saved_path.removeprefix("fb://")]
    assert "coloring_profile_link_pending" not in app.session_state


@pytest.mark.parametrize("origin", sorted(studio.ORIGENS_COM_REFERENCIA))
def test_reference_based_page_never_calls_ai_without_source(origin, monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("A source-free conversion must never reach a paid generator")

    monkeypatch.setattr(studio, "gerar_imagem", forbidden)
    with pytest.raises(ValueError, match="imagem disponível"):
        studio._gerar_uma_pagina({}, {"origem": origin, "nome": "Página sem fonte"})


def test_photo_conversion_form_requires_photo(isolated_studio, coloring_project):
    state, _ = coloring_project
    state = {**state, "paginas": []}
    app, _ = open_result(isolated_studio, state)
    app.session_state["etapa_c"] = "paginas"
    app.run(timeout=15)
    next(widget for widget in app.selectbox if widget.label == "Como você quer criar esta página?").select("📷 Foto real → Line Art").run(timeout=15)
    next(widget for widget in app.text_input if widget.label == "Nome da página").set_value("Minha foto").run(timeout=15)
    assert not app.exception
    assert button(app, "➕ Adicionar página ao projeto").disabled


def official_master(image, *, role="color_master", name="Lia", collection="Coleção somente de Masters", **asset_changes):
    asset = armazenamento.salvar_na_galeria(str(image), f"{name} Master", tipo="referencia_personagem")
    asset_library.update_asset(asset["id"], approved=True, visual_status="COLOR_MASTER" if role == "color_master" else "LINEART_MASTER", **asset_changes)
    character = character_universe.criar_personagem_oficial(
        collection, name, {"campos_bloqueados": {"olhos": "verdes com estrelas brilhantes", "marcas": "laço rosa"}},
        **{role: asset["storage_uri"]},
        metadata={"current_master_asset_ids": {role: asset["id"]}},
    )
    return character, asset


def test_coloring_form_reuses_approved_official_master_without_saved_story(isolated_studio, coloring_project, monkeypatch):
    state, original = coloring_project
    character, asset = official_master(original)
    assert armazenamento.listar_livros() == []
    assert armazenamento.listar_colecoes() == []
    original_bytes = original.read_bytes()
    master_before = isolated_studio.get_json(f"character_universe/{character['id']}.json")
    generated = []
    monkeypatch.setattr(studio, "obter_preset", lambda _: None)
    monkeypatch.setattr(studio, "gerar_imagem", lambda **kwargs: generated.append(kwargs) or str(original))

    app, _ = open_result(isolated_studio, {**state, "paginas": []})
    app.session_state["etapa_c"] = "paginas"
    app.run(timeout=15)
    next(widget for widget in app.selectbox if widget.label == "Como você quer criar esta página?").select("👥 Personagem da Biblioteca → Line Art").run(timeout=15)
    collection = next(widget for widget in app.selectbox if widget.label == "Coleção da Biblioteca")
    assert collection.value == character["colecao"]
    selector = next(widget for widget in app.selectbox if widget.label == "Personagem")
    assert selector.value == f"official:{character['id']}"
    assert any("Color Master" in caption.value and asset["id"][:8] in caption.value for caption in app.caption)
    next(widget for widget in app.text_input if widget.label == "Nome da página").set_value("Lia e as flores").run(timeout=15)
    button(app, "➕ Adicionar página ao projeto").click().run(timeout=15)
    assert not app.exception
    page = app.session_state["state_c"]["paginas"][0]
    assert page["character_id"] == character["id"]
    assert page["character_master_asset_id"] == asset["id"]
    button(app, "✨ Gerar").click().run(timeout=15)
    assert not app.exception and len(generated) == 1
    assert generated[0]["imagem_base"] == character["color_master"]
    assert Path(generated[0]["imagem_base"]).read_bytes() == original_bytes
    assert "verdes com estrelas brilhantes" in generated[0]["prompt"]
    assert "laço rosa" in generated[0]["prompt"]
    assert isolated_studio.get_json(f"character_universe/{character['id']}.json") == master_before


@pytest.mark.parametrize("restriction", ["unapproved", "archived_asset", "candidate", "wrong_id", "usage", "archived_character"])
def test_coloring_reference_selector_excludes_unusable_official_master(isolated_studio, coloring_project, restriction):
    _, image = coloring_project
    character, asset = official_master(image)
    if restriction == "unapproved":
        asset_library.update_asset(asset["id"], approved=False)
    elif restriction == "archived_asset":
        asset_library.set_archived(asset["id"])
    elif restriction == "candidate":
        asset_library.update_asset(asset["id"], visual_status="MASTER_CANDIDATE")
    elif restriction == "wrong_id":
        character_universe.atualizar_personagem_oficial(character["id"], {"metadata": {"current_master_asset_ids": {"color_master": "other"}}})
    elif restriction == "usage":
        character_universe.atualizar_personagem_oficial(character["id"], {"metadata": {"usos_permitidos": ["story"]}})
    else:
        character_universe.atualizar_personagem_oficial(character["id"], {"status": "arquivado"})
    assert studio._referencias_biblioteca(character["colecao"]) == []


def test_coloring_prefers_approved_line_master_and_preserves_legacy_reference(isolated_studio, coloring_project):
    _, image = coloring_project
    character, color = official_master(image)
    line = armazenamento.salvar_na_galeria(str(image), "Line Master", tipo="line_art")
    asset_library.update_asset(line["id"], approved=True, visual_status="LINEART_MASTER")
    character_universe.atualizar_personagem_oficial(character["id"], {
        "line_art_master": line["storage_uri"],
        "metadata": {"current_master_asset_ids": {"line_art_master": line["id"], "color_master": color["id"]}},
    })
    armazenamento.atualizar_biblioteca_personagens(character["colecao"], {
        "Legado": {"nome": "Legado", "imagem_referencia": str(image)},
    })
    options = studio._referencias_biblioteca(character["colecao"])
    assert len(options) == 2
    assert options[0]["master_role"] == "line_art_master"
    assert options[0]["asset_id"] == line["id"]
    assert options[1]["id"] == "legacy:Legado"
    assert Path(options[1]["caminho"]).read_bytes() == image.read_bytes()


def open_draft(state):
    app = AppTest.from_string("from coloring_studio import render_coloring_studio\nrender_coloring_studio()")
    app.session_state["state_c"] = deepcopy(state)
    app.session_state["etapa_c"] = "paginas"
    app.run(timeout=15)
    assert not app.exception
    return app


def test_each_coloring_generation_checkpoints_before_later_provider_failure(isolated_studio, coloring_project, monkeypatch):
    _, image = coloring_project
    state = {"titulo": "Rascunho pago", "tema_geral": "Flores", "paginas": [
        {"nome": "Primeira página", "origem": "gerar_ia", "aprovada": False},
        {"nome": "Segunda página", "origem": "gerar_ia", "aprovada": False},
    ]}
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError("Synthetic provider interruption")
        return str(image)

    monkeypatch.setattr(studio, "gerar_imagem", generate)
    app = open_draft(state)
    app.button(key="gen_c_0").click().run(timeout=15)
    assert not app.exception
    saved_path = app.session_state["caminho_salvo_c"]
    first_checkpoint = load_project({"kind": "coloring", "storage_path": saved_path})
    assert Path(first_checkpoint["paginas"][0]["caminho_arquivo"]).read_bytes() == image.read_bytes()
    assert not first_checkpoint["paginas"][0]["aprovada"]
    app.button(key="gen_c_1").click().run(timeout=15)
    assert not app.exception and len(calls) == 2
    assert any("Não foi possível gerar" in error.value for error in app.error)
    reloaded = load_project({"kind": "coloring", "storage_path": saved_path})
    assert Path(reloaded["paginas"][0]["caminho_arquivo"]).read_bytes() == image.read_bytes()
    assert not reloaded["paginas"][1].get("caminho_arquivo")
    assert not reloaded.get("pdf_miolo") and not reloaded.get("layout_paginas")
    assert button(app, "📐 Diagramar projeto aprovado").disabled
    assert isolated_studio.list("livros_colorir") == [saved_path.removeprefix("fb://")]


def test_failed_draft_save_can_retry_without_another_generation(isolated_studio, coloring_project, monkeypatch):
    _, image = coloring_project
    state = {"titulo": "Rascunho recuperável", "tema_geral": "Flores",
             "paginas": [{"nome": "Página", "origem": "gerar_ia", "aprovada": False}]}
    calls = []
    original_save = studio.salvar_livro_colorir
    monkeypatch.setattr(studio, "gerar_imagem", lambda **kwargs: calls.append(kwargs) or str(image))

    def unavailable(*args):
        raise StorageError("Synthetic save failure")

    monkeypatch.setattr(studio, "salvar_livro_colorir", unavailable)
    app = open_draft(state)
    app.button(key="gen_c_0").click().run(timeout=15)
    assert not app.exception and len(calls) == 1
    assert app.session_state["state_c"]["paginas"][0]["caminho_arquivo"] == str(image)
    assert any("ainda precisam ser salvos" in warning.value for warning in app.warning)
    assert not isolated_studio.list("livros_colorir")
    monkeypatch.setattr(studio, "salvar_livro_colorir", original_save)
    button(app, "💾 Tentar salvar novamente").click().run(timeout=15)
    assert not app.exception and len(calls) == 1
    reloaded = load_project({"kind": "coloring", "storage_path": app.session_state["caminho_salvo_c"]})
    assert Path(reloaded["paginas"][0]["caminho_arquivo"]).read_bytes() == image.read_bytes()
    assert "coloring_save_error" not in app.session_state


def test_generated_variation_and_original_history_are_durable_before_layout(isolated_studio, coloring_project, tmp_path, monkeypatch):
    _, original = coloring_project
    variant = tmp_path / "variation.png"
    Image.new("RGB", (100, 100), "pink").save(variant)
    page = {"nome": "Página", "origem": "imagem_enviada", "imagem_referencia": str(original),
            "caminho_arquivo": str(original), "aprovada": True}
    studio._registrar_variacao_inicial(page)
    state = {"titulo": "Variação preservada", "tema_geral": "Flores", "paginas": [page]}
    calls = []
    monkeypatch.setattr(studio, "gerar_imagem", lambda **kwargs: calls.append(kwargs) or str(variant))
    app = open_draft(state)
    app.text_area(key="var_prompt_0").set_value("Flores maiores").run(timeout=15)
    app.button(key="var_btn_0").click().run(timeout=15)
    assert not app.exception and len(calls) == 1
    assert calls[0]["imagem_base"] == str(original)
    reloaded = load_project({"kind": "coloring", "storage_path": app.session_state["caminho_salvo_c"]})
    saved_page = reloaded["paginas"][0]
    assert not saved_page["aprovada"] and saved_page["status"] == "pronta"
    assert len(saved_page["variacoes"]) == 2
    assert Path(saved_page["variacoes"][0]["caminho_arquivo"]).read_bytes() == original.read_bytes()
    assert Path(saved_page["variacoes"][1]["caminho_arquivo"]).read_bytes() == variant.read_bytes()
    assert Path(saved_page["caminho_arquivo"]).read_bytes() == variant.read_bytes()
    assert not reloaded.get("layout_paginas") and not reloaded.get("pdf_miolo")


def test_untitled_coloring_project_cannot_start_paid_generation(isolated_studio, coloring_project, monkeypatch):
    _, image = coloring_project

    def forbidden(**kwargs):
        raise AssertionError("Name the durable project before generating paid artwork")

    monkeypatch.setattr(studio, "gerar_imagem", forbidden)
    app = open_draft({"titulo": " ", "paginas": [{"nome": "Página", "origem": "gerar_ia",
        "caminho_arquivo": str(image), "aprovada": False}]})
    assert app.button(key="gen_c_0").disabled
    app.text_area(key="var_prompt_0").set_value("Flores maiores").run(timeout=15)
    assert app.button(key="var_btn_0").disabled
    assert not isolated_studio.list("livros_colorir")

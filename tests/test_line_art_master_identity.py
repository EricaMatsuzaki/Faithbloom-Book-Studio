"""Exercise Master identity through page, variation and real cover UI boundaries offline."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from agents import line_art_colorir as line_art
import coloring_studio as studio


DNA = "Olhos verdes-esmeralda, um reflexo de estrela e um coração; laço rosa, pelagem creme."


@pytest.mark.parametrize("sexo", ["macho", "femea"])
def test_supplied_dna_overrides_generic_sex_code_without_coloring_the_interior(sexo):
    provider = Mock(return_value="candidate.png")
    line_art.gerar_pagina_colorir(
        "Mel", "gatinha", "no jardim", provider, sexo=sexo,
        imagem_referencia="approved-master.png", character_dna_prompt=DNA,
        preset={"prompt_base": "Composição simples, contornos grossos."},
    )
    prompt = provider.call_args.kwargs["prompt"]
    assert DNA in prompt and "estrela" in prompt and "coração" in prompt
    assert "prevalecem sobre o preset genérico" in prompt
    assert "2 pontos de brilho" not in prompt
    assert "sem preenchimento colorido, cinza ou sombreado" in prompt
    assert "As cores canônicas identificam o personagem, não autorizam colorir a line art" in prompt
    assert provider.call_args.kwargs["imagem_base"] == "approved-master.png"


@pytest.mark.parametrize("sexo", ["macho", "femea"])
def test_generic_sex_preset_remains_available_without_dna_or_master(sexo):
    prompt = line_art.prompt_pagina_colorir("Novo", "animal", "no jardim", sexo=sexo)
    assert line_art.CODIGO_VISUAL_SEXO[sexo] in prompt
    assert "PRIORIDADE DE IDENTIDADE" not in prompt


def test_reference_alone_preserves_observable_eyes_instead_of_inventing_generic_eyes():
    provider = Mock(return_value="candidate.png")
    line_art.gerar_pagina_colorir("Mel", "gatinha", "no jardim", provider,
                                sexo="femea", imagem_referencia="original-master.png")
    prompt = provider.call_args.kwargs["prompt"]
    assert "2 pontos de brilho" not in prompt
    assert "detalhes observáveis da imagem fornecida" in prompt
    assert "estrelas e corações" in prompt


def test_variation_keeps_selected_derivative_and_original_master_separate(tmp_path):
    master = tmp_path / "master.png"
    Image.new("RGB", (16, 16), "green").save(master)
    before_hash = sha256(master.read_bytes()).hexdigest()
    page = {"nome": "Mel", "categoria": "gatinha", "sexo": "femea", "cena": "no jardim",
            "caminho_arquivo": "selected-line-art.png", "imagem_referencia": str(master),
            "character_dna_prompt": DNA, "variacoes": [{"id": "approved-original"}]}
    before = deepcopy(page)
    provider = Mock(return_value="new-line-art.png")
    candidate = line_art.gerar_variacao_line_art(page, provider, instrucao="Flores maiores.")
    assert provider.call_args.kwargs["imagem_base"] == "selected-line-art.png"
    assert provider.call_args.kwargs["imagens_referencia"] == [str(master)]
    assert DNA in candidate["prompt"] and "2 pontos de brilho" not in candidate["prompt"]
    assert candidate["base"] == "selected-line-art.png" and page == before
    assert sha256(master.read_bytes()).hexdigest() == before_hash


def cover_state(tmp_path):
    pages = []
    for index in range(4):
        master = tmp_path / f"master-{index}.png"
        derivative = tmp_path / f"line-{index}.png"
        Image.new("RGB", (20, 20), (50 + index * 30, 200, 100)).save(master)
        Image.new("RGB", (20, 20), "white").save(derivative)
        pages.append({"nome": f"Cena {index}", "personagem_nome": f"Personagem {index}",
                      "categoria": "animal", "sexo": "femea", "character_id": f"official-{index}",
                      "character_master_asset_id": f"approved-{index}", "imagem_referencia": str(master),
                      "caminho_arquivo": str(derivative), "character_dna_prompt": f"Modo visual: line_art; {DNA}",
                      "character_color_dna_prompt": f"Modo visual: color; {DNA} Detalhe canônico {index}.",
                      "aprovada": True})
    return {"titulo": "Jardim", "tema_geral": "Esperança", "paginas": pages,
            "paginas_fisicas_total": 24, "trim_largura_in": 8.5, "trim_altura_in": 8.5}


@pytest.mark.parametrize("cover_function", [line_art.gerar_capa_ebook_colorir, line_art.gerar_capa_fisica_wrap_colorir])
def test_cover_agents_receive_original_masters_and_color_dna_for_every_character(tmp_path, monkeypatch, cover_function):
    state = cover_state(tmp_path)
    before = deepcopy(state)
    hashes = [sha256(Path(page["imagem_referencia"]).read_bytes()).hexdigest() for page in state["paginas"]]
    monkeypatch.setattr(line_art, "carregar_asset_marca", lambda *args: None)
    monkeypatch.setattr(line_art, "aplicar_faixa_colecao", lambda path, *args: path)
    provider = Mock(return_value="cover.png")
    cover_function(state, provider)
    call = provider.call_args.kwargs
    assert call["imagem_base"] == state["paginas"][0]["imagem_referencia"]
    assert call["imagens_referencia"] == [page["imagem_referencia"] for page in state["paginas"][1:]]
    assert "2 pontos de brilho" not in call["prompt"]
    assert "Modo visual: line_art" not in call["prompt"]
    assert "preserve também as cores canônicas exatas" in call["prompt"]
    for index in range(4):
        assert f"Detalhe canônico {index}" in call["prompt"]
    assert state == before
    assert hashes == [sha256(Path(page["imagem_referencia"]).read_bytes()).hexdigest() for page in state["paginas"]]


def test_legacy_cover_retains_existing_reference_fallback():
    state = {"paginas": [{"nome": "Vaso", "caminho_arquivo": "existing-line.png"}]}
    assert line_art.referencias_capa_colorir(state) == {"imagem_base": "existing-line.png"}


def test_legacy_color_cover_with_supplied_master_keeps_reference_details_without_inventing_a_dna():
    subjects = [{"nome": "Mel", "categoria": "gatinha", "sexo": "femea"}]
    before = deepcopy(subjects)
    provider = Mock(return_value="cover.png")
    line_art.gerar_capa_colorida(subjects, "Jardim", provider, imagem_referencia="original-master.png")
    assert provider.call_args.kwargs["imagem_base"] == "original-master.png"
    assert "2 pontos de brilho" not in provider.call_args.kwargs["prompt"]
    assert "detalhes observáveis da imagem fornecida" in provider.call_args.kwargs["prompt"]
    assert subjects == before


def test_physical_cover_ui_connects_color_dna_and_original_masters_for_front_and_back(tmp_path, monkeypatch):
    state = cover_state(tmp_path)
    before = deepcopy(state["paginas"])
    provider = Mock(return_value=state["paginas"][0]["caminho_arquivo"])
    monkeypatch.setattr(studio, "gerar_imagem", provider)
    monkeypatch.setattr(studio, "listar_livros_colorir", lambda: [])
    monkeypatch.setattr(studio, "_salvar_projeto_atual", lambda state: True)
    monkeypatch.setattr(studio, "preflight_livro", lambda *args, **kwargs: {"bloqueios": []})
    monkeypatch.setattr(studio, "gerar_capa_print_ready", lambda *args, **kwargs: {"caminho_pdf": "synthetic-cover.pdf"})
    app = AppTest.from_string("from coloring_studio import render_coloring_studio\nrender_coloring_studio()")
    app.session_state["state_c"] = deepcopy(state)
    app.session_state["etapa_c"] = "resultado"
    app.run(timeout=15)
    assert not app.exception
    next(button for button in app.button if button.label == "✨ Gerar artes e montar capa paperback").click().run(timeout=15)
    assert not app.exception and provider.call_count == 2
    for call in provider.call_args_list:
        assert call.kwargs["imagem_base"] == state["paginas"][0]["imagem_referencia"]
        assert call.kwargs["imagens_referencia"] == [page["imagem_referencia"] for page in state["paginas"][1:]]
        assert "2 pontos de brilho" not in call.kwargs["prompt"]
        assert "Modo visual: line_art" not in call.kwargs["prompt"]
        assert all(f"Detalhe canônico {index}" in call.kwargs["prompt"] for index in range(4))
    assert "Sujeitos em destaque, centralizados" not in provider.call_args_list[1].kwargs["prompt"]
    assert app.session_state["state_c"]["paginas"] == before

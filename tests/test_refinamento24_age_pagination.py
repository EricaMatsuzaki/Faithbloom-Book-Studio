from pathlib import Path

from pypdf import PdfReader

from age_profiles import (
    AGE_PROFILES,
    normalizar_faixa_etaria,
    perfil_etario,
    instrucao_faixa_etaria,
)
from agents.gerador_ideias import gerador_ideias_node
from agents.roteirista import montar_prompt
from agents.estilos_narrativos import gerar_comparativo_estilos
from agents.complementos_editoriais import gerar_complementos_editoriais
from agents.diagramador import montar_layout
import renderizador_editorial as renderer


def test_faixas_oficiais_e_compatibilidade():
    assert set(("3-5", "6-8", "9-12", "3-8")).issubset(AGE_PROFILES)
    assert normalizar_faixa_etaria("3–5 anos") == "3-5"
    assert normalizar_faixa_etaria("6 a 8") == "6-8"
    assert normalizar_faixa_etaria("9–12") == "9-12"
    assert normalizar_faixa_etaria(None) == "3-8"
    assert perfil_etario("3-5")["pdf_font_size"] > perfil_etario("9-12")["pdf_font_size"]


def test_gerador_de_ideias_recebe_faixa_etaria():
    chamadas = []

    def fake_llm(*, sistema, instrucao):
        chamadas.append((sistema, instrucao))
        return []

    gerador_ideias_node(
        4,
        [],
        fake_llm,
        "Coleção",
        "Autora",
        faixa_etaria="9-12",
    )
    assert chamadas
    sistema = chamadas[0][0]
    assert "9–12 anos" in sistema
    assert "leitor independente" in sistema


def test_roteirista_muda_instrucao_conforme_idade():
    base = {
        "titulo": "Teste",
        "personagens": {},
        "paginas_minimas": 24,
        "versiculo_referencia": "Salmo 118:24",
        "emocao_central": "alegria",
        "aprendizado_cristao": "gratidão",
    }
    p35 = montar_prompt({**base, "faixa_etaria": "3-5"})
    p912 = montar_prompt({**base, "faixa_etaria": "9-12"})
    assert "3–5 anos" in p35
    assert "9–12 anos" in p912
    assert "pré-leitor" in p35
    assert "leitor independente" in p912
    assert p35 != p912


def test_quatro_estilos_preservam_mesma_faixa():
    chamadas = []

    def fake_llm(*, sistema, instrucao):
        chamadas.append((sistema, instrucao))
        return {"titulo": "T", "amostra": "A", "licao_final": "M"}

    gerar_comparativo_estilos(
        {
            "titulo": "Teste",
            "faixa_etaria": "6-8",
            "personagens": {},
            "paginas_minimas": 24,
            "versiculo_referencia": "Salmo 118:24",
            "emocao_central": "alegria",
            "aprendizado_cristao": "gratidão",
        },
        fake_llm,
        modo="amostra",
    )
    assert len(chamadas) == 4
    assert all("6–8 anos" in sistema for sistema, _ in chamadas)
    assert all("6–8 anos" in instrucao for _, instrucao in chamadas)


def test_complementos_fixam_faixa_do_projeto():
    capturado = {}

    def fake_llm(*, sistema, instrucao):
        capturado["sistema"] = sistema
        return {
            "boas_vindas": "Bem-vindos",
            "pais_educadores": {"perguntas": ["1", "2", "3", "4"]},
            "ficha_pedagogica": {"faixa_etaria": "ERRADA", "perguntas_reflexao": ["1", "2", "3", "4"]},
        }

    out = gerar_complementos_editoriais(
        {
            "titulo": "Teste",
            "faixa_etaria": "9-12",
            "versiculo_referencia": "Salmo 118:24",
        },
        fake_llm,
    )
    assert "exatamente 4 perguntas" in capturado["sistema"]
    assert out["ficha_pedagogica"]["faixa_etaria"] == "9–12 anos"


def test_layout_fisico_tem_front_matter_spreads_complementos_e_paridade():
    state = {
        "cenas_texto": [
            {"numero": 1, "texto": "Cena 1"},
            {"numero": 2, "texto": "Cena 2"},
        ],
        "boas_vindas": "Bem-vindos",
        "pais_educadores": {"mensagem": "Apoio"},
        "ficha_pedagogica": {"faixa_etaria": "6–8 anos"},
        "paginas_colorir": [
            {"numero": 1},
            {"numero": 2},
            {"numero": 3},
        ],
    }
    layout = montar_layout(state)
    by_page = {x["pagina"]: x for x in layout}

    assert by_page[3]["tipo"] == "boas_vindas"
    assert by_page[4]["tipo"] == "texto" and by_page[4]["lado"] == "esquerda"
    assert by_page[5]["tipo"] == "imagem" and by_page[5]["lado"] == "direita"
    assert by_page[6]["tipo"] == "imagem" and by_page[6]["lado"] == "esquerda"
    assert by_page[7]["tipo"] == "texto" and by_page[7]["lado"] == "direita"
    tipos = [x["tipo"] for x in layout]
    assert "pais_educadores" in tipos
    assert "ficha_pedagogica" in tipos
    assert tipos.count("atividade_colorir") == 3
    assert layout[-1]["pagina"] % 2 == 0


def test_renderer_materializa_paginas_editoriais_no_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(
        renderer,
        "preflight_livro",
        lambda state, bleed=True: {"bloqueios": [], "checks": {}},
    )
    destino = tmp_path / "miolo.pdf"
    state = {
        "titulo": "Livro Teste",
        "colecao": "FaithBloom",
        "autora": "Autora Teste",
        "faixa_etaria": "6-8",
        "versiculo_referencia": "Salmo 118:24",
        "boas_vindas": "Que alegria ter você nesta história.",
        "pais_educadores": {
            "mensagem": "Conversem sobre a história.",
            "tema": "Gratidão",
            "perguntas": ["O que você aprendeu?"],
        },
        "ficha_pedagogica": {
            "faixa_etaria": "6–8 anos",
            "tema_central": "Gratidão",
            "objetivo_pedagogico": "Reconhecer motivos para agradecer.",
        },
        "layout_paginas": [
            {"pagina": 3, "tipo": "boas_vindas", "lado": "direita"},
            {"pagina": 4, "tipo": "pais_educadores", "lado": "esquerda"},
            {"pagina": 5, "tipo": "ficha_pedagogica", "lado": "direita"},
            {"pagina": 6, "tipo": "pagina_em_branco", "lado": "esquerda"},
        ],
        "cenas_texto": [],
        "cenas_imagem": [],
        "paginas_colorir": [],
    }
    result = renderer.renderizar_miolo_pdf(state, destino=str(destino), bleed=False, forcar=True)
    assert result["ok"] is True
    assert Path(result["caminho"]).exists()

    reader = PdfReader(str(destino))
    texto = "\n".join((p.extract_text() or "") for p in reader.pages)
    assert "Bem-vindos" in texto
    assert "Pais e Educadores" in texto
    assert "Ficha Pedagógica" in texto
    assert "6–8 anos" in texto


def test_instrucao_etaria_nao_e_regra_de_mercado():
    texto = instrucao_faixa_etaria("3-5")
    assert "FAIXA ETÁRIA OFICIAL" in texto
    assert "3–5 anos" in texto

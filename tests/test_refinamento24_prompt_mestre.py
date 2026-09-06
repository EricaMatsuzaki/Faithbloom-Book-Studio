from agents.estilos_narrativos import (
    ESTILOS_NARRATIVOS,
    aplicar_estilo_ao_state,
    gerar_comparativo_estilos,
)
from agents.complementos_editoriais import gerar_complementos_editoriais
from prompt_master_compliance import avaliar_prompt_mestre


def test_quatro_estilos_oficiais():
    assert list(ESTILOS_NARRATIVOS) == ["estilo_1", "estilo_2", "estilo_3", "misto"]


def test_amostra_nao_substitui_historia_aprovada():
    state = {
        "titulo": "Título original",
        "licao_final": "Moral original",
        "cenas_texto": [{"numero": 1, "texto": "Cena original"}],
        "revisao_aprovada": True,
    }
    versao = {
        "modo": "amostra",
        "titulo": "Outro título",
        "licao_final": "Outra moral",
        "cenas_texto": [{"numero": 1, "texto": "Outra cena"}],
    }
    novo = aplicar_estilo_ao_state(state, "estilo_2", versao)
    assert novo["estilo_narrativo"] == "estilo_2"
    assert novo["titulo"] == "Título original"
    assert novo["licao_final"] == "Moral original"
    assert novo["cenas_texto"] == state["cenas_texto"]
    assert novo["revisao_aprovada"] is True


def test_historia_completa_substitui_rascunho_e_exige_nova_revisao():
    state = {
        "titulo": "Título original",
        "licao_final": "Moral original",
        "cenas_texto": [{"numero": 1, "texto": "Cena original"}],
        "revisao_aprovada": True,
    }
    versao = {
        "modo": "completa",
        "titulo": "Título novo",
        "licao_final": "Moral nova",
        "sinopse_poetica": "Nova sinopse",
        "cenas_texto": [{"numero": 1, "texto": "Cena nova"}],
    }
    novo = aplicar_estilo_ao_state(state, "misto", versao)
    assert novo["titulo"] == "Título novo"
    assert novo["licao_final"] == "Moral nova"
    assert novo["cenas_texto"][0]["texto"] == "Cena nova"
    assert novo["revisao_aprovada"] is False


def test_comparativo_chama_os_quatro_estilos():
    chamadas = []

    def fake_llm(*, sistema, instrucao):
        chamadas.append((sistema, instrucao))
        return {
            "titulo": "Mesmo título",
            "sinopse_poetica": "Sinopse",
            "amostra": "Amostra",
            "licao_final": "Moral",
        }

    state = {
        "titulo": "História",
        "emocao_central": "alegria",
        "aprendizado_cristao": "bondade",
        "versiculo_referencia": "Efésios 4:32",
        "personagens": {"Mel": {"descricao_fixa": "gatinha creme"}},
    }
    resultado = gerar_comparativo_estilos(state, fake_llm, modo="amostra")
    assert set(resultado) == set(ESTILOS_NARRATIVOS)
    assert len(chamadas) == 4
    for chave, versao in resultado.items():
        assert versao["estilo"] == chave
        assert versao["modo"] == "amostra"


def test_moral_ausente_e_bloqueio_obrigatorio():
    relatorio = avaliar_prompt_mestre({
        "estilo_narrativo": "estilo_1",
        "boas_vindas": "Olá!",
        "pais_educadores": {"mensagem": "Mensagem"},
        "ficha_pedagogica": {"tema_central": "Bondade"},
        "paginas_colorir": [{}, {}, {}],
    })
    assert relatorio["ok_para_finalizar"] is False
    assert any(x["codigo"] == "MORAL_OBRIGATORIA" for x in relatorio["bloqueios"])


def test_tres_paginas_colorir_sao_o_padrao_atual():
    relatorio = avaliar_prompt_mestre({
        "licao_final": "A bondade floresce quando ajudamos.",
        "estilo_narrativo": "estilo_1",
        "boas_vindas": "Olá!",
        "pais_educadores": {"mensagem": "Mensagem"},
        "ficha_pedagogica": {"tema_central": "Bondade"},
        "paginas_colorir": [{}, {}, {}],
    })
    assert relatorio["regra_colorir"] == 3
    assert not any(x["codigo"] == "COLORIR_INCOMPLETO" for x in relatorio["recomendacoes"])


def test_complementos_editoriais_normalizados():
    def fake_llm(*, sistema, instrucao):
        return {
            "boas_vindas": "Olá, amiguinho!",
            "pais_educadores": {
                "mensagem": "Conversem sobre a história.",
                "perguntas": ["O que você aprendeu?"],
            },
            "ficha_pedagogica": {
                "faixa_etaria": "3–8 anos",
                "tema_central": "Bondade",
            },
        }

    extras = gerar_complementos_editoriais(
        {
            "titulo": "Livro",
            "licao_final": "Bondade",
            "versiculo_referencia": "Efésios 4:32",
        },
        fake_llm,
    )
    assert extras["boas_vindas"] == "Olá, amiguinho!"
    assert extras["pais_educadores"]["mensagem"]
    assert extras["ficha_pedagogica"]["faixa_etaria"] == "3–8 anos"

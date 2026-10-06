from agents.estilos_narrativos import _personagens_resumo, aplicar_estilo_ao_state
from agents.roteirista import roteirista_node


def test_briefing_de_personagens_entra_no_comparador_sem_dna_formal():
    state = {
        "personagens": {},
        "personagens_historia_brief": "Mel — gatinha protagonista.\nTéo — passarinho azul amigo.",
    }
    resumo = _personagens_resumo(state)
    assert "Mel" in resumo
    assert "Téo" in resumo
    assert "Briefing narrativo" in resumo


def test_escolha_de_amostra_define_estilo_sem_substituir_historia():
    state = {
        "titulo": "Meu título",
        "licao_final": "Minha moral",
        "cenas_texto": [{"numero": 1, "texto": "Original"}],
    }
    amostra = {
        "modo": "amostra",
        "titulo": "Outro título",
        "licao_final": "Outra moral",
        "amostra": "Preview",
    }
    novo = aplicar_estilo_ao_state(state, "estilo_2", amostra)
    assert novo["estilo_narrativo"] == "estilo_2"
    assert novo["titulo"] == "Meu título"
    assert novo["licao_final"] == "Minha moral"
    assert novo["cenas_texto"][0]["texto"] == "Original"
    assert novo["historia_escolhida_preservar"] is False


def test_historia_completa_escolhida_fica_marcada_para_preservacao():
    versao = {
        "modo": "completa",
        "titulo": "Versão aventura",
        "sinopse_poetica": "Sinopse",
        "licao_final": "Esperar com fé também é crescer.",
        "cenas_texto": [{"numero": 1, "texto": "Mel olhou o vaso."}],
    }
    novo = aplicar_estilo_ao_state({}, "estilo_1", versao)
    assert novo["historia_escolhida_preservar"] is True
    assert novo["cenas_texto"] == versao["cenas_texto"]


def test_roteirista_nao_sobrescreve_historia_completa_escolhida():
    chamadas = []

    def fake_llm(*args, **kwargs):
        chamadas.append((args, kwargs))
        raise AssertionError("LLM não deveria ser chamada quando a história escolhida deve ser preservada")

    state = {
        "estilo_narrativo": "misto",
        "historia_escolhida_preservar": True,
        "cenas_texto": [{"numero": 1, "texto": "História escolhida"}],
        "licao_final": "Moral obrigatória",
    }
    saida = roteirista_node(state, fake_llm)
    assert saida["cenas_texto"][0]["texto"] == "História escolhida"
    assert saida["historia_escolhida_preservar"] is False
    assert saida["revisao_aprovada"] is False
    assert chamadas == []

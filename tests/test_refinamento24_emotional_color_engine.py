from emotion_colors import EMOCOES, REGRA_NAO_MONOCROMATICA
from emotional_color_director import analisar_plutchik, direcao_emocional, construir_mapa_emocional
from agents.ilustrador import prompt_cena


def test_tabela_prompt_mestre_permanece_canonica():
    assert EMOCOES["alegria"]["cor"] == "amarelo-dourado"
    assert EMOCOES["tristeza"]["cor"] == "azul-claro"
    assert EMOCOES["medo"]["cor"] == "roxo-escuro"
    assert EMOCOES["raiva"]["cor"] == "vermelho/laranja"
    assert EMOCOES["ansiedade"]["cor"] == "rosa/lilás"
    assert EMOCOES["esperanca"]["cor"] == "dourado + azul-celeste"
    assert EMOCOES["alegria"]["uso_espiritual"] == "Amor de Deus e gratidão"
    assert EMOCOES["esperanca"]["uso_espiritual"] == "Clímax espiritual/final"


def test_plutchik_organiza_emocao_sem_substituir_cor_canonica():
    p = analisar_plutchik("esperanca", intensidade=3)
    assert p["familia_principal"] == "antecipacao"
    assert p["familia_secundaria"] == "alegria"
    assert p["combinacao"] == "otimismo"

    d = direcao_emocional("esperanca", intensidade=3)
    assert d["cor_principal"] == "dourado + azul-celeste"
    assert "Plutchik" in d["plutchik"]["nota"]


def test_subemocao_refina_atmosfera_e_preserva_nao_monocromia():
    d = direcao_emocional(
        "tristeza",
        intensidade=3,
        subemocao="frustracao",
        transicao="tristeza → começando a surgir esperança",
    )
    assert d["cor_principal"] == "azul-claro"
    assert "lavanda suave" in d["cores_apoio"]
    assert d["transicao_emocional"].startswith("tristeza")
    assert d["regra_nao_monocromatica"] == REGRA_NAO_MONOCROMATICA
    assert "Nunca recolorir" in d["regra_character_dna"]


def test_mapa_emocional_guarda_subemocao_intensidade_e_transicao():
    mapa = construir_mapa_emocional([
        {
            "numero": 1,
            "texto": "Mel esperou mais um pouquinho.",
            "emocao": "tristeza",
            "emocao_secundaria": "frustracao",
            "intensidade_emocional": 2,
            "transicao_emocional": "frustração → esperança",
        }
    ])
    d = mapa[0]["direcao"]
    assert d["subemocao"] == "frustracao"
    assert d["intensidade"] == 2
    assert d["transicao_emocional"] == "frustração → esperança"


def test_ilustrador_recebe_motor_emocional_completo():
    cena = {
        "numero": 1,
        "texto": "Mel olhou para o vasinho vazio.",
        "emocao": "tristeza",
        "emocao_secundaria": "frustracao",
        "intensidade_emocional": 2,
        "transicao_emocional": "tristeza → esperança",
        "figurino": "laço rosa",
        "contexto_visual": "jardim ao amanhecer",
        "personagem_principal": "Mel",
        "expressao": "olhar baixo, depois pequeno sorriso",
    }
    personagens = {
        "Mel": {
            "nome": "Mel",
            "descricao_fixa": "gatinha creme, olhos verdes",
            "papel": "protagonista",
        }
    }
    prompt = prompt_cena(cena, personagens, "esquerda")
    assert "azul-claro" in prompt
    assert "frustracao" in prompt
    assert "tristeza → esperança" in prompt
    assert "não a torne monocromática" in prompt
    assert "gatinha creme, olhos verdes" in prompt

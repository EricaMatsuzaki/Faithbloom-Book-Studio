from emotion_colors import EMOCOES, REGRA_NAO_MONOCROMATICA, paleta_para_prompt
from emotional_color_director import analisar_plutchik, direcao_emocional, construir_mapa_emocional
from agents.ilustrador import prompt_cena
from agents.estilos_narrativos import gerar_comparativo_estilos
from prompt_master_compliance import avaliar_prompt_mestre
from state import CenaTexto


def test_tabela_prompt_mestre_permanece_canonica():
    assert EMOCOES["alegria"]["cor"] == "amarelo-dourado"
    assert EMOCOES["tristeza"]["cor"] == "azul-claro"
    assert EMOCOES["medo"]["cor"] == "roxo-escuro"
    assert EMOCOES["raiva"]["cor"] == "vermelho/laranja"
    assert EMOCOES["ansiedade"]["cor"] == "rosa/lilás"
    assert EMOCOES["esperanca"]["cor"] == "dourado + azul-celeste"
    assert EMOCOES["alegria"]["uso_espiritual"] == "Amor de Deus e gratidão"
    assert EMOCOES["esperanca"]["uso_espiritual"] == "Clímax espiritual/final"


def test_paleta_aceita_emocoes_legadas_com_acento():
    assert "dourado + azul-celeste" in paleta_para_prompt("esperança")
    assert "azul-claro" in paleta_para_prompt("frustração")
    assert "amarelo-dourado" in paleta_para_prompt("gratidão")


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


def test_schema_cena_texto_documenta_campos_emocionais():
    anotacoes = CenaTexto.__annotations__
    assert "emocao" in anotacoes
    assert "emocao_secundaria" in anotacoes
    assert "intensidade_emocional" in anotacoes
    assert "transicao_emocional" in anotacoes


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


def test_compliance_nao_quebra_com_intensidade_legada_invalida():
    relatorio = avaliar_prompt_mestre({
        "licao_final": "Aprendemos a confiar em Deus.",
        "cenas_texto": [
            {"numero": 1, "texto": "Cena", "emocao": "alegria", "intensidade_emocional": ""},
            {"numero": 2, "texto": "Cena", "emocao": "tristeza", "intensidade_emocional": "antigo"},
        ],
    })
    assert any(x["codigo"] == "EMOCAO_POR_CENA_INCOMPLETA" for x in relatorio["recomendacoes"])


def test_quatro_estilos_completos_pedem_metadados_emocionais():
    chamadas = []

    def fake_llm(*, sistema, instrucao):
        chamadas.append((sistema, instrucao))
        return {
            "titulo": "História",
            "sinopse_poetica": "Sinopse",
            "cenas_texto": [],
            "licao_final": "Moral",
        }

    gerar_comparativo_estilos(
        {
            "titulo": "História",
            "emocao_central": "alegria",
            "aprendizado_cristao": "gratidão",
            "versiculo_referencia": "Salmo 118:24",
            "personagens": {},
            "paginas_minimas": 24,
        },
        fake_llm,
        modo="completa",
    )
    assert len(chamadas) == 4
    assert all("intensidade_emocional" in instrucao for _, instrucao in chamadas)
    assert all("transicao_emocional" in instrucao for _, instrucao in chamadas)
    assert all("onomatopeias" in sistema for sistema, _ in chamadas)

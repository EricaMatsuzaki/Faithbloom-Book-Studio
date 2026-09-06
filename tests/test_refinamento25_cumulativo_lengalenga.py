from pathlib import Path

from agents.estilos_narrativos import (
    ESTILOS_NARRATIVOS,
    ESTILOS_ADICIONAIS,
    ORDEM_ESTILOS,
    ORDEM_ESTILOS_ADICIONAIS,
    aplicar_estilo_ao_state,
    gerar_estilo_adicional,
)


def _state_base():
    return {
        "titulo": "Uma história que cresce",
        "_entrada_tema_livre": "Uma criança aprende gratidão à medida que novos amigos aparecem.",
        "emocao_central": "alegria",
        "aprendizado_cristao": "agradecer a Deus e compartilhar alegria",
        "versiculo_referencia": "1 Tessalonicenses 5:18",
        "faixa_etaria": "6-8",
        "paginas_minimas": 24,
        "personagens_historia_brief": "Lia; Beto; Pipoca.",
    }


def test_cumulativo_e_adicional_e_nao_aumenta_nucleo_de_quatro():
    assert list(ESTILOS_NARRATIVOS) == ["estilo_1", "estilo_2", "estilo_3", "misto"]
    assert ORDEM_ESTILOS == ("estilo_1", "estilo_2", "estilo_3", "misto")
    assert "cumulativo_lengalenga" not in ESTILOS_NARRATIVOS
    assert "cumulativo_lengalenga" in ORDEM_ESTILOS_ADICIONAIS
    spec = ESTILOS_ADICIONAIS["cumulativo_lengalenga"]
    assert spec["skill_base"] == "storyteller"
    assert "refrão" in spec["instrucao"]
    assert "releitura" in spec["instrucao"]
    assert "humor" in spec["instrucao"]


def test_cumulativo_herda_skill_storyteller_e_exige_originalidade():
    capturado = {}

    def fake_llm(*, sistema, instrucao):
        capturado["sistema"] = sistema
        capturado["instrucao"] = instrucao
        return {
            "titulo": "A Festa que Crescia",
            "sinopse_poetica": "Cada novo amigo acrescenta um motivo para agradecer.",
            "amostra": "Chegou um amigo. Depois chegou outro. E a alegria cresceu.",
            "licao_final": "A gratidão cresce quando aprendemos a reconhecer as bênçãos de Deus.",
        }

    out = gerar_estilo_adicional(_state_base(), fake_llm, "cumulativo_lengalenga", modo="amostra")
    assert out["estilo"] == "cumulativo_lengalenga"
    assert out["modo"] == "amostra"
    assert "storytelling infantil" in capturado["sistema"]
    assert "estrutura cumulativa original" in capturado["sistema"]
    assert "não copie" in capturado["sistema"].lower()


def test_cumulativo_completo_pode_ser_aplicado_sem_virar_aventura():
    state = _state_base()
    versao = {
        "modo": "completa",
        "titulo": "A Festa que Crescia",
        "sinopse_poetica": "Uma festa de gratidão cresce amigo por amigo.",
        "cenas_texto": [{"numero": 1, "texto": "Lia bateu palmas uma vez."}],
        "licao_final": "A gratidão cresce quando compartilhamos alegria.",
    }
    novo = aplicar_estilo_ao_state(state, "cumulativo_lengalenga", versao)
    assert novo["estilo_narrativo"] == "cumulativo_lengalenga"
    assert novo["estilo_narrativo_label"] == "🔁 Cumulativo / Lengalenga"
    assert novo["historia_escolhida_preservar"] is True
    assert novo["cenas_texto"][0]["numero"] == 1


def test_ui_expoe_biblioteca_opcional_sem_geracao_automatica():
    source = Path("pages/40_➕_Explorar_outros_estilos.py").read_text(encoding="utf-8")
    assert "Explorar outros estilos" in source
    assert "Gerar amostra Cumulativo/Lengalenga" in source
    assert "Gerar história COMPLETA Cumulativo/Lengalenga" in source
    assert "Tornar Cumulativo/Lengalenga a versão ativa" in source
    assert "prazer de antecipação e releitura" in source


def test_fluxo_principal_aponta_para_biblioteca_de_estilos_adicionais():
    source = Path("pages/39_✍️_Historia_4_Estilos.py").read_text(encoding="utf-8")
    assert '"pages/40_➕_Explorar_outros_estilos.py"' in source
    assert "➕ Explorar outros estilos narrativos" in source
    assert "Cumulativo/Lengalenga" in source
    assert '"💾 Salvar rascunho"' in source

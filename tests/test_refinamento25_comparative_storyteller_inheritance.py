from agents.estilos_narrativos import (
    ESTILOS_NARRATIVOS,
    ORDEM_ESTILOS,
    SKILL_PROFILE_IDS,
    gerar_comparativo_estilos,
)


def _state_base():
    return {
        "titulo": "Clara e o Corredor",
        "_entrada_tema_livre": "Clara precisa atravessar um corredor escuro e aprender a confiar em Deus.",
        "emocao_central": "medo",
        "aprendizado_cristao": "confiar em Deus quando sentimos medo",
        "versiculo_referencia": "Salmos 56:3",
        "faixa_etaria": "6-8",
        "paginas_minimas": 24,
        "personagens_historia_brief": "Clara; Sofia; Ben; Floc.",
    }


def test_todos_os_estilos_formais_declaram_storyteller_como_skill_base():
    assert SKILL_PROFILE_IDS == ("storyteller",)
    assert len(ORDEM_ESTILOS) == 4
    for estilo in ORDEM_ESTILOS:
        assert ESTILOS_NARRATIVOS[estilo]["skill_base"] == "storyteller"


def test_comparative_story_director_herda_contrato_storyteller_em_todos_os_estilos():
    chamadas = []

    def fake_llm(*, sistema, instrucao):
        chamadas.append((sistema, instrucao))
        return {
            "titulo": "Clara e o Corredor",
            "sinopse_poetica": "Uma história de coragem e confiança.",
            "amostra": "Clara respirou fundo e deu um passo.",
            "licao_final": "Podemos confiar em Deus quando sentimos medo.",
        }

    gerar_comparativo_estilos(_state_base(), fake_llm, modo="amostra")

    assert len(chamadas) == 4
    for sistema, _ in chamadas:
        assert "HERDA integralmente a skill formal `storyteller`" in sistema
        assert "storytelling infantil" in sistema
        assert "gancho inicial" in sistema
        assert "page-turn structure" in sistema
        assert "read-aloud rhythm" in sistema
        assert "arco emocional" in sistema
        assert "ação visual" in sistema
        assert "integração cristã natural" in sistema
        assert "fechamento memorável" in sistema


def test_cada_estilo_mantem_sua_especializacao_sobre_o_mesmo_core():
    sistemas = []

    def fake_llm(*, sistema, instrucao):
        sistemas.append(sistema)
        return {"amostra": "Amostra", "licao_final": "Moral"}

    gerar_comparativo_estilos(_state_base(), fake_llm, modo="amostra")

    for estilo, sistema in zip(ORDEM_ESTILOS, sistemas):
        spec = ESTILOS_NARRATIVOS[estilo]
        assert spec["label"] in sistema
        assert spec["instrucao"] in sistema
        assert "ESPECIALIZAÇÃO NARRATIVA OBRIGATÓRIA" in sistema

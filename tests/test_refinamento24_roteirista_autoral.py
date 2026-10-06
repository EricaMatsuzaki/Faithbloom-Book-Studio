from pathlib import Path

from agents.estilos_narrativos import normalizar_licao_final
from agents.roteirista_autoral import (
    gerar_proposta_roteirista,
    gerar_versao_autoral_roteirista,
)
from state import LivroState


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


def test_moral_estruturada_vira_texto_limpo():
    moral = normalizar_licao_final({
        "texto": "Clara escolheu confiar mesmo com medo.",
        "versiculo": "Salmos 56:3",
        "reflexao_extra": "A coragem pode começar com um passo pequeno.",
    })
    assert "{" not in moral
    assert "Clara escolheu confiar" in moral
    assert "A coragem pode começar" in moral
    assert "Salmos 56:3" in moral


def test_proposta_do_roteirista_usa_skill_storyteller_e_nao_gera_cenas():
    capturado = {}

    def fake_llm(*, sistema, instrucao):
        capturado["sistema"] = sistema
        capturado["instrucao"] = instrucao
        return {
            "titulo_alternativo": "Um Passo no Escuro",
            "gancho": "Um rangido muda a noite de Clara.",
            "direcao_narrativa": "A coragem cresce a cada tentativa.",
            "arco_emocional": "medo → confiança",
            "momento_de_virada": "Clara recorda a referência bíblica.",
            "final_sugerido": "Ela atravessa e depois ajuda Sofia.",
            "estilo_recomendado": "misto",
            "justificativa_criativa": "Equilibra movimento e ternura.",
        }

    out = gerar_proposta_roteirista(_state_base(), fake_llm)
    assert out["origem"] == "storyteller_skill"
    assert out["estilo_recomendado"] == "misto"
    assert "ROTEIRISTA PRINCIPAL" in capturado["sistema"]
    assert "storytelling infantil" in capturado["sistema"]
    assert "Não reescreva o briefing e não gere cenas completas" in capturado["instrucao"]


def test_versao_autoral_roteirista_e_quinta_opcao_independente():
    def fake_llm(*, sistema, instrucao):
        return {
            "titulo": "Um Passo no Escuro",
            "sinopse_poetica": "Clara aprende que coragem não é ausência de medo.",
            "cenas_texto": [{"numero": 1, "texto": "CREEEC! Clara parou."}],
            "licao_final": {"texto": "Podemos confiar em Deus quando sentimos medo.", "versiculo": "Salmos 56:3"},
            "estilo_recomendado": "Estilo misto",
            "justificativa_criativa": "O tema pede movimento e acolhimento.",
        }

    out = gerar_versao_autoral_roteirista(_state_base(), fake_llm)
    assert out["estilo"] == "roteirista_autoral"
    assert out["origem"] == "storyteller_skill"
    assert out["modo"] == "completa"
    assert out["estilo_recomendado"] == "misto"
    assert out["cenas_texto"][0]["numero"] == 1
    assert "{" not in out["licao_final"]


def test_state_formaliza_biblioteca_de_versoes():
    for campo in (
        "proposta_roteirista",
        "versao_roteirista_autoral",
        "comparativo_estilos",
        "versoes_narrativas_salvas",
        "versao_narrativa_ativa",
        "versao_narrativa_origem",
        "historico_derivados_por_versao",
    ):
        assert campo in LivroState.__annotations__


def test_ui_expoe_roteirista_e_biblioteca_persistente():
    source = Path("pages/39_✍️_Historia_4_Estilos.py").read_text(encoding="utf-8")
    assert "Ver a proposta do Roteirista para esta ideia" in source
    assert "Gerar versão do Roteirista" in source
    assert "Biblioteca de Versões Narrativas" in source
    assert "versoes_narrativas_salvas" in source
    assert "Salvar todas as versões no projeto" in source
    assert "historico_derivados_por_versao" in source

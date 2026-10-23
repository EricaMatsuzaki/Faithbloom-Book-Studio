from pathlib import Path

from agents.estilos_narrativos import (
    ESTILOS_ADICIONAIS,
    ESTILOS_NARRATIVOS,
    gerar_estilo_adicional,
)
from agents.formato_quadrinhos import (
    FORMATO_QUADRINHOS_ID,
    gerar_roteiro_quadrinhos,
)


def _state():
    return {
        "colecao": "PILOTO QA",
        "titulo": "Clara e o corredor",
        "_entrada_tema_livre": "Clara sente medo do corredor escuro e aprende a confiar em Deus.",
        "faixa_etaria": "6-8",
        "paginas_minimas": 24,
        "emocao_central": "medo",
        "aprendizado_cristao": "Confiar em Deus quando sentimos medo.",
        "versiculo_referencia": "Salmos 56:3",
        "versao_narrativa_ativa": "misto",
        "estilo_narrativo": "misto",
        "estilo_narrativo_label": "Estilo misto",
        "personagens": {
            "Clara": {"papel": "protagonista", "descricao_fixa": "menina curiosa"},
            "Sofia": {"papel": "irmã", "descricao_fixa": "irmã mais nova"},
        },
        "cenas_texto": [
            {"numero": 1, "texto": "Clara parou diante do corredor e apertou a lanterna."},
            {"numero": 2, "texto": "Sofia chamou Clara e as duas seguiram juntas."},
        ],
        "licao_final": "Quando sinto medo, posso confiar em Deus.",
    }


def test_cotidiano_comico_e_adicional_sem_alterar_quatro_oficiais():
    assert tuple(ESTILOS_NARRATIVOS) == ("estilo_1", "estilo_2", "estilo_3", "misto")
    assert "cotidiano_comico_diario_visual" in ESTILOS_ADICIONAIS
    spec = ESTILOS_ADICIONAIS["cotidiano_comico_diario_visual"]
    assert spec["skill_base"] == "storyteller"
    texto = (spec["descricao"] + " " + spec["instrucao"] + " " + spec["meta_editorial"]).lower()
    assert "terceira pessoa" in texto
    assert "cotidiano" in texto
    assert "diálogos" in texto
    assert "humor" in texto
    assert "bordões" in texto
    assert "6–8" in texto
    assert "9–12" in texto


def test_cotidiano_comico_herda_skill_real_do_roteirista():
    chamadas = []

    def fake_llm(*, sistema, instrucao):
        chamadas.append((sistema, instrucao))
        return {
            "titulo": "Uma terça muito complicada",
            "sinopse_poetica": "Um problema comum vira uma confusão divertida.",
            "amostra": "Clara tinha um plano. Era um plano excelente. Por quase três minutos.",
            "elementos_graficos_sugeridos": ["Lista dos planos que deram errado"],
            "licao_final": "Pedir ajuda também é um ato de coragem.",
        }

    resultado = gerar_estilo_adicional(
        _state(), fake_llm, "cotidiano_comico_diario_visual", modo="amostra"
    )
    assert resultado["estilo"] == "cotidiano_comico_diario_visual"
    assert resultado["elementos_graficos_sugeridos"] == ["Lista dos planos que deram errado"]
    sistema = chamadas[0][0].lower()
    assert "skill formal `storyteller`" in sistema
    assert "page-turn" in sistema
    assert "não copie" in sistema
    assert "bordões" in sistema


def test_hq_e_formato_visual_e_preserva_historia_fonte():
    chamadas = []

    def fake_llm(*, sistema, instrucao):
        chamadas.append((sistema, instrucao))
        return {
            "titulo": "Clara e o corredor",
            "paginas": [
                {
                    "numero": 1,
                    "layout_sugerido": "três painéis verticais",
                    "gancho_virada": "A porta faz toc-toc.",
                    "paineis": [
                        {
                            "numero": 1,
                            "acao_visual": "Clara segura a lanterna diante do corredor.",
                            "dialogos": [{"personagem": "Clara", "fala": "Eu consigo."}],
                            "narracao": "",
                            "sfx": "toc-toc",
                            "emocao": "medo",
                            "personagem_foco": "Clara",
                        }
                    ],
                }
            ],
            "licao_final": "Quando sinto medo, posso confiar em Deus.",
            "observacoes_diagramacao": "Balões curtos e leitura da esquerda para a direita.",
        }

    resultado = gerar_roteiro_quadrinhos(_state(), fake_llm)
    assert resultado["formato"] == FORMATO_QUADRINHOS_ID
    assert resultado["estilo_narrativo_origem"] == "misto"
    assert resultado["paginas"][0]["paineis"][0]["dialogos"][0]["personagem"] == "Clara"
    sistema, instrucao = chamadas[0]
    sistema_lower = sistema.lower()
    assert "formato narrativo visual" in sistema_lower
    assert "skill formal `storyteller`" in sistema_lower
    assert "balões" in sistema_lower
    assert "nunca peça ao gerador de imagens" in sistema_lower
    assert "não copie bordões" in sistema_lower
    assert "Clara parou diante do corredor" in instrucao
    assert "Salmos 56:3" in instrucao


def test_ui_separa_estilo_de_formato_e_expoe_as_duas_novas_opcoes():
    source = Path("pages/40_➕_Explorar_outros_estilos.py").read_text(encoding="utf-8")
    assert "📚 Estilos narrativos adicionais" in source
    assert "🗯️ Formatos narrativos visuais" in source
    assert "cotidiano_comico_diario_visual" not in source  # vem do registry, sem hardcode por estilo
    assert "gerar_roteiro_quadrinhos" in source
    assert "🗯️ Gerar roteiro de Quadrinhos/HQ infantil" in source
    assert "✅ Usar Quadrinhos/HQ como formato ativo" in source
    assert 's.setdefault("formatos_narrativos_salvos", {})' in source
    assert "A história literária original foi preservada" in source

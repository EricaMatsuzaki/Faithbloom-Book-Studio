"""
Monta o pipeline completo em LangGraph.

Ordem: Roteirista -> Revisor -(loop se reprovado)-> Roteirista
                   -(aprovado)-> Ilustrador -> Dedicatória Dinâmica
                   -> Tradutor -> Sinopse de Vendas -> Diagramador/KDP
"""

from langgraph.graph import StateGraph, END

from state import LivroState
from agents.curador_tema import curador_tema_node
from agents.roteirista import roteirista_node
from agents.revisor import revisor_node, precisa_retrabalho
from agents.ilustrador import ilustrador_node
from agents.atividades_colorir import atividades_colorir_node
from agents.audiobook import audiobook_node, narracao_node
from agents.dedicatoria import dedicatoria_node
from agents.tradutor import tradutor_node
from agents.sinopse import sinopse_node
from agents.pesquisa_mercado import pesquisa_palavras_chave_node, pesquisa_categorias_node
from agents.diagramador import diagramador_node
from agents.capa import capa_node
from agents.marketing import marketing_lancamento_node


def construir_grafo(chamar_llm, gerar_imagem, gerar_audio):
    """
    chamar_llm, gerar_imagem e gerar_audio são injetados de fora (ver
    main.py) para manter os agentes desacoplados de qual provedor de IA
    está sendo usado - troca de modelo/API não exige reescrever os
    agentes.
    """
    grafo = StateGraph(LivroState)

    grafo.add_node("curador_tema", lambda s: curador_tema_node(s, chamar_llm))
    grafo.add_node("roteirista", lambda s: roteirista_node(s, chamar_llm))
    grafo.add_node("revisor", lambda s: revisor_node(s, chamar_llm))
    grafo.add_node("ilustrador", lambda s: ilustrador_node(s, gerar_imagem))
    grafo.add_node("atividades_colorir", lambda s: atividades_colorir_node(s, gerar_imagem))
    grafo.add_node("audiobook", lambda s: audiobook_node(s, chamar_llm))
    grafo.add_node("narrador", lambda s: narracao_node(s, gerar_audio))
    grafo.add_node("dedicatoria", lambda s: dedicatoria_node(s, chamar_llm))
    grafo.add_node("tradutor", lambda s: tradutor_node(s, chamar_llm))
    grafo.add_node("sinopse", lambda s: sinopse_node(s, chamar_llm))
    grafo.add_node("palavras_chave", lambda s: pesquisa_palavras_chave_node(s, chamar_llm))
    grafo.add_node("categorias", lambda s: pesquisa_categorias_node(s, chamar_llm))
    grafo.add_node("diagramador", lambda s: diagramador_node(s))
    grafo.add_node("capa", lambda s: capa_node(s, gerar_imagem))
    grafo.add_node("marketing", lambda s: marketing_lancamento_node(s, chamar_llm))

    grafo.set_entry_point("curador_tema")
    grafo.add_edge("curador_tema", "roteirista")
    grafo.add_edge("roteirista", "revisor")
    grafo.add_conditional_edges(
        "revisor",
        precisa_retrabalho,
        {"roteirista": "roteirista", "ilustrador": "ilustrador"},
    )
    grafo.add_edge("ilustrador", "atividades_colorir")
    grafo.add_edge("atividades_colorir", "audiobook")
    grafo.add_edge("audiobook", "narrador")
    grafo.add_edge("narrador", "dedicatoria")
    grafo.add_edge("dedicatoria", "tradutor")
    grafo.add_edge("tradutor", "sinopse")
    grafo.add_edge("sinopse", "palavras_chave")
    grafo.add_edge("palavras_chave", "categorias")
    grafo.add_edge("categorias", "diagramador")
    grafo.add_edge("diagramador", "capa")
    grafo.add_edge("capa", "marketing")
    grafo.add_edge("marketing", END)

    return grafo.compile()

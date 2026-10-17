"""
Monta o pipeline completo em LangGraph.

Ordem: Roteirista -> Revisor -(loop se reprovado)-> Roteirista
                   -(aprovado)-> Complementos Editoriais -> Ilustrador
                   -> Dedicatória Dinâmica -> Tradutor -> Sinopse de Vendas
                   -> Diagramador/KDP
"""

from langgraph.graph import StateGraph, END

from state import LivroState
from state_prompt_master import LivroStatePromptMestre
from agents.curador_tema import curador_tema_node
from agents.roteirista import roteirista_node
from agents.revisor import revisor_node
from agents.complementos_editoriais import gerar_complementos_editoriais
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


def _complementos_node(state: LivroState, chamar_llm) -> LivroState:
    extras = gerar_complementos_editoriais(dict(state), chamar_llm)
    state["boas_vindas"] = extras.get("boas_vindas", "")
    state["pais_educadores"] = extras.get("pais_educadores", {})
    state["ficha_pedagogica"] = extras.get("ficha_pedagogica", {})
    return state


def construir_grafo(chamar_llm, gerar_imagem, gerar_audio, *, max_editorial_reviews: int = 2, resume_after_emotional_review: bool = False):
    """
    chamar_llm, gerar_imagem e gerar_audio são injetados de fora (ver
    main.py) para manter os agentes desacoplados de qual provedor de IA
    está sendo usado - troca de modelo/API não exige reescrever os
    agentes.
    """
    if isinstance(max_editorial_reviews, bool) or not isinstance(max_editorial_reviews, int) or not 1 <= max_editorial_reviews <= 5:
        raise ValueError("Escolha entre uma e cinco revisões editoriais por execução.")
    if not isinstance(resume_after_emotional_review, bool):
        raise ValueError("Informe explicitamente se deseja retomar o mapa emocional revisado.")

    def review(state):
        result = revisor_node(state, chamar_llm)
        result["editorial_review_attempts"] = int(state.get("editorial_review_attempts", 0)) + 1
        if result.get("revisao_aprovada"):
            result["pipeline_status"] = "editorial_review_approved"
            from emotional_visual_binding import require_book_emotional_map
            try:
                require_book_emotional_map(result)
            except PermissionError:
                result["pipeline_status"] = "awaiting_emotional_review"
        elif result["editorial_review_attempts"] >= max_editorial_reviews:
            result["pipeline_status"] = "awaiting_human_review"
        else:
            result["pipeline_status"] = "editorial_revision_requested"
        from generation_autosave import persist_generation_snapshot
        persist_generation_snapshot(result, reason="editorial_review_checkpoint")
        return result

    def after_review(state):
        if state.get("pipeline_status") == "awaiting_emotional_review":
            return "human_review"
        if state.get("revisao_aprovada"):
            return "approved"
        if int(state.get("editorial_review_attempts", 0)) >= max_editorial_reviews:
            return "human_review"
        return "revise"

    def start(state):
        # A new invocation has its own finite attempt budget, while preserving
        # existing notes and drafts. A review pause never starts image/audio.
        state["editorial_review_attempts"] = 0
        state["pipeline_status"] = "editorial_review_started"
        return curador_tema_node(state, chamar_llm)

    def resume(state):
        from emotional_visual_binding import require_book_emotional_map
        if state.get("revisao_aprovada") is not True:
            raise PermissionError("Conclua a revisão editorial da história antes de retomar as ilustrações.")
        require_book_emotional_map(state)
        state["pipeline_status"] = "emotional_review_approved"
        return state

    grafo = StateGraph(LivroStatePromptMestre)

    grafo.add_node("curador_tema", start)
    grafo.add_node("roteirista", lambda s: roteirista_node(s, chamar_llm))
    grafo.add_node("revisor", review)
    grafo.add_node("complementos_editoriais", lambda s: _complementos_node(s, chamar_llm))
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

    if resume_after_emotional_review:
        grafo.add_node("retomar_mapa_emocional", resume)
        grafo.set_entry_point("retomar_mapa_emocional")
        grafo.add_edge("retomar_mapa_emocional", "complementos_editoriais")
    else:
        grafo.set_entry_point("curador_tema")
    grafo.add_edge("curador_tema", "roteirista")
    grafo.add_edge("roteirista", "revisor")
    grafo.add_conditional_edges(
        "revisor",
        after_review,
        {"revise": "roteirista", "approved": "complementos_editoriais", "human_review": END},
    )
    grafo.add_edge("complementos_editoriais", "ilustrador")
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

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
        try:
            persist_generation_snapshot(result, reason="editorial_review_checkpoint")
        except Exception:
            if not result.get("autosave_pending"):
                raise
            result["pipeline_status"] = "awaiting_generation_save"
        return result

    def after_review(state):
        if state.get("autosave_pending"):
            return "human_review"
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

    def guarded(operation):
        def step(state):
            if state.get("autosave_pending"):
                state["pipeline_status"] = "awaiting_generation_save"
                return state
            # LangGraph keeps only declared channels. Saved annotations outside
            # that schema are not deletions made by this pipeline: restore them
            # from the exact read handle before an agent checkpoints its output.
            # An expired handle fails before making any provider request.
            if state.get("storage_path"):
                from armazenamento import get_book_read_context
                from copy import deepcopy
                observed = get_book_read_context(state, state["storage_path"])["view"]
                declared = LivroStatePromptMestre.__annotations__
                for key, value in observed.items():
                    if key not in declared and key not in state:
                        state[key] = deepcopy(value)
            try:
                result = operation(state)
            except Exception:
                if not state.get("autosave_pending"):
                    raise
                result = state
            if result.get("autosave_pending"):
                result["pipeline_status"] = "awaiting_generation_save"
            return result
        return step

    def route_after_save(next_step):
        def route(state):
            return "pause" if state.get("autosave_pending") else "continue"
        return route, {"pause": END, "continue": next_step}

    grafo = StateGraph(LivroStatePromptMestre)

    grafo.add_node("curador_tema", guarded(start))
    grafo.add_node("roteirista", guarded(lambda s: roteirista_node(s, chamar_llm)))
    grafo.add_node("revisor", guarded(review))
    grafo.add_node("complementos_editoriais", guarded(lambda s: _complementos_node(s, chamar_llm)))
    grafo.add_node("ilustrador", guarded(lambda s: ilustrador_node(s, gerar_imagem)))
    grafo.add_node("atividades_colorir", guarded(lambda s: atividades_colorir_node(s, gerar_imagem)))
    grafo.add_node("audiobook", guarded(lambda s: audiobook_node(s, chamar_llm)))
    grafo.add_node("narrador", guarded(lambda s: narracao_node(s, gerar_audio)))
    grafo.add_node("dedicatoria", guarded(lambda s: dedicatoria_node(s, chamar_llm)))
    grafo.add_node("tradutor", guarded(lambda s: tradutor_node(s, chamar_llm)))
    grafo.add_node("sinopse", guarded(lambda s: sinopse_node(s, chamar_llm)))
    grafo.add_node("palavras_chave", guarded(lambda s: pesquisa_palavras_chave_node(s, chamar_llm)))
    grafo.add_node("categorias", guarded(lambda s: pesquisa_categorias_node(s, chamar_llm)))
    grafo.add_node("diagramador", guarded(lambda s: diagramador_node(s)))
    grafo.add_node("capa", guarded(lambda s: capa_node(s, gerar_imagem)))
    grafo.add_node("marketing", guarded(lambda s: marketing_lancamento_node(s, chamar_llm)))

    if resume_after_emotional_review:
        grafo.add_node("retomar_mapa_emocional", guarded(resume))
        grafo.set_entry_point("retomar_mapa_emocional")
        route, options = route_after_save("complementos_editoriais")
        grafo.add_conditional_edges("retomar_mapa_emocional", route, options)
    else:
        grafo.set_entry_point("curador_tema")
    for first, following in (("curador_tema", "roteirista"), ("roteirista", "revisor")):
        route, options = route_after_save(following)
        grafo.add_conditional_edges(first, route, options)
    grafo.add_conditional_edges(
        "revisor",
        after_review,
        {"revise": "roteirista", "approved": "complementos_editoriais", "human_review": END},
    )
    chain = ("complementos_editoriais", "ilustrador", "atividades_colorir", "audiobook", "narrador",
             "dedicatoria", "tradutor", "sinopse", "palavras_chave", "categorias", "diagramador", "capa", "marketing")
    for first, following in zip(chain, chain[1:]):
        route, options = route_after_save(following)
        grafo.add_conditional_edges(first, route, options)
    grafo.add_edge("marketing", END)

    return grafo.compile()

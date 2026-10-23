"""User actions for the persistent editorial dispatcher."""
from __future__ import annotations

from copy import deepcopy
import uuid
import streamlit as st
from editorial_dispatch import (
    SPECIALIZED_TYPES, create_editorial_run, execute_editorial_generation,
    initialize_specialist, list_runs, load_run, sync_source,
    apply_native_studio_context,
    prepare_comic_handoff,
)


def render_editorial_execution(route: dict) -> None:
    st.subheader("Crie ou continue o projeto")
    with st.expander("Novo projeto", expanded=not st.session_state.get("editorial_run_id")):
        title = st.text_input("Título do projeto", key="run_new_title")
        brief = st.text_area("O que você quer criar?", key="run_new_brief", placeholder="Conte a ideia, o objetivo, o tema ou cole seu conteúdo.")
        collection = st.text_input("Coleção do projeto (opcional)", key="run_new_collection")
        bible = st.text_input("Referência bíblica (obrigatória para devocional)", key="run_bible_reference")
        unit_count = st.number_input("Unidades ou capítulos", min_value=1, max_value=40, value=3, step=1, key="run_unit_count")
        source_text = st.text_area("Material de referência para estudos, exercícios ou cartões", key="run_source_text", help="Forneça o trecho que poderá ser usado para elaborar e conferir o conteúdo.")
        custom = st.text_input("Blocos de um projeto personalizado (separe por vírgula)", key="run_custom_blocks")
        if st.button("Criar projeto e salvar briefing", type="primary", disabled=not title.strip() or not brief.strip(), key="create_editorial_run"):
            try:
                sources = [{"id": "author_source", "label": "Material fornecido pela autora", "content": source_text.strip()}] if source_text.strip() else []
                run = create_editorial_run(route["project_type"], title, brief, origin=route["origin"], audience=route["audience"], editorial_line=route["editorial_line"], collection=collection, derived_outputs=list(st.session_state.get("orchestrator_derived_outputs") or []), unit_count=int(unit_count), sources=sources, bible_reference=bible.strip(), custom_blocks=[x.strip() for x in custom.split(",") if x.strip()])
                st.session_state["editorial_run_id"] = run["id"]
                run = initialize_specialist(run["id"])
                st.success("Projeto salvo. A geração só começa quando você escolher a ação.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    try:
        runs = list_runs()
    except Exception:
        st.error("Não foi possível ler os projetos salvos. O armazenamento precisa responder antes de continuar.")
        return
    if runs:
        ids = [row["id"] for row in runs]
        selected = st.selectbox("Projetos do Orquestrador", ["", *ids], format_func=lambda value: "Escolha um projeto" if not value else next(row["title"] + " · " + row["route_plan"]["project_label"] for row in runs if row["id"] == value), key="run_saved_selection")
        if selected and st.button("Abrir projeto selecionado", key="open_editorial_run"):
            st.session_state["editorial_run_id"] = selected
            selected_run = load_run(selected)
            st.session_state["orchestrator_visual_plan_id"] = selected_run.get("visual_plan_id") or None
            st.rerun()
    run_id = st.session_state.get("editorial_run_id")
    if not run_id:
        return
    try:
        run = load_run(run_id)
    except Exception:
        st.warning("O projeto ativo não pôde ser carregado. Selecione um projeto salvo para continuar.")
        return
    st.markdown(f"**Projeto ativo: {run['title']}**")
    st.caption(run["route_plan"]["project_label"])
    if run["project_type"] != route["project_type"]:
        st.info("O projeto salvo mantém o tipo e as opções escolhidos na criação. As opções acima serão usadas apenas em novos projetos.")
    if not run.get("source"):
        if st.button("Inicializar o Studio deste projeto", key="initialize_editorial_run"):
            try:
                initialize_specialist(run_id)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        return
    state = run["generation"].get("status")
    labels = {"not_started": "Conteúdo ainda não gerado", "running": "Execução interrompida ou ainda em andamento — revise antes de retomar", "interrupted": "Geração interrompida; rascunho preservado", "completed": "Conteúdo gerado; revise no Studio"}
    st.write(labels.get(state, "Projeto em desenvolvimento"))
    if run["project_type"] in SPECIALIZED_TYPES:
        confirmed = st.checkbox("Confirmo gerar o conteúdo com IA e consumir os créditos do provedor configurado", key=f"run_paid_{run_id}")
        consent = st.checkbox("Confirmo ter autorização para enviar os dados deste relato real ao provedor de IA", key=f"run_consent_{run_id}") if run["route_plan"].get("origin")=="real_experience" else False
        resume = st.checkbox("Revisei o rascunho e confirmo retomar a execução interrompida", key=f"run_resume_{run_id}") if state in {"running", "interrupted", "save_failed"} else False
        if st.button("Gerar unidades pendentes", disabled=not confirmed or state == "completed" or (run["route_plan"].get("origin")=="real_experience" and not consent), key=f"run_generate_{run_id}"):
            try:
                with st.spinner("Gerando e salvando cada unidade..."):
                    execute_editorial_generation(run_id, confirmed=confirmed, resume_confirmed=resume, consent_confirmed=consent)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
                st.info("Revise o rascunho no Studio antes de tentar novamente. Unidades concluídas são preservadas.")
    col1, col2 = st.columns(2)
    studio_label = "Preparar ou revisar a história-base" if run["project_type"] == "comic" else "Abrir Studio para gerar ou revisar"
    if col1.button(studio_label, key=f"run_studio_{run_id}", use_container_width=True):
        try:
            run = sync_source(run_id)
            apply_native_studio_context(st.session_state,run)
            st.switch_page(run["studio_page"])
        except Exception as exc:
            st.error(str(exc))
    if col2.button("Atualizar conteúdo salvo pelo Studio", key=f"run_sync_{run_id}", use_container_width=True):
        try:
            run = sync_source(run_id)
            st.session_state["orchestrator_visual_plan_id"] = run.get("visual_plan_id") or None
            st.success("Conteúdo atualizado a partir do projeto salvo.")
        except Exception as exc:
            st.error(str(exc))
    # Offer the canonical shared studios with the exact source loaded in session.
    if run.get("source", {}).get("cenas_texto"):
        if run["project_type"] in {"children_story", "real_life_story", "comic"}:
            if st.button("Adaptar esta história em quadrinhos", key=f"run_comic_handoff_{run_id}"):
                try:
                    prepare_comic_handoff(st.session_state, run_id)
                    st.switch_page("pages/58_🗯️_Quadrinhos.py")
                except Exception as exc:
                    st.error(str(exc))
        st.caption("Saídas adicionais usam a mesma fonte salva e continuam exigindo revisão e aprovação.")
        targets = [("Traduzir / localizar", "pages/21_Translation_Localization_Studio.py"), ("Audiobook", "pages/24_🎧_Audiobook_Studio.py"), ("Revisão de qualidade", "pages/25_🛡️_Quality_Guardian.py")]
        for col, (label, page) in zip(st.columns(3), targets):
            if col.button(label, key=f"run_handoff_{page}_{run_id}", use_container_width=True):
                from integration_ux import PROJECT_CONTEXT_KEY, make_project_context
                try:
                    run = sync_source(run_id)
                    source = deepcopy(run["source"])
                    source["storage_path"] = run["source_ref"]
                    context = make_project_context({"kind": "story", "titulo": source.get("titulo"), "colecao": source.get("colecao"), "storage_path": run["source_ref"]}, source)
                    context["audience"] = run["route_plan"]["audience"]
                    target = "translation" if page.startswith("pages/21_") else "audiobook" if page.startswith("pages/24_") else "quality"
                    st.session_state[PROJECT_CONTEXT_KEY] = context
                    st.session_state["editorial_studio_handoff"] = {"target": target, "project": context, "token": uuid.uuid4().hex}
                    st.session_state["state"] = source
                    st.switch_page(page)
                except Exception as exc:
                    st.error(str(exc))
    st.divider()

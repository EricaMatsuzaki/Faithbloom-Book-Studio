"""User actions for the persistent editorial dispatcher."""
from __future__ import annotations

from copy import deepcopy
import json
import uuid
import streamlit as st
from editorial_dispatch import (
    SPECIALIZED_TYPES, create_editorial_run, execute_editorial_generation,
    initialize_specialist, list_runs, load_run, sync_source,
    apply_native_studio_context,
    prepare_comic_handoff,
)


def preserve_editorial_response(exc, reference: str) -> bool:
    """Keep an unacknowledged paid response for this exact saved source."""
    from editorial_generation_runtime import EditorialCheckpointError
    from storage_backend import is_storage_uri, storage_uri, uri_to_path
    if not isinstance(exc, EditorialCheckpointError):
        return False
    def canonical(value):
        return storage_uri(uri_to_path(value) if is_storage_uri(value) else value)
    try:
        if canonical(reference) != canonical(exc.product_ref):
            return False
    except Exception:
        return False
    copies = st.session_state.setdefault("editorial_received_responses", {})
    copies[(canonical(reference), exc.attempt_token)] = deepcopy(exc.response)
    return True


def render_editorial_recovery(reference: str, *, key_prefix: str, on_change=None) -> dict | None:
    """Recovery only records evidence; generation remains a separate action."""
    from editorial_generation_runtime import (
        generation_status, recover_generation, reconcile_attempt,
        adopt_legacy_interruption,
    )
    from storage_backend import is_storage_uri, storage_uri, uri_to_path
    try:
        from editorial_products import load_product
        canonical = storage_uri(uri_to_path(reference) if is_storage_uri(reference) else reference)
        execution = generation_status(canonical)
        source = load_product(canonical)
        meta = source["editorial_product"]
        if (meta.get("execution") or {}).get("revision", 0) != execution["revision"]:
            raise RuntimeError("O estado salvo mudou durante a leitura.")
    except Exception:
        st.error("Não foi possível conferir as tentativas salvas. Reabra o projeto quando o armazenamento responder; nenhuma geração foi iniciada.")
        return None
    claim = execution.get("claim") or {}
    active = claim.get("owner_active") is True
    pending = [attempt for attempt in execution["attempts"] if attempt["state"] in {"running", "uncertain", "raw"}]
    uncertain = any(attempt["state"] in {"running", "uncertain"} for attempt in pending)
    legacy = execution.get("status") == "legacy_needs_review" or bool(execution.get("legacy_review_required"))
    draft = meta.get("draft") or {}
    remaining = len(meta["unit_plan"]) - len(draft.get("units", [])) if draft or not meta.get("units") else 0
    received = {attempt["index"] for attempt in pending if attempt["state"] == "raw"
                and attempt.get("draft_id") == draft.get("id") and len(draft.get("units", [])) <= attempt["index"] < len(meta["unit_plan"])}
    paid_pending = max(0, remaining - len(received))
    labels = {
        "ready": "Pronto para gerar as unidades pendentes.",
        "running": "Há uma execução em andamento. Aguarde antes de iniciar outra.",
        "needs_reconciliation": "Uma chamada precisa ser conferida no provedor antes de continuar.",
        "save_failed": "O rascunho foi preservado. Confira os resultados antes de retomar.",
        "completed": "Conteúdo gerado. Revise e aprove a versão no Studio.",
        "legacy_needs_review": "Este rascunho antigo precisa de conferência antes da retomada.",
    }
    st.info(labels.get(execution.get("status"), "Confira o estado salvo antes de continuar."))
    if st.button("Atualizar estado da geração", key=f"{key_prefix}_refresh"):
        st.rerun()
    if any(attempt["state"] == "raw" for attempt in pending) and not active:
        st.caption("Uma resposta já foi recebida. A retomada reutiliza essa resposta; somente unidades ainda não recebidas podem exigir novas chamadas.")

    def apply_change(callback):
        try:
            updated = callback()
        except Exception as exc:
            st.error(str(exc))
            return
        if on_change is not None:
            try:
                on_change(updated)
            except Exception:
                st.warning("A conferência foi salva. Reabra o projeto para atualizar a tela.")
                return
        st.rerun()

    if active or legacy:
        marker = claim.get("token") if active else str(execution["revision"])
        with st.expander("Conferir uma execução interrompida"):
            st.caption("Aguarde uma geração que ainda esteja trabalhando. Use esta ação somente após confirmar o encerramento de todas as execuções deste produto; ela não confirma o resultado da chamada no provedor.")
            note = st.text_area("Como foi confirmado o encerramento da execução?", key=f"{key_prefix}_shutdown_note_{marker}")
            confirmed = st.checkbox("Confirmei que a execução foi encerrada", key=f"{key_prefix}_shutdown_confirm_{marker}")
            if st.button("Registrar encerramento e conferir tentativas", disabled=not confirmed or not note.strip(), key=f"{key_prefix}_shutdown_{marker}"):
                if active:
                    apply_change(lambda: recover_generation(canonical, execution_token=claim["token"], confirmed=confirmed, shutdown_note=note))
                else:
                    apply_change(lambda: adopt_legacy_interruption(canonical, confirmed=confirmed, shutdown_note=note))

    copies = st.session_state.get("editorial_received_responses", {})
    for attempt in pending:
        token = attempt["token"]
        recovered = copies.get((canonical, token))
        if recovered is not None:
            st.warning("A resposta recebida também está preservada nesta sessão. Baixe uma cópia antes de fechar a página.")
            st.download_button("Baixar resposta recebida", json.dumps(recovered, ensure_ascii=False, indent=2),
                file_name="resposta-editorial-recuperada.json", mime="application/json", key=f"{key_prefix}_received_{token}")
        if active or attempt["state"] == "running":
            continue
        with st.expander(f"Conferir chamada da unidade {attempt['index'] + 1}"):
            outcomes = {"not_sent": "O provedor confirmou que a chamada não foi enviada", "failed": "O provedor confirmou que a chamada falhou", "succeeded": "O provedor retornou uma resposta que quero recuperar"}
            outcome = st.selectbox("Resultado conferido no provedor", ["", *outcomes], format_func=lambda value: outcomes.get(value, "Selecione o resultado conferido"), key=f"{key_prefix}_outcome_{token}")
            note = st.text_area("Evidência ou justificativa da conferência", key=f"{key_prefix}_evidence_{token}")
            actual = st.text_input("Custo confirmado no provedor em US$ (opcional)", key=f"{key_prefix}_cost_{token}")
            response_text = ""
            if outcome == "succeeded" and attempt["state"] != "raw" and recovered is None:
                response_text = st.text_area("Resposta recuperada do provedor (JSON)", key=f"{key_prefix}_response_{token}")
            confirmed = st.checkbox("Conferi este resultado no provedor e autorizo registrar a conferência", key=f"{key_prefix}_reconcile_confirm_{token}")
            if st.button("Salvar conferência desta chamada", disabled=not outcome or not note.strip() or not confirmed,
                         key=f"{key_prefix}_reconcile_{token}"):
                def reconcile():
                    cost = float(actual.replace(",", ".")) if actual.strip() else None
                    response = recovered
                    if response_text.strip():
                        response = json.loads(response_text)
                    return reconcile_attempt(canonical, attempt_token=token, provider_outcome=outcome,
                        note=note, confirmed=confirmed, recovered_response=response, actual_usd=cost)
                apply_change(reconcile)
    return {"execution": execution, "can_generate": not active and not uncertain and not legacy,
            "can_edit": not active and not pending and not legacy,
            "paid_pending": paid_pending,
            "needs_resume": execution.get("status") in {"save_failed", "needs_reconciliation"} or bool(pending)}


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
    if run["project_type"] not in SPECIALIZED_TYPES:
        st.write("Gere e revise o conteúdo no Studio deste projeto.")
    if run["project_type"] in SPECIALIZED_TYPES:
        recovery = render_editorial_recovery(run["source_ref"], key_prefix=f"run_recovery_{run_id}",
                                            on_change=lambda _product: sync_source(run_id))
        needs_provider = not recovery or recovery["paid_pending"] > 0
        confirmation = "Confirmo gerar o conteúdo com IA e consumir os créditos do provedor configurado" if needs_provider else "Confirmo recuperar as respostas recebidas sem nova chamada à IA"
        confirmed = st.checkbox(confirmation, key=f"run_paid_{run_id}_{'new' if needs_provider else 'received'}")
        consent = st.checkbox("Confirmo ter autorização para enviar os dados deste relato real ao provedor de IA", key=f"run_consent_{run_id}") if needs_provider and run["route_plan"].get("origin")=="real_experience" else False
        needs_resume = state in {"running", "interrupted", "save_failed", "needs_reconciliation"} or bool(recovery and recovery["needs_resume"])
        resume = st.checkbox("Revisei o rascunho e confirmo retomar a execução interrompida", key=f"run_resume_{run_id}") if needs_resume else False
        completed = bool(recovery and recovery["execution"].get("status") == "completed")
        if st.button("Gerar unidades pendentes", disabled=not confirmed or not recovery or not recovery["can_generate"] or completed or (needs_resume and not resume) or (needs_provider and run["route_plan"].get("origin")=="real_experience" and not consent), key=f"run_generate_{run_id}"):
            try:
                with st.spinner("Gerando e salvando cada unidade..."):
                    execute_editorial_generation(run_id, confirmed=confirmed, resume_confirmed=resume, consent_confirmed=consent)
                st.rerun()
            except Exception as exc:
                preserve_editorial_response(exc, run["source_ref"])
                st.error(str(exc))
                st.info("Unidades recebidas são preservadas. Atualize a tela e confira qualquer chamada pendente antes de retomar.")
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

"""Explicit visual actions on the author's approved orchestration plan."""
from __future__ import annotations

import json

import streamlit as st
import storage_backend as storage
from editorial_dispatch import content_fingerprint, validate_visual_source
from orchestrator_visual import load_visual_plan, load_world_master, link_location_approval
from storage_backend import materializar
from visual_execution import (
    VisualExecutionError, estimate_visual_operation, generate_world_candidates,
    select_world_candidate, generate_scene_options, select_scene_option,
    generate_selected_scene, generate_scene_batch, list_visual_operations,
    element_lock_capability, apply_scene_asset,
)


def _show_asset(asset: dict) -> None:
    uri = asset.get("storage_uri") or asset.get("path") or asset.get("caminho_arquivo")
    if uri:
        try:
            st.image(materializar(uri), use_container_width=True)
        except Exception:
            st.warning("A imagem está registrada, mas não pôde ser aberta agora.")


def _action(callback) -> None:
    st.session_state["visual_data_consent_epoch"] = st.session_state.get("visual_data_consent_epoch", 0) + 1
    try:
        with st.spinner("Executando e salvando os resultados..."):
            callback()
        st.rerun()
    except VisualExecutionError as exc:
        st.error(str(exc))
        st.info("Os resultados concluídos foram registrados. Uma chamada sem resposta não será repetida automaticamente.")
    except Exception as exc:
        st.error(str(exc))


def _story_source(plan: dict) -> dict | None:
    """Read the saved source, never a same-title book or an open Studio state."""
    reference = str(plan.get("source_ref") or "")
    if not reference or not plan.get("source_fingerprint"):
        return None
    if plan.get("editorial_run_id"):
        validate_visual_source(plan)
    canonical = reference if storage.is_storage_uri(reference) else storage.storage_uri(reference)
    path = storage.uri_to_path(canonical)
    source = json.loads(storage.BACKEND.get_bytes(path).decode("utf-8"))
    if not isinstance(source, dict) or content_fingerprint(source) != plan["source_fingerprint"]:
        raise PermissionError("O conteúdo salvo mudou. Atualize o projeto no Orquestrador e aprove o novo pré-voo antes de gerar ou escolher ilustrações.")
    book_id = source.get("book_id") or source.get("project_id") or source.get("id")
    if plan.get("source_book_id") and book_id != plan["source_book_id"]:
        raise PermissionError("A identidade do livro de origem mudou. Reabra o projeto salvo antes de continuar.")
    logical_path = path.split("/", 2)[2] if path.startswith("tenants/") else path
    return source if logical_path.startswith("livros/") and logical_path.endswith(".json") else None


def _apply_to_book(plan_id: str, scene_key: str, asset_id: str, number: int) -> None:
    result = apply_scene_asset(plan_id, scene_key, asset_id, scene_number=number, confirmed=True)
    # Refresh an already-open copy only when it belongs to this exact source.
    # A different Studio project remains open and is never a save payload.
    current = st.session_state.get("state")
    if isinstance(current, dict):
        reference = str(current.get("storage_path") or current.get("source_ref") or "")
        saved = result["state"]
        same_identity = (current.get("book_id") or current.get("project_id") or current.get("id")) == (saved.get("book_id") or saved.get("project_id") or saved.get("id"))
        try:
            canonical = reference if storage.is_storage_uri(reference) else storage.storage_uri(reference) if reference else ""
            same_path = bool(canonical) and storage.uri_to_path(canonical) == storage.uri_to_path(result["storage_path"])
        except (storage.StorageError, ValueError, PermissionError):
            same_path = False
        if same_identity and same_path:
            st.session_state["state"] = storage.materializar_assets_em_objeto(saved)
    st.session_state[f"visual_applied_{plan_id}"] = f"Ilustração salva e aprovada na cena {number} do livro vinculado. A imagem anterior permanece no histórico."


def _visual_data_consent(plan: dict, action_key: str) -> bool:
    from emotional_visual_binding import source_for_plan
    source = source_for_plan(plan)
    marker = (source.get("comic_product") or {}).get("source_data") or {}
    private = bool(source.get("real_experience") or source.get("real_life_brief") or source.get("uses_personal_data") or marker.get("uses_personal_data"))
    if not private:
        return False
    epoch = st.session_state.get("visual_data_consent_epoch", 0)
    return st.checkbox("Autorizo enviar os dados pessoais desta obra à IA somente para esta ação", key=f"visual_data_consent_{action_key}_{epoch}")


def render_visual_execution(plan_id: str) -> None:
    plan = load_visual_plan(plan_id)
    if not plan:
        return
    st.subheader("Geração visual com aprovação")
    render_emotional_review(plan_id)
    try:
        source = _story_source(plan)
    except PermissionError as exc:
        st.warning(str(exc))
        return
    except Exception:
        st.error("Não foi possível conferir o livro salvo. Reabra o projeto quando o armazenamento estiver disponível; nenhuma geração foi iniciada.")
        return
    if notice := st.session_state.pop(f"visual_applied_{plan_id}", None):
        st.success(notice)
    scene_rows = {}
    duplicate_numbers = set()
    for row in (source or {}).get("cenas_texto") or []:
        try:
            number = int(row["numero"])
        except (ValueError, TypeError, KeyError):
            continue
        if number in scene_rows:
            duplicate_numbers.add(number)
        scene_rows[number] = row
    scene_rows = {number: row for number, row in scene_rows.items() if number not in duplicate_numbers}
    if source is None:
        if plan.get("source_ref") and plan.get("source_fingerprint"):
            st.info("As candidatas deste tipo de projeto ficam na galeria. A aplicação direta pelo número da cena está disponível para Story Books vinculados.")
        else:
            st.info("Este pré-voo mantém as candidatas na galeria. Para usar uma imagem no livro, abra o projeto salvo no Orquestrador e crie o pré-voo vinculado a ele.")
    elif not scene_rows:
        st.warning("O livro vinculado ainda não tem cenas com números únicos. Corrija e aprove o conteúdo salvo antes de aplicar uma ilustração; as candidatas permanecem na galeria.")
    else:
        st.caption(f"Livro vinculado: {source.get('titulo') or plan.get('title')} · {source.get('colecao') or 'Sem coleção'}. A escolha abaixo altera somente este livro salvo e preserva os Masters.")
    st.caption("O projeto salva cada resultado. O orçamento registra estimativas e reservas; isso não substitui a cobrança informada pelo provedor.")
    cols = st.columns(3)
    cols[0].metric("Custo estimado concluído (US$)", f"{float(plan.get('budget_spent_usd') or 0):.2f}")
    cols[1].metric("Reservas (US$)", f"{float(plan.get('budget_reserved_usd') or 0):.2f}")
    cols[2].metric("Limite (US$)", "Sem limite" if plan.get("budget_limit_usd") is None else f"{float(plan['budget_limit_usd']):.2f}")
    with st.expander("Candidatas A/B/C dos cenários"):
        approvals = (plan.get("approvals") or {}).get("locations") or {}
        drafts = plan.get("location_world_drafts") or {}
        for loc in plan.get("locations") or []:
            key = str(loc.get("id") or loc.get("name") or "")
            world_id = (approvals.get(key) or {}).get("world_master_id") or drafts.get(key)
            if not world_id:
                st.caption(f"{loc.get('name') or key}: salve a descrição do cenário primeiro.")
                continue
            world = load_world_master(world_id)
            st.markdown(f"**{world.get('name') or key}**")
            try:
                estimate = estimate_visual_operation(plan_id, "imagem", 3)
                st.caption(f"Estimativa A/B/C: US$ {float(estimate.get('estimated_usd') or estimate.get('total_usd') or 0):.2f}. Conteúdo e estilo precisam estar aprovados.")
            except Exception as exc:
                st.caption(str(exc))
            world_consent = _visual_data_consent(plan, f"world_{plan_id}_{key}")
            confirmed = st.checkbox("Confirmo gerar três candidatas e consumir os créditos necessários", key=f"world_paid_{plan_id}_{key}")
            if st.button("Gerar candidatas do cenário", disabled=not confirmed, key=f"world_abc_{plan_id}_{key}"):
                _action(lambda: generate_world_candidates(plan_id, world_id, confirmed=confirmed, consent_confirmed=world_consent))
            candidates = world.get("candidates") or []
            for col, candidate in zip(st.columns(max(1, min(3, len(candidates)))), candidates[:3]):
                with col:
                    _show_asset(candidate)
                    st.caption(candidate.get("label", "Candidata"))
                    if st.button("Escolher e aprovar este cenário", key=f"world_choose_{world_id}_{candidate['asset_id']}"):
                        def choose():
                            select_world_candidate(world_id, candidate["asset_id"])
                            link_location_approval(load_visual_plan(plan_id), key, world_id)
                        _action(choose)
    with st.expander("Diretor de Cena — propostas A/B/C", expanded=True):
        key = st.text_input("Identificador da cena", value="cena_1", key=f"scene_key_{plan_id}")
        binding_rows = (plan.get("emotional_binding") or {}).get("scenes") or []
        source_number = st.selectbox("Cena do mapa emocional para esta proposta", [row["numero"] for row in binding_rows], index=None, key=f"scene_emotional_number_{plan_id}", placeholder="Selecione a cena exata da obra") if binding_rows else None
        excerpt = st.text_area("Trecho e direção desta cena", key=f"scene_excerpt_{plan_id}", help="Vincule esta proposta à cena exata do mapa aprovado. A direção emocional canônica prevalece sobre sugestões livres.")
        options_consent = _visual_data_consent(plan, f"options_{plan_id}")
        confirm_text = st.checkbox("Confirmo gerar as três propostas de direção com IA", key=f"scene_text_paid_{plan_id}")
        if st.button("Preparar opções A/B/C", disabled=not key.strip() or not excerpt.strip() or not confirm_text or source_number is None, key=f"scene_options_{plan_id}"):
            _action(lambda: generate_scene_options(plan_id, key.strip(), excerpt.strip(), confirmed=confirm_text, source_scene_number=source_number, consent_confirmed=options_consent))
        scenes = plan.get("scene_execution") or {}
        for scene_key, record in scenes.items():
            st.markdown(f"**{scene_key}**")
            options = record.get("options") or []
            for option in options:
                option_id = str(option.get("id") or option.get("option_id") or "")
                st.write(option.get("titulo") or option.get("title") or option.get("label") or option_id)
                details = {"Cenário": option.get("cenario"), "Ação": option.get("acao"), "Poses": option.get("poses"), "Emoção": option.get("emocao"), "Cores": option.get("psicologia_cores"), "Luz": option.get("iluminacao"), "Câmera": option.get("camera"), "Por que funciona": option.get("por_que_funciona")}
                for label, value in details.items():
                    if value:
                        st.write(f"{label}: {value}")
                description = option.get("description") or option.get("prompt") or option.get("scene_prompt")
                if description:
                    st.write(description)
                if st.button("Escolher esta direção", key=f"scene_select_{plan_id}_{scene_key}_{option_id}"):
                    _action(lambda: select_scene_option(plan_id, scene_key, option_id))
            selected = ((plan.get("approvals") or {}).get("scene_options") or {}).get(scene_key)
            if selected:
                image_consent = _visual_data_consent(plan, f"image_{plan_id}_{scene_key}")
                confirmed = st.checkbox("Confirmo gerar a ilustração da direção escolhida", key=f"scene_image_paid_{plan_id}_{scene_key}")
                if st.button("Gerar ilustração", disabled=not confirmed, key=f"scene_image_{plan_id}_{scene_key}"):
                    _action(lambda: generate_selected_scene(plan_id, scene_key, confirmed=confirmed, consent_confirmed=image_consent))
            assets = record.get("assets") or []
            scene_number = None
            if assets and scene_rows:
                scene_number = st.selectbox(
                    "Cena do livro que receberá a ilustração", list(scene_rows), index=None,
                    format_func=lambda value: f"Cena {value} · {str(scene_rows[value].get('texto') or '')[:110]}",
                    placeholder="Escolha a cena pelo número e pelo texto",
                    key=f"scene_apply_number_{plan_id}_{scene_key}_{plan.get('source_fingerprint')}",
                )
            for asset in assets:
                _show_asset(asset)
                if record.get("selected_asset_id") == asset.get("asset_id"):
                    st.success(f"Ilustração escolhida para a cena {record.get('book_scene_number')} do livro salvo.")
                if scene_rows:
                    aid = asset["asset_id"]
                    confirmed = st.checkbox(
                        "Confirmo usar esta ilustração na cena escolhida do livro vinculado",
                        disabled=scene_number is None,
                        key=f"scene_apply_confirm_{plan_id}_{scene_key}_{aid}_{scene_number}",
                    )
                    if st.button("Usar esta ilustração no livro", disabled=scene_number is None or not confirmed,
                                 key=f"scene_apply_{plan_id}_{scene_key}_{aid}"):
                        _action(lambda: _apply_to_book(plan_id, scene_key, aid, scene_number))
        selected_keys = list(((plan.get("approvals") or {}).get("scene_options") or {}))
        if selected_keys:
            batch = st.multiselect("Cenas escolhidas para o lote", selected_keys, key=f"scene_batch_keys_{plan_id}")
            batch_consent = _visual_data_consent(plan, f"batch_{plan_id}")
            confirmed = st.checkbox("Confirmo gerar o lote selecionado dentro do orçamento do projeto", key=f"scene_batch_paid_{plan_id}")
            if st.button("Gerar lote de cenas escolhidas", disabled=not batch or not confirmed, key=f"scene_batch_{plan_id}"):
                _action(lambda: generate_scene_batch(plan_id, batch, confirmed=confirmed, consent_confirmed=batch_consent))
    with st.expander("Histórico de execuções e reservas"):
        operations = list_visual_operations(plan_id)
        st.dataframe([{"operação": row.get("kind"), "status": row.get("status"), "resultados": len(row.get("results") or [])} for row in operations], use_container_width=True, hide_index=True)
    capability = element_lock_capability()
    st.caption(capability.get("notice") or "Edição exata por máscara ainda depende de um provedor compatível; o contrato de Element Lock não garante preservação de pixels.")


def render_emotional_review(plan_id: str) -> None:
    """A local preparation/review action, separate from any paid AI action."""
    from copy import deepcopy
    from emotional_color_director import PALETAS_PRESET, direcao_emocional
    from emotional_visual_binding import prepare_emotional_binding, approve_emotional_binding, require_emotional_binding, source_for_plan
    from orchestrator_visual import save_visual_plan
    plan = load_visual_plan(plan_id)
    with st.expander("Psicologia das cores e emoções — mapa obrigatório por cena", expanded=not bool((plan.get("emotional_binding") or {}).get("approval"))):
        st.caption("Esta é uma direção editorial da obra. Revise emoções, intensidade, transições e instruções antes da IA; as cores e os detalhes dos olhos dos Masters são preservados pelas referências e exigem revisão visual.")
        try:
            source = source_for_plan(plan)
            prepared = prepare_emotional_binding(plan, source)
        except Exception as exc:
            st.warning(str(exc))
            return
        existing = plan.get("emotional_binding") or {}
        same_source = existing.get("source_signature") == prepared["emotional_binding"]["source_signature"]
        rows = deepcopy(existing.get("scenes") if same_source and existing.get("scenes") else prepared["emotional_binding"]["scenes"])
        stamp = prepared["emotional_binding"]["source_signature"][:16]
        edits = []
        for item in rows:
            number = item["numero"]
            d = item.get("direcao") or {}
            prefix = f"emotion_review_{plan_id}_{stamp}_{number}"
            st.markdown(f"**Cena {number}**")
            emotion = st.text_input("Emoção principal", value=str(d.get("emocao_narrativa") or "esperanca"), key=prefix + "_emotion")
            sub = st.text_input("Subemoção", value=str(d.get("subemocao") or ""), key=prefix + "_sub")
            intensity = st.slider("Intensidade emocional", 1, 5, int(d.get("intensidade") or 3), key=prefix + "_intensity")
            transition = st.text_input("Transição emocional", value=str(d.get("transicao_emocional") or ""), key=prefix + "_transition")
            author = st.text_input("Instrução emocional da autora", value=str(item.get("instrucao_autora") or ""), key=prefix + "_author")
            presets = list(PALETAS_PRESET)
            preset = st.selectbox("Paleta editorial", presets, index=presets.index(d.get("preset")) if d.get("preset") in presets else 0, key=prefix + "_preset")
            direction = direcao_emocional(emotion, preset, intensity, sub, transition)
            st.caption(f"Base: {direction['cor_principal']} · luz: {direction['luz_emocional']} · atmosfera: {direction['atmosfera']}")
            item.update(direcao=direction, instrucao_autora=author)
            edits.append(item)
        reviewer = st.text_input("Responsável pela revisão emocional", key=f"emotion_reviewer_{plan_id}_{stamp}")
        reviewed = st.checkbox("Revisei a direção emocional de todas as cenas e a preservação dos Masters", key=f"emotion_reviewed_{plan_id}_{stamp}")
        if st.button("Aprovar e salvar este mapa emocional", disabled=not reviewed or not reviewer.strip(), key=f"emotion_approve_{plan_id}_{stamp}"):
            _action(lambda: save_visual_plan(approve_emotional_binding(load_visual_plan(plan_id), edits, reviewed=reviewed, reviewer=reviewer)))
        try:
            require_emotional_binding(plan)
            st.success("Mapa emocional aprovado e vinculado à versão exata da obra e do estilo.")
        except Exception as exc:
            st.info(str(exc))

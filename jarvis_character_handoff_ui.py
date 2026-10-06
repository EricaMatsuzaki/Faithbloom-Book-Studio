"""UI do Character Universe para pedidos recebidos do Jarvis.

Fluxo principal: a autora informa nome + colecao e envia imagens. O Jarvis analisa,
prepara Character Master, Reference Pack, Color Master e DNA visual; a autora faz
uma unica aprovacao final. O fluxo manual continua disponivel como fallback.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from armazenamento import listar_colecoes
from character_universe import (
    buscar_personagens_por_nome,
    criar_personagem_oficial,
    listar_personagens_oficiais,
    mover_personagem_para_colecao,
)
from jarvis_character_auto_setup import (
    execute_auto_setup,
    infer_character_context,
    prepare_auto_setup,
)
from jarvis_handoff_inbox import capture_legacy_handoff, list_handoffs, update_handoff
from visual_master_manager import register_upload


_COLLECTION_PLACEHOLDER = "— Selecione a coleção de destino —"


def _image_files(package: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in package.get("files") or [] if str(f.get("kind") or "") == "image" and f.get("data")]


def _find_character_id(collection: str, name: str) -> str:
    wanted = (name or "").strip().casefold()
    if not wanted or not collection:
        return ""
    for item in listar_personagens_oficiais(collection, incluir_arquivados=False):
        if str(item.get("nome") or "").strip().casefold() == wanted:
            return str(item.get("id") or "")
    return ""


def _known_collections(current_collection: str = "") -> list[str]:
    values = {str(x).strip() for x in listar_colecoes() if str(x).strip()}
    values.update(
        str(item.get("colecao") or "").strip()
        for item in listar_personagens_oficiais(incluir_arquivados=True)
        if str(item.get("colecao") or "").strip()
    )
    if str(current_collection or "").strip():
        values.add(str(current_collection).strip())
    return sorted(values, key=str.casefold)


def _attach_images(character_id: str, files: list[dict[str, Any]]) -> int:
    count = 0
    for file in files:
        register_upload(
            character_id,
            str(file.get("name") or "referencia.png"),
            bytes(file.get("data") or b""),
            "outra",
        )
        count += 1
    return count


def _render_collection_correction_tool(current_collection: str) -> None:
    """Corrige cadastros antigos colocados na colecao errada sem recriar."""
    characters = listar_personagens_oficiais(incluir_arquivados=False)
    if not characters:
        return
    with st.expander("🧭 Corrigir coleção de um personagem existente", expanded=False):
        st.caption(
            "Use apenas quando um personagem foi cadastrado na coleção errada. "
            "O mesmo Character Master é movido; DNA, Reference Pack, Masters, assets, versões e histórico são preservados."
        )
        by_id = {str(item.get("id") or ""): item for item in characters if item.get("id")}
        selected_id = st.selectbox(
            "Personagem a corrigir",
            [""] + list(by_id),
            format_func=lambda pid: "— Selecione —" if not pid else f"{by_id[pid].get('nome')} · atual: {by_id[pid].get('colecao')}",
            key="character_collection_correction_character",
        )
        if not selected_id:
            return
        selected = by_id[selected_id]
        current = str(selected.get("colecao") or "")
        collections = _known_collections(current_collection)
        destination = st.selectbox(
            "Mover para a coleção correta",
            [_COLLECTION_PLACEHOLDER] + [c for c in collections if c != current],
            key=f"character_collection_correction_target_{selected_id}",
        )
        if destination == _COLLECTION_PLACEHOLDER:
            st.info("Selecione explicitamente a coleção correta. A coleção aberta na tela não será usada automaticamente.")
            return
        collisions = [
            item for item in buscar_personagens_por_nome(str(selected.get("nome") or ""))
            if str(item.get("id") or "") != selected_id and str(item.get("colecao") or "") == destination
        ]
        if collisions:
            st.error(f"Já existe {selected.get('nome')} em {destination}. A movimentação foi bloqueada para evitar duplicidade.")
            return
        st.warning(f"Mover **{selected.get('nome')}** de **{current}** para **{destination}**.")
        confirmed = st.checkbox(
            "Confirmo que esta é a coleção correta e quero mover o mesmo Character Master sem duplicá-lo",
            key=f"confirm_character_collection_move_{selected_id}_{destination}",
        )
        if st.button(
            "🔁 Corrigir coleção do personagem",
            type="primary",
            disabled=not confirmed,
            key=f"move_character_collection_{selected_id}_{destination}",
        ):
            try:
                moved = mover_personagem_para_colecao(
                    selected_id,
                    destination,
                    confirmacao_explicita=True,
                    motivo="correcao_collection_safe_ui",
                )
            except (ValueError, PermissionError, KeyError) as exc:
                st.error(str(exc))
            else:
                st.success(
                    f"{moved.get('nome')} foi movido para {destination}. "
                    "O ID, DNA, referências, Masters, assets, versões e histórico foram preservados."
                )
                st.rerun()


def _render_auto_setup_summary(plan: dict[str, Any]) -> None:
    analysis = plan.get("analysis") or {}
    fields = analysis.get("campos_bloqueados") or {}
    st.success("🤖 Jarvis analisou as imagens e preparou o Character Auto-Setup.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Personagem", str(plan.get("character_name") or "—"))
    c2.metric("Referências", int(plan.get("reference_count") or 0))
    c3.metric("Character Master", "Atualizar" if plan.get("operation") == "update" else "Criar")
    c4.metric("Color Master", "Criar" if plan.get("will_promote_color_master") else "Preservar atual")
    st.caption(f"📚 Coleção confirmada: **{plan.get('target_collection')}**")
    if plan.get("move_from_collection"):
        st.warning(
            f"O mesmo Character Master será movido de **{plan.get('move_from_collection')}** "
            f"para **{plan.get('target_collection')}**, sem criar duplicata."
        )
    if analysis.get("resumo_visual"):
        st.markdown("**DNA visual detectado**")
        st.write(analysis.get("resumo_visual"))
    if fields:
        compact = " · ".join(f"**{key.replace('_', ' ')}:** {value}" for key, value in fields.items())
        st.markdown(compact)
    best = int(plan.get("best_reference_index") or 0) + 1
    reason = str(analysis.get("melhor_referencia_motivo") or "")
    st.caption(f"⭐ Referência sugerida para Color Master: imagem {best}" + (f" · {reason}" if reason else ""))
    st.info(
        "Ao clicar em **Aprovar e salvar tudo**, o Jarvis fará em uma única ação: "
        "Character Master oficial + Reference Pack + Color Master (quando ainda não existir) + DNA visual. "
        "Se já houver DNA ou Color Master oficial, eles não serão sobrescritos silenciosamente."
    )


def _manual_fallback(package: dict[str, Any], package_id: str, name: str, target_collection: str, files: list[dict[str, Any]]) -> None:
    """Mantem as acoes antigas disponiveis caso a analise de IA falhe/nao seja desejada."""
    target_id = _find_character_id(target_collection, name) if target_collection else ""
    same_name_elsewhere = [
        item for item in buscar_personagens_por_nome(name)
        if str(item.get("colecao") or "") != target_collection
    ] if name.strip() and target_collection else []

    if target_id:
        if st.button("➕ Salvar somente como Reference Pack", key=f"manual_attach_{package_id}", disabled=not files):
            added = _attach_images(target_id, files)
            update_handoff(
                st.session_state,
                package_id,
                status="completed",
                character_name=name.strip(),
                target_collection=target_collection,
                character_id=target_id,
                imported_references=added,
                completion_mode="manual_reference_only",
            )
            st.success(f"{added} referência(s) adicionada(s) a {name}.")
            st.rerun()
        return

    if target_collection and same_name_elsewhere:
        if len(same_name_elsewhere) == 1:
            existing = same_name_elsewhere[0]
            existing_id = str(existing.get("id") or "")
            existing_collection = str(existing.get("colecao") or "")
            st.warning(
                f"Encontrei **{name}** em **{existing_collection}**. Para evitar duplicidade, "
                "mova o mesmo Character Master em vez de criar outro."
            )
            confirmed_move = st.checkbox(
                f"Confirmo mover {name} de {existing_collection} para {target_collection}",
                key=f"manual_confirm_move_{package_id}_{existing_id}",
            )
            if st.button(
                "🔁 Mover + salvar referências",
                disabled=not confirmed_move,
                key=f"manual_move_{package_id}_{existing_id}",
            ):
                moved = mover_personagem_para_colecao(
                    existing_id,
                    target_collection,
                    confirmacao_explicita=True,
                    motivo=f"jarvis_handoff_manual:{package_id}",
                )
                added = _attach_images(existing_id, files) if files else 0
                update_handoff(
                    st.session_state,
                    package_id,
                    status="completed",
                    character_name=name.strip(),
                    target_collection=target_collection,
                    character_id=existing_id,
                    imported_references=added,
                    completion_mode="manual_move_reference",
                )
                st.success(f"{moved.get('nome')} movido e {added} referência(s) adicionada(s).")
                st.rerun()
        else:
            locations = ", ".join(sorted({str(x.get('colecao') or '') for x in same_name_elsewhere}))
            st.error(f"Há mais de um personagem chamado {name} em outras coleções ({locations}). Resolva a duplicidade antes de continuar.")
        return

    if target_collection:
        confirmed = st.checkbox(
            "Confirmo criar este Character Master oficial nesta coleção somente com as imagens como referências",
            key=f"manual_confirm_create_{package_id}",
        )
        if st.button(
            "⭐ Criar personagem + importar referências",
            disabled=not (confirmed and name.strip() and files),
            key=f"manual_create_{package_id}",
        ):
            character = criar_personagem_oficial(
                target_collection,
                name.strip(),
                {"descricao_master": "", "campos_bloqueados": {}, "caracteristicas_bloqueadas": ""},
                metadata={
                    "usos_permitidos": ["story", "coloring", "activity", "cover"],
                    "origem": "jarvis_handoff_manual",
                    "handoff_id": package_id,
                },
            )
            character_id = str(character.get("id") or "")
            added = _attach_images(character_id, files)
            update_handoff(
                st.session_state,
                package_id,
                status="completed",
                character_name=name.strip(),
                target_collection=target_collection,
                character_id=character_id,
                imported_references=added,
                completion_mode="manual_create_reference",
            )
            st.success(f"{name} criado em {target_collection} e {added} referência(s) importada(s).")
            st.rerun()


def render_character_handoff_inbox(collection: str) -> None:
    """Auto-Setup primeiro; formulario manual apenas quando nome/colecao estiverem ambiguos."""
    capture_legacy_handoff(st.session_state, route_id="character_reference")
    items = list_handoffs(st.session_state, route_id="character_reference", include_done=False)

    if items:
        st.markdown("### 📥 Pedidos recebidos do Jarvis")
        st.caption(
            "Diga apenas quem é o personagem e a coleção. O Jarvis analisa as imagens, "
            "preenche o DNA e prepara tudo para uma única aprovação final."
        )

        known = _known_collections(collection)
        for package in reversed(items):
            package_id = str(package.get("id") or "")
            status = str(package.get("status") or "received")
            files = _image_files(package)
            inferred = infer_character_context(str(package.get("request") or ""), known)
            inferred_name = str(package.get("character_name") or inferred.get("character_name") or "")
            inferred_collection = str(package.get("target_collection") or inferred.get("target_collection") or "")
            available_collections = list(known)
            if inferred_collection and inferred_collection not in available_collections:
                available_collections.append(inferred_collection)
                available_collections.sort(key=str.casefold)
            collection_options = [_COLLECTION_PLACEHOLDER] + available_collections

            with st.container(border=True):
                st.subheader(f"📦 {inferred_name or 'Pedido de personagem'}")
                st.caption(f"Status: {status} · Origem: Jarvis · ID: {package_id}")
                if package.get("request"):
                    st.markdown("**Pedido original**")
                    st.write(package.get("request"))
                if files:
                    cols = st.columns(min(3, len(files)))
                    for index, file in enumerate(files):
                        with cols[index % len(cols)]:
                            st.image(bytes(file.get("data") or b""), caption=str(file.get("name") or "Imagem"), width="stretch")
                else:
                    st.warning("Este handoff não contém imagens disponíveis nesta sessão.")

                name = st.text_input(
                    "Nome do personagem",
                    value=inferred_name,
                    key=f"jarvis_handoff_name_{package_id}",
                    placeholder="Ex.: Téo ou Manu",
                )
                default_index = collection_options.index(inferred_collection) if inferred_collection in collection_options else 0
                target_collection = st.selectbox(
                    "Coleção do personagem",
                    collection_options,
                    index=default_index,
                    key=f"jarvis_handoff_collection_{package_id}",
                    help="Se o Jarvis reconheceu a coleção na sua frase, ela já aparece selecionada.",
                )
                if target_collection == _COLLECTION_PLACEHOLDER:
                    target_collection = ""
                    st.warning("Não consegui confirmar a coleção pela frase. Escolha somente este campo para continuar.")
                else:
                    update_handoff(
                        st.session_state,
                        package_id,
                        character_name=name.strip(),
                        target_collection=target_collection,
                    )

                plan_key = f"jarvis_character_auto_setup_plan_{package_id}"
                error_key = f"jarvis_character_auto_setup_error_{package_id}"
                inputs_ready = bool(name.strip() and target_collection and files)

                if inputs_ready and plan_key not in st.session_state:
                    try:
                        with st.spinner("Jarvis está analisando as imagens e preenchendo o Character Master…"):
                            st.session_state[plan_key] = prepare_auto_setup(
                                package,
                                character_name=name.strip(),
                                target_collection=target_collection,
                            )
                        st.session_state.pop(error_key, None)
                    except Exception as exc:
                        st.session_state[error_key] = str(exc)

                plan = st.session_state.get(plan_key)
                if plan:
                    _render_auto_setup_summary(plan)
                    if st.button(
                        "✅ Aprovar e salvar tudo",
                        type="primary",
                        key=f"approve_auto_setup_{package_id}",
                    ):
                        try:
                            with st.spinner("Salvando Character Master, referências, Color Master e DNA visual…"):
                                result = execute_auto_setup(plan, confirmed=True)
                        except (ValueError, PermissionError, KeyError, RuntimeError) as exc:
                            st.error(str(exc))
                        else:
                            update_handoff(
                                st.session_state,
                                package_id,
                                status="completed",
                                character_name=result["character_name"],
                                target_collection=result["target_collection"],
                                character_id=result["character_id"],
                                imported_references=result["references_added"],
                                auto_setup_completed=True,
                                color_master_asset_id=result.get("color_master_asset_id", ""),
                                dna_filled=result.get("dna_filled", False),
                            )
                            st.session_state.pop(plan_key, None)
                            st.success(
                                f"Pronto: {result['character_name']} foi organizado em {result['target_collection']}. "
                                f"Character Master + {result['references_added']} referência(s) + DNA visual "
                                + ("+ Color Master oficial." if result.get("color_master_asset_id") else "+ Color Master existente preservado.")
                            )
                            st.rerun()
                elif inputs_ready:
                    error = str(st.session_state.get(error_key) or "")
                    if error:
                        st.warning(f"O Auto-Setup não conseguiu concluir a análise nesta tentativa: {error}")
                    if st.button("🔄 Tentar análise automática novamente", key=f"retry_auto_setup_{package_id}"):
                        st.session_state.pop(error_key, None)
                        st.session_state.pop(plan_key, None)
                        st.rerun()

                if inputs_ready:
                    with st.expander("🛠️ Fluxo manual (somente se necessário)", expanded=False):
                        st.caption("Use este fallback apenas se não quiser ou não conseguir usar a análise automática.")
                        _manual_fallback(package, package_id, name, target_collection, files)

                if st.button("🗄️ Arquivar este pedido da inbox", key=f"archive_handoff_{package_id}"):
                    update_handoff(st.session_state, package_id, status="archived")
                    st.session_state.pop(plan_key, None)
                    st.rerun()

    _render_collection_correction_tool(collection)

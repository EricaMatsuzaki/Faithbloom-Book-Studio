"""UI do Character Universe para pedidos recebidos do Jarvis.

Reutiliza o Character Universe e o Reference Pack existentes. Nenhum anexo vira
Master automaticamente; criação/movimentação de Character Master exige ação
humana explícita. A coleção ativa da tela nunca é assumida silenciosamente como
destino de um handoff.
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
        register_upload(character_id, str(file.get("name") or "referencia.png"), bytes(file.get("data") or b""), "")
        count += 1
    return count


def _render_collection_correction_tool(current_collection: str) -> None:
    """Corrige cadastros antigos colocados na coleção errada sem recriar o personagem."""
    characters = listar_personagens_oficiais(incluir_arquivados=False)
    if not characters:
        return
    with st.expander("🧭 Corrigir coleção de um personagem existente", expanded=False):
        st.caption(
            "Use apenas quando um personagem foi cadastrado na coleção errada. "
            "O mesmo Character Master é movido; DNA, Reference Pack, Masters, assets, versões e histórico são preservados."
        )
        by_id = {str(item.get("id") or ""): item for item in characters if item.get("id")}
        options = [""] + list(by_id)
        selected_id = st.selectbox(
            "Personagem a corrigir",
            options,
            format_func=lambda pid: "— Selecione —" if not pid else f"{by_id[pid].get('nome')} · atual: {by_id[pid].get('colecao')}",
            key="character_collection_correction_character",
        )
        if not selected_id:
            return
        selected = by_id[selected_id]
        current = str(selected.get("colecao") or "")
        collections = _known_collections(current_collection)
        destination_options = [_COLLECTION_PLACEHOLDER] + [c for c in collections if c != current]
        destination = st.selectbox(
            "Mover para a coleção correta",
            destination_options,
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


def render_character_handoff_inbox(collection: str) -> None:
    """Captura handoffs do Jarvis e exige coleção-destino explícita antes de importar."""
    capture_legacy_handoff(st.session_state, route_id="character_reference")
    items = list_handoffs(st.session_state, route_id="character_reference", include_done=False)

    if items:
        st.markdown("### 📥 Pedidos recebidos do Jarvis")
        st.caption(
            "Escolha explicitamente a coleção de destino de cada personagem. "
            "A coleção atualmente aberta é apenas um filtro e nunca será assumida automaticamente."
        )

        collection_options = [_COLLECTION_PLACEHOLDER] + _known_collections(collection)

        for package in reversed(items):
            package_id = str(package.get("id") or "")
            status = str(package.get("status") or "received")
            inferred_name = str(package.get("character_name") or "")
            files = _image_files(package)
            with st.container(border=True):
                title = inferred_name or "Pedido de personagem"
                st.subheader(f"📦 {title}")
                st.caption(f"Status: {status} · Origem: Jarvis · ID: {package_id}")
                if package.get("request"):
                    st.markdown("**Pedido original**")
                    st.write(package.get("request"))
                if files:
                    st.markdown(f"**Referências recebidas ({len(files)})**")
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
                saved_target = str(package.get("target_collection") or "")
                default_index = collection_options.index(saved_target) if saved_target in collection_options else 0
                target_collection = st.selectbox(
                    "Coleção de destino do personagem",
                    collection_options,
                    index=default_index,
                    key=f"jarvis_handoff_collection_{package_id}",
                    help="Obrigatório. Não usamos a última coleção aberta automaticamente.",
                )
                if target_collection == _COLLECTION_PLACEHOLDER:
                    st.warning("Selecione a coleção correta antes de criar ou adicionar referências.")
                    target_collection = ""
                elif target_collection != saved_target:
                    update_handoff(st.session_state, package_id, target_collection=target_collection)

                target_id = _find_character_id(target_collection, name) if target_collection else ""
                same_name_elsewhere = [
                    item for item in buscar_personagens_por_nome(name)
                    if str(item.get("colecao") or "") != target_collection
                ] if name.strip() and target_collection else []

                if target_id:
                    st.info(
                        f"Encontrei **{name}** em **{target_collection}**. "
                        "Posso adicionar estas imagens ao Reference Pack sem alterar o Master atual."
                    )
                    if st.button(
                        "➕ Adicionar referências ao personagem existente",
                        key=f"attach_handoff_{package_id}",
                        disabled=not files,
                    ):
                        added = _attach_images(target_id, files)
                        update_handoff(
                            st.session_state,
                            package_id,
                            status="completed",
                            character_name=name.strip(),
                            target_collection=target_collection,
                            character_id=target_id,
                            imported_references=added,
                        )
                        st.success(f"{added} referência(s) adicionada(s) a {name}. Agora use ‘🛠️ Restaurar / Melhorar’ no personagem abaixo.")
                        st.rerun()
                elif target_collection and same_name_elsewhere:
                    if len(same_name_elsewhere) == 1:
                        existing = same_name_elsewhere[0]
                        existing_id = str(existing.get("id") or "")
                        existing_collection = str(existing.get("colecao") or "")
                        st.warning(
                            f"Encontrei **{name}** já cadastrado em **{existing_collection}**, mas você escolheu **{target_collection}**. "
                            "Para evitar duplicidade, mova o mesmo Character Master em vez de criar outro."
                        )
                        confirmed_move = st.checkbox(
                            f"Confirmo mover {name} de {existing_collection} para {target_collection}",
                            key=f"confirm_move_handoff_{package_id}_{existing_id}",
                        )
                        if st.button(
                            "🔁 Mover personagem existente + continuar",
                            type="primary",
                            disabled=not confirmed_move,
                            key=f"move_handoff_{package_id}_{existing_id}",
                        ):
                            try:
                                moved = mover_personagem_para_colecao(
                                    existing_id,
                                    target_collection,
                                    confirmacao_explicita=True,
                                    motivo=f"jarvis_handoff:{package_id}",
                                )
                                added = _attach_images(existing_id, files) if files else 0
                            except (ValueError, PermissionError, KeyError) as exc:
                                st.error(str(exc))
                            else:
                                update_handoff(
                                    st.session_state,
                                    package_id,
                                    status="completed",
                                    character_name=name.strip(),
                                    target_collection=target_collection,
                                    character_id=existing_id,
                                    imported_references=added,
                                )
                                st.success(
                                    f"{moved.get('nome')} foi movido para {target_collection}. "
                                    f"{added} nova(s) referência(s) foram adicionadas sem criar duplicata."
                                )
                                st.rerun()
                    else:
                        locations = ", ".join(sorted({str(x.get('colecao') or '') for x in same_name_elsewhere}))
                        st.error(
                            f"Há mais de um personagem chamado {name} em outras coleções ({locations}). "
                            "A criação foi bloqueada; corrija a duplicidade antes de continuar."
                        )
                elif target_collection:
                    st.info(
                        f"Ainda não encontrei **{name or 'este personagem'}** em **{target_collection}**. "
                        "Você pode criar o Character Master e importar as referências em uma única ação confirmada."
                    )
                    confirmed = st.checkbox(
                        "Confirmo criar este Character Master oficial nesta coleção, com as imagens apenas como referências",
                        key=f"confirm_create_handoff_{package_id}",
                    )
                    if st.button(
                        "⭐ Criar personagem + importar referências",
                        key=f"create_handoff_{package_id}",
                        type="primary",
                        disabled=not (confirmed and name.strip() and files and target_collection),
                    ):
                        character = criar_personagem_oficial(
                            target_collection,
                            name.strip(),
                            {
                                "descricao_master": "",
                                "campos_bloqueados": {},
                                "caracteristicas_bloqueadas": "",
                            },
                            metadata={
                                "usos_permitidos": ["story", "coloring", "activity", "cover"],
                                "origem": "jarvis_handoff",
                                "handoff_id": package_id,
                                "pedido_original": str(package.get("request") or ""),
                                "colecao_confirmada_no_handoff": True,
                            },
                        )
                        added = _attach_images(str(character.get("id") or ""), files)
                        update_handoff(
                            st.session_state,
                            package_id,
                            status="completed",
                            character_name=name.strip(),
                            target_collection=target_collection,
                            character_id=str(character.get("id") or ""),
                            imported_references=added,
                        )
                        st.success(f"{name} criado em {target_collection} e {added} referência(s) importada(s). Nenhuma imagem virou Master automaticamente.")
                        st.rerun()

                if st.button("🗄️ Arquivar este pedido da inbox", key=f"archive_handoff_{package_id}"):
                    update_handoff(st.session_state, package_id, status="archived")
                    st.rerun()

    _render_collection_correction_tool(collection)

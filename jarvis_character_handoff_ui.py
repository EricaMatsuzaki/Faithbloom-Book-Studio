"""UI do Character Universe para pedidos recebidos do Jarvis.

Reutiliza o Character Universe e o Reference Pack existentes. Nenhum anexo vira
Master automaticamente; criação de Character Master exige ação humana explícita.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from character_universe import criar_personagem_oficial, listar_personagens_oficiais
from jarvis_handoff_inbox import capture_legacy_handoff, list_handoffs, update_handoff
from visual_master_manager import register_upload


def _image_files(package: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in package.get("files") or [] if str(f.get("kind") or "") == "image" and f.get("data")]


def _find_character_id(collection: str, name: str) -> str:
    wanted = (name or "").strip().casefold()
    if not wanted:
        return ""
    for item in listar_personagens_oficiais(collection, incluir_arquivados=False):
        if str(item.get("nome") or "").strip().casefold() == wanted:
            return str(item.get("id") or "")
    return ""


def _attach_images(character_id: str, files: list[dict[str, Any]]) -> int:
    count = 0
    for file in files:
        register_upload(character_id, str(file.get("name") or "referencia.png"), bytes(file.get("data") or b""), "")
        count += 1
    return count


def render_character_handoff_inbox(collection: str) -> None:
    """Captura o handoff legado e mostra uma inbox operacional no destino."""
    capture_legacy_handoff(st.session_state, route_id="character_reference")
    items = list_handoffs(st.session_state, route_id="character_reference", include_done=False)
    if not items:
        return

    st.markdown("### 📥 Pedidos recebidos do Jarvis")
    st.caption("Os anexos permanecem como referências. Nada é promovido a Character Master ou Color Master sem sua confirmação.")

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
            target_id = _find_character_id(collection, name)
            if target_id:
                st.info(f"Encontrei **{name}** nesta coleção. Posso adicionar estas imagens ao Reference Pack sem alterar o Master atual.")
                if st.button("➕ Adicionar referências ao personagem existente", key=f"attach_handoff_{package_id}", disabled=not files):
                    added = _attach_images(target_id, files)
                    update_handoff(
                        st.session_state,
                        package_id,
                        status="completed",
                        character_name=name.strip(),
                        character_id=target_id,
                        imported_references=added,
                    )
                    st.success(f"{added} referência(s) adicionada(s) a {name}. Agora use ‘🛠️ Restaurar / Melhorar’ no personagem abaixo.")
                    st.rerun()
            else:
                st.info("Ainda não encontrei esse nome como personagem oficial nesta coleção. Você pode criar o Character Master e importar as referências em uma única ação confirmada.")
                confirmed = st.checkbox(
                    "Confirmo criar este Character Master oficial com as imagens apenas como referências",
                    key=f"confirm_create_handoff_{package_id}",
                )
                if st.button(
                    "⭐ Criar personagem + importar referências",
                    key=f"create_handoff_{package_id}",
                    type="primary",
                    disabled=not (confirmed and name.strip() and files),
                ):
                    character = criar_personagem_oficial(
                        collection,
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
                        },
                    )
                    added = _attach_images(str(character.get("id") or ""), files)
                    update_handoff(
                        st.session_state,
                        package_id,
                        status="completed",
                        character_name=name.strip(),
                        character_id=str(character.get("id") or ""),
                        imported_references=added,
                    )
                    st.success(f"{name} criado e {added} referência(s) importada(s). Nenhuma imagem virou Master automaticamente.")
                    st.rerun()

            if st.button("🗄️ Arquivar este pedido da inbox", key=f"archive_handoff_{package_id}"):
                update_handoff(st.session_state, package_id, status="archived")
                st.rerun()

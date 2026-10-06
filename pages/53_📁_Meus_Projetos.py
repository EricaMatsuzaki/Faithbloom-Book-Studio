"""Catálogo pesquisável de Story Books e Coloring Books do perfil ativo."""
from __future__ import annotations

import streamlit as st
from estilo import aplicar_estilo, hero
from family_profiles import get_workspace_profile, list_workspace_profiles
from integration_ux import PROJECT_CONTEXT_KEY
from painel_dados import filter_projects, project_status
from painel_projetos import available_projects, searchable_projects, project_path, project_snapshot, project_cover_path, activate_project, open_project

st.set_page_config(page_title="Meus projetos · FaithBloom", page_icon="📁", layout="wide")
aplicar_estilo()
hero("Meus projetos", "Encontre seus livros e continue de onde parou.")

profiles = list_workspace_profiles()
profile_id = str(st.session_state.get("faithbloom_workspace_profile_id") or "")
valid_ids = [profile["id"] for profile in profiles]
if profile_id not in valid_ids:
    profile_id = valid_ids[0] if valid_ids else ""
    st.session_state["faithbloom_workspace_profile_id"] = profile_id
    for key in (PROJECT_CONTEXT_KEY, "state", "state_r", "state_c", "etapa_r", "etapa_c",
                "jarvis_conversation_history", "jarvis_reply", "jarvis_reply_token", "jarvis_audio_path",
                "jarvis_pending_handoff", "jarvis_handoff_package"):
        st.session_state.pop(key, None)
profile = get_workspace_profile(profile_id) if profile_id else None
if profile:
    st.caption(f"Projetos de {profile['display_name']}")
else:
    st.caption("Todos os projetos salvos do estúdio")

st.page_link("pages/00_🤖_Jarvis.py", label="← Voltar ao início")
query = st.text_input("Buscar projetos", placeholder="Título, coleção ou personagem…")
kind_label = st.radio("Tipo de livro", ["Todos", "Histórias", "Colorir"], horizontal=True)
cards = available_projects(profile_id)
if query.strip():
    cards = filter_projects(searchable_projects(cards), query)
if kind_label != "Todos":
    kind = "story" if kind_label == "Histórias" else "coloring"
    cards = [card for card in cards if card["kind"] == kind]

if not cards:
    st.info("Nenhum projeto encontrado. Crie seu primeiro livro ou ajuste a busca.")
    st.page_link("pages/39_✍️_Historia_4_Estilos.py", label="Criar um livro →")
else:
    st.caption(f"{len(cards)} projeto(s)")
    for offset in range(0, len(cards), 4):
        columns = st.columns(4)
        for column, card in zip(columns, cards[offset:offset + 4]):
            path = project_path(card)
            state = project_snapshot(path)
            cover = project_cover_path(state)
            status, _ = project_status(card, state)
            with column:
                with st.container(border=True):
                    if cover:
                        st.image(cover, use_container_width=True)
                    else:
                        st.markdown("### 🖍️" if card["kind"] == "coloring" else "### 📖")
                    st.markdown(f"**{card.get('titulo') or 'Sem título'}**")
                    st.caption(card.get("colecao") or card.get("tema_geral") or "FaithBloom")
                    st.caption(status)
                    if st.button("Selecionar", key=f"fb53_select_{path}", use_container_width=True):
                        try:
                            activate_project(card, profile_id)
                        except Exception:
                            st.error("Não foi possível carregar esse projeto agora.")
                        else:
                            st.success("Projeto ativo atualizado.")
                    if st.button("Abrir →", key=f"fb53_open_{path}", use_container_width=True):
                        try:
                            open_project(card, profile_id)
                        except Exception:
                            st.error("Não foi possível abrir esse projeto agora.")

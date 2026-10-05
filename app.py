"""Painel ilustrado FaithBloom conectado aos projetos e Studios existentes."""
from __future__ import annotations

from html import escape
from pathlib import Path
import uuid

import streamlit as st

from armazenamento import listar_livros, listar_livros_colorir, salvar_na_galeria
from asset_library import get_thumbnail
from estilo import aplicar_estilo
from family_profiles import (
    list_workspace_profiles, get_workspace_profile, visible_project_cards,
    project_links_for_profile,
)
from integration_ux import PROJECT_CONTEXT_KEY
from painel_dados import ACTIONS, filter_projects, filter_actions, suggest_actions, production_stages
from painel_visual import render_banner, render_action_card, render_jarvis_mobile
from storage_backend import BACKEND, materializar, storage_uri
from painel_projetos import project_snapshot, project_path, searchable_project, activate_project, open_project

st.set_page_config(page_title="FaithBloom Book Studio", page_icon="💜", layout="wide", initial_sidebar_state="auto")
aplicar_estilo()


def heading(title: str, subtitle: str, icon: str) -> None:
    st.markdown(
        f'<div class="fb-panel-heading"><span class="fb-panel-icon" aria-hidden="true">{icon}</span>'
        f'<div><h2>{escape(title)}</h2><p>{escape(subtitle)}</p></div></div>',
        unsafe_allow_html=True,
    )


profiles = list_workspace_profiles()
profile_id = st.session_state.get("faithbloom_workspace_profile_id", "")
if not profiles:
    if profile_id:
        st.session_state.pop(PROJECT_CONTEXT_KEY, None)
    profile_id = ""
    st.session_state["faithbloom_workspace_profile_id"] = ""
if profiles and profile_id not in {p["id"] for p in profiles}:
    profile_id = profiles[0]["id"]
    st.session_state["faithbloom_workspace_profile_id"] = profile_id
profile = get_workspace_profile(profile_id) if profile_id else None
display_name = (profile or {}).get("display_name") or "Erica"

with st.container(key="fb_topbar"):
    search_col, gift_col, plan_col, notice_col, user_col = st.columns([4.8, .45, 1.65, .45, 1.25], gap="small")
    with search_col:
        query = st.text_input("Buscar no FaithBloom", placeholder="Buscar projetos, personagens, histórias...",
                              label_visibility="collapsed", icon=":material/search:", key="fb_search")
    with gift_col:
        with st.popover("🎁", help="Inspiração para seu próximo projeto"):
            st.markdown("**Uma nova ideia para hoje**")
            st.write("Transforme uma história em um livro de colorir ou em atividades.")
            st.page_link("pages/3_#L01f58d#Ufe0f_Livros_de_Colorir.py", label="Criar um livro de colorir →")
            st.page_link("pages/23_🧩_Activity_Book_Studio.py", label="Criar atividades →")
    with plan_col:
        with st.popover("👑 Plano Profissional", help="Ferramentas profissionais do seu estúdio"):
            st.markdown("**Seu estúdio editorial**")
            st.write("Histórias, personagens, ilustrações, revisão, traduções e preparação para publicação.")
            st.page_link("pages/29_☁️_Production_Deployment_Real_E2E.py", label="Configurações do estúdio →")
    with notice_col:
        with st.popover("🔔", help="Avisos do estúdio"):
            st.markdown("**Acompanhe suas produções**")
            st.write("Selecione um livro nos projetos recentes para ver suas etapas no painel de produção.")
            st.page_link("pages/12_🏭_Fila_de_Producao.py", label="Ver fila de produção →")
    with user_col:
        if profiles:
            options = [p["id"] for p in profiles]
            selected = st.selectbox("Perfil do workspace", options, index=options.index(profile_id),
                                    format_func=lambda pid: next(p["display_name"] for p in profiles if p["id"] == pid),
                                    label_visibility="collapsed", key="fb_workspace_picker")
            if selected != profile_id:
                st.session_state["faithbloom_workspace_profile_id"] = selected
                st.session_state.pop(PROJECT_CONTEXT_KEY, None)
                for key in ("fb_jarvis_result", "faithbloom_jarvis_idea", "fb_jarvis_welcome", "fb_jarvis_attachments"):
                    st.session_state.pop(key, None)
                st.rerun()
        else:
            st.page_link("pages/34_🏠_Perfis_e_Dashboard.py", label=display_name + " ⌄", icon=":material/account_circle:", use_container_width=True)

render_banner(display_name.split()[0])
if render_jarvis_mobile():
    st.session_state["fb_jarvis_welcome"] = True

# Keep profile filtering from the previous dashboard.
projects = visible_project_cards(
    [{"kind": "story", **p} for p in listar_livros()] + [{"kind": "coloring", **p} for p in listar_livros_colorir()], profile_id,
)
links = project_links_for_profile(profile_id) if profile_id else []
rank = {(link["kind"], link["storage_path"]): i for i, link in enumerate(links)}
projects.sort(key=lambda p: rank.get((p["kind"], project_path(p)), 9999))

if query.strip():
    searchable = [searchable_project(p) for p in projects]
    found_projects, found_actions = filter_projects(searchable, query), filter_actions(query)
    st.caption(f"{len(found_projects)} projeto(s) e {len(found_actions)} ferramenta(s) para “{query.strip()}”")
    if not found_projects and not found_actions:
        st.info("Nenhum resultado. Tente o título, uma coleção ou o nome de um personagem.")
else:
    found_projects, found_actions = projects, ACTIONS

with st.container(key="fb_dashboard_actions"):
    for offset in range(0, len(found_actions), 3):
        cols = st.columns(3, gap="small")
        for col, action in zip(cols, found_actions[offset:offset + 3]):
            with col:
                render_action_card(**action)

with st.container(key="fb_jarvis"):
    heading("Prefere só contar o que precisa?", "Converse ou envie arquivos para o Jarvis e encontre o próximo passo.", "☏")
    if st.session_state.get("fb_jarvis_welcome"):
        st.info("Oi! Conte sua ideia abaixo e eu mostro os atalhos para começar. 💜")
    with st.form("fb_jarvis_form", clear_on_submit=True, border=False):
        attach_col, message_col, send_col = st.columns([.65, 6, 2], gap="small", vertical_alignment="center")
        with attach_col:
            with st.popover("📎", help="Anexar arquivos para a biblioteca"):
                attachments = st.file_uploader("Enviar arquivos", type=["pdf", "png", "jpg", "jpeg", "webp", "txt"],
                                               accept_multiple_files=True, key="fb_jarvis_attachments")
                st.caption("Os arquivos enviados ficam na sua biblioteca de imagens e assets.")
        with message_col:
            message = st.text_input("Mensagem para o Jarvis", placeholder="Escreva sua mensagem ou envie arquivos (PDF, imagens, etc.)...",
                                    label_visibility="collapsed", key="fb_jarvis_message")
        with send_col:
            submitted = st.form_submit_button("✦ Enviar para o Jarvis", type="primary", use_container_width=True)
    if submitted:
        if not message.strip() and not attachments:
            st.info("Conte o que você quer criar ou anexe um arquivo para começar.")
        else:
            saved_names, failed_names = [], []
            for upload in attachments:
                filename = Path(upload.name).name
                path = f"assets/briefings/{uuid.uuid4().hex}/{filename}"
                try:
                    BACKEND.put_bytes(path, upload.getvalue(), upload.type)
                    salvar_na_galeria(storage_uri(path), filename, tipo="referencia", tags=["Jarvis"],
                                      metadata={"origem": "dashboard", "workspace_profile_id": profile_id})
                    saved_names.append(filename)
                except Exception:
                    failed_names.append(filename)
            st.session_state["fb_jarvis_result"] = {
                "message": message.strip(), "saved": saved_names, "failed": failed_names,
                "actions": suggest_actions(message or "imagens"),
            }
            st.session_state["faithbloom_jarvis_idea"] = message.strip()
    result = st.session_state.get("fb_jarvis_result")
    if result:
        if result["message"]:
            st.write(f"💜 Você: {result['message']}")
        if result["saved"]:
            st.success("Arquivos salvos na biblioteca: " + ", ".join(result["saved"]))
        if result["failed"]:
            st.error("Não foi possível salvar: " + ", ".join(result["failed"]) + ". Tente enviar novamente.")
        st.caption("Atalhos sugeridos para seu pedido. Escolha uma ferramenta para continuar.")
        cols = st.columns(len(result["actions"]))
        for col, action in zip(cols, result["actions"]):
            col.page_link(action["route"], label=action["title"] + " →", use_container_width=True)

recent_col, progress_col = st.columns([2.65, 1], gap="small")
with recent_col:
    with st.container(key="fb_recent"):
        title_col, all_col = st.columns([4, 1])
        with title_col:
            heading("Projetos recentes", "Seus livros e histórias em um só lugar.", "▣")
        with all_col:
            st.page_link("pages/38_📁_Meus_Projetos.py", label="Ver todos →", use_container_width=True)
        shown = found_projects if query.strip() else found_projects[:4]
        if not shown:
            st.markdown('<div class="fb-empty-project"><h3>Uma nova história começa aqui 💜</h3><p>Seus projetos salvos vão aparecer neste espaço. Escolha “Criar um livro” para dar o primeiro passo.</p></div>', unsafe_allow_html=True)
            if not query:
                st.page_link("pages/1_#L01f4d6_Criar_do_Zero.py", label="Criar meu primeiro livro →", use_container_width=True)
        for offset in range(0, len(shown), 4):
            cols = st.columns(4, gap="small")
            for col, project in zip(cols, shown[offset:offset + 4]):
                with col:
                    path = project_path(project)
                    snapshot = project_snapshot(path)
                    with st.container(key=f"fb_project_{uuid.uuid5(uuid.NAMESPACE_URL, path).hex}"):
                        linked = next((link for link in links if (link["kind"], link["storage_path"]) == (project["kind"], path)), {})
                        thumb = get_thumbnail(linked["thumbnail_asset_id"], max_px=360) if linked.get("thumbnail_asset_id") else None
                        if not thumb and snapshot.get("capa_ebook"):
                            try:
                                thumb = materializar(snapshot["capa_ebook"])
                            except Exception:
                                thumb = None
                        if thumb:
                            st.image(thumb, use_container_width=True)
                        else:
                            st.markdown(f'<div class="fb-book-placeholder" aria-hidden="true"><span>✦</span><b>{escape(project.get("titulo") or "Meu livro")}</b><span>📖</span></div>', unsafe_allow_html=True)
                        stages = production_stages(snapshot, project["kind"])
                        status = "Publicado" if stages[-1]["status"] == "concluido" else "Pacote pronto" if snapshot.get("pacote_pronto") else "Em andamento" if snapshot.get("cenas_texto") or snapshot.get("paginas") else "Rascunho"
                        st.markdown(f'<span class="fb-project-badge">{escape(status)}</span><h3 class="fb-project-title">{escape(project.get("titulo") or "Sem título")}</h3>', unsafe_allow_html=True)
                        st.caption(project.get("colecao") or project.get("tema_geral") or "Projeto FaithBloom")
                        active = path == str((st.session_state.get(PROJECT_CONTEXT_KEY) or {}).get("storage_path") or "").removeprefix("fb://").strip("/")
                        if st.button("✓ Selecionado" if active else "Selecionar", key=f"fb_select_{path}", use_container_width=True):
                            activate_project(project, profile_id)
                            st.rerun()
                        if st.button("Abrir →", key=f"fb_open_{path}", use_container_width=True):
                            open_project(project, profile_id)

with progress_col:
    with st.container(key="fb_production"):
        heading("Status da produção", "Acompanhe o progresso do seu livro.", "▥")
        context_path = (st.session_state.get(PROJECT_CONTEXT_KEY) or {}).get("storage_path")
        selected_path = str(context_path or "").removeprefix("fb://").strip("/")
        active = next((p for p in projects if project_path(p) == selected_path), projects[0] if projects else None)
        if active:
            st.caption(active.get("titulo") or "Projeto ativo")
            stages = production_stages(project_snapshot(project_path(active)), active["kind"])
        else:
            stages = production_stages({})
        labels = {"concluido": "Concluído", "em_andamento": "Em andamento", "pendente": "Pendente"}
        rows = []
        for i, stage in enumerate(stages, 1):
            status = stage["status"]
            rows.append(f'<li class="fb-stage fb-stage-{status}" title="{escape(stage["detail"], quote=True)}"><span class="fb-stage-number">{i}</span><span class="fb-stage-label">{escape(stage["label"])}</span><span class="fb-stage-status">{labels[status]}</span></li>')
        st.markdown('<ol class="fb-stage-list">' + "".join(rows) + '</ol>', unsafe_allow_html=True)
        if active:
            if st.button("Ver detalhes →", key="fb_progress_details", use_container_width=True):
                open_project(active, profile_id)
        else:
            st.caption("Crie ou selecione um projeto para acompanhar as etapas.")

st.caption("FaithBloom Book Studio · Você sonha. Nós orquestramos. Deus floresce. 💜")

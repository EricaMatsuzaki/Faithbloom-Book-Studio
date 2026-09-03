"""FaithBloom Book Studio 2.0 — dashboard simplificado por perfil/workspace."""
from __future__ import annotations

import streamlit as st

from armazenamento import listar_livros, listar_livros_colorir, listar_colecoes, estatisticas_armazenamento
from estilo import aplicar_estilo, hero, card, section_title, callout
from family_profiles import list_workspace_profiles, get_workspace_profile, visible_project_cards, project_links_for_profile, touch_project
from integration_ux import PROJECT_CONTEXT_KEY, make_project_context
from asset_library import get_thumbnail

st.set_page_config(page_title="FaithBloom Book Studio", page_icon="📖", layout="wide", initial_sidebar_state="expanded")
aplicar_estilo()

# ------------------------- contexto pessoal
profiles = list_workspace_profiles()
active_profile_id = st.session_state.get("faithbloom_workspace_profile_id", "")
if profiles and active_profile_id not in {p.get("id") for p in profiles}:
    active_profile_id = profiles[0]["id"]
    st.session_state["faithbloom_workspace_profile_id"] = active_profile_id
active_profile = get_workspace_profile(active_profile_id) if active_profile_id else None
prefs = (active_profile or {}).get("preferences") or {}
dashboard_mode = prefs.get("dashboard_mode", "simple")

hero(
    "FaithBloom Book Studio",
    (f"Olá, {active_profile.get('display_name')}. Continue seus projetos ou escolha o que deseja fazer hoje."
     if active_profile else
     "Seu estúdio editorial para criar, revisar, ilustrar, localizar e publicar livros com controle humano em cada etapa."),
    "FaithBloom AI · Creative Publishing OS",
)

if profiles:
    c1, c2 = st.columns([4, 1])
    with c1:
        options = [p["id"] for p in profiles]
        selected = st.selectbox(
            "Perfil do workspace",
            options,
            index=options.index(active_profile_id),
            format_func=lambda pid: next(p.get("display_name") for p in profiles if p["id"] == pid),
            help="Personaliza projetos recentes e preferências. Não substitui autenticação/OIDC e não define automaticamente a autoria dos livros.",
        )
        if selected != active_profile_id:
            st.session_state["faithbloom_workspace_profile_id"] = selected
            st.session_state.pop(PROJECT_CONTEXT_KEY, None)
            st.rerun()
    with c2:
        st.page_link("pages/34_🏠_Perfis_e_Dashboard.py", label="⚙️ Perfis", use_container_width=True)
else:
    callout(
        "Configure perfis pessoais",
        "Crie um perfil para você, sua filha, seu marido ou outros usuários. Projetos e preferências podem ficar organizados por pessoa sem mudar a autoria do livro.",
        "👤",
    )
    st.page_link("pages/34_🏠_Perfis_e_Dashboard.py", label="➕ Criar primeiro perfil", use_container_width=True)

# ------------------------- dados observáveis
story_all = [{"kind": "story", **x} for x in listar_livros()]
coloring_all = [{"kind": "coloring", **x} for x in listar_livros_colorir()]
all_cards = story_all + coloring_all
visible = visible_project_cards(all_cards, active_profile_id) if active_profile_id else all_cards
storage = estatisticas_armazenamento()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Meus projetos" if active_profile else "Projetos", len(visible))
m2.metric("Story Books", sum(1 for x in visible if x.get("kind") == "story"))
m3.metric("Coloring Books", sum(1 for x in visible if x.get("kind") == "coloring"))
m4.metric("Storage", "Cloud" if storage.get("persistente_cloud") else "Local")

# ------------------------- continuar / projeto ativo
section_title("Continuar de onde parou", "Selecione um projeto para mantê-lo ativo enquanto navega entre os Studios.", "Workspace")
if active_profile:
    links = project_links_for_profile(active_profile_id)
else:
    links = []

if not visible:
    st.info("Este perfil ainda não possui projetos atribuídos. Crie um projeto novo ou use Perfis & Dashboard para atribuir um projeto existente.")
    a, b = st.columns(2)
    a.page_link("pages/1_#L01f4d6_Criar_do_Zero.py", label="📖 Criar Story Book", use_container_width=True)
    b.page_link("pages/34_🏠_Perfis_e_Dashboard.py", label="📚 Organizar projetos", use_container_width=True)
else:
    link_rank = {(x.get("kind"), x.get("storage_path")): i for i, x in enumerate(links)}
    visible.sort(key=lambda x: link_rank.get((x.get("kind"), str(x.get("storage_path") or x.get("arquivo") or "").replace("fb://", "", 1).strip("/")), 9999))
    options = list(range(len(visible)))
    chosen_i = st.selectbox(
        "Projeto ativo",
        options,
        format_func=lambda i: f"{'📖' if visible[i].get('kind') == 'story' else '🖍️'} {visible[i].get('titulo')} · {visible[i].get('colecao') or visible[i].get('tema_geral') or ''}",
    )
    chosen = visible[chosen_i]
    c1, c2, c3 = st.columns([2, 5, 2])
    with c1:
        key = (chosen.get("kind"), str(chosen.get("storage_path") or chosen.get("arquivo") or "").replace("fb://", "", 1).strip("/"))
        linked = next((x for x in links if (x.get("kind"), x.get("storage_path")) == key), {})
        thumb = get_thumbnail(linked.get("thumbnail_asset_id", ""), max_px=360) if linked.get("thumbnail_asset_id") else None
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            st.markdown("### 📘" if chosen.get("kind") == "story" else "### 🖍️")
            st.caption("Defina uma capa/thumbnail em Perfis & Dashboard.")
    with c2:
        st.markdown(f"### {chosen.get('titulo', '(sem título)')}")
        st.caption(chosen.get("colecao") or chosen.get("tema_geral") or "Projeto FaithBloom")
        if chosen.get("kind") == "story":
            st.write("✅ Pacote pronto" if chosen.get("pacote_pronto") else "📝 Em desenvolvimento")
        else:
            st.write("🖍️ Coloring Book")
        current_ctx = st.session_state.get(PROJECT_CONTEXT_KEY) or {}
        if current_ctx.get("storage_path") == chosen.get("storage_path"):
            st.success("Projeto ativo neste momento.")
    with c3:
        if st.button("📌 Tornar ativo", use_container_width=True, key=f"activate_{chosen_i}"):
            st.session_state[PROJECT_CONTEXT_KEY] = make_project_context(chosen)
            if active_profile_id:
                touch_project(
                    active_profile_id, chosen.get("kind"), chosen.get("storage_path") or chosen.get("arquivo"),
                    title=chosen.get("titulo", ""), collection=chosen.get("colecao") or chosen.get("tema_geral") or "",
                )
            st.success("Projeto ativo atualizado.")
            st.rerun()
        st.page_link("pages/27_🚀_Project_Hub.py", label="🚀 Abrir Project Hub", use_container_width=True)
        st.page_link("pages/31_🖼️_Asset_Library_Media_Manager.py", label="🖼️ Abrir assets", use_container_width=True)

# ------------------------- objetivo principal
section_title("O que você quer fazer?", "Entre pelo objetivo; o FaithBloom leva você ao Studio correto.", "Ações rápidas")
q1, q2, q3 = st.columns(3, gap="medium")
with q1:
    card("Criar um livro", "Comece uma história nova com personagens, emoção e direção editorial.", "pages/1_#L01f4d6_Criar_do_Zero.py", "Criar →", "📖")
    card("Revisar / remasterizar", "Importe um livro existente ou continue uma restauração preservando o original.", "pages/16_🩺_Book_Doctor.py", "Revisar →", "🩺")
    card("Criar Coloring Book", "Crie ou aperfeiçoe páginas de colorir e line art.", "pages/3_#L01f58d#Ufe0f_Livros_de_Colorir.py", "Colorir →", "🖍️")
with q2:
    card("Criar atividades", "Kids, teens, adultos e 60+, com dificuldade, QA e gabarito.", "pages/23_🧩_Activity_Book_Studio.py", "Atividades →", "🧩")
    card("Traduzir e localizar", "Tradução por mercado, onomatopeias e Bible Guard.", "pages/21_Translation_Localization_Studio.py", "Traduzir →", "🌍")
    card("Produzir audiobook", "Vozes, previews, pronúncia, versões e QA de áudio.", "pages/24_🎧_Audiobook_Studio.py", "Audiobook →", "🎧")
with q3:
    card("Gerenciar imagens", "Encontre Masters, referências, capas, line arts, versões e favoritos.", "pages/31_🖼️_Asset_Library_Media_Manager.py", "Biblioteca →", "🖼️")
    card("Revisão final", "Execute o Quality Guardian antes de liberar uma edição.", "pages/25_🛡️_Quality_Guardian.py", "Revisar qualidade →", "🛡️")
    card("Preparar publicação", "Organize formatos, plataformas, pacotes e status de distribuição.", "pages/26_🌐_Publishing_Distribution_Center.py", "Publicar →", "🌐")
    card("Best-seller Readiness", "Revise skills dos agentes, referência bíblica, evidência de mercado e fatores controláveis.", "pages/37_🧠_Agent_Skills_Bestseller_Readiness.py", "Analisar →", "🧠")

# ------------------------- recentes do perfil
section_title("Projetos recentes", "Somente projetos vinculados a este perfil aparecem aqui no modo pessoal.", "Biblioteca")
for row_start in range(0, min(len(visible), 6), 3):
    cols = st.columns(3)
    for col, project in zip(cols, visible[row_start:row_start + 3]):
        with col:
            icon = "📖" if project.get("kind") == "story" else "🖍️"
            st.markdown(f"#### {icon} {project.get('titulo', '(sem título)')}")
            st.caption(project.get("colecao") or project.get("tema_geral") or "")
            if project.get("kind") == "story":
                st.write("✅ Pacote pronto" if project.get("pacote_pronto") else "📝 Em desenvolvimento")

# ------------------------- catálogo avançado
advanced_routes = [
    ("🚀 Project Hub", "pages/27_🚀_Project_Hub.py"),
    ("✍️ Autores & Colaboradores", "pages/32_✍️_Autores_e_Colaboradores.py"),
    ("👤 Perfis & Dashboard", "pages/34_🏠_Perfis_e_Dashboard.py"),
    ("👥 Character Universe", "pages/14_👥_Character_Universe.py"),
    ("🎭 Emotional & Color Director", "pages/17_🎭_Emotional_Color_Director.py"),
    ("🎨 Style DNA Lab", "pages/18_🎨_Style_DNA_Lab.py"),
    ("✨ Restoration Studio", "pages/19_✨_Restoration_Studio.py"),
    ("🖍️ Coloring Book Doctor", "pages/20_🖍️_Coloring_Book_Doctor.py"),
    ("📐 Publishing Platform Engine", "pages/22_📐_Publishing_Platform_Engine.py"),
    ("🧭 Integration & UX Center", "pages/33_🧭_Integration_UX_Center.py"),
    ("📚 Biblioteca Editorial", "pages/15_📚_Biblioteca_Editorial.py"),
    ("🏭 Fila de Produção", "pages/12_🏭_Fila_de_Producao.py"),
    ("🛡️ Custos & Segurança", "pages/11_🛡️_Custos_e_Seguranca.py"),
    ("🧪 Testes End-to-End", "pages/9_🧪_Teste_End_to_End.py"),
    ("🧱 Stable Hardening", "pages/28_🧱_Stable_Release_Hardening.py"),
    ("☁️ Production E2E", "pages/29_☁️_Production_Deployment_Real_E2E.py"),
    ("🏆 Stable Candidate", "pages/30_🏆_Stable_Candidate_Cloud_Launch.py"),
    ("🧪 Real Pilot & Bug Fix", "pages/35_🧪_Real_Pilot_Bug_Fix.py"),
    ("🧠 Agent Skills & Bestseller Readiness", "pages/37_🧠_Agent_Skills_Bestseller_Readiness.py"),
    ("🏆 RC4 Final Pre-Launch", "pages/36_🏆_RC4_Final_PreLaunch.py"),
]

expanded = dashboard_mode == "advanced"
with st.expander("🧰 Ferramentas avançadas", expanded=expanded):
    st.caption("O modo simplificado mantém estas ferramentas acessíveis sem poluir a tela inicial. Altere o modo no perfil do workspace.")
    cols = st.columns(3)
    for i, (label, page) in enumerate(advanced_routes):
        cols[i % 3].page_link(page, label=label, use_container_width=True)

# ------------------------- sistema
if storage.get("persistente_cloud"):
    st.success("☁️ Armazenamento persistente em nuvem ativo.")
else:
    st.warning("💻 Armazenamento local ativo. Para produção no Streamlit Cloud, configure storage persistente antes da versão Stable.")

st.caption("FaithBloom 2.0 · Refinamento 21 · Agent Skills & Bestseller Readiness · perfis de workspace não substituem autenticação real nem autoria editorial.")

"""Lista de projetos salvos, com o mesmo perfil e contexto do dashboard."""
import streamlit as st
from armazenamento import listar_livros, listar_livros_colorir
from estilo import aplicar_estilo, hero
from family_profiles import visible_project_cards, get_workspace_profile
from painel_dados import filter_projects, production_stages
from painel_projetos import project_path, project_snapshot, searchable_project, open_project

st.set_page_config(page_title="Meus projetos | FaithBloom", page_icon="📁", layout="wide")
aplicar_estilo()
profile_id = st.session_state.get("faithbloom_workspace_profile_id", "")
profile = get_workspace_profile(profile_id) if profile_id else None
hero("Meus projetos", "Encontre uma história e continue de onde parou.")
if profile:
    st.caption(f"Perfil: {profile['display_name']}")
projects = visible_project_cards(
    [{"kind": "story", **p} for p in listar_livros()] + [{"kind": "coloring", **p} for p in listar_livros_colorir()], profile_id,
)
query = st.text_input("Buscar projetos", placeholder="Título, coleção ou personagem...", icon=":material/search:")
if query.strip():
    projects = filter_projects([searchable_project(p) for p in projects], query)
if not projects:
    st.info("Nenhum projeto encontrado. Crie um livro ou organize projetos existentes no seu perfil.")
    st.page_link("pages/1_#L01f4d6_Criar_do_Zero.py", label="Criar um livro →")
    st.page_link("pages/34_🏠_Perfis_e_Dashboard.py", label="Organizar meu perfil →")
for project in projects:
    with st.container(border=True):
        title, action = st.columns([5, 1], vertical_alignment="center")
        with title:
            st.subheader(project.get("titulo") or "Sem título")
            st.caption(("Livro de colorir" if project["kind"] == "coloring" else "Livro de história") + " · " + (project.get("colecao") or project.get("tema_geral") or "FaithBloom"))
            stages = production_stages(project_snapshot(project_path(project)), project["kind"])
            completed = sum(stage["status"] == "concluido" for stage in stages)
            st.caption(f"{completed} de {len(stages)} etapas concluídas")
        with action:
            if st.button("Abrir →", key=project_path(project), type="primary", use_container_width=True):
                open_project(project, profile_id)

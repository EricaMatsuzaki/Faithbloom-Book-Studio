"""Navegação compartilhada entre o dashboard e a lista de projetos."""
from __future__ import annotations
import streamlit as st
from family_profiles import touch_project
from integration_ux import PROJECT_CONTEXT_KEY, make_project_context
from storage_backend import BACKEND


@st.cache_data(ttl=20, show_spinner=False)
def project_snapshot(path: str) -> dict:
    value = BACKEND.get_json(path, {})
    return value if isinstance(value, dict) else {}


def project_path(project: dict) -> str:
    return str(project.get("storage_path") or project.get("arquivo") or "").removeprefix("fb://").strip("/")


def searchable_project(project: dict) -> dict:
    state = project_snapshot(project_path(project))
    return {**project, "personagens": state.get("personagens", {}),
            "personagens_nomes": [page.get("personagem_nome", "") for page in state.get("paginas", []) if isinstance(page, dict)]}


def activate_project(project: dict, profile_id: str = "") -> None:
    st.session_state[PROJECT_CONTEXT_KEY] = make_project_context(project)
    if profile_id:
        touch_project(profile_id, project["kind"], project_path(project),
                      title=project.get("titulo", ""), collection=project.get("colecao") or project.get("tema_geral") or "")


def open_project(project: dict, profile_id: str = "") -> None:
    activate_project(project, profile_id)
    if project["kind"] == "coloring":
        from armazenamento import carregar_livro_colorir
        st.session_state["state_c"] = carregar_livro_colorir(project_path(project))
        st.session_state["etapa_c"] = "paginas"
        st.switch_page("pages/3_#L01f58d#Ufe0f_Livros_de_Colorir.py")
    st.switch_page("pages/27_🚀_Project_Hub.py")

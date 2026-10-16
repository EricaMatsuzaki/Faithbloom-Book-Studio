"""Projetos do painel conectados ao storage e aos fluxos canônicos existentes."""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from armazenamento import carregar_livro, carregar_livro_colorir, listar_livros, listar_livros_colorir
from asset_library import get_thumbnail
from family_profiles import project_links_for_profile, touch_project, visible_project_cards
from integration_ux import PROJECT_CONTEXT_KEY, make_project_context
from painel_dados import project_session_updates
from storage_backend import BACKEND, materializar

PROJECT_LIST_PAGE = "pages/53_📁_Meus_Projetos.py"
STORY_PAGE = "pages/2_📚_Retomar_Livro.py"
COLORING_PAGE = "pages/3_🖍️_Livros_de_Colorir.py"


def project_path(project: dict) -> str:
    return str(project.get("storage_path") or project.get("arquivo") or "").removeprefix("fb://").strip("/")


@st.cache_data(ttl=20, show_spinner=False)
def project_snapshot(path: str) -> dict:
    value = BACKEND.get_json(str(path).removeprefix("fb://").strip("/"), {})
    return value if isinstance(value, dict) else {}


def available_projects(profile_id: str = "") -> list[dict]:
    cards = [{"kind": "story", **item} for item in listar_livros()]
    cards += [{"kind": "coloring", **item} for item in listar_livros_colorir()]
    cards = visible_project_cards(cards, profile_id)
    links = project_links_for_profile(profile_id) if profile_id else []
    rank = {(link.get("kind"), link.get("storage_path")): index for index, link in enumerate(links)}
    cards.sort(key=lambda card: rank.get((card["kind"], project_path(card)), 9999))
    return cards


def searchable_projects(projects: list[dict]) -> list[dict]:
    enriched = []
    for project in projects:
        state = project_snapshot(project_path(project))
        pages = state.get("paginas") or []
        names = [str(page.get("personagem_nome") or page.get("nome") or "")
                 for page in pages if isinstance(page, dict)] if isinstance(pages, list) else []
        enriched.append({**project, "personagens": state.get("personagens", {}), "character_names": names,
                         "sinopse_poetica": state.get("sinopse_poetica", "")})
    return enriched


def load_project(project: dict) -> dict:
    if project.get("kind") == "coloring":
        return carregar_livro_colorir(project_path(project))
    if project.get("kind") == "story":
        return carregar_livro(str(project.get("colecao") or ""), project_path(project))
    raise ValueError("Tipo de projeto desconhecido.")


def get_active_project(cards: list[dict]) -> dict | None:
    context = st.session_state.get(PROJECT_CONTEXT_KEY) or {}
    path = str(context.get("storage_path") or "").removeprefix("fb://").strip("/")
    kind = context.get("kind")
    return next((card for card in cards if project_path(card) == path and (not kind or card["kind"] == kind)), None)


def activate_project(project: dict, profile_id: str = "") -> dict:
    previous = st.session_state.get(PROJECT_CONTEXT_KEY) or {}
    changed = (str(previous.get("storage_path") or "").removeprefix("fb://").strip("/") != project_path(project)
               or previous.get("kind") != project.get("kind"))
    coloring = project.get("kind") == "coloring"
    saved_key = "caminho_salvo_c" if coloring else "caminho_salvo_r"
    state_key = "state_c" if coloring else "state_r"
    existing_path = str(st.session_state.get(saved_key) or "").removeprefix("fb://").strip("/")
    existing = st.session_state.get(state_key)
    # Reabrir o mesmo livro preserva edições da sessão ainda não salvas.
    state = existing if not changed and existing_path == project_path(project) and existing else load_project(project)
    updates = project_session_updates(project, state)
    if changed:
        # Estes são previews/pedidos transitórios, nunca os arquivos salvos.
        st.session_state.pop("capa_colorir_phase8", None)
        for key in list(st.session_state):
            if key.startswith("r_"):
                st.session_state.pop(key, None)
    if coloring:
        st.session_state.pop("capa_colorir_phase8", None)
    st.session_state.update(updates)
    context = make_project_context({**project, "storage_path": project_path(project)}, state)
    context["kind"] = project["kind"]
    st.session_state[PROJECT_CONTEXT_KEY] = context
    if profile_id:
        touch_project(profile_id, project["kind"], project_path(project), title=state.get("titulo", ""),
                      collection=state.get("colecao") or state.get("tema_geral") or "")
    return updates["state"]


def open_project(project: dict, profile_id: str = "") -> None:
    activate_project(project, profile_id)
    st.switch_page(COLORING_PAGE if project["kind"] == "coloring" else STORY_PAGE)


def project_cover_path(state: dict, project: dict | None = None, profile_id: str = "") -> str:
    """Prefere a thumbnail configurada no perfil; usa uma capa salva como fallback."""
    candidates = []
    if project and profile_id:
        try:
            linked = next((link for link in project_links_for_profile(profile_id)
                           if link.get("kind") == project.get("kind") and project_path(link) == project_path(project)), {})
            if linked.get("thumbnail_asset_id"):
                candidates.append(get_thumbnail(linked["thumbnail_asset_id"], max_px=360))
        except Exception:
            pass
    candidates.extend(state.get(field) for field in ("arte_capa_frontal", "capa_ebook", "capa_fisica_preview", "imagem_capa", "cover_image"))
    for value in candidates:
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()
        suffix = Path(value.split("?", 1)[0]).suffix.lower()
        if suffix and suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif", ".bmp"}:
            continue
        try:
            path = materializar(value)
        except Exception:
            continue
        if path.startswith(("https://", "http://", "data:image/")) or Path(path).is_file():
            return path
    return ""

"""Refinamento 18 — Perfis pessoais/familiares e preferências do dashboard."""
from __future__ import annotations

import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from armazenamento import listar_livros, listar_livros_colorir
from author_profiles import list_author_profiles, profile_display_name
from asset_library import list_assets
from family_profiles import (
    AGE_PROFILES, create_workspace_profile, list_workspace_profiles,
    update_workspace_profile, assign_project, update_project_sharing,
    set_project_thumbnail, project_link, project_links_for_profile, profile_summary,
)

st.set_page_config(page_title="Perfis & Dashboard", page_icon="🏠", layout="wide")
aplicar_estilo()
hero(
    "🏠 Perfis & Dashboard",
    "Organize o espaço de trabalho de cada pessoa sem confundir usuário, autoria e segurança de conta.",
    "Refinamento 18 · Family Profiles & Simplified Dashboard",
)

callout(
    "Três identidades diferentes",
    "Perfil familiar/workspace personaliza projetos e preferências. Perfil de autoria define quem assina o livro. Autenticação real/OIDC continua sendo a camada de segurança da conta.",
    "🔐",
)

profiles_tab, projects_tab, prefs_tab = st.tabs(["👤 Perfis pessoais", "📚 Projetos por perfil", "⚙️ Preferências"])

authors = list_author_profiles()
author_map = {p["id"]: profile_display_name(p) for p in authors}

with profiles_tab:
    section_title("Perfis do workspace", "Crie um espaço pessoal para cada pessoa que usa o FaithBloom.", "Family")
    profiles = list_workspace_profiles(include_archived=True)
    with st.expander("➕ Criar perfil", expanded=not profiles):
        with st.form("new_workspace_profile"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nome do perfil *", placeholder="Ex.: Larissa")
            relationship = c2.text_input("Identificação opcional", placeholder="Ex.: filha, marido, equipe")
            linked = st.selectbox(
                "Perfil de autoria relacionado (opcional)",
                options=[""] + list(author_map),
                format_func=lambda x: "— Nenhum —" if not x else author_map[x],
                help="Isso é apenas um vínculo conveniente. O perfil pessoal não vira automaticamente autor de todos os livros.",
            )
            c1, c2 = st.columns(2)
            locale = c1.text_input("Idioma padrão", value="pt-BR")
            age = c2.selectbox("Faixa etária padrão", sorted(AGE_PROFILES), index=sorted(AGE_PROFILES).index("3-8") if "3-8" in AGE_PROFILES else 0)
            style = st.text_input("Estilo visual preferido (opcional)")
            markets = st.text_input("Mercados de publicação preferidos", placeholder="Amazon KDP, Kobo, Apple Books")
            mode = st.radio("Dashboard", ["simple", "advanced"], format_func=lambda x: "Simplificado" if x == "simple" else "Avançado", horizontal=True)
            notes = st.text_area("Notas internas (opcional)")
            if st.form_submit_button("Criar perfil", use_container_width=True):
                try:
                    p = create_workspace_profile(
                        name,
                        relationship=relationship,
                        linked_author_profile_id=linked,
                        default_locale=locale,
                        default_age_profile=age,
                        default_visual_style=style,
                        publication_markets=[x.strip() for x in markets.split(",") if x.strip()],
                        dashboard_mode=mode,
                        notes=notes,
                    )
                    st.session_state["faithbloom_workspace_profile_id"] = p["id"]
                    st.success(f"Perfil criado: {p['display_name']}")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    profiles = list_workspace_profiles(include_archived=True)
    if profiles:
        opts = {f"{p.get('display_name')}{' · arquivado' if not p.get('active', True) else ''}": p for p in profiles}
        label = st.selectbox("Editar perfil", list(opts))
        p = opts[label]
        prefs = p.get("preferences") or {}
        with st.form(f"edit_workspace_{p['id']}"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nome", value=p.get("display_name", ""))
            relationship = c2.text_input("Identificação", value=p.get("relationship", ""))
            linked_options = [""] + list(author_map)
            current_linked = p.get("linked_author_profile_id", "")
            if current_linked not in linked_options:
                linked_options.append(current_linked)
            linked = st.selectbox("Perfil de autoria relacionado", linked_options, index=linked_options.index(current_linked), format_func=lambda x: "— Nenhum —" if not x else author_map.get(x, x))
            c1, c2 = st.columns(2)
            locale = c1.text_input("Idioma padrão", value=prefs.get("default_locale", "pt-BR"))
            age_options = sorted(AGE_PROFILES)
            current_age = prefs.get("default_age_profile", "3-8")
            if current_age not in age_options: age_options.append(current_age)
            age = c2.selectbox("Faixa etária padrão", age_options, index=age_options.index(current_age))
            style = st.text_input("Estilo visual preferido", value=prefs.get("default_visual_style", ""))
            markets = st.text_input("Mercados preferidos", value=", ".join(prefs.get("publication_markets") or []))
            mode = st.radio("Dashboard", ["simple", "advanced"], index=0 if prefs.get("dashboard_mode", "simple") == "simple" else 1, format_func=lambda x: "Simplificado" if x == "simple" else "Avançado", horizontal=True)
            active = st.checkbox("Perfil ativo", value=bool(p.get("active", True)))
            notes = st.text_area("Notas", value=p.get("notes", ""))
            if st.form_submit_button("Salvar perfil", use_container_width=True):
                update_workspace_profile(
                    p["id"], display_name=name, relationship=relationship,
                    linked_author_profile_id=linked, default_locale=locale,
                    default_age_profile=age, default_visual_style=style,
                    publication_markets=[x.strip() for x in markets.split(",") if x.strip()],
                    dashboard_mode=mode, active=active, notes=notes,
                )
                st.success("Perfil atualizado.")
                st.rerun()
        with st.expander("Resumo do perfil"):
            st.json(profile_summary(p))
    else:
        st.info("Crie o primeiro perfil pessoal para ativar o dashboard por pessoa.")

with projects_tab:
    section_title("Projetos por perfil", "Defina quem é o responsável pelo projeto e com quem ele é compartilhado.", "Workspace")
    profiles = list_workspace_profiles()
    if not profiles:
        st.info("Crie um perfil pessoal primeiro.")
    else:
        pmap = {p["id"]: p for p in profiles}
        story = [{"kind": "story", **x} for x in listar_livros()]
        coloring = [{"kind": "coloring", **x} for x in listar_livros_colorir()]
        cards = story + coloring
        if not cards:
            st.info("Ainda não há projetos salvos para atribuir.")
        else:
            idx = st.selectbox("Projeto", range(len(cards)), format_func=lambda i: f"{'📖' if cards[i]['kind']=='story' else '🖍️'} {cards[i].get('titulo')} · {cards[i].get('colecao') or cards[i].get('tema_geral') or ''}")
            card = cards[idx]
            path = card.get("storage_path") or card.get("arquivo")
            current = project_link(card["kind"], path)
            owner_default = current.get("owner_profile_id") if current else list(pmap)[0]
            if owner_default not in pmap: owner_default = list(pmap)[0]
            owner = st.selectbox("Perfil responsável", list(pmap), index=list(pmap).index(owner_default), format_func=lambda x: pmap[x]["display_name"])
            shared_defaults = [x for x in (current or {}).get("shared_profile_ids", []) if x in pmap and x != owner]
            shared = st.multiselect("Compartilhar no dashboard com", [x for x in pmap if x != owner], default=shared_defaults, format_func=lambda x: pmap[x]["display_name"])

            asset_page = list_assets({"media_kind": "image", "archived": False}, page=1, page_size=100, sort="newest")
            asset_rows = asset_page.get("items") or []
            asset_map = {a.get("id"): a for a in asset_rows if a.get("id")}
            thumb_options = [""] + list(asset_map)
            current_thumb = (current or {}).get("thumbnail_asset_id", "")
            if current_thumb and current_thumb not in thumb_options: thumb_options.append(current_thumb)
            thumb = st.selectbox("Thumbnail/capa no dashboard (opcional)", thumb_options, index=thumb_options.index(current_thumb) if current_thumb in thumb_options else 0, format_func=lambda x: "— Sem thumbnail —" if not x else asset_map.get(x, {}).get("nome") or asset_map.get(x, {}).get("name") or x)
            if st.button("Salvar organização do projeto", use_container_width=True):
                assign_project(
                    owner, card["kind"], path,
                    title=card.get("titulo", ""),
                    collection=card.get("colecao") or card.get("tema_geral") or "",
                    shared_profile_ids=shared,
                    thumbnail_asset_id=thumb,
                )
                st.success("Projeto organizado. O conteúdo editorial do livro não foi alterado.")
                st.rerun()

            if current:
                st.caption(f"Responsável atual: {pmap.get(current.get('owner_profile_id'), {}).get('display_name', current.get('owner_profile_id'))}")
                with st.expander("Vínculo do workspace"):
                    st.json(current)

with prefs_tab:
    section_title("Como isso aparece no dashboard", "O modo simplificado prioriza objetivos e continuação de trabalho; o avançado expõe mais Studios.", "UX")
    st.markdown("**Modo simplificado**")
    st.write("• Continuar de onde parou\n• Criar / revisar / traduzir / gerar atividades / audiobook / publicar\n• Projetos recentes do perfil\n• Ferramentas avançadas recolhidas")
    st.markdown("**Modo avançado**")
    st.write("• Mantém os atalhos rápidos\n• Exibe o catálogo completo de Studios e ferramentas técnicas")
    callout("Projetos não são movidos nem duplicados", "A organização por perfil usa vínculos externos ao Book Master. Trocar o responsável no workspace não muda autoria, conteúdo, Quality Gate ou fingerprint editorial do livro.", "🧭")

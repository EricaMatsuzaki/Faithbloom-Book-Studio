"""Refinamento 17 — Author & Contributor Profiles."""
from __future__ import annotations
import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from armazenamento import (
    listar_livros, listar_livros_colorir,
)
from project_metadata_ui import open_project_metadata
from author_profiles import (
    CONTRIBUTOR_ROLES, create_author_profile, list_author_profiles,
    update_author_profile, profile_display_name, ensure_project_authorship,
    set_project_authors, add_project_contributor, remove_project_credit,
    set_cover_credit_override, authorship_summary,
)

st.set_page_config(page_title="Autores & Colaboradores", page_icon="✍️", layout="wide")
aplicar_estilo()
hero(
    "✍️ Autores & Colaboradores",
    "Cadastre perfis reutilizáveis e escolha quem assina cada livro. Usuário do SaaS e autor do projeto são identidades independentes.",
    "Refinamento 17 · Author & Contributor Profiles",
)

profiles_tab, credits_tab = st.tabs(["👤 Perfis", "📚 Créditos por projeto"])


def profiles_for_page(*, include_archived=False):
    try:
        return list_author_profiles(include_archived=include_archived)
    except Exception:
        st.error("Não foi possível abrir os perfis editoriais nesta sessão. Confira o acesso e atualize a página.")
        st.stop()

with profiles_tab:
    section_title("Perfis editoriais", "Um perfil pode ser autor em um livro, tradutor em outro ou nem participar de determinado projeto.", "People")
    profiles = profiles_for_page(include_archived=True)
    with st.expander("➕ Criar novo perfil", expanded=not profiles):
        with st.form("new_author_profile"):
            c1,c2=st.columns(2)
            display=c1.text_input("Nome de publicação *", placeholder="Ex.: Larissa Ayumi")
            pen=c2.text_input("Pseudônimo (opcional)")
            legal=st.text_input("Nome completo interno (opcional)", help="Não é usado automaticamente em capa/metadados públicos.")
            bio=st.text_area("Biografia curta (opcional)")
            locales=st.text_input("Idiomas/locales (opcional)", placeholder="pt-BR, ja-JP, en-US")
            website=st.text_input("Site (opcional)")
            socials=st.text_input("Links/redes (opcional, separados por vírgula)")
            notes=st.text_area("Notas internas (opcional)")
            if st.form_submit_button("Criar perfil"):
                try:
                    p=create_author_profile(display,legal_name=legal,pen_name=pen,bio=bio,locales=[x.strip() for x in locales.split(",") if x.strip()],website=website,social_links=[x.strip() for x in socials.split(",") if x.strip()],notes=notes)
                    st.success(f"Perfil criado: {profile_display_name(p)}")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    profiles=profiles_for_page(include_archived=True)
    if not profiles:
        st.info("Nenhum perfil criado ainda.")
    else:
        opts={f"{profile_display_name(p)}{' · arquivado' if not p.get('active',True) else ''}":p for p in profiles}
        label=st.selectbox("Editar perfil",list(opts))
        p=opts[label]
        with st.form(f"edit_profile_{p['id']}"):
            c1,c2=st.columns(2)
            display=c1.text_input("Nome de publicação",value=p.get("display_name",""))
            pen=c2.text_input("Pseudônimo",value=p.get("pen_name",""))
            legal=st.text_input("Nome completo interno",value=p.get("legal_name",""))
            bio=st.text_area("Biografia",value=p.get("bio",""))
            locales=st.text_input("Idiomas/locales",value=", ".join(p.get("locales") or []))
            website=st.text_input("Site",value=p.get("website",""))
            socials=st.text_input("Links/redes",value=", ".join(p.get("social_links") or []))
            active=st.checkbox("Perfil ativo",value=bool(p.get("active",True)))
            if st.form_submit_button("Salvar alterações"):
                try:
                    update_author_profile(p["id"],display_name=display,pen_name=pen,legal_name=legal,bio=bio,locales=[x.strip() for x in locales.split(",") if x.strip()],website=website,social_links=[x.strip() for x in socials.split(",") if x.strip()],active=active)
                    st.success("Perfil atualizado. Livros antigos mantêm o snapshot de crédito até você atualizar o projeto explicitamente.")
                    st.rerun()
                except Exception:
                    st.error("Não foi possível confirmar a alteração do perfil. Seus campos continuam disponíveis para revisão.")

with credits_tab:
    section_title("Créditos do livro", "Escolha autor principal, coautores e colaboradores. A autoria pertence ao projeto, não ao usuário logado.", "Project")
    try:
        story=[{"kind":"story",**x} for x in listar_livros()]
        coloring=[{"kind":"coloring",**x} for x in listar_livros_colorir()]
    except Exception:
        st.error("Não foi possível abrir os projetos desta sessão. Confira o acesso e atualize a página.")
        st.stop()
    projects=story+coloring
    if not projects:
        st.info("Ainda não há livros salvos.")
    else:
        active=st.session_state.get("faithbloom_active_project") or {}
        project_map={x.get("storage_path") or x.get("arquivo"):x for x in projects}
        references=list(project_map)
        active_ref=str(active.get("storage_path") or "").removeprefix("fb://")
        default_idx=next((i for i,ref in enumerate(references) if str(ref).removeprefix("fb://")==active_ref),0)
        selected_ref=st.selectbox("Projeto",references,index=default_idx,format_func=lambda ref:f"{'📖' if project_map[ref]['kind']=='story' else '🖍️'} {project_map[ref].get('titulo')} · {project_map[ref].get('colecao') or project_map[ref].get('tema_geral') or 'sem coleção'}")
        card=project_map[selected_ref]
        editor=open_project_metadata(card.get("storage_path") or card.get("arquivo"),kind=card["kind"],namespace="project_credits")
        state=ensure_project_authorship(editor.state)
        def save(updated):
            try:
                return editor.save(updated,fields=["authorship","autora"])
            except Exception:
                st.error("Não foi possível preparar os créditos para salvar. Recarregue o projeto e confira os perfis escolhidos.")
                return False
        summary=authorship_summary(state)
        callout("Crédito atual", summary["author_display"] or "Nenhum autor definido", "✍️")

        active_profiles=profiles_for_page()
        profile_map={p["id"]:p for p in active_profiles}
        labels={p["id"]:profile_display_name(p) for p in active_profiles}
        current_ids=[x.get("profile_id") for x in state["authorship"]["authors"] if x.get("profile_id") in profile_map]
        if active_profiles:
            primary_default=current_ids[0] if current_ids else list(profile_map)[0]
            primary=st.selectbox("Autor(a) principal",options=list(profile_map),index=list(profile_map).index(primary_default),format_func=lambda pid:labels[pid],key=editor.key("primary"))
            co_defaults=[x for x in current_ids[1:] if x != primary]
            coauthors=st.multiselect("Coautores",options=[x for x in profile_map if x != primary],default=co_defaults,format_func=lambda pid:labels[pid],key=editor.key("coauthors"))
            ordered=[primary]
            if coauthors:
                st.caption("Defina a ordem dos coautores (2 = primeiro coautor).")
                order_rows=[]
                for j,pid in enumerate(coauthors,2):
                    n=st.number_input(f"Ordem · {labels[pid]}",min_value=2,max_value=99,value=j,step=1,key=editor.key(f"author_order_{pid}"))
                    order_rows.append((int(n),pid))
                ordered += [pid for _,pid in sorted(order_rows,key=lambda x:(x[0],labels[x[1]].casefold()))]
            if st.button("Salvar autoria deste projeto",use_container_width=True,disabled=not editor.can_save):
                try:
                    updated=set_project_authors(state,ordered)
                    if save(updated):
                        st.success("Autoria salva no projeto. O usuário logado não foi alterado."); st.rerun()
                except Exception:
                    st.error("Não foi possível preparar a autoria. Confira os perfis escolhidos antes de salvar novamente.")
        else:
            st.warning("Crie pelo menos um perfil na aba Perfis para substituir o crédito legado deste livro.")

        st.markdown("#### Colaboradores")
        rows=summary["contributors"]
        if rows:
            for r in rows:
                c1,c2,c3=st.columns([3,2,1]); c1.write(f"**{r['name']}**"); c2.caption(r["role_label"])
                if c3.button("Remover",key=editor.key(f"rm_{r['profile_id']}_{r['role']}"),disabled=not editor.can_save):
                    updated=remove_project_credit(state,profile_id=r["profile_id"],role=r["role"])
                    if save(updated): st.rerun()
        if active_profiles:
            c1,c2=st.columns(2)
            pid=c1.selectbox("Pessoa",list(profile_map),format_func=lambda x:labels[x],key=editor.key("contrib_person"))
            role_opts=[k for k in CONTRIBUTOR_ROLES if k not in {"author","coauthor"}]
            role=c2.selectbox("Função",role_opts,format_func=lambda x:CONTRIBUTOR_ROLES[x],key=editor.key("contrib_role"))
            credit_as=st.text_input("Crédito como (opcional)",placeholder="Deixe vazio para usar o nome de publicação do perfil",key=editor.key("contrib_credit"))
            if st.button("Adicionar colaborador",use_container_width=True,key=editor.key("add_contrib"),disabled=not editor.can_save):
                try:
                    updated=add_project_contributor(state,pid,role,credit_as=credit_as)
                    if save(updated): st.rerun()
                except Exception:
                    st.error("Não foi possível preparar o colaborador. Confira o perfil escolhido antes de salvar novamente.")

        st.markdown("#### Crédito na capa")
        override=st.text_input("Override opcional",value=state["authorship"].get("cover_credit_override", ""),help="Se vazio, a capa usa automaticamente a autoria estruturada do projeto.",key=editor.key("cover_credit"))
        if st.button("Salvar crédito de capa",key=editor.key("save_cover_credit"),disabled=not editor.can_save):
            updated=set_cover_credit_override(state,override)
            if save(updated): st.success("Crédito de capa salvo."); st.rerun()

        if editor.stale:
            editor.preserve_form_inputs({"cover_credit_override":override,
                "author_profile_ids":ordered if active_profiles else [],
                "contributor_profile_id":pid if active_profiles else None,
                "contributor_role":role if active_profiles else None,
                "contributor_credit":credit_as if active_profiles else ""})

        with st.expander("Ver estrutura editorial deste projeto"):
            st.json(authorship_summary(state))

callout("Snapshots protegem edições antigas", "Alterar um perfil global não reescreve silenciosamente o crédito já salvo em um livro. Para atualizar uma edição, abra o projeto e salve a autoria novamente.", "🔒")

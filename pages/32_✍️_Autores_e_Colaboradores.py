"""Refinamento 17 — Author & Contributor Profiles."""
from __future__ import annotations
import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from armazenamento import (
    listar_livros, carregar_livro, atualizar_livro_salvo,
    listar_livros_colorir, carregar_livro_colorir, atualizar_livro_colorir_salvo,
)
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

with profiles_tab:
    section_title("Perfis editoriais", "Um perfil pode ser autor em um livro, tradutor em outro ou nem participar de determinado projeto.", "People")
    profiles = list_author_profiles(include_archived=True)
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

    profiles=list_author_profiles(include_archived=True)
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
                update_author_profile(p["id"],display_name=display,pen_name=pen,legal_name=legal,bio=bio,locales=[x.strip() for x in locales.split(",") if x.strip()],website=website,social_links=[x.strip() for x in socials.split(",") if x.strip()],active=active)
                st.success("Perfil atualizado. Livros antigos mantêm o snapshot de crédito até você atualizar o projeto explicitamente.")
                st.rerun()

with credits_tab:
    section_title("Créditos do livro", "Escolha autor principal, coautores e colaboradores. A autoria pertence ao projeto, não ao usuário logado.", "Project")
    story=[{"kind":"story",**x} for x in listar_livros()]
    coloring=[{"kind":"coloring",**x} for x in listar_livros_colorir()]
    projects=story+coloring
    if not projects:
        st.info("Ainda não há livros salvos.")
    else:
        active=st.session_state.get("faithbloom_active_project") or {}
        default_idx=0
        for i,b in enumerate(projects):
            if active.get("storage_path") and active.get("storage_path")==b.get("storage_path"):
                default_idx=i; break
        idx=st.selectbox("Projeto",range(len(projects)),index=default_idx,format_func=lambda i:f"{'📖' if projects[i]['kind']=='story' else '🖍️'} {projects[i].get('titulo')} · {projects[i].get('colecao') or projects[i].get('tema_geral') or 'sem coleção'}")
        card=projects[idx]
        if card["kind"]=="story":
            state=carregar_livro(card.get("colecao",""),card.get("storage_path") or card.get("arquivo"))
            save=lambda updated: atualizar_livro_salvo(card.get("storage_path") or card.get("arquivo"),updated)
        else:
            state=carregar_livro_colorir(card.get("storage_path") or card.get("arquivo"))
            save=lambda updated: atualizar_livro_colorir_salvo(card.get("storage_path") or card.get("arquivo"),updated)
        state=ensure_project_authorship(state)
        summary=authorship_summary(state)
        callout("Crédito atual", summary["author_display"] or "Nenhum autor definido", "✍️")

        active_profiles=list_author_profiles()
        profile_map={p["id"]:p for p in active_profiles}
        labels={p["id"]:profile_display_name(p) for p in active_profiles}
        current_ids=[x.get("profile_id") for x in state["authorship"]["authors"] if x.get("profile_id") in profile_map]
        if active_profiles:
            primary_default=current_ids[0] if current_ids else list(profile_map)[0]
            primary=st.selectbox("Autor(a) principal",options=list(profile_map),index=list(profile_map).index(primary_default),format_func=lambda pid:labels[pid])
            co_defaults=[x for x in current_ids[1:] if x != primary]
            coauthors=st.multiselect("Coautores",options=[x for x in profile_map if x != primary],default=co_defaults,format_func=lambda pid:labels[pid])
            ordered=[primary]
            if coauthors:
                st.caption("Defina a ordem dos coautores (2 = primeiro coautor).")
                order_rows=[]
                for j,pid in enumerate(coauthors,2):
                    n=st.number_input(f"Ordem · {labels[pid]}",min_value=2,max_value=99,value=j,step=1,key=f"author_order_{card.get('storage_path')}_{pid}")
                    order_rows.append((int(n),pid))
                ordered += [pid for _,pid in sorted(order_rows,key=lambda x:(x[0],labels[x[1]].casefold()))]
            if st.button("Salvar autoria deste projeto",use_container_width=True):
                updated=set_project_authors(state,ordered); save(updated)
                st.success("Autoria salva no projeto. O usuário logado não foi alterado."); st.rerun()
        else:
            st.warning("Crie pelo menos um perfil na aba Perfis para substituir o crédito legado deste livro.")

        st.markdown("#### Colaboradores")
        rows=summary["contributors"]
        if rows:
            for r in rows:
                c1,c2,c3=st.columns([3,2,1]); c1.write(f"**{r['name']}**"); c2.caption(r["role_label"])
                if c3.button("Remover",key=f"rm_{card.get('storage_path')}_{r['profile_id']}_{r['role']}"):
                    updated=remove_project_credit(state,profile_id=r["profile_id"],role=r["role"]); save(updated); st.rerun()
        if active_profiles:
            c1,c2=st.columns(2)
            pid=c1.selectbox("Pessoa",list(profile_map),format_func=lambda x:labels[x],key=f"contrib_person_{card.get('storage_path')}")
            role_opts=[k for k in CONTRIBUTOR_ROLES if k not in {"author","coauthor"}]
            role=c2.selectbox("Função",role_opts,format_func=lambda x:CONTRIBUTOR_ROLES[x],key=f"contrib_role_{card.get('storage_path')}")
            credit_as=st.text_input("Crédito como (opcional)",placeholder="Deixe vazio para usar o nome de publicação do perfil",key=f"contrib_credit_{card.get('storage_path')}")
            if st.button("Adicionar colaborador",use_container_width=True,key=f"add_contrib_{card.get('storage_path')}"):
                updated=add_project_contributor(state,pid,role,credit_as=credit_as); save(updated); st.rerun()

        st.markdown("#### Crédito na capa")
        override=st.text_input("Override opcional",value=state["authorship"].get("cover_credit_override", ""),help="Se vazio, a capa usa automaticamente a autoria estruturada do projeto.",key=f"cover_credit_{card.get('storage_path')}")
        if st.button("Salvar crédito de capa",key=f"save_cover_credit_{card.get('storage_path')}"):
            updated=set_cover_credit_override(state,override); save(updated); st.success("Crédito de capa salvo."); st.rerun()

        with st.expander("Ver estrutura editorial deste projeto"):
            st.json(authorship_summary(state))

callout("Snapshots protegem edições antigas", "Alterar um perfil global não reescreve silenciosamente o crédito já salvo em um livro. Para atualizar uma edição, abra o projeto e salve a autoria novamente.", "🔒")

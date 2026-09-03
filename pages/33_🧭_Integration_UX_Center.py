"""Refinamento 17 — Integration & UX Center."""
from __future__ import annotations
import streamlit as st
from estilo import aplicar_estilo, hero, section_title, callout
from armazenamento import listar_livros, carregar_livro
from integration_ux import STUDIOS, make_project_context, make_asset_context, make_handoff, validate_handoff

st.set_page_config(page_title="Integration & UX Center",page_icon="🧭",layout="wide")
aplicar_estilo()
hero("🧭 Integration & UX Center","Mantenha projeto e asset ativos ao navegar entre os Studios e veja claramente o que será reaproveitado antes de mudar de etapa.","Refinamento 17 · Context-aware navigation")

section_title("Contexto ativo","O contexto só facilita navegação; ele não modifica um Book Master automaticamente.","Context")
books=listar_livros()
if books:
    active=st.session_state.get("faithbloom_active_project") or {}
    default=0
    for i,b in enumerate(books):
        if active.get("storage_path")==b.get("storage_path"): default=i; break
    idx=st.selectbox("Projeto ativo",range(len(books)),index=default,format_func=lambda i:f"{books[i].get('titulo')} · {books[i].get('colecao') or 'sem coleção'}")
    card=books[idx]; state=carregar_livro(card.get("colecao",""),card.get("storage_path") or card.get("arquivo"))
    ctx=make_project_context(card,state); st.session_state["faithbloom_active_project"]=ctx
    st.success(f"📘 {ctx['title']} · {ctx['collection'] or 'sem coleção'} · {ctx['language'] or 'locale não definido'}")
else:
    st.info("Nenhum Story Book salvo ainda.")
    state={}; ctx={}

asset=st.session_state.get("faithbloom_selected_asset") or {}
if asset:
    actx=make_asset_context(asset)
    st.info(f"🖼️ Asset ativo: {actx['name'] or actx['asset_id']} · {actx['media_kind'] or 'tipo não definido'}")
else:
    actx={}; st.caption("Nenhum asset selecionado. Escolha um na Asset Library quando quiser reutilizá-lo.")

section_title("Ir para um Studio","O FaithBloom registra um handoff explícito com o projeto/asset atual, sem gerar ou sobrescrever conteúdo no destino.","Handoff")
cols=st.columns(3)
for i,(sid,spec) in enumerate(STUDIOS.items()):
    with cols[i%3]:
        with st.container(border=True):
            st.markdown(f"**{spec['label']}**")
            st.caption("Aceita: " + ", ".join(spec["accepts"]))
            payload=make_handoff("integration_center",sid,project=ctx if ctx and "project" in spec["accepts"] else None,asset=asset if actx and "asset" in spec["accepts"] else None)
            check=validate_handoff(payload)
            if st.button("Preparar handoff",key=f"handoff_{sid}",use_container_width=True):
                st.session_state["faithbloom_handoff"]=payload
                if payload.get("project"): st.session_state["faithbloom_active_project"]=payload["project"]
                if payload.get("asset"):
                    st.session_state["faithbloom_selected_asset_id"]=payload["asset"].get("asset_id","")
                    st.session_state["faithbloom_selected_asset_path"]=payload["asset"].get("path","")
                st.success("Contexto preparado.")
            st.page_link(spec["page"],label="Abrir →",use_container_width=True)

handoff=st.session_state.get("faithbloom_handoff")
if handoff:
    section_title("Último handoff","Útil para diagnosticar se uma seleção chegou ao Studio correto.","Debug")
    check=validate_handoff(handoff)
    (st.success if check["valid"] else st.error)("Handoff válido" if check["valid"] else f"Handoff inválido: {check['errors']}")
    with st.expander("Detalhes"):
        st.json(handoff)

callout("Sem alteração silenciosa","Selecionar projeto/asset aqui só define contexto de navegação. A ação editorial continua exigindo confirmação dentro do Studio responsável.","🔒")

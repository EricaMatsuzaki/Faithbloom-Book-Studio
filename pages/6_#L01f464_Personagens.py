"""Biblioteca oficial + Galeria visual do FaithBloom 2.0."""

import streamlit as st
from estilo import aplicar_estilo, hero
from armazenamento import (
    listar_colecoes,
    carregar_biblioteca_personagens,
    listar_galeria,
    favoritar_item_galeria,
)

st.set_page_config(page_title="Personagens e Galeria", page_icon="👤", layout="wide")
aplicar_estilo()
hero("👤 Personagens & Galeria", "Personagens oficiais de cada coleção e ideias visuais guardadas para uso futuro.")

tab_biblioteca, tab_galeria = st.tabs(["👥 Biblioteca Oficial", "🖼️ Galeria de Imagens"])

with tab_biblioteca:
    st.caption("A Biblioteca guarda somente personagens oficiais/aprovados de cada coleção.")
    colecoes = listar_colecoes()
    if not colecoes:
        st.info("Nenhuma coleção com personagens salvos ainda.")
    else:
        colecao_escolhida = st.selectbox("Coleção", colecoes)
        biblioteca = carregar_biblioteca_personagens(colecao_escolhida)
        if not biblioteca:
            st.caption("Essa coleção ainda não tem personagens salvos.")
        else:
            cols = st.columns(3)
            for i, (nome, p) in enumerate(biblioteca.items()):
                with cols[i % 3]:
                    with st.container(border=True):
                        if p.get("imagem_referencia"):
                            st.image(p["imagem_referencia"], use_container_width=True)
                        st.markdown(f"**{nome}**")
                        st.caption(p.get("papel", ""))
                        if p.get("aparencia_aprovada"):
                            st.success("🔒 Aparência oficial aprovada")
                        st.write(p.get("descricao_fixa", ""))

with tab_galeria:
    st.caption(
        "A Galeria pode guardar opções lindas que não serviram para a história atual. "
        "Nada aqui precisa ser um personagem oficial."
    )
    itens = listar_galeria()
    if not itens:
        st.info("Sua Galeria ainda está vazia. Nas telas de aprovação use 💾 Salvar na Galeria.")
    else:
        filtro = st.selectbox("Mostrar", ["Todos", "personagem", "cena", "line_art", "referencia"])
        exibidos = itens if filtro == "Todos" else [i for i in itens if i.get("tipo") == filtro]
        cols = st.columns(4)
        for i, item in enumerate(exibidos):
            with cols[i % 4]:
                with st.container(border=True):
                    caminho = item.get("caminho_arquivo", "")
                    if caminho:
                        try:
                            st.image(caminho, use_container_width=True)
                        except Exception:
                            st.warning("Arquivo visual não está disponível nesta sessão.")
                    st.markdown(f"**{item.get('nome', 'Imagem')}**")
                    st.caption(f"Tipo: {item.get('tipo', '')}")
                    tags = item.get("tags", [])
                    if tags:
                        st.caption(" · ".join(tags))
                    fav = bool(item.get("favorita"))
                    if st.button("💖 Favorita" if fav else "♡ Favoritar", key=f"gal_fav_{item.get('id')}", use_container_width=True):
                        favoritar_item_galeria(item.get("id", ""), not fav)
                        st.rerun()

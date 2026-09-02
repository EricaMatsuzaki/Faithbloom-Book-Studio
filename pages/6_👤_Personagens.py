"""
Biblioteca de Personagens - veja o elenco fixo de cada coleção, com a
referência visual de cada personagem.
"""

import streamlit as st
from estilo import aplicar_estilo, hero

from armazenamento import listar_colecoes, carregar_biblioteca_personagens

st.set_page_config(page_title="Personagens", page_icon="👤")
aplicar_estilo()
hero("👤 Biblioteca de Personagens", "O elenco fixo de cada coleção, reaproveitado automaticamente.")
st.caption("Elenco fixo de cada coleção - reaproveitado automaticamente em todo livro novo dela.")

colecoes = listar_colecoes()
if not colecoes:
    st.info("Nenhuma coleção com personagens salvos ainda.")
    st.stop()

colecao_escolhida = st.selectbox("Coleção", colecoes)
biblioteca = carregar_biblioteca_personagens(colecao_escolhida)

if not biblioteca:
    st.caption("Essa coleção ainda não tem personagens salvos.")
else:
    cols = st.columns(3)
    for i, (nome, p) in enumerate(biblioteca.items()):
        with cols[i % 3]:
            if p.get("imagem_referencia"):
                st.image(p["imagem_referencia"], width=200)
            st.markdown(f"**{nome}**")
            st.caption(p.get("papel", ""))
            st.write(p.get("descricao_fixa", ""))

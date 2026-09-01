"""
FaithBloom Book Studio - Hub principal.

O Streamlit gera o menu lateral automaticamente a partir dos arquivos
em pages/ - essa página (app.py) é só a "Home", com visão geral e
atalhos estilizados. As ferramentas de verdade estão nas páginas do
menu lateral (ver estilo.py para o tema visual compartilhado).
"""

import streamlit as st
from armazenamento import listar_livros, listar_livros_colorir, listar_colecoes
from estilo import aplicar_estilo, hero, card, badge_status

st.set_page_config(page_title="FaithBloom Book Studio", page_icon="📖", layout="wide")
aplicar_estilo()

hero(
    "📖 FaithBloom Book Studio",
    "Sua fábrica de livros infantis — histórias, ilustrações, audiobook e livros de colorir, tudo num só lugar.",
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Coleções", len(listar_colecoes()))
with col2:
    st.metric("Livros com história", len(listar_livros()))
with col3:
    st.metric("Livros de colorir", len(listar_livros_colorir()))

st.write("")
st.subheader("Para onde ir")

col1, col2 = st.columns(2)
with col1:
    card("📖 Criar do Zero", "Tema/resumo livre ou preenchimento manual — passa pelo pipeline inteiro, do Roteirista à Capa.")
    card("🖍️ Livros de Colorir", "Projetos de line art (bichinhos, princesas, carros, o que for), separados dos livros com história.")
    card("🔍 Analisar Livro", "Veja o texto gerado cena a cena, os personagens usados, dedicatória, sinopse — tudo de um livro salvo.")
with col2:
    card("📚 Retomar Livro", "Já tem o roteiro pronto? Pula direto pro Ilustrador, sem reescrever a história.")
    card("🎯 Ir Direto para Etapa", "Escolha um livro salvo e rode só UM agente específico — ex: só regerar a capa.")
    card("👤 Personagens", "Biblioteca de personagens de cada coleção, com a referência visual de cada um.")

st.write("")
st.subheader("Livros recentes")
livros = listar_livros()[:5]
if not livros:
    st.caption("Nenhum livro com história salvo ainda.")
for livro in livros:
    st.markdown(
        f"{badge_status(livro['pacote_pronto'])} &nbsp; **{livro['titulo']}** &nbsp; · &nbsp; {livro['colecao']}",
        unsafe_allow_html=True,
    )

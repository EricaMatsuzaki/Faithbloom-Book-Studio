"""Página multipage do Coloring Book Studio 2.0."""
import streamlit as st
from estilo import aplicar_estilo, hero
from coloring_studio import render_coloring_studio

st.set_page_config(page_title="Coloring Book Studio", page_icon="🖍️", layout="wide")
aplicar_estilo()
hero("🖍️ Coloring Book Studio", "Crie line arts para crianças, jovens ou adultos e salve seus próprios estilos.")
render_coloring_studio()


st.divider()
st.page_link("pages/20_🖍️_Coloring_Book_Doctor.py", label="🩺 Já tenho um livro de colorir? Abrir Coloring Book Doctor →", use_container_width=True)

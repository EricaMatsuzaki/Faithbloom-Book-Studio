"""Entrada standalone do FaithBloom Coloring Book Studio 2.0."""
import streamlit as st
from estilo import aplicar_estilo, hero
from coloring_studio import render_coloring_studio

st.set_page_config(page_title="Coloring Book Studio", page_icon="🖍️", layout="wide")
aplicar_estilo()
hero("🖍️ Coloring Book Studio", "Infantil, juvenil, adulto e personalizado — com presets, Galeria e Biblioteca.")
render_coloring_studio()

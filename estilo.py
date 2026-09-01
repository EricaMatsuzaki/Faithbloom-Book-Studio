"""
Estilo visual compartilhado do FaithBloom Book Studio.

Paleta baseada na identidade visual que a Erica já usa no selo/faixa
da coleção: teal suave + dourado + creme quente. Chamar
aplicar_estilo() no topo de cada página (depois do st.set_page_config)
pra manter a mesma identidade visual em todo o app.
"""

import streamlit as st

TEAL = "#4FA89B"
TEAL_ESCURO = "#2F7A70"
DOURADO = "#D4A574"
CREME = "#FFFBF5"
CREME_ESCURO = "#FDF1E3"
MARROM = "#3A2E22"
ROSA_SUAVE = "#F4C7C3"

CSS = f"""
<style>
    /* Cabeçalho com gradiente suave */
    .fb-hero {{
        background: linear-gradient(135deg, {TEAL} 0%, {TEAL_ESCURO} 100%);
        padding: 2rem 2.2rem;
        border-radius: 18px;
        color: white;
        margin-bottom: 1.6rem;
        box-shadow: 0 6px 20px rgba(47, 122, 112, 0.25);
    }}
    .fb-hero h1 {{
        color: white !important;
        margin: 0;
        font-size: 2rem;
    }}
    .fb-hero p {{
        color: #EAF6F4;
        margin: 0.3rem 0 0 0;
        font-size: 1.02rem;
    }}

    /* Cards de navegação/estatística */
    .fb-card {{
        background: white;
        border: 1px solid {CREME_ESCURO};
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        box-shadow: 0 2px 10px rgba(58, 46, 34, 0.06);
        margin-bottom: 0.9rem;
        transition: transform 0.15s ease;
    }}
    .fb-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(58, 46, 34, 0.10);
    }}
    .fb-card h4 {{
        margin: 0 0 0.3rem 0;
        color: {TEAL_ESCURO};
    }}
    .fb-card p {{
        margin: 0;
        color: {MARROM};
        font-size: 0.92rem;
        opacity: 0.85;
    }}

    /* Badge de status */
    .fb-badge-pronto {{
        background: {TEAL};
        color: white;
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
    }}
    .fb-badge-andamento {{
        background: {DOURADO};
        color: white;
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
    }}

    /* Botões primários com gradiente suave */
    .stButton > button[kind="primary"], .stButton > button {{
        border-radius: 10px !important;
        border: 1px solid {TEAL} !important;
    }}
    .stButton > button:hover {{
        border-color: {TEAL_ESCURO} !important;
        color: {TEAL_ESCURO} !important;
    }}

    /* Sidebar com fundo levemente diferenciado e título estilizado */
    section[data-testid="stSidebar"] {{
        background: {CREME_ESCURO};
    }}
    section[data-testid="stSidebar"] .stMarkdown h3 {{
        color: {TEAL_ESCURO};
    }}

    /* Métricas com um toque mais colorido */
    div[data-testid="stMetric"] {{
        background: white;
        border-radius: 12px;
        padding: 0.8rem 1rem;
        border: 1px solid {CREME_ESCURO};
    }}
    div[data-testid="stMetricValue"] {{
        color: {TEAL_ESCURO};
    }}

    /* Expanders com cantos suaves */
    div[data-testid="stExpander"] {{
        border-radius: 12px !important;
        border: 1px solid {CREME_ESCURO} !important;
    }}
</style>
"""


def aplicar_estilo():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(titulo: str, subtitulo: str = ""):
    st.markdown(
        f"""<div class="fb-hero"><h1>{titulo}</h1><p>{subtitulo}</p></div>""",
        unsafe_allow_html=True,
    )


def card(titulo: str, descricao: str):
    st.markdown(
        f"""<div class="fb-card"><h4>{titulo}</h4><p>{descricao}</p></div>""",
        unsafe_allow_html=True,
    )


def badge_status(pronto: bool) -> str:
    if pronto:
        return '<span class="fb-badge-pronto">✅ pronto</span>'
    return '<span class="fb-badge-andamento">🔧 em andamento</span>'

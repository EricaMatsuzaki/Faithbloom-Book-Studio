"""
Sistema visual compartilhado do FaithBloom Book Studio 2.0.

Fase 10: identidade premium/futurista acolhedora, com glassmorphism
leve, gradientes teal/azul/lilás e componentes reutilizáveis. O visual
foi pensado para continuar delicado e editorial — não "cyberpunk" —
porque o FaithBloom atende livros infantis, cristãos e coloring books.
"""

from html import escape
import streamlit as st

TEAL = "#22A899"
TEAL_ESCURO = "#167C78"
AZUL = "#4E7CFF"
LILAS = "#8B6CF6"
ROSA = "#F69AC8"
DOURADO = "#D7A45D"
CREME = "#FFFDF8"
INK = "#152536"
INK_SOFT = "#5F6B7A"
BORDER = "rgba(31, 87, 105, 0.12)"

CSS = f"""
<style>
    :root {{
        --fb-teal: {TEAL};
        --fb-teal-dark: {TEAL_ESCURO};
        --fb-blue: {AZUL};
        --fb-lilac: {LILAS};
        --fb-pink: {ROSA};
        --fb-gold: {DOURADO};
        --fb-ink: {INK};
        --fb-muted: {INK_SOFT};
    }}

    html {{ scroll-behavior: smooth; }}

    .stApp {{
        background:
            radial-gradient(circle at 8% 0%, rgba(34,168,153,.10), transparent 30%),
            radial-gradient(circle at 93% 4%, rgba(139,108,246,.10), transparent 32%),
            radial-gradient(circle at 55% 100%, rgba(78,124,255,.07), transparent 35%),
            linear-gradient(180deg, #FFFFFF 0%, #FBFCFF 48%, #FFFDF9 100%);
        color: {INK};
    }}

    .block-container {{
        max-width: 1480px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }}

    /* HERO */
    .fb-hero {{
        position: relative;
        overflow: hidden;
        background:
            linear-gradient(125deg, rgba(21,49,76,.97) 0%, rgba(24,112,113,.96) 45%, rgba(84,77,174,.94) 100%);
        padding: 2.3rem 2.5rem;
        border-radius: 26px;
        color: white;
        margin-bottom: 1.55rem;
        box-shadow: 0 22px 55px rgba(27,78,104,.18);
        border: 1px solid rgba(255,255,255,.24);
    }}
    .fb-hero::before {{
        content: "";
        position: absolute;
        width: 330px;
        height: 330px;
        right: -75px;
        top: -150px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,255,255,.20), rgba(255,255,255,0));
    }}
    .fb-hero::after {{
        content: "";
        position: absolute;
        width: 200px;
        height: 200px;
        left: 34%;
        bottom: -135px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(246,154,200,.22), rgba(246,154,200,0));
    }}
    .fb-hero h1 {{
        color: white !important;
        margin: .2rem 0 .45rem 0;
        font-size: clamp(2rem, 3vw, 3rem);
        line-height: 1.08;
        letter-spacing: -.035em;
        position: relative;
        z-index: 2;
    }}
    .fb-hero p {{
        color: rgba(255,255,255,.86);
        margin: 0;
        font-size: 1.02rem;
        max-width: 820px;
        line-height: 1.6;
        position: relative;
        z-index: 2;
    }}
    .fb-eyebrow {{
        display: inline-flex;
        align-items: center;
        gap: .45rem;
        padding: .33rem .72rem;
        border-radius: 999px;
        background: rgba(255,255,255,.12);
        border: 1px solid rgba(255,255,255,.18);
        color: rgba(255,255,255,.92);
        font-size: .73rem;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: .10em;
        position: relative;
        z-index: 2;
    }}

    /* SECTION TITLES */
    .fb-section {{ margin: 1.8rem 0 .85rem 0; }}
    .fb-section .kicker {{
        color: {TEAL_ESCURO};
        font-size: .72rem;
        text-transform: uppercase;
        letter-spacing: .12em;
        font-weight: 800;
        margin-bottom: .18rem;
    }}
    .fb-section h2 {{
        color: {INK} !important;
        font-size: 1.34rem;
        margin: 0;
        letter-spacing: -.02em;
    }}
    .fb-section p {{
        margin: .25rem 0 0 0;
        color: {INK_SOFT};
        font-size: .92rem;
    }}

    /* FEATURE / NAV CARDS */
    .fb-card, .fb-feature-card {{
        background: rgba(255,255,255,.78);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid {BORDER};
        border-radius: 20px;
        padding: 1.15rem 1.25rem;
        box-shadow: 0 12px 30px rgba(41,73,102,.07);
        margin-bottom: .72rem;
        min-height: 118px;
        transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
    }}
    .fb-card:hover, .fb-feature-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 17px 38px rgba(41,73,102,.12);
        border-color: rgba(34,168,153,.25);
    }}
    .fb-card h4, .fb-feature-card h4 {{
        margin: 0 0 .34rem 0;
        color: {INK};
        font-size: 1rem;
        letter-spacing: -.015em;
    }}
    .fb-card p, .fb-feature-card p {{
        margin: 0;
        color: {INK_SOFT};
        font-size: .86rem;
        line-height: 1.5;
    }}
    .fb-feature-icon {{
        width: 42px;
        height: 42px;
        border-radius: 13px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: .72rem;
        background: linear-gradient(135deg, rgba(34,168,153,.13), rgba(139,108,246,.13));
        border: 1px solid rgba(34,168,153,.12);
        font-size: 1.28rem;
    }}

    /* CALLOUT */
    .fb-callout {{
        background: linear-gradient(135deg, rgba(34,168,153,.08), rgba(139,108,246,.07));
        border: 1px solid rgba(34,168,153,.16);
        border-radius: 20px;
        padding: 1.2rem 1.35rem;
        margin: .75rem 0;
    }}
    .fb-callout strong {{ color: {INK}; }}
    .fb-callout p {{ margin: .28rem 0 0 0; color: {INK_SOFT}; font-size: .9rem; }}

    /* BADGES */
    .fb-badge-pronto, .fb-badge-andamento, .fb-badge-neutral {{
        display:inline-block;
        padding:.18rem .62rem;
        border-radius:999px;
        font-size:.74rem;
        font-weight:750;
    }}
    .fb-badge-pronto {{ background:rgba(34,168,153,.14); color:{TEAL_ESCURO}; border:1px solid rgba(34,168,153,.20); }}
    .fb-badge-andamento {{ background:rgba(215,164,93,.14); color:#98651D; border:1px solid rgba(215,164,93,.24); }}
    .fb-badge-neutral {{ background:rgba(78,124,255,.09); color:#3F61C5; border:1px solid rgba(78,124,255,.16); }}

    /* METRICS */
    div[data-testid="stMetric"] {{
        background: rgba(255,255,255,.78);
        backdrop-filter: blur(12px);
        border-radius: 18px;
        padding: .92rem 1.08rem;
        border: 1px solid {BORDER};
        box-shadow: 0 8px 24px rgba(41,73,102,.055);
    }}
    div[data-testid="stMetricLabel"] {{ color: {INK_SOFT}; }}
    div[data-testid="stMetricValue"] {{ color: {TEAL_ESCURO}; letter-spacing: -.025em; }}

    /* BUTTONS + PAGE LINKS */
    .stButton > button, .stDownloadButton > button {{
        border-radius: 12px !important;
        border: 1px solid rgba(34,168,153,.24) !important;
        min-height: 2.55rem;
        font-weight: 650 !important;
        transition: all .18s ease !important;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover {{
        transform: translateY(-1px);
        border-color: {TEAL} !important;
        box-shadow: 0 8px 18px rgba(34,168,153,.12) !important;
    }}
    .stButton > button[kind="primary"] {{
        color: white !important;
        background: linear-gradient(100deg, {TEAL_ESCURO}, {TEAL}, {AZUL}) !important;
        border: none !important;
        box-shadow: 0 9px 22px rgba(34,168,153,.20) !important;
    }}
    a[data-testid="stPageLink-NavLink"] {{
        border-radius: 12px !important;
        background: rgba(255,255,255,.72) !important;
        border: 1px solid rgba(34,168,153,.14) !important;
        min-height: 2.45rem;
        transition: all .18s ease;
    }}
    a[data-testid="stPageLink-NavLink"]:hover {{
        background: rgba(34,168,153,.055) !important;
        border-color: rgba(34,168,153,.30) !important;
        transform: translateY(-1px);
    }}

    /* INPUTS */
    div[data-baseweb="input"] > div,
    div[data-baseweb="textarea"] > div,
    div[data-baseweb="select"] > div {{
        border-radius: 12px !important;
        border-color: rgba(31,87,105,.16) !important;
        background: rgba(255,255,255,.84) !important;
    }}

    /* TABS */
    button[data-baseweb="tab"] {{
        border-radius: 10px 10px 0 0;
        font-weight: 650;
    }}

    /* EXPANDERS / CONTAINERS */
    div[data-testid="stExpander"] {{
        border-radius: 16px !important;
        border: 1px solid {BORDER} !important;
        background: rgba(255,255,255,.63);
    }}

    /* SIDEBAR */
    section[data-testid="stSidebar"] {{
        background:
            linear-gradient(180deg, rgba(246,251,250,.98) 0%, rgba(250,248,255,.98) 100%);
        border-right: 1px solid rgba(31,87,105,.08);
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {{
        border-radius: 11px;
        margin: 2px 8px;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {{
        background: rgba(34,168,153,.07);
    }}
    section[data-testid="stSidebar"] .stMarkdown h3 {{ color: {TEAL_ESCURO}; }}

    /* ALERTS */
    div[data-testid="stAlert"] {{ border-radius: 15px; }}

    /* DATAFRAME / JSON */
    div[data-testid="stDataFrame"] {{ border-radius: 16px; overflow: hidden; }}

    /* Hide default Streamlit decoration line, retain menu/share controls. */
    [data-testid="stDecoration"] {{ display:none; }}

    @media (max-width: 800px) {{
        .fb-hero {{ padding: 1.6rem 1.4rem; border-radius: 20px; }}
        .block-container {{ padding-top: 1.2rem; }}
        .fb-card, .fb-feature-card {{ min-height: auto; }}
    }}
</style>
"""


def aplicar_estilo():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(titulo: str, subtitulo: str = "", eyebrow: str = "FaithBloom AI · Editorial Studio"):
    titulo = escape(titulo)
    subtitulo = escape(subtitulo)
    eyebrow = escape(eyebrow)
    st.markdown(
        f"""
        <div class="fb-hero">
            <span class="fb-eyebrow">✦ {eyebrow}</span>
            <h1>{titulo}</h1>
            <p>{subtitulo}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(titulo: str, subtitulo: str = "", kicker: str = ""):
    kicker_html = f'<div class="kicker">{escape(kicker)}</div>' if kicker else ""
    subtitle_html = f"<p>{escape(subtitulo)}</p>" if subtitulo else ""
    st.markdown(
        f'<div class="fb-section">{kicker_html}<h2>{escape(titulo)}</h2>{subtitle_html}</div>',
        unsafe_allow_html=True,
    )


def card(titulo: str, descricao: str, pagina: str | None = None, label_botao: str = "Abrir →", icone: str = ""):
    """Card visual premium com navegação real opcional para uma página Streamlit."""
    icon_html = f'<div class="fb-feature-icon">{escape(icone)}</div>' if icone else ""
    st.markdown(
        f'<div class="fb-feature-card">{icon_html}<h4>{escape(titulo)}</h4><p>{escape(descricao)}</p></div>',
        unsafe_allow_html=True,
    )
    if pagina:
        st.page_link(pagina, label=label_botao, use_container_width=True)


def callout(titulo: str, texto: str, icone: str = "✦"):
    st.markdown(
        f'<div class="fb-callout"><strong>{escape(icone)} {escape(titulo)}</strong><p>{escape(texto)}</p></div>',
        unsafe_allow_html=True,
    )


def badge_status(pronto: bool) -> str:
    if pronto:
        return '<span class="fb-badge-pronto">✓ pronto</span>'
    return '<span class="fb-badge-andamento">◌ em andamento</span>'


def badge_neutral(texto: str) -> str:
    return f'<span class="fb-badge-neutral">{escape(texto)}</span>'

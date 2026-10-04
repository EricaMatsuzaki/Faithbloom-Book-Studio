"""FaithBloom landing entrypoint.

Jarvis is the official front door of the studio. The former dashboard remains
available as "Dashboard do Estúdio" in pages/02_🏠_Dashboard_do_Estudio.py.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="FaithBloom · Jarvis",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.switch_page("pages/00_🤖_Jarvis.py")

"""Jarvis Premium — interface canônica aprovada + conversa por voz/texto."""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from jarvis_assistant import inspect_project_state, interpret_request
from jarvis_conversation import (
    append_turn,
    detect_general_intent,
    detect_safe_navigation,
    enrich_follow_up,
    help_reply,
    looks_like_echo,
    strip_wake_word,
    thanks_reply,
)
from jarvis_push_to_talk import decode_recording, push_to_talk
from jarvis_voice import build_spoken_reply, synthesize_reply, transcribe_audio
from jarvis_weather import WMO_PT, extract_location, fetch_weather, is_weather_request

st.set_page_config(
    page_title="Jarvis · FaithBloom",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Nesta página, a própria arte aprovada contém sidebar/topbar. O chrome nativo do
# Streamlit é ocultado para preservar a composição visual canônica.
st.markdown(
    """
    <style>
    [data-testid="stSidebar"], [data-testid="collapsedControl"],
    header[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu,
    footer, .stDeployButton {display:none!important;visibility:hidden!important}
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        margin:0!important; padding:0!important; background:#f7fbff!important;
    }
    [data-testid="stMainBlockContainer"], .block-container {
        max-width:none!important; width:100%!important; padding:0!important; margin:0!important;
    }
    div[data-testid="stVerticalBlock"] {gap:0!important}
    .stAlert {margin:.35rem 1rem!important}
    </style>
    """,
    unsafe_allow_html=True,
)

NAV_PAGES = {
    "orchestrator": "pages/0_🤖_Orquestrador_FaithBloom.py",
    "create": "pages/1_📖_Criar_do_Zero.py",
    "resume": "pages/2_📚_Retomar_Livro.py",
    "characters": "pages/14_👥_Character_Universe.py",
    "library": "pages/15_📚_Biblioteca_Editorial.py",
    "project": "pages/27_🚀_Project_Hub.py",
    "gallery": "pages/8_🖼️_Galeria_e_Armazenamento.py",
    "review": "pages/5_🔍_Analisar_Livro.py",
}


def _audio_b64(path: str | None) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as file:
            return base64.b64encode(file.read()).decode("ascii")
    except OSError:
        return ""


def _speak_reply(reply: str) -> None:
    st.session_state["jarvis_voice_audio"] = ""
    st.session_state["jarvis_voice_audio_error"] = ""
    token = f"jarvis_{uuid.uuid4().hex[:10]}"
    try:
        st.session_state["jarvis_voice_audio"] = synthesize_reply(reply, name=token)
    except Exception as exc:
        # A conversa textual continua funcionando mesmo se o TTS estiver fora.
        st.session_state["jarvis_voice_audio_error"] = str(exc)
    st.session_state["jarvis_voice_reply_token"] = token


def _set_ui_error(message: str) -> None:
    st.session_state["jarvis_voice_reply"] = message
    st.session_state["jarvis_voice_audio"] = ""
    st.session_state["jarvis_voice_reply_token"] = f"err_{uuid.uuid4().hex[:10]}"
    st.session_state["jarvis_voice_stage"] = "error"


def _process_request(transcript: str, *, weather_location: str, project_progress: dict | None) -> None:
    """Mantém contexto e usa os módulos FaithBloom existentes sem duplicação."""
    raw = (transcript or "").strip()
    if not raw:
        raise ValueError("Não consegui entender a mensagem.")

    history = list(st.session_state.get("jarvis_conversation_history") or [])
    last_reply = st.session_state.get("jarvis_voice_reply", "")
    if looks_like_echo(raw, last_reply):
        st.session_state["jarvis_voice_stage"] = "listening"
        st.session_state["jarvis_echo_ignored"] = True
        return

    clean = enrich_follow_up(raw, history, default_weather_location=weather_location)
    clean = strip_wake_word(clean) or raw
    st.session_state["jarvis_voice_transcript"] = raw
    st.session_state["jarvis_request"] = clean
    st.session_state["jarvis_voice_stage"] = "executing"
    st.session_state["jarvis_echo_ignored"] = False

    general_intent = detect_general_intent(clean)
    navigation = detect_safe_navigation(clean)
    weather = is_weather_request(clean)
    intent = "editorial"
    metadata: dict = {}

    if general_intent == "help":
        intent, reply = "help", help_reply()
    elif general_intent == "thanks":
        intent, reply = "thanks", thanks_reply()
    elif general_intent == "project_status":
        intent = "project_status"
        reply = (project_progress or {}).get("message") or (
            "Ainda não encontrei um projeto ativo nesta sessão. Posso começar um novo quando você quiser."
        )
    elif navigation:
        intent = "navigation"
        st.session_state["jarvis_suggested_destination"] = navigation
        reply = f"Claro. Posso abrir {navigation['label']} para você."
    elif weather:
        intent = "weather"
        location = extract_location(clean) or (weather_location or "").strip()
        if location:
            metadata["location"] = location
            st.session_state["jarvis_last_weather_location"] = location
        reply = build_spoken_reply(
            clean,
            project_progress=project_progress,
            weather_location=location or weather_location,
            history=history,
            natural=False,
        )
    else:
        result = interpret_request(clean)
        st.session_state["jarvis_result"] = result
        reply = build_spoken_reply(
            clean,
            result=result,
            project_progress=project_progress,
            weather_location=weather_location,
            history=history,
            natural=True,
        )

    history = append_turn(history, "user", raw, intent=intent, metadata=metadata)
    history = append_turn(history, "assistant", reply, intent=intent, metadata=metadata)
    st.session_state["jarvis_conversation_history"] = history
    st.session_state["jarvis_voice_reply"] = reply
    _speak_reply(reply)
    st.session_state["jarvis_voice_stage"] = "done"


def _handle_audio(
    audio_bytes: bytes,
    fmt: str,
    language: str,
    weather_location: str,
    project_progress: dict | None,
) -> None:
    st.session_state["jarvis_voice_stage"] = "thinking"
    transcription = transcribe_audio(audio_bytes, fmt=fmt, language=language)
    _process_request(
        transcription["text"],
        weather_location=weather_location,
        project_progress=project_progress,
    )


def _greeting() -> str:
    timezone_name = os.environ.get("JARVIS_TIMEZONE", "Asia/Tokyo")
    try:
        now = datetime.now(ZoneInfo(timezone_name))
    except Exception:
        now = datetime.now()
    if now.hour < 12:
        opening = "Bom dia"
    elif now.hour < 18:
        opening = "Boa tarde"
    else:
        opening = "Boa noite"
    return f"{opening}, Erica! Posso ajudar com seus livros, personagens e revisões."


@st.cache_data(ttl=600, show_spinner=False)
def _weather_card(location: str) -> str:
    if not location.strip():
        return "Pronto para consultar"
    try:
        weather = fetch_weather(location)
        current = weather.get("current") or {}
        temp = current.get("temperature_2m")
        code = int(current.get("weather_code", -1))
        condition = WMO_PT.get(code, "condição variável")
        if temp is None:
            return condition.capitalize()
        return f"{float(temp):.0f}°C · {condition.capitalize()}"
    except Exception:
        return "Clima disponível por voz"


current_state = st.session_state.get("state")
project_progress = inspect_project_state(current_state) if current_state else None
language = st.session_state.get("jarvis_ptt_language", "pt")
weather_location = (
    st.session_state.get("jarvis_weather_location", "")
    or st.session_state.get("jarvis_last_weather_location", "")
)
reply = st.session_state.get("jarvis_voice_reply", "")
audio_path = st.session_state.get("jarvis_voice_audio", "")
reply_token = st.session_state.get("jarvis_voice_reply_token", "")

shell = push_to_talk(
    key="jarvis_push_to_talk_main",
    greeting=_greeting(),
    reply_text=reply,
    reply_audio=_audio_b64(audio_path),
    reply_token=reply_token,
    weather_status=_weather_card(weather_location),
    agenda_status="Ainda não conectada",
)

if shell is None:
    # Contingência para versões antigas do Streamlit; não cria outra interface.
    st.image("assets/jarvis_premium_ui_reference.jpg", use_container_width=True)
    st.warning("O componente interativo do Jarvis não carregou neste navegador.")
    st.stop()

# 1) Voz
recording_payload = getattr(shell, "recording", None)
try:
    decoded = decode_recording(recording_payload)
except Exception:
    decoded = None
    _set_ui_error("Não consegui abrir essa gravação. Tente falar novamente.")

if decoded:
    audio_bytes, fmt, recording_id = decoded
    if recording_id and recording_id != st.session_state.get("jarvis_last_recording_id"):
        st.session_state["jarvis_last_recording_id"] = recording_id
        try:
            _handle_audio(audio_bytes, fmt, language, weather_location, project_progress)
        except Exception:
            _set_ui_error("Não consegui entender essa fala. Tente novamente, falando um pouco mais perto do microfone.")
        st.rerun()

# 2) Texto digitado dentro da própria interface aprovada
typed_payload = getattr(shell, "typed_request", None)
if isinstance(typed_payload, dict):
    typed_id = str(typed_payload.get("id") or "")
    typed_text = str(typed_payload.get("text") or "").strip()
    if typed_id and typed_id != st.session_state.get("jarvis_last_typed_request_id"):
        st.session_state["jarvis_last_typed_request_id"] = typed_id
        try:
            _process_request(typed_text, weather_location=weather_location, project_progress=project_progress)
        except Exception:
            _set_ui_error("Não consegui concluir esse pedido agora. Tente novamente em instantes.")
        st.rerun()

# 3) Hotspots de navegação sobre a sidebar/cards da própria arte
nav_payload = getattr(shell, "navigation", None)
if isinstance(nav_payload, dict):
    nav_id = str(nav_payload.get("id") or "")
    destination = str(nav_payload.get("destination") or "")
    if nav_id and nav_id != st.session_state.get("jarvis_last_navigation_id"):
        st.session_state["jarvis_last_navigation_id"] = nav_id
        page = NAV_PAGES.get(destination)
        if page:
            st.switch_page(page)

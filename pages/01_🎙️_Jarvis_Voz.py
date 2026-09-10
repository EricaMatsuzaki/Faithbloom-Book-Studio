"""Jarvis Voice — premium FaithBloom interface and conversation experience."""
from __future__ import annotations

import base64
import os
import uuid

import streamlit as st

from estilo import aplicar_estilo
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
from jarvis_weather import extract_location, is_weather_request

st.set_page_config(page_title="Jarvis · FaithBloom", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")
aplicar_estilo()


def _audio_format(uploaded) -> str:
    mime = str(getattr(uploaded, "type", "") or "").lower()
    name = str(getattr(uploaded, "name", "") or "").lower()
    by_mime = {
        "audio/wav": "wav", "audio/x-wav": "wav", "audio/mpeg": "mp3", "audio/mp3": "mp3",
        "audio/flac": "flac", "audio/x-flac": "flac", "audio/mp4": "m4a", "audio/m4a": "m4a",
        "audio/x-m4a": "m4a", "audio/ogg": "ogg", "audio/webm": "webm", "audio/aac": "aac",
    }
    if mime in by_mime:
        return by_mime[mime]
    for ext in ("wav", "mp3", "flac", "m4a", "ogg", "webm", "aac"):
        if name.endswith(f".{ext}"):
            return ext
    return "wav"


def _audio_b64(path: str | None) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""


def _speak_reply(reply: str) -> None:
    st.session_state["jarvis_voice_audio"] = ""
    st.session_state["jarvis_voice_audio_error"] = ""
    name = f"jarvis_{uuid.uuid4().hex[:10]}"
    try:
        st.session_state["jarvis_voice_audio"] = synthesize_reply(reply, name=name)
    except Exception as exc:
        st.session_state["jarvis_voice_audio_error"] = str(exc)
    st.session_state["jarvis_voice_reply_token"] = name


def _process_request(transcript: str, *, weather_location: str, project_progress: dict | None) -> None:
    """Entende a fala, preserva contexto e usa resposta natural sem duplicar Studios."""
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
    st.session_state["jarvis_suggested_destination"] = None

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
        reply = (project_progress or {}).get("message") or "Ainda não encontrei um projeto ativo nesta sessão. Posso começar um novo quando você quiser."
    elif navigation:
        intent = "navigation"
        st.session_state["jarvis_suggested_destination"] = navigation
        reply = f"Claro. Deixei {navigation['label']} pronto para você abrir logo abaixo."
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


def _handle_audio(audio_bytes: bytes, fmt: str, language: str, weather_location: str, project_progress: dict | None) -> None:
    st.session_state["jarvis_voice_stage"] = "thinking"
    transcricao = transcribe_audio(audio_bytes, fmt=fmt, language=language)
    _process_request(transcricao["text"], weather_location=weather_location, project_progress=project_progress)


# A navegação automática do Streamlit continua disponível tecnicamente, mas é
# ocultada nesta tela para que o Jarvis tenha a organização visual do mockup.
st.markdown("""
<style>
[data-testid="stSidebarNav"]{display:none!important}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#fbfdff 0%,#f5f9ff 100%)!important;border-right:1px solid #e1ebf7}
[data-testid="stSidebar"] .block-container{padding-top:1.15rem!important}
.block-container{padding-top:.5rem!important;max-width:1460px!important;padding-left:1.35rem!important;padding-right:1.35rem!important}
header[data-testid="stHeader"]{background:transparent!important}
#MainMenu,footer{visibility:hidden}
.fb-topbar{height:66px;display:flex;align-items:center;justify-content:space-between;gap:20px;padding:0 4px 8px}.fb-top-title strong{display:block;font-size:25px;color:#102d59;line-height:1.05}.fb-top-title span{display:block;margin-top:5px;font-size:10px;letter-spacing:.22em;color:#7890b3;font-weight:700}.fb-top-actions{display:flex;align-items:center;gap:12px}.fb-search{min-width:250px;padding:11px 16px;border:1px solid #d9e6f5;border-radius:15px;background:#f7faff;color:#7e91ac;font-size:12px}.fb-bell{font-size:19px;color:#163c75}.fb-profile{display:flex;align-items:center;gap:9px;padding-left:10px;border-left:1px solid #e2e9f4}.fb-avatar{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#0e6fb8,#6e49d7);color:white;font-weight:900}.fb-profile-copy b{display:block;color:#17345e;font-size:13px}.fb-profile-copy small{color:#8090a7;font-size:10px}.fb-input-shell{margin-top:14px;padding:16px 18px;border:1px solid #dbe8f6;border-radius:20px;background:linear-gradient(135deg,#f7fcff,#f9f7ff);box-shadow:0 8px 28px rgba(56,93,145,.06)}.fb-section-label{text-align:center;color:#274f77;font-size:12px;font-weight:750;margin:3px 0 9px}.fb-quick-title{font-size:12px;font-weight:800;color:#375778;margin:17px 0 8px}.fb-footer{text-align:center;color:#a0b0c7;font-size:10px;letter-spacing:.02em;margin:22px 0 6px}.stPageLink a{border-radius:17px!important;border:1px solid #dce7f4!important;background:#fff!important;min-height:72px!important;box-shadow:0 7px 22px rgba(50,85,132,.06)!important}.stPageLink a:hover{border-color:#9dcdf2!important;box-shadow:0 10px 26px rgba(50,85,132,.11)!important}
@media(max-width:850px){.fb-search{display:none}.fb-profile-copy{display:none}.block-container{padding-left:.75rem!important;padding-right:.75rem!important}}
</style>
""", unsafe_allow_html=True)

# Sidebar premium, com os módulos existentes do FaithBloom — sem duplicação.
with st.sidebar:
    st.markdown("""
    <div style="padding:4px 2px 18px">
      <div style="font-size:25px;font-weight:850;color:#123461">💠 FaithBloom</div>
      <div style="font-size:8px;letter-spacing:.28em;color:#7f94b0;margin:4px 0 0 29px">IDEIAS QUE IMPACTAM</div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("PRINCIPAL")
    st.page_link("pages/00_🤖_Jarvis.py", label="💬  Jarvis")
    st.page_link("pages/0_🤖_Orquestrador_FaithBloom.py", label="🧭  Orquestrador FaithBloom")
    st.page_link("pages/01_🎙️_Jarvis_Voz.py", label="🎙️  Jarvis Voz")
    st.caption("CRIAÇÃO")
    st.page_link("pages/39_✍️_Historia_4_Estilos.py", label="📄  Criar do Zero")
    st.page_link("pages/15_📚_Biblioteca_Editorial.py", label="↶  Retomar Livro")
    st.caption("PROJETOS")
    st.page_link("pages/14_👥_Character_Universe.py", label="👥  Personagens")
    st.page_link("pages/15_📚_Biblioteca_Editorial.py", label="📖  Biblioteca Editorial")
    st.page_link("pages/12_🏭_Fila_de_Producao.py", label="🚀  Project Hub")
    st.caption("FERRAMENTAS")
    st.page_link("pages/11_🛡️_Custos_e_Seguranca.py", label="🛡️  Custos e Segurança")
    st.page_link("pages/12_🏭_Fila_de_Producao.py", label="📋  Fila de Produção")
    st.page_link("pages/13_✅_QA_Final_e_Release.py", label="✅  QA Final e Release")
    st.markdown("""
    <div style="margin-top:22px;padding:15px;border-radius:17px;background:linear-gradient(135deg,#f0f9ff,#f0f2ff);border:1px solid #dce9f6;color:#315274;font-size:11px">💠 &nbsp;Um mundo melhor<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;através de histórias.</div>
    """, unsafe_allow_html=True)

st.markdown("""
<div class="fb-topbar">
  <div class="fb-top-title"><strong>Jarvis</strong><span>SEU COMPANHEIRO INTELIGENTE DO FAITHBLOOM</span></div>
  <div class="fb-top-actions">
    <div class="fb-search">⌕ &nbsp; Pesquisar na FaithBloom...</div>
    <div class="fb-bell">♧</div>
    <div class="fb-profile"><div class="fb-avatar">E</div><div class="fb-profile-copy"><b>Erica</b><small>Escritora</small></div></div>
  </div>
</div>
""", unsafe_allow_html=True)

current_state = st.session_state.get("state")
project_progress = inspect_project_state(current_state) if current_state else None
language = st.session_state.get("jarvis_ptt_language", "pt")
weather_location = st.session_state.get("jarvis_weather_location", "") or st.session_state.get("jarvis_last_weather_location", "")
reply = st.session_state.get("jarvis_voice_reply", "")
audio_path = st.session_state.get("jarvis_voice_audio", "")
reply_token = st.session_state.get("jarvis_voice_reply_token", "")

greeting = "Olá, Erica! Que bom ter você aqui. Posso ajudar com seus livros, personagens, revisões e próximos passos."
ptt_result = push_to_talk(
    key="jarvis_push_to_talk_main",
    greeting=greeting,
    reply_text=reply,
    reply_audio=_audio_b64(audio_path),
    reply_token=reply_token,
)
ptt_payload = getattr(ptt_result, "recording", None) if ptt_result is not None else None

try:
    decoded = decode_recording(ptt_payload)
except Exception as exc:
    decoded = None
    st.error(f"Não consegui abrir a gravação: {exc}")

if decoded:
    audio_bytes, fmt, recording_id = decoded
    if recording_id and recording_id != st.session_state.get("jarvis_last_recording_id"):
        st.session_state["jarvis_last_recording_id"] = recording_id
        try:
            with st.spinner("Jarvis está entendendo e cuidando do seu pedido…"):
                _handle_audio(audio_bytes, fmt, language, weather_location, project_progress)
            st.rerun()
        except Exception as exc:
            st.session_state["jarvis_voice_stage"] = "error"
            st.error(f"Não consegui entender ou processar sua fala: {exc}")

if ptt_result is None:
    st.warning("O modo de voz avançado não carregou neste navegador. Use o campo de texto abaixo.")
if st.session_state.get("jarvis_echo_ignored"):
    st.caption("🔇 Ignorei um trecho que parecia ser a própria voz do Jarvis, para evitar resposta em loop.")

st.markdown('<div class="fb-input-shell"><div class="fb-section-label">⌨️ DIGITE SUA MENSAGEM PARA O JARVIS</div></div>', unsafe_allow_html=True)
with st.form("jarvis_direct_text", clear_on_submit=True):
    c_text, c_send = st.columns([7, 1.4])
    with c_text:
        typed_request = st.text_input("Mensagem", placeholder="Ex.: Jarvis, continue o livro da Mel…", label_visibility="collapsed")
    with c_send:
        send = st.form_submit_button("Enviar", use_container_width=True)
if send and typed_request.strip():
    try:
        with st.spinner("Jarvis está cuidando do seu pedido…"):
            _process_request(typed_request.strip(), weather_location=weather_location, project_progress=project_progress)
        st.rerun()
    except Exception as exc:
        st.error(f"Não consegui concluir o pedido: {exc}")

voice_error = st.session_state.get("jarvis_voice_audio_error", "")
if voice_error and reply:
    st.info("🔊 A resposta está pronta. Se a voz premium falhar, o navegador tenta falar a mesma resposta como contingência.")

history = list(st.session_state.get("jarvis_conversation_history") or [])
if history:
    with st.expander("💬 Conversa recente", expanded=False):
        for item in history[-8:]:
            who = "Você" if item.get("role") == "user" else "Jarvis"
            st.markdown(f"**{who}:** {item.get('text','')}")

navigation = st.session_state.get("jarvis_suggested_destination")
if navigation:
    st.page_link(navigation["page"], label=f"➡️ Abrir {navigation['label']}", use_container_width=True)

st.markdown('<div class="fb-quick-title">ATALHOS RÁPIDOS</div>', unsafe_allow_html=True)
q1, q2, q3 = st.columns(3)
with q1:
    st.page_link("pages/39_✍️_Historia_4_Estilos.py", label="📗  Criar livro\n\nDo conceito à estrutura, com apoio do Jarvis.", use_container_width=True)
with q2:
    st.page_link("pages/16_🩺_Book_Doctor.py", label="📄  Revisar projeto\n\nAnalise, melhore e receba sugestões.", use_container_width=True)
with q3:
    st.page_link("pages/12_🏭_Fila_de_Producao.py", label="☑️  Ver pendências\n\nRevisões, tarefas e próximos passos.", use_container_width=True)

with st.expander("⚙️ Opções e contingência", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        selected = st.selectbox("Idioma", ["pt", "en", "ja", "es"], format_func=lambda x: {"pt":"🇧🇷 Português","en":"🇺🇸 English","ja":"🇯🇵 日本語","es":"🇪🇸 Español"}[x], index=["pt","en","ja","es"].index(language), key="jarvis_voice_language_settings")
        st.session_state["jarvis_ptt_language"] = selected
    with c2:
        city = st.text_input("Cidade padrão para clima", value=weather_location, placeholder="Ex.: Toyohashi, Japan", key="jarvis_voice_city_settings")
        st.session_state["jarvis_weather_location"] = city.strip()
    uploaded = st.file_uploader("Se o microfone bloquear, envie um áudio", type=["wav","mp3","flac","m4a","ogg","webm","aac"], key="jarvis_audio_upload_fallback")
    if uploaded is not None and st.button("Processar áudio enviado", use_container_width=True, key="jarvis_voice_fallback_send"):
        try:
            _handle_audio(uploaded.getvalue(), _audio_format(uploaded), selected, city, project_progress)
            st.rerun()
        except Exception as exc:
            st.error(f"Não consegui concluir: {exc}")
    if voice_error:
        st.caption(f"Diagnóstico técnico da última voz premium: {voice_error}")

st.markdown('<div class="fb-footer">“Tecnologia a serviço do seu propósito.” &nbsp;&nbsp; · &nbsp;&nbsp; F A I T H B L O O M</div>', unsafe_allow_html=True)

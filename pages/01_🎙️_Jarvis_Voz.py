"""Jarvis Voice — premium robot-first conversation experience."""
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

st.set_page_config(page_title="Jarvis Premium · FaithBloom", page_icon="🤖", layout="wide")
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
        # A conversa não falha por causa do TTS; o componente usa voz nativa como fallback.
        st.session_state["jarvis_voice_audio_error"] = str(exc)
    st.session_state["jarvis_voice_reply_token"] = name


def _process_request(transcript: str, *, weather_location: str, project_progress: dict | None) -> None:
    """Processa conversa, contexto curto, eco e roteamento sem duplicar os Studios."""
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
    metadata = {}

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
        reply = build_spoken_reply(clean, project_progress=project_progress, weather_location=location or weather_location)
    else:
        result = interpret_request(clean)
        st.session_state["jarvis_result"] = result
        reply = build_spoken_reply(clean, result=result, project_progress=project_progress, weather_location=weather_location)

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


st.markdown("""
<style>
.block-container{padding-top:.75rem!important;max-width:1280px!important}
.fb-premium-head{display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;margin:.2rem 0 1rem}
.fb-brand h1{margin:0!important;font-size:clamp(1.8rem,3vw,2.7rem)!important;background:linear-gradient(90deg,#173d5a,#6556d8);-webkit-background-clip:text;color:transparent!important}
.fb-brand p{margin:.15rem 0 0;color:#68798c}.fb-status-row{display:flex;flex-wrap:wrap;gap:.45rem;justify-content:flex-end}
.fb-chip{padding:.38rem .7rem;border-radius:999px;background:rgba(255,255,255,.72);border:1px solid rgba(65,151,190,.16);box-shadow:0 6px 18px rgba(42,90,130,.07);font-size:.79rem;font-weight:750;color:#2a4860}
.fb-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.7rem;margin:.85rem 0 1rem}.fb-card{border-radius:18px;padding:.8rem .9rem;background:linear-gradient(135deg,rgba(255,255,255,.9),rgba(239,247,255,.8));border:1px solid rgba(63,151,198,.14);box-shadow:0 9px 24px rgba(35,75,110,.08)}
.fb-card b{display:block;color:#173b59;font-size:.9rem}.fb-card span{color:#758395;font-size:.76rem}.fb-section-title{text-align:center;margin:.8rem 0 .55rem;font-weight:850;color:#173b59}.fb-conversation-note{text-align:center;color:#60758a;font-size:.84rem;margin:.2rem 0 .7rem}.stExpander{margin-top:.65rem}
@media(max-width:760px){.fb-premium-head{display:block}.fb-status-row{justify-content:flex-start;margin-top:.7rem}.fb-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
<div class="fb-premium-head">
  <div class="fb-brand"><h1>Jarvis <span style="font-weight:400">Premium Futurista</span></h1><p>Seu companheiro inteligente do FaithBloom</p></div>
  <div class="fb-status-row"><span class="fb-chip">🟢 Online</span><span class="fb-chip">🎙️ Voz ativa</span><span class="fb-chip">🧠 Contexto curto</span><span class="fb-chip">🔇 Anti-eco</span></div>
</div>
<div class="fb-grid">
  <div class="fb-card"><b>🤖 Conversa natural</b><span>Jarvis pode aparecer em qualquer ponto da frase</span></div>
  <div class="fb-card"><b>💬 Follow-up</b><span>Continua assuntos recentes sem repetir tudo</span></div>
  <div class="fb-card"><b>📚 FaithBloom</b><span>Reutiliza seus Studios, Masters e Orquestrador</span></div>
  <div class="fb-card"><b>🛡️ Controle humano</b><span>Ações críticas continuam protegidas</span></div>
</div>
""", unsafe_allow_html=True)

current_state = st.session_state.get("state")
project_progress = inspect_project_state(current_state) if current_state else None
language = st.session_state.get("jarvis_ptt_language", "pt")
weather_location = st.session_state.get("jarvis_weather_location", "") or st.session_state.get("jarvis_last_weather_location", "")
reply = st.session_state.get("jarvis_voice_reply", "")
audio_path = st.session_state.get("jarvis_voice_audio", "")
reply_token = st.session_state.get("jarvis_voice_reply_token", "")

greeting = "Olá, Erica! Que bom ter você aqui. Eu sou o Jarvis. O que vamos fazer hoje?"
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
    st.warning("O modo de voz avançado não carregou neste navegador. Use o campo de texto ou abra as opções abaixo.")

if st.session_state.get("jarvis_echo_ignored"):
    st.caption("🔇 Ignorei um trecho que parecia ser a própria voz do Jarvis, para evitar resposta em loop.")

st.markdown('<div class="fb-section-title">Fale ou digite diretamente para o Jarvis</div>', unsafe_allow_html=True)
st.markdown('<div class="fb-conversation-note">Depois de um assunto, você pode continuar com frases curtas como “e amanhã?” sem repetir tudo.</div>', unsafe_allow_html=True)
typed_request = st.chat_input("Ex.: Jarvis, continue meu projeto atual…")
if typed_request:
    try:
        with st.spinner("Jarvis está cuidando do seu pedido…"):
            _process_request(typed_request, weather_location=weather_location, project_progress=project_progress)
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

st.markdown('<div class="fb-section-title">Atalhos rápidos</div>', unsafe_allow_html=True)
q1, q2, q3, q4 = st.columns(4)
with q1: st.page_link("pages/39_✍️_Historia_4_Estilos.py", label="✨ Criar uma história", use_container_width=True)
with q2: st.page_link("pages/14_👥_Character_Universe.py", label="👤 Personagens", use_container_width=True)
with q3: st.page_link("pages/15_📚_Biblioteca_Editorial.py", label="📚 Biblioteca", use_container_width=True)
with q4: st.page_link("pages/0_🤖_Orquestrador_FaithBloom.py", label="🧭 Orquestrador", use_container_width=True)

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

st.caption("Jarvis Premium · conversa curta com contexto, proteção contra eco e acesso aos módulos FaithBloom existentes. Nenhum código do projeto isair/jarvis foi copiado.")

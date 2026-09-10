"""Jarvis Voice — robot-first conversation experience."""
from __future__ import annotations

import base64
import os
import uuid

import streamlit as st

from estilo import aplicar_estilo
from jarvis_assistant import inspect_project_state, interpret_request
from jarvis_push_to_talk import decode_recording, push_to_talk
from jarvis_voice import build_spoken_reply, synthesize_reply, transcribe_audio
from jarvis_weather import is_weather_request

st.set_page_config(page_title="Jarvis · FaithBloom", page_icon="🤖", layout="centered")
aplicar_estilo()


def _audio_format(uploaded) -> str:
    mime=str(getattr(uploaded,"type","") or "").lower();name=str(getattr(uploaded,"name","") or "").lower()
    by_mime={"audio/wav":"wav","audio/x-wav":"wav","audio/mpeg":"mp3","audio/mp3":"mp3","audio/flac":"flac","audio/x-flac":"flac","audio/mp4":"m4a","audio/m4a":"m4a","audio/x-m4a":"m4a","audio/ogg":"ogg","audio/webm":"webm","audio/aac":"aac"}
    if mime in by_mime:return by_mime[mime]
    for ext in ("wav","mp3","flac","m4a","ogg","webm","aac"):
        if name.endswith(f".{ext}"):return ext
    return "wav"


def _audio_b64(path: str | None) -> str:
    if not path or not os.path.exists(path):return ""
    try:
        with open(path,"rb") as f:return base64.b64encode(f.read()).decode("ascii")
    except Exception:return ""


def _process_request(transcript: str, *, weather_location: str, project_progress: dict | None) -> None:
    transcript=(transcript or "").strip()
    if not transcript:raise ValueError("Não consegui entender a mensagem.")
    st.session_state["jarvis_voice_transcript"]=transcript
    st.session_state["jarvis_request"]=transcript
    st.session_state["jarvis_voice_stage"]="executing"
    weather=is_weather_request(transcript)
    result=None
    if not weather:
        result=interpret_request(transcript)
        st.session_state["jarvis_result"]=result
    reply=build_spoken_reply(transcript,result=result,project_progress=project_progress,weather_location=weather_location)
    st.session_state["jarvis_voice_reply"]=reply
    name=f"jarvis_{uuid.uuid4().hex[:10]}"
    audio_path=synthesize_reply(reply,name=name)
    st.session_state["jarvis_voice_audio"]=audio_path
    st.session_state["jarvis_voice_reply_token"]=name
    st.session_state["jarvis_voice_stage"]="done"


def _handle_audio(audio_bytes: bytes, fmt: str, language: str, weather_location: str, project_progress: dict | None) -> None:
    st.session_state["jarvis_voice_stage"]="thinking"
    transcricao=transcribe_audio(audio_bytes,fmt=fmt,language=language)
    _process_request(transcricao["text"],weather_location=weather_location,project_progress=project_progress)


# Minimal chrome: the robot is the product experience, not a form dashboard.
st.markdown("""
<style>
.block-container{padding-top:1.2rem!important;max-width:920px!important}.jarvis-top{text-align:center;margin:.15rem 0 .8rem}.jarvis-top h1{font-size:clamp(1.55rem,3vw,2.2rem)!important;margin:0;color:#15334d!important}.jarvis-top p{margin:.25rem 0 0;color:#687789}.jarvis-mini{display:inline-flex;gap:.45rem;align-items:center;padding:.32rem .7rem;border-radius:999px;background:rgba(31,116,121,.08);font-size:.8rem;font-weight:750;margin-top:.5rem}.jarvis-answer{border-radius:18px;padding:.9rem 1rem;background:rgba(34,168,153,.08);border:1px solid rgba(34,168,153,.15);line-height:1.5}.stExpander{margin-top:.7rem}
</style>
<div class="jarvis-top"><h1>🤖 Jarvis</h1><p>Seu companheiro inteligente do FaithBloom</p><span class="jarvis-mini">🟢 Online · 🎙️ Voz ativa · 🌦️ Clima conectado</span></div>
""",unsafe_allow_html=True)

current_state=st.session_state.get("state")
project_progress=inspect_project_state(current_state) if current_state else None
language=st.session_state.get("jarvis_ptt_language","pt")
weather_location=st.session_state.get("jarvis_weather_location","")
reply=st.session_state.get("jarvis_voice_reply","")
audio_path=st.session_state.get("jarvis_voice_audio","")
reply_token=st.session_state.get("jarvis_voice_reply_token","")

greeting="Olá, Erica! Que bom ter você aqui. Eu sou o Jarvis. O que vamos fazer hoje?"
ptt_result=push_to_talk(
    key="jarvis_push_to_talk_main",
    greeting=greeting,
    reply_text=reply,
    reply_audio=_audio_b64(audio_path),
    reply_token=reply_token,
)
ptt_payload=getattr(ptt_result,"recording",None) if ptt_result is not None else None

try:
    decoded=decode_recording(ptt_payload)
except Exception as exc:
    decoded=None;st.error(f"Não consegui abrir a gravação: {exc}")

if decoded:
    audio_bytes,fmt,recording_id=decoded
    if recording_id and recording_id!=st.session_state.get("jarvis_last_recording_id"):
        st.session_state["jarvis_last_recording_id"]=recording_id
        try:
            with st.spinner("Jarvis está entendendo seu pedido…"):
                _handle_audio(audio_bytes,fmt,language,weather_location,project_progress)
            st.rerun()
        except Exception as exc:
            st.session_state["jarvis_voice_stage"]="error"
            st.error(f"Não consegui concluir: {exc}")

if ptt_result is None:
    st.warning("O modo de voz avançado não carregou neste navegador. Abra as opções abaixo para usar o modo alternativo.")

transcript=st.session_state.get("jarvis_voice_transcript","")
if transcript:
    with st.expander("💬 Ver conversa",expanded=False):
        st.markdown(f"**Você:** {transcript}")
        if reply:st.markdown(f"**Jarvis:** {reply}")

with st.expander("⚙️ Opções e modo alternativo",expanded=False):
    c1,c2=st.columns(2)
    with c1:
        selected=st.selectbox("Idioma",["pt","en","ja","es"],format_func=lambda x:{"pt":"🇧🇷 Português","en":"🇺🇸 English","ja":"🇯🇵 日本語","es":"🇪🇸 Español"}[x],index=["pt","en","ja","es"].index(language),key="jarvis_voice_language_settings")
        st.session_state["jarvis_ptt_language"]=selected
    with c2:
        city=st.text_input("Cidade padrão para clima",value=weather_location,placeholder="Ex.: Toyohashi, Japan",key="jarvis_voice_city_settings")
        st.session_state["jarvis_weather_location"]=city.strip()
    st.caption("Use esta área só se o navegador bloquear o microfone do robô.")
    uploaded=st.file_uploader("Enviar áudio",type=["wav","mp3","flac","m4a","ogg","webm","aac"],key="jarvis_audio_upload_fallback")
    typed=st.text_input("Ou digite para testar",placeholder="Ex.: Jarvis, como está o tempo em Toyohashi?",key="jarvis_voice_typed_fallback")
    if st.button("Enviar pelo modo alternativo",use_container_width=True,key="jarvis_voice_fallback_send"):
        try:
            if typed.strip():_process_request(typed.strip(),weather_location=city,project_progress=project_progress)
            elif uploaded is not None:_handle_audio(uploaded.getvalue(),_audio_format(uploaded),selected,city,project_progress)
            else:raise ValueError("Envie um áudio ou digite uma mensagem.")
            st.rerun()
        except Exception as exc:st.error(f"Não consegui concluir: {exc}")

st.caption("Segure o coração do Jarvis para falar. Ao soltar, ele recebe a mensagem automaticamente. Ações críticas continuam exigindo sua aprovação.")

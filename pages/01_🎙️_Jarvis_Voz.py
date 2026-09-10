"""Conversa por voz do Jarvis — push-to-talk + STT + resposta falada + clima atual."""
from __future__ import annotations

import os
import uuid

import streamlit as st

from estilo import aplicar_estilo
from jarvis_assistant import inspect_project_state, interpret_request
from jarvis_push_to_talk import decode_recording, push_to_talk
from jarvis_voice import build_spoken_reply, synthesize_reply, transcribe_audio
from jarvis_weather import is_weather_request

st.set_page_config(page_title="Jarvis por Voz · FaithBloom", page_icon="🎙️", layout="wide")
aplicar_estilo()


def _audio_format(uploaded) -> str:
    """Descobre o formato real sem assumir WAV para todo tipo de entrada."""
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


def _process_request(transcript: str, *, weather_location: str, project_progress: dict | None) -> None:
    """Uma única rota de processamento para push-to-talk, upload e texto de contingência."""
    transcript = (transcript or "").strip()
    if not transcript:
        raise ValueError("Não encontrei uma mensagem para enviar ao Jarvis.")

    st.session_state["jarvis_voice_transcript"] = transcript
    st.session_state["jarvis_request"] = transcript
    st.session_state["jarvis_voice_stage"] = "executing"

    lower = transcript.casefold()
    weather = is_weather_request(transcript)
    result = None
    if not weather:
        result = interpret_request(transcript)
        st.session_state["jarvis_result"] = result

    reply = build_spoken_reply(
        transcript,
        result=result,
        project_progress=project_progress,
        weather_location=weather_location,
    )
    st.session_state["jarvis_voice_reply"] = reply

    name = f"jarvis_{uuid.uuid4().hex[:10]}"
    audio_path = synthesize_reply(reply, name=name)
    st.session_state["jarvis_voice_audio"] = audio_path
    st.session_state["jarvis_voice_stage"] = "done"

    if weather:
        st.session_state["jarvis_visual_expression"] = "normal"
    elif any(x in lower for x in ("incrível", "incrivel", "sensacional", "uau")):
        st.session_state["jarvis_visual_expression"] = "star"
    elif any(x in lower for x in ("amor", "carinho", "amizade", "família", "familia", "fé", "fe")):
        st.session_state["jarvis_visual_expression"] = "heart"
    else:
        st.session_state["jarvis_visual_expression"] = "normal"


def _handle_audio(audio_bytes: bytes, fmt: str, language: str, weather_location: str, project_progress: dict | None) -> None:
    st.session_state["jarvis_visual_expression"] = "thinking"
    st.session_state["jarvis_voice_stage"] = "thinking"
    transcricao = transcribe_audio(audio_bytes, fmt=fmt, language=language)
    _process_request(
        transcricao["text"],
        weather_location=weather_location,
        project_progress=project_progress,
    )


st.markdown(
    """
    <style>
    .jv-shell{border-radius:28px;padding:1.8rem 2rem;background:linear-gradient(125deg,rgba(13,39,62,.98),rgba(23,104,108,.96) 52%,rgba(77,67,151,.95));color:white;box-shadow:0 22px 60px rgba(25,72,102,.2);margin-bottom:1rem}
    .jv-shell h1{color:white!important;margin:.2rem 0 .4rem;font-size:clamp(2rem,4vw,3.2rem)}
    .jv-shell p{color:rgba(255,255,255,.86);max-width:850px;line-height:1.6;margin:0}
    .jv-bot{font-size:4rem;display:inline-block;animation:jvFloat 3.2s ease-in-out infinite;filter:drop-shadow(0 0 18px rgba(117,242,239,.35))}
    .jv-status{display:inline-block;margin:.8rem .35rem 0 0;padding:.28rem .7rem;border-radius:999px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);font-weight:700;font-size:.8rem}
    .jv-bubble{border-radius:20px 20px 20px 6px;padding:1rem 1.1rem;background:linear-gradient(135deg,rgba(34,168,153,.09),rgba(139,108,246,.08));border:1px solid rgba(34,168,153,.17);line-height:1.55;margin:.6rem 0}
    .jv-stage{border-radius:16px;padding:.7rem .9rem;background:rgba(34,168,153,.08);border:1px solid rgba(34,168,153,.15);font-weight:750;margin:.6rem 0}
    @keyframes jvFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
    </style>
    <div class="jv-shell">
      <div class="jv-bot">🤖🎙️</div>
      <h1>Jarvis por Voz</h1>
      <p>Segure o botão, fale e solte. Ao soltar, eu recebo sua mensagem automaticamente — sem botão separado para enviar.</p>
      <span class="jv-status">🎙️ Push-to-talk</span>
      <span class="jv-status">🌦️ Clima conectado</span>
      <span class="jv-status">👀 Aprovação em ações críticas</span>
    </div>
    """,
    unsafe_allow_html=True,
)

current_state = st.session_state.get("state")
project_progress = inspect_project_state(current_state) if current_state else None

left, right = st.columns([1.7, 1])
with left:
    st.markdown("### 🎙️ Fale com Jarvis")

    controls = st.columns([1, 1.4])
    with controls[0]:
        language = st.selectbox(
            "Idioma da fala",
            options=["pt", "en", "ja", "es"],
            format_func=lambda x: {"pt": "🇧🇷 Português", "en": "🇺🇸 English", "ja": "🇯🇵 日本語", "es": "🇪🇸 Español"}[x],
            index=0,
            key="jarvis_ptt_language",
        )
    with controls[1]:
        weather_location = st.text_input(
            "Cidade padrão para clima (opcional)",
            value=st.session_state.get("jarvis_weather_location", ""),
            placeholder="Ex.: Toyohashi, Japan",
            key="jarvis_ptt_weather_location",
        )
        st.session_state["jarvis_weather_location"] = weather_location.strip()

    ptt_result = push_to_talk(key="jarvis_push_to_talk_main")
    ptt_payload = getattr(ptt_result, "recording", None) if ptt_result is not None else None
    decoded = None
    try:
        decoded = decode_recording(ptt_payload)
    except Exception as exc:
        st.error(f"Não consegui abrir a gravação recebida: {exc}")

    if decoded:
        audio_bytes, fmt, recording_id = decoded
        if recording_id and recording_id != st.session_state.get("jarvis_last_recording_id"):
            st.session_state["jarvis_last_recording_id"] = recording_id
            try:
                with st.spinner("🧠 Jarvis está entendendo e executando sua solicitação..."):
                    _handle_audio(audio_bytes, fmt, language, weather_location, project_progress)
                st.success("✅ Concluído. Jarvis já preparou a resposta.")
            except Exception as exc:
                st.session_state["jarvis_visual_expression"] = "attention"
                st.session_state["jarvis_voice_stage"] = "error"
                st.error(f"Não consegui concluir a conversa por voz: {exc}")

    if ptt_result is None:
        st.warning("Seu Streamlit ainda não tem o componente push-to-talk moderno. Atualize o app; enquanto isso, use o modo alternativo abaixo.")

    stage = st.session_state.get("jarvis_voice_stage")
    if stage == "thinking":
        st.markdown("<div class='jv-stage'>🧠 Pensando…</div>", unsafe_allow_html=True)
    elif stage == "executing":
        st.markdown("<div class='jv-stage'>⚙️ Executando…</div>", unsafe_allow_html=True)
    elif stage == "done":
        st.markdown("<div class='jv-stage'>✅ Concluído · posso receber outro pedido.</div>", unsafe_allow_html=True)

    with st.expander("🛟 Modo alternativo, se o navegador bloquear o microfone"):
        uploaded_audio = st.file_uploader(
            "Enviar áudio do celular",
            type=["wav", "mp3", "flac", "m4a", "ogg", "webm", "aac"],
            key="jarvis_audio_upload_fallback",
        )
        typed_message = st.text_area(
            "Ou digite sua mensagem",
            key="jarvis_voice_typed_fallback",
            height=80,
            placeholder="Ex.: Jarvis, como está o tempo em Toyohashi?",
        )
        if st.button("Enviar pelo modo alternativo", use_container_width=True, key="jarvis_voice_fallback_send"):
            try:
                with st.spinner("Jarvis está processando..."):
                    if typed_message.strip():
                        _process_request(
                            typed_message.strip(),
                            weather_location=weather_location,
                            project_progress=project_progress,
                        )
                    elif uploaded_audio is not None:
                        data = uploaded_audio.getvalue()
                        if not data:
                            raise ValueError("O arquivo de áudio está vazio.")
                        _handle_audio(data, _audio_format(uploaded_audio), language, weather_location, project_progress)
                    else:
                        raise ValueError("Envie um áudio ou digite uma mensagem.")
                st.success("✅ Concluído.")
            except Exception as exc:
                st.session_state["jarvis_visual_expression"] = "attention"
                st.error(f"Não consegui concluir: {exc}")

    transcript = st.session_state.get("jarvis_voice_transcript")
    reply = st.session_state.get("jarvis_voice_reply")
    audio_path = st.session_state.get("jarvis_voice_audio")
    if transcript:
        st.markdown("### 🗣️ Você disse")
        st.markdown(f"<div class='jv-bubble'>{transcript}</div>", unsafe_allow_html=True)
    if reply:
        st.markdown("### 🤖 Jarvis respondeu")
        st.markdown(f"<div class='jv-bubble'><strong>Jarvis:</strong> {reply}</div>", unsafe_allow_html=True)
    if audio_path and os.path.exists(audio_path):
        st.audio(audio_path, format="audio/mp3", autoplay=True)
        st.caption("🔊 O Jarvis tenta responder automaticamente. Se o iPhone bloquear autoplay, toque em play uma vez.")

with right:
    with st.container(border=True):
        st.markdown("#### Agora funciona assim")
        st.write("👆 Segure o botão")
        st.write("🎙️ Fale normalmente")
        st.write("🤚 Solte para enviar automaticamente")
        st.write("🧠 Jarvis entende o pedido")
        st.write("⚙️ Executa o que for seguro/permitido")
        st.write("🔊 Volta com resposta falada")

    with st.container(border=True):
        st.markdown("#### O que ele já consegue fazer")
        st.caption(
            "Consultar clima em tempo real, entender pedidos editoriais, localizar o fluxo correto do FaithBloom e acompanhar o próximo checkpoint do projeto. "
            "Ações destrutivas, publicação e alterações de Masters continuam exigindo sua aprovação."
        )

    if project_progress:
        with st.container(border=True):
            st.markdown("#### 📚 Projeto atual")
            st.write(project_progress["title"])
            st.caption(project_progress["message"])

st.page_link("pages/00_🤖_Jarvis.py", label="← Voltar para a Home do Jarvis", use_container_width=True)
st.caption("Jarvis Voice · push-to-talk sobre STT/TTS e módulos FaithBloom existentes · praticidade sem perder o controle.")

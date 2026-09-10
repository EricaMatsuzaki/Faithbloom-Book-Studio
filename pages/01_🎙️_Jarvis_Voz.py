"""Conversa por voz do Jarvis — STT + resposta falada + clima atual."""
from __future__ import annotations

import os
import uuid

import streamlit as st

from estilo import aplicar_estilo
from jarvis_assistant import inspect_project_state, interpret_request
from jarvis_voice import build_spoken_reply, synthesize_reply, transcribe_audio
from jarvis_weather import is_weather_request

st.set_page_config(page_title="Jarvis por Voz · FaithBloom", page_icon="🎙️", layout="wide")
aplicar_estilo()

st.markdown(
    """
    <style>
    .jv-shell{border-radius:28px;padding:1.8rem 2rem;background:linear-gradient(125deg,rgba(13,39,62,.98),rgba(23,104,108,.96) 52%,rgba(77,67,151,.95));color:white;box-shadow:0 22px 60px rgba(25,72,102,.2);margin-bottom:1rem}
    .jv-shell h1{color:white!important;margin:.2rem 0 .4rem;font-size:clamp(2rem,4vw,3.2rem)}
    .jv-shell p{color:rgba(255,255,255,.86);max-width:850px;line-height:1.6;margin:0}
    .jv-bot{font-size:4rem;display:inline-block;animation:jvFloat 3.2s ease-in-out infinite;filter:drop-shadow(0 0 18px rgba(117,242,239,.35))}
    .jv-status{display:inline-block;margin:.8rem .35rem 0 0;padding:.28rem .7rem;border-radius:999px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);font-weight:700;font-size:.8rem}
    .jv-bubble{border-radius:20px 20px 20px 6px;padding:1rem 1.1rem;background:linear-gradient(135deg,rgba(34,168,153,.09),rgba(139,108,246,.08));border:1px solid rgba(34,168,153,.17);line-height:1.55;margin:.6rem 0}
    @keyframes jvFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
    </style>
    <div class="jv-shell">
      <div class="jv-bot">🤖🎙️</div>
      <h1>Jarvis por Voz</h1>
      <p>Fale naturalmente. Eu transcrevo sua mensagem, organizo pedidos do FaithBloom e também posso consultar o clima atual quando você pedir.</p>
      <span class="jv-status">🟢 Voz sob demanda</span>
      <span class="jv-status">🌦️ Clima conectado</span>
      <span class="jv-status">👀 Aprovação humana</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info(
    "🎙️ Sua gravação só é enviada para transcrição quando você toca em **Enviar para o Jarvis**. "
    "A resposta também fica escrita na tela. Algumas versões do navegador podem bloquear reprodução automática de áudio."
)

current_state = st.session_state.get("state")
project_progress = inspect_project_state(current_state) if current_state else None

left, right = st.columns([1.7, 1])
with left:
    st.markdown("### 🎤 Fale comigo")
    recording = st.audio_input("Grave sua mensagem para o Jarvis")

    controls = st.columns([1, 1.4])
    with controls[0]:
        language = st.selectbox(
            "Idioma da fala",
            options=["pt", "en", "ja", "es"],
            format_func=lambda x: {"pt": "🇧🇷 Português", "en": "🇺🇸 English", "ja": "🇯🇵 日本語", "es": "🇪🇸 Español"}[x],
            index=0,
        )
    with controls[1]:
        weather_location = st.text_input(
            "Cidade padrão para clima (opcional)",
            value=st.session_state.get("jarvis_weather_location", ""),
            placeholder="Ex.: Toyohashi, Japan",
            help="Se você disser a cidade na própria pergunta, ela terá prioridade. Este campo evita precisar repetir a cidade toda vez.",
        )
        st.session_state["jarvis_weather_location"] = weather_location.strip()

    st.caption("🌦️ Exemplos: “Jarvis, como está o tempo em Toyohashi?” · “Vai chover hoje?”")

    if st.button(
        "✨ Enviar para o Jarvis",
        type="primary",
        use_container_width=True,
        disabled=recording is None,
    ):
        try:
            st.session_state["jarvis_visual_expression"] = "thinking"
            with st.spinner("Jarvis está ouvindo e organizando sua mensagem..."):
                transcricao = transcribe_audio(recording.getvalue(), fmt="wav", language=language)
                transcript = transcricao["text"]
                st.session_state["jarvis_voice_transcript"] = transcript
                st.session_state["jarvis_request"] = transcript

                # Pedidos editoriais continuam usando exatamente o mesmo interpretador/roteador.
                lower = transcript.casefold()
                is_weather = is_weather_request(transcript)
                result = None
                if not is_weather:
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

                if is_weather:
                    st.session_state["jarvis_visual_expression"] = "normal"
                elif any(x in lower for x in ("incrível", "incrivel", "sensacional", "uau")):
                    st.session_state["jarvis_visual_expression"] = "star"
                elif any(x in lower for x in ("amor", "carinho", "amizade", "família", "familia", "fé", "fe")):
                    st.session_state["jarvis_visual_expression"] = "heart"
                else:
                    st.session_state["jarvis_visual_expression"] = "normal"
        except Exception as exc:
            st.session_state["jarvis_visual_expression"] = "attention"
            st.error(f"Não consegui concluir a conversa por voz: {exc}")

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
        st.caption("🔊 Se o navegador não tocar automaticamente, use o botão de play acima.")

with right:
    with st.container(border=True):
        st.markdown("#### Como funciona")
        st.write("🎙️ Você grava")
        st.write("📝 Jarvis transcreve")
        st.write("🌦️ Consulta clima quando solicitado")
        st.write("🧠 Usa o roteador editorial nos pedidos de projeto")
        st.write("🔊 Reutiliza o TTS do FaithBloom")
        st.write("👀 Você continua aprovando decisões importantes")

    with st.container(border=True):
        st.markdown("#### 🌦️ Clima")
        st.caption(
            "O clima usa Open-Meteo e geocodificação por cidade. Se você não disser a cidade na frase, "
            "o Jarvis usa a cidade padrão preenchida ao lado. A consulta de clima não usa créditos de LLM."
        )

    if project_progress:
        with st.container(border=True):
            st.markdown("#### 📚 Projeto atual")
            st.write(project_progress["title"])
            st.caption(project_progress["message"])

    with st.container(border=True):
        st.markdown("#### Segurança")
        st.caption(
            "A conversa por voz não publica livros, não promove Character Masters e não executa ações irreversíveis automaticamente. "
            "Chamadas de áudio continuam sujeitas ao controle de custos e anti-duplicação já existente."
        )

st.page_link("pages/00_🤖_Jarvis.py", label="← Voltar para a Home do Jarvis", use_container_width=True)
st.caption("Jarvis Voice MVP · STT + clima atual + TTS existente · praticidade sem perder o controle.")

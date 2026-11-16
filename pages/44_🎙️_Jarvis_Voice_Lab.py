"""Jarvis Voice Lab — comparação segura de vozes oficiais Google Cloud TTS."""
from __future__ import annotations

import os

import streamlit as st

from estilo import aplicar_estilo
from google_cloud_tts import (
    GOOGLE_TTS_API_KEY_ENV,
    GOOGLE_PT_BR_VOICES,
    GoogleCloudTTSError,
    available_voice_labels,
    synthesize_google_voice,
)

st.set_page_config(page_title="Jarvis Voice Lab · FaithBloom", page_icon="🎙️", layout="wide")
aplicar_estilo()

st.title("🎙️ Jarvis Voice Lab")
st.caption("Teste isolado de vozes oficiais do Google Cloud TTS. Nada aqui altera a voz principal do Jarvis.")

with st.expander("🔍 Verificação anti-duplicação", expanded=False):
    st.markdown(
        """
- **Já existe:** TTS principal do FaithBloom/OpenRouter.
- **Existe parcialmente:** Jarvis já sintetiza voz e reproduz MP3.
- **Novo somente onde necessário:** este laboratório chama Google Cloud TTS como provider experimental separado.
- **Não faz:** substituir Jarvis, alterar release, salvar segredo no código ou promover voz automaticamente.
"""
    )

try:
    secret_key = str(st.secrets.get(GOOGLE_TTS_API_KEY_ENV, "") or "").strip()
except Exception:
    secret_key = ""
env_key = (os.environ.get(GOOGLE_TTS_API_KEY_ENV) or "").strip()
api_key = secret_key or env_key

if api_key:
    st.success("Google Cloud TTS configurado para este ambiente. A chave permanece oculta.")
else:
    st.warning(
        "Para gerar os áudios, adicione `GOOGLE_CLOUD_TTS_API_KEY` nos Secrets do Streamlit Cloud. "
        "Não cole a chave na página nem no GitHub."
    )

DEFAULT_PHRASE = (
    "Boa noite, Erica. Estou online e pronto para ajudar. "
    "Posso consultar o clima, acompanhar seu projeto e responder com uma voz clara e natural."
)

left, right = st.columns([1.1, 0.9], gap="large")
with left:
    phrase = st.text_area(
        "Frase de teste",
        value=st.session_state.get("voice_lab_phrase", DEFAULT_PHRASE),
        height=150,
        max_chars=500,
    )
    st.session_state["voice_lab_phrase"] = phrase

    labels = available_voice_labels()
    selected = st.selectbox(
        "Voz Google para testar",
        labels,
        index=labels.index(st.session_state.get("voice_lab_selected", "Neural2-B"))
        if st.session_state.get("voice_lab_selected", "Neural2-B") in labels
        else 0,
        format_func=lambda label: f"{label} · {GOOGLE_PT_BR_VOICES[label]['family']} · masculino pt-BR",
    )
    st.session_state["voice_lab_selected"] = selected

    generate = st.button("▶️ Testar esta voz", type="primary", use_container_width=True, disabled=not bool(api_key))

    if generate:
        try:
            with st.spinner(f"Gerando {selected} no Google Cloud TTS…"):
                path = synthesize_google_voice(phrase, selected, api_key=api_key)
            st.session_state["voice_lab_audio_path"] = path
            st.session_state["voice_lab_audio_label"] = selected
            st.success(f"Áudio gerado com {selected}.")
        except (GoogleCloudTTSError, ValueError) as exc:
            st.session_state["voice_lab_audio_path"] = ""
            st.error(str(exc))

with right:
    st.subheader("Candidatos iniciais")
    for label, cfg in GOOGLE_PT_BR_VOICES.items():
        marker = "⭐" if label == selected else "•"
        st.markdown(f"{marker} **{label}**  \n`{cfg['name']}` · {cfg['family']} · {cfg['gender']}")

    st.info(
        "O nome ‘Antonio’ visto na extensão não foi identificado como uma voz oficial Google Cloud. "
        "Este laboratório serve para encontrar a voz oficial mais parecida, sem engenharia reversa da extensão."
    )

audio_path = str(st.session_state.get("voice_lab_audio_path") or "")
audio_label = str(st.session_state.get("voice_lab_audio_label") or "")
if audio_path and os.path.exists(audio_path):
    st.divider()
    st.subheader(f"🔊 Resultado · {audio_label}")
    st.audio(audio_path, format="audio/mpeg")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⭐ Marcar como favorita experimental", use_container_width=True):
            st.session_state["voice_lab_favorite"] = audio_label
            st.success(f"{audio_label} marcada como favorita experimental. Isso ainda não altera o Jarvis.")
    with c2:
        st.page_link("pages/00_🤖_Jarvis.py", label="🤖 Voltar ao Jarvis", use_container_width=True)

favorite = st.session_state.get("voice_lab_favorite")
if favorite:
    st.caption(f"Favorita experimental desta sessão: **{favorite}**")

st.divider()
st.markdown(
    """
### Como vamos decidir
Use a **mesma frase** nas quatro vozes e compare: naturalidade, gravidade, clareza, ritmo e sensação de assistente sofisticado. Só depois da sua escolha vamos considerar integrar a vencedora ao coração do Jarvis, mantendo fallback e testes.
"""
)

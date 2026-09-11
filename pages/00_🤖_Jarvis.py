"""Jarvis canônico — interface futurística, voz, texto e roteamento FaithBloom.

Esta página substitui a experiência MVP por uma única porta de entrada operacional.
Ela reutiliza os módulos existentes (STT/TTS, diálogo, clima e orquestração) e usa
controles nativos do Streamlit para evitar as falhas do componente visual achatado
observadas no Safari/iPhone.
"""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

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
from jarvis_voice import build_spoken_reply, synthesize_reply, transcribe_audio
from jarvis_weather import extract_location, is_weather_request

st.set_page_config(
    page_title="Jarvis · FaithBloom",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)
aplicar_estilo()

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
    return f"{opening}, Erica. Estou online e pronto para ajudar."


def _audio_format(mime: str | None) -> str:
    value = (mime or "").casefold()
    if "wav" in value:
        return "wav"
    if "mpeg" in value or "mp3" in value:
        return "mp3"
    if "mp4" in value or "m4a" in value:
        return "m4a"
    if "ogg" in value:
        return "ogg"
    return "webm"


def _set_stage(stage: str, message: str | None = None) -> None:
    st.session_state["jarvis_stage"] = stage
    if message is not None:
        st.session_state["jarvis_status_message"] = message


def _synthesize(reply: str) -> None:
    token = f"jarvis_{uuid.uuid4().hex[:10]}"
    st.session_state["jarvis_audio_path"] = ""
    st.session_state["jarvis_audio_error"] = ""
    try:
        st.session_state["jarvis_audio_path"] = synthesize_reply(reply, name=token)
    except Exception as exc:
        st.session_state["jarvis_audio_error"] = str(exc)
    st.session_state["jarvis_reply_token"] = token


def _process_request(text: str, *, project_progress: dict | None = None) -> str:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Mensagem vazia")

    history = list(st.session_state.get("jarvis_conversation_history") or [])
    last_reply = str(st.session_state.get("jarvis_reply") or "")
    if looks_like_echo(raw, last_reply):
        _set_stage("idle", "Eco ignorado. Pode continuar falando.")
        return last_reply

    default_weather_location = str(st.session_state.get("jarvis_last_weather_location") or "")
    clean = enrich_follow_up(raw, history, default_weather_location=default_weather_location)
    clean = strip_wake_word(clean) or raw
    st.session_state["jarvis_request"] = clean
    _set_stage("thinking", "Analisando seu pedido…")

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
            "Ainda não encontrei um projeto ativo nesta sessão. Posso ajudar a começar um novo."
        )
    elif navigation:
        intent = "navigation"
        st.session_state["jarvis_suggested_destination"] = navigation
        reply = f"Posso abrir {navigation['label']} para você. Use o atalho abaixo."
    elif weather:
        intent = "weather"
        location = extract_location(clean) or default_weather_location
        if location:
            metadata["location"] = location
            st.session_state["jarvis_last_weather_location"] = location
        reply = build_spoken_reply(
            clean,
            project_progress=project_progress,
            weather_location=location,
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
            weather_location=default_weather_location,
            history=history,
            natural=True,
        )

    history = append_turn(history, "user", raw, intent=intent, metadata=metadata)
    history = append_turn(history, "assistant", reply, intent=intent, metadata=metadata)
    st.session_state["jarvis_conversation_history"] = history
    st.session_state["jarvis_reply"] = reply
    _set_stage("speaking", "Resposta pronta.")
    _synthesize(reply)
    return reply


def _audio_data_url(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as fh:
            encoded = base64.b64encode(fh.read()).decode("ascii")
        return f"data:audio/mpeg;base64,{encoded}"
    except OSError:
        return ""


# Estado inicial
st.session_state.setdefault("jarvis_stage", "idle")
st.session_state.setdefault("jarvis_status_message", "Online")
st.session_state.setdefault("jarvis_reply", "")

current_state = st.session_state.get("state")
project_progress = inspect_project_state(current_state) if current_state else None
stage = st.session_state.get("jarvis_stage", "idle")
status_message = st.session_state.get("jarvis_status_message", "Online")
reply = st.session_state.get("jarvis_reply", "")

# UI futurística real — sem depender de uma imagem achatada/base64.
st.markdown(
    f"""
    <style>
    .fb-j-stage{{position:relative;overflow:hidden;min-height:610px;border-radius:34px;padding:clamp(22px,4vw,54px);background:
      radial-gradient(circle at 72% 23%,rgba(74,236,255,.17),transparent 19%),
      radial-gradient(circle at 76% 68%,rgba(121,91,255,.22),transparent 28%),
      linear-gradient(135deg,#071b2b 0%,#0c3f50 47%,#27265f 100%);color:#fff;border:1px solid rgba(125,238,255,.2);box-shadow:0 30px 90px rgba(13,48,78,.28)}}
    .fb-j-grid{{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(300px,.9fr);gap:28px;align-items:center;position:relative;z-index:2}}
    .fb-j-kicker{{display:inline-flex;padding:.42rem .78rem;border:1px solid rgba(161,244,255,.22);border-radius:999px;background:rgba(255,255,255,.06);font-size:.72rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase}}
    .fb-j-title{{font-size:clamp(3rem,7vw,6.7rem);line-height:.9;letter-spacing:-.055em;margin:.8rem 0 .55rem;font-weight:850;text-shadow:0 0 35px rgba(80,237,255,.12)}}
    .fb-j-copy{{font-size:clamp(1rem,1.8vw,1.28rem);line-height:1.65;color:rgba(242,250,255,.86);max-width:760px}}
    .fb-j-pills{{display:flex;gap:.55rem;flex-wrap:wrap;margin-top:1.2rem}}.fb-j-pill{{padding:.38rem .7rem;border-radius:999px;background:rgba(255,255,255,.075);border:1px solid rgba(255,255,255,.11);font-size:.76rem;font-weight:750}}
    .fb-j-status{{margin-top:1.05rem;display:flex;align-items:center;gap:.6rem;font-weight:700;color:#bdfaff}}.fb-j-dot{{width:10px;height:10px;border-radius:50%;background:#75f4ef;box-shadow:0 0 16px #75f4ef;animation:fbPulse 1.7s ease-in-out infinite}}
    .fb-j-robot-wrap{{position:relative;min-height:390px;display:grid;place-items:center;perspective:800px}}
    .fb-j-aura{{position:absolute;width:330px;height:330px;border-radius:50%;background:radial-gradient(circle,rgba(72,231,255,.18),rgba(100,83,255,.09) 45%,transparent 70%);filter:blur(3px);animation:fbAura 3s ease-in-out infinite}}
    .fb-j-floor{{position:absolute;bottom:25px;width:260px;height:54px;border-radius:50%;background:radial-gradient(ellipse,rgba(83,235,255,.28),transparent 67%);filter:blur(7px);animation:fbFloor 2.4s ease-in-out infinite}}
    .fb-j-robot{{position:relative;width:240px;height:330px;animation:fbFloat 4.2s ease-in-out infinite;filter:drop-shadow(0 26px 26px rgba(0,0,0,.22))}}
    .fb-j-ant{{position:absolute;left:50%;top:3px;transform:translateX(-50%);width:10px;height:44px;border-radius:12px;background:linear-gradient(#e6feff,#5ce5ed);box-shadow:0 0 18px rgba(92,229,237,.8)}}.fb-j-ant:before{{content:'';position:absolute;width:18px;height:18px;border-radius:50%;left:-4px;top:-9px;background:#8ff9f3;box-shadow:0 0 22px #8ff9f3}}
    .fb-j-head{{position:absolute;left:17px;top:45px;width:206px;height:150px;border-radius:49% 49% 43% 43%/43% 43% 52% 52%;background:linear-gradient(145deg,#fff,#d8e9f5 62%,#aabdd0);border:2px solid rgba(255,255,255,.95);box-shadow:inset -12px -14px 25px rgba(57,80,110,.16),0 0 35px rgba(83,237,255,.22)}}
    .fb-j-face{{position:absolute;inset:18px 17px 22px;border-radius:51px;background:radial-gradient(circle at 50% 23%,#18476a,#07131f 69%);border:2px solid #76f4ef;box-shadow:inset 0 0 30px rgba(80,219,245,.14),0 0 23px rgba(89,239,242,.36)}}
    .fb-j-eye{{position:absolute;top:47px;width:42px;height:15px;border-top:7px solid #77fff4;border-radius:50%;filter:drop-shadow(0 0 7px #77fff4);animation:fbBlink 5s infinite}}.fb-j-eye.l{{left:34px}}.fb-j-eye.r{{right:34px}}
    .fb-j-smile{{position:absolute;left:50%;bottom:24px;transform:translateX(-50%);width:40px;height:19px;border-bottom:6px solid #78fff5;border-radius:0 0 28px 28px;filter:drop-shadow(0 0 8px #78fff5)}}
    .fb-j-body{{position:absolute;left:51px;top:196px;width:138px;height:112px;border-radius:36px 36px 48px 48px;background:linear-gradient(145deg,#fff,#d9e8f2 67%,#a5b8cb);border:2px solid rgba(255,255,255,.92);box-shadow:inset -11px -13px 22px rgba(55,76,105,.15)}}
    .fb-j-core{{position:absolute;left:50%;top:25px;transform:translateX(-50%);width:60px;height:60px;border-radius:50%;display:grid;place-items:center;background:#071927;border:4px solid #66eef1;box-shadow:0 0 28px rgba(102,238,241,.72),inset 0 0 18px rgba(108,103,255,.22);font-size:27px;color:#ff7fd1;animation:fbCore 1.7s ease-in-out infinite}}
    .fb-j-arm{{position:absolute;top:214px;width:31px;height:82px;border-radius:20px;background:linear-gradient(#f6fbff,#a9bed0);border:1px solid rgba(255,255,255,.9)}}.fb-j-arm.l{{left:25px;transform:rotate(18deg)}}.fb-j-arm.r{{right:25px;transform:rotate(-18deg)}}
    .fb-j-scan{{position:absolute;left:20px;right:20px;top:58px;height:2px;background:linear-gradient(90deg,transparent,#75fff7,transparent);box-shadow:0 0 14px #75fff7;opacity:.0;animation:fbScan 4.8s ease-in-out infinite}}
    .fb-j-stage[data-state='thinking'] .fb-j-core{{animation-duration:.72s}}.fb-j-stage[data-state='thinking'] .fb-j-scan{{opacity:.9;animation-duration:1.25s}}.fb-j-stage[data-state='speaking'] .fb-j-core{{box-shadow:0 0 42px rgba(255,112,212,.75),0 0 28px rgba(102,238,241,.8)}}
    @keyframes fbFloat{{0%,100%{{transform:translateY(0) rotateY(-2deg)}}50%{{transform:translateY(-13px) rotateY(2deg)}}}}@keyframes fbAura{{0%,100%{{transform:scale(.96);opacity:.72}}50%{{transform:scale(1.06);opacity:1}}}}@keyframes fbFloor{{0%,100%{{transform:scaleX(.9);opacity:.55}}50%{{transform:scaleX(1.1);opacity:.9}}}}@keyframes fbPulse{{50%{{transform:scale(1.45);opacity:.55}}}}@keyframes fbCore{{0%,100%{{transform:translateX(-50%) scale(.94)}}50%{{transform:translateX(-50%) scale(1.07)}}}}@keyframes fbBlink{{0%,46%,50%,100%{{transform:scaleY(1)}}48%{{transform:scaleY(.08)}}}}@keyframes fbScan{{0%,55%{{transform:translateY(0);opacity:0}}60%{{opacity:.85}}80%{{transform:translateY(74px);opacity:.45}}100%{{opacity:0}}}}
    .fb-j-reply{{margin-top:1rem;padding:1rem 1.05rem;border-radius:18px;background:linear-gradient(135deg,rgba(43,222,218,.08),rgba(127,96,255,.08));border:1px solid rgba(100,227,239,.16);line-height:1.55}}
    @media(max-width:850px){{.fb-j-stage{{min-height:auto;padding:22px 18px;border-radius:24px}}.fb-j-grid{{grid-template-columns:1fr}}.fb-j-robot-wrap{{min-height:310px;order:-1}}.fb-j-robot{{transform:scale(.86)}}.fb-j-title{{font-size:3.25rem}}}}
    @media(prefers-reduced-motion:reduce){{.fb-j-robot,.fb-j-aura,.fb-j-floor,.fb-j-dot,.fb-j-core,.fb-j-eye,.fb-j-scan{{animation:none!important}}}}
    </style>
    <section class="fb-j-stage" data-state="{stage}">
      <div class="fb-j-grid">
        <div>
          <span class="fb-j-kicker">FaithBloom Intelligence · Jarvis Core</span>
          <div class="fb-j-title">JARVIS</div>
          <div class="fb-j-copy">{_greeting()} Fale ou escreva o que deseja criar, revisar, continuar ou diagnosticar. Eu coordeno os módulos existentes e mantenho as decisões críticas sob sua aprovação.</div>
          <div class="fb-j-pills"><span class="fb-j-pill">🟢 Online</span><span class="fb-j-pill">🎙️ Voz</span><span class="fb-j-pill">🧠 Contexto</span><span class="fb-j-pill">♻️ Anti-duplicação</span><span class="fb-j-pill">🔐 Security by Default</span></div>
          <div class="fb-j-status"><span class="fb-j-dot"></span>{status_message}</div>
          {f'<div class="fb-j-reply"><strong>Jarvis:</strong> {reply}</div>' if reply else ''}
        </div>
        <div class="fb-j-robot-wrap">
          <div class="fb-j-aura"></div><div class="fb-j-floor"></div>
          <div class="fb-j-robot" aria-label="Jarvis animado do FaithBloom">
            <div class="fb-j-ant"></div><div class="fb-j-head"><div class="fb-j-face"><div class="fb-j-eye l"></div><div class="fb-j-eye r"></div><div class="fb-j-smile"></div><div class="fb-j-scan"></div></div></div>
            <div class="fb-j-arm l"></div><div class="fb-j-arm r"></div><div class="fb-j-body"><div class="fb-j-core">♥</div></div>
          </div>
        </div>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown("### Converse com o Jarvis")
left, right = st.columns([1, 1], gap="large")

with left:
    audio = st.audio_input("🎙️ Fale com o Jarvis", key="jarvis_native_audio")
    if audio is not None:
        audio_bytes = audio.getvalue()
        digest = f"{len(audio_bytes)}:{hash(audio_bytes[:64])}"
        if digest != st.session_state.get("jarvis_last_native_audio"):
            st.session_state["jarvis_last_native_audio"] = digest
            try:
                _set_stage("thinking", "Transcrevendo sua fala…")
                transcript = transcribe_audio(audio_bytes, fmt=_audio_format(getattr(audio, "type", None)), language="pt")
                st.session_state["jarvis_last_transcript"] = transcript["text"]
                _process_request(transcript["text"], project_progress=project_progress)
                st.rerun()
            except Exception:
                _set_stage("error", "Não consegui processar a fala. Tente novamente ou use o campo de texto.")
                st.rerun()
    if st.session_state.get("jarvis_last_transcript"):
        st.caption(f"Você disse: {st.session_state['jarvis_last_transcript']}")

with right:
    with st.form("jarvis_text_form", clear_on_submit=True):
        typed = st.text_area("⌨️ Escreva para o Jarvis", height=112, placeholder="Ex.: Jarvis, continue meu livro da Mel…")
        submitted = st.form_submit_button("Enviar ao Jarvis", type="primary", use_container_width=True)
    if submitted and typed.strip():
        try:
            _process_request(typed, project_progress=project_progress)
            st.rerun()
        except Exception:
            _set_stage("error", "Não consegui concluir esse pedido agora. Tente novamente.")
            st.rerun()

# Reprodução da voz premium; o player nativo é confiável em iPhone/Safari.
audio_path = str(st.session_state.get("jarvis_audio_path") or "")
if audio_path and os.path.exists(audio_path):
    st.markdown("#### 🔊 Resposta em voz")
    st.audio(audio_path, format="audio/mpeg")
elif st.session_state.get("jarvis_audio_error") and reply:
    st.info("A resposta textual está pronta. A voz premium ficou indisponível nesta tentativa.")

# Atalho contextual sugerido pelo entendimento natural.
destination = st.session_state.get("jarvis_suggested_destination") or {}
page_key = destination.get("destination") or destination.get("id")
if page_key in NAV_PAGES:
    if st.button(f"Abrir {destination.get('label') or page_key}", type="primary", use_container_width=True):
        st.switch_page(NAV_PAGES[page_key])

st.markdown("### Ações rápidas")
cols = st.columns(4)
quick = [
    ("📖 Criar", "pages/1_📖_Criar_do_Zero.py"),
    ("📚 Retomar", "pages/2_📚_Retomar_Livro.py"),
    ("👥 Personagens", "pages/14_👥_Character_Universe.py"),
    ("🚀 Project Hub", "pages/27_🚀_Project_Hub.py"),
]
for col, (label, page) in zip(cols, quick):
    col.page_link(page, label=label, use_container_width=True)

with st.expander("🧠 O que este Jarvis já coordena", expanded=False):
    st.markdown(
        """
- Conversa natural por **texto e voz** com memória curta.
- Roteamento para o **Orquestrador FaithBloom** e módulos existentes.
- Consulta de **clima** quando solicitada.
- Continuidade de projeto e navegação segura.
- **Anti-duplicação**, aprovação humana e proteção de Masters.
- Resposta por **TTS premium** quando o provedor estiver disponível.
        """
    )

st.caption("Jarvis FaithBloom · interface canônica responsiva · voz original do FaithBloom, sem imitar ator ou personagem conhecido.")

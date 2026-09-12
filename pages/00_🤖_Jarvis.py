"""Jarvis canônico — voz, Daily Intelligence e roteamento FaithBloom.

O coração do robô é o controle principal: toque uma vez para falar e novamente
para terminar. O Jarvis abre com briefing automático diário e mantém rotas
instantâneas para data/hora, clima e agenda antes de recorrer ao diálogo de IA.
"""
from __future__ import annotations

import os
import time
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
from jarvis_daily_intelligence import (
    DEFAULT_LOCATION,
    DEFAULT_TIMEZONE,
    build_daily_intelligence,
    format_date_pt,
    greeting_for,
    local_now,
)
from jarvis_heart_mic import decode_recording, heart_mic
from jarvis_voice import build_spoken_reply, synthesize_reply, transcribe_audio
from jarvis_weather import extract_location, is_weather_request

st.set_page_config(page_title="Jarvis · FaithBloom", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")
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


def _now() -> datetime:
    return local_now(os.environ.get("JARVIS_TIMEZONE", DEFAULT_TIMEZONE))


def _greeting() -> str:
    now = _now()
    return f"{greeting_for(now)}, Erica. Estou online e pronto para ajudar."


def _set_stage(stage: str, message: str | None = None) -> None:
    st.session_state["jarvis_stage"] = stage
    if message is not None:
        st.session_state["jarvis_status_message"] = message


def _audio_mime(path: str) -> str:
    ext = os.path.splitext(path or "")[1].lower()
    if ext == ".wav":
        return "audio/wav"
    if ext == ".pcm":
        return "audio/pcm"
    return "audio/mpeg"


def _record_latency(name: str, seconds: float) -> None:
    metrics = dict(st.session_state.get("jarvis_latency_metrics") or {})
    metrics[name] = round(float(seconds), 3)
    st.session_state["jarvis_latency_metrics"] = metrics


def _synthesize(reply: str) -> bool:
    started = time.perf_counter()
    token = f"jarvis_{uuid.uuid4().hex[:12]}"
    st.session_state["jarvis_audio_path"] = ""
    st.session_state["jarvis_audio_error"] = ""
    try:
        path = synthesize_reply(reply, name=token)
        _record_latency("tts_s", time.perf_counter() - started)
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            st.session_state["jarvis_audio_path"] = path
            st.session_state["jarvis_reply_token"] = token
            _set_stage("speaking", "Resposta pronta — reproduzindo voz…")
            return True
        st.session_state["jarvis_audio_error"] = "O TTS não gerou um arquivo de áudio válido."
    except Exception as exc:
        _record_latency("tts_s", time.perf_counter() - started)
        st.session_state["jarvis_audio_error"] = str(exc)
    st.session_state["jarvis_reply_token"] = token
    _set_stage("idle", "Resposta pronta. A voz ficou indisponível nesta tentativa.")
    return False


def _is_datetime_request(text: str) -> bool:
    value = (text or "").casefold()
    return any(x in value for x in (
        "que dia é hoje", "que dia e hoje", "qual a data", "data de hoje",
        "que horas são", "que horas sao", "qual o horário", "qual o horario", "hora agora",
    ))


def _datetime_reply(text: str) -> str:
    now = _now()
    value = (text or "").casefold()
    if any(x in value for x in ("horas", "horário", "horario", "hora agora")):
        return f"Agora são {now.strftime('%H:%M')} no horário do Japão. Hoje é {format_date_pt(now)}."
    return f"Hoje é {format_date_pt(now)}. Agora são {now.strftime('%H:%M')} no horário do Japão."


def _is_calendar_request(text: str) -> bool:
    value = (text or "").casefold()
    return any(x in value for x in (
        "agenda", "calendário", "calendario", "compromisso", "compromissos",
        "o que tenho hoje", "próximo compromisso", "proximo compromisso",
    ))


def _calendar_reply() -> str:
    daily = dict(st.session_state.get("jarvis_daily_intelligence") or {})
    if not daily:
        return "Ainda não carreguei sua agenda de hoje."
    if not daily.get("calendar_connected"):
        return "Seu Google Calendar ainda precisa ser conectado ao FaithBloom para eu ler sua agenda automaticamente."
    events = daily.get("events") or []
    if not events:
        return "Você não tem compromissos no Google Calendar hoje."
    nxt = daily.get("next_event") or {}
    count = len(events)
    reply = f"Você tem {count} compromisso{'s' if count != 1 else ''} hoje."
    if nxt:
        if nxt.get("all_day"):
            reply += f" O próximo é {nxt.get('title', 'um compromisso')}, durante o dia todo."
        elif nxt.get("start"):
            reply += f" O próximo é {nxt.get('title', 'um compromisso')}, às {nxt['start'].strftime('%H:%M')}."
    return reply


def _process_request(text: str, *, project_progress: dict | None = None) -> str:
    started = time.perf_counter()
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Mensagem vazia")
    history = list(st.session_state.get("jarvis_conversation_history") or [])
    last_reply = str(st.session_state.get("jarvis_reply") or "")
    if looks_like_echo(raw, last_reply):
        _set_stage("idle", "Eco ignorado. Pode continuar falando.")
        return last_reply

    default_weather_location = str(st.session_state.get("jarvis_last_weather_location") or DEFAULT_LOCATION)
    clean = strip_wake_word(enrich_follow_up(raw, history, default_weather_location=default_weather_location)) or raw
    st.session_state["jarvis_request"] = clean
    _set_stage("thinking", "Analisando seu pedido…")

    general_intent = detect_general_intent(clean)
    navigation = detect_safe_navigation(clean)
    weather = is_weather_request(clean)
    intent = "editorial"
    metadata: dict = {}

    if _is_datetime_request(clean):
        intent, reply = "datetime", _datetime_reply(clean)
    elif _is_calendar_request(clean):
        intent, reply = "calendar", _calendar_reply()
    elif general_intent == "help":
        intent, reply = "help", help_reply()
    elif general_intent == "thanks":
        intent, reply = "thanks", thanks_reply()
    elif general_intent == "project_status":
        intent = "project_status"
        reply = (project_progress or {}).get("message") or "Ainda não encontrei um projeto ativo nesta sessão. Posso ajudar a começar um novo."
    elif navigation:
        intent = "navigation"
        st.session_state["jarvis_suggested_destination"] = navigation
        reply = f"Posso abrir {navigation['label']} para você. Use o atalho abaixo."
    elif weather:
        intent = "weather"
        location = extract_location(clean) or default_weather_location
        metadata["location"] = location
        st.session_state["jarvis_last_weather_location"] = location
        reply = build_spoken_reply(clean, project_progress=project_progress, weather_location=location, history=history, natural=False)
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

    _record_latency("logic_s", time.perf_counter() - started)
    history = append_turn(history, "user", raw, intent=intent, metadata=metadata)
    history = append_turn(history, "assistant", reply, intent=intent, metadata=metadata)
    st.session_state["jarvis_conversation_history"] = history
    st.session_state["jarvis_reply"] = reply
    _set_stage("thinking", "Gerando resposta em voz…")
    _synthesize(reply)
    _record_latency("request_total_s", time.perf_counter() - started)
    return reply


def _handle_audio(audio_bytes: bytes, fmt: str, recording_id: str, project_progress: dict | None) -> None:
    pipeline_started = time.perf_counter()
    if recording_id and recording_id == st.session_state.get("jarvis_last_heart_recording_id"):
        return
    st.session_state["jarvis_last_heart_recording_id"] = recording_id
    _set_stage("thinking", "Transcrevendo e preparando sua resposta…")
    stt_started = time.perf_counter()
    transcript = transcribe_audio(audio_bytes, fmt=fmt, language="pt")
    _record_latency("stt_s", time.perf_counter() - stt_started)
    text = str(transcript.get("text") or "").strip()
    st.session_state["jarvis_last_transcript"] = text
    _process_request(text, project_progress=project_progress)
    _record_latency("voice_pipeline_total_s", time.perf_counter() - pipeline_started)


def _run_automatic_daily_briefing() -> None:
    now = _now()
    today_key = now.strftime("%Y-%m-%d")
    if st.session_state.get("jarvis_daily_briefing_date") == today_key:
        return
    st.session_state["jarvis_daily_briefing_date"] = today_key
    _set_stage("thinking", "Preparando seu briefing diário…")
    try:
        daily = build_daily_intelligence(
            location=os.environ.get("JARVIS_BRIEFING_LOCATION", DEFAULT_LOCATION),
            timezone_name=os.environ.get("JARVIS_TIMEZONE", DEFAULT_TIMEZONE),
            now=now,
            include_calendar=True,
        )
        st.session_state["jarvis_daily_intelligence"] = daily
        st.session_state["jarvis_reply"] = daily["spoken"]
        for key, value in (daily.get("timings") or {}).items():
            _record_latency(f"daily_{key}", value)
        _set_stage("thinking", "Briefing pronto — preparando voz…")
        _synthesize(daily["spoken"])
    except Exception as exc:
        st.session_state["jarvis_daily_intelligence"] = {"error": str(exc), "calendar_connected": False}
        _set_stage("idle", "Jarvis online. O briefing automático ficou parcialmente indisponível.")


st.session_state.setdefault("jarvis_stage", "idle")
st.session_state.setdefault("jarvis_status_message", "Online")
st.session_state.setdefault("jarvis_reply", "")
st.session_state.setdefault("jarvis_autoplayed_token", "")
st.session_state.setdefault("jarvis_latency_metrics", {})

current_state = st.session_state.get("state")
project_progress = inspect_project_state(current_state) if current_state else None

# Automatic by design: once per local day in the current Streamlit session.
_run_automatic_daily_briefing()

stage = str(st.session_state.get("jarvis_stage") or "idle")
reply = str(st.session_state.get("jarvis_reply") or "")
audio_path = str(st.session_state.get("jarvis_audio_path") or "")
reply_token = str(st.session_state.get("jarvis_reply_token") or "")

st.html("""
<style>
div.st-key-jarvis_core{position:relative;overflow:hidden;border-radius:30px;padding:clamp(20px,4vw,46px);background:radial-gradient(circle at 72% 22%,rgba(74,236,255,.18),transparent 20%),radial-gradient(circle at 75% 70%,rgba(121,91,255,.22),transparent 28%),linear-gradient(135deg,#071b2b,#0c3f50 48%,#282660);color:#fff;border:1px solid rgba(125,238,255,.22);box-shadow:0 28px 80px rgba(13,48,78,.25)}
div.st-key-jarvis_core h1,div.st-key-jarvis_core h2,div.st-key-jarvis_core h3,div.st-key-jarvis_core p{color:#fff}.j-kicker{display:inline-flex;padding:.42rem .78rem;border:1px solid rgba(161,244,255,.24);border-radius:999px;background:rgba(255,255,255,.06);font-size:.72rem;font-weight:800;letter-spacing:.11em;text-transform:uppercase}.j-title{font-size:clamp(3rem,7vw,6rem);font-weight:850;line-height:.92;letter-spacing:-.055em;margin:.8rem 0 .6rem}.j-copy{font-size:clamp(1rem,1.7vw,1.22rem);line-height:1.62;color:rgba(242,250,255,.88);max-width:720px}.j-pills{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:1.15rem}.j-pill{padding:.38rem .68rem;border-radius:999px;background:rgba(255,255,255,.075);border:1px solid rgba(255,255,255,.12);font-size:.75rem;font-weight:750}.j-status{margin-top:1rem;color:#bdfaff;font-weight:750}.j-reply{margin-top:1rem;padding:1rem;border-radius:18px;background:linear-gradient(135deg,rgba(43,222,218,.08),rgba(127,96,255,.08));border:1px solid rgba(100,227,239,.16);line-height:1.55;color:#f7fdff}@media(max-width:800px){div.st-key-jarvis_core{padding:20px 17px;border-radius:22px}.j-title{font-size:3.05rem}}
</style>
""")

with st.container(key="jarvis_core"):
    left, right = st.columns([1.15, .85], gap="large")
    with left:
        st.html(
            f'<span class="j-kicker">FaithBloom Intelligence · Jarvis Core</span>'
            f'<div class="j-title">JARVIS</div>'
            f'<div class="j-copy">{_greeting()} O briefing diário é automático. Depois, toque no coração e fale normalmente.</div>'
            '<div class="j-pills"><span class="j-pill">🟢 Online</span><span class="j-pill">☀️ Daily Intelligence</span><span class="j-pill">❤️ Coração-microfone</span><span class="j-pill">🔊 Voz Charon</span><span class="j-pill">⚡ Rotas rápidas</span><span class="j-pill">🔐 Security by Default</span></div>'
            f'<div class="j-status">● {st.session_state.get("jarvis_status_message", "Online")}</div>'
            + (f'<div class="j-reply"><strong>Jarvis:</strong> {reply}</div>' if reply else "")
        )
    with right:
        heart = heart_mic(
            key="jarvis_heart_control",
            stage=stage,
            reply_text=reply,
            reply_audio="",
            reply_token=reply_token,
        )

if audio_path and os.path.exists(audio_path) and reply_token:
    if reply_token != st.session_state.get("jarvis_autoplayed_token"):
        st.audio(audio_path, format=_audio_mime(audio_path), autoplay=True)
        st.session_state["jarvis_autoplayed_token"] = reply_token

# Daily Intelligence: voice is intentionally concise; screen keeps the details.
daily = dict(st.session_state.get("jarvis_daily_intelligence") or {})
if daily:
    with st.expander("☀️ Briefing de hoje · detalhes", expanded=False):
        if daily.get("error"):
            st.warning("O briefing automático ficou parcialmente indisponível nesta abertura.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Data", daily.get("date", "—"))
            c2.metric("Hora local", daily.get("local_time", "—"))
            c3.metric("Calendário", "Conectado" if daily.get("calendar_connected") else "Aguardando conexão")
            st.markdown("**Clima**")
            st.write(daily.get("weather_detail") or "—")
            st.markdown("**Agenda de hoje**")
            st.text(daily.get("calendar_detail") or "Google Calendar ainda não conectado.")

recording_payload = getattr(heart, "recording", None) if heart is not None else None
decoded = None
try:
    decoded = decode_recording(recording_payload) if isinstance(recording_payload, dict) else None
except Exception:
    decoded = None
if decoded:
    audio_bytes, fmt, recording_id = decoded
    if recording_id and recording_id != st.session_state.get("jarvis_last_heart_recording_id"):
        try:
            _handle_audio(audio_bytes, fmt, recording_id, project_progress)
        except Exception:
            _set_stage("error", "Não consegui entender essa fala. Tente novamente ou use o texto.")
        st.rerun()

if heart is None:
    st.warning("O controle interativo do coração não está disponível neste runtime. Use o microfone de compatibilidade abaixo.")
    fallback = st.audio_input("🎙️ Microfone de compatibilidade", key="jarvis_native_audio_fallback")
    if fallback is not None:
        data = fallback.getvalue()
        fid = f"fallback-{len(data)}-{hash(data[:64])}"
        if fid != st.session_state.get("jarvis_last_heart_recording_id"):
            try:
                mime = str(getattr(fallback, "type", "") or "").casefold()
                fmt = "wav" if "wav" in mime else "m4a" if ("mp4" in mime or "m4a" in mime) else "webm"
                _handle_audio(data, fmt, fid, project_progress)
            except Exception:
                _set_stage("error", "Não consegui processar a gravação.")
            st.rerun()

if st.session_state.get("jarvis_last_transcript"):
    st.caption(f"🎙️ Você disse: {st.session_state['jarvis_last_transcript']}")

st.markdown("### Ou escreva para o Jarvis")
with st.form("jarvis_text_form", clear_on_submit=True):
    typed = st.text_area("Mensagem", height=100, placeholder="Ex.: Jarvis, qual é meu próximo compromisso?", label_visibility="collapsed")
    submitted = st.form_submit_button("Enviar ao Jarvis", type="primary", use_container_width=True)
if submitted and typed.strip():
    try:
        _process_request(typed, project_progress=project_progress)
    except Exception:
        _set_stage("error", "Não consegui concluir esse pedido agora. Tente novamente.")
    st.rerun()

if audio_path and os.path.exists(audio_path):
    with st.expander("🔊 Ouvir novamente", expanded=False):
        st.audio(audio_path, format=_audio_mime(audio_path))
elif st.session_state.get("jarvis_audio_error") and reply:
    st.error("A resposta textual está pronta, mas o TTS não gerou áudio nesta tentativa.")
    with st.expander("Diagnóstico da voz", expanded=False):
        st.code(str(st.session_state.get("jarvis_audio_error") or "Erro não informado."))

with st.expander("⚡ Diagnóstico de velocidade", expanded=False):
    metrics = dict(st.session_state.get("jarvis_latency_metrics") or {})
    if metrics:
        st.json(metrics)
    else:
        st.caption("As medições aparecem depois do primeiro briefing ou pedido.")

destination = st.session_state.get("jarvis_suggested_destination") or {}
page_key = destination.get("destination") or destination.get("id")
if page_key in NAV_PAGES and st.button(f"Abrir {destination.get('label') or page_key}", type="primary", use_container_width=True):
    st.switch_page(NAV_PAGES[page_key])

st.markdown("### Ações rápidas")
cols = st.columns(4)
for col, (label, page) in zip(cols, [
    ("📖 Criar", "pages/1_📖_Criar_do_Zero.py"),
    ("📚 Retomar", "pages/2_📚_Retomar_Livro.py"),
    ("👥 Personagens", "pages/14_👥_Character_Universe.py"),
    ("🚀 Project Hub", "pages/27_🚀_Project_Hub.py"),
]):
    col.page_link(page, label=label, use_container_width=True)

with st.expander("🧠 O que este Jarvis já coordena", expanded=False):
    st.markdown("""
- **Briefing automático diário** com data/hora local e clima.
- **Google Calendar somente leitura** quando OAuth estiver configurado no FaithBloom.
- **Próximo compromisso** e resumo da agenda do dia.
- **Rotas instantâneas** para data/hora, agenda e clima antes de usar IA pesada.
- **Medição de latência** de STT, lógica, TTS e briefing.
- Resposta curta por voz primeiro; detalhes ficam na tela.
- Continuidade de projeto, navegação segura, anti-duplicação e aprovação humana.
""")

st.caption("Jarvis FaithBloom · voz original Charon aprovada · sem imitar ator ou personagem conhecido.")

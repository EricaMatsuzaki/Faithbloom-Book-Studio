"""Jarvis canônico — voz, Daily Intelligence e roteamento FaithBloom.

O Jarvis separa conversa de ações editoriais. Pedidos acionáveis entram por uma
rota determinística e idempotente; conversa comum continua no assistente. Isso
evita que Revisão Completa dependa da presença de um PDF ou do comportamento da IA.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime

import streamlit as st

from estilo import aplicar_estilo
from faithbloom_cost_mode import COST_MODES, mode_config, mode_rows, set_cost_mode
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
    calendar_is_configured,
    calendar_write_is_enabled,
    execute_calendar_action,
    format_date_pt,
    greeting_for,
    local_now,
    prepare_calendar_action,
)
from jarvis_handoff_inbox import enqueue_handoff
from jarvis_heart_mic import decode_recording, heart_mic
from jarvis_multimodal import (
    SUPPORTED_UPLOAD_TYPES,
    build_handoff_package,
    handoff_summary,
    normalize_attachment,
    should_prepare_handoff,
)
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
    "book_doctor": "pages/16_🩺_Book_Doctor.py",
    "restoration": "pages/19_✨_Restoration_Studio.py",
    "audiobook": "pages/24_🎧_Audiobook_Studio.py",
    "project": "pages/27_🚀_Project_Hub.py",
    "assets": "pages/31_🖼️_Asset_Library_Media_Manager.py",
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


def _synthesize(reply: str, *, force: bool = False) -> bool:
    if not force and not bool(st.session_state.get("jarvis_auto_voice", False)):
        st.session_state["jarvis_audio_path"] = ""
        st.session_state["jarvis_audio_error"] = ""
        _set_stage("idle", "Resposta pronta em texto · voz sob demanda.")
        return False
    if not (reply or "").strip():
        return False
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
        "evento", "eventos", "o que tenho hoje", "próximo compromisso", "proximo compromisso",
    ))


def _is_confirmation(text: str) -> bool:
    value = " ".join((text or "").casefold().split())
    return value in {"sim", "sim pode", "sim pode fazer", "pode fazer", "confirma", "confirmo", "confirmar", "pode confirmar", "sim confirme"}


def _is_cancel(text: str) -> bool:
    value = " ".join((text or "").casefold().split())
    return value in {"não", "nao", "cancela", "cancelar", "não faça", "nao faca", "deixa pra lá", "deixa pra la"}


def _calendar_reply() -> str:
    daily = dict(st.session_state.get("jarvis_daily_intelligence") or {})
    if not daily:
        return "Ainda não carreguei sua agenda de hoje. Use ‘Gerar briefing agora’ ou peça sua agenda."
    if not daily.get("calendar_connected"):
        return "Seu Google Calendar ainda precisa ser conectado ao FaithBloom para eu acessar sua agenda."
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


def _refresh_daily_calendar() -> None:
    try:
        daily = build_daily_intelligence(
            location=os.environ.get("JARVIS_BRIEFING_LOCATION", DEFAULT_LOCATION),
            timezone_name=os.environ.get("JARVIS_TIMEZONE", DEFAULT_TIMEZONE),
            now=_now(),
            include_calendar=True,
        )
        st.session_state["jarvis_daily_intelligence"] = daily
    except Exception:
        pass


def _execute_pending_calendar_action() -> str:
    plan = dict(st.session_state.get("jarvis_pending_calendar_action") or {})
    if not plan:
        return "Não há nenhuma alteração de calendário aguardando confirmação."
    result = execute_calendar_action(plan, timezone_name=os.environ.get("JARVIS_TIMEZONE", DEFAULT_TIMEZONE))
    st.session_state.pop("jarvis_pending_calendar_action", None)
    _refresh_daily_calendar()
    when = result.get("start")
    time_text = when.strftime("%d/%m às %H:%M") if when else "no horário solicitado"
    verb = "Adicionei" if plan.get("action") == "create" else "Atualizei"
    return f"{verb} {result.get('title', 'o compromisso')} no seu Google Calendar para {time_text}."


def _prepare_multimodal_handoff(request: str, uploads: list[object]) -> dict[str, object]:
    attachments = []
    for uploaded in uploads:
        data = uploaded.getvalue()
        attachments.append(normalize_attachment(uploaded.name, getattr(uploaded, "type", ""), data))
    package = build_handoff_package(request, attachments)
    st.session_state["jarvis_pending_handoff"] = package
    st.session_state["jarvis_reply"] = package["spoken"]
    _set_stage("thinking", "Encaminhamento preparado — aguardando sua confirmação…")
    _synthesize(str(package["spoken"]))
    return package


def _confirm_handoff(package: dict[str, object]) -> None:
    # Inbox idempotente + slot legado para destinos que ainda o consomem.
    accepted = enqueue_handoff(st.session_state, package)
    st.session_state["jarvis_handoff_package"] = accepted
    st.session_state.pop("jarvis_pending_handoff", None)
    route = accepted.get("route") or {}
    st.session_state["jarvis_reply"] = f"Certo. Encaminhando para {route.get('label', 'o especialista responsável')}."
    _set_stage("idle", "Encaminhamento confirmado.")
    page = str(route.get("page") or "")
    if page:
        st.switch_page(page)


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
    pending = dict(st.session_state.get("jarvis_pending_calendar_action") or {})

    if pending and _is_confirmation(clean):
        intent = "calendar_write"
        try:
            reply = _execute_pending_calendar_action()
        except Exception as exc:
            reply = f"Não consegui concluir a alteração do calendário: {exc}"
    elif pending and _is_cancel(clean):
        intent = "calendar_write"
        st.session_state.pop("jarvis_pending_calendar_action", None)
        reply = "Certo. Cancelei essa alteração e não mexi no seu calendário."
    elif _is_datetime_request(clean):
        intent, reply = "datetime", _datetime_reply(clean)
    elif _is_calendar_request(clean):
        intent = "calendar"
        plan = prepare_calendar_action(clean, now=_now(), timezone_name=os.environ.get("JARVIS_TIMEZONE", DEFAULT_TIMEZONE))
        if plan is not None:
            intent = "calendar_write"
            if not calendar_is_configured():
                reply = "Seu Google Calendar ainda precisa ser conectado ao FaithBloom antes que eu possa adicionar ou alterar compromissos."
            elif not calendar_write_is_enabled():
                reply = "Seu calendário está conectado para leitura, mas a permissão de escrita ainda precisa ser habilitada. Não vou alterar nada sem essa autorização."
            elif not plan.get("ready"):
                reply = str(plan.get("message") or "Preciso de mais detalhes antes de preparar essa alteração.")
            else:
                st.session_state["jarvis_pending_calendar_action"] = plan
                reply = f"Entendi: {plan['summary']}. Quer que eu confirme essa alteração no Google Calendar?"
        else:
            reply = _calendar_reply()
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
    _set_stage("thinking", "Resposta pronta — verificando preferência de voz…")
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
    if should_prepare_handoff(text):
        _prepare_multimodal_handoff(text, [])
    else:
        _process_request(text, project_progress=project_progress)
    _record_latency("voice_pipeline_total_s", time.perf_counter() - pipeline_started)


def _run_daily_briefing() -> None:
    now = _now()
    _set_stage("thinking", "Preparando seu briefing…")
    try:
        daily = build_daily_intelligence(
            location=os.environ.get("JARVIS_BRIEFING_LOCATION", DEFAULT_LOCATION),
            timezone_name=os.environ.get("JARVIS_TIMEZONE", DEFAULT_TIMEZONE),
            now=now,
            include_calendar=True,
        )
        st.session_state["jarvis_daily_intelligence"] = daily
        st.session_state["jarvis_daily_briefing_date"] = now.strftime("%Y-%m-%d")
        st.session_state["jarvis_reply"] = daily["spoken"]
        for key, value in (daily.get("timings") or {}).items():
            _record_latency(f"daily_{key}", value)
        _set_stage("idle", "Briefing pronto. A voz só toca se você pedir.")
        _synthesize(daily["spoken"])
    except Exception as exc:
        st.session_state["jarvis_daily_intelligence"] = {"error": str(exc), "calendar_connected": False}
        _set_stage("idle", "Jarvis online. O briefing ficou parcialmente indisponível.")


st.session_state.setdefault("jarvis_stage", "idle")
st.session_state.setdefault("jarvis_status_message", "Online")
st.session_state.setdefault("jarvis_reply", "")
st.session_state.setdefault("jarvis_autoplayed_token", "")
st.session_state.setdefault("jarvis_latency_metrics", {})
st.session_state.setdefault("faithbloom_cost_mode", "economico")
st.session_state.setdefault("jarvis_auto_voice", False)
set_cost_mode(str(st.session_state.get("faithbloom_cost_mode") or "economico"))

current_state = st.session_state.get("state")
project_progress = inspect_project_state(current_state) if current_state else None

with st.expander("💸 Modo de IA e economia", expanded=True):
    mode_keys = ["economico", "balanceado", "premium"]
    current_mode = str(st.session_state.get("faithbloom_cost_mode") or "economico")
    selected_mode = st.radio(
        "Como o FaithBloom deve gastar IA?", mode_keys,
        index=mode_keys.index(current_mode) if current_mode in mode_keys else 0,
        format_func=lambda key: str(COST_MODES[key]["label"]), horizontal=True,
        key="faithbloom_cost_mode_selector",
    )
    if selected_mode != current_mode:
        st.session_state["faithbloom_cost_mode"] = set_cost_mode(selected_mode)
        cfg = mode_config(selected_mode)
        st.session_state["jarvis_auto_voice"] = bool(cfg.get("auto_voice", False))
        st.rerun()
    set_cost_mode(selected_mode)
    cfg = mode_config(selected_mode)
    st.success(f"Modo atual: {cfg['label']} — {cfg['description']}")
    st.caption(f"Ideal para: {cfg['ideal_for']} | Atenção: {cfg['tradeoff']}")
    st.markdown(f"**Jarvis/texto:** `{cfg['dialogue_model']}`  ·  **DNA visual/análise de personagem:** `{cfg['vision_model']}`")
    st.checkbox("🔊 Falar respostas automaticamente (TTS consome créditos)", key="jarvis_auto_voice", help="Desligado no modo Econômico. Você ainda pode gerar a voz manualmente para qualquer resposta.")
    briefing_col, info_col = st.columns([1, 2])
    if briefing_col.button("☀️ Gerar briefing agora", use_container_width=True):
        _run_daily_briefing(); st.rerun()
    info_col.caption("O briefing não roda mais ao atualizar/recarregar a página. Só é gerado quando você pedir.")
    with st.expander("Quando usar cada modo", expanded=False):
        for row in mode_rows():
            st.markdown(f"**{row['label']}**  \n• Jarvis: `{row['dialogue_model']}`  \n• Visão/DNA: `{row['vision_model']}`  \n• Melhor uso: {row['ideal_for']}  \n• Observação: {row['tradeoff']}")

stage = str(st.session_state.get("jarvis_stage") or "idle")
reply = str(st.session_state.get("jarvis_reply") or "")
audio_path = str(st.session_state.get("jarvis_audio_path") or "")
reply_token = str(st.session_state.get("jarvis_reply_token") or "")
active_cfg = mode_config()

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
            f'<div class="j-copy">{_greeting()} Briefing e voz automática ficam sob seu controle. Fale, escreva ou envie arquivos; eu preparo a rota para o especialista certo.</div>'
            f'<div class="j-pills"><span class="j-pill">🟢 Online</span><span class="j-pill">{active_cfg["label"]}</span><span class="j-pill">☀️ Briefing sob demanda</span><span class="j-pill">❤️ Coração-microfone</span><span class="j-pill">📎 Multimodal</span><span class="j-pill">🔊 Voz Charon</span><span class="j-pill">⚡ Rotas rápidas</span><span class="j-pill">📅 Calendar seguro</span><span class="j-pill">🔐 Security by Default</span></div>'
            f'<div class="j-status">● {st.session_state.get("jarvis_status_message", "Online")}</div>'
            + (f'<div class="j-reply"><strong>Jarvis:</strong> {reply}</div>' if reply else "")
        )
    with right:
        heart = heart_mic(key="jarvis_heart_control", stage=stage, reply_text=reply, reply_audio="", reply_token=reply_token)

if audio_path and os.path.exists(audio_path) and reply_token and reply_token != st.session_state.get("jarvis_autoplayed_token"):
    st.audio(audio_path, format=_audio_mime(audio_path), autoplay=True)
    st.session_state["jarvis_autoplayed_token"] = reply_token

if reply and not bool(st.session_state.get("jarvis_auto_voice", False)):
    if st.button("🔊 Ouvir esta resposta com Charon", use_container_width=False):
        _synthesize(reply, force=True); st.rerun()

daily = dict(st.session_state.get("jarvis_daily_intelligence") or {})
if daily:
    with st.expander("☀️ Briefing de hoje · detalhes", expanded=False):
        if daily.get("error"):
            st.warning("O briefing ficou parcialmente indisponível nesta tentativa.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Data", daily.get("date", "—")); c2.metric("Hora local", daily.get("local_time", "—"))
            calendar_label = "Leitura + escrita" if daily.get("calendar_write_enabled") else "Somente leitura" if daily.get("calendar_connected") else "Aguardando conexão"
            c3.metric("Calendário", calendar_label)
            st.markdown("**Clima**"); st.write(daily.get("weather_detail") or "—")
            st.markdown("**Agenda de hoje**"); st.text(daily.get("calendar_detail") or "Google Calendar ainda não conectado.")

pending_calendar = dict(st.session_state.get("jarvis_pending_calendar_action") or {})
if pending_calendar:
    st.info(f"📅 Aguardando sua confirmação: {pending_calendar.get('summary', 'alteração no calendário')}")
    confirm_col, cancel_col = st.columns(2)
    if confirm_col.button("✅ Confirmar no Google Calendar", type="primary", use_container_width=True):
        try:
            reply = _execute_pending_calendar_action(); st.session_state["jarvis_reply"] = reply
            _set_stage("thinking", "Alteração confirmada — resposta pronta."); _synthesize(reply)
        except Exception as exc:
            st.session_state["jarvis_reply"] = f"Não consegui concluir a alteração do calendário: {exc}"
            _set_stage("error", "Falha ao alterar o Google Calendar.")
        st.rerun()
    if cancel_col.button("Cancelar", use_container_width=True):
        st.session_state.pop("jarvis_pending_calendar_action", None)
        st.session_state["jarvis_reply"] = "Certo. Cancelei essa alteração e não mexi no seu calendário."
        _set_stage("idle", "Alteração cancelada."); st.rerun()

pending_handoff = dict(st.session_state.get("jarvis_pending_handoff") or {})
if pending_handoff:
    route = pending_handoff.get("route") or {}
    st.info(f"📦 Aguardando confirmação: {handoff_summary(pending_handoff)}")
    if pending_handoff.get("files"):
        st.caption("Arquivos: " + ", ".join(str(f.get("name") or "arquivo") for f in pending_handoff["files"]))
    elif pending_handoff.get("text_payload"):
        st.caption("Entrada: manuscrito em texto preservado para o handoff.")
    handoff_confirm, handoff_cancel = st.columns(2)
    if handoff_confirm.button(f"✅ Encaminhar para {route.get('label', 'especialista')}", type="primary", use_container_width=True):
        _confirm_handoff(pending_handoff)
    if handoff_cancel.button("Cancelar encaminhamento", use_container_width=True):
        st.session_state.pop("jarvis_pending_handoff", None)
        st.session_state["jarvis_reply"] = "Certo. Cancelei o encaminhamento e preservei os arquivos sem promovê-los a Master."
        _set_stage("idle", "Encaminhamento cancelado."); st.rerun()

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
        data = fallback.getvalue(); fid = f"fallback-{len(data)}-{hash(data[:64])}"
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

st.markdown("### Converse ou envie arquivos para o Jarvis")
uploads = st.file_uploader(
    "📎 Anexar imagens, PDF, documentos ou áudio", type=list(SUPPORTED_UPLOAD_TYPES),
    accept_multiple_files=True, key="jarvis_multimodal_uploads",
    help="Os anexos ficam no contexto da sessão. Nenhum upload vira Master automaticamente.",
)
if uploads:
    st.caption(f"{len(uploads)} arquivo{'s' if len(uploads) != 1 else ''} selecionado{'s' if len(uploads) != 1 else ''}.")

with st.form("jarvis_text_form", clear_on_submit=True):
    typed = st.text_area(
        "Mensagem", height=100,
        placeholder="Ex.: faça a Revisão Completa deste texto-base; revise este PDF; use esta imagem como referência…",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Enviar ao Jarvis", type="primary", use_container_width=True)
if submitted and (typed.strip() or uploads):
    try:
        # Regra central: arquivo OU ação editorial inequívoca = handoff. Texto de
        # conversa continua no Jarvis. Assim Revisão Completa funciona sem PDF.
        if uploads or should_prepare_handoff(typed):
            _prepare_multimodal_handoff(typed, list(uploads or []))
        else:
            _process_request(typed, project_progress=project_progress)
    except Exception as exc:
        st.session_state["jarvis_reply"] = f"Não consegui preparar esse pedido: {exc}"
        _set_stage("error", "Não consegui processar os anexos ou o pedido.")
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
    if metrics: st.json(metrics)
    else: st.caption("As medições aparecem depois do primeiro pedido ou briefing manual.")

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
- **Conversa × ação:** pedidos editoriais inequívocos usam rota determinística; conversa comum não dispara Studios.
- **Revisão Completa por texto:** manuscrito colado pode entrar no Book Doctor sem precisar virar PDF.
- **Handoff idempotente:** fingerprint evita duplicação acidental por rerun/duplo clique.
- **Briefing sob demanda**, modos de custo e voz sob controle.
- **Google Calendar** com confirmação explícita para escrita.
- **Entrada multimodal:** imagens, PDF, documentos e áudio.
- **Proteção de Masters:** nenhum anexo vira Master sem aprovação humana.
- **Rotas instantâneas** para data/hora, agenda e clima antes de IA pesada.
- **Medição de latência** de STT, lógica, TTS e briefing.
""")

st.caption("Jarvis FaithBloom · modo Econômico padrão · voz original Charon aprovada · sem imitar ator ou personagem conhecido.")

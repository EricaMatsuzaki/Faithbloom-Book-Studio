"""Jarvis canônico — voz, Daily Intelligence e roteamento FaithBloom.

O Jarvis separa conversa de ações editoriais. Pedidos acionáveis entram por uma
rota determinística e idempotente; conversa comum continua no assistente. Isso
evita que Revisão Completa dependa da presença de um PDF ou do comportamento da IA.
"""
from __future__ import annotations

import hashlib
import html as html_lib
import os
import time
import uuid
from datetime import datetime

import streamlit as st

import engenheiro_code_review
from estilo import aplicar_estilo
from integration_ux import PROJECT_CONTEXT_KEY
from painel_dados import ACTIONS, filter_projects, filter_actions, production_stages, jarvis_project_progress, project_status
from painel_projetos import available_projects, project_snapshot, project_path, searchable_projects, activate_project, open_project, project_cover_path
from painel_visual import render_banner, render_action_card
from faithbloom_cost_mode import COST_MODES, mode_config, mode_rows, set_cost_mode
from family_profiles import get_workspace_profile, list_workspace_profiles
from jarvis_assistant import interpret_request
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

st.set_page_config(page_title="Jarvis · FaithBloom", page_icon="🤖", layout="wide", initial_sidebar_state="auto")
aplicar_estilo()

NAV_PAGES = {
    "engineering": "pages/37_🧠_Agent_Skills_Bestseller_Readiness.py",
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


def _active_workspace_profile() -> dict | None:
    """Resolve o perfil pessoal ativo usado pela home/Jarvis.

    A sessão compartilha o mesmo profile_id do Dashboard. Se ainda não houver um
    perfil válido selecionado, usa o primeiro perfil ativo apenas como default de UX.
    """
    active_id = str(st.session_state.get("faithbloom_workspace_profile_id") or "")
    profiles = list_workspace_profiles()
    valid_ids = {str(p.get("id") or "") for p in profiles}
    if active_id and active_id not in valid_ids:
        for key in ("faithbloom_active_project", "state", "state_r", "state_c", "etapa_r", "etapa_c",
                    "jarvis_conversation_history", "jarvis_reply", "jarvis_audio_path", "jarvis_pending_handoff",
                    "jarvis_handoff_package", "jarvis_multimodal_uploads", "fb_home_profile"):
            st.session_state.pop(key, None)
    if not profiles:
        st.session_state.pop("faithbloom_workspace_profile_id", None)
        return None
    if active_id not in valid_ids:
        active_id = str(profiles[0].get("id") or "")
        st.session_state["faithbloom_workspace_profile_id"] = active_id
    return get_workspace_profile(active_id) or next(
        (p for p in profiles if str(p.get("id") or "") == active_id),
        None,
    )


def _active_profile_name() -> str:
    profile = _active_workspace_profile() or {}
    return str(profile.get("display_name") or "").strip()


def _greeting() -> str:
    now = _now()
    name = _active_profile_name()
    who = f", {name}" if name else ""
    return f"{greeting_for(now)}{who}. Estou online e pronto para ajudar."


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


def _acionar_engenheiro_automatico(descricao_do_bug: str, arquivo_suspeito: str) -> None:
    """Chamado quando o Jarvis encontra sozinho um erro técnico real (não um
    erro de negócio esperado, como "não entendi a fala"). Aciona o Engenheiro
    de Code Review Profundo em segundo plano, sem travar a experiência do
    usuário além do necessário. Nunca mescla nada sozinho — só investiga e,
    se tiver confiança alta, abre um PR Draft para revisão.

    Deduplicação: o mesmo erro (mesma descrição) só aciona o Engenheiro uma
    vez por sessão, para não abrir PRs repetidos por uma falha intermitente.
    """
    if not bool(st.session_state.get("jarvis_engenheiro_automatico", True)):
        return
    assinatura = hashlib.sha256(descricao_do_bug.encode("utf-8", errors="ignore")).hexdigest()[:16]
    ja_reportados = set(st.session_state.get("jarvis_engenheiro_reportados") or [])
    if assinatura in ja_reportados:
        return
    ja_reportados.add(assinatura)
    st.session_state["jarvis_engenheiro_reportados"] = ja_reportados

    try:
        resultado = engenheiro_code_review.investigar_e_corrigir(descricao_do_bug, arquivo_suspeito)
    except Exception as exc:
        resultado = engenheiro_code_review.ResultadoEngenheiro(
            False, f"O Engenheiro não conseguiu investigar: {exc}"
        )

    historico = list(st.session_state.get("jarvis_engenheiro_resultados") or [])
    historico.append({
        "descricao": descricao_do_bug,
        "arquivo": arquivo_suspeito,
        "sucesso": resultado.sucesso,
        "diagnostico": resultado.diagnostico,
        "resumo": resultado.resumo,
        "pr_url": resultado.pr_url,
        "motivo_bloqueio": resultado.motivo_bloqueio,
    })
    st.session_state["jarvis_engenheiro_resultados"] = historico[-10:]


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
        _acionar_engenheiro_automatico(
            f"Ao gerar voz para uma resposta do Jarvis, a geração de áudio falhou com este erro: {exc}",
            "jarvis_voice.py",
        )
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
    elif navigation and navigation.get("id") == "engineering":
        intent = "engineering"
        st.session_state["jarvis_suggested_destination"] = navigation
        st.session_state["engineering_request"] = clean
        reply = "Abra Engenharia e Skills para executar o diagnóstico técnico e a revisão profunda dos módulos selecionados."
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
st.session_state.setdefault("jarvis_engenheiro_automatico", True)
set_cost_mode(str(st.session_state.get("faithbloom_cost_mode") or "economico"))

active_workspace_profile = _active_workspace_profile()
active_workspace_profile_id = str((active_workspace_profile or {}).get("id") or "")
active_workspace_name = str((active_workspace_profile or {}).get("display_name") or "").strip()
home_catalog = available_projects(active_workspace_profile_id)
context_path = str((st.session_state.get(PROJECT_CONTEXT_KEY) or {}).get("storage_path") or "").removeprefix("fb://").strip("/")
active_home_project = next((item for item in home_catalog if project_path(item) == context_path), None)
active_kind = active_home_project.get("kind", "story") if active_home_project else "story"
session_path_key = "caminho_salvo_c" if active_kind == "coloring" else "caminho_salvo_r"
session_path = str(st.session_state.get(session_path_key) or "").removeprefix("fb://").strip("/")
if active_home_project:
    active_project_state = (st.session_state.get("state") or {}) if session_path == context_path else project_snapshot(context_path)
else:
    active_project_state = st.session_state.get("state") or {}
project_progress = jarvis_project_progress(active_project_state, active_kind) if active_project_state else None


def _change_home_profile() -> None:
    st.session_state["faithbloom_workspace_profile_id"] = st.session_state["fb_home_profile"]
    for key in (PROJECT_CONTEXT_KEY, "state", "state_r", "state_c", "etapa_r", "etapa_c",
                "jarvis_conversation_history", "jarvis_reply", "jarvis_reply_token", "jarvis_audio_path",
                "jarvis_pending_handoff", "jarvis_handoff_package", "jarvis_multimodal_uploads",
                "jarvis_request", "jarvis_last_transcript", "jarvis_suggested_destination"):
        st.session_state.pop(key, None)


def _heading(title: str, subtitle: str, icon: str) -> None:
    st.markdown(
        f'<div class="fb-panel-heading"><span class="fb-panel-icon" aria-hidden="true">{icon}</span>'
        f'<div><h2>{html_lib.escape(title)}</h2><p>{html_lib.escape(subtitle)}</p></div></div>',
        unsafe_allow_html=True,
    )


def _render_ai_controls() -> None:
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
        st.checkbox(
            "🛠️ Deixar o Engenheiro investigar e corrigir erros técnicos sozinho",
            key="jarvis_engenheiro_automatico",
            help="Quando o Jarvis encontrar uma falha técnica real (não uma resposta que ele apenas não entendeu), o Engenheiro de Code Review Profundo investiga e, se tiver confiança alta, abre um Pull Request Draft para você revisar. Nunca mescla sozinho.",
        )
        briefing_col, info_col = st.columns([1, 2])
        if briefing_col.button("☀️ Gerar briefing agora", use_container_width=True):
            _run_daily_briefing(); st.rerun()
        info_col.caption("O briefing não roda mais ao atualizar/recarregar a página. Só é gerado quando você pedir.")
        with st.expander("Quando usar cada modo", expanded=False):
            for row in mode_rows():
                st.markdown(f"**{row['label']}**  \n• Jarvis: `{row['dialogue_model']}`  \n• Visão/DNA: `{row['vision_model']}`  \n• Melhor uso: {row['ideal_for']}  \n• Observação: {row['tradeoff']}")



with st.container(key="fb_topbar"):
    top_search, gift_col, plan_col, bell_col, top_profile = st.columns([4.9, .38, 1.18, .38, 1.15], gap="small")
    with top_search:
        home_search = st.text_input("Buscar no FaithBloom", placeholder="🔎 Buscar projetos, personagens, histórias…",
                                    label_visibility="collapsed", key="faithbloom_home_search")
    with gift_col:
        with st.popover("", icon=":material/featured_seasonal_and_gifts:", help="Inspiração e movimento do banner"):
            st.write("Uma pequena história pode florescer em uma grande lição. 💜")
            st.toggle("Movimento do banner", key="fb_banner_motion", value=True)
            st.page_link("pages/39_✍️_Historia_4_Estilos.py", label="Criar uma nova história →")
    with plan_col:
        with st.popover("👑 Plano Profissional"):
            st.write("Seu estúdio reúne criação, personagens, ilustrações, revisão e publicação.")
            st.page_link("pages/38_🪄_Prompt_Mestre_Studio.py", label="Abrir Prompt-Mestre Studio →")
    with bell_col:
        with st.popover("", icon=":material/notifications:", help="Acompanhar seu projeto"):
            st.write((project_progress or {}).get("message") or "Escolha um projeto para acompanhar sua produção.")
    with top_profile:
        with st.popover((active_workspace_name.split()[0] if active_workspace_name else "Erica") + " ⌄", icon=":material/account_circle:"):
            profiles = list_workspace_profiles()
            if profiles:
                ids = [str(profile["id"]) for profile in profiles]
                st.selectbox("Perfil do workspace", ids,
                             index=ids.index(active_workspace_profile_id) if active_workspace_profile_id in ids else 0,
                             format_func=lambda pid: next(profile["display_name"] for profile in profiles if str(profile["id"]) == pid),
                             key="fb_home_profile", on_change=_change_home_profile)
            st.page_link("pages/34_🏠_Perfis_e_Dashboard.py", label="Gerenciar perfis →")

found_projects = filter_projects(searchable_projects(home_catalog), home_search) if home_search.strip() else home_catalog
found_actions = filter_actions(home_search) if home_search.strip() else ACTIONS

stage = str(st.session_state.get("jarvis_stage") or "idle")
reply = str(st.session_state.get("jarvis_reply") or "")
audio_path = str(st.session_state.get("jarvis_audio_path") or "")
reply_token = str(st.session_state.get("jarvis_reply_token") or "")
active_cfg = mode_config()

st.html("""
<style>
.block-container{max-width:1500px!important;padding-top:.7rem!important}
div.st-key-fb_live_jarvis_closed{display:none}
div[class*="st-key-fb_live_jarvis_"]{border-radius:20px;border:1px solid #ece5f4;padding:.8rem;background:radial-gradient(ellipse at 30% 20%,#fff6dc,transparent 60%),linear-gradient(120deg,#fff0f4,#eafaff 55%,#f6efff)}
.fb-live-bubble{width:fit-content;max-width:95%;margin:0 auto;padding:.7rem 1.4rem;text-align:center;border-radius:24px;background:#ffffffed;color:#8b3edb;font-size:1.15rem;font-weight:750}
.st-key-fb_assistant_heading{margin-top:.3rem}.st-key-fb_assistant_heading [data-testid="stHorizontalBlock"]{align-items:center}
.st-key-jarvis_compose{border:1px solid #ececf6;border-radius:16px;padding:.4rem .8rem;background:white}
.st-key-jarvis_compose [data-testid="stForm"]{border:0;padding:0}
.st-key-jarvis_compose textarea{min-height:48px!important;border-radius:12px!important}
.st-key-jarvis_compose [data-testid="stFormSubmitButton"] button{min-height:48px;border:0;background:linear-gradient(110deg,#ff90b7,#b35cf6 60%,#8677ff);color:white;border-radius:12px}
.st-key-jarvis_compose [data-testid="stHorizontalBlock"]{align-items:center}
.st-key-fb_voice_toggle [data-testid="stCheckbox"] p{font-size:.75rem;color:#7b43ca}
.st-key-fb_home_responses{border:1px solid #ececf6;border-radius:16px;padding:.65rem;background:white}
@media(max-width:768px){
 div.st-key-fb_live_jarvis_closed{display:block}
 .st-key-fb_voice_toggle{display:none}
 .st-key-jarvis_compose form [data-testid="stHorizontalBlock"]{flex-wrap:wrap}
 .st-key-jarvis_compose form [data-testid="stColumn"]{min-width:100%!important}
}
</style>
""")

render_banner(active_workspace_name or "Erica", show_motion_control=False)
voice_open = bool(st.session_state.get("fb_voice_open", False))
with st.container(key="fb_live_jarvis_open" if voice_open else "fb_live_jarvis_closed"):
    st.html('<div class="fb-live-bubble">Oi! Eu sou o Jarvis.<br>Vamos criar juntos? 💜</div>')
    heart = heart_mic(key="jarvis_heart_control", stage=stage, reply_text=reply,
                      reply_audio="", reply_token=reply_token, compact=False)

if home_search.strip():
    st.caption(f"{len(found_projects)} projeto(s) e {len(found_actions)} ferramenta(s) para “{home_search.strip()}”.")
for offset in range(0, len(found_actions), 3):
    cols = st.columns(3, gap="small")
    for col, action in zip(cols, found_actions[offset:offset + 3]):
        with col:
            render_action_card(**action)

with st.container(key="fb_assistant_heading"):
    title_col, voice_col = st.columns([5, 1.1], gap="small")
    with title_col:
        _heading("Prefere só contar o que precisa?", "Converse ou envie arquivos para o Jarvis. Ele entende sua ideia e já organiza os próximos passos.", "💬")
    with voice_col:
        with st.container(key="fb_voice_toggle"):
            st.toggle("🎙️ Falar", key="fb_voice_open")

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

with st.container(key="jarvis_compose"):
    attach_col, form_col = st.columns([.42, 6.1], gap="small")
    with attach_col:
        with st.popover("📎", use_container_width=True):
            uploads = st.file_uploader(
                "Anexar imagens, PDF, documentos ou áudio",
                type=list(SUPPORTED_UPLOAD_TYPES),
                accept_multiple_files=True,
                key="jarvis_multimodal_uploads",
                help="Os anexos ficam no contexto da sessão. Nenhum upload vira Master automaticamente.",
            )
            if uploads:
                st.caption(f"{len(uploads)} arquivo{'s' if len(uploads) != 1 else ''} selecionado{'s' if len(uploads) != 1 else ''}.")
    with form_col:
        with st.form("jarvis_text_form", clear_on_submit=True):
            msg_col, send_col = st.columns([5.2, 1.35], gap="small")
            with msg_col:
                typed = st.text_area(
                    "Mensagem",
                    height=48,
                    placeholder="Escreva sua mensagem ou envie arquivos (PDF, imagens, etc.)…",
                    label_visibility="collapsed",
                )
            with send_col:
                submitted = st.form_submit_button("✨ Enviar para o Jarvis", type="primary", use_container_width=True)
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

history = list(st.session_state.get("jarvis_conversation_history") or [])
if history or reply:
    with st.container(key="fb_home_responses"):
        for turn in history[-4:]:
            with st.chat_message("user" if turn.get("role") == "user" else "assistant", avatar="💜" if turn.get("role") != "user" else None):
                st.write(str(turn.get("text") or ""))
        if reply and (not history or str(history[-1].get("text") or "") != reply):
            with st.chat_message("assistant", avatar="💜"):
                st.write(reply)

if audio_path and os.path.exists(audio_path):
    with st.expander("🔊 Ouvir novamente", expanded=False):
        st.audio(audio_path, format=_audio_mime(audio_path))
elif st.session_state.get("jarvis_audio_error") and reply:
    st.error("A resposta textual está pronta, mas o TTS não gerou áudio nesta tentativa.")
    with st.expander("Diagnóstico da voz", expanded=False):
        st.code(str(st.session_state.get("jarvis_audio_error") or "Erro não informado."))

engenheiro_resultados = list(st.session_state.get("jarvis_engenheiro_resultados") or [])
if engenheiro_resultados:
    with st.expander("🛠️ O Engenheiro agiu sozinho nesta sessão", expanded=False):
        for item in reversed(engenheiro_resultados):
            if item["sucesso"]:
                st.success(f"PR aberto: {item['resumo'] or item['diagnostico']}")
                st.markdown(f"[Ver o Pull Request →]({item['pr_url']})")
            else:
                st.caption(f"Investigado, sem correção automática: {item['diagnostico']}")
                if item.get("motivo_bloqueio"):
                    st.caption(item["motivo_bloqueio"])

destination = st.session_state.get("jarvis_suggested_destination") or {}
page_key = destination.get("destination") or destination.get("id")
if page_key in NAV_PAGES and st.button(f"Abrir {destination.get('label') or page_key}", type="primary", use_container_width=True):
    st.switch_page(NAV_PAGES[page_key])

projects_col, status_col = st.columns([2.65, 1], gap="small")
with projects_col:
    with st.container(key="fb_recent"):
        title_col, all_col = st.columns([4, 1])
        with title_col:
            _heading("Projetos recentes", "Seus livros e histórias em um só lugar.", "▣")
        with all_col:
            st.page_link("pages/53_📁_Meus_Projetos.py", label="Ver todos →", use_container_width=True)
        recent = found_projects if home_search.strip() else found_projects[:4]
        if not recent:
            st.markdown('<div class="fb-empty-project"><h3>Uma nova história começa aqui 💜</h3><p>Seus projetos salvos vão aparecer neste espaço.</p></div>', unsafe_allow_html=True)
            if not home_search.strip():
                st.page_link("pages/39_✍️_Historia_4_Estilos.py", label="Criar meu primeiro livro →")
        for offset in range(0, len(recent), 4):
            cols = st.columns(4, gap="small")
            for col, item in zip(cols, recent[offset:offset + 4]):
                with col:
                    path = project_path(item)
                    data = project_snapshot(path)
                    with st.container(key=f"fb_project_{uuid.uuid5(uuid.NAMESPACE_URL, path).hex}"):
                        cover = project_cover_path(data)
                        if cover:
                            st.image(cover, use_container_width=True)
                        else:
                            st.markdown(f'<div class="fb-book-placeholder" aria-hidden="true"><span>✦</span><b>{html_lib.escape(item.get("titulo") or "Meu livro")}</b><span>📖</span></div>', unsafe_allow_html=True)
                        status_label, status_kind = project_status(item, data)
                        st.markdown(f'<span class="fb-project-badge">{html_lib.escape(status_label)}</span><h3 class="fb-project-title">{html_lib.escape(item.get("titulo") or "Sem título")}</h3>', unsafe_allow_html=True)
                        st.caption(item.get("colecao") or item.get("tema_geral") or "Projeto FaithBloom")
                        if st.button("✓ Selecionado" if path == context_path else "Selecionar", key=f"fb_select_{path}", use_container_width=True):
                            activate_project(item, active_workspace_profile_id)
                            st.rerun()
                        if st.button("Abrir →", key=f"fb_open_{path}", use_container_width=True):
                            open_project(item, active_workspace_profile_id)

with status_col:
    with st.container(key="fb_production"):
        _heading("Status da produção", "Acompanhe o progresso do seu livro.", "▥")
        if active_home_project:
            st.caption(active_home_project.get("titulo") or "Projeto ativo")
        stages = production_stages(active_project_state, active_kind)
        labels = {"concluido": "Concluído", "em_andamento": "Em andamento", "pendente": "Pendente"}
        lines = []
        for idx, item in enumerate(stages, 1):
            state_label = item["status"]
            lines.append(f'<li class="fb-stage fb-stage-{state_label}" title="{html_lib.escape(item["detail"], quote=True)}"><span class="fb-stage-number">{idx}</span><span class="fb-stage-label">{html_lib.escape(item["label"])}</span><span class="fb-stage-status">{labels[state_label]}</span></li>')
        st.markdown('<ol class="fb-stage-list">' + "".join(lines) + '</ol>', unsafe_allow_html=True)
        if active_home_project:
            if st.button("Ver detalhes →", key="fb_progress_details", use_container_width=True):
                open_project(active_home_project, active_workspace_profile_id)
        else:
            st.caption("Selecione um projeto para acompanhar as etapas.")

with st.expander("⚙️ Preferências do Jarvis e modo de IA", expanded=False):
    _render_ai_controls()
    metrics = dict(st.session_state.get("jarvis_latency_metrics") or {})
    if metrics:
        with st.expander("⚡ Diagnóstico de velocidade", expanded=False):
            st.json(metrics)

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
- **Engenheiro de plantão:** falhas técnicas reais (não erros de entendimento) podem virar um PR de correção automaticamente, sempre aguardando sua revisão.
""")

st.caption("Jarvis FaithBloom · modo Econômico padrão · voz original Charon aprovada · sem imitar ator ou personagem conhecido.")

"""Jarvis canônico — voz, Daily Intelligence e roteamento FaithBloom.

O Jarvis separa conversa de ações editoriais. Pedidos acionáveis entram por uma
rota determinística e idempotente; conversa comum continua no assistente. Isso
evita que Revisão Completa dependa da presença de um PDF ou do comportamento da IA.
"""
from __future__ import annotations

import base64
import hashlib
import html as html_lib
import mimetypes
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

import engenheiro_code_review
from armazenamento import carregar_livro, carregar_livro_colorir, listar_livros, listar_livros_colorir
from character_universe import buscar_personagens_por_nome, carregar_personagem_oficial
from estilo import aplicar_estilo
from faithbloom_cost_mode import COST_MODES, mode_config, mode_rows, set_cost_mode
from family_profiles import get_workspace_profile, list_workspace_profiles, visible_project_cards
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
    profiles = list_workspace_profiles()
    if not profiles:
        return None
    active_id = str(st.session_state.get("faithbloom_workspace_profile_id") or "")
    valid_ids = {str(p.get("id") or "") for p in profiles}
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


CANONICAL_HOME_COLLECTION = "Pequenas Histórias, Grandes Lições"


def _canonical_character(name: str) -> dict:
    candidates = buscar_personagens_por_nome(name, incluir_arquivados=False)
    if not candidates:
        return {}
    chosen = next(
        (x for x in candidates if str(x.get("colecao") or "").strip() == CANONICAL_HOME_COLLECTION),
        candidates[0],
    )
    try:
        return carregar_personagem_oficial(str(chosen.get("id") or ""))
    except Exception:
        return {}


def _character_master_path(name: str) -> str:
    personagem = _canonical_character(name)
    master = str(personagem.get("color_master") or "").strip()
    if master and (master.startswith(("http://", "https://")) or os.path.exists(master)):
        return master
    for ref in personagem.get("reference_pack") or []:
        if not isinstance(ref, dict):
            continue
        for field in ("asset", "caminho_arquivo", "path", "storage_uri", "uri"):
            value = str(ref.get(field) or "").strip()
            if value and (value.startswith(("http://", "https://")) or os.path.exists(value)):
                return value
    return ""


def _image_data_uri(path: str) -> str:
    value = str(path or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "data:")):
        return value
    try:
        data = Path(value).read_bytes()
    except Exception:
        return ""
    mime = mimetypes.guess_type(value)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _home_project_title(item: dict) -> str:
    return str(item.get("titulo") or item.get("tema_geral") or "Projeto FaithBloom").strip()


def _is_home_project(item: dict) -> bool:
    """Esconde artefatos técnicos do dashboard principal sem apagar nada."""
    title = _home_project_title(item).casefold()
    technical_markers = ("teste ", "teste_", "test ", "persistência supabase", "persistencia supabase", "diagnóstico", "diagnostico")
    return bool(title) and not any(marker in title for marker in technical_markers)


def _load_home_project(item: dict) -> dict:
    try:
        if item.get("kind") == "coloring":
            return carregar_livro_colorir(str(item.get("storage_path") or item.get("arquivo") or ""))
        return carregar_livro(
            str(item.get("colecao") or ""),
            str(item.get("storage_path") or item.get("arquivo") or ""),
        )
    except Exception:
        return {}


def _project_cover_path(data: dict) -> str:
    candidates = [
        data.get("arte_capa_frontal"),
        data.get("capa_ebook"),
        data.get("capa_fisica_preview"),
        data.get("capa_fisica_wrap"),
        data.get("imagem_capa"),
        data.get("cover_image"),
    ]
    for value in candidates:
        if not isinstance(value, str):
            continue
        value = value.strip()
        if not value:
            continue
        if value.startswith(("http://", "https://")) or os.path.exists(value):
            return value
    return ""


def _project_status(item: dict, data: dict) -> tuple[str, str]:
    raw = str(data.get("status") or data.get("status_publicacao") or "").casefold()
    if bool(data.get("publicado")) or bool(item.get("pacote_pronto")) or bool(data.get("pacote_pronto")) or raw in {"published", "publicado"}:
        return "Publicado", "published"
    if bool(data.get("revisao_aprovada")) or bool(data.get("cenas_texto")) or bool(data.get("texto_final")) or raw in {"in_progress", "em andamento", "remastering"}:
        return "Em andamento", "progress"
    return "Rascunho", "draft"


st.session_state.setdefault("jarvis_stage", "idle")
st.session_state.setdefault("jarvis_status_message", "Online")
st.session_state.setdefault("jarvis_reply", "")
st.session_state.setdefault("jarvis_autoplayed_token", "")
st.session_state.setdefault("jarvis_latency_metrics", {})
st.session_state.setdefault("faithbloom_cost_mode", "economico")
st.session_state.setdefault("jarvis_auto_voice", False)
st.session_state.setdefault("jarvis_engenheiro_automatico", True)
set_cost_mode(str(st.session_state.get("faithbloom_cost_mode") or "economico"))

current_state = st.session_state.get("state")
project_progress = inspect_project_state(current_state) if current_state else None
active_workspace_profile = _active_workspace_profile()
active_workspace_profile_id = str((active_workspace_profile or {}).get("id") or "")
active_workspace_name = str((active_workspace_profile or {}).get("display_name") or "").strip()
active_workspace_role = str((active_workspace_profile or {}).get("relationship") or "").strip()
all_home_catalog = [
    *[{"kind": "story", **x} for x in listar_livros()],
    *[{"kind": "coloring", **x} for x in listar_livros_colorir()],
]
home_catalog = (
    visible_project_cards(all_home_catalog, active_workspace_profile_id)
    if active_workspace_profile_id
    else all_home_catalog
)
home_catalog = [x for x in home_catalog if _is_home_project(x)]
home_manu_uri = _image_data_uri(_character_master_path("Manu"))
home_mel_uri = _image_data_uri(_character_master_path("Mel"))
home_teo_uri = _image_data_uri(_character_master_path("Téo"))

with st.sidebar:
    if home_manu_uri or home_mel_uri:
        sidebar_imgs = '<div style="position:relative;height:118px;margin-bottom:.25rem">'
        if home_manu_uri:
            sidebar_imgs += f'<img src="{home_manu_uri}" alt="Manu Master" style="position:absolute;width:112px;height:118px;object-fit:contain;left:-8px;bottom:-4px;-webkit-mask-image:radial-gradient(ellipse at center,#000 66%,transparent 98%);mask-image:radial-gradient(ellipse at center,#000 66%,transparent 98%)">'
        if home_mel_uri:
            sidebar_imgs += f'<img src="{home_mel_uri}" alt="Mel Master" style="position:absolute;width:86px;height:90px;object-fit:contain;left:76px;bottom:-1px;-webkit-mask-image:radial-gradient(ellipse at center,#000 66%,transparent 98%);mask-image:radial-gradient(ellipse at center,#000 66%,transparent 98%)">'
        sidebar_imgs += '</div>'
        st.html(
            '<div style="margin-top:.75rem;padding:.45rem .55rem .75rem;border-radius:16px;'
            'background:linear-gradient(150deg,#fff1f5,#ffe9ef 58%,#f7efff);'
            'border:1px solid rgba(211,104,156,.10);text-align:center;color:#8a4268;overflow:hidden">'
            + sidebar_imgs +
            '<div style="font-family:Georgia,serif;font-style:italic;font-weight:650;font-size:.85rem;line-height:1.35">'
            'Mais histórias para um futuro<br>ainda mais brilhante! 💗</div></div>'
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



top_search, gift_col, plan_col, bell_col, top_profile = st.columns([4.9, .38, 1.18, .38, 1.15], gap="small")
with top_search:
    home_search = st.text_input(
        "Buscar no FaithBloom",
        placeholder="🔎  Buscar projetos, personagens, histórias…",
        label_visibility="collapsed",
        key="faithbloom_home_search",
    )
with gift_col:
    st.html('<div class="fb-top-icon" title="Novidades">🎁</div>')
with plan_col:
    st.html('<div class="fb-plan-chip">👑 <strong>Plano Profissional</strong></div>')
with bell_col:
    st.html('<div class="fb-top-icon" title="Notificações">🔔</div>')
with top_profile:
    safe_profile_name = html_lib.escape(active_workspace_name or "Perfil")
    safe_profile_role = html_lib.escape(active_workspace_role.title() if active_workspace_role else "Perfil do workspace")
    initial = safe_profile_name[:1].upper() if safe_profile_name else "🌸"
    st.html(
        '<div class="fb-profile-chip"><span class="fb-profile-avatar">'+initial+'</span>'
        f'<span><strong>{safe_profile_name}</strong><small>{safe_profile_role}</small></span>'
        '<span class="fb-profile-chevron">⌄</span></div>'
    )

if home_search.strip():
    q = home_search.strip().casefold()
    matches = [
        item for item in home_catalog
        if q in (_home_project_title(item) + " " + str(item.get("colecao") or item.get("tema_geral") or "")).casefold()
    ][:6]
    with st.expander(f"🔎 Resultados para “{home_search.strip()}”", expanded=True):
        if matches:
            for item in matches:
                st.write(f"📖 **{_home_project_title(item)}** · {item.get('colecao') or item.get('tema_geral') or 'FaithBloom'}")
            st.page_link("pages/02_🏠_Dashboard_do_Estudio.py", label="Ver na biblioteca de projetos →")
        else:
            st.caption("Nenhum projeto salvo corresponde a essa busca.")

stage = str(st.session_state.get("jarvis_stage") or "idle")
reply = str(st.session_state.get("jarvis_reply") or "")
audio_path = str(st.session_state.get("jarvis_audio_path") or "")
reply_token = str(st.session_state.get("jarvis_reply_token") or "")
active_cfg = mode_config()

st.html("""
<style>
header[data-testid="stHeader"]{height:0!important;min-height:0!important;background:transparent!important}div[data-testid="stToolbar"]{display:none!important}.block-container{padding-top:.7rem!important}
.fb-profile-chip{height:46px;display:flex;align-items:center;justify-content:flex-end;gap:.65rem;padding:.35rem .65rem;border-radius:16px;background:rgba(255,255,255,.90);border:1px solid rgba(102,90,185,.10);box-shadow:0 7px 22px rgba(59,72,101,.05);color:#20394f}
.fb-profile-avatar{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#ffd6e7,#e8dfff);font-size:.9rem;font-weight:850;color:#6c4ec7}.fb-profile-chip small{display:block;color:#7a8490;font-size:.68rem;margin-top:.05rem}.fb-profile-chevron{color:#8469d9;font-weight:800}
.fb-top-icon{height:46px;display:flex;align-items:center;justify-content:center;font-size:1.15rem;color:#7356d6}
.fb-plan-chip{height:46px;display:flex;align-items:center;justify-content:center;gap:.34rem;padding:0 .7rem;border-radius:14px;background:linear-gradient(135deg,#fff7f8,#f5ecff);border:1px solid rgba(124,88,205,.10);font-size:.78rem;color:#3a315f;white-space:nowrap}
div[data-testid="stTextInput"] input{border-radius:15px!important;border:1px solid rgba(75,98,131,.13)!important;background:#fff!important;box-shadow:0 5px 18px rgba(59,72,101,.04)!important}
div.st-key-faithbloom_home_hero{
  position:relative;overflow:hidden;border-radius:20px;padding:16px 18px 10px;
  min-height:214px;
  background:
    radial-gradient(circle at 7% 78%,rgba(255,174,204,.34),transparent 25%),
    radial-gradient(circle at 20% 22%,rgba(255,232,149,.45),transparent 28%),
    radial-gradient(circle at 87% 18%,rgba(186,223,255,.48),transparent 28%),
    linear-gradient(102deg,#fff5f7 0%,#fff9e9 25%,#eef9ff 62%,#f7eeff 100%);
  border:1px solid rgba(108,89,183,.10);box-shadow:0 13px 34px rgba(55,72,102,.08);
}
div.st-key-faithbloom_home_hero:after{
  content:"✝";position:absolute;right:15.5%;top:7px;font-size:42px;color:rgba(188,137,77,.24);z-index:0
}
.fb-master-stage{height:190px;position:relative;overflow:visible}
.fb-master-stage:after{content:"🌸  🌼   🌷";position:absolute;left:0;right:0;bottom:0;font-size:24px;letter-spacing:12px;opacity:.72;white-space:nowrap}
.fb-master{position:absolute;object-fit:contain;filter:drop-shadow(0 8px 10px rgba(73,56,63,.11));-webkit-mask-image:radial-gradient(ellipse at center,#000 63%,rgba(0,0,0,.94) 76%,transparent 99%);mask-image:radial-gradient(ellipse at center,#000 63%,rgba(0,0,0,.94) 76%,transparent 99%)}
.fb-master-manu{width:190px;height:200px;left:-18px;bottom:-10px;z-index:2}
.fb-master-mel{width:132px;height:142px;left:128px;bottom:-4px;z-index:3}
.fb-master-teo{width:65px;height:70px;left:240px;bottom:16px;z-index:4}
.fb-master-fallback{font-size:86px;padding-top:56px;text-align:center}
.fbh-copy-wrap{padding:.2rem .25rem 0 .4rem;position:relative;z-index:2}
.fbh-title{font-size:clamp(1.85rem,2.8vw,2.9rem);line-height:1.02;letter-spacing:-.04em;font-weight:880;color:#172a67;margin:.18rem 0 .35rem}
.fbh-copy{font-size:clamp(.9rem,1.22vw,1.05rem);line-height:1.42;color:#253b69;max-width:710px}
.fbh-tagline{margin-top:.55rem;font-size:clamp(.96rem,1.35vw,1.12rem);font-weight:760;color:#7655c8;font-style:italic}
.fb-jarvis-bubble{margin:.1rem auto .2rem;max-width:205px;padding:.62rem .75rem;border-radius:17px;background:rgba(255,255,255,.88);border:1px solid rgba(126,93,204,.12);color:#7652c9;font-weight:780;text-align:center;box-shadow:0 7px 16px rgba(92,72,136,.07)}
.fb-home-section{margin:.72rem 0 .42rem}.fb-home-section h2{margin:0;color:#17305f;font-size:1.24rem;letter-spacing:-.02em}.fb-home-section p{margin:.18rem 0 0;color:#69778a;font-size:.83rem}
.fb-action-card{min-height:92px;padding:.76rem 3.65rem .72rem .9rem;border-radius:18px;border:1px solid rgba(57,87,118,.06);box-shadow:0 8px 20px rgba(50,74,103,.045);transition:.16s ease;margin:0;display:grid;grid-template-columns:54px 1fr;grid-template-rows:auto auto;column-gap:.72rem;align-items:center}
.fb-card-pink{background:linear-gradient(135deg,#fff3f7,#ffe8f0)}.fb-card-blue{background:linear-gradient(135deg,#eff9ff,#dff1ff)}.fb-card-mint{background:linear-gradient(135deg,#effdf7,#dcfaeb)}.fb-card-gold{background:linear-gradient(135deg,#fffaf0,#fff0c9)}.fb-card-lilac{background:linear-gradient(135deg,#f8f1ff,#eadfff)}.fb-card-rose{background:linear-gradient(135deg,#fff2f7,#ffe2ed)}
.fb-action-card:hover{transform:translateY(-2px);box-shadow:0 13px 27px rgba(50,74,103,.09)}
.fb-action-icon{width:48px;height:48px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:1.55rem;background:rgba(255,255,255,.64);box-shadow:inset 0 0 0 1px rgba(255,255,255,.65);grid-column:1;grid-row:1/3}
.fb-action-card h3{font-size:.96rem;margin:0;color:#152a62;grid-column:2;grid-row:1;align-self:end}.fb-action-card p{margin:.08rem 0 0;color:#445779;font-size:.78rem;line-height:1.28;grid-column:2;grid-row:2;align-self:start}
div[class*="st-key-home_action_"]{position:relative;margin-bottom:.55rem}
div[class*="st-key-home_action_"] div[data-testid="stPageLink"]{position:absolute;right:14px;top:50%;transform:translateY(-50%);z-index:5;width:40px}
div[class*="st-key-home_action_"] a[data-testid="stPageLink-NavLink"]{width:40px!important;height:40px!important;min-height:40px!important;border-radius:50%!important;padding:0!important;justify-content:center!important;background:rgba(255,255,255,.55)!important;border:1px solid rgba(91,78,160,.08)!important;box-shadow:none!important}
div[class*="st-key-home_action_"] a[data-testid="stPageLink-NavLink"] p{font-size:1.28rem!important;margin:0!important;color:#6e51dd!important}
.fb-assistant-box{margin-top:.65rem;padding:.75rem 1rem;border-radius:17px;background:#fff;border:1px solid rgba(91,78,160,.10);box-shadow:0 7px 20px rgba(50,74,103,.045)}
div.st-key-jarvis_compose{padding:.8rem 1rem;border:1px solid rgba(91,78,160,.10);border-radius:18px;background:#fff;box-shadow:0 7px 20px rgba(50,74,103,.04);margin-top:.35rem}
div.st-key-jarvis_compose div[data-testid="stFileUploaderDropzone"]{padding:.38rem .55rem!important;min-height:42px!important;border-radius:13px!important;background:#fafbff!important}
div.st-key-jarvis_compose div[data-testid="stFileUploaderDropzone"] small{display:none!important}
div.st-key-jarvis_compose textarea{min-height:54px!important;border-radius:13px!important}
div.st-key-jarvis_compose div[data-testid="stFormSubmitButton"] button{border:0!important;border-radius:13px!important;background:linear-gradient(90deg,#ff91b9,#b66cff 55%,#745cf5)!important;color:white!important;font-weight:820!important;min-height:48px!important;box-shadow:0 8px 20px rgba(143,83,223,.18)!important}
.fb-project-card{padding:.56rem;border-radius:14px;background:#fff;border:1px solid rgba(57,87,118,.08);min-height:190px;box-shadow:0 7px 18px rgba(50,74,103,.04);overflow:hidden}.fb-project-card .t{font-weight:790;color:#17324b;font-size:.82rem;line-height:1.22;margin:.48rem .12rem .15rem}.fb-project-card .m{font-size:.72rem;color:#7a8490;margin:.12rem}.fb-project-thumb-wrap{height:118px;border-radius:11px;overflow:hidden;position:relative;background:linear-gradient(135deg,#fff2f6,#eef8ff,#effcf7);border:1px solid rgba(105,89,183,.07)}.fb-project-thumb{width:100%;height:100%;object-fit:cover;display:block}.fb-project-cover-placeholder{height:100%;display:flex;align-items:center;justify-content:center;font-size:2.2rem}.fb-project-badge{position:absolute;left:7px;bottom:7px;padding:.24rem .48rem;border-radius:999px;background:rgba(255,255,255,.93);box-shadow:0 3px 10px rgba(42,56,82,.12);font-size:.68rem;font-weight:820}.fb-badge-published{color:#16835d;background:#eafaf2}.fb-badge-progress{color:#704fd1;background:#f1ebff}.fb-badge-draft{color:#c77810;background:#fff3d8}
.fb-status-panel{padding:.82rem;border-radius:17px;background:#fff;border:1px solid rgba(57,87,118,.08);box-shadow:0 8px 20px rgba(50,74,103,.045)}
.fb-status-line{display:flex;align-items:center;gap:.5rem;padding:.44rem .55rem;border-radius:11px;margin:.3rem 0;background:#f8f9fc;color:#43576b;font-size:.78rem}.fb-status-line.done{background:#effbf6;color:#167c67}.fb-status-line.active{background:#f2ecff;color:#7652c9}.fb-status-num{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:white;border:1px solid rgba(84,100,120,.10);font-size:.68rem;font-weight:800}
@media(max-width:900px){.fb-master-stage{height:160px}.fb-master-manu{width:150px;height:165px}.fb-master-mel{width:110px;height:118px;left:100px}.fb-master-teo{width:62px;height:68px;left:188px}.fbh-title{font-size:2rem}}
</style>
""")

with st.container(key="faithbloom_home_hero"):
    chars, copy, bot = st.columns([1.08, 1.65, .78], gap="small")
    with chars:
        if home_manu_uri or home_mel_uri or home_teo_uri:
            imgs = '<div class="fb-master-stage">'
            if home_manu_uri:
                imgs += f'<img class="fb-master fb-master-manu" src="{home_manu_uri}" alt="Manu Character Master">'
            if home_mel_uri:
                imgs += f'<img class="fb-master fb-master-mel" src="{home_mel_uri}" alt="Mel Character Master">'
            if home_teo_uri:
                imgs += f'<img class="fb-master fb-master-teo" src="{home_teo_uri}" alt="Téo Character Master">'
            imgs += '</div>'
            st.html(imgs)
        else:
            st.html('<div class="fb-master-fallback">👧🏻 🐱 🐦</div>')
    with copy:
        safe_name = html_lib.escape(active_workspace_name) if active_workspace_name else "bem-vindo(a)"
        st.html(
            f'<div class="fbh-copy-wrap"><div class="fbh-title">Oi, {safe_name}! ✨<br>O que você quer fazer hoje?</div>'
            f'<div class="fbh-copy">O Jarvis entende seu objetivo, monta a equipe certa de especialistas e guia todo o processo, do começo ao fim.</div>'
            f'<div class="fbh-tagline">Você sonha. Nós orquestramos. Deus floresce. 💜</div></div>'
        )
    with bot:
        st.html('<div class="fb-jarvis-bubble">Oi! Eu sou o Jarvis.<br>Vamos criar juntos? 💜</div>')
        heart = heart_mic(key="jarvis_heart_control", stage=stage, reply_text=reply, reply_audio="", reply_token=reply_token, compact=True)

action_rows = [
    [
        ("create","📖","Criar um livro","Do zero, com a equipe certa para a sua história.","pages/39_✍️_Historia_4_Estilos.py","fb-card-pink"),
        ("resume","🔄","Continuar / Atualizar","Melhorar um livro existente ou retomar de onde parou.","pages/16_🩺_Book_Doctor.py","fb-card-blue"),
        ("characters","👥","Personagens","Criar, editar e gerenciar personagens (ex.: Mel).","pages/14_👥_Character_Universe.py","fb-card-mint"),
    ],
    [
        ("images","🖼️","Imagens & ilustrações","Gerar, melhorar ou restaurar ilustrações.","pages/31_🖼️_Asset_Library_Media_Manager.py","fb-card-gold"),
        ("review","📄","Texto & revisão","Escrever, revisar e ajustar com apoio da IA.","pages/5_🔍_Analisar_Livro.py","fb-card-lilac"),
        ("publish","🚀","Publicar","Formatar e preparar para KDP e outras plataformas.","pages/26_🌐_Publishing_Distribution_Center.py","fb-card-rose"),
    ],
]
for row in action_rows:
    cols = st.columns(3, gap="medium")
    for col, (key, icon, title, desc, page, css_class) in zip(cols, row):
        with col:
            with st.container(key=f"home_action_{key}"):
                st.html(f'<div class="fb-action-card {css_class}"><div class="fb-action-icon">{icon}</div><h3>{title}</h3><p>{desc}</p></div>')
                st.page_link(page, label="→", use_container_width=False)

st.html('<div class="fb-assistant-box"><strong style="color:#17305f">💬 Prefere só contar o que precisa?</strong><br><span style="color:#63717e;font-size:.86rem">Converse ou envie arquivos para o Jarvis. Ele entende sua ideia e já organiza os próximos passos.</span></div>')

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
    uploads = st.file_uploader(
        "📎 Anexar imagens, PDF, documentos ou áudio", type=list(SUPPORTED_UPLOAD_TYPES),
        accept_multiple_files=True, key="jarvis_multimodal_uploads",
        help="Os anexos ficam no contexto da sessão. Nenhum upload vira Master automaticamente.",
    )
    if uploads:
        st.caption(f"{len(uploads)} arquivo{'s' if len(uploads) != 1 else ''} selecionado{'s' if len(uploads) != 1 else ''}.")
    with st.form("jarvis_text_form", clear_on_submit=True):
        msg_col, send_col = st.columns([5.2, 1.25], gap="small")
        with msg_col:
            typed = st.text_area(
                "Mensagem", height=62,
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

with st.expander("⚡ Diagnóstico de velocidade", expanded=False):
    metrics = dict(st.session_state.get("jarvis_latency_metrics") or {})
    if metrics: st.json(metrics)
    else: st.caption("As medições aparecem depois do primeiro pedido ou briefing manual.")

destination = st.session_state.get("jarvis_suggested_destination") or {}
page_key = destination.get("destination") or destination.get("id")
if page_key in NAV_PAGES and st.button(f"Abrir {destination.get('label') or page_key}", type="primary", use_container_width=True):
    st.switch_page(NAV_PAGES[page_key])

st.html('<div class="fb-home-section"><h2>📁 Projetos recentes <span style="font-weight:500;color:#7b8493;font-size:.78rem;margin-left:.45rem">Seus livros e histórias em um só lugar.</span></h2></div>')
recent = home_catalog[:4]

projects_col, status_col = st.columns([3.15, 1], gap="medium")
with projects_col:
    if recent:
        cols = st.columns(min(4, len(recent)), gap="small")
        for col, item in zip(cols, recent):
            data = _load_home_project(item)
            cover = _project_cover_path(data)
            status_label, status_kind = _project_status(item, data)
            title = _home_project_title(item)
            collection = str(item.get("colecao") or item.get("tema_geral") or "")
            with col:
                safe_title = html_lib.escape(title)
                safe_collection = html_lib.escape(collection)
                cover_src = _image_data_uri(cover) if cover else ""
                badge_class = "fb-badge-published" if status_kind == "published" else "fb-badge-progress" if status_kind == "progress" else "fb-badge-draft"
                status_icon = "✓" if status_kind == "published" else "◌" if status_kind == "progress" else "▼"
                thumb = (
                    f'<img class="fb-project-thumb" src="{cover_src}" alt="{safe_title}">'
                    if cover_src else '<div class="fb-project-cover-placeholder">📚🌸</div>'
                )
                st.html(
                    f'<div class="fb-project-card"><div class="fb-project-thumb-wrap">{thumb}'
                    f'<span class="fb-project-badge {badge_class}">{status_icon} {html_lib.escape(status_label)}</span></div>'
                    f'<div class="t">{safe_title}</div>'
                    f'<div class="m">{safe_collection or "FaithBloom"}</div></div>'
                )
        st.page_link("pages/02_🏠_Dashboard_do_Estudio.py", label="Ver todos os projetos →", use_container_width=False)
    else:
        st.caption("Seus projetos aparecerão aqui assim que forem salvos.")

with status_col:
    progress = project_progress or {
        "story_ready": False,
        "characters_ready": False,
        "visuals_ready": False,
        "review_ready": False,
        "package_ready": False,
    }
    status_steps = [
        ("História", bool(progress.get("story_ready"))),
        ("Personagens", bool(progress.get("characters_ready"))),
        ("Ilustrações", bool(progress.get("visuals_ready"))),
        ("Revisão", bool(progress.get("review_ready"))),
        ("Diagramação", bool(progress.get("package_ready"))),
        ("Publicação", bool(progress.get("package_ready"))),
    ]
    first_pending = next((i for i, (_, done) in enumerate(status_steps) if not done), len(status_steps))
    lines = '<div class="fb-status-panel"><strong style="color:#17324b">📊 Status da produção</strong><div style="color:#7a8490;font-size:.78rem;margin:.18rem 0 .65rem">Acompanhe o progresso do livro ativo.</div>'
    for idx, (label, done) in enumerate(status_steps, 1):
        active = (idx - 1) == first_pending and not done
        cls = "done" if done else "active" if active else ""
        state_label = "Concluído" if done else "Em andamento" if active else "Pendente"
        marker = "✓" if done else str(idx)
        lines += (
            f'<div class="fb-status-line {cls}"><span class="fb-status-num">{marker}</span>'
            f'<span style="flex:1">{label}</span><small>{state_label}</small></div>'
        )
    lines += '</div>'
    st.html(lines)

with st.expander("⚙️ Preferências do Jarvis e modo de IA", expanded=False):
    _render_ai_controls()

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

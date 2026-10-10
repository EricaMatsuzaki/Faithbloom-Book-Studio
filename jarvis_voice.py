"""Camada de voz do Jarvis sobre os serviços já existentes do FaithBloom.

Esta implementação NÃO duplica o Audiobook Studio nem o TTS do OpenRouter.
Ela acrescenta transcrição de fala (STT), coordenação de resposta curta e integra
clima via Open-Meteo e briefing útil para estrangeiros no Japão, reutilizando
``openrouter_client.gerar_audio`` na saída.

O Jarvis canônico prioriza baixa latência: perguntas locais simples (data/hora,
saudação e rotas editoriais diretas) não chamam LLM; conversa aberta usa o modelo
rápido dedicado em ``jarvis_dialogue``. STT e TTS registram latência no runtime.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import time
import unicodedata
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from controle_geracao import (
    POLITICA,
    extrair_custo_reportado,
    finalizar_requisicao,
    liberar_requisicao,
    sanitizar_texto,
    iniciar_requisicao,
)
from jarvis_assistant import interpret_request
from jarvis_dialogue import build_natural_reply
from jarvis_japan_briefing import build_japan_news_reply, is_daily_briefing_request, is_japan_news_request
from jarvis_weather import build_weather_reply, extract_location, is_weather_request, requested_day_offset
from openrouter_client import OPENROUTER_BASE_URL, _json_resposta, _post_com_retry, gerar_audio

MODELO_TRANSCRICAO = os.environ.get("OPENROUTER_MODELO_STT", "openai/whisper-1")
DEFAULT_JARVIS_VOICE_MODEL = "google/gemini-3.1-flash-tts-preview"
DEFAULT_JARVIS_GEMINI_VOICE = "Charon"
JARVIS_VOICE_PROFILE_VERSION = "2026-09-12-charon-realtime-v5"
LEGACY_UNAVAILABLE_TTS_MODELS = {"openai/gpt-4o-mini-tts-2025-12-15"}
LEGACY_OPENAI_VOICE_IDS = {"alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"}

_configured_voice_model = os.environ.get("OPENROUTER_MODELO_VOZ_JARVIS", "").strip()
JARVIS_VOICE_MODEL = (
    DEFAULT_JARVIS_VOICE_MODEL
    if not _configured_voice_model or _configured_voice_model in LEGACY_UNAVAILABLE_TTS_MODELS
    else _configured_voice_model
)

_configured_voice_id = os.environ.get("OPENROUTER_VOZ_JARVIS", "").strip()
if JARVIS_VOICE_MODEL.startswith("google/"):
    JARVIS_VOICE_ID = DEFAULT_JARVIS_GEMINI_VOICE
else:
    JARVIS_VOICE_ID = _configured_voice_id or "alloy"

JARVIS_VOICE_INSTRUCTIONS = os.environ.get(
    "OPENROUTER_INSTRUCOES_VOZ_JARVIS",
    "Fale em português do Brasil com voz masculina adulta, média-grave, calma e confiante. "
    "Use uma cadência internacional refinada e discreta, dicção muito clara, ritmo controlado, "
    "tom elegante de assistente executivo futurista e humor sutil quando apropriado. "
    "Não imite nenhum ator, personagem, celebridade ou voz protegida. "
    "Evite soar infantil, caricato, teatral ou excessivamente animado.",
)
SUPPORTED_AUDIO_FORMATS = {"wav", "mp3", "flac", "m4a", "ogg", "webm", "aac"}
DEFAULT_BRIEFING_LOCATION = os.environ.get("JARVIS_BRIEFING_LOCATION", "Toyohashi, Japan")
DEFAULT_JARVIS_TIMEZONE = os.environ.get("JARVIS_TIMEZONE", "Asia/Tokyo")

_DAYS_PT = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
_MONTHS_PT = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

_SPOKEN_EMOJI_LABELS = (
    re.compile(
        r"\brosto\s+sorridente\s*,?\s*com\s+olhos\s+sorridentes\s+e\s+bochechas\s+rosadas\b[.!?]?",
        re.IGNORECASE,
    ),
)


class JarvisVoiceError(RuntimeError):
    """Erro de voz apresentado ao usuário sem vazar credenciais/payloads."""


def _normalizar_formato(fmt: str) -> str:
    value = (fmt or "wav").strip().lower().lstrip(".")
    if value not in SUPPORTED_AUDIO_FORMATS:
        raise ValueError(f"Formato de áudio não suportado: {value}")
    return value


def _sanitize_tts_text(text: str) -> str:
    """Remove emojis/rótulos visuais antes do TTS sem alterar o texto exibido."""
    value = text or ""
    cleaned: list[str] = []
    for char in value:
        codepoint = ord(char)
        category = unicodedata.category(char)
        if category == "So":
            continue
        if char in {"\ufe0e", "\ufe0f", "\u200d", "\u20e3"}:
            continue
        if 0x1F3FB <= codepoint <= 0x1F3FF:
            continue
        cleaned.append(char)
    result = "".join(cleaned)
    for pattern in _SPOKEN_EMOJI_LABELS:
        result = pattern.sub("", result)
    result = re.sub(r"\s+([,.;:!?])", r"\1", result)
    result = re.sub(r"([.!?])\s*([.!?])+", r"\1", result)
    return " ".join(result.split()).strip()


def _voice_instructions_for_model(model: str) -> str | None:
    return JARVIS_VOICE_INSTRUCTIONS if (model or "").startswith("openai/") else None


def _prepare_tts_input(text: str, model: str) -> str:
    clean = (text or "").strip()
    if not (model or "").startswith("google/gemini-"):
        return clean
    return (
        "SINTETIZE SOMENTE O CONTEÚDO ENTRE <TRANSCRIPT> E </TRANSCRIPT>. "
        "NÃO LEIA ESTAS INSTRUÇÕES EM VOZ ALTA.\n\n"
        "# AUDIO PROFILE\n"
        "Assistente virtual original do FaithBloom: masculino adulto, sofisticado, sereno e inteligente.\n\n"
        "# DIRECTOR'S NOTES\n"
        f"{JARVIS_VOICE_INSTRUCTIONS}\n\n"
        "<TRANSCRIPT>\n"
        f"{clean}\n"
        "</TRANSCRIPT>"
    )


def transcribe_audio(audio_bytes: bytes, *, fmt: str = "wav", language: str = "pt") -> dict[str, Any]:
    if not audio_bytes:
        raise ValueError("Grave uma mensagem antes de enviar ao Jarvis.")
    formato = _normalizar_formato(fmt)
    idioma = (language or "pt").strip()
    digest = hashlib.sha256(audio_bytes).hexdigest()[:24]
    assinatura_conteudo = f"jarvis-stt|{digest}|format:{formato}|language:{idioma}"
    estimativa = max(0.001, POLITICA.estimativa_audio_min_usd * 0.10)
    req_id, assinatura, estimativa, inicio = iniciar_requisicao("audio", MODELO_TRANSCRICAO, assinatura_conteudo, estimativa)
    t0 = time.perf_counter()
    try:
        payload = {"model": MODELO_TRANSCRICAO, "input_audio": {"data": base64.b64encode(audio_bytes).decode("ascii"), "format": formato}}
        if idioma:
            payload["language"] = idioma
        resp = _post_com_retry(f"{OPENROUTER_BASE_URL}/audio/transcriptions", payload, 60)
        dados = _json_resposta(resp)
        texto = str(dados.get("text") or "").strip()
        if not texto:
            raise JarvisVoiceError("Não consegui entender a gravação. Tente falar um pouco mais perto do microfone.")
        finalizar_requisicao(req_id, assinatura, "audio", MODELO_TRANSCRICAO, estimativa, inicio, "sucesso", extrair_custo_reportado(dados))
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"[FaithBloom Jarvis Latency] stt_ms={elapsed_ms} model={MODELO_TRANSCRICAO}", flush=True)
        return {"text": texto, "model": MODELO_TRANSCRICAO, "usage": dados.get("usage")}
    except Exception as exc:
        finalizar_requisicao(req_id, assinatura, "audio", MODELO_TRANSCRICAO, estimativa, inicio, "erro", detalhe=sanitizar_texto(str(exc)))
        raise
    except BaseException:
        liberar_requisicao(assinatura)
        raise


def _parece_pedido_tempo(text: str) -> bool:
    return is_weather_request(text)


def _parece_continuar_projeto(text: str) -> bool:
    value = (text or "").casefold()
    return any(x in value for x in ("continuar", "continue", "retomar", "retome", "projeto atual"))


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold().strip())


def _is_date_time_request(text: str) -> bool:
    value = _normalized(text)
    exact = {
        "que dia é hoje", "que dia e hoje", "qual a data de hoje", "qual é a data de hoje",
        "qual e a data de hoje", "que horas são", "que horas sao", "que horas é", "que horas e",
        "qual o dia de hoje", "data de hoje", "hora agora", "horas agora",
    }
    return value in exact or any(
        phrase in value
        for phrase in ("que dia é hoje", "qual a data de hoje", "que horas são agora", "data e hora de hoje")
    )


def _build_date_time_reply() -> str:
    try:
        now = datetime.now(ZoneInfo(DEFAULT_JARVIS_TIMEZONE))
    except Exception:
        now = datetime.now()
    weekday = _DAYS_PT[now.weekday()]
    month = _MONTHS_PT[now.month - 1]
    return f"Hoje é {weekday}, {now.day} de {month} de {now.year}. Agora são {now.hour:02d}:{now.minute:02d}."


def _is_simple_greeting(text: str) -> bool:
    value = _normalized(text).strip(" !?.")
    return value in {"oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e aí", "e ai"}


def _greeting_reply() -> str:
    try:
        hour = datetime.now(ZoneInfo(DEFAULT_JARVIS_TIMEZONE)).hour
    except Exception:
        hour = datetime.now().hour
    opening = "Bom dia" if hour < 12 else "Boa tarde" if hour < 18 else "Boa noite"
    return f"{opening}, Erica. Estou pronto. O que você precisa?"


def _is_fast_editorial_command(text: str) -> bool:
    """Skip the LLM for explicit operational commands that already have a route."""
    value = _normalized(text)
    verbs = (
        "crie", "criar", "faça", "faca", "fazer", "monte", "montar", "prepare", "preparar",
        "transforme", "transformar", "gere", "gerar", "produza", "produzir",
    )
    objects = (
        "livro", "história", "historia", "colorir", "atividade", "atividades", "audiobook",
        "quadrinho", "hq", "devocional", "flashcard", "workbook", "caderno de exercícios",
        "caderno de exercicios", "animação", "animacao", "vídeo", "video", "música", "musica",
    )
    return any(v in value for v in verbs) and any(obj in value for obj in objects)


def _build_daily_briefing(location: str) -> str:
    parts: list[str] = [_build_date_time_reply()]
    try:
        parts.append(build_weather_reply(location, day_offset=0))
    except Exception:
        parts.append(f"Não consegui consultar o clima de {location} nesta tentativa.")
    try:
        news_reply, _items = build_japan_news_reply(limit=5)
        parts.append(news_reply)
    except Exception:
        parts.append("As fontes de notícias para estrangeiros no Japão ficaram indisponíveis nesta tentativa.")
    return " Briefing de hoje. " + " ".join(parts)


def build_spoken_reply(
    transcript: str,
    *,
    result: dict | None = None,
    project_progress: dict | None = None,
    weather_location: str | None = None,
    history: list[dict[str, Any]] | None = None,
    natural: bool = False,
) -> str:
    """Cria resposta curta priorizando rotas locais antes de qualquer chamada LLM."""
    texto = (transcript or "").strip()
    if not texto:
        return "Não consegui ouvir uma mensagem. Grave novamente e tente de novo."

    from agents.engenheiro_saas_automacao import is_engineering_request
    if is_engineering_request(texto):
        return "Posso analisar esse problema em Engenharia e Skills. Abra o diagnóstico técnico para executar a auditoria local ou selecionar módulos para revisão profunda."

    if _is_date_time_request(texto):
        return _build_date_time_reply()

    if _is_simple_greeting(texto):
        return _greeting_reply()

    if is_daily_briefing_request(texto):
        location = extract_location(texto) or (weather_location or "").strip() or DEFAULT_BRIEFING_LOCATION
        return _build_daily_briefing(location)

    if is_japan_news_request(texto):
        news_reply, _items = build_japan_news_reply(limit=5)
        return news_reply

    if is_weather_request(texto):
        location = extract_location(texto) or (weather_location or "").strip()
        if not location:
            return "Claro. Para consultar a previsão do tempo, me diga a cidade. Por exemplo: Jarvis, como está o tempo em Toyohashi?"
        return build_weather_reply(location, day_offset=requested_day_offset(texto))

    if project_progress and _parece_continuar_projeto(texto):
        return str(project_progress.get("message") or "Encontrei seu projeto atual e posso continuar do próximo checkpoint.")

    interpreted = result or interpret_request(texto)
    use_natural_dialogue = natural and not _is_fast_editorial_command(texto)
    if use_natural_dialogue:
        try:
            return build_natural_reply(
                texto,
                history=history,
                route_result=interpreted,
                project_progress=project_progress,
            )
        except Exception:
            pass

    plan = interpreted.get("route_plan") or {}
    projeto = plan.get("project_label") or "seu projeto"
    publico = plan.get("audience_label") or "o público escolhido"
    if (interpreted.get("anti_duplication") or {}).get("ok", False):
        return (
            f"Entendi. Você quer {projeto} para {publico}. A rota está pronta com o que já existe no FaithBloom. "
            "Vou pedir sua confirmação antes de qualquer etapa importante."
        )
    return (
        f"Entendi o pedido de {projeto}, mas encontrei um ponto que precisa de revisão na rota. "
        "Não vou avançar automaticamente até você confirmar."
    )


def _log_tts_runtime_failure(exc: Exception, *, model: str, voice: str, response_format: str) -> None:
    detail = sanitizar_texto(str(exc)) or exc.__class__.__name__
    print(
        "[FaithBloom Jarvis TTS] falha de runtime "
        f"profile={JARVIS_VOICE_PROFILE_VERSION} model={model} voice={voice} format={response_format} "
        f"error={detail}",
        flush=True,
    )


def _log_tts_runtime_success(*, model: str, voice: str, response_format: str, spoken_text: str, path: str, elapsed_ms: int) -> None:
    digest = hashlib.sha256(spoken_text.encode("utf-8")).hexdigest()[:12]
    print(
        "[FaithBloom Jarvis TTS] sucesso "
        f"profile={JARVIS_VOICE_PROFILE_VERSION} model={model} voice={voice} format={response_format} "
        f"file={os.path.splitext(path)[1].lower()} text_sha={digest} tts_ms={elapsed_ms}",
        flush=True,
    )


def synthesize_reply(text: str, *, name: str = "jarvis_resposta", voice: str | None = None) -> str:
    """Reutiliza o TTS oficial com perfil Jarvis e saída compatível com Gemini/Safari."""
    if not (text or "").strip():
        raise ValueError("A resposta do Jarvis está vazia.")
    spoken_text = _sanitize_tts_text(text)
    if not spoken_text:
        raise ValueError("A resposta do Jarvis não contém conteúdo falável após remover elementos visuais.")
    prepared_text = _prepare_tts_input(spoken_text, JARVIS_VOICE_MODEL)
    selected_voice = voice or JARVIS_VOICE_ID
    # Gemini TTS produz PCM 24 kHz/16-bit/mono nativamente. Pedimos PCM e o cliente
    # compartilhado o encapsula em WAV para reprodução confiável no Streamlit/Safari.
    response_format = "pcm" if JARVIS_VOICE_MODEL.startswith("google/gemini-") else "mp3"
    t0 = time.perf_counter()
    try:
        path = gerar_audio(
            prepared_text,
            name,
            voice=selected_voice,
            model=JARVIS_VOICE_MODEL,
            instructions=_voice_instructions_for_model(JARVIS_VOICE_MODEL),
            response_format=response_format,
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        _log_tts_runtime_success(
            model=JARVIS_VOICE_MODEL,
            voice=selected_voice,
            response_format=response_format,
            spoken_text=spoken_text,
            path=path,
            elapsed_ms=elapsed_ms,
        )
        print(f"[FaithBloom Jarvis Latency] tts_ms={elapsed_ms} model={JARVIS_VOICE_MODEL}", flush=True)
        return path
    except Exception as exc:
        _log_tts_runtime_failure(
            exc,
            model=JARVIS_VOICE_MODEL,
            voice=selected_voice,
            response_format=response_format,
        )
        raise

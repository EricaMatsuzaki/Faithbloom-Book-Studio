"""Camada de voz do Jarvis sobre os serviços já existentes do FaithBloom.

Esta implementação NÃO duplica o Audiobook Studio nem o TTS do OpenRouter.
Ela acrescenta transcrição de fala (STT), coordenação de resposta curta e integra
clima via Open-Meteo, reutilizando ``openrouter_client.gerar_audio`` na saída.
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Any

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
from jarvis_weather import build_weather_reply, extract_location, is_weather_request, requested_day_offset
from openrouter_client import OPENROUTER_BASE_URL, _json_resposta, _post_com_retry, gerar_audio

MODELO_TRANSCRICAO = os.environ.get("OPENROUTER_MODELO_STT", "openai/whisper-1")
JARVIS_VOICE_MODEL = os.environ.get("OPENROUTER_MODELO_VOZ_JARVIS", "openai/gpt-4o-mini-tts-2025-12-15")
# Onyx gives the prototype a deeper adult base than Alloy. This is an original
# FaithBloom profile, not a clone or imitation of any actor/character voice.
JARVIS_VOICE_ID = os.environ.get("OPENROUTER_VOZ_JARVIS", "onyx")
JARVIS_VOICE_INSTRUCTIONS = os.environ.get(
    "OPENROUTER_INSTRUCOES_VOZ_JARVIS",
    "Fale em português do Brasil com voz masculina adulta, média-grave, calma e confiante. "
    "Use uma cadência britânica refinada e discreta, dicção muito clara, ritmo controlado, "
    "tom elegante de assistente executivo futurista e humor sutil quando apropriado. "
    "Não imite nenhum ator ou personagem conhecido. Evite soar infantil, caricato, teatral ou excessivamente animado.",
)
SUPPORTED_AUDIO_FORMATS = {"wav", "mp3", "flac", "m4a", "ogg", "webm", "aac"}


class JarvisVoiceError(RuntimeError):
    """Erro de voz apresentado ao usuário sem vazar credenciais/payloads."""


def _normalizar_formato(fmt: str) -> str:
    value = (fmt or "wav").strip().lower().lstrip(".")
    if value not in SUPPORTED_AUDIO_FORMATS:
        raise ValueError(f"Formato de áudio não suportado: {value}")
    return value


def transcribe_audio(audio_bytes: bytes, *, fmt: str = "wav", language: str = "pt") -> dict[str, Any]:
    if not audio_bytes:
        raise ValueError("Grave uma mensagem antes de enviar ao Jarvis.")
    formato = _normalizar_formato(fmt)
    idioma = (language or "pt").strip()
    digest = hashlib.sha256(audio_bytes).hexdigest()[:24]
    assinatura_conteudo = f"jarvis-stt|{digest}|format:{formato}|language:{idioma}"
    estimativa = max(0.001, POLITICA.estimativa_audio_min_usd * 0.10)
    req_id, assinatura, estimativa, inicio = iniciar_requisicao("audio", MODELO_TRANSCRICAO, assinatura_conteudo, estimativa)
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


def build_spoken_reply(
    transcript: str,
    *,
    result: dict | None = None,
    project_progress: dict | None = None,
    weather_location: str | None = None,
    history: list[dict[str, Any]] | None = None,
    natural: bool = False,
) -> str:
    """Cria uma resposta falada curta.

    Clima e progresso usam dados determinísticos. Na UI, quando a rota já foi
    interpretada, a resposta passa automaticamente pela camada conversacional
    para evitar a mesma frase genérica em pedidos diferentes.
    """
    texto = (transcript or "").strip()
    if not texto:
        return "Não consegui ouvir uma mensagem. Grave novamente e tente de novo."

    if is_weather_request(texto):
        location = extract_location(texto) or (weather_location or "").strip()
        if not location:
            return "Claro. Para consultar a previsão do tempo, me diga a cidade. Por exemplo: Jarvis, como está o tempo em Toyohashi?"
        return build_weather_reply(location, day_offset=requested_day_offset(texto))

    if project_progress and _parece_continuar_projeto(texto):
        return str(project_progress.get("message") or "Encontrei seu projeto atual e posso continuar do próximo checkpoint.")

    interpreted = result or interpret_request(texto)
    use_natural_dialogue = natural or result is not None
    if use_natural_dialogue:
        try:
            return build_natural_reply(
                texto,
                history=history,
                route_result=interpreted,
                project_progress=project_progress,
            )
        except Exception:
            # A conversa continua mesmo se o modelo textual estiver indisponível.
            pass

    plan = interpreted.get("route_plan") or {}
    projeto = plan.get("project_label") or "seu projeto"
    publico = plan.get("audience_label") or "o público escolhido"
    if (interpreted.get("anti_duplication") or {}).get("ok", False):
        return (
            f"Entendi. Você quer {projeto} para {publico}. Eu organizei a rota usando os especialistas que já existem no FaithBloom. "
            "Vou pedir sua confirmação antes de avançar para qualquer etapa importante."
        )
    return (
        f"Entendi o pedido de {projeto}, mas encontrei um ponto que precisa de revisão na rota. "
        "Não vou avançar automaticamente até você confirmar."
    )


def synthesize_reply(text: str, *, name: str = "jarvis_resposta", voice: str | None = None) -> str:
    """Reutiliza o TTS oficial com um perfil sonoro específico do Jarvis."""
    if not (text or "").strip():
        raise ValueError("A resposta do Jarvis está vazia.")
    return gerar_audio(
        text.strip(), name, voice=voice or JARVIS_VOICE_ID, model=JARVIS_VOICE_MODEL,
        instructions=JARVIS_VOICE_INSTRUCTIONS, response_format="mp3",
    )

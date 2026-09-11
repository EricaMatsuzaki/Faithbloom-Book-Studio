"""Adaptador experimental de Google Cloud Text-to-Speech para o Jarvis Voice Lab.

Este módulo é isolado do TTS principal do FaithBloom. Ele existe somente para
comparar vozes oficiais do Google Cloud antes de qualquer promoção para o Jarvis
canônico. Nenhuma credencial é persistida no repositório.
"""
from __future__ import annotations

import base64
import os
import re
import uuid
from pathlib import Path
from typing import Any, Callable

import requests

GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
GOOGLE_TTS_API_KEY_ENV = "GOOGLE_CLOUD_TTS_API_KEY"
VOICE_LAB_MAX_CHARS = 500
OUTPUT_DIR = Path("saida_audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Curadoria inicial: vozes masculinas pt-BR oficiais do Google Cloud TTS.
GOOGLE_PT_BR_VOICES: dict[str, dict[str, str]] = {
    "Neural2-B": {
        "name": "pt-BR-Neural2-B",
        "language_code": "pt-BR",
        "gender": "MALE",
        "family": "Neural2",
    },
    "WaveNet-B": {
        "name": "pt-BR-Wavenet-B",
        "language_code": "pt-BR",
        "gender": "MALE",
        "family": "WaveNet",
    },
    "WaveNet-E": {
        "name": "pt-BR-Wavenet-E",
        "language_code": "pt-BR",
        "gender": "MALE",
        "family": "WaveNet",
    },
    "Chirp3-HD-Charon": {
        "name": "pt-BR-Chirp3-HD-Charon",
        "language_code": "pt-BR",
        "gender": "MALE",
        "family": "Chirp 3 HD",
    },
}


class GoogleCloudTTSError(RuntimeError):
    """Erro seguro do Voice Lab sem exposição de credenciais."""


def available_voice_labels() -> list[str]:
    return list(GOOGLE_PT_BR_VOICES)


def voice_config(label: str) -> dict[str, str]:
    try:
        return dict(GOOGLE_PT_BR_VOICES[label])
    except KeyError as exc:
        raise ValueError(f"Voz do Voice Lab não suportada: {label}") from exc


def _clean_text(text: str) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    if not value:
        raise ValueError("Digite uma frase para testar a voz.")
    if len(value) > VOICE_LAB_MAX_CHARS:
        raise ValueError(f"O teste aceita no máximo {VOICE_LAB_MAX_CHARS} caracteres por geração.")
    return value


def _resolve_api_key(explicit_key: str | None = None) -> str:
    key = (explicit_key or os.environ.get(GOOGLE_TTS_API_KEY_ENV) or "").strip()
    if not key:
        raise GoogleCloudTTSError(
            "Google Cloud TTS ainda não está configurado. Adicione GOOGLE_CLOUD_TTS_API_KEY "
            "nos Secrets do Streamlit Cloud para liberar o Voice Lab."
        )
    return key


def build_synthesis_payload(text: str, voice_label: str) -> dict[str, Any]:
    clean = _clean_text(text)
    cfg = voice_config(voice_label)
    return {
        "input": {"text": clean},
        "voice": {
            "languageCode": cfg["language_code"],
            "name": cfg["name"],
            "ssmlGender": cfg["gender"],
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": 1.0,
            "pitch": 0.0,
        },
    }


def synthesize_google_voice(
    text: str,
    voice_label: str,
    *,
    api_key: str | None = None,
    requester: Callable[..., Any] = requests.post,
    timeout: int = 45,
    output_dir: str | os.PathLike[str] | None = None,
) -> str:
    """Gera um MP3 de teste usando a API oficial Google Cloud TTS.

    O segredo é enviado somente como parâmetro HTTPS da chamada e nunca é salvo
    no nome do arquivo, mensagem de erro ou estado persistente.
    """
    key = _resolve_api_key(api_key)
    payload = build_synthesis_payload(text, voice_label)
    try:
        response = requester(
            GOOGLE_TTS_URL,
            params={"key": key},
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        suffix = f" (HTTP {status})" if status else ""
        raise GoogleCloudTTSError(
            "Não consegui gerar a voz no Google Cloud TTS. Verifique se a API Text-to-Speech "
            "está habilitada, se a chave possui permissão e se o projeto tem faturamento ativo"
            + suffix
            + "."
        ) from None
    except ValueError as exc:
        raise GoogleCloudTTSError("O Google Cloud TTS retornou uma resposta inválida.") from exc

    audio_b64 = data.get("audioContent") if isinstance(data, dict) else None
    if not isinstance(audio_b64, str) or not audio_b64.strip():
        raise GoogleCloudTTSError("O Google Cloud TTS não retornou áudio nesta tentativa.")
    try:
        audio_bytes = base64.b64decode(audio_b64, validate=True)
    except Exception as exc:
        raise GoogleCloudTTSError("O áudio retornado pelo Google Cloud TTS está corrompido.") from exc
    if not audio_bytes:
        raise GoogleCloudTTSError("O Google Cloud TTS retornou um arquivo de áudio vazio.")

    target_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    cfg = voice_config(voice_label)
    safe_voice = re.sub(r"[^A-Za-z0-9_-]+", "_", cfg["name"])
    path = target_dir / f"voice_lab_{safe_voice}_{uuid.uuid4().hex[:10]}.mp3"
    path.write_bytes(audio_bytes)
    return str(path)

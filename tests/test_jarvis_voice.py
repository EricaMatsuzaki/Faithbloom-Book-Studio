import pytest

import jarvis_voice as voice


def test_empty_audio_is_rejected_before_network():
    with pytest.raises(ValueError, match="Grave uma mensagem"):
        voice.transcribe_audio(b"")


def test_unsupported_audio_format_is_rejected():
    with pytest.raises(ValueError, match="não suportado"):
        voice.transcribe_audio(b"abc", fmt="exe")


def test_stt_payload_uses_openrouter_audio_transcriptions(monkeypatch):
    captured = {}

    class FakeResponse:
        pass

    def fake_start(*args, **kwargs):
        return "req", "sig", 0.001, 1.0

    def fake_post(url, payload, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(voice, "iniciar_requisicao", fake_start)
    monkeypatch.setattr(voice, "_post_com_retry", fake_post)
    monkeypatch.setattr(voice, "_json_resposta", lambda resp: {"text": "Crie uma história infantil"})
    monkeypatch.setattr(voice, "finalizar_requisicao", lambda *a, **k: None)

    result = voice.transcribe_audio(b"RIFFfakewav", fmt="wav", language="pt")

    assert result["text"] == "Crie uma história infantil"
    assert captured["url"].endswith("/audio/transcriptions")
    assert captured["payload"]["model"] == voice.MODELO_TRANSCRICAO
    assert captured["payload"]["input_audio"]["format"] == "wav"
    assert captured["payload"]["input_audio"]["data"]
    assert captured["payload"]["language"] == "pt"


def test_spoken_reply_reuses_editorial_route_and_requires_confirmation():
    reply = voice.build_spoken_reply("Crie uma história infantil cristã para 3–8 anos")
    lower = reply.casefold()
    assert "especialistas" in lower
    assert "confirma" in lower


def test_weather_voice_request_asks_city_when_missing():
    reply = voice.build_spoken_reply("Jarvis, qual é a previsão do tempo para hoje?")
    assert "cidade" in reply.casefold()


def test_weather_voice_request_uses_realtime_weather_module(monkeypatch):
    called = {}

    def fake_weather(location):
        called["location"] = location
        return "Em Toyohashi, agora está 28 graus e parcialmente nublado."

    monkeypatch.setattr(voice, "build_weather_reply", fake_weather)
    reply = voice.build_spoken_reply("Jarvis, como está o tempo em Toyohashi?")
    assert called["location"] == "Toyohashi"
    assert "28 graus" in reply


def test_weather_voice_can_use_configured_default_city(monkeypatch):
    monkeypatch.setattr(voice, "build_weather_reply", lambda location: f"Clima consultado em {location}.")
    reply = voice.build_spoken_reply("Vai chover hoje?", weather_location="Nagoya, Japan")
    assert reply == "Clima consultado em Nagoya, Japan."


def test_continue_project_speaks_existing_progress_message():
    progress = {
        "message": "Recebi a história. O próximo passo é confirmar os personagens antes das ilustrações."
    }
    reply = voice.build_spoken_reply("Continue meu projeto atual", project_progress=progress)
    assert reply == progress["message"]


def test_synthesize_reply_delegates_to_existing_tts(monkeypatch):
    called = {}

    def fake_generate(text, name, voice=None):
        called.update(text=text, name=name, voice=voice)
        return "saida_audio/mock.mp3"

    monkeypatch.setattr(voice, "gerar_audio", fake_generate)
    path = voice.synthesize_reply("Olá, Erica!", name="jarvis_teste", voice="voz-1")
    assert path == "saida_audio/mock.mp3"
    assert called == {"text": "Olá, Erica!", "name": "jarvis_teste", "voice": "voz-1"}

import base64

import pytest

import jarvis_push_to_talk as ptt
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

    def fake_weather(location, **kwargs):
        called["location"] = location
        called["day_offset"] = kwargs.get("day_offset")
        return "Em Toyohashi, agora está 28 graus e parcialmente nublado."

    monkeypatch.setattr(voice, "build_weather_reply", fake_weather)
    reply = voice.build_spoken_reply("Jarvis, como está o tempo em Toyohashi?")
    assert called["location"] == "Toyohashi"
    assert called["day_offset"] == 0
    assert "28 graus" in reply


def test_weather_voice_can_use_configured_default_city(monkeypatch):
    monkeypatch.setattr(voice, "build_weather_reply", lambda location, **kwargs: f"Clima consultado em {location}.")
    reply = voice.build_spoken_reply("Vai chover hoje?", weather_location="Nagoya, Japan")
    assert reply == "Clima consultado em Nagoya, Japan."


def test_weather_voice_tomorrow_selects_next_day(monkeypatch):
    called = {}

    def fake_weather(location, **kwargs):
        called.update(location=location, **kwargs)
        return "Amanhã haverá chuva leve."

    monkeypatch.setattr(voice, "build_weather_reply", fake_weather)
    reply = voice.build_spoken_reply("Previsão do tempo em Toyohashi amanhã")
    assert called["location"] == "Toyohashi"
    assert called["day_offset"] == 1
    assert "Amanhã" in reply


def test_continue_project_speaks_existing_progress_message():
    progress = {"message": "Recebi a história. O próximo passo é confirmar os personagens antes das ilustrações."}
    reply = voice.build_spoken_reply("Continue meu projeto atual", project_progress=progress)
    assert reply == progress["message"]


def test_synthesize_reply_delegates_to_existing_tts_with_jarvis_profile(monkeypatch):
    called = {}

    def fake_generate(text, name, voice=None, **kwargs):
        called.update(text=text, name=name, voice=voice, **kwargs)
        return "saida_audio/mock.mp3"

    monkeypatch.setattr(voice, "gerar_audio", fake_generate)
    path = voice.synthesize_reply("Olá, Erica!", name="jarvis_teste", voice="voz-1")
    assert path == "saida_audio/mock.mp3"
    assert called["text"] == "Olá, Erica!"
    assert called["name"] == "jarvis_teste"
    assert called["voice"] == "voz-1"
    assert called["model"] == voice.JARVIS_VOICE_MODEL
    assert called["response_format"] == "mp3"
    assert "futurista" in called["instructions"]


def test_push_to_talk_decodes_browser_webm_payload():
    payload = {"id": "rec-1", "data": base64.b64encode(b"fake-webm-audio").decode("ascii"), "mime_type": "audio/webm;codecs=opus"}
    decoded = ptt.decode_recording(payload)
    assert decoded == (b"fake-webm-audio", "webm", "rec-1")


def test_push_to_talk_maps_ios_mp4_to_m4a():
    payload = {"id": "rec-ios", "data": base64.b64encode(b"fake-mp4-audio").decode("ascii"), "mime_type": "audio/mp4"}
    decoded = ptt.decode_recording(payload)
    assert decoded == (b"fake-mp4-audio", "m4a", "rec-ios")

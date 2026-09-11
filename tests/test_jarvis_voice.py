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
    assert called["name"] == "jarvis_teste"
    assert called["voice"] == "voz-1"
    assert called["model"] == voice.JARVIS_VOICE_MODEL
    assert called["response_format"] == "mp3"
    if voice.JARVIS_VOICE_MODEL.startswith("google/gemini-"):
        assert "<TRANSCRIPT>" in called["text"]
        assert "Olá, Erica!" in called["text"]
        assert "assistente virtual original" in called["text"].casefold()
        assert called["instructions"] is None
    else:
        assert called["text"] == "Olá, Erica!"


def test_voice_instructions_are_provider_aware():
    assert voice._voice_instructions_for_model("google/gemini-3.1-flash-tts-preview") is None
    openai_instructions = voice._voice_instructions_for_model("openai/some-current-tts")
    assert openai_instructions is not None
    assert "futurista" in openai_instructions.casefold()


def test_gemini_input_receives_original_voice_direction_without_imitation():
    prepared = voice._prepare_tts_input("Boa noite, Erica.", "google/gemini-3.1-flash-tts-preview")
    lower = prepared.casefold()
    assert "audio profile" in lower
    assert "director's notes" in lower
    assert "masculino adulto" in lower
    assert "futurista" in lower
    assert "não imite" in lower
    assert "<transcript>" in lower
    assert "boa noite, erica." in lower


def test_non_gemini_tts_input_is_not_wrapped():
    assert voice._prepare_tts_input("Olá", "openai/some-current-tts") == "Olá"


def test_routed_request_uses_natural_dialogue_in_voice_ui(monkeypatch):
    route = {
        "route_plan": {"project_label": "História infantil", "audience_label": "3–8 anos"},
        "anti_duplication": {"ok": True},
        "requires_author_approval": True,
    }
    called = {}

    def fake_natural(text, **kwargs):
        called["text"] = text
        called.update(kwargs)
        return "Entendi: você quer continuar o livro da Mel. Posso preparar o próximo checkpoint."

    monkeypatch.setattr(voice, "build_natural_reply", fake_natural)
    reply = voice.build_spoken_reply("Continue o livro da Mel", result=route, natural=True)
    assert "livro da Mel" in reply
    assert called["route_result"] is route


def test_default_jarvis_voice_uses_current_available_tts_profile():
    assert voice.JARVIS_VOICE_MODEL == "google/gemini-3.1-flash-tts-preview"
    assert voice.JARVIS_VOICE_ID == "Charon"
    instructions = voice.JARVIS_VOICE_INSTRUCTIONS.casefold()
    assert "internacional" in instructions
    assert "não imite" in instructions


def test_google_profile_never_falls_back_to_legacy_openai_voice_id():
    assert voice.JARVIS_VOICE_ID.casefold() not in voice.LEGACY_OPENAI_VOICE_IDS


def test_tts_runtime_failure_is_logged_with_safe_profile_context(monkeypatch, capsys):
    def fail_generate(*args, **kwargs):
        raise RuntimeError("OpenRouter recusou a chamada (HTTP 403)")

    monkeypatch.setattr(voice, "gerar_audio", fail_generate)
    with pytest.raises(RuntimeError, match="HTTP 403"):
        voice.synthesize_reply("Teste de diagnóstico")

    output = capsys.readouterr().out
    assert "[FaithBloom Jarvis TTS]" in output
    assert f"model={voice.JARVIS_VOICE_MODEL}" in output
    assert f"voice={voice.JARVIS_VOICE_ID}" in output
    assert "format=mp3" in output
    assert "HTTP 403" in output


def test_push_to_talk_decodes_browser_webm_payload():
    payload = {"id": "rec-1", "data": base64.b64encode(b"fake-webm-audio").decode("ascii"), "mime_type": "audio/webm;codecs=opus"}
    decoded = ptt.decode_recording(payload)
    assert decoded == (b"fake-webm-audio", "webm", "rec-1")


def test_push_to_talk_maps_ios_mp4_to_m4a():
    payload = {"id": "rec-ios", "data": base64.b64encode(b"fake-mp4-audio").decode("ascii"), "mime_type": "audio/mp4"}
    decoded = ptt.decode_recording(payload)
    assert decoded == (b"fake-mp4-audio", "m4a", "rec-ios")


def test_premium_shell_uses_the_approved_visual_asset():
    assert ptt._SKIN_PATH.name == "jarvis_premium_ui_reference.jpg"
    assert ptt._SKIN_PATH.exists()
    assert ptt._skin_b64()
    assert "fb-jarvis-skin" in ptt.HTML


def test_premium_shell_keeps_voice_text_and_navigation_interactive():
    assert "fb-ptt" in ptt.HTML
    assert "fb-text-input" in ptt.HTML
    assert 'data-nav="create"' in ptt.HTML
    assert 'data-nav="characters"' in ptt.HTML
    assert "typed_request" in ptt.JS
    assert "navigation" in ptt.JS

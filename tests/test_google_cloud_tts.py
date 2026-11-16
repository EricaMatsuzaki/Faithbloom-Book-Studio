import base64
from pathlib import Path

import pytest
import requests

import google_cloud_tts as gtts


def test_voice_lab_has_expected_male_pt_br_candidates():
    labels = gtts.available_voice_labels()
    assert labels == ["Neural2-B", "WaveNet-B", "WaveNet-E", "Chirp3-HD-Charon"]
    for label in labels:
        cfg = gtts.voice_config(label)
        assert cfg["language_code"] == "pt-BR"
        assert cfg["gender"] == "MALE"
        assert cfg["name"].startswith("pt-BR-")


def test_build_payload_uses_selected_official_voice():
    payload = gtts.build_synthesis_payload("Olá, Erica.", "Neural2-B")
    assert payload["input"]["text"] == "Olá, Erica."
    assert payload["voice"] == {
        "languageCode": "pt-BR",
        "name": "pt-BR-Neural2-B",
        "ssmlGender": "MALE",
    }
    assert payload["audioConfig"]["audioEncoding"] == "MP3"


def test_build_payload_rejects_unknown_voice():
    with pytest.raises(ValueError, match="não suportada"):
        gtts.build_synthesis_payload("Oi", "Antonio")


def test_voice_lab_limits_text_length():
    with pytest.raises(ValueError, match="no máximo"):
        gtts.build_synthesis_payload("x" * (gtts.VOICE_LAB_MAX_CHARS + 1), "WaveNet-B")


def test_missing_api_key_fails_before_network(monkeypatch):
    monkeypatch.delenv(gtts.GOOGLE_TTS_CREDENTIAL_ENV, raising=False)
    with pytest.raises(gtts.GoogleCloudTTSError, match="GOOGLE_CLOUD_TTS_API_KEY"):
        gtts.synthesize_google_voice("Oi", "WaveNet-B")


def test_synthesize_writes_mp3_and_never_exposes_key(tmp_path):
    captured = {}
    audio = b"ID3fake-google-audio"

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"audioContent": base64.b64encode(audio).decode("ascii")}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    path = gtts.synthesize_google_voice(
        "Boa noite, Erica.",
        "Chirp3-HD-Charon",
        api_key="super-secret-key",
        requester=fake_post,
        output_dir=tmp_path,
    )

    output = Path(path)
    assert output.exists()
    assert output.read_bytes() == audio
    assert output.suffix == ".mp3"
    assert "super-secret-key" not in output.name
    assert captured["url"] == gtts.GOOGLE_TTS_URL
    assert captured["params"] == {"key": "super-secret-key"}
    assert captured["json"]["voice"]["name"] == "pt-BR-Chirp3-HD-Charon"
    assert captured["timeout"] == 45


def test_http_error_is_sanitized_and_does_not_leak_key(tmp_path):
    class FakeResponse:
        status_code = 403

        def raise_for_status(self):
            exc = requests.HTTPError("forbidden super-secret-key")
            exc.response = self
            raise exc

    def fake_post(*args, **kwargs):
        return FakeResponse()

    with pytest.raises(gtts.GoogleCloudTTSError) as exc_info:
        gtts.synthesize_google_voice(
            "Oi",
            "WaveNet-E",
            api_key="super-secret-key",
            requester=fake_post,
            output_dir=tmp_path,
        )
    message = str(exc_info.value)
    assert "HTTP 403" in message
    assert "super-secret-key" not in message

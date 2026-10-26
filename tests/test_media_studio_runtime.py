from copy import deepcopy
import hashlib
import io
import json
import socket
import subprocess
import wave
from pathlib import Path

from PIL import Image
import pytest
import requests

import media_studio as ms


class MemoryBackend:
    def __init__(self):
        self.data = {}
        self.events = []
        self.fail_save = False

    def put_bytes(self, path, data, content_type=None):
        self.data[path] = data
        self.events.append(("bytes", path))

    def get_bytes(self, path):
        return self.data[path]

    def put_json(self, path, data):
        if self.fail_save:
            raise RuntimeError("storage outage")
        self.data[path] = json.dumps(data).encode()
        self.events.append(("json", deepcopy(data)))

    def get_json(self, path, default=None):
        return json.loads(self.data[path]) if path in self.data else deepcopy(default)

    def list(self, prefix):
        return [p for p in self.data if p.startswith(prefix + "/")]


class Response:
    def __init__(self, data=None, payload=b"", code=200, headers=None):
        self.data, self.payload, self.status_code = data, payload, code
        self.headers = headers or {}
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("provider secret raw payload")

    def json(self):
        return deepcopy(self.data)

    def iter_content(self, size):
        yield self.payload

    def close(self):
        self.closed = True


class HTTP:
    def __init__(self, backend, post=None, gets=None):
        self.backend = backend
        self.post_result = post or Response({"id": "prediction1", "status": "starting"})
        self.gets = list(gets or [])
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        assert any(event[0] == "json" and event[1].get("jobs") and event[1]["jobs"][-1]["status"] == "submission_pending" for event in self.backend.events)
        if isinstance(self.post_result, Exception):
            raise self.post_result
        return self.post_result

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        assert any(event[0] == "json" and event[1].get("jobs") and event[1]["jobs"][-1].get("prediction_id") == "prediction1" for event in self.backend.events)
        value = self.gets.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def image_bytes(color):
    out = io.BytesIO()
    Image.new("RGB", (160, 100), color).save(out, format="PNG")
    return out.getvalue()


def audio_bytes():
    out = io.BytesIO()
    with wave.open(out, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 16000)
    return out.getvalue()


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "tenant_local_directory", lambda kind: tmp_path)
    return ms.MediaStudioStore(MemoryBackend())


@pytest.fixture
def configured(monkeypatch):
    settings = {
        "REPLICATE_API_TOKEN": "fake-token-never-print", "FAITHBLOOM_MUSIC_REPLICATE_MODEL": "test-owner/test-music",
        "FAITHBLOOM_MUSIC_INPUT_FIELDS": '["prompt", "duration"]', "FAITHBLOOM_MUSIC_ESTIMATED_COST_USD": "0.5",
        "FAITHBLOOM_VIDEO_REPLICATE_MODEL": "test-owner/test-video", "FAITHBLOOM_VIDEO_INPUT_FIELDS": '["prompt", "image"]',
        "FAITHBLOOM_VIDEO_IMAGE_INPUT_FIELD": "image", "FAITHBLOOM_VIDEO_ESTIMATED_COST_USD": "0.5",
        "FAITHBLOOM_MEDIA_MAX_COST_USD": "1", "FAITHBLOOM_MEDIA_GENERATION_ENABLED": "true",
        "FAITHBLOOM_MEDIA_SINGLE_WORKER_CONFIRMED": "true",
    }
    monkeypatch.setattr(ms, "_setting", lambda name: settings.get(name, ""))
    return settings


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(ms.socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])


def test_original_sources_survive_reopen_and_approval_is_explicit(store):
    state = store.create("Filme do jardim", "animation_video", source_ref="book-master-id")
    data = image_bytes("red")
    with pytest.raises(ms.MediaStudioError, match="aprovação"):
        store.add_image(state["id"], data, approved=False)
    assert not store.load(state["id"])["sources"]
    state = store.add_image(state["id"], data, approved=True, provenance="official master selected by author")
    reopened = ms.MediaStudioStore(store.backend).load(state["id"])
    source = reopened["sources"][0]
    assert store.backend.get_bytes(source["asset"].removeprefix("fb://")) == data
    assert source["sha256"] == hashlib.sha256(data).hexdigest()
    assert reopened["source_ref"] == "book-master-id"
    assert reopened["auto_promote_master"] is False
    assert reopened["auto_publish"] is False


@pytest.mark.parametrize("data", [b"<html>not an image</html>", b"", b"svg<script>" * 100])
def test_invalid_uploaded_images_never_become_approved_sources(store, data):
    state = store.create("Filme", "animation_video")
    with pytest.raises(ms.MediaStudioError):
        store.add_image(state["id"], data, approved=True)
    assert not store.load(state["id"])["sources"]


def test_duplicate_source_is_not_added_twice(store):
    state = store.create("Filme", "animation_video")
    data = image_bytes("red")
    for _ in range(2):
        store.add_image(state["id"], data, approved=True)
    assert len(store.load(state["id"])["sources"]) == 1


def test_real_animatic_contains_two_ordered_frames_and_optional_audio(store):
    if not ms.media_readiness()["local_animatic"]["available"]:
        pytest.skip("ffmpeg not installed")
    state = store.create("Animatic real", "animation_video")
    first, second = image_bytes("red"), image_bytes("blue")
    store.add_image(state["id"], first, approved=True)
    store.add_image(state["id"], second, approved=True)
    store.add_audio(state["id"], audio_bytes(), approved=True)
    output = ms.render_animatic(store, state["id"], seconds_per_image=1, width=320, height=180)
    reopened = store.load(state["id"])
    assert output["status"] == "needs_review" and not output["approved"]
    assert 1.9 <= output["inspection"]["duration_seconds"] <= 2.2
    assert {s["codec_type"] for s in output["inspection"]["streams"]} == {"audio", "video"}
    data = store.backend.get_bytes(output["asset"].removeprefix("fb://"))
    path = ms.tenant_local_directory("outputs") / "verify.mp4"
    path.write_bytes(data)
    colors = []
    for at in (.3, 1.3):
        rgb = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(path), "-vf", "crop=2:2:159:89", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        colors.append(tuple(rgb[:3]))
    assert colors[0][0] > 200 and colors[0][2] < 30
    assert colors[1][2] > 200 and colors[1][0] < 30
    assert output["provenance"]["character_animation"] is False
    assert output["provenance"]["source_sha256"] == [hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest()]
    assert store.backend.get_bytes(reopened["sources"][0]["asset"].removeprefix("fb://")) == first
    with pytest.raises(ms.MediaStudioError):
        store.approve_output(state["id"], output["id"], confirmed=False)
    store.approve_output(state["id"], output["id"], confirmed=True)
    assert store.load(state["id"])["outputs"][0]["approved"]
    assert not store.load(state["id"])["auto_promote_master"]


@pytest.mark.parametrize("kwargs", [{"seconds_per_image": float("nan")}, {"seconds_per_image": 0}, {"width": 321}, {"width": 4096}])
def test_invalid_render_settings_are_rejected_before_render(store, kwargs):
    state = store.create("Filme", "animation_video")
    store.add_image(state["id"], image_bytes("red"), approved=True)
    with pytest.raises(ms.MediaStudioError):
        ms.render_animatic(store, state["id"], **kwargs)
    assert not store.load(state["id"])["outputs"]


def test_changed_source_or_cross_project_source_cannot_render(store):
    state = store.create("Filme", "animation_video")
    state = store.add_image(state["id"], image_bytes("red"), approved=True)
    asset = state["sources"][0]["asset"]
    store.backend.put_bytes(asset.removeprefix("fb://"), image_bytes("blue"))
    with pytest.raises(ms.MediaStudioError, match="mudou"):
        ms.render_animatic(store, state["id"])
    state["sources"][0]["asset"] = "fb://media_studio/assets/another/sources/secret.png"
    store.save(state)
    with pytest.raises(ms.MediaStudioError, match="outro projeto"):
        ms.render_animatic(store, state["id"])


def test_unconfigured_provider_cannot_start_a_paid_request(store, monkeypatch):
    monkeypatch.setattr(ms, "_setting", lambda name: "")
    state = store.create("Canção", "music")
    http = HTTP(store.backend)
    with pytest.raises(ms.MediaStudioError, match="Configure"):
        ms.ReplicateMediaClient(store, http).draft(state["id"], {"prompt": "uma canção"})
    assert http.calls == []


@pytest.mark.parametrize("setting, value", [("FAITHBLOOM_MEDIA_GENERATION_ENABLED", "false"), ("FAITHBLOOM_MEDIA_SINGLE_WORKER_CONFIRMED", "false"), ("FAITHBLOOM_MUSIC_ESTIMATED_COST_USD", "nan"), ("FAITHBLOOM_MUSIC_ESTIMATED_COST_USD", "2"), ("FAITHBLOOM_MUSIC_REPLICATE_MODEL", "../private"), ("FAITHBLOOM_MUSIC_INPUT_FIELDS", "{}")])
def test_deployment_cost_and_single_worker_flags_gate_paid_execution(store, configured, setting, value):
    configured[setting] = value
    assert not ms.provider_configuration("music")["available"]


def test_exact_draft_confirmation_and_id_checkpoint_precede_polling(store, configured):
    state = store.create("Canção", "music")
    http = HTTP(store.backend, gets=[Response({"id": "prediction1", "status": "processing"})])
    client = ms.ReplicateMediaClient(store, http)
    draft = client.draft(state["id"], {"prompt": "canção original"})
    with pytest.raises(ms.MediaStudioError):
        client.submit(draft, confirmed_fingerprint="another-draft")
    assert not http.calls
    job = client.submit(draft, confirmed_fingerprint=draft["fingerprint"])
    assert job["prediction_id"] == "prediction1"
    assert len(http.calls) == 1
    assert http.calls[0][1] == "https://api.replicate.com/v1/models/test-owner/test-music/predictions"
    assert http.calls[0][2]["allow_redirects"] is False
    reopened = ms.ReplicateMediaClient(ms.MediaStudioStore(store.backend), http)
    assert reopened.submit(draft, confirmed_fingerprint=draft["fingerprint"])["id"] == job["id"]
    assert len(http.calls) == 1
    assert reopened.poll(state["id"], job["id"])["status"] == "processing"
    assert http.calls[-1][1] == "https://api.replicate.com/v1/predictions/prediction1"


def test_storage_checkpoint_failure_prevents_paid_post(store, configured):
    state = store.create("Canção", "music")
    http = HTTP(store.backend)
    client = ms.ReplicateMediaClient(store, http)
    draft = client.draft(state["id"], {"prompt": "canção"})
    store.backend.fail_save = True
    with pytest.raises(RuntimeError):
        client.submit(draft, confirmed_fingerprint=draft["fingerprint"])
    assert not http.calls


def test_uncertain_paid_submission_is_not_repeated_and_blocks_changed_payload(store, configured):
    state = store.create("Canção", "music")
    http = HTTP(store.backend, post=requests.Timeout("raw-token-secrets"))
    client = ms.ReplicateMediaClient(store, http)
    draft = client.draft(state["id"], {"prompt": "canção"})
    with pytest.raises(ms.MediaStudioError, match="incerto") as exc:
        client.submit(draft, confirmed_fingerprint=draft["fingerprint"])
    assert "raw-token" not in str(exc.value)
    reopened = ms.ReplicateMediaClient(ms.MediaStudioStore(store.backend), http)
    assert reopened.submit(draft, confirmed_fingerprint=draft["fingerprint"])["status"] == "submission_uncertain"
    changed = reopened.draft(state["id"], {"prompt": "outra canção"})
    with pytest.raises(ms.MediaStudioError, match="pendente ou incerto"):
        reopened.submit(changed, confirmed_fingerprint=changed["fingerprint"])
    assert len(http.calls) == 1


def test_aggregate_project_budget_blocks_additional_paid_calls(store, configured):
    state = store.create("Canção", "music")
    http = HTTP(store.backend)
    client = ms.ReplicateMediaClient(store, http)
    for i in range(2):
        draft = client.draft(state["id"], {"prompt": f"canção {i}"})
        job = client.submit(draft, confirmed_fingerprint=draft["fingerprint"])
        stored = store.load(state["id"])
        stored["jobs"][-1]["status"] = "failed"
        store.save(stored)
    draft = client.draft(state["id"], {"prompt": "canção 3"})
    with pytest.raises(ms.MediaStudioError, match="orçamento"):
        client.submit(draft, confirmed_fingerprint=draft["fingerprint"])
    assert len(http.calls) == 2


def test_video_provider_uses_exact_approved_original_bytes(store, configured):
    state = store.create("Filme", "animation_video")
    data = image_bytes("red")
    state = store.add_image(state["id"], data, approved=True)
    client = ms.ReplicateMediaClient(store, HTTP(store.backend))
    with pytest.raises(ms.MediaStudioError, match="Selecione"):
        client.draft(state["id"], {"prompt": "sutil"})
    draft = client.draft(state["id"], {"prompt": "sutil"}, source_id=state["sources"][0]["id"])
    import base64
    assert base64.b64decode(draft["input"]["image"].split(",", 1)[1]) == data
    assert draft["source_sha256"] == hashlib.sha256(data).hexdigest()
    with pytest.raises(ms.MediaStudioError, match="URL substituta"):
        client.draft(state["id"], {"prompt": "sutil", "image": "https://other-image.example"}, source_id=state["sources"][0]["id"])
    assert client.submit(draft, confirmed_fingerprint=draft["fingerprint"])["source_sha256"] == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("url", ["http://replicate.delivery/a.wav", "https://127.0.0.1/a.wav", "https://evilreplicate.delivery/a.wav", "https://replicate.delivery.evil.test/a.wav", "https://replicate.delivery:8443/a.wav", "https://a@replicate.delivery/a.wav"])
def test_untrusted_media_output_urls_are_rejected(url, public_dns):
    with pytest.raises(ms.MediaStudioError):
        ms._public_output_url(url)


def test_known_cdn_resolving_to_private_network_is_rejected(monkeypatch):
    monkeypatch.setattr(ms.socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))])
    with pytest.raises(ms.MediaStudioError):
        ms._public_output_url("https://replicate.delivery/a.wav")


def test_successful_music_download_is_validated_persisted_and_needs_review(store, configured, public_dns):
    state = store.create("Canção", "music")
    download = Response(payload=audio_bytes())
    http = HTTP(store.backend, gets=[Response({"id": "prediction1", "status": "succeeded", "output": "https://replicate.delivery/a.wav"}), download])
    client = ms.ReplicateMediaClient(store, http)
    draft = client.draft(state["id"], {"prompt": "canção original"})
    job = client.submit(draft, confirmed_fingerprint=draft["fingerprint"])
    complete = client.poll(state["id"], job["id"])
    assert complete["output_id"]
    output = store.load(state["id"])["outputs"][0]
    assert output["status"] == "needs_review" and not output["approved"]
    assert output["provenance"]["prediction_id"] == "prediction1"
    assert store.backend.get_bytes(output["asset"].removeprefix("fb://")) == audio_bytes()
    assert "headers" not in http.calls[-1][2]
    assert http.calls[-1][2]["allow_redirects"] is False
    assert download.closed
    client.poll(state["id"], job["id"])
    assert len(http.calls) == 3


@pytest.mark.parametrize("download", [Response(payload=b"<html>error</html>"), Response(payload=audio_bytes(), code=302, headers={"Location": "http://127.0.0.1"})])
def test_html_or_redirect_output_does_not_become_media_and_retry_only_gets(store, configured, public_dns, download):
    state = store.create("Canção", "music")
    status = Response({"id": "prediction1", "status": "succeeded", "output": "https://replicate.delivery/a.wav"})
    http = HTTP(store.backend, gets=[status, download, status, Response(payload=audio_bytes())])
    client = ms.ReplicateMediaClient(store, http)
    draft = client.draft(state["id"], {"prompt": "canção"})
    job = client.submit(draft, confirmed_fingerprint=draft["fingerprint"])
    with pytest.raises(ms.MediaStudioError):
        client.poll(state["id"], job["id"])
    assert not store.load(state["id"])["outputs"]
    assert client.poll(state["id"], job["id"])["output_id"]
    assert sum(c[0] == "POST" for c in http.calls) == 1


def test_idea_capture_and_selection_are_durable_without_media_generation(store):
    idea = store.capture_idea("Um livro sobre a bondade.", title="Nova ideia")
    other = store.capture_idea("Um livro sobre a bondade.", title="Nova ideia")
    assert idea["id"] != other["id"]
    reopened = ms.MediaStudioStore(store.backend)
    assert len(reopened.list_ideas()) == 2
    with pytest.raises(ms.MediaStudioError):
        reopened.approve_idea(idea["id"], confirmed=False)
    assert reopened.approve_idea(idea["id"], confirmed=True)["status"] == "approved"
    assert not reopened.list_projects()

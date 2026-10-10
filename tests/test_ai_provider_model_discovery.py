import ai_provider_router as router


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


def _reset():
    router._GEMINI_MODEL_CACHE["at"] = 0.0
    router._GEMINI_MODEL_CACHE["models"] = []
    router._GEMINI_INVALID_MODELS.clear()
    router._GEMINI_LAST_SELECTED_MODEL = ""


def test_discovery_only_keeps_generate_content_text_models(monkeypatch):
    _reset()
    monkeypatch.setattr(router, "GEMINI_API_KEY", "test-key")

    payload = {
        "models": [
            {"name": "models/gemini-live-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
            {"name": "models/imagen-4.0", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-pro-text", "supportedGenerationMethods": ["generateContent"]},
        ]
    }
    monkeypatch.setattr(router.requests, "get", lambda *a, **k: FakeResponse(200, payload))

    models = router._discover_gemini_models(force=True)
    assert models == ["gemini-live-flash", "gemini-pro-text"]


def test_discovery_becomes_authoritative_over_invalid_configured_models(monkeypatch):
    _reset()
    monkeypatch.setattr(router, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(router, "GEMINI_TEXT_MODEL", "gemini-made-up")
    monkeypatch.setattr(router, "GEMINI_FALLBACK_MODELS", ["gemini-also-made-up"])

    payload = {
        "models": [
            {"name": "models/gemini-available-flash", "supportedGenerationMethods": ["generateContent"]},
        ]
    }
    monkeypatch.setattr(router.requests, "get", lambda *a, **k: FakeResponse(200, payload))

    assert router._gemini_candidate_models() == ["gemini-available-flash"]


def test_404_model_is_removed_from_runtime_candidates(monkeypatch):
    _reset()
    monkeypatch.setattr(router, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(router, "GEMINI_MAX_ATTEMPTS", 1)

    def fake_post(*args, **kwargs):
        return FakeResponse(404, {})

    monkeypatch.setattr(router.requests, "post", fake_post)

    try:
        router._gemini_model("gemini-gone", "system", "instruction")
    except router.AIProviderPermanentError:
        pass
    else:
        raise AssertionError("expected permanent error")

    assert "gemini-gone" in router._GEMINI_INVALID_MODELS


def test_discovery_auth_failure_is_not_silently_ignored(monkeypatch):
    _reset()
    monkeypatch.setattr(router, "GEMINI_API_KEY", "bad-key")
    monkeypatch.setattr(router.requests, "get", lambda *a, **k: FakeResponse(403, {}))

    try:
        router._discover_gemini_models(force=True)
    except router.AIProviderPermanentError as exc:
        assert "autenticação" in str(exc)
    else:
        raise AssertionError("expected permanent auth error")

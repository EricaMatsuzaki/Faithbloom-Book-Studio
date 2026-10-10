from types import SimpleNamespace

import pytest

import ai_provider_router as router
from storage_backend import SupabaseStorageBackend, StorageError, _normalize_storage_path


class FakeResponse:
    def __init__(self, status_code=200, *, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_retry_after_honors_header():
    response = FakeResponse(429, headers={"Retry-After": "7"})
    assert router._retry_after_seconds(response, 0) == 7.0


def test_post_with_retry_recovers_from_429(monkeypatch):
    responses = iter([FakeResponse(429), FakeResponse(200)])
    sleeps = []
    monkeypatch.setattr(router.time, "sleep", lambda seconds: sleeps.append(seconds))
    result = router._post_with_retry(lambda: next(responses), provider="Gemini/test", max_attempts=2)
    assert result.status_code == 200
    assert sleeps


def test_openrouter_402_is_cached_as_permanent(monkeypatch):
    router._OPENROUTER_DISABLED_REASON = ""

    def fake_openrouter(*args, **kwargs):
        raise RuntimeError("HTTP 402 insufficient credits")

    import openrouter_client
    monkeypatch.setattr(openrouter_client, "chamar_llm", fake_openrouter)
    with pytest.raises(router.AIProviderPermanentError):
        router._openrouter("s", "i")
    assert "402" in router._OPENROUTER_DISABLED_REASON
    router._OPENROUTER_DISABLED_REASON = ""


def test_storage_path_normalizer_rejects_traversal():
    with pytest.raises(StorageError):
        _normalize_storage_path("livros/../segredo.json")


def test_supabase_list_accepts_already_prefixed_names(monkeypatch):
    backend = SupabaseStorageBackend("https://abc.supabase.co", "sb_secret_test", "faithbloom")
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None, data=None):
        calls.append((url, dict(json or {})))
        prefix = (json or {}).get("prefix", "")
        if prefix == "livros":
            return FakeResponse(200, payload=[{"name": "livros/demo", "id": None, "metadata": None}])
        if prefix == "livros/demo":
            return FakeResponse(200, payload=[{"name": "book.json", "id": "1", "metadata": {"size": 1}}])
        return FakeResponse(200, payload=[])

    monkeypatch.setattr("storage_backend.requests.post", fake_post)
    assert backend.list("livros") == ["livros/demo/book.json"]
    assert [payload["prefix"] for _, payload in calls] == ["livros", "livros/demo"]


def test_supabase_url_is_reduced_to_project_origin():
    backend = SupabaseStorageBackend(
        "https://abc.supabase.co/storage/v1/object/list/faithbloom",
        "sb_secret_test",
        "faithbloom",
    )
    assert backend.url == "https://abc.supabase.co"

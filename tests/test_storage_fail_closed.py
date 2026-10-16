"""An outage, denied read or corrupt catalog must never become an empty index."""
from types import SimpleNamespace

import pytest
import requests

import author_profiles
import storage_backend as storage


@pytest.mark.parametrize("payload", [b"{broken", b"\xff\xfe", b"null", b"{}"])
def test_corrupt_list_index_is_not_replaced_with_empty_default(tmp_path, payload):
    backend = storage.LocalStorageBackend(str(tmp_path))
    backend.put_bytes("index.json", payload)
    with pytest.raises(storage.StorageCorrupt):
        backend.get_json("index.json", [])
    assert backend.get_bytes("index.json") == payload


def test_only_absence_returns_default_and_exists_false(tmp_path):
    backend = storage.LocalStorageBackend(str(tmp_path))
    assert backend.get_json("missing.json", []) == []
    assert backend.exists("missing.json") is False
    backend.put_json("index.json", [])
    assert backend.get_json("index.json", []) == []
    assert backend.exists("index.json") is True


@pytest.mark.parametrize("status", [403, 429, 500, 503])
def test_supabase_permission_and_server_failure_propagate(status, monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    monkeypatch.setattr(storage.requests, "get", lambda *a, **k: SimpleNamespace(status_code=status, text="secret-response-body", content=b""))
    with pytest.raises(storage.StorageUnavailable) as error:
        backend.get_json("index.json", [])
    assert "secret-response-body" not in str(error.value)
    with pytest.raises(storage.StorageUnavailable):
        backend.exists("index.json")


def test_supabase_404_is_explicit_absence(monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    monkeypatch.setattr(storage.requests, "get", lambda *a, **k: SimpleNamespace(status_code=404, content=b""))
    assert backend.get_json("missing.json", []) == []
    assert backend.exists("missing.json") is False


def test_legacy_supabase_gateway_explicit_not_found_code_is_absence(monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    monkeypatch.setattr(storage.requests, "get", lambda *a, **k: SimpleNamespace(status_code=400, json=lambda: {"statusCode": "404", "error": "not_found", "message": "Object not found"}))
    assert backend.get_json("missing.json", []) == []


def test_supabase_message_claiming_missing_is_not_enough(monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    monkeypatch.setattr(storage.requests, "get", lambda *a, **k: SimpleNamespace(status_code=400, json=lambda: {"message": "Object not found"}))
    with pytest.raises(storage.StorageUnavailable):
        backend.get_json("index.json", [])


def test_timeout_is_safe_error_and_not_absence(monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    def unavailable(*args, **kwargs):
        raise requests.Timeout("apikey=sb_secret_fake private/path")
    monkeypatch.setattr(storage.requests, "get", unavailable)
    with pytest.raises(storage.StorageUnavailable) as error:
        backend.get_json("index.json", [])
    assert "sb_secret" not in str(error.value)
    assert "private/path" not in str(error.value)
    with pytest.raises(storage.StorageUnavailable):
        backend.exists("index.json")


def test_author_catalog_corruption_blocks_rewrite_and_preserves_original(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(str(tmp_path))
    original = b'{"wrong":"shape"}'
    backend.put_bytes(author_profiles.INDEX_PATH, original)
    monkeypatch.setattr(author_profiles, "BACKEND", backend)
    with pytest.raises(storage.StorageCorrupt):
        author_profiles.create_author_profile("New author")
    assert backend.get_bytes(author_profiles.INDEX_PATH) == original


def test_author_catalog_network_failure_never_uploads_empty_index(monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    uploads = []
    def upload(url, **kwargs):
        uploads.append((url, kwargs.get("data")))
        return SimpleNamespace(status_code=200)
    monkeypatch.setattr(storage.requests, "post", upload)
    monkeypatch.setattr(storage.requests, "get", lambda *a, **k: SimpleNamespace(status_code=403, content=b""))
    monkeypatch.setattr(author_profiles, "BACKEND", backend)
    with pytest.raises(storage.StorageUnavailable):
        author_profiles.create_author_profile("New author")
    assert len(uploads) == 1  # profile draft may exist; previous index never overwritten
    assert "/authors/index.json" not in uploads[0][0]


def test_failed_descendant_listing_is_not_reported_as_complete(monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    def respond(url, **kwargs):
        if kwargs["json"]["prefix"] == "authors":
            return SimpleNamespace(status_code=200, json=lambda: [{"name": "profiles", "id": None, "metadata": None}])
        return SimpleNamespace(status_code=403, text="sensitive")
    monkeypatch.setattr(storage.requests, "post", respond)
    with pytest.raises(storage.StorageUnavailable):
        backend.list("authors")


def test_supabase_listing_paginates_past_first_thousand(monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    offsets = []
    def respond(url, **kwargs):
        offset = kwargs["json"]["offset"]
        offsets.append(offset)
        count = 1000 if offset == 0 else 1
        return SimpleNamespace(status_code=200, json=lambda: [{"name": f"{offset+i}.json", "id": "file", "metadata": {}} for i in range(count)])
    monkeypatch.setattr(storage.requests, "post", respond)
    assert len(backend.list("authors")) == 1001
    assert offsets == [0, 1000]


def test_failed_upload_and_listing_do_not_expose_provider_response(monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    monkeypatch.setattr(storage.requests, "post", lambda *a, **k: SimpleNamespace(status_code=403, text="token sb_secret_fake private data"))
    for operation in (lambda: backend.put_json("index.json", []), lambda: backend.list("authors")):
        with pytest.raises(storage.StorageUnavailable) as error:
            operation()
        assert "sb_secret" not in str(error.value)
        assert "private data" not in str(error.value)


def test_invalid_list_response_is_not_treated_as_empty(monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    monkeypatch.setattr(storage.requests, "post", lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: {"error": "unavailable"}))
    with pytest.raises(storage.StorageCorrupt):
        backend.list("authors")


@pytest.mark.parametrize("name", ["", "../private.json"])
def test_corrupt_list_entry_is_not_silently_omitted(name, monkeypatch):
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    monkeypatch.setattr(storage.requests, "post", lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: [{"name": name, "id": "file", "metadata": {}}]))
    with pytest.raises(storage.StorageCorrupt):
        backend.list("authors")


def test_local_traversal_and_symlink_outside_storage_are_denied(tmp_path):
    backend = storage.LocalStorageBackend(str(tmp_path / "data"))
    external = tmp_path / "private.json"
    external.write_text("{}")
    (backend.root / "linked.json").symlink_to(external)
    with pytest.raises(storage.StorageError):
        backend.get_json("../private.json", {})
    with pytest.raises(storage.StorageError):
        backend.get_json("linked.json", {})
    with pytest.raises(storage.StorageError):
        backend.list("")

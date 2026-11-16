"""No lost index entries across workers; no fake CAS or permission downgrade."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import multiprocessing
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest
import requests

import saas_access as access
import storage_backend as storage


def _append_worker(root, worker, count):
    backend = storage.LocalStorageBackend(root)
    for number in range(count):
        backend.update_json("index.json", lambda rows: rows + [[worker, number]], [])


def test_independent_local_workers_preserve_every_index_entry_and_hide_lock_files(tmp_path):
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(_append_worker, str(tmp_path), worker, 50) for worker in range(2)]
        for future in futures:
            future.result()
    backend = storage.LocalStorageBackend(str(tmp_path))
    assert sorted(backend.get_json("index.json", [])) == [[worker, number] for worker in range(2) for number in range(50)]
    assert backend.list("") == ["index.json"]


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="Linux file-lock workers")
def test_two_real_processes_preserve_index_updates(tmp_path):
    context = multiprocessing.get_context("fork")
    workers = [context.Process(target=_append_worker, args=(str(tmp_path), worker, 40)) for worker in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(10)
        if worker.is_alive():
            worker.terminate()
            worker.join()
        assert worker.exitcode == 0
    assert len(storage.LocalStorageBackend(str(tmp_path)).get_json("index.json", [])) == 80


def test_stale_local_revision_cannot_overwrite_another_session(tmp_path):
    first = storage.LocalStorageBackend(str(tmp_path))
    second = storage.LocalStorageBackend(str(tmp_path))
    first.put_json("book.json", {"text": "original"})
    stale = first.get_json_snapshot("book.json", {})
    second.update_json("book.json", lambda book: {**book, "text": "new result"}, {})
    newer_bytes = second.get_bytes("book.json")
    with pytest.raises(storage.StorageConflict):
        first.compare_and_swap_json("book.json", stale.revision, {"text": "stale result"})
    assert first.get_bytes("book.json") == newer_bytes


@pytest.mark.parametrize("initial", [b"broken", b"{}"])
def test_corrupt_index_never_runs_mutator_or_replaces_original(tmp_path, initial):
    backend = storage.LocalStorageBackend(str(tmp_path))
    backend.put_bytes("index.json", initial)
    def forbidden(_value):
        pytest.fail("Corrupt data cannot reach a mutator")
    with pytest.raises(storage.StorageCorrupt):
        backend.update_json("index.json", forbidden, [])
    assert backend.get_bytes("index.json") == initial


def test_callback_failure_keeps_existing_document_and_does_not_mutate_default(tmp_path):
    backend = storage.LocalStorageBackend(str(tmp_path))
    original = {"available": 2, "operations": []}
    backend.put_json("budget.json", original)
    def reserve_too_much(budget):
        budget["operations"].append("attempt")
        if budget["available"] < 3:
            raise ValueError("insufficient budget")
        return budget
    with pytest.raises(ValueError, match="insufficient"):
        backend.update_json("budget.json", reserve_too_much, original)
    assert backend.get_json("budget.json") == original
    assert original["operations"] == []


def test_accidental_nested_write_fails_without_deadlock_or_replacement(tmp_path):
    backend = storage.LocalStorageBackend(str(tmp_path))
    backend.put_json("index.json", ["original"])
    def forbidden_nested_write(rows):
        backend.put_json("index.json", ["nested"])
        return rows + ["outer"]
    with pytest.raises(storage.StorageError, match="mesmo registro"):
        backend.update_json("index.json", forbidden_nested_write, [])
    assert backend.get_json("index.json") == ["original"]


class RpcDatabase:
    """HTTP double with atomic row CAS; SQL installation is a separate gate."""
    def __init__(self):
        self.rows = {}
        self.legacy = {}
        self.calls = []
        self.lock = Lock()

    def get(self, url, **kwargs):
        path = url.split("/object/faithbloom/", 1)[1]
        if path in self.legacy:
            return SimpleNamespace(status_code=200, content=self.legacy[path])
        return SimpleNamespace(status_code=404, content=b"")

    def post(self, url, **kwargs):
        payload = kwargs["json"]
        if "/storage/v1/object/list/" in url:
            return SimpleNamespace(status_code=200, json=lambda: [])
        operation = url.rsplit("_", 1)[1]
        with self.lock:
            self.calls.append((operation, deepcopy(payload)))
            path = payload.get("p_path")
            key = (payload["p_bucket"], path)
            row = self.rows.get(key, {"revision": 0, "found": False})
            if operation == "get":
                result = deepcopy(row)
            elif operation in {"cas", "delete"}:
                if row["revision"] != payload["p_expected_revision"]:
                    result = {"written": False, "revision": row["revision"]}
                else:
                    row = {"revision": row["revision"] + 1, "found": operation != "delete", "value": deepcopy(payload.get("p_value"))}
                    self.rows[key] = row
                    result = {"written": True, "revision": row["revision"]}
            elif operation == "list":
                prefix = payload["p_prefix"]
                rows = [{"path": path, "deleted": not row["found"]} for (bucket, path), row in sorted(self.rows.items()) if bucket == payload["p_bucket"] and (not prefix or path == prefix or path.startswith(prefix + "/"))]
                offset = payload["p_offset"]
                result = {"items": rows[offset:offset + 500], "has_more": len(rows) > offset + 500}
            else:
                raise AssertionError(operation)
        return SimpleNamespace(status_code=200, json=lambda: result)


@pytest.fixture
def rpc(monkeypatch):
    database = RpcDatabase()
    monkeypatch.setattr(storage.requests, "post", database.post)
    monkeypatch.setattr(storage.requests, "get", database.get)
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake", json_mode="rpc_cas")
    return backend, database


def test_rpc_two_workers_reapply_only_pure_update_after_conflict(rpc):
    first, database = rpc
    second = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake", json_mode="rpc_cas")
    first.put_json("index.json", [])
    barrier = Barrier(2)
    callback_counts = [0, 0]
    def worker(backend, number):
        def append(rows):
            callback_counts[number] += 1
            if callback_counts[number] == 1:
                barrier.wait(timeout=5)
            return rows + [number]
        backend.update_json("index.json", append, [])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, backend, number) for number, backend in enumerate((first, second))]
        for future in futures:
            future.result()
    assert sorted(first.get_json("index.json", [])) == [0, 1]
    assert sorted(callback_counts) == [1, 2]
    assert database.rows[("faithbloom", "index.json")]["revision"] == 3


def test_missing_rpc_never_falls_back_to_unconditional_upload(monkeypatch):
    calls = []
    def unavailable(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(status_code=404, text="secret internals")
    monkeypatch.setattr(storage.requests, "post", unavailable)
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake", json_mode="rpc_cas")
    with pytest.raises(storage.StorageUnavailable) as error:
        backend.update_json("index.json", lambda rows: rows + ["new"], [])
    assert len(calls) == 1
    assert "/rest/v1/rpc/" in calls[0]
    assert "secret internals" not in str(error.value)


def test_legacy_backend_refuses_atomic_api_before_any_outbound_call(monkeypatch):
    monkeypatch.setattr(storage.requests, "post", lambda *a, **k: pytest.fail("Legacy mode cannot pretend CAS"))
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    with pytest.raises(storage.StorageConcurrencyUnsupported):
        backend.update_json("index.json", lambda rows: rows + ["new"], [])


@pytest.mark.parametrize("operation", ["read", "update", "direct_create"])
def test_unmigrated_legacy_json_cannot_be_replaced_with_empty_catalog(rpc, operation):
    backend, database = rpc
    database.legacy["index.json"] = b'[{"id":"legacy-master"}]'
    with pytest.raises(storage.StorageMigrationRequired):
        if operation == "read":
            backend.get_json("index.json", [])
        elif operation == "direct_create":
            backend.compare_and_swap_json("index.json", 0, [])
        else:
            backend.update_json("index.json", lambda rows: rows + ["new"], [])
    assert database.legacy["index.json"] == b'[{"id":"legacy-master"}]'
    assert not database.rows
    assert not any(operation == "cas" for operation, _payload in database.calls)


def test_deleted_revision_cannot_be_resurrected_by_stale_writer(rpc):
    backend, database = rpc
    backend.put_json("book.json", {"text": "original"})
    old = backend.get_json_snapshot("book.json")
    backend.delete("book.json")
    tombstone = backend.get_json_snapshot("book.json", {})
    assert tombstone.exists is False and tombstone.revision == 2
    with pytest.raises(storage.StorageConflict):
        backend.compare_and_swap_json("book.json", old.revision, {"text": "old session"})
    database.legacy["book.json"] = b'{"text":"older Storage copy"}'
    assert backend.get_json("book.json", {}) == {}
    assert backend.list("") == []
    backend.compare_and_swap_json("book.json", tombstone.revision, {"text": "intentional recreation"})
    assert backend.get_json_snapshot("book.json").revision == 3


def test_rpc_list_and_bytes_use_same_canonical_documents(rpc):
    backend, _database = rpc
    backend.put_bytes("projects/book.json", b'{"title":"Master","unchanged":[1,2]}', "application/json")
    assert backend.list("projects") == ["projects/book.json"]
    assert json.loads(backend.get_bytes("projects/book.json")) == {"title": "Master", "unchanged": [1, 2]}
    assert backend.exists("projects/book.json")
    assert not backend.exists("projects/missing.json")


def test_network_failure_is_not_retried_as_a_conflict(rpc, monkeypatch):
    backend, _database = rpc
    attempts = []
    def timeout(*args, **kwargs):
        attempts.append(1)
        raise requests.Timeout("private key/URL")
    monkeypatch.setattr(storage.requests, "post", timeout)
    with pytest.raises(storage.StorageUnavailable) as error:
        backend.update_json("index.json", lambda rows: rows, [])
    assert len(attempts) == 1
    assert "private key" not in str(error.value)


def test_budget_rejection_runs_before_any_cas_or_outbound_spend(rpc):
    backend, database = rpc
    backend.put_json("budget.json", {"available": 1})
    database.calls.clear()
    def reject(budget):
        if budget["available"] < 2:
            raise ValueError("insufficient budget")
        return {"available": budget["available"] - 2}
    with pytest.raises(ValueError, match="insufficient"):
        backend.update_json("budget.json", reject, {})
    assert [operation for operation, _payload in database.calls] == ["get"]
    assert backend.get_json("budget.json")["available"] == 1


def test_foreign_tenant_and_missing_identity_fail_before_rpc_or_mutator(rpc, monkeypatch):
    raw, database = rpc
    wrapper = storage.TenantStorageBackend(raw)
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://identity.example")
    actor = access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": "own-account"})
    forbidden = lambda _value: pytest.fail("Denied callback cannot execute")
    with pytest.raises(access.AccessDenied):
        wrapper.update_json("index.json", forbidden, [])
    with access.access_context(actor):
        for operation in (
            lambda: wrapper.get_json_snapshot("tenants/someone-else/index.json", []),
            lambda: wrapper.compare_and_swap_json("tenants/someone-else/index.json", 0, []),
            lambda: wrapper.update_json("tenants/someone-else/index.json", forbidden, []),
        ):
            with pytest.raises(access.AccessDenied):
                operation()
    assert database.calls == []


def test_authorized_rpc_update_preserves_own_namespace_and_pilot_root(rpc, monkeypatch):
    raw, database = rpc
    raw.put_json("index.json", ["author-pilot"])
    wrapper = storage.TenantStorageBackend(raw)
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://identity.example")
    actor = access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": "own-account"})
    with access.access_context(actor):
        assert wrapper.update_json("index.json", lambda rows: rows + ["own"], []) == ["own"]
        uri = storage.storage_uri("index.json")
        assert uri == f"fb://tenants/{actor.tenant_id}/index.json"
        assert wrapper.get_json_snapshot(uri.removeprefix("fb://"), []).value == ["own"]
    assert database.rows[("faithbloom", "index.json")]["value"] == ["author-pilot"]
    assert database.rows[("faithbloom", f"tenants/{actor.tenant_id}/index.json")]["value"] == ["own"]


def test_rpc_mode_requires_explicit_configuration(monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_STORAGE_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_fake")
    monkeypatch.delenv("FAITHBLOOM_SUPABASE_JSON_MODE", raising=False)
    assert storage.get_backend().json_mode == "storage"
    monkeypatch.setenv("FAITHBLOOM_SUPABASE_JSON_MODE", "rpc_cas")
    assert storage.get_backend().json_concurrency == "postgres_RPC_CAS"
    monkeypatch.setenv("FAITHBLOOM_SUPABASE_JSON_MODE", "magic-etag")
    with pytest.raises(storage.StorageError):
        storage.get_backend()


def test_conflict_retries_are_bounded_and_do_not_change_callers_value(rpc, monkeypatch):
    backend, _database = rpc
    backend.put_json("index.json", [])
    callbacks = []
    def always_conflict(path, revision, value):
        raise storage.StorageConflict(revision, revision + 1)
    monkeypatch.setattr(backend, "compare_and_swap_json", always_conflict)
    def append(rows):
        rows.append("pending-result")
        callbacks.append(list(rows))
        return rows
    with pytest.raises(storage.StorageConflict):
        backend.update_json("index.json", append, [], max_attempts=3)
    assert callbacks == [["pending-result"]] * 3
    assert backend.get_json("index.json", []) == []


def test_repeating_rpc_list_page_is_a_failure_not_an_infinite_partial_list(rpc, monkeypatch):
    backend, _database = rpc
    monkeypatch.setattr(backend, "_rpc", lambda *a, **k: {"items": [{"path": "projects/book.json", "deleted": False}], "has_more": True})
    with pytest.raises(storage.StorageCorrupt):
        backend.list("projects")

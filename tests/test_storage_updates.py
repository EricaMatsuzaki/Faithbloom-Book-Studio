"""Migrated callers preserve native atomic failures and the pilot's limits."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import multiprocessing
from threading import Barrier
import time

import pytest

import storage_backend as storage
from storage_updates import update_json_document, json_update_mode


class LegacyBucket(storage.StorageBackend):
    name = "supabase"
    bucket = "test-pilot"
    json_concurrency = "read_modify_write_without_cross_worker_CAS"

    def __init__(self, root):
        self.store = storage.LocalStorageBackend(str(root))
        self.reads = self.writes = 0

    def get_json(self, path, default=None):
        self.reads += 1
        return self.store.get_json(path, default)

    def put_json(self, path, value):
        self.writes += 1
        return self.store.put_json(path, value)


def _increment(value):
    time.sleep(0.001)
    return {"count": value["count"] + 1}


def _pilot_process(data, cache, barrier):
    storage.CACHE_DIR = cache
    backend = LegacyBucket(data)
    barrier.wait(timeout=10)
    for _ in range(15):
        update_json_document(backend, "counter.json", _increment, {"count": 0}, allow_legacy_pilot=True)


@pytest.fixture(autouse=True)
def pilot(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    monkeypatch.setattr(storage, "CACHE_DIR", tmp_path / "cache")


def test_legacy_pilot_requires_explicit_consumer_opt_in(tmp_path):
    backend = LegacyBucket(tmp_path / "data")
    with pytest.raises(storage.StorageConcurrencyUnsupported):
        update_json_document(backend, "index.json", lambda rows: rows + ["new"], [])
    assert backend.reads == backend.writes == 0
    assert json_update_mode(backend) == "strict_backend_atomic_update"


def test_legacy_customer_mode_never_uses_pilot_compatibility(tmp_path, monkeypatch):
    backend = LegacyBucket(tmp_path / "data")
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    with pytest.raises(storage.StorageConcurrencyUnsupported):
        update_json_document(backend, "index.json", lambda rows: rows + ["new"], [], allow_legacy_pilot=True)
    assert backend.reads == backend.writes == 0


def test_rpc_failure_does_not_downgrade_to_upload(tmp_path):
    class FailingRpc(LegacyBucket):
        json_concurrency = "postgres_RPC_CAS"

        def update_json(self, *args, **kwargs):
            raise storage.StorageUnavailable("RPC response uncertain")

    backend = FailingRpc(tmp_path / "data")
    calls = []
    with pytest.raises(storage.StorageUnavailable, match="uncertain"):
        update_json_document(backend, "index.json", lambda rows: calls.append(True) or rows, [], allow_legacy_pilot=True)
    assert not calls and backend.reads == backend.writes == 0


def test_pilot_same_host_threads_do_not_lose_updates(tmp_path):
    backend = LegacyBucket(tmp_path / "data")
    ready = Barrier(3)

    def worker(_):
        ready.wait(timeout=5)
        for _ in range(15):
            update_json_document(backend, "counter.json", _increment, {"count": 0}, allow_legacy_pilot=True)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(worker, range(3)))
    assert backend.store.get_json("counter.json") == {"count": 45}
    assert json_update_mode(backend, allow_legacy_pilot=True) == "pilot_same_host_file_lock"


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="Shared-host file locks")
def test_pilot_same_host_processes_do_not_lose_updates(tmp_path):
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    processes = [context.Process(target=_pilot_process, args=(tmp_path / "data", tmp_path / "cache", barrier)) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(15)
        assert all(not process.is_alive() and process.exitcode == 0 for process in processes)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
    assert storage.LocalStorageBackend(str(tmp_path / "data")).get_json("counter.json") == {"count": 30}


def test_corrupt_index_is_not_replaced_by_an_empty_default(tmp_path):
    backend = LegacyBucket(tmp_path / "data")
    backend.store.put_bytes("index.json", b"broken original json")
    calls = []
    with pytest.raises(storage.StorageCorrupt):
        update_json_document(backend, "index.json", lambda rows: calls.append(True) or rows + ["new"], [], allow_legacy_pilot=True)
    assert not calls and backend.writes == 0
    assert backend.store.get_bytes("index.json") == b"broken original json"


def test_failed_callback_does_not_mutate_defaults_or_persist(tmp_path):
    backend = LegacyBucket(tmp_path / "data")
    default = {"items": []}
    original = deepcopy(default)

    def rejected(value):
        value["items"].append("uncommitted")
        raise PermissionError("revoked")

    with pytest.raises(PermissionError, match="revoked"):
        update_json_document(backend, "index.json", rejected, default, allow_legacy_pilot=True)
    assert default == original and backend.writes == 0
    assert not backend.store.exists("index.json")


def test_nonfinite_result_is_rejected_before_legacy_write(tmp_path):
    backend = LegacyBucket(tmp_path / "data")
    backend.store.put_json("index.json", {"count": 1})
    with pytest.raises(ValueError):
        update_json_document(backend, "index.json", lambda value: {"count": float("nan")}, {}, allow_legacy_pilot=True)
    assert backend.writes == 0
    assert backend.store.get_json("index.json") == {"count": 1}

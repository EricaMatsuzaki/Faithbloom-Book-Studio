"""Exercise visual claims across processes and native RPC callback replay.

Providers and downstream media writes are harmless doubles. The project, plans,
local file locks and RPC revision checks use the real application code.
"""
from copy import deepcopy
import multiprocessing
from queue import Empty
from unittest.mock import Mock

import pytest

import armazenamento
import governance_runtime
import orchestrator_visual as ov
import storage_backend as storage
import visual_execution as ve
from test_storage_atomic_updates import RpcDatabase
from test_storage_updates import LegacyBucket
from test_visual_execution_integration import project  # noqa: F401 - shared fixture


def _claim_worker(root, plan_id, payload, operation_key, ready, entered, release,
                  calls, results, provider_barrier=None, persist_barrier=None):
    """Each child owns an independent backend and process-local executor lock."""
    backend = storage.LocalStorageBackend(root)
    storage.BACKEND = armazenamento.BACKEND = backend

    def authorize(_action, **kwargs):
        # Both workers observed the initial ledger before either may reserve.
        ready.wait(timeout=10)
        return {"operation_id": kwargs["operation_id"], "test_evidence": True}

    governance_runtime.authorize_generation = authorize

    def produce(index, route):
        with calls.get_lock():
            calls.value += 1
        entered.set()
        if provider_barrier is not None:
            provider_barrier.wait(timeout=10)
        if release is not None and not release.wait(timeout=10):
            raise RuntimeError("test provider release timed out")
        return {"fake_provider_result": payload, "index": index}

    def persist(raw, index, operation_id):
        if persist_barrier is not None:
            persist_barrier.wait(timeout=10)
        return {"id": operation_id, "asset_id": operation_id, "raw": raw}

    try:
        result = ve._run(plan_id, "world_candidates", payload, 1, "imagem", True,
                         operation_key, produce, persist)
        results.put(("complete", result["id"]))
    except Exception as exc:
        results.put(("blocked", type(exc).__name__, str(exc)))


def _join_workers(workers):
    for worker in workers:
        worker.join(timeout=10)
    for worker in workers:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
    assert all(worker.exitcode == 0 for worker in workers)


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(),
                    reason="Independent shared-disk workers require fork")
@pytest.mark.parametrize("operation_keys", [("same", "same"), ("first", "changed")])
def test_two_processes_cannot_claim_same_paid_input(project, operation_keys):
    context = multiprocessing.get_context("fork")
    ready, entered, release = context.Barrier(2), context.Event(), context.Event()
    calls, results = context.Value("i", 0), context.Queue()
    plan_id = project["plan"]["id"]
    workers = [context.Process(target=_claim_worker, args=(
        str(project["backend"].root), plan_id, {"shared_input": True}, key,
        ready, entered, release, calls, results,
    )) for key in operation_keys]
    messages = []
    try:
        for worker in workers:
            worker.start()
        assert entered.wait(timeout=10), "No worker reached the provider double"
        try:
            messages.append(results.get(timeout=10))
        except Empty:
            pytest.fail("The competing worker entered the provider instead of rejecting its claim")
        assert messages[0][0] == "blocked", messages
        assert messages[0][1] == "VisualExecutionError", messages
        assert calls.value == 1
    finally:
        release.set()
        _join_workers(workers)
    messages.append(results.get(timeout=5))
    assert sorted(message[0] for message in messages) == ["blocked", "complete"]
    operations = ve.list_visual_operations(plan_id)
    assert len(operations) == 1
    assert operations[0]["status"] == "complete"
    assert operations[0]["items"][0]["attempt_token"]
    assert operations[0]["budget"]["estimated_spent_usd"] == pytest.approx(.08)
    assert operations[0]["budget"]["reserved_usd"] == 0


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(),
                    reason="Independent shared-disk workers require fork")
def test_two_processes_reserve_against_latest_shared_project_budget(project):
    plan = ov.load_visual_plan(project["plan"]["id"])
    plan["budget_limit_usd"] = .12  # Each .08 call fits; two calls do not.
    ov.save_visual_plan(plan)
    context = multiprocessing.get_context("fork")
    ready, entered, release = context.Barrier(2), context.Event(), context.Event()
    calls, results = context.Value("i", 0), context.Queue()
    workers = [context.Process(target=_claim_worker, args=(
        str(project["backend"].root), plan["id"], {"distinct_input": number},
        "default", ready, entered, release, calls, results,
    )) for number in range(2)]
    messages = []
    try:
        for worker in workers:
            worker.start()
        assert entered.wait(timeout=10)
        try:
            messages.append(results.get(timeout=10))
        except Empty:
            pytest.fail("Both workers spent against an obsolete project budget")
        assert messages[0][0] == "blocked", messages
        assert messages[0][1] == "PermissionError", messages
        assert calls.value == 1
        ledger = ve._ledger(plan)
        totals = ve._totals(ledger)
        assert len(ledger["operations"]) == 1
        assert totals["estimated_spent_usd"] + totals["reserved_usd"] <= .12
    finally:
        release.set()
        _join_workers(workers)
    messages.append(results.get(timeout=5))
    assert sorted(message[0] for message in messages) == ["blocked", "complete"]
    operations = ve.list_visual_operations(plan["id"])
    assert len(operations) == 1
    assert operations[0]["budget"]["estimated_spent_usd"] == pytest.approx(.08)
    assert operations[0]["budget"]["reserved_usd"] == 0


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(),
                    reason="Independent shared-disk workers require fork")
def test_two_processes_preserve_each_operations_checkpoints(project):
    context = multiprocessing.get_context("fork")
    ready, entered = context.Barrier(2), context.Event()
    providers, persistence = context.Barrier(2), context.Barrier(2)
    calls, results = context.Value("i", 0), context.Queue()
    plan_id = project["plan"]["id"]
    workers = [context.Process(target=_claim_worker, args=(
        str(project["backend"].root), plan_id, {"distinct_input": number},
        "default", ready, entered, None, calls, results, providers, persistence,
    )) for number in range(2)]
    try:
        for worker in workers:
            worker.start()
        messages = [results.get(timeout=15) for _ in workers]
    finally:
        _join_workers(workers)
    assert all(message[0] == "complete" for message in messages), messages
    assert calls.value == 2
    operations = ve.list_visual_operations(plan_id)
    assert len(operations) == 2
    assert {item["id"] for item in operations} == {message[1] for message in messages}
    assert all(item["status"] == "complete" for item in operations)
    assert all(item["items"][0]["attempt_token"] for item in operations)
    assert all(item["governance_receipt"]["operation_id"] == item["id"] for item in operations)
    assert operations[0]["budget"]["estimated_spent_usd"] == pytest.approx(.16)
    assert operations[0]["budget"]["reserved_usd"] == 0


def test_rpc_claim_conflict_replays_only_pure_mutation_and_keeps_attempt_token(project, monkeypatch):
    database = RpcDatabase()
    monkeypatch.setattr(storage.requests, "post", database.post)
    monkeypatch.setattr(storage.requests, "get", database.get)
    backend = storage.SupabaseStorageBackend(
        "https://example.supabase.co", "sb_secret_fake", json_mode="rpc_cas")
    plan = deepcopy(project["plan"])
    backend.put_json(f"orchestrator/visual_plans/{plan['id']}.json", plan)
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setattr(governance_runtime, "authorize_generation", lambda _action, **kwargs: {
        "operation_id": kwargs["operation_id"], "test_evidence": True})
    original_cas, original_update = backend.compare_and_swap_json, backend.update_json
    candidate_claims, callback_active = [], []
    ledger_writes = 0
    conflicted = False

    def conflicting_cas(path, revision, value):
        nonlocal conflicted, ledger_writes
        if "visual_budgets/" in path:
            ledger_writes += 1
            claims = [operation for operation in value["operations"].values()
                      if any(item["state"] == "running" for item in operation["items"])]
            if ledger_writes == 1:
                assert claims, "The first reservation must also durably claim its paid item"
            if claims:
                candidate_claims.append(deepcopy(claims[0]))
            if claims and not conflicted:
                conflicted = True
                concurrent = deepcopy(value)
                concurrent["operations"] = {}
                concurrent["concurrent_marker"] = "preserved"
                committed = original_cas(path, revision, concurrent)
                raise storage.StorageConflict(revision, committed.revision)
        return original_cas(path, revision, value)

    def auditing_update(path, mutator, default=None, **kwargs):
        def observed(value):
            callback_active.append(True)
            try:
                return mutator(value)
            finally:
                callback_active.pop()
        return original_update(path, observed, default, **kwargs)

    monkeypatch.setattr(backend, "compare_and_swap_json", conflicting_cas)
    monkeypatch.setattr(backend, "update_json", auditing_update)
    produced, persisted = Mock(), Mock()

    def produce(index, route):
        assert not callback_active, "Paid work cannot execute inside a replayable callback"
        current = backend.get_json(ve._ledger_path(plan))
        operation = next(iter(current["operations"].values()))
        assert operation["items"][index]["state"] == "running"
        assert operation["items"][index]["reserved"] is True
        assert operation["items"][index]["attempt_token"]
        produced(index, route)
        return {"fake_provider_result": True}

    def persist(raw, index, operation_id):
        assert not callback_active
        persisted(raw, index, operation_id)
        return {"id": operation_id, "asset_id": operation_id}

    result = ve._run(plan["id"], "world_candidates", {"rpc": "claim"}, 1,
                     "imagem", True, "rpc-claim", produce, persist)
    assert conflicted
    assert len(candidate_claims) >= 2
    assert candidate_claims[0]["items"][0]["attempt_token"] == candidate_claims[1]["items"][0]["attempt_token"]
    assert all(candidate["items"][0]["reserved"] for candidate in candidate_claims[:2])
    produced.assert_called_once()
    persisted.assert_called_once()
    ledger = backend.get_json(ve._ledger_path(plan))
    assert ledger["concurrent_marker"] == "preserved"
    assert len(ledger["operations"]) == 1
    assert result["status"] == "complete"
    assert result["budget"]["estimated_spent_usd"] == pytest.approx(.08)
    assert result["budget"]["reserved_usd"] == 0


@pytest.mark.parametrize("state,reserved", [
    ("running", False), ("uncertain", False), ("raw", True),
    ("succeeded", True), ("reconciled_failed", True),
])
def test_inconsistent_attempt_reservation_is_corrupt_and_cannot_free_budget(project, monkeypatch, state, reserved):
    plan = project["plan"]
    path = ve._ledger_path(plan)
    ledger = {"project_id": plan["project_id"], "operations": {
        "prior-operation": {"id": "prior-operation", "plan_id": plan["id"],
            "input_fingerprint": "different-input", "status": "needs_reconciliation",
            "items": [{"index": 0, "state": state, "reserved": reserved,
                       "estimated_usd": .08, "actual_usd": None, "attempt_token": "prior-attempt"}]},
    }}
    project["backend"].put_json(path, ledger)
    before = project["backend"].get_bytes(path)
    monkeypatch.setattr(governance_runtime, "authorize_generation", lambda _action, **kwargs: {
        "operation_id": kwargs["operation_id"], "test_evidence": True})
    produce, persist = Mock(return_value="fake result"), Mock(return_value={"id": "fake asset"})
    with pytest.raises(ve.VisualExecutionError):
        ve._run(plan["id"], "world_candidates", {"new_input": True}, 1,
                "imagem", True, "new-input", produce, persist)
    produce.assert_not_called()
    persist.assert_not_called()
    assert project["backend"].get_bytes(path) == before


@pytest.mark.parametrize("state,estimated,actual,reserved", [
    ("succeeded", 1e308, None, False),
    ("succeeded", .08, 1e308, False),
    ("running", 1e308, None, True),
    ("pending", 1e308, None, False),
])
def test_overflowing_project_cost_totals_block_even_without_limit(project, monkeypatch,
                                                                 state, estimated, actual, reserved):
    plan = ov.load_visual_plan(project["plan"]["id"])
    plan["budget_limit_usd"] = None
    ov.save_visual_plan(plan)
    path = ve._ledger_path(plan)
    ledger = {"project_id": plan["project_id"], "operations": {}}
    for number in range(2):
        operation_id = f"overflow-{number}"
        ledger["operations"][operation_id] = {
            "id": operation_id, "plan_id": plan["id"], "input_fingerprint": operation_id,
            "items": [{"index": 0, "state": state, "reserved": reserved,
                       "estimated_usd": estimated, "actual_usd": actual,
                       "attempt_token": operation_id, "result": {"id": operation_id}}],
        }
    project["backend"].put_json(path, ledger)
    before = project["backend"].get_bytes(path)
    monkeypatch.setattr(governance_runtime, "authorize_generation", lambda _action, **kwargs: {
        "operation_id": kwargs["operation_id"], "test_evidence": True})
    produce, persist = Mock(return_value="fake result"), Mock(return_value={"id": "fake asset"})
    with pytest.raises(ve.VisualExecutionError):
        ve._run(plan["id"], "world_candidates", {"new_input": True}, 1,
                "imagem", True, "new-input", produce, persist)
    produce.assert_not_called()
    persist.assert_not_called()
    assert project["backend"].get_bytes(path) == before


@pytest.mark.parametrize("mode", ["pilot", "multi_tenant"])
def test_executor_legacy_compatibility_is_limited_to_explicit_pilot(project, monkeypatch, mode):
    class LegacyVisualBackend(LegacyBucket):
        def get_bytes(self, path):
            return self.store.get_bytes(path)

    backend = LegacyVisualBackend(project["backend"].root)
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", mode)
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setattr(governance_runtime, "authorize_generation", lambda _action, **kwargs: {
        "operation_id": kwargs["operation_id"], "test_evidence": True})
    produce, persist = Mock(return_value="fake result"), Mock(return_value={"id": "fake asset"})

    def run():
        return ve._run(project["plan"]["id"], "world_candidates", {"legacy": True}, 1,
                       "imagem", True, "legacy-input", produce, persist)

    if mode == "multi_tenant":
        with pytest.raises(storage.StorageConcurrencyUnsupported):
            run()
        produce.assert_not_called()
        persist.assert_not_called()
        assert backend.writes == 0
        assert not backend.store.exists(ve._ledger_path(project["plan"]))
    else:
        result = run()
        assert result["status"] == "complete"
        assert result["budget"]["estimated_spent_usd"] == pytest.approx(.08)
        produce.assert_called_once()
        persist.assert_called_once()
        assert backend.writes > 0

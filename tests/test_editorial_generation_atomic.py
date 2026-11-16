"""Real worker races and lost acknowledgements cannot buy duplicate units."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import multiprocessing
import os
import socket
from threading import Barrier, Event
from unittest.mock import Mock

import pytest
import requests

import armazenamento
import editorial_dispatch as dispatch
import editorial_generation_runtime as runtime
import editorial_products as studio
import storage_backend as storage
from test_storage_atomic_updates import RpcDatabase


@pytest.fixture
def durable(tmp_path, monkeypatch):
    import controle_geracao
    for name in ("_RECENT", "_EXECUTIONS"):
        monkeypatch.setattr(controle_geracao, name, {})
    monkeypatch.setattr(controle_geracao, "_IN_FLIGHT", set())
    backend = storage.LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    monkeypatch.chdir(tmp_path)
    return backend


def product(count=1):
    value = studio.create_product("other", "Livro próprio", "Praticar atenção e cuidado",
                                  unit_count=count, custom_blocks=["Abertura"])
    studio.save_product(value)
    return value


def unit(number=1):
    return {"title": f"Aprender com cuidado {number}", "objectives": ["Observar uma ação concreta"],
            "source_refs": [], "blocks": [{"label": "Abertura", "text": "Observe uma flor e conte como você cuidaria dela."}]}


def provider(**kwargs):
    return unit(json.loads(kwargs["instrucao"])["unit_plan"]["number"])


def execution(backend, value):
    return backend.get_json(runtime._path(value["storage_path"]))["editorial_product"]["execution"]


def _worker(root, reference, barrier, entered, release, calls, results, remote=False):
    backend = storage.LocalStorageBackend(root)
    storage.BACKEND = armazenamento.BACKEND = backend
    if remote:
        runtime.socket.gethostname = lambda: "another-execution-host"
    source = studio.load_product(reference)
    def paid(**kwargs):
        with calls.get_lock():
            calls.value += 1
        entered.set()
        assert release.wait(10)
        return provider(**kwargs)
    try:
        if barrier is not None:
            barrier.wait(10)
        studio.generate_product(source, paid, confirmed=True)
        results.put("completed")
    except Exception as exc:
        results.put(type(exc).__name__)


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="Linux file-lock workers")
def test_two_independent_processes_share_one_paid_product_claim(durable):
    source = product()
    context = multiprocessing.get_context("fork")
    barrier, entered, release = context.Barrier(2), context.Event(), context.Event()
    calls, results = context.Value("i", 0), context.Queue()
    workers = [context.Process(target=_worker, args=(str(durable.root), source["storage_path"],
        barrier, entered, release, calls, results)) for _ in range(2)]
    try:
        for worker in workers:
            worker.start()
        assert entered.wait(10)
        assert results.get(timeout=10) == "PermissionError"
        release.set()
        assert results.get(timeout=10) == "completed"
        for worker in workers:
            worker.join(10)
            assert worker.exitcode == 0
    finally:
        release.set()
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
        results.close()
    assert calls.value == 1
    saved = studio.load_product(source["storage_path"])
    assert len(saved["editorial_product"]["units"]) == 1
    assert [a["state"] for a in saved["editorial_product"]["execution"]["attempts"]] == ["applied"]


def test_native_studio_and_central_dispatcher_cannot_buy_the_same_product(durable):
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("other", "Livro", "Objetivo",
        custom_blocks=["Abertura"], unit_count=1)["id"])
    source = studio.load_product(run["source_ref"])
    entered, release = Event(), Event()
    calls = []
    def paid(**kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return provider(**kwargs)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(studio.generate_product, source, paid, confirmed=True)
        try:
            assert entered.wait(5)
            with pytest.raises(PermissionError, match="ativa|conferência"):
                dispatch.execute_editorial_generation(run["id"], confirmed=True, resume_confirmed=True,
                    chamar_llm=lambda **_: pytest.fail("Central caller duplicated native generation"))
        finally:
            release.set()
        future.result(10)
    completed = dispatch.execute_editorial_generation(run["id"], confirmed=True,
        chamar_llm=lambda **_: pytest.fail("Canonical completed result must be reused"))
    assert calls == [1] and completed["generation"]["status"] == "completed"


@pytest.mark.parametrize("landed", [False, True])
@pytest.mark.parametrize("boundary", ["execution", "paid_attempt"])
def test_claim_failure_or_lost_ack_sends_zero_provider_calls(durable, monkeypatch, landed, boundary):
    source = product()
    original = durable.update_json
    failed = False
    def interrupted(path, callback, default=None, **kwargs):
        nonlocal failed
        current = durable.get_json(path, default)
        candidate = callback(deepcopy(current))
        state = runtime._execution(candidate)
        match = bool(state.get("claim")) and (bool(state["attempts"]) if boundary == "paid_attempt" else not state["attempts"])
        if match and not failed:
            failed = True
            if landed:
                original(path, callback, default, **kwargs)
            raise storage.StorageUnavailable("Lost exact claim acknowledgement")
        return original(path, callback, default, **kwargs)
    monkeypatch.setattr(durable, "update_json", interrupted)
    paid = Mock(side_effect=AssertionError("Provider must follow a committed acknowledgement"))
    with pytest.raises(storage.StorageUnavailable):
        studio.generate_product(source, paid, confirmed=True)
    paid.assert_not_called()
    state = execution(durable, source)
    if landed and boundary == "execution":
        assert state["claim"]["owner_active"] is True
        with pytest.raises(PermissionError):
            studio.generate_product(studio.load_product(source["storage_path"]), paid, confirmed=True)
        runtime.recover_generation(source["storage_path"], execution_token=state["claim"]["token"], confirmed=True)
    if landed and boundary == "paid_attempt":
        assert [a["state"] for a in state["attempts"]] == ["uncertain"]
        with pytest.raises(PermissionError):
            studio.generate_product(studio.load_product(source["storage_path"]), paid, confirmed=True)


@pytest.mark.parametrize("landed", [False, True])
def test_raw_response_ack_loss_preserves_received_output_and_never_rebuys_it(durable, monkeypatch, landed):
    source = product()
    original = durable.update_json
    failed = False
    def interrupted(path, callback, default=None, **kwargs):
        nonlocal failed
        current = durable.get_json(path, default)
        candidate = callback(deepcopy(current))
        old = runtime._execution(current)
        new = runtime._execution(candidate)
        raw = any(a["state"] == "raw" for a in new["attempts"])
        was_raw = any(a["state"] == "raw" for a in old["attempts"])
        if raw and not was_raw and not failed:
            failed = True
            if landed:
                original(path, callback, default, **kwargs)
            raise storage.StorageUnavailable("Lost raw response acknowledgement")
        return original(path, callback, default, **kwargs)
    monkeypatch.setattr(durable, "update_json", interrupted)
    paid = Mock(side_effect=provider)
    with pytest.raises(runtime.EditorialCheckpointError) as received:
        studio.generate_product(source, paid, confirmed=True)
    assert received.value.response == unit()
    assert paid.call_count == 1
    state = execution(durable, source)
    assert state["attempts"][-1]["state"] == ("raw" if landed else "uncertain")
    if not landed:
        with pytest.raises(PermissionError):
            studio.generate_product(studio.load_product(source["storage_path"]), paid, confirmed=True)
        runtime.reconcile_attempt(source["storage_path"], attempt_token=received.value.attempt_token,
            confirmed=True, provider_outcome="succeeded", note="Recovered exact structured response from received call",
            recovered_response=received.value.response, actual_usd=0.03)
    completed = studio.generate_product(studio.load_product(source["storage_path"]),
        lambda **_: pytest.fail("Received response must not be purchased again"), confirmed=True)
    assert completed["editorial_product"]["units"][0]["title"] == unit()["title"]
    assert paid.call_count == 1


def test_lost_final_checkpoint_ack_can_finish_without_another_provider(durable, monkeypatch):
    source = product()
    original = durable.update_json
    failed = False
    def interrupted(path, callback, default=None, **kwargs):
        nonlocal failed
        candidate = callback(deepcopy(durable.get_json(path, default)))
        meta = candidate["editorial_product"]
        if meta["units"] and meta.get("draft") is None and not failed:
            failed = True
            original(path, callback, default, **kwargs)
            raise storage.StorageUnavailable("Final source write landed, acknowledgement lost")
        return original(path, callback, default, **kwargs)
    monkeypatch.setattr(durable, "update_json", interrupted)
    paid = Mock(side_effect=provider)
    with pytest.raises(storage.StorageUnavailable):
        studio.generate_product(source, paid, confirmed=True)
    assert paid.call_count == 1
    saved = studio.generate_product(studio.load_product(source["storage_path"]),
        lambda **_: pytest.fail("Final canonical units already exist"), confirmed=True)
    assert len(saved["editorial_product"]["units"]) == 1


def test_current_annotations_survive_paid_return_and_source_checkpoints(durable):
    source = product()
    def paid(**kwargs):
        durable.update_json(runtime._path(source["storage_path"]),
            lambda current: {**current, "author_notes": ["Independent current annotation"]})
        return provider(**kwargs)
    saved = studio.generate_product(source, paid, confirmed=True)
    assert saved["author_notes"] == ["Independent current annotation"]
    assert studio.load_product(source["storage_path"])["author_notes"] == saved["author_notes"]


def test_stale_manual_save_cannot_replace_new_paid_content(durable):
    source = product()
    stale = deepcopy(source)
    studio.generate_product(source, provider, confirmed=True)
    before = durable.get_bytes(runtime._path(source["storage_path"]))
    with pytest.raises(storage.StorageConflict):
        studio.save_product(stale)
    assert durable.get_bytes(runtime._path(source["storage_path"])) == before


def test_live_local_owner_cannot_be_recovered_or_manually_overwritten(durable):
    source = product()
    entered, release = Event(), Event()
    def paid(**kwargs):
        entered.set()
        assert release.wait(5)
        return provider(**kwargs)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(studio.generate_product, source, paid, confirmed=True)
        try:
            assert entered.wait(5)
            state = runtime.generation_status(source["storage_path"])
            with pytest.raises(PermissionError, match="ativo"):
                runtime.recover_generation(source["storage_path"], execution_token=state["claim"]["token"],
                    confirmed=True, shutdown_note="A note cannot override a live local owner")
            with pytest.raises(PermissionError):
                studio.save_product(studio.load_product(source["storage_path"]))
            with pytest.raises(PermissionError, match="ativa"):
                runtime.reconcile_attempt(source["storage_path"], attempt_token=state["attempts"][-1]["token"],
                    confirmed=True, provider_outcome="failed", note="Attempt still running")
        finally:
            release.set()
        future.result(10)


def test_two_human_reconcilers_cannot_replace_each_others_evidence(durable, monkeypatch):
    source = product()
    with pytest.raises(RuntimeError):
        studio.generate_product(source, lambda **_: (_ for _ in ()).throw(RuntimeError("Unknown provider result")), confirmed=True)
    token = runtime.generation_status(source["storage_path"])["attempts"][-1]["token"]
    original, barrier = runtime._update, Barrier(2)
    def paused(*args, **kwargs):
        barrier.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(runtime, "_update", paused)
    def reconcile(note):
        try:
            runtime.reconcile_attempt(source["storage_path"], attempt_token=token, confirmed=True,
                provider_outcome="failed", note=note, actual_usd=0.02)
            return "saved"
        except storage.StorageConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(reconcile, ["First receipt", "Second receipt"]))
    assert sorted(results) == ["conflict", "saved"]
    attempt = execution(durable, source)["attempts"][-1]
    assert len(attempt["reconciliations"]) == 1 and attempt["actual_usd"] == 0.02


def test_legacy_draft_needs_shutdown_adoption_and_separate_provider_evidence(durable):
    source = product()
    meta = source["editorial_product"]
    meta.pop("execution")
    meta["draft"] = {"id": "legacy-draft", "units": [], "spec_fingerprint": studio._spec_fingerprint(source)}
    durable.put_json(runtime._path(source["storage_path"]), source)
    paid = Mock(side_effect=provider)
    assert runtime.generation_status(source["storage_path"])["status"] == "legacy_needs_review"
    with pytest.raises(PermissionError):
        studio.generate_product(source, paid, confirmed=True)
    with pytest.raises(PermissionError):
        runtime.adopt_legacy_interruption(source["storage_path"], confirmed=True)
    adopted = runtime.adopt_legacy_interruption(source["storage_path"], confirmed=True,
        shutdown_note="Deployment confirms every old generating worker has stopped")
    token = adopted["editorial_product"]["execution"]["attempts"][-1]["token"]
    with pytest.raises(PermissionError):
        studio.generate_product(studio.load_product(source["storage_path"]), paid, confirmed=True)
    runtime.reconcile_attempt(source["storage_path"], attempt_token=token, provider_outcome="not_sent",
        confirmed=True, note="Provider logs confirm the legacy request was never submitted", actual_usd=0)
    saved = studio.generate_product(studio.load_product(source["storage_path"]), paid, confirmed=True)
    assert paid.call_count == 1 and len(saved["editorial_product"]["units"]) == 1


def test_stale_run_snapshot_cannot_erase_updated_history_or_generation(durable):
    run = dispatch.create_editorial_run("other", "Livro", "Objetivo", custom_blocks=["Abertura"])
    stale = deepcopy(run)
    run["history"].append({"event": "current"})
    current = dispatch.save_run(run)
    stale["title"] = "Old source title"
    with pytest.raises(storage.StorageConflict):
        dispatch.save_run(stale)
    assert dispatch.load_run(run["id"])["history"] == current["history"]


def test_rpc_conflict_replays_only_pure_claim_with_identical_attempt_identity(durable, monkeypatch):
    database = RpcDatabase()
    monkeypatch.setattr(storage.requests, "post", database.post)
    monkeypatch.setattr(storage.requests, "get", database.get)
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake", json_mode="rpc_cas")
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    source = product()
    original = backend.compare_and_swap_json
    identities = []
    conflicted = False
    def compare(path, expected, value):
        nonlocal conflicted
        if path != runtime._path(source["storage_path"]):
            return original(path, expected, value)
        state = runtime._execution(value)
        if state.get("claim") and not state["attempts"] and not value["editorial_product"].get("draft"):
            identities.append(deepcopy(state["claim"]))
            if not conflicted:
                conflicted = True
                current = backend.get_json(path)
                current["independent_rpc_note"] = "preserve current metadata"
                original(path, expected, current)
        return original(path, expected, value)
    monkeypatch.setattr(backend, "compare_and_swap_json", compare)
    paid = Mock(side_effect=provider)
    saved = studio.generate_product(source, paid, confirmed=True)
    assert paid.call_count == 1 and conflicted
    assert len(identities) == 2 and identities[0] == identities[1]
    assert saved["independent_rpc_note"] == "preserve current metadata"


@pytest.mark.parametrize("selected", ["gemini", "groq", "openrouter"])
@pytest.mark.parametrize("failure", ["503", "404", "timeout", "invalid_json"])
def test_native_default_has_one_http_attempt_without_model_or_provider_fallback(durable, monkeypatch, selected, failure):
    import ai_provider_router as router
    import openrouter_client
    monkeypatch.setattr(router, "GEMINI_API_KEY", "test-configured-gemini" if selected == "gemini" else "")
    monkeypatch.setattr(router, "GROQ_API_KEY", "test-configured-groq" if selected != "openrouter" else "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-configured-openrouter")
    monkeypatch.setattr(openrouter_client, "OPENROUTER_API_KEY", "test-configured-openrouter")
    monkeypatch.setattr(router, "_OPENROUTER_DISABLED_REASON", "")
    monkeypatch.setattr(router, "_gemini_candidate_models", lambda: ["gemini-first", "gemini-second"])
    monkeypatch.setattr(router.time, "sleep", lambda *_: pytest.fail("Strict paid request must not retry/backoff"))
    posts = []
    def request(url, **kwargs):
        posts.append(url)
        if failure == "timeout":
            raise requests.Timeout("Response unknown")
        response = requests.Response()
        response.status_code = 200 if failure == "invalid_json" else int(failure)
        response.url = "https://provider.example/request"
        if selected == "gemini":
            payload = {"candidates": [{"content": {"parts": [{"text": "not valid JSON"}]}}]}
        else:
            payload = {"choices": [{"message": {"content": "not valid JSON"}}]}
        response._content = json.dumps(payload).encode()
        return response
    monkeypatch.setattr(router.requests, "post", request)
    source = product()
    with pytest.raises(Exception):
        studio.generate_product(source, confirmed=True)
    assert len(posts) == 1
    assert selected in posts[0]
    assert execution(durable, source)["attempts"][-1]["state"] == "uncertain"
    with pytest.raises(PermissionError):
        studio.generate_product(studio.load_product(source["storage_path"]), confirmed=True)
    assert len(posts) == 1


def test_sync_repairs_only_orphan_run_projection_after_canonical_completion(durable):
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("other", "Livro", "Objetivo",
        custom_blocks=["Abertura"], unit_count=1)["id"])
    source = studio.load_product(run["source_ref"])
    studio.generate_product(source, provider, confirmed=True)
    durable.update_json(dispatch._path(run["id"]), lambda current: {
        **current, "generation": {"status": "running", "dispatch_token": "old-run-projection"}})
    repaired = dispatch.sync_source(run["id"])
    assert repaired["generation"]["status"] == "completed"
    assert repaired["source"]["editorial_product"]["units"] == source["editorial_product"]["units"]


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="Linux independent worker")
def test_late_foreign_response_cannot_replace_human_reconciliation(durable):
    source = product()
    context = multiprocessing.get_context("fork")
    entered, release, results = context.Event(), context.Event(), context.Queue()
    calls = context.Value("i", 0)
    worker = context.Process(target=_worker, args=(str(durable.root), source["storage_path"],
        None, entered, release, calls, results, True))
    try:
        worker.start()
        assert entered.wait(10)
        current = runtime.generation_status(source["storage_path"])
        token, attempt = current["claim"]["token"], current["attempts"][-1]["token"]
        with pytest.raises(PermissionError, match="evidência"):
            runtime.recover_generation(source["storage_path"], execution_token=token, confirmed=True)
        runtime.recover_generation(source["storage_path"], execution_token=token, confirmed=True,
            shutdown_note="Deployment operator attests this exact remote execution was stopped")
        runtime.reconcile_attempt(source["storage_path"], attempt_token=attempt, provider_outcome="failed",
            confirmed=True, note="Provider receipt was checked separately", actual_usd=0.04)
        before = deepcopy(execution(durable, source)["attempts"][-1])
        release.set()
        assert results.get(timeout=10) == "EditorialCheckpointError"
        worker.join(10)
        assert worker.exitcode == 0
        after = execution(durable, source)["attempts"][-1]
        assert after == before and after["state"] == "reconciled_failed" and after["actual_usd"] == 0.04
        assert calls.value == 1
    finally:
        release.set()
        if worker.is_alive():
            worker.terminate()
            worker.join(5)
        results.close()


@pytest.mark.parametrize("corrupt", ["invalid_status", "missing_owner", "malformed_owner", "empty_legacy_draft"])
def test_corrupt_execution_never_rearms_or_overwrites_original(durable, corrupt):
    source = product()
    state = source["editorial_product"]["execution"]
    if corrupt == "invalid_status":
        state["status"] = "assume_safe_and_retry"
    elif corrupt == "missing_owner":
        state["status"] = "running"
    elif corrupt == "malformed_owner":
        state.update(status="running", claim={"token": "bad", "owner_active": True})
    else:
        source["editorial_product"].pop("execution")
        source["editorial_product"]["draft"] = {}
    durable.put_json(runtime._path(source["storage_path"]), source)
    before = durable.get_bytes(runtime._path(source["storage_path"]))
    with pytest.raises((ValueError, PermissionError)):
        studio.generate_product(source, lambda **_: pytest.fail("Corruption cannot authorize spending"), confirmed=True)
    assert durable.get_bytes(runtime._path(source["storage_path"])) == before
    if corrupt == "empty_legacy_draft":
        with pytest.raises(ValueError, match="rascunho antigo"):
            runtime.adopt_legacy_interruption(source["storage_path"], confirmed=True,
                shutdown_note="Old workers were stopped; corrupted draft still requires repair")
        assert durable.get_bytes(runtime._path(source["storage_path"])) == before


def test_raw_only_recovery_needs_no_new_provider_budget_or_consent(durable, monkeypatch):
    source = product()
    original = durable.update_json
    failed = False
    def lose_ack(path, callback, default=None, **kwargs):
        nonlocal failed
        candidate = callback(deepcopy(durable.get_json(path, default)))
        if not failed and any(a["state"] == "raw" for a in runtime._execution(candidate)["attempts"]):
            failed = True
            original(path, callback, default, **kwargs)
            raise storage.StorageUnavailable("Received raw persisted, acknowledgement lost")
        return original(path, callback, default, **kwargs)
    monkeypatch.setattr(durable, "update_json", lose_ack)
    with pytest.raises(runtime.EditorialCheckpointError):
        studio.generate_product(source, provider, confirmed=True)
    import controle_geracao
    import governance_runtime
    import ai_provider_router
    monkeypatch.setattr(controle_geracao, "validar_orcamento", lambda *_: pytest.fail("No new budget reservation for received-only recovery"))
    monkeypatch.setattr(governance_runtime, "authorize_generation", lambda *_a, **_k: pytest.fail("No new provider authorization for received-only recovery"))
    monkeypatch.setattr(ai_provider_router, "chamar_llm", lambda *_a, **_k: pytest.fail("No provider required for received output"))
    saved = studio.generate_product(studio.load_product(source["storage_path"]), confirmed=False)
    assert len(saved["editorial_product"]["units"]) == 1
    assert saved["editorial_product"]["execution"]["status"] == "completed"


def test_current_approval_of_previous_version_is_archived_when_new_version_completes(durable):
    source = product()
    studio.generate_product(source, provider, confirmed=True)
    studio.approve_product(source, "First reviewer", content_reviewed=True, accuracy_reviewed=True)
    old_version = source["editorial_product"]["active_version"]
    def paid(**kwargs):
        def current_approval(current):
            current["editorial_product"]["approval"]["reviewer"] = "Current concurrent review evidence"
            return current
        durable.update_json(runtime._path(source["storage_path"]), current_approval)
        return provider(**kwargs)
    saved = studio.generate_product(source, paid, confirmed=True, new_version=True)
    archived = next(v for v in saved["editorial_product"]["versions"] if v["id"] == old_version)
    assert archived["approval"]["reviewer"] == "Current concurrent review evidence"
    assert saved["editorial_product"]["approval"] is None  # The new version still requires its own human review.


def test_current_content_edit_is_not_replaced_by_a_paid_response(durable):
    source = product()
    def paid(**kwargs):
        def human_edit(current):
            updated = unit()
            updated["title"] = "Human-edited canonical unit"
            current["editorial_product"]["draft"]["units"].append(
                studio.validate_unit(updated, current["editorial_product"]["unit_plan"][0],
                                     current["editorial_product"]["spec"]))
            return current
        durable.update_json(runtime._path(source["storage_path"]), human_edit)
        return provider(**kwargs)
    with pytest.raises(storage.StorageConflict):
        studio.generate_product(source, paid, confirmed=True)
    saved = studio.load_product(source["storage_path"])
    assert saved["editorial_product"]["draft"]["units"][0]["title"] == "Human-edited canonical unit"
    attempt = saved["editorial_product"]["execution"]["attempts"][-1]
    assert attempt["state"] == "raw" and attempt["response"]["title"] == unit()["title"]


def test_secondary_save_ack_cannot_erase_correction_after_canonical_checkpoint(durable):
    source = product()
    corrected = False
    paid = Mock(side_effect=provider)
    def checkpoint(state):
        nonlocal corrected
        if (state["editorial_product"].get("draft") or {}).get("units") and not corrected:
            corrected = True
            def human_correction(current):
                current["editorial_product"]["draft"]["units"][0]["title"] = "Current human correction after source checkpoint"
                return current
            durable.update_json(runtime._path(state["storage_path"]), human_correction)
        studio.save_product(state)
    with pytest.raises(storage.StorageConflict):
        studio.generate_product(source, paid, checkpoint=checkpoint, confirmed=True)
    assert paid.call_count == 1 and corrected
    current = studio.load_product(source["storage_path"])
    assert current["editorial_product"]["draft"]["units"][0]["title"] == "Current human correction after source checkpoint"
    saved = studio.generate_product(current, lambda **_: pytest.fail("The unit was already received and corrected"), confirmed=False)
    assert saved["editorial_product"]["units"][0]["title"] == "Current human correction after source checkpoint"
    assert paid.call_count == 1

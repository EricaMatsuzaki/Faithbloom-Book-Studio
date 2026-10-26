"""Independent editorial acceptance; temporary storage and harmless doubles only."""
from copy import deepcopy
from unittest.mock import Mock

import pytest
import requests

import armazenamento
import controle_geracao as costs
import editorial_generation_runtime as runtime
import editorial_products as studio
import editorial_dispatch as dispatch
import governance_runtime as governance
import saas_access as access
import storage_backend as storage
from test_editorial_generation_atomic import durable, product, provider, unit  # noqa: F401
from test_storage_atomic_updates import RpcDatabase


def _leave_received_raw(source, durable, monkeypatch):
    original = durable.update_json
    interrupted = False

    def lose_raw_ack(path, callback, default=None, **kwargs):
        nonlocal interrupted
        candidate = callback(deepcopy(durable.get_json(path, default)))
        execution = runtime._execution(candidate)
        if not interrupted and any(a["state"] == "raw" for a in execution["attempts"]):
            interrupted = True
            original(path, callback, default, **kwargs)
            raise storage.StorageUnavailable("Independent acceptance: received response committed, ACK lost")
        return original(path, callback, default, **kwargs)

    monkeypatch.setattr(durable, "update_json", lose_raw_ack)
    paid = Mock(side_effect=provider)
    with pytest.raises(runtime.EditorialCheckpointError):
        studio.generate_product(source, paid, confirmed=True)
    assert paid.call_count == 1
    assert interrupted
    canonical = studio.load_product(source["storage_path"])
    assert runtime._execution(canonical)["attempts"][-1]["state"] == "raw"
    return canonical


def test_received_only_recovery_requires_neither_budget_nor_provider(durable, monkeypatch):
    source = _leave_received_raw(product(), durable, monkeypatch)
    import ai_provider_router
    monkeypatch.setattr(costs, "validar_orcamento", lambda *_: pytest.fail("No new paid units need a budget check"))
    monkeypatch.setattr(governance, "authorize_generation", lambda *_a, **_k: pytest.fail("No new transmission needs authorization"))
    monkeypatch.setattr(governance, "text_provider_configuration", lambda: pytest.fail("Received data does not require a configured provider"))
    monkeypatch.setattr(ai_provider_router, "chamar_llm", lambda *_a, **_k: pytest.fail("Do not buy the received response again"))
    saved = studio.generate_product(source, confirmed=False)
    assert saved["editorial_product"]["units"][0]["title"] == unit()["title"]
    assert runtime._execution(saved)["status"] == "completed"
    assert [a["state"] for a in runtime._execution(saved)["attempts"]] == ["applied"]


def test_partial_raw_recovery_authorizes_only_units_still_unpurchased(durable, monkeypatch):
    source = _leave_received_raw(product(count=2), durable, monkeypatch)
    original_budget = costs.validar_orcamento
    original_authorize = governance.authorize_generation
    budgets, authorizations = [], []

    def budget(amount):
        budgets.append(amount)
        return original_budget(amount)

    def authorize(action, **kwargs):
        authorizations.append(kwargs["projected_cost"])
        return original_authorize(action, **kwargs)

    monkeypatch.setattr(costs, "validar_orcamento", budget)
    monkeypatch.setattr(governance, "authorize_generation", authorize)
    paid = Mock(side_effect=provider)
    saved = studio.generate_product(source, paid, confirmed=True)
    assert paid.call_count == 1
    assert len(saved["editorial_product"]["units"]) == 2
    # The body and governance may independently check the same remaining cost.
    # Neither check may include the unit whose response was already received.
    assert budgets and all(value == pytest.approx(costs.estimar_custo("texto", 1)) for value in budgets)
    assert authorizations == [pytest.approx(costs.estimar_custo("texto", 1))]


def test_paid_attempt_cas_replay_preserves_identity_and_runs_provider_once(durable, monkeypatch):
    database = RpcDatabase()
    monkeypatch.setattr(storage.requests, "post", database.post)
    monkeypatch.setattr(storage.requests, "get", database.get)
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake", json_mode="rpc_cas")
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    source = product()
    original_cas, original_update = backend.compare_and_swap_json, backend.update_json
    claims, active = [], []
    conflicted = False

    def compare(path, expected, value):
        nonlocal conflicted
        if path == runtime._path(source["storage_path"]):
            attempts = runtime._execution(value)["attempts"]
            if attempts and attempts[-1]["state"] == "running":
                claims.append(deepcopy(attempts[-1]))
                if not conflicted:
                    conflicted = True
                    latest = backend.get_json(path)
                    latest["independent_cas_note"] = "Do not overwrite me during paid-claim conflict replay"
                    original_cas(path, expected, latest)
        return original_cas(path, expected, value)

    def observed_update(path, callback, default=None, **kwargs):
        def observe(current):
            active.append(True)
            try:
                return callback(current)
            finally:
                active.pop()
        return original_update(path, observe, default, **kwargs)

    monkeypatch.setattr(backend, "compare_and_swap_json", compare)
    monkeypatch.setattr(backend, "update_json", observed_update)
    paid = Mock()

    def generate(**kwargs):
        assert not active, "A replayable callback cannot execute paid work"
        paid(**kwargs)
        return provider(**kwargs)

    saved = studio.generate_product(source, generate, confirmed=True)
    assert conflicted and len(claims) >= 2
    assert claims[0] == claims[1]
    paid.assert_called_once()
    assert saved["independent_cas_note"].startswith("Do not overwrite")


def test_tenant_reference_is_authorized_before_claim_or_paid_generation(durable, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://identity.example")
    monkeypatch.delenv("FAITHBLOOM_ACCESS_ROLES", raising=False)
    a, b = [access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": sub})
            for sub in ("editorial-independent-a", "editorial-independent-b")]
    tenant = storage.TenantStorageBackend(durable)
    monkeypatch.setattr(storage, "BACKEND", tenant)
    monkeypatch.setattr(armazenamento, "BACKEND", tenant)
    with access.access_context(a):
        source = product()
        reference = source["storage_path"]
        assert reference.startswith("fb://tenants/" + a.tenant_id + "/livros/")
    before = {path: durable.get_bytes(path) for path in durable.list("tenants/" + a.tenant_id)}
    paid = Mock(side_effect=AssertionError("Unauthorized caller must never reach paid generation"))
    with access.access_context(b):
        with pytest.raises(access.AccessDenied):
            studio.generate_product(deepcopy(source), paid, confirmed=True)
        with pytest.raises(access.AccessDenied):
            runtime.generation_status(reference)
    with pytest.raises(access.AccessDenied):
        studio.generate_product(deepcopy(source), paid, confirmed=True)
    paid.assert_not_called()
    assert {path: durable.get_bytes(path) for path in durable.list("tenants/" + a.tenant_id)} == before


def test_central_real_router_timeout_has_one_http_attempt_and_blocks_resume(durable, monkeypatch):
    import ai_provider_router as router
    import openrouter_client
    monkeypatch.setattr(router, "GEMINI_API_KEY", "fake-available-gemini")
    monkeypatch.setattr(router, "GROQ_API_KEY", "fake-available-groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-available-openrouter")
    monkeypatch.setattr(openrouter_client, "OPENROUTER_API_KEY", "fake-available-openrouter")
    monkeypatch.setattr(router, "_OPENROUTER_DISABLED_REASON", "")
    monkeypatch.setattr(router, "_gemini_candidate_models", lambda: ["first-model", "second-model"])
    monkeypatch.setattr(router.time, "sleep", lambda *_: pytest.fail("Central paid execution must not back off and resend"))
    posts = []

    def request(url, **kwargs):
        posts.append(url)
        raise requests.Timeout("Independent acceptance: provider outcome unknown")

    monkeypatch.setattr(router.requests, "post", request)
    run = dispatch.initialize_specialist(dispatch.create_editorial_run(
        "other", "Paid central boundary", "Describe an act of care", unit_count=1,
        custom_blocks=["Abertura"])["id"])
    with pytest.raises(requests.Timeout):
        dispatch.execute_editorial_generation(run["id"], confirmed=True)
    assert len(posts) == 1 and "gemini" in posts[0]
    source = studio.load_product(run["source_ref"])
    assert runtime._execution(source)["attempts"][-1]["state"] == "uncertain"
    assert dispatch.load_run(run["id"])["generation"]["status"] == "interrupted"
    with pytest.raises(PermissionError):
        dispatch.execute_editorial_generation(run["id"], confirmed=True, resume_confirmed=True)
    assert len(posts) == 1


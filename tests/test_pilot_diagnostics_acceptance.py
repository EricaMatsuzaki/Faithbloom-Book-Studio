"""Operational diagnostics must match configured routing and verified cleanup.

All API credentials are synthetic; provider requests are forbidden. Storage
checks exercise temporary real files and the actual tenant boundary.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import ai_provider_router as router
import production_deployment as deployment
import saas_access as access
import stable_hardening as hardening
import storage_backend as storage


@pytest.fixture
def diagnostics(monkeypatch):
    monkeypatch.setattr(hardening, "backend_status", lambda: {"modo": "supabase", "persistente_cloud": True})
    monkeypatch.setattr(deployment, "backend_status", lambda: {"modo": "supabase", "persistente_cloud": True})
    monkeypatch.setattr(deployment, "load_settings", lambda: {})
    monkeypatch.setattr(router.requests, "post", lambda *a, **k: pytest.fail("Diagnostics must not buy a generation"))
    monkeypatch.setattr(router.requests, "get", lambda *a, **k: pytest.fail("Configuration checks must not discover models"))
    return {"FAITHBLOOM_DEPLOYMENT_MODE": "production", "FAITHBLOOM_AUTH_MODE": "external"}


@pytest.mark.parametrize("key,provider", [
    ("GEMINI_API_KEY", "gemini"), ("GOOGLE_API_KEY", "gemini"),
    ("GROQ_API_KEY", "groq"), ("OPENROUTER_API_KEY", "openrouter"),
])
def test_valid_provider_configuration_is_not_reported_as_missing_openrouter(diagnostics, key, provider):
    synthetic_value = "synthetic-never-display-provider-value"
    env = {**diagnostics, key: synthetic_value, "FAITHBLOOM_PROVEDOR_TEXTO": provider}
    result = hardening.environment_diagnostics(env)
    check = next(x for x in result["checks"] if x["id"] == "text_provider")
    assert check["ok"] and result["ok_for_production"]
    assert result["text_provider"]["providers"] == [provider]
    assert result["text_provider"]["live_access_verified"] is False
    snapshot = deployment.deployment_config_snapshot(env)
    assert snapshot["env_present"][key] is True
    assert snapshot["text_provider"]["primary"] == provider
    assert synthetic_value not in json.dumps([result, snapshot])


@pytest.mark.parametrize("selected", ["gemini", "groq", "openrouter"])
def test_forced_missing_provider_cannot_borrow_an_available_alternative(diagnostics, selected):
    keys = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
    env = {**diagnostics, "FAITHBLOOM_PROVEDOR_TEXTO": selected,
           **{key: "synthetic-alternative" for name, key in keys.items() if name != selected}}
    result = hardening.environment_diagnostics(env)
    assert result["text_provider"]["configured"] is False
    assert result["text_provider"]["providers"] == []
    assert result["text_provider"]["primary"] == selected
    assert "text_provider" in {x["id"] for x in result["blockers"]}
    assert deployment.deployment_config_snapshot(env)["text_provider"]["configured"] is False


def test_runtime_diagnostic_uses_strict_router_and_honors_disabled_selected_route(diagnostics, monkeypatch):
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-openrouter")
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", "openrouter")
    monkeypatch.setattr(router, "GEMINI_API_KEY", "synthetic-loaded-gemini")
    monkeypatch.setattr(router, "GROQ_API_KEY", "")
    monkeypatch.setattr(router, "_OPENROUTER_DISABLED_REASON", "synthetic-disabled-route")
    result = hardening.environment_diagnostics()
    snapshot = deployment.deployment_config_snapshot()
    assert result["text_provider"]["configured"] is False
    assert result["text_provider"]["source"] == "runtime_configuration"
    assert snapshot["env_present"]["OPENROUTER_API_KEY"] is True
    assert snapshot["text_provider"]["configured"] is False
    assert "synthetic-loaded-gemini" not in json.dumps([result, snapshot])


def test_google_alias_runtime_is_reported_without_changing_loaded_keys(diagnostics, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "synthetic-alias")
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", "gemini")
    monkeypatch.setattr(router, "GEMINI_API_KEY", "")
    monkeypatch.setattr(router, "GROQ_API_KEY", "")
    result = hardening.environment_diagnostics()
    assert result["text_provider"]["providers"] == ["gemini"]
    assert result["text_provider"]["live_access_verified"] is False
    assert router.GEMINI_API_KEY == ""


def test_explicit_snapshot_does_not_borrow_runtime_configuration(diagnostics, monkeypatch):
    monkeypatch.setattr(router, "provider_status", lambda **_: pytest.fail("An explicit snapshot must not borrow loaded keys"))
    env = {**diagnostics, "FAITHBLOOM_PROVEDOR_TEXTO": "Bearer synthetic-private-preference"}
    before = dict(env)
    result = hardening.environment_diagnostics(env)
    snapshot = deployment.deployment_config_snapshot(env)
    assert env == before
    assert not result["text_provider"]["configured"]
    assert not result["text_provider"]["configuration_valid"]
    assert "synthetic-private-preference" not in json.dumps([result, snapshot])


def test_invalid_runtime_preference_is_reported_invalid_without_echoing_its_value(diagnostics, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", "Bearer synthetic-private-preference")
    monkeypatch.setattr(router, "GEMINI_API_KEY", "synthetic-loaded-gemini")
    result = hardening.environment_diagnostics()
    assert not result["text_provider"]["configured"]
    assert not result["text_provider"]["configuration_valid"]
    assert result["text_provider"]["primary"] == "indisponível"
    assert "synthetic-private-preference" not in json.dumps(result)


def test_manual_e2e_attestation_does_not_claim_an_automatic_live_test(diagnostics, monkeypatch):
    monkeypatch.setattr(hardening, "storage_roundtrip_probe", lambda: pytest.fail("Checklist evaluation cannot run a storage probe"))
    evidence = {x["id"]: True for x in deployment.real_e2e_checklist() if x["required"]}
    result = deployment.evaluate_real_e2e(evidence)
    assert result["cloud_e2e_passed"]
    assert result["evidence_mode"] == "manual_attestation"
    assert result["live_access_verified_automatically"] is False
    text = next(x for x in result["items"] if x["id"] == "openrouter_text")
    assert "provedor selecionado" in text["label"]


class ProbeFiles(storage.LocalStorageBackend):
    def __init__(self, root, failure=""):
        super().__init__(root)
        self.failure = failure
        self.events = []
        self.reads = 0

    def put_json(self, path, value):
        self.events.append(("write", path))
        result = super().put_json(path, value)
        if self.failure == "write_ack":
            raise storage.StorageUnavailable("synthetic-token-must-never-be-in-report")
        return result

    def get_json(self, path, default=None):
        self.events.append(("read", path))
        self.reads += 1
        if self.failure == "read" and self.reads == 1 or self.failure == "delete_read" and self.reads == 2:
            raise storage.StorageUnavailable("synthetic-token-must-never-be-in-report")
        if self.failure == "mismatch" and self.reads == 1:
            return {"different": "payload"}
        return super().get_json(path, default)

    def delete(self, path):
        self.events.append(("delete", path))
        if self.failure == "delete":
            raise storage.StorageUnavailable("synthetic-token-must-never-be-in-report")
        if self.failure == "noop_delete":
            return
        return super().delete(path)


@pytest.mark.parametrize("failure", ["delete", "noop_delete", "delete_read"])
def test_probe_cannot_report_success_when_cleanup_is_not_confirmed(tmp_path, monkeypatch, failure):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    backend = ProbeFiles(tmp_path, failure)
    monkeypatch.setattr(hardening, "BACKEND", backend)
    result = hardening.storage_roundtrip_probe()
    assert not result["ok"] and not result["cleanup_verified"]
    assert result["checks"]["write"] and result["checks"]["read"]
    assert "synthetic-token" not in json.dumps(result)
    if failure != "delete_read":
        assert backend.exists(result["path"])
    else:
        assert not backend.exists(result["path"])
    assert sum(event == "write" for event, _ in backend.events) == 1


@pytest.mark.parametrize("failure", ["write_ack", "read", "mismatch"])
def test_probe_retains_failed_result_and_cleans_its_object_without_retry(tmp_path, monkeypatch, failure):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    backend = ProbeFiles(tmp_path, failure)
    monkeypatch.setattr(hardening, "BACKEND", backend)
    result = hardening.storage_roundtrip_probe()
    assert not result["ok"] and result["cleanup_verified"]
    assert not backend.exists(result["path"])
    assert sum(event == "write" for event, _ in backend.events) == 1
    assert sum(event == "delete" for event, _ in backend.events) == 1
    assert "synthetic-token" not in json.dumps(result)


def test_successful_probes_are_unique_and_do_not_touch_existing_books(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    backend = ProbeFiles(tmp_path)
    backend.put_json("livros/original.json", {"book_id": "original", "text": "preserve"})
    original = backend.get_bytes("livros/original.json")
    backend.events.clear()
    monkeypatch.setattr(hardening, "BACKEND", backend)
    first, second = hardening.storage_roundtrip_probe(), hardening.storage_roundtrip_probe()
    assert first["ok"] and second["ok"]
    assert first["path"] != second["path"]
    assert all(path.startswith("system/probes/") for _, path in backend.events)
    assert backend.list("system/probes") == []
    assert backend.get_bytes("livros/original.json") == original


@pytest.fixture
def tenant_probe(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://synthetic.identity")
    monkeypatch.delenv("FAITHBLOOM_ACCESS_ROLES", raising=False)
    actors = [access.actor_from_trusted_claims({"authenticated": True, "iss": "https://synthetic.identity", "sub": sub})
              for sub in ("a", "b")]
    raw = ProbeFiles(tmp_path)
    backend = storage.TenantStorageBackend(raw)
    monkeypatch.setattr(hardening, "BACKEND", backend)
    return actors, raw, backend


@pytest.mark.parametrize("kind", ["missing_actor", "viewer", "no_delete"])
def test_probe_authorizes_all_capabilities_before_any_storage_io(tenant_probe, monkeypatch, kind):
    actors, raw, _ = tenant_probe
    if kind == "missing_actor":
        result = hardening.storage_roundtrip_probe()
    else:
        actor = replace(actors[0], role="viewer") if kind == "viewer" else actors[0]
        if kind == "no_delete":
            monkeypatch.setattr(access, "PERMISSIONS", {**access.PERMISSIONS, "member": {"view", "storage.read", "storage.list", "storage.write"}})
        with access.access_context(actor):
            result = hardening.storage_roundtrip_probe()
    assert not result["ok"] and not result["checks"]["authorization"]
    assert result["error_type"] == "AccessDenied"
    assert raw.events == []
    assert raw.list("") == []


def test_probe_is_bound_to_own_tenant_and_preserves_both_accounts(tenant_probe):
    actors, raw, backend = tenant_probe
    for actor in actors:
        with access.access_context(actor):
            backend.put_json("livros/same.json", {"private": actor.subject})
    originals = {actor.tenant_id: raw.get_bytes(f"tenants/{actor.tenant_id}/livros/same.json") for actor in actors}
    raw.events.clear()
    for actor in actors:
        with access.access_context(actor):
            result = hardening.storage_roundtrip_probe()
        assert result["ok"] and result["cleanup_verified"]
    writes = [path for event, path in raw.events if event == "write"]
    # TenantStorageBackend writes through put_bytes, which is below this double's
    # put_json boundary; physical files still prove exact cleanup/isolation.
    assert not writes
    assert raw.list("tenants") == [f"tenants/{actor.tenant_id}/livros/same.json" for actor in sorted(actors, key=lambda a: a.tenant_id)]
    for actor in actors:
        assert raw.get_bytes(f"tenants/{actor.tenant_id}/livros/same.json") == originals[actor.tenant_id]


def test_actor_change_cannot_redirect_probe_reads_or_cleanup_to_another_account(tenant_probe, monkeypatch):
    actors, raw, backend = tenant_probe
    actor_a, actor_b = actors
    fixed = "a" * 32
    monkeypatch.setattr(hardening.uuid, "uuid4", lambda: SimpleNamespace(hex=fixed))
    b_path = f"tenants/{actor_b.tenant_id}/system/probes/{fixed}.json"
    raw.put_json(b_path, {"private_b": "preserve"})
    before = raw.get_bytes(b_path)
    original_put = raw.put_bytes

    def switch_after_write(path, data, content_type=None):
        result = original_put(path, data, content_type)
        access._ACTOR.set(actor_b)  # Trusted test injection, not a browser claim.
        return result

    monkeypatch.setattr(raw, "put_bytes", switch_after_write)
    with access.access_context(actor_a):
        result = hardening.storage_roundtrip_probe()
    assert not result["ok"] and not result["cleanup_verified"]
    assert result["error_type"] == result["cleanup_error_type"] == "AccessDenied"
    assert raw.get_bytes(b_path) == before
    assert raw.exists(f"tenants/{actor_a.tenant_id}/system/probes/{fixed}.json")
    assert actor_a.tenant_id not in json.dumps(result) and actor_b.tenant_id not in json.dumps(result)

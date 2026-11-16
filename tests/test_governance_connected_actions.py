"""Offline checks of connected governance decisions, not profile declarations."""
from copy import deepcopy
from dataclasses import replace
import json
from unittest.mock import Mock

import pytest

import controle_geracao as costs
import governance
import governance_runtime as runtime
import saas_access as access
import storage_backend as storage


@pytest.fixture
def backend(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(tmp_path / "durable")
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    monkeypatch.setattr(costs, "LOG_PATH", tmp_path / "meter.jsonl")
    monkeypatch.setattr(costs, "POLITICA", replace(costs.POLITICA, orcamento_diario_usd=1.0))
    return backend


def authorize(**changes):
    options = dict(confirmed=True, provider_configured=True, operation_id="specific-draft-fingerprint",
        source_module="assistant_services.py", consent_confirmed=True, paid=False,
        state={"profile_id": "private-profile", "payload": {"body": "PRIVATE-DRAFT", "to": "owner@example.test"}})
    options.update(changes)
    return runtime.authorize_external_action("assistant.gmail.send", **options)


def saved(backend):
    return [backend.get_json(path) for path in backend.list() if path.startswith("governance/")]


def test_free_send_requires_real_four_agent_checks_and_durable_receipts_without_meter(backend, monkeypatch):
    called = []
    for role, (module_name, entrypoint) in governance.SPECIALIST_ACTION_CHECKS.items():
        import importlib
        module = importlib.import_module("agents." + module_name)
        original = getattr(module, entrypoint)
        def checker(*args, _role=role, _original=original, **kwargs):
            called.append((_role, args[0], kwargs["requires_confirmation"]))
            return _original(*args, **kwargs)
        monkeypatch.setattr(module, entrypoint, checker)
    def no_meter(*args, **kwargs):
        raise AssertionError("A declared free send must not reserve, charge or read the paid meter")
    monkeypatch.setattr(costs, "custo_hoje_usd", no_meter)
    monkeypatch.setattr(costs, "validar_orcamento", no_meter)
    result = authorize()
    assert {row[0] for row in called} == set(governance.SPECIALIST_ACTION_CHECKS)
    assert all(row[1:] == ("assistant.gmail.send", True) for row in called)
    assert len(result["specialist_refs"]) == 4
    assert len(saved(backend)) == 5
    policy = next(item for item in saved(backend) if item["role_id"] == "governance_runtime")
    assert policy["scope"] == "single_external_action"
    assert policy["metadata"]["budget_basis"] == "adapter_explicit_unpaid_action"
    assert policy["metadata"]["provider_live_verified"] is False
    assert {item["path"] for item in policy["metadata"]["artifacts"] if item.get("path", "").startswith("agents/")} == {
        f"agents/{module_name}.py" for module_name, _ in governance.SPECIALIST_ACTION_CHECKS.values()}
    assert policy["allowed"] is False  # Pilot applicability never manufactures a tenant.
    assert policy["metadata"]["execution_decision"]["allowed"] is True
    serialized = json.dumps(saved(backend))
    assert all(private not in serialized for private in ("PRIVATE-DRAFT", "owner@example.test", "private-profile"))
    assert not costs.LOG_PATH.exists()


@pytest.mark.parametrize("change,control", [
    ({"confirmed": False}, "human_approval"),
    ({"consent_confirmed": False}, "personal_consent"),
    ({"provider_configured": False}, "provider_configuration"),
    ({"paid": False, "projected_cost": .1}, "cost_classification"),
    ({"paid": "false"}, "cost_classification"),
    ({"paid": None}, "cost_classification"),
    ({"paid": True}, "budget"),
    ({"paid": True, "projected_cost": 2.0}, "budget"),
])
def test_missing_action_evidence_blocks_free_or_paid_external_provider(backend, change, control):
    provider = Mock()
    with pytest.raises(runtime.GovernanceBlocked):
        authorize(**change)
        provider()
    provider.assert_not_called()
    policy = next(item for item in saved(backend) if item["role_id"] == "governance_runtime")
    assert any(item["code"] == control and item["status"] != "PASS" for item in policy["findings"])
    assert policy["metadata"]["execution_decision"]["allowed"] is False


def test_known_paid_external_action_uses_budget_guard_without_a_second_charge(backend):
    result = authorize(paid=True, projected_cost=.2, budget_remaining=.2)
    assert result["allowed_for_mode"] is True
    assert not costs.LOG_PATH.exists()
    assert next(item for item in saved(backend) if item["role_id"] == "governance_runtime")["metadata"]["paid"] is True


@pytest.mark.parametrize("source", [
    {"source_identity": {"source_ref": "fb://tenants/foreign/books/original.json"}},
    {"inputs": [{"canonical_source_ref": "tenants/foreign/books/original.json"}]},
    {"storage_path": "fb://tenants/foreign/../books/original.json"},
])
def test_nested_foreign_resource_scope_cannot_be_hidden_in_draft(backend, source):
    with pytest.raises(runtime.GovernanceBlocked):
        authorize(state=source)
    assert saved(backend) == []


@pytest.mark.parametrize("corruption", ["duplicate", "missing", "unavailable"])
def test_missing_or_duplicate_specialist_evidence_never_authorizes(backend, monkeypatch, corruption):
    diagnostics = governance.run_all_diagnostics()
    if corruption == "duplicate":
        diagnostics[-1] = deepcopy(diagnostics[0])
    elif corruption == "missing":
        diagnostics.pop()
    else:
        diagnostics[-1]["findings"] = [governance.finding("diagnostic_unavailable", "UNKNOWN", "Unavailable", [])]
    monkeypatch.setattr(governance, "run_all_diagnostics", lambda: diagnostics)
    with pytest.raises(runtime.GovernanceBlocked, match="evidências"):
        authorize()


def test_specialist_denial_overrides_central_policy_and_is_visible_in_evidence(backend, monkeypatch):
    from agents import governanca_dados
    original = governanca_dados.check_data_action
    def reject(action, **kwargs):
        result = original(action, **kwargs)
        target = next(item for item in result["findings"] if item["code"] == "personal_consent")
        target["status"] = "FAIL"
        return result
    monkeypatch.setattr(governanca_dados, "check_data_action", reject)
    with pytest.raises(runtime.GovernanceBlocked):
        authorize()
    policies = saved(backend)
    assert len(policies) == 5
    assert all(item["metadata"]["execution_decision"]["allowed"] is False for item in policies)
    policy = next(item for item in policies if item["role_id"] == "governance_runtime")
    assert next(item for item in policy["findings"] if item["code"] == "specialist_action_checks")["status"] == "FAIL"
    data = next(item for item in policies if item["role_id"] == "data_governance")
    assert any(item["code"] == "runtime_personal_consent" and item["status"] == "FAIL" for item in data["findings"])


@pytest.mark.parametrize("status", ["FAIL", "UNKNOWN", "WARN"])
def test_new_specialist_control_is_binding_and_retained_in_history(backend, monkeypatch, status):
    from agents import governanca_dados
    original = governanca_dados.check_data_action
    def added_control(action, **kwargs):
        result = original(action, **kwargs)
        result["findings"].append(governance.finding("data_minimization", status,
            "Minimização de dados nesta ação", ["runtime:data-minimization-check"]))
        result["allowed"] = False
        return result
    monkeypatch.setattr(governanca_dados, "check_data_action", added_control)
    with pytest.raises(runtime.GovernanceBlocked):
        authorize()
    data = next(item for item in saved(backend) if item["role_id"] == "data_governance")
    assert any(item["code"] == "runtime_data_minimization" and item["status"] == status for item in data["findings"])
    assert data["metadata"]["execution_decision"]["allowed"] is False


def test_explicit_silent_denial_cannot_be_changed_to_approval(backend, monkeypatch):
    from agents import governanca_dados
    def reject(action, **kwargs):
        result = governance.build_report("data_governance", "Dados", [
            governance.finding("tenant_scope", "PASS", "Controle observado", ["runtime:scope"]),
            governance.finding("personal_consent", "PASS", "Controle observado", ["runtime:consent"])])
        result["allowed"] = False
        return result
    monkeypatch.setattr(governanca_dados, "check_data_action", reject)
    with pytest.raises(runtime.GovernanceBlocked):
        authorize()
    data = next(item for item in saved(backend) if item["role_id"] == "data_governance")
    assert any(item["code"] == "runtime_specialist_decision" and item["status"] == "FAIL" for item in data["findings"])


def test_report_write_that_silently_drops_evidence_cannot_authorize_send(backend, monkeypatch):
    monkeypatch.setattr(backend, "put_json", lambda *args, **kwargs: None)
    with pytest.raises(runtime.GovernanceBlocked, match="evidências"):
        authorize()


def test_readback_with_changed_operation_is_rejected_before_provider(backend, monkeypatch):
    load = governance.load_report
    def wrong_receipt(*args, **kwargs):
        result = load(*args, **kwargs)
        result["metadata"]["operation_sha256"] = "another-operation"
        return result
    monkeypatch.setattr(governance, "load_report", wrong_receipt)
    with pytest.raises(runtime.GovernanceBlocked, match="evidências"):
        authorize()


@pytest.mark.parametrize("change", ["finding", "metadata", "name"])
def test_changed_persisted_evidence_is_rejected_but_original_snapshot_survives(backend, change):
    report = governance.build_report("data_governance", "Dados", [governance.finding("consent", "UNKNOWN", "Consentimento", [])], metadata={"input_sha256": "original-hash"})
    first = governance.save_report(report)
    original_bytes = backend.get_bytes(storage.uri_to_path(first))
    second = governance.save_report(report)
    stored = backend.get_json(storage.uri_to_path(second))
    if change == "finding":
        stored["findings"][0]["status"] = "PASS"
        stored["findings"][0]["evidence"] = ["unobserved/event"]
    elif change == "metadata":
        stored["metadata"]["input_sha256"] = "substituted-hash"
    else:
        stored["name"] = "Another agent"
    backend.put_json(storage.uri_to_path(second), stored)
    with pytest.raises(storage.StorageError, match="alterada"):
        governance.load_report(second)
    assert backend.get_bytes(storage.uri_to_path(first)) == original_bytes
    assert governance.load_report(first)["status"] == "UNKNOWN"
    assert len(governance.list_reports()) == 1


def test_legacy_history_remains_readable_without_claiming_signed_integrity(backend):
    report = governance.build_report("it_governance", "TI", [])
    reference = governance.save_report(report)
    stored = backend.get_json(storage.uri_to_path(reference))
    stored.pop("integrity_sha256")
    backend.put_json(storage.uri_to_path(reference), stored)
    assert governance.load_report(reference)["status"] == "UNKNOWN"


def test_free_send_does_not_bypass_existing_commercial_readiness(backend, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setattr(storage, "BACKEND", storage.TenantStorageBackend(backend))
    actor = access.AccessActor("verified-subject", "issuer", "a" * 64)
    with access.access_context(actor), pytest.raises(runtime.GovernanceBlocked):
        authorize(resource_tenant_id=actor.tenant_id)
    reports = [backend.get_json(path) for path in backend.list()]
    policy = next(item for item in reports if item["role_id"] == "governance_runtime")
    assert next(item for item in policy["findings"] if item["code"] == "commercial_readiness")["status"] == "FAIL"


def test_explicit_confirmation_classification_cannot_be_coerced_to_true():
    result = governance.preflight_action("assistant.gmail.send", requires_confirmation="true")
    assert result["allowed"] is False
    assert any(item["code"] == "approval_classification" and item["status"] == "UNKNOWN" for item in result["findings"])

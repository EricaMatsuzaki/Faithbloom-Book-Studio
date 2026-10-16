"""Governance checks must deny unsupported claims and preserve safe evidence."""
import copy
from datetime import datetime, timedelta, timezone
import json

import pytest

import governance
import saas_access
import storage_backend


def timestamp(delta=timedelta()):
    return (datetime.now(timezone.utc) + delta).isoformat()


def tenant_evidence(tenant="tenant-a", resource=None):
    return {
        "verified": True, "tenant_id": tenant, "resource_tenant_id": resource or tenant,
        "evidence_ref": "auth/session/123", "observed_at": timestamp(),
    }


def scoped_action(action="generate_book", **kwargs):
    return governance.preflight_action(
        action, tenant_id="tenant-a", resource_tenant_id="tenant-a",
        tenant_evidence=tenant_evidence(), **kwargs,
    )


def approval(action):
    return {
        "approved": True, "action": action, "actor_id": "reviewer-123",
        "actor_type": "human", "approved_at": timestamp(), "evidence_ref": "approval/event/123",
    }


def consent(action):
    return {
        "granted": True, "scope": action, "subject_id": "subject-123",
        "observed_at": timestamp(), "evidence_ref": "consent/event/123",
    }


@pytest.fixture
def backend(monkeypatch, tmp_path):
    result = storage_backend.LocalStorageBackend(tmp_path / "storage")
    monkeypatch.setattr(storage_backend, "BACKEND", result)
    return result


def test_unknown_control_does_not_become_success_and_empty_audit_is_unknown():
    report = governance.build_report("ai", "Governança IA", [
        governance.finding("source", "PASS", "Contrato no código", ["agents/example.py:10"]),
        governance.finding("live_provider", "UNKNOWN", "Provedor real", []),
    ])
    assert report["status"] == "UNKNOWN"
    assert report["counts"] == {"PASS": 1, "WARN": 0, "FAIL": 0, "UNKNOWN": 1, "total": 2}
    assert governance.build_report("ai", "IA", [])["status"] == "UNKNOWN"
    assert governance.finding("self_claim", "PASS", "Declarado", [])["status"] == "UNKNOWN"


def test_explicit_failure_is_preserved_even_with_unknown_and_pass_controls():
    report = governance.build_report("it", "TI", [
        governance.finding("backup", "UNKNOWN", "Backup", []),
        governance.finding("scope", "FAIL", "Escopo incorreto", ["audit/scope"]),
        governance.finding("syntax", "PASS", "Código", ["module.py:1"]),
    ])
    assert report["status"] == "FAIL"
    assert report["counts"]["FAIL"] == 1


@pytest.mark.parametrize("claim", [True, "PASS", {"verified": True, "status": "PASS"},
    {"verified": True, "status": "PASS", "evidence_ref": "audit/test"}])
def test_runtime_controls_require_evidence_and_observation_time(claim):
    assert governance.verify_control({"backup": claim}, "backup")[0] == "UNKNOWN"


def test_runtime_controls_support_scoped_context_and_reject_stale_observation():
    control = {"status": "PASS", "verified": True, "evidence_ref": "audit/backup/123", "observed_at": timestamp()}
    assert governance.verify_control({"controls": {"backup": control}}, "backup") == ("PASS", ["audit/backup/123"])
    control["status"] = "FAIL"
    assert governance.verify_control({"backup": control}, "backup")[0] == "FAIL"
    control["observed_at"] = timestamp(timedelta(days=-2))
    assert governance.verify_control({"backup": control}, "backup")[0] == "UNKNOWN"
    control["observed_at"] = "2026-10-14T10:00:00"
    assert governance.verify_control({"backup": control}, "backup")[0] == "UNKNOWN"


def test_source_evidence_is_confined_and_qualified_without_exposing_source(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "example.py"
    source.write_text("class Abstract:\n    def put_bytes(self):\n        pass\nclass Local:\n    def put_bytes(self):\n        return 'private-person@example.com'\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("def put_bytes():\n    pass\n", encoding="utf-8")
    (root / "link.py").symlink_to(outside)
    assert governance.inspect_source(root, "example.py", "Local.put_bytes") == ["example.py:5"]
    assert governance.inspect_source(root, "example.py", "missing") == []
    assert governance.inspect_source(root, "../outside.py", "put_bytes") == []
    assert governance.inspect_source(root, "link.py", "put_bytes") == []
    assert "private-person" not in json.dumps(governance.inspect_source(root, "example.py"))


def test_tenant_scope_fails_closed_even_with_an_approval():
    missing = governance.preflight_action("generate_book")
    assert missing["allowed"] is False
    assert missing["status"] == "UNKNOWN"
    assert scoped_action()["allowed"] is True
    mismatch = governance.preflight_action("generate_book", tenant_id="tenant-a", resource_tenant_id="tenant-b", tenant_evidence=tenant_evidence(resource="tenant-b"))
    assert mismatch["allowed"] is False
    assert mismatch["status"] == "FAIL"


@pytest.mark.parametrize("evidence_change", [
    {"verified": "true"}, {"evidence_ref": ""}, {"tenant_id": "tenant-b"},
    {"resource_tenant_id": "tenant-b"}, {"observed_at": ""}, {"observed_at": timestamp(timedelta(days=-2))},
])
def test_tenant_evidence_must_match_trusted_caller_scope(evidence_change):
    evidence = {**tenant_evidence(), **evidence_change}
    result = governance.preflight_action("generate_book", tenant_id="tenant-a", resource_tenant_id="tenant-a", tenant_evidence=evidence)
    assert result["allowed"] is False


@pytest.mark.parametrize("action", ["delete_book", "promote_master", "overwrite_master", "publish", "publicar_pacote", "merge", "deploy"])
def test_destructive_master_and_publication_actions_require_specific_human_approval(action):
    assert scoped_action(action)["allowed"] is False
    assert scoped_action(action, approval=approval(action))["allowed"] is True
    assert scoped_action(action, approval=approval("other-action"))["allowed"] is False
    assert scoped_action(action, approval={**approval(action), "actor_type": "agent"})["allowed"] is False
    assert scoped_action(action, approval={**approval(action), "approved_at": timestamp(timedelta(days=-2))})["allowed"] is False
    assert scoped_action(action, approval={**approval(action), "approved": False})["status"] == "FAIL"


@pytest.mark.parametrize("projected,remaining", [(None, 10), (1, None), (-1, 10), ("NaN", 10), (1, "Infinity"), (True, 10), (2, 1)])
def test_paid_calls_deny_missing_invalid_or_exceeded_budget(projected, remaining):
    assert scoped_action(paid=True, projected_cost=projected, budget_remaining=remaining)["allowed"] is False


def test_budget_passes_at_exact_boundary_and_rejects_currency_conflicts():
    assert scoped_action(paid=True, projected_cost="0.10", budget_remaining="0.10", approval=approval("generate_book"))["allowed"] is True
    assert scoped_action(paid=True, projected_cost=1, budget_remaining=5, currency="USD", budget_currency="JPY")["allowed"] is False
    # A positive projected cost cannot bypass the cost gate through paid=False.
    assert scoped_action(paid=False, projected_cost=5, budget_remaining=2)["allowed"] is False
    assert scoped_action(paid="false")["allowed"] is False


def test_paid_action_requires_human_approval_even_with_a_valid_budget():
    assert scoped_action(paid=True, projected_cost=1, budget_remaining=2)["allowed"] is False
    assert scoped_action(paid=True, projected_cost=1, budget_remaining=2, approval=approval("generate_book"))["allowed"] is True


def test_personal_data_needs_current_specific_non_revoked_consent():
    assert scoped_action(uses_personal_data=True)["allowed"] is False
    assert scoped_action(uses_personal_data=True, consent=consent("generate_book"))["allowed"] is True
    assert scoped_action(uses_personal_data=True, consent=consent("send_email"))["allowed"] is False
    assert scoped_action(uses_personal_data=True, consent={**consent("generate_book"), "revoked": True})["status"] == "FAIL"
    assert scoped_action(uses_personal_data=True, consent={**consent("generate_book"), "observed_at": timestamp(timedelta(days=-2))})["allowed"] is False
    assert scoped_action(uses_personal_data="false")["allowed"] is False


def test_preflight_has_no_storage_or_provider_side_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A policy check must not write, delete or invoke a provider")
    for method in ("put_bytes", "get_bytes", "delete", "list"):
        monkeypatch.setattr(storage_backend.BACKEND, method, forbidden)
    result = scoped_action(paid=True, projected_cost=1, budget_remaining=2, approval=approval("generate_book"))
    assert result["allowed"] is True


def test_report_persistence_redacts_nested_secrets_contacts_and_content(backend):
    # Assemble a deliberately synthetic token for the redaction test without
    # placing a credential-shaped literal in the repository's secret scan.
    secret = "sk-or-v1-" + "1234567890abcdefghijklmnop"
    original = governance.build_report("data", "Governança de dados", [
        governance.finding("config", "WARN", "Contato person@example.com", [f"config/key={secret}"]),
    ], metadata={
        "OPENROUTER_API_KEY": secret, "nested": {"password": "private-password", "prompt": "private story"},
        "contacts": ["person@example.com"], "evidence_ref": "log/test?access_token=private-token",
        "approval": {"actor_id": "human-secret"},
    })
    # Persistence must redact newly added metadata too, not only builder output.
    original["metadata"]["raw_prompt"] = "private injected story"
    before = copy.deepcopy(original)
    path = governance.save_report(original)
    stored_bytes = backend.get_bytes(path.removeprefix("fb://"))
    for sensitive in (secret, "private-password", "private story", "private injected story", "person@example.com", "private-token", "human-secret"):
        assert sensitive.encode() not in stored_bytes
    assert b"[REDACTED]" in stored_bytes
    assert original == before
    assert governance.load_report(path)["report_id"] == original["report_id"]


def test_report_history_preserves_identity_without_overwriting_prior_snapshot(backend):
    report = governance.build_report("ai", "IA", [governance.finding("approval", "UNKNOWN", "Aprovação", [])])
    first = governance.save_report(report, workspace_id="owner-a")
    first_bytes = backend.get_bytes(first.removeprefix("fb://"))
    report["findings"] = [governance.finding("approval", "PASS", "Aprovação", ["audit/event/123"])]
    second = governance.save_report(report, workspace_id="owner-a")
    assert first != second
    assert backend.get_bytes(first.removeprefix("fb://")) == first_bytes
    first_version = governance.load_report(first, workspace_id="owner-a")
    second_version = governance.load_report(second, workspace_id="owner-a")
    assert first_version["report_id"] == second_version["report_id"] == report["report_id"]
    assert first_version["status"] == "UNKNOWN"
    assert second_version["status"] == "PASS"
    assert len(governance.list_reports(workspace_id="owner-a")) == 2
    assert governance.list_reports(workspace_id="owner-b") == []


def test_cross_workspace_and_traversal_reads_are_rejected_before_storage(backend, monkeypatch):
    report = governance.build_report("data", "Dados", [])
    path = governance.save_report(report, workspace_id="owner-a")
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid scope must be rejected before reading storage")
    monkeypatch.setattr(backend, "get_bytes", forbidden)
    with pytest.raises(storage_backend.StorageError):
        governance.load_report(path, workspace_id="owner-b")
    prefix = governance._workspace_prefix("owner-a")
    with pytest.raises(storage_backend.StorageError):
        governance.load_report(f"fb://{prefix}/../credentials.json", workspace_id="owner-a")


def test_invalid_snapshot_identity_is_rejected_and_skipped_in_listing(backend):
    report = governance.build_report("it", "TI", [])
    path = governance.save_report(report)
    stored = backend.get_json(path.removeprefix("fb://"))
    stored["report_id"] = "other-report"
    backend.put_json(path.removeprefix("fb://"), stored)
    with pytest.raises(storage_backend.StorageError):
        governance.load_report(path)
    assert governance.list_reports() == []


def test_saved_and_loaded_status_is_recomputed_from_actual_findings(backend):
    report = governance.build_report("it", "TI", [governance.finding("backup", "UNKNOWN", "Backup", [])])
    report.update({"status": "PASS", "counts": {"PASS": 100}, "allowed": True})
    path = governance.save_report(report)
    stored = backend.get_json(path.removeprefix("fb://"))
    stored["status"] = "PASS"
    stored["allowed"] = True
    backend.put_json(path.removeprefix("fb://"), stored)
    loaded = governance.load_report(path)
    assert loaded["status"] == "UNKNOWN"
    assert loaded["counts"]["UNKNOWN"] == 1
    assert loaded["allowed"] is False


def test_redaction_never_stringifies_arbitrary_objects():
    class Unsafe:
        def __repr__(self):
            raise AssertionError("repr can contain secrets")
    assert governance.redact_sensitive({"value": Unsafe()}) == {"value": "[UNSUPPORTED VALUE]"}
    assert governance.redact_sensitive({Unsafe(): "value"}) == {"[UNSUPPORTED KEY]": "value"}


def test_in_memory_report_is_redacted_before_any_ui_display():
    report = governance.build_report("it", "TI", [
        governance.finding("config", "UNKNOWN", "Verificar user@example.com", ["audit?api_key=private-key"]),
    ], metadata={"prompt": "unpublished story", "error": 'Authorization: Basic c2VjcmV0OnBhc3N3b3Jk; password="private two words"'})
    serialized = json.dumps(report)
    for secret in ("user@example.com", "private-key", "unpublished story", "c2VjcmV0OnBhc3N3b3Jk", "private two words"):
        assert secret not in serialized


def test_one_unavailable_diagnostic_does_not_mask_other_agents_or_expose_errors(monkeypatch, tmp_path):
    real_import = governance.importlib.import_module
    def sometimes_unavailable(name):
        if name == "agents.governanca_ia":
            raise RuntimeError("api_key=private-runtime-key")
        return real_import(name)
    monkeypatch.setattr(governance.importlib, "import_module", sometimes_unavailable)
    reports = governance.run_all_diagnostics(root=tmp_path)
    assert len(reports) == 4
    assert reports[0]["status"] == "UNKNOWN"
    assert reports[0]["findings"][0]["code"] == "diagnostic_unavailable"
    assert all(report["findings"][0]["code"] != "diagnostic_unavailable" for report in reports[1:])
    assert "private-runtime-key" not in json.dumps(reports)


def test_tenant_qualified_report_uri_roundtrips_and_cannot_be_replayed_by_other_actor(backend, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setattr(storage_backend, "BACKEND", storage_backend.TenantStorageBackend(backend))
    actor_a = saas_access.AccessActor("subject-a", "issuer", "a" * 64)
    actor_b = saas_access.AccessActor("subject-b", "issuer", "b" * 64)
    report = governance.build_report("data", "Dados", [])
    with saas_access.access_context(actor_a):
        first = governance.save_report(report)
        assert first.startswith(f"fb://tenants/{actor_a.tenant_id}/governance/")
        assert governance.load_report(first)["report_id"] == report["report_id"]
        assert governance.list_reports()[0]["path"] == first
        second = governance.save_report(report)
        assert second != first
        assert len(governance.list_reports()) == 2
    with saas_access.access_context(actor_b):
        assert governance.list_reports() == []
        with pytest.raises(saas_access.AccessDenied):
            governance.load_report(first)
    with pytest.raises(saas_access.AccessDenied):
        governance.load_report(first)

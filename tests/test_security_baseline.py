from security_baseline import (
    DEFAULT_MAX_UPLOAD_BYTES,
    PRODUCTION_REQUIRED,
    authorize_action,
    production_security_profile,
    security_by_default_gate,
    validate_upload,
)


def _all_controls_true():
    return {name: True for name in PRODUCTION_REQUIRED}


def test_production_security_gate_is_fail_closed():
    gate = security_by_default_gate({}, production=True)
    assert gate["status"] == "BLOCKED"
    assert gate["ready"] is False
    assert gate["missing"]


def test_production_security_gate_passes_only_with_all_required_controls():
    gate = security_by_default_gate(_all_controls_true(), production=True)
    assert gate["status"] == "PASS"
    assert gate["ready"] is True
    assert gate["missing"] == []


def test_privileged_access_requires_mfa_and_recent_reauth():
    gate = security_by_default_gate(_all_controls_true(), production=True, privileged_access=True)
    assert gate["status"] == "BLOCKED"
    assert "mfa_for_privileged_users" in gate["missing"]
    assert "recent_reauth_for_critical_actions" in gate["missing"]


def test_development_reports_gaps_without_pretending_production_ready():
    gate = security_by_default_gate({}, production=False)
    assert gate["ready"] is False
    assert gate["ready_for_environment"] is True
    assert gate["status"] == "BLOCKED"


def test_authorization_requires_auth_permission_and_same_tenant():
    permissions = {"owner": {"view", "edit"}, "viewer": {"view"}}
    ok = authorize_action(
        authenticated=True, role="owner", action="edit", permissions=permissions,
        actor_tenant_id="workspace-a", resource_tenant_id="workspace-a",
    )
    assert ok["allowed"] is True

    denied = authorize_action(
        authenticated=True, role="owner", action="edit", permissions=permissions,
        actor_tenant_id="workspace-a", resource_tenant_id="workspace-b",
    )
    assert denied["allowed"] is False
    assert "cross_tenant_access_denied" in denied["reasons"]


def test_authorization_denies_unauthenticated_and_missing_permission():
    permissions = {"viewer": {"view"}}
    denied = authorize_action(
        authenticated=False, role="viewer", action="delete", permissions=permissions,
    )
    assert denied["allowed"] is False
    assert "authentication_required" in denied["reasons"]
    assert "permission_denied" in denied["reasons"]


def test_upload_policy_blocks_path_traversal_active_content_and_oversize():
    bad_path = validate_upload("../evil.pdf", size_bytes=100, content_type="application/pdf")
    assert bad_path["ok"] is False
    assert "unsafe_filename" in bad_path["blockers"]

    active = validate_upload("payload.txt", size_bytes=100, content_type="text/html")
    assert active["ok"] is False
    assert "active_content_not_allowed" in active["blockers"]

    too_big = validate_upload(
        "book.pdf", size_bytes=DEFAULT_MAX_UPLOAD_BYTES + 1, content_type="application/pdf"
    )
    assert too_big["ok"] is False
    assert "upload_too_large" in too_big["blockers"]


def test_upload_policy_defaults_to_private_storage_and_malware_scan():
    result = validate_upload("book.pdf", size_bytes=1024, content_type="application/pdf")
    assert result["ok"] is True
    assert result["storage_visibility"] == "private_by_default"
    assert result["requires_malware_scan_before_publication"] is True


def test_security_profile_starts_unapproved_and_requires_gate():
    profile = production_security_profile(provider="supabase")
    assert profile["provider"] == "supabase"
    assert all(value is False for value in profile["controls"].values())
    assert profile["policy"]["production_requires_security_gate_pass"] is True
    assert profile["policy"]["deny_cross_tenant_by_default"] is True

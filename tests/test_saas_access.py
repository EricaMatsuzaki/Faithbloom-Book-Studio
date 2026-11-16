"""Tenant boundaries with two server-verified identities and real isolated files."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import saas_access as access
import storage_backend as storage


@pytest.fixture
def tenants(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://identity.example")
    monkeypatch.delenv("FAITHBLOOM_ACCESS_ROLES", raising=False)
    a = access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": "account-a"})
    b = access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": "account-b"})
    raw = storage.LocalStorageBackend(str(tmp_path / "private-data"))
    wrapper = storage.TenantStorageBackend(raw)
    monkeypatch.setattr(storage, "BACKEND", wrapper)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    return a, b, raw, wrapper


def test_pilot_preserves_authors_namespace_and_is_not_customer_readiness(tmp_path, monkeypatch):
    monkeypatch.delenv("FAITHBLOOM_ACCESS_MODE", raising=False)
    backend = storage.TenantStorageBackend(storage.LocalStorageBackend(str(tmp_path)))
    backend.put_json("authors/index.json", [{"id": "original"}])
    assert backend.list("authors") == ["authors/index.json"]
    assert storage.storage_uri("authors/index.json") == "fb://authors/index.json"
    assert access.access_readiness()["customer_ready"] is False
    assert access.require_streamlit_access(SimpleNamespace()) is None


@pytest.mark.parametrize("claims", [
    {"authenticated": False, "sub": "a", "iss": "https://identity.example"},
    {"authenticated": True, "sub": "", "iss": "https://identity.example"},
    {"authenticated": True, "sub": "a"},
    {"authenticated": True, "sub": "a", "iss": "https://attacker.example"},
])
def test_missing_unverified_or_untrusted_oidc_claims_are_rejected(tenants, claims):
    with pytest.raises(access.AccessDenied):
        access.actor_from_trusted_claims(claims)


def test_profile_email_tenant_and_role_claims_cannot_escalate(tenants):
    a, _, _, _ = tenants
    spoof = access.actor_from_trusted_claims({
        "authenticated": True, "sub": a.subject, "iss": a.issuer,
        "email": "admin@example.invalid", "role": "admin", "tenant_id": "victim",
        "profile": {"role": "owner"},
    })
    assert spoof.tenant_id == a.tenant_id
    assert spoof.role == "member"
    assert len(spoof.tenant_id) == 64
    assert a.subject not in spoof.tenant_id


def test_issuer_is_part_of_identity_and_delimiters_do_not_alias(monkeypatch):
    issuers = "https://identity.example,https://identity.example:a"
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", issuers)
    a = access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": "a:b"})
    b = access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example:a", "sub": "b"})
    assert a.tenant_id != b.tenant_id


def test_server_side_role_config_is_honored_and_invalid_role_fails(tenants, monkeypatch):
    a, _, _, _ = tenants
    monkeypatch.setenv("FAITHBLOOM_ACCESS_ROLES", json.dumps({a.tenant_id: "viewer"}))
    viewer = access.actor_from_trusted_claims({"authenticated": True, "iss": a.issuer, "sub": a.subject})
    assert viewer.role == "viewer"
    monkeypatch.setenv("FAITHBLOOM_ACCESS_ROLES", json.dumps({a.tenant_id: "owner"}))
    with pytest.raises(access.AccessDenied):
        access.actor_from_trusted_claims({"authenticated": True, "iss": a.issuer, "sub": a.subject})


def test_context_resets_and_no_actor_can_read_or_write(tenants):
    a, b, _, backend = tenants
    with access.access_context(a):
        assert access.current_actor() is a
        with access.access_context(b):
            assert access.current_actor() is b
        assert access.current_actor() is a
    assert access.current_actor() is None
    for operation in (lambda: backend.get_json("index.json", []), lambda: backend.put_json("index.json", []), lambda: backend.list(""), lambda: backend.delete("index.json")):
        with pytest.raises(access.AccessDenied):
            operation()


def test_actual_authorization_check_runs_at_the_storage_boundary(tenants, monkeypatch):
    a, _, _, backend = tenants
    decisions = []
    original = access.authorize_action
    def record(**kwargs):
        decisions.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(access, "authorize_action", record)
    with access.access_context(a):
        backend.put_json("index.json", ["a"])
        backend.get_json("index.json", [])
    assert {call["action"] for call in decisions} >= {"storage.write", "storage.read"}
    assert all(call["actor_tenant_id"] == a.tenant_id for call in decisions)


def test_same_paths_are_isolated_and_root_pilot_data_is_preserved(tenants):
    a, b, raw, backend = tenants
    raw.put_json("authors/index.json", [{"id": "author-original"}])
    with access.access_context(a):
        backend.put_json("authors/index.json", [{"id": "a"}])
        uri_a = storage.storage_uri("authors/index.json")
    with access.access_context(b):
        assert backend.get_json("authors/index.json", []) == []
        backend.put_json("authors/index.json", [{"id": "b"}])
        assert backend.list("authors") == ["authors/index.json"]
        assert backend.get_json("authors/index.json", []) == [{"id": "b"}]
        with pytest.raises(access.AccessDenied):
            backend.get_bytes(uri_a.removeprefix("fb://"))
        with pytest.raises(access.AccessDenied):
            backend.put_json(uri_a.removeprefix("fb://"), [])
        with pytest.raises(access.AccessDenied):
            backend.delete(uri_a.removeprefix("fb://"))
    with access.access_context(a):
        assert backend.get_json("authors/index.json", []) == [{"id": "a"}]
    assert raw.get_json("authors/index.json", []) == [{"id": "author-original"}]


def test_viewer_cannot_mutate_own_tenant(tenants):
    a, _, _, backend = tenants
    with access.access_context(a):
        backend.put_bytes("asset.png", b"image")
    with access.access_context(replace(a, role="viewer")):
        assert backend.get_bytes("asset.png") == b"image"
        for operation in (lambda: backend.put_bytes("asset.png", b"changed"), lambda: backend.delete("asset.png")):
            with pytest.raises(access.AccessDenied):
                operation()


def test_backend_listing_cannot_leak_other_tenant(tenants, monkeypatch):
    a, b, raw, backend = tenants
    monkeypatch.setattr(raw, "list", lambda prefix: [f"tenants/{a.tenant_id}/mine.json", f"tenants/{b.tenant_id}/private.json"])
    with access.access_context(a), pytest.raises(access.AccessDenied):
        backend.list("")


def test_cross_tenant_uri_is_denied_before_cache_hit(tenants, monkeypatch):
    a, b, raw, backend = tenants
    with access.access_context(a):
        backend.put_bytes("assets/master.png", b"original-master")
        uri = storage.storage_uri("assets/master.png")
        cached = storage.materializar(uri)
        assert Path(cached).read_bytes() == b"original-master"
        assert a.tenant_id in cached
    calls = []
    monkeypatch.setattr(raw, "get_bytes", lambda path: calls.append(path) or b"should-not-read")
    with access.access_context(b):
        with pytest.raises(access.AccessDenied):
            storage.materializar(uri)
        with pytest.raises(access.AccessDenied):
            storage.materializar(cached)
        with pytest.raises(access.AccessDenied):
            storage.materializar_assets_em_objeto({"source_ref": uri.replace(".png", ".json")})
        with pytest.raises(access.AccessDenied):
            storage.persistir_assets_em_objeto({"image": uri}, "assets")
    assert calls == []


def test_unqualified_legacy_uri_is_not_adopted_by_customer(tenants):
    a, _, _, _ = tenants
    with access.access_context(a), pytest.raises(access.AccessDenied):
        storage.materializar("fb://assets/pilot-master.png")


def test_local_asset_paths_restricted_to_own_cache_or_output(tenants, tmp_path):
    a, b, _, backend = tenants
    outside = tmp_path / "global-export.pdf"
    outside.write_bytes(b"private")
    with access.access_context(a):
        own = storage.tenant_local_directory("outputs") / "book.pdf"
        own.write_bytes(b"my-pdf")
        uri = storage.persistir_arquivo(str(own))
        assert uri.startswith(f"fb://tenants/{a.tenant_id}/")
        assert backend.get_bytes(storage.uri_to_path(uri)) == b"my-pdf"
        with pytest.raises(access.AccessDenied):
            storage.persistir_arquivo(str(outside))
        with pytest.raises(access.AccessDenied):
            storage.materializar_assets_em_objeto({"pdf": str(outside)})
    with access.access_context(b), pytest.raises(access.AccessDenied):
        storage.persistir_arquivo(str(own))


def test_symlink_does_not_authorize_external_local_asset(tenants, tmp_path):
    a, _, _, _ = tenants
    private = tmp_path / "elsewhere.png"
    private.write_bytes(b"sensitive")
    with access.access_context(a):
        link = storage.tenant_local_directory("outputs") / "linked.png"
        link.symlink_to(private)
        with pytest.raises(access.AccessDenied):
            storage.persistir_arquivo(str(link))


def test_materialization_rejects_symlink_in_existing_cache(tenants, tmp_path):
    a, _, _, backend = tenants
    private = tmp_path / "private.png"
    private.write_bytes(b"sensitive")
    with access.access_context(a):
        backend.put_bytes("assets/book.png", b"safe-image")
        uri = storage.storage_uri("assets/book.png")
        digest = hashlib.sha256(storage.uri_to_path(uri).encode()).hexdigest()[:24]
        cached = storage.tenant_local_directory("cache") / f"{digest}.png"
        cached.symlink_to(private)
        with pytest.raises(access.AccessDenied):
            storage.materializar(uri)


def test_tenant_root_symlink_cannot_change_ownership(tenants, tmp_path):
    a, b, _, _ = tenants
    with access.access_context(b):
        b_root = storage.tenant_local_directory("outputs").parent
    (storage.CACHE_DIR / "tenants" / a.tenant_id).symlink_to(b_root, target_is_directory=True)
    with access.access_context(a), pytest.raises(access.AccessDenied):
        storage.tenant_local_directory("outputs")


def test_epub_is_persisted_and_reopened_byte_for_byte(tenants):
    a, _, _, backend = tenants
    payload = b"PK\x03\x04test-epub-container"
    with access.access_context(a):
        original = storage.tenant_local_directory("outputs") / "book.epub"
        original.write_bytes(payload)
        uri = storage.persistir_arquivo(str(original), "exports/books")
        assert uri.endswith(".epub")
        assert backend.get_bytes(storage.uri_to_path(uri)) == payload
        assert Path(storage.materializar(uri)).read_bytes() == payload


def test_trusted_worker_context_rejects_path_like_tenant_ids(tenants):
    a, _, _, _ = tenants
    with pytest.raises(access.AccessDenied):
        with access.access_context(replace(a, tenant_id="../../another-account")):
            pytest.fail("invalid context accepted")


def test_two_concurrent_request_contexts_are_isolated(tenants):
    a, b, raw, backend = tenants
    def request(actor):
        with access.access_context(actor):
            backend.put_json("work/book.json", {"actor": actor.subject})
            return backend.get_json("work/book.json", {})["actor"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(request, (a, b))) == [a.subject, b.subject]
    assert access.current_actor() is None
    assert len(raw.list("tenants")) == 2


class StreamlitStub:
    def __init__(self, user=None, **session):
        self.user = user
        self.session_state = session
        self.errors = []
    def error(self, value):
        self.errors.append(value)
    def stop(self):
        raise RuntimeError("stopped")


def test_session_profile_cannot_authenticate_and_prior_actor_is_cleared(tenants):
    a, _, _, _ = tenants
    st = StreamlitStub(None, role="admin", sub=a.subject, tenant_id=a.tenant_id, authenticated=True)
    with access.access_context(a):
        with pytest.raises(RuntimeError, match="stopped"):
            access.require_streamlit_access(st)
        assert access.current_actor() is None
    assert "Entre" in st.errors[0]


def test_customer_ui_stays_blocked_after_verified_login(tenants):
    a, _, _, _ = tenants
    st = StreamlitStub(SimpleNamespace(is_logged_in=True, sub=a.subject, iss=a.issuer))
    with pytest.raises(RuntimeError, match="stopped"):
        access.require_streamlit_access(st)
    assert access.current_actor() is None
    assert "isolamento" in st.errors[0]
    readiness = access.access_readiness()
    assert readiness["status"] == "BLOCKED"
    assert "legacy_filesystem_exports_not_tenant_isolated" in readiness["blockers"]
    assert "cloud_index_updates_without_compare_and_swap" in readiness["blockers"]


def test_invalid_access_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "tenant-typo")
    assert access.access_readiness()["ready"] is False
    with pytest.raises(access.AccessDenied):
        access.require_action("view")

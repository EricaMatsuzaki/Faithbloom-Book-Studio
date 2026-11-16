"""Exercise real paid boundaries and honest pilot/commercial evidence offline."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import armazenamento
import controle_geracao as costs
import editorial_products as products
import governance
import governance_runtime as runtime
import saas_access as access
import storage_backend as storage


@pytest.fixture
def backend(tmp_path, monkeypatch):
    result = storage.LocalStorageBackend(tmp_path / "durable")
    monkeypatch.setattr(storage, "BACKEND", result)
    monkeypatch.setattr(armazenamento, "BACKEND", result)
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    monkeypatch.setattr(costs, "LOG_PATH", tmp_path / "generation.jsonl")
    monkeypatch.setattr(costs, "POLITICA", replace(costs.POLITICA, orcamento_diario_usd=1.0))
    return result


def _authorize(**kwargs):
    return runtime.authorize_generation("editorial_product.generate", confirmed=True,
        projected_cost=.03, provider_configured=True, operation_id="opaque-operation-1",
        source_module="editorial_products.py", **kwargs)


def _product(origin="own_idea"):
    return products.create_product("children_advice", "Projeto privado", "Aprender a esperar a vez",
                                   unit_count=1, origin=origin)


def _valid_unit():
    return {"title": "Uma pequena espera", "objectives": ["Esperar com acolhimento"],
            "situation": "Duas pessoas desejam falar.", "advice": "Ouça e espere a sua vez.",
            "reflection": "Como é ser ouvido?", "activity": "Pratique em uma conversa."}


def _reports(backend):
    return [backend.get_json(path) for path in backend.list() if "governance/" in path]


def test_private_pilot_executes_with_four_scoped_reports_without_fake_verified_tenant(backend):
    state = {"titulo": "PERSONAL-MANUSCRIPT", "texto": "PRIVATE-CONTENT",
             "api_key": "sk-private-super-secret-value"}
    receipt = _authorize(state=state)
    reports = _reports(backend)
    assert len(reports) == 5
    assert {x["role_id"] for x in reports} == {
        "governance_runtime", "ai_governance", "data_governance", "it_governance", "cybersecurity"}
    report = next(x for x in reports if x["role_id"] == "governance_runtime")
    findings = {item["code"]: item for item in report["findings"]}
    assert findings["tenant_scope"]["status"] == "UNKNOWN"
    assert findings["commercial_readiness"]["status"] == "UNKNOWN"
    assert report["allowed"] is False  # Strict policy remains honest.
    assert report["metadata"]["execution_decision"]["allowed"] is True
    assert report["metadata"]["execution_decision"]["customer_ready"] is False
    assert report["metadata"]["provider_live_verified"] is False
    canonical = json.dumps(state, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert any(item["sha256"] == sha256(canonical.encode()).hexdigest()
               for item in report["metadata"]["artifacts"])
    assert len(receipt["specialist_refs"]) == 4
    persisted = json.dumps(reports)
    assert all(value not in persisted for value in ("PERSONAL-MANUSCRIPT", "PRIVATE-CONTENT", state["api_key"]))
    assert len(report["metadata"]["operation_version_sha256"]) == 64


def test_product_without_action_confirmation_cannot_call_provider(backend):
    provider = Mock(return_value=_valid_unit())
    with pytest.raises(runtime.GovernanceBlocked):
        products.generate_product(_product(), provider)
    provider.assert_not_called()
    assert any(item["code"] == "human_approval" and item["status"] == "FAIL"
               for report in _reports(backend) for item in report["findings"])


def test_product_daily_budget_exhaustion_prevents_every_provider_call(backend, monkeypatch):
    monkeypatch.setattr(costs, "POLITICA", replace(costs.POLITICA, orcamento_diario_usd=0.0))
    provider = Mock(return_value=_valid_unit())
    with pytest.raises(costs.GeracaoBloqueada):
        products.generate_product(_product(), provider, confirmed=True)
    provider.assert_not_called()


def test_project_budget_balance_is_observed_without_adding_a_charge(backend):
    with pytest.raises(runtime.GovernanceBlocked):
        _authorize(budget_remaining=.01)
    assert not costs.LOG_PATH.exists()
    report = next(x for x in _reports(backend) if x["role_id"] == "governance_runtime")
    assert next(x for x in report["findings"] if x["code"] == "budget")["status"] == "FAIL"


@pytest.mark.parametrize("cost", [None, True, -1, float("inf"), float("nan")])
def test_invalid_cost_never_becomes_an_authorized_paid_action(backend, cost):
    with pytest.raises(runtime.GovernanceBlocked):
        runtime.authorize_generation("editorial_product.generate", confirmed=True,
            projected_cost=cost, provider_configured=True, operation_id="invalid-cost",
            source_module="editorial_products.py")


def test_provider_configuration_missing_blocks_before_default_router(backend, monkeypatch):
    import ai_provider_router
    provider = Mock(return_value=_valid_unit())
    monkeypatch.setattr(ai_provider_router, "chamar_llm", provider)
    monkeypatch.setattr(ai_provider_router, "provider_status", lambda **_: {"gemini": False, "groq": False, "openrouter": False})
    with pytest.raises(runtime.GovernanceBlocked):
        products.generate_product(_product(), confirmed=True)
    provider.assert_not_called()


def test_real_experience_requires_separate_data_consent_and_retains_four_reports(backend):
    product = _product(origin="real_experience")
    provider = Mock(return_value=_valid_unit())
    with pytest.raises(runtime.GovernanceBlocked):
        products.generate_product(product, provider, confirmed=True)
    provider.assert_not_called()
    products.generate_product(product, provider, confirmed=True, consent_confirmed=True)
    assert provider.call_count == 1
    reloaded = products.load_product(product["storage_path"])
    # A completed project is a read/save operation, not another purchase.
    products.generate_product(reloaded, provider)
    assert provider.call_count == 1
    assert len(_reports(backend)) == 10


def test_generation_receipts_follow_the_version_when_an_old_proposal_is_restored(backend):
    product = _product()
    products.generate_product(product, lambda **_: _valid_unit(), confirmed=True)
    original_id = product["editorial_product"]["active_version"]
    original_receipts = product["editorial_product"]["active_governance"]
    products.generate_product(product, lambda **_: _valid_unit(), confirmed=True, new_version=True)
    next_receipts = product["editorial_product"]["active_governance"]
    assert original_receipts != next_receipts
    products.restore_version(product, original_id)
    reloaded = products.load_product(product["storage_path"])
    assert reloaded["editorial_product"]["active_governance"] == original_receipts
    assert reloaded["editorial_product"]["versions"][-1]["governance_receipts"] == next_receipts


@pytest.mark.parametrize("failure_index", [1, 3, 5])
def test_failed_policy_or_specialist_write_prevents_provider_even_with_approval(backend, monkeypatch, failure_index):
    save = governance.save_report
    attempts = 0
    def fail_one(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == failure_index:
            raise OSError("private SDK error with token=SECRET-MUST-NOT-LEAK")
        return save(*args, **kwargs)
    monkeypatch.setattr(governance, "save_report", fail_one)
    provider = Mock(return_value=_valid_unit())
    with pytest.raises(runtime.GovernanceBlocked, match="evidências") as error:
        products.generate_product(_product(), provider, confirmed=True)
    assert "SECRET-MUST-NOT-LEAK" not in str(error.value)
    provider.assert_not_called()


def test_multi_tenant_checks_real_access_role_and_foreign_resource_before_provider(backend, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    actor = access.AccessActor("server-verified-subject", "issuer", "a" * 64)
    with access.access_context(actor), pytest.raises(access.AccessDenied):
        _authorize(resource_tenant_id="b" * 64)
    viewer = replace(actor, role="viewer")
    with access.access_context(viewer), pytest.raises(access.AccessDenied):
        _authorize(resource_tenant_id=actor.tenant_id)
    with pytest.raises(access.AccessDenied):
        _authorize()
    assert _reports(backend) == []


def test_commercial_critical_readiness_is_not_bypassed_by_an_authenticated_actor(backend, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    tenant_backend = storage.TenantStorageBackend(backend)
    monkeypatch.setattr(storage, "BACKEND", tenant_backend)
    actor = access.AccessActor("server-verified-subject", "issuer", "a" * 64)
    with access.access_context(actor), pytest.raises(runtime.GovernanceBlocked):
        _authorize(resource_tenant_id=actor.tenant_id)
    reports = _reports(backend)
    report = next(x for x in reports if x["role_id"] == "governance_runtime")
    findings = {item["code"]: item for item in report["findings"]}
    assert findings["tenant_scope"]["status"] == "PASS"
    assert findings["commercial_readiness"]["status"] == "FAIL"
    assert report["allowed"] is False
    assert report["metadata"]["execution_decision"]["allowed"] is False


@pytest.mark.parametrize("prefix", ["fb://tenants/", "tenants/"])
def test_foreign_qualified_source_is_not_hidden_by_matching_resource_argument(backend, monkeypatch, prefix):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    actor = access.AccessActor("server-verified-subject", "issuer", "a" * 64)
    with access.access_context(actor), pytest.raises(runtime.GovernanceBlocked):
        _authorize(resource_tenant_id=actor.tenant_id,
                   state={"source_ref": prefix + "b" * 64 + "/livros/private.json"})


def test_pilot_cannot_replay_a_customer_qualified_resource(backend):
    with pytest.raises(runtime.GovernanceBlocked):
        _authorize(state={"source_ref": "fb://tenants/" + "b" * 64 + "/livros/private.json"})


def test_runtime_evidence_is_available_in_the_existing_governance_history_ui(backend, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr("estilo.render_sidebar_navigation", lambda: None)
    _authorize()
    page_path = Path(runtime.__file__).parent / "pages/54_🛡️_Governanca.py"
    page = AppTest.from_file(str(page_path), default_timeout=20).run()
    next(button for button in page.button if button.label == "Consultar histórico").click().run()
    assert not page.exception
    assert len(page.session_state["governance_history"]) == 5
    assert len(_reports(backend)) == 5  # Merely viewing does not rerun diagnostics.

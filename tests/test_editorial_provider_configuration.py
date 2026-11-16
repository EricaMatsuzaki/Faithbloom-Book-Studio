"""Explicit editorial routing survives the shared single-attempt runtime."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from streamlit.testing.v1 import AppTest

import ai_provider_router as router
import armazenamento
import controle_geracao
import editorial_dispatch as dispatch
import editorial_products as studio
import governance_runtime
import openrouter_client
import painel_visual
import storage_backend as storage

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("gemini", "groq", "openrouter")


@pytest.fixture
def configured(tmp_path, monkeypatch):
    for name in ("FAITHBLOOM_PROVEDOR_TEXTO", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                 "GEMINI_MODELO_TEXTO", "GEMINI_TEXT_MODEL", "GROQ_API_KEY",
                 "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(router, "GEMINI_API_KEY", "fake-primary-gemini-key")
    monkeypatch.setattr(router, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-openrouter-key")
    monkeypatch.setattr(openrouter_client, "OPENROUTER_API_KEY", "fake-openrouter-key")
    monkeypatch.setattr(router, "_OPENROUTER_DISABLED_REASON", "")
    monkeypatch.setattr(router, "_GEMINI_LAST_SELECTED_MODEL", "")
    monkeypatch.setattr(router.requests, "get", lambda *_a, **_k: pytest.fail("Strict selection must not discover a substitute model"))
    monkeypatch.setattr(router, "time", SimpleNamespace(time=router.time.time,
        sleep=lambda *_: pytest.fail("A paid attempt cannot back off and resend")))
    backend = storage.LocalStorageBackend(str(tmp_path / "durable"))
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setattr(storage, "CACHE_DIR", tmp_path / "cache")
    for name in ("_RECENT", "_EXECUTIONS"):
        monkeypatch.setattr(controle_geracao, name, {})
    monkeypatch.setattr(controle_geracao, "_IN_FLIGHT", set())
    monkeypatch.chdir(tmp_path)
    state = {"posts": [], "failure": None}

    def post(url, **kwargs):
        state["posts"].append((url, kwargs))
        if state["failure"] == "timeout":
            raise requests.Timeout("Result of the one selected attempt is unknown")
        response = requests.Response()
        response.url = url
        response.status_code = int(state["failure"]) if state["failure"] in {"503", "404"} else 200
        unit = {"title": "Observar e cuidar", "objectives": ["Cuidar de uma flor"], "source_refs": [],
                "blocks": [{"label": "Abertura", "text": "Observe uma flor e explique como você cuidaria dela."}]}
        text = "not JSON" if state["failure"] == "invalid_json" else json.dumps(unit)
        payload = ({"candidates": [{"content": {"parts": [{"text": text}]}}]}
                   if "generativelanguage.googleapis.com" in url else
                   {"choices": [{"message": {"content": text}}]})
        response._content = json.dumps(payload).encode()
        return response

    monkeypatch.setattr(router.requests, "post", post)
    return state


def assert_selected_request(state, provider):
    assert len(state["posts"]) == 1
    url = state["posts"][0][0]
    assert {"gemini": "generativelanguage.googleapis.com", "groq": "api.groq.com",
            "openrouter": "openrouter.ai"}[provider] in url


@pytest.mark.parametrize("provider", PROVIDERS)
def test_forced_provider_wins_over_other_configured_keys(configured, monkeypatch, provider):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", " " + provider.upper() + " ")
    status = router.provider_status(strict=True)
    assert [name for name in PROVIDERS if status[name]] == [provider]
    assert governance_runtime.text_provider_configuration(strict=True)["providers"] == [provider]
    assert isinstance(router.chamar_llm("system", "instruction", no_retries=True, no_paid_fallback=True), dict)
    assert_selected_request(configured, provider)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_forced_missing_provider_never_transmits_to_configured_alternative(configured, monkeypatch, provider):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", provider)
    if provider == "gemini":
        monkeypatch.setattr(router, "GEMINI_API_KEY", "")
    elif provider == "groq":
        monkeypatch.setattr(router, "GROQ_API_KEY", "")
    else:
        monkeypatch.delenv("OPENROUTER_API_KEY")
    assert not any(router.provider_status(strict=True)[name] for name in PROVIDERS)
    assert governance_runtime.text_provider_configuration(strict=True)["configured"] is False
    with pytest.raises(router.AIProviderPermanentError, match="selecionado"):
        router.chamar_llm("system", "instruction", no_retries=True, no_paid_fallback=True)
    assert configured["posts"] == []


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("failure", ["503", "404", "timeout", "invalid_json"])
def test_forced_provider_failure_never_retries_or_transmits_to_alternatives(configured, monkeypatch, provider, failure):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", provider)
    configured["failure"] = failure
    with pytest.raises((router.AIProviderError, requests.RequestException,
                        openrouter_client.OpenRouterFaithBloomError, ValueError)):
        router.chamar_llm("system", "instruction", no_retries=True, no_paid_fallback=True)
    assert_selected_request(configured, provider)


@pytest.mark.parametrize("legacy,modern,expected", [
    (None, None, "gemini-flash-latest"),
    ("gemini-existing-legacy", None, "gemini-existing-legacy"),
    (None, "gemini-explicit-modern", "gemini-explicit-modern"),
    ("gemini-existing-legacy", "gemini-explicit-modern", "gemini-existing-legacy"),
    ("  ", "models/gemini-explicit-modern", "gemini-explicit-modern"),
])
def test_strict_model_preserves_legacy_preference_default_and_modern_alias(configured, monkeypatch, legacy, modern, expected):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", "gemini")
    if legacy is not None:
        monkeypatch.setenv("GEMINI_MODELO_TEXTO", legacy)
    if modern is not None:
        monkeypatch.setenv("GEMINI_TEXT_MODEL", modern)
    router.chamar_llm("system", "instruction", no_retries=True, no_paid_fallback=True)
    assert_selected_request(configured, "gemini")
    assert f"/models/{expected}:generateContent?" in configured["posts"][0][0]


@pytest.mark.parametrize("preference", ["auto", "gemini"])
def test_google_key_alias_is_eligible_and_used_without_mutating_global_key(configured, monkeypatch, preference):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", preference)
    monkeypatch.setattr(router, "GEMINI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-google-alias-key")
    assert router.provider_status(strict=True)["gemini"] is True
    assert governance_runtime.text_provider_configuration(strict=True)["configured"] is True
    router.chamar_llm("system", "instruction", no_retries=True, no_paid_fallback=True)
    assert_selected_request(configured, "gemini")
    assert configured["posts"][0][0].endswith("key=fake-google-alias-key")
    assert router.GEMINI_API_KEY == ""


def test_primary_key_has_precedence_over_google_alias(configured, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-unused-alias-key")
    router.chamar_llm("system", "instruction", no_retries=True, no_paid_fallback=True)
    assert configured["posts"][0][0].endswith("key=fake-primary-gemini-key")


@pytest.mark.parametrize("preference", ["", "auto"])
def test_auto_chooses_one_available_provider_before_any_transmission(configured, monkeypatch, preference):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", preference)
    monkeypatch.setattr(router, "GEMINI_API_KEY", "")
    router.chamar_llm("system", "instruction", no_retries=True, no_paid_fallback=True)
    assert_selected_request(configured, "groq")


def test_invalid_preference_and_disabled_forced_openrouter_fail_closed(configured, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", "unsupported-provider")
    assert not governance_runtime.text_provider_configuration(strict=True)["configured"]
    with pytest.raises(router.AIProviderPermanentError, match="suportado"):
        router.chamar_llm("system", "instruction", no_retries=True, no_paid_fallback=True)
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", "openrouter")
    monkeypatch.setattr(router, "_OPENROUTER_DISABLED_REASON", "Provider credit unavailable")
    assert not governance_runtime.text_provider_configuration(strict=True)["configured"]
    with pytest.raises(router.AIProviderPermanentError):
        router.chamar_llm("system", "instruction", no_retries=True, no_paid_fallback=True)
    assert configured["posts"] == []


def test_non_strict_router_keeps_existing_discovery_and_defaults(configured, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", "openrouter")
    monkeypatch.setenv("GEMINI_MODELO_TEXTO", "strict-only-model")
    called = []
    monkeypatch.setattr(router, "_gemini", lambda *args: called.append(args) or {"original": True})
    before = router.GEMINI_TEXT_MODEL
    assert router.chamar_llm("system", "instruction") == {"original": True}
    assert called == [("system", "instruction")]
    assert router.GEMINI_TEXT_MODEL == before
    assert router.provider_status()["gemini"] is True


@pytest.mark.parametrize("target", ["native", "central"])
def test_google_alias_crosses_real_editorial_configuration_and_execution_gates(configured, monkeypatch, target):
    monkeypatch.setattr(router, "GEMINI_API_KEY", "")
    monkeypatch.setattr(router, "GROQ_API_KEY", "")
    monkeypatch.delenv("OPENROUTER_API_KEY")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-editorial-google-alias")
    monkeypatch.setenv("GEMINI_MODELO_TEXTO", "gemini-approved-legacy-model")
    if target == "native":
        value = studio.create_product("other", "Livro com alias", "Cuidar de uma flor",
                                      unit_count=1, custom_blocks=["Abertura"])
        studio.save_product(value)
        monkeypatch.setattr(painel_visual, "_sidebar_page_link", lambda *_a, **_k: None)
        app = AppTest.from_file(str(ROOT / "pages/55_📚_Produtos_Editoriais.py"))
        app.session_state["editorial_product_id"] = value["storage_path"]
        app.run(timeout=15)
        assert not app.exception
        checkbox = next(item for item in app.checkbox if item.label == "Autorizo a geração das unidades pendentes e o custo do provedor")
        checkbox.check().run()
        button = next(item for item in app.button if item.label == "Gerar / retomar unidades")
        assert not button.disabled
        button.click().run(timeout=15)
        assert not app.exception
        saved = studio.load_product(value["storage_path"])
    else:
        run = dispatch.initialize_specialist(dispatch.create_editorial_run("other", "Livro com alias", "Cuidar de uma flor",
            custom_blocks=["Abertura"], unit_count=1)["id"])
        dispatch.execute_editorial_generation(run["id"], confirmed=True)
        saved = studio.load_product(run["source_ref"])
    assert len(saved["editorial_product"]["units"]) == 1
    assert_selected_request(configured, "gemini")
    assert "/models/gemini-approved-legacy-model:generateContent?" in configured["posts"][0][0]


def test_native_forced_missing_provider_does_not_enable_generation(configured, monkeypatch):
    monkeypatch.setattr(router, "GEMINI_API_KEY", "")
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", "gemini")
    value = studio.create_product("other", "Seleção explícita", "Objetivo",
                                  unit_count=1, custom_blocks=["Abertura"])
    studio.save_product(value)
    monkeypatch.setattr(painel_visual, "_sidebar_page_link", lambda *_a, **_k: None)
    app = AppTest.from_file(str(ROOT / "pages/55_📚_Produtos_Editoriais.py"))
    app.session_state["editorial_product_id"] = value["storage_path"]
    app.run(timeout=15)
    assert not app.exception
    next(item for item in app.checkbox if item.label == "Autorizo a geração das unidades pendentes e o custo do provedor").check().run()
    assert next(item for item in app.button if item.label == "Gerar / retomar unidades").disabled
    assert configured["posts"] == []


@pytest.mark.parametrize("provider", ["gemini", "openrouter"])
def test_central_missing_forced_provider_does_not_claim_paid_attempt_or_attest_configuration(configured, monkeypatch, provider):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", provider)
    if provider == "gemini":
        monkeypatch.setattr(router, "GEMINI_API_KEY", "")
    else:
        monkeypatch.delenv("OPENROUTER_API_KEY")
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("other", "Provedor explícito ausente", "Objetivo",
        custom_blocks=["Abertura"], unit_count=1)["id"])
    with pytest.raises(governance_runtime.GovernanceBlocked):
        dispatch.execute_editorial_generation(run["id"], confirmed=True)
    saved = studio.load_product(run["source_ref"])
    assert saved["editorial_product"]["execution"]["attempts"] == []
    assert saved["editorial_product"]["execution"].get("claim") is None
    assert not saved["editorial_product"]["draft"].get("governance_receipts")
    assert configured["posts"] == []


def test_central_forced_openrouter_does_not_send_to_available_gemini(configured, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_PROVEDOR_TEXTO", "openrouter")
    run = dispatch.initialize_specialist(dispatch.create_editorial_run("other", "Provedor escolhido", "Objetivo",
        custom_blocks=["Abertura"], unit_count=1)["id"])
    completed = dispatch.execute_editorial_generation(run["id"], confirmed=True)
    assert completed["generation"]["status"] == "completed"
    assert_selected_request(configured, "openrouter")

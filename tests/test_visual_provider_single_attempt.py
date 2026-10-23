from dataclasses import replace
from unittest.mock import Mock

import pytest
import requests

import controle_geracao as control
import gemini_client as gemini
import openrouter_client as client


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setattr(control, "LOG_PATH", tmp_path / "generation.jsonl")
    monkeypatch.setattr(control, "POLITICA", replace(control.POLITICA, cooldown_duplicado_seg=0))
    control._IN_FLIGHT.clear()
    control._EXECUTIONS.clear()
    control._RECENT.clear()
    monkeypatch.setattr(gemini, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(client, "OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setattr(client, "PROVEDOR_TEXTO", "auto")
    return monkeypatch


@pytest.mark.parametrize("modality", ["image", "text"])
def test_gemini_timeout_has_one_http_call_no_model_retry_no_paid_fallback(configured, modality):
    post = Mock(side_effect=requests.Timeout("ambiguous timeout"))
    configured.setattr(gemini.requests, "post", post)
    router = Mock(side_effect=AssertionError("paid fallback must not execute"))
    configured.setattr(client, "_chamar_llm_openrouter", router)
    configured.setattr(client, "_post_com_retry", router)
    with pytest.raises(gemini.GeminiFaithBloomError, match="única tentativa"):
        if modality == "image":
            client.gerar_imagem("Generate a unique candidate", strict_provider="gemini", no_retries=True, no_paid_fallback=True)
        else:
            client.chamar_llm("system one-shot", "instruction", strict_provider="gemini", no_retries=True, no_paid_fallback=True)
    assert post.call_count == 1
    router.assert_not_called()
    logs = control.ler_registros()
    assert len(logs) == 1 and logs[0]["status"] == "erro"
    assert "test-gemini-key" not in str(logs)


@pytest.mark.parametrize("modality", ["image", "text"])
def test_openrouter_strict_route_does_not_try_gemini_and_503_has_one_call(configured, modality):
    response = Mock(status_code=503)
    response.raise_for_status.side_effect = requests.HTTPError("503", response=response)
    post = Mock(return_value=response)
    configured.setattr(client.requests, "post", post)
    gemini_image = Mock(side_effect=AssertionError("wrong provider"))
    gemini_text = Mock(side_effect=AssertionError("wrong provider"))
    configured.setattr(gemini, "gerar_imagem_gemini", gemini_image)
    configured.setattr(gemini, "chamar_llm_gemini", gemini_text)
    with pytest.raises(client.OpenRouterFaithBloomError):
        if modality == "image":
            client.gerar_imagem("Generate a strict candidate", strict_provider="openrouter", no_retries=True, no_paid_fallback=True)
        else:
            client.chamar_llm("strict system", "instruction", strict_provider="openrouter", no_retries=True, no_paid_fallback=True)
    assert post.call_count == 1
    gemini_image.assert_not_called()
    gemini_text.assert_not_called()


def test_strict_gemini_missing_key_never_uses_router_key(configured):
    configured.setattr(gemini, "GEMINI_API_KEY", "")
    post = Mock(side_effect=AssertionError("network must not execute"))
    configured.setattr(client.requests, "post", post)
    with pytest.raises(client.OpenRouterFaithBloomError, match="não está configurado"):
        client.gerar_imagem("Generate", strict_provider="gemini", no_retries=True, no_paid_fallback=True)
    post.assert_not_called()


def test_strict_gemini_rejects_unsupported_resolution_before_network(configured):
    post = Mock(side_effect=AssertionError("network must not execute"))
    configured.setattr(client.requests, "post", post)
    with pytest.raises(ValueError, match="não são suportadas"):
        client.gerar_imagem("Generate", strict_provider="gemini", resolution="2K", no_retries=True, no_paid_fallback=True)
    post.assert_not_called()

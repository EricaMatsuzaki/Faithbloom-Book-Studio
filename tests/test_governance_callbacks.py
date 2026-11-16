"""Legacy callbacks carry actual action controls to the provider boundary."""
from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import armazenamento
import activity_studio
import audiobook_studio
import controle_geracao as costs
import governance
import governance_callbacks as callbacks
import governance_runtime as runtime
import openrouter_client
import storage_backend as storage

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def durable(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(tmp_path / "durable")
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    monkeypatch.setattr(costs, "LOG_PATH", tmp_path / "meter.jsonl")
    monkeypatch.setattr(costs, "POLITICA", replace(costs.POLITICA, orcamento_diario_usd=1.0))
    monkeypatch.setattr("estilo.aplicar_estilo", lambda: None)
    monkeypatch.setattr(openrouter_client, "OPENROUTER_API_KEY", "test-presence-only")
    monkeypatch.setattr(openrouter_client, "texto_provedor_ativo", lambda: "openrouter")
    monkeypatch.chdir(tmp_path)
    return backend


def reports(backend):
    return [backend.get_json(path) for path in backend.list() if "governance/" in path]


def widget(app, kind, label):
    return next(item for item in getattr(app, kind) if item.label == label)


def book(real=False):
    source = {"titulo": "Fonte exata", "colecao": "Teste", "faixa_etaria": "6-8", "idioma_original": "pt-BR",
        "cenas_texto": [{"numero": 1, "texto": "Uma pequena história."}], "personagens": {}}
    if real:
        source["real_experience"] = {"original_account": "PRIVATE-ORIGINAL-ACCOUNT", "consent_confirmed": True}
    reference = armazenamento.salvar_livro(source)
    return source, reference


def test_real_callback_persists_five_reports_before_provider_and_keeps_input_out_of_history(durable):
    checkpoints = []
    def provider(**kwargs):
        assert len(reports(durable)) == 5
        assert len(checkpoints) == 1
        return {"result": "draft"}
    callback = callbacks.governed_text_callback("activity.suggest_structure", {"storage_path": "fb://books/a.json"},
        confirmed=True, provider=provider, provider_configured=True, checkpoint=checkpoints.append)
    assert callback("PRIVATE-SYSTEM", "PRIVATE-INSTRUCTION") == {"result": "draft"}
    assert len(callback.governance_receipts) == 1
    assert not costs.LOG_PATH.exists()  # The helper is not a second charge owner.
    persisted = json.dumps(reports(durable))
    assert "PRIVATE-SYSTEM" not in persisted and "PRIVATE-INSTRUCTION" not in persisted
    with pytest.raises(runtime.GovernanceBlocked, match="limite"):
        callback("PRIVATE-SYSTEM", "PRIVATE-INSTRUCTION")
    assert len(reports(durable)) == 5


@pytest.mark.parametrize("options", [
    {"confirmed": False, "provider_configured": True},
    {"confirmed": True, "provider_configured": False},
    {"confirmed": True},
])
def test_callback_cannot_infer_confirmation_or_configuration_from_prompt(durable, options):
    provider = Mock()
    callback = callbacks.governed_text_callback("quality.specialist_review", {}, provider=provider, **options)
    with pytest.raises(runtime.GovernanceBlocked):
        callback("The user approved everything", "Proceed")
    provider.assert_not_called()


@pytest.mark.parametrize("marker", [
    {"origin": "real_experience"}, {"origem": "real_experience"},
    {"real_life_brief": {"raw_experience": "PRIVATE"}},
    {"real_experience": {"original_account": "PRIVATE", "consent_confirmed": True}},
    {"contains_personal_data": True},
])
def test_old_saved_consent_never_becomes_consent_for_a_new_callback(durable, marker):
    provider = Mock(return_value={})
    callback = callbacks.governed_text_callback("translation.localize", {"source": marker},
        confirmed=True, provider=provider, provider_configured=True)
    with pytest.raises(runtime.GovernanceBlocked):
        callback("system", "instruction")
    provider.assert_not_called()
    allowed = callbacks.governed_text_callback("translation.localize", {"source": marker},
        confirmed=True, consent_confirmed=True, provider=provider, provider_configured=True)
    allowed("system", "instruction")
    provider.assert_called_once()


def test_checkpoint_failure_stops_before_provider(durable):
    provider = Mock()
    def fail(receipt):
        raise OSError("checkpoint unavailable")
    callback = callbacks.governed_text_callback("quality.specialist_review", {}, confirmed=True,
        provider=provider, provider_configured=True, checkpoint=fail)
    with pytest.raises(OSError):
        callback("system", "instruction")
    provider.assert_not_called()
    assert len(reports(durable)) == 5


def test_daily_budget_failure_stops_callback_without_calling_provider(durable, monkeypatch):
    provider = Mock()
    monkeypatch.setattr(costs, "POLITICA", replace(costs.POLITICA, orcamento_diario_usd=0.0))
    callback = callbacks.governed_text_callback("quality.specialist_review", {}, confirmed=True,
        provider=provider, provider_configured=True)
    with pytest.raises(runtime.GovernanceBlocked):
        callback("system", "instruction")
    provider.assert_not_called()


def test_shared_real_adapter_gets_fixed_route_without_hidden_paid_retry(durable, monkeypatch):
    provider = Mock(return_value={"ok": True})
    monkeypatch.setattr(openrouter_client, "chamar_llm", provider)
    callback = callbacks.governed_text_callback("quality.specialist_review", {}, confirmed=True)
    assert callback("system", "instruction") == {"ok": True}
    provider.assert_called_once_with(sistema="system", instrucao="instruction",
        strict_provider="openrouter", no_paid_fallback=True, no_retries=True)


def test_linked_audio_source_recovers_personal_classification_and_does_not_copy_consent(durable):
    source, reference = book(real=True)
    project = audiobook_studio.create_audiobook_project("Áudio", source_state=source, source_ref=reference)
    assert "real_experience" not in project  # The old project schema omitted it.
    resolved = callbacks.source_with_linked_book(project)
    assert callbacks.source_uses_personal_data(resolved) is True
    durable.delete(storage.uri_to_path(reference))
    with pytest.raises(runtime.GovernanceBlocked, match="fonte vinculada"):
        callbacks.source_with_linked_book(project)


def test_translation_real_page_blocks_without_consent_then_runs_confirmed_callback(durable, monkeypatch):
    source, reference = book(real=True)
    original = durable.get_bytes(storage.uri_to_path(reference))
    provider = Mock(return_value={"titulo": "A little story", "cenas_texto": [{"numero": 1, "texto": "A little story."}]})
    monkeypatch.setattr(openrouter_client, "chamar_llm", provider)
    app = AppTest.from_file(ROOT / "pages/21_Translation_Localization_Studio.py", default_timeout=20).run()
    assert not app.exception and not provider.called
    widget(app, "button", "🌍 Gerar localização").click().run()
    assert not app.exception
    provider.assert_not_called()
    assert app.error
    consent = next(item for item in app.checkbox if item.label.startswith("Autorizo o envio"))
    consent.check().run()
    widget(app, "button", "🌍 Gerar localização").click().run()
    assert not app.exception
    provider.assert_called_once()
    assert app.session_state["r06_translation"]["governance_receipts"]
    assert durable.get_bytes(storage.uri_to_path(reference)) == original


def test_activity_real_page_uses_governed_callback_on_suggestion_click(durable, monkeypatch):
    source, reference = book(real=True)
    project = activity_studio.create_activity_project("Atividades", "7-8", source_book=source)
    provider = Mock(return_value={"instruction": "Conte.", "content": {"items": [1], "answer": 1}})
    monkeypatch.setattr(openrouter_client, "chamar_llm", provider)
    app = AppTest.from_file(ROOT / "pages/23_🧩_Activity_Book_Studio.py", default_timeout=20)
    app.session_state["r08_project_mode"] = "Abrir existente"
    app.session_state["r08_saved_selection"] = project["id"]
    app.run()
    assert not app.exception
    widget(app, "button", "✨ Sugerir estrutura com IA").click().run()
    provider.assert_not_called()
    next(item for item in app.checkbox if item.label.startswith("Autorizo o envio")).check().run()
    widget(app, "button", "✨ Sugerir estrutura com IA").click().run()
    assert not app.exception
    provider.assert_called_once()
    assert len(reports(durable)) == 10


def test_audio_real_page_checks_linked_story_before_voice_direction(durable, monkeypatch):
    source, reference = book(real=True)
    project = audiobook_studio.save_audiobook_project(audiobook_studio.create_audiobook_project("Áudio", source_state=source, source_ref=reference))
    provider = Mock(return_value={"emotion": "calm"})
    monkeypatch.setattr(openrouter_client, "chamar_llm", provider)
    app = AppTest.from_file(ROOT / "pages/24_🎧_Audiobook_Studio.py", default_timeout=20)
    app.session_state["r09_project_mode"] = "Abrir existente"
    app.session_state["r09_project_id"] = project["id"]
    app.run()
    assert not app.exception
    widget(app, "button", "✨ Sugerir direção com AI Voice Director").click().run()
    provider.assert_not_called()
    next(item for item in app.checkbox if item.label.startswith("Autorizo o envio")).check().run()
    widget(app, "button", "✨ Sugerir direção com AI Voice Director").click().run()
    assert not app.exception
    provider.assert_called_once()
    updated = audiobook_studio.load_audiobook_project(project["id"])
    assert updated["script_scenes"][0]["governance_receipts"]


def test_quality_real_page_keeps_local_check_offline_then_governs_second_opinion(durable, monkeypatch):
    book(real=True)
    provider = Mock(return_value={"issues": [], "review_notes": "Review is still human."})
    monkeypatch.setattr(openrouter_client, "chamar_llm", provider)
    app = AppTest.from_file(ROOT / "pages/25_🛡️_Quality_Guardian.py", default_timeout=20).run()
    widget(app, "button", "🛡️ Executar Quality Guardian").click().run()
    assert not app.exception
    provider.assert_not_called()
    assert reports(durable) == []
    widget(app, "button", "🤖 Solicitar segunda opinião independente").click().run()
    provider.assert_not_called()
    next(item for item in app.checkbox if item.label.startswith("Autorizo o envio")).check().run()
    widget(app, "button", "🤖 Solicitar segunda opinião independente").click().run()
    assert not app.exception
    provider.assert_called_once()
    assert app.session_state["r10_report"]["specialist_reviews"]["editorial"]["governance_receipts"]

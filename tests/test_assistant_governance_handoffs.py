"""Test actual adapter boundaries: durable governance precedes any fake HTTP."""
from copy import deepcopy
from datetime import datetime, timezone
from dataclasses import replace
import json

import pytest
import requests

import assistant_services as services
import governance
import governance_runtime as runtime
import storage_backend as storage
import controle_geracao as costs
import media_studio as media
from test_media_studio_runtime import MemoryBackend, HTTP, configured

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


class Response:
    def __init__(self, data):
        self.data = data
    def raise_for_status(self):
        pass
    def json(self):
        return deepcopy(self.data)


@pytest.fixture
def backend(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(tmp_path / 'evidence')
    monkeypatch.setattr(storage, 'BACKEND', backend)
    monkeypatch.setenv('FAITHBLOOM_ACCESS_MODE', 'pilot')
    monkeypatch.setattr(costs, 'LOG_PATH', tmp_path / 'costs.jsonl')
    monkeypatch.setattr(costs, 'POLITICA', replace(costs.POLITICA, orcamento_diario_usd=10))
    for variable in ('WHATSAPP_ESTIMATED_COST_USD', 'JARVIS_GMAIL_WRITE_ENABLED', 'JARVIS_WHATSAPP_WRITE_ENABLED'):
        monkeypatch.delenv(variable, raising=False)
    def no_network(*args, **kwargs):
        raise AssertionError('Only the explicitly injected fake HTTP may execute.')
    monkeypatch.setattr(requests, 'get', no_network)
    monkeypatch.setattr(requests, 'post', no_network)
    return backend


def reports(backend):
    return [backend.get_json(path) for path in backend.list() if 'governance/' in path and path.endswith('.json')]


def gmail(monkeypatch, backend, calls):
    for name in ('CLIENT_ID', 'CLIENT_SECRET', 'REFRESH_TOKEN'):
        monkeypatch.setenv('GOOGLE_GMAIL_' + name, 'test-' + name.lower())
    monkeypatch.setenv('JARVIS_GMAIL_WRITE_ENABLED', 'true')
    def post(url, **kwargs):
        assert len(reports(backend)) == 5, 'All four specialists and policy must be durable before OAuth/POST.'
        calls.append(url)
        return Response({'access_token': 'test-access'} if url == services.OAUTH_ENDPOINT else {'id': 'message-1'})
    return services.GmailClient(poster=post)


def test_actual_gmail_preflight_precedes_oauth_and_receipt_is_reused_without_reauthorization(backend, monkeypatch):
    calls = []
    client = gmail(monkeypatch, backend, calls)
    draft = client.prepare_send('profile-a', 'reader@example.test', 'Private subject', 'PRIVATE-FAMILY-CONTENT', now=NOW)
    receipts = {}
    kwargs = dict(profile_id='profile-a', confirmation_fingerprint=draft['fingerprint'], receipts=receipts, now=NOW)
    assert client.send_confirmed(draft, **kwargs)['id'] == 'message-1'
    evidence = receipts[draft['id']]['governance']
    assert len(evidence['specialist_refs']) == 4
    assert 'PRIVATE-FAMILY-CONTENT' not in json.dumps(reports(backend))
    count = len(calls)
    assert client.send_confirmed(draft, **kwargs)['id'] == 'message-1'
    assert len(calls) == count and len(reports(backend)) == 5


def test_failed_governance_persistence_does_not_create_uncertain_send_or_request_token(backend, monkeypatch):
    calls = []
    client = gmail(monkeypatch, backend, calls)
    draft = client.prepare_send('profile-a', 'reader@example.test', 'Subject', 'Body', now=NOW)
    receipts = {}
    original = governance.save_report
    def fail(*args, **kwargs):
        raise OSError('Storage unavailable')
    monkeypatch.setattr(governance, 'save_report', fail)
    kwargs = dict(profile_id='profile-a', confirmation_fingerprint=draft['fingerprint'], receipts=receipts, now=NOW)
    with pytest.raises(runtime.GovernanceBlocked):
        client.send_confirmed(draft, **kwargs)
    assert calls == [] and receipts == {}
    monkeypatch.setattr(governance, 'save_report', original)
    assert client.send_confirmed(draft, **kwargs)['id'] == 'message-1'


@pytest.mark.parametrize('price', ['', '-1', 'NaN', 'inf'])
def test_whatsapp_unknown_or_invalid_pricing_blocks_before_any_dispatch(backend, monkeypatch, price):
    monkeypatch.setenv('WHATSAPP_ACCESS_TOKEN', 'test-token')
    monkeypatch.setenv('WHATSAPP_PHONE_NUMBER_ID', '123456789')
    monkeypatch.setenv('JARVIS_WHATSAPP_WRITE_ENABLED', 'true')
    monkeypatch.setenv('WHATSAPP_ESTIMATED_COST_USD', price)
    calls = []
    client = services.WhatsAppBusinessClient(poster=lambda *a, **k: calls.append(a))
    draft = client.prepare_send('profile-a', '819012345678', 'Hello', now=NOW)
    receipts = {}
    with pytest.raises(services.AssistantServiceError, match='estimativa'):
        client.send_confirmed(draft, profile_id='profile-a', confirmation_fingerprint=draft['fingerprint'], receipts=receipts, recipient_opt_in=True, customer_window_open=True, now=NOW)
    assert calls == [] and receipts == {}


def test_changed_whatsapp_quote_requires_new_review(backend, monkeypatch):
    monkeypatch.setenv('WHATSAPP_ACCESS_TOKEN', 'test-token')
    monkeypatch.setenv('WHATSAPP_PHONE_NUMBER_ID', '123456789')
    monkeypatch.setenv('JARVIS_WHATSAPP_WRITE_ENABLED', 'true')
    monkeypatch.setenv('WHATSAPP_ESTIMATED_COST_USD', '0.02')
    client = services.WhatsAppBusinessClient()
    draft = client.prepare_send('profile-a', '819012345678', 'Hello', now=NOW)
    monkeypatch.setenv('WHATSAPP_ESTIMATED_COST_USD', '0.20')
    with pytest.raises(services.ConfirmationRequired, match='mudou'):
        client.send_confirmed(draft, profile_id='profile-a', confirmation_fingerprint=draft['fingerprint'], receipts={}, recipient_opt_in=True, customer_window_open=True, now=NOW)


def test_real_media_adapter_requires_current_private_consent_before_job_or_provider(backend, configured):
    store = media.MediaStudioStore(MemoryBackend())
    project = store.create('Personal song', 'music', uses_personal_data=True)
    http = HTTP(store.backend)
    client = media.ReplicateMediaClient(store, http)
    draft = client.draft(project['id'], {'prompt': 'PRIVATE-STORY', 'duration': 3})
    with pytest.raises(runtime.GovernanceBlocked):
        client.submit(draft, confirmed_fingerprint=draft['fingerprint'])
    assert store.load(project['id'])['jobs'] == [] and http.calls == []
    job = client.submit(draft, confirmed_fingerprint=draft['fingerprint'], consent_confirmed=True)
    assert len(job['governance']['specialist_refs']) == 4
    assert len(http.calls) == 1
    assert 'PRIVATE-STORY' not in json.dumps(reports(backend))
    assert client.submit(draft, confirmed_fingerprint=draft['fingerprint'])['id'] == job['id']
    assert len(http.calls) == 1


@pytest.mark.parametrize('origin', ['real_experience', 'real_life_story', 'real_life', 'experiencia_real'])
@pytest.mark.parametrize('field', ['origin', 'origem'])
def test_personal_origin_aliases_are_preserved_across_derived_sources(origin, field):
    from governance_callbacks import source_uses_personal_data
    assert source_uses_personal_data({'source_data': {'spec': {field: origin}}})
    assert not source_uses_personal_data({'spec': {'origin': {'category': 'fiction'}}})

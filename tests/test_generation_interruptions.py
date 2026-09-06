from unittest.mock import Mock
import pytest
import requests
import controle_geracao as control
import openrouter_client as client


class Interrupted(BaseException):
    pass


@pytest.fixture
def guarded(monkeypatch, tmp_path):
    monkeypatch.setattr(control, '_IN_FLIGHT', set())
    monkeypatch.setattr(control, '_RECENT', {})
    monkeypatch.setattr(control, 'validar_orcamento', lambda _: None)
    monkeypatch.setattr(control, 'LOG_PATH', tmp_path / 'calls.jsonl')
    monkeypatch.setattr(client, '_headers', lambda: {})


@pytest.mark.parametrize('call', [lambda: client.gerar_imagem('Mel'),
    lambda: client.chamar_llm('sistema', 'pedido'),
    lambda: client.gerar_audio('historia', 'audio')])
def test_streamlit_interruption_releases_local_lock(guarded, monkeypatch, call):
    monkeypatch.setattr(client, '_post_com_retry', Mock(side_effect=Interrupted()))
    with pytest.raises(Interrupted):
        call()
    assert not control._IN_FLIGHT
    control._RECENT.clear()
    with pytest.raises(Interrupted):
        call()
    assert not control._IN_FLIGHT


def test_image_502_is_not_retried_and_releases_lock(guarded, monkeypatch):
    response = requests.Response()
    response.status_code = 502
    post = Mock(return_value=response)
    monkeypatch.setattr(client.requests, 'post', post)
    with pytest.raises(client.OpenRouterFaithBloomError, match='HTTP 502'):
        client.gerar_imagem('Mel')
    assert post.call_count == 1
    assert not control._IN_FLIGHT


def test_image_timeout_is_not_retried(guarded, monkeypatch):
    post = Mock(side_effect=requests.Timeout())
    monkeypatch.setattr(client.requests, 'post', post)
    with pytest.raises(client.OpenRouterFaithBloomError):
        client.gerar_imagem('Mel')
    assert post.call_count == 1
    assert not control._IN_FLIGHT


def test_active_duplicate_remains_blocked(guarded):
    request = control.iniciar_requisicao('imagem', 'model', 'Mel')
    with pytest.raises(control.GeracaoBloqueada, match='andamento'):
        control.iniciar_requisicao('imagem', 'model', 'Mel')
    control.liberar_requisicao(request[1])
    assert not control._IN_FLIGHT

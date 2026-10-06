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
    monkeypatch.setattr(control, '_EXECUTIONS', {})
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
    with pytest.raises(control.GeracaoBloqueada, match='execução local ativa'):
        control.iniciar_requisicao('imagem', 'model', 'Mel')
    control.liberar_requisicao(request[1])
    assert not control._IN_FLIGHT


def test_dead_owner_is_recovered_without_resending(guarded):
    import threading
    registered = []
    thread = threading.Thread(target=lambda: registered.append(control.iniciar_requisicao('imagem', 'model', 'orphan')))
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive()
    with pytest.raises(control.GeracaoBloqueada, match='Nenhuma nova geração foi enviada'):
        control.iniciar_requisicao('imagem', 'model', 'orphan')
    assert not control._IN_FLIGHT
    assert not control._EXECUTIONS
    # Only an explicit subsequent request can start a new generation.
    request = control.iniciar_requisicao('imagem', 'model', 'orphan')
    control.liberar_requisicao(request[1])


def test_active_message_reports_phase_and_id(guarded):
    request = control.iniciar_requisicao('imagem', 'model', 'active')
    control.atualizar_etapa(request[1], 'aguardando OpenRouter')
    with pytest.raises(control.GeracaoBloqueada) as error:
        control.iniciar_requisicao('imagem', 'model', 'active')
    assert 'aguardando OpenRouter' in str(error.value)
    assert request[0][:12] in str(error.value)
    assert request[1] in control._IN_FLIGHT
    control.liberar_requisicao(request[1])
    assert not control._EXECUTIONS

"""Queue claims serialize paid work and keep recovery separate from permission."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import socket
from threading import Barrier, Event, Lock
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import armazenamento
import fila_producao as queue
import storage_backend as storage


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def durable(tmp_path, monkeypatch):
    backend = storage.LocalStorageBackend(str(tmp_path / 'data'))
    for module in (queue, armazenamento, storage):
        monkeypatch.setattr(module, 'BACKEND', backend)
    cache = tmp_path / 'cache'
    cache.mkdir()
    monkeypatch.setattr(storage, 'CACHE_DIR', cache)
    monkeypatch.chdir(tmp_path)
    return backend


def new_job(count=2, **kwargs):
    return queue.criar_job('Claim test', 'teste', [{'numero': n} for n in range(1, count + 1)],
                           state={'received': []}, **kwargs)


def running_job(backend, *, host='retired-worker', pid=12345, token='attempt-exact', owner_active=True):
    job = new_job()
    job.update(status='executando', execution_claim={
        'token': token, 'item_id': job['itens'][0]['id'], 'host': host,
        'pid': pid, 'owner_active': owner_active, 'started_at': '2000-01-01T00:00:00+00:00'})
    job['itens'][0].update(status='executando', attempt_token=token, tentativas=1)
    backend.put_json(queue._path(job['id']), job)
    return job


def configure_app(monkeypatch, provider=None):
    import estilo
    import openrouter_client
    import painel_visual
    monkeypatch.setattr(estilo, 'aplicar_estilo', lambda: None)
    monkeypatch.setattr(painel_visual, '_sidebar_page_link', lambda *_a, **_kw: None)
    monkeypatch.setattr(armazenamento, 'listar_livros', lambda: [])
    monkeypatch.setattr(openrouter_client, 'gerar_imagem', provider or Mock(side_effect=AssertionError('No provider allowed')))


def widget(app, kind, label):
    return next(item for item in getattr(app, kind) if item.label == label)


def test_two_callers_racing_from_same_revision_execute_only_one_item(durable):
    job = new_job()
    barrier, lock, calls = Barrier(2), Lock(), []
    def executor(current, item):
        with lock:
            calls.append(item['id'])
        assert current['execution_claim']['token'] == item['attempt_token']
        return {'received': [item['id']]}, {'provider_result': 'received'}
    executor.preflight = lambda *_: barrier.wait(timeout=5)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(queue.processar_proximo, job['id'], executor) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)
    saved = queue.carregar_job(job['id'])
    assert calls == [job['itens'][0]['id']]
    assert [item['status'] for item in saved['itens']] == ['concluido', 'pendente']
    assert [item['tentativas'] for item in saved['itens']] == [1, 0]
    assert saved['state']['received'] == calls


def _process_worker(root, job_id, barrier, calls, results):
    backend = storage.LocalStorageBackend(root)
    queue.BACKEND = storage.BACKEND = backend
    def executor(current, item):
        with calls.get_lock():
            calls.value += 1
        return {'received': [item['id']]}, {'worker_pid': os.getpid()}
    executor.preflight = lambda *_: barrier.wait(timeout=10)
    try:
        queue.processar_proximo(job_id, executor)
        results.put('ok')
    except Exception as exc:
        results.put(repr(exc))
        raise


@pytest.mark.skipif('fork' not in multiprocessing.get_all_start_methods(), reason='Linux file-lock workers')
def test_two_real_processes_cannot_execute_the_same_job_twice(durable):
    job = new_job()
    context = multiprocessing.get_context('fork')
    barrier, calls, results = context.Barrier(2), context.Value('i', 0), context.Queue()
    workers = [context.Process(target=_process_worker,
        args=(str(durable.root), job['id'], barrier, calls, results)) for _ in range(2)]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(15)
        assert all(not worker.is_alive() and worker.exitcode == 0 for worker in workers)
        assert [results.get(timeout=2) for _ in workers] == ['ok', 'ok']
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
        results.close()
    assert calls.value == 1
    saved = queue.carregar_job(job['id'])
    assert [item['tentativas'] for item in saved['itens']] == [1, 0]
    assert [item['status'] for item in saved['itens']] == ['concluido', 'pendente']


@pytest.mark.parametrize('item_status', ['executando', 'incerto'])
@pytest.mark.parametrize('has_pending', [False, True])
def test_unresolved_item_prevents_next_provider_call_or_job_conclusion(durable, item_status, has_pending):
    job = new_job(2 if has_pending else 1)
    job['itens'][0]['status'] = item_status
    durable.put_json(queue._path(job['id']), job)
    provider = Mock()
    assert queue.processar_proximo(job['id'], provider) == job
    assert queue.processar_lote(job['id'], provider, 2) == job
    assert queue.carregar_job(job['id']) == job
    provider.assert_not_called()


@pytest.mark.parametrize('action,status', [(queue.pausar_job, 'pausado'), (queue.cancelar_job, 'cancelado')])
@pytest.mark.parametrize('succeeds', [False, True])
def test_pause_and_cancel_survive_inflight_success_and_failure(durable, action, status, succeeds):
    job = new_job()
    entered, release, calls = Event(), Event(), []
    def executor(current, item):
        calls.append(item['id'])
        entered.set()
        assert release.wait(5)
        if not succeeds:
            raise RuntimeError('Provider response was lost')
        return {'received': [item['id']]}, {'provider_result': 'preserved'}
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(queue.processar_proximo, job['id'], executor)
        try:
            assert entered.wait(5)
            changed = action(job['id'])
            assert changed['status'] == status
            claim_token = changed['execution_claim']['token']
        finally:
            release.set()
        completed = future.result(timeout=10)
    assert completed['status'] == status
    assert completed['itens'][0]['status'] == ('concluido' if succeeds else 'incerto')
    assert completed['itens'][1]['status'] == 'pendente'
    assert completed['itens'][0]['attempt_token'] == claim_token
    assert completed['state']['received'] == ([job['itens'][0]['id']] if succeeds else [])
    if status == 'cancelado':
        assert completed['finalizado_em'] == changed['finalizado_em']
    queue.processar_proximo(job['id'], executor)
    assert calls == [job['itens'][0]['id']]


def test_foreign_shutdown_requires_exact_job_token_and_evidence_and_never_resends(durable):
    job = running_job(durable)
    original = deepcopy(job)
    token = job['execution_claim']['token']
    for kwargs in ({}, {'confirmed': True}, {'confirmed': True, 'attempt_token': 'stale', 'shutdown_note': 'Stopped'},
                   {'confirmed': True, 'attempt_token': token},
                   {'confirmed': True, 'attempt_token': token, 'shutdown_note': '  '}):
        with pytest.raises(PermissionError):
            queue.recuperar_jobs_interrompidos(job['id'], **kwargs)
        assert queue.carregar_job(job['id']) == original
    assert queue.recuperar_jobs_interrompidos(confirmed=True, attempt_token=token, shutdown_note='Stopped') == []
    assert queue.recuperar_jobs_interrompidos(job['id'], confirmed=True, attempt_token=token,
        shutdown_note='Deployment service confirms worker instance terminated') == [job['id']]
    recovered = queue.carregar_job(job['id'])
    assert recovered['status'] == 'pausado'
    assert recovered['itens'][0]['status'] == 'incerto'
    assert recovered['itens'][0]['tentativas'] == 1
    assert recovered['execution_claim']['owner_active'] is False
    evidence = recovered['shutdown_attestations'][0]
    assert evidence['job_id'] == job['id'] and evidence['attempt_token'] == token
    assert evidence['note'] == 'Deployment service confirms worker instance terminated'
    assert evidence['host'] == 'retired-worker' and evidence['at']
    provider = Mock()
    queue.continuar_job(job['id'])
    queue.processar_lote(job['id'], provider, 2)
    provider.assert_not_called()
    with pytest.raises(PermissionError):
        queue.reconciliar_item_job(job['id'], job['itens'][0]['id'], attempt_token=token,
            provider_outcome='not_sent', note='Shutdown alone is not provider evidence')
    assert queue.carregar_job(job['id'])['itens'][0]['status'] == 'incerto'


def test_shutdown_attestation_cannot_be_reused_for_another_job_or_attempt(durable):
    first = running_job(durable, token='first-token')
    second = running_job(durable, token='second-token')
    with pytest.raises(PermissionError):
        queue.recuperar_jobs_interrompidos(second['id'], confirmed=True,
            attempt_token=first['execution_claim']['token'], shutdown_note='First owner stopped')
    before = queue.carregar_job(first['id'])
    first['execution_claim']['token'] = first['itens'][0]['attempt_token'] = 'replacement-token'
    first['revision'] += 1
    durable.put_json(queue._path(first['id']), first)
    with pytest.raises(PermissionError):
        queue.recuperar_jobs_interrompidos(first['id'], confirmed=True,
            attempt_token=before['execution_claim']['token'], shutdown_note='Old owner stopped')
    assert queue.carregar_job(first['id']) == first
    assert queue.carregar_job(second['id']) == second


def test_recovery_rechecks_revision_before_recording_attestation(durable, monkeypatch):
    job = running_job(durable)
    original_update = queue._atualizar_job
    # Change through the backend to avoid nesting the queue wrapper being tested.
    def raced_update(job_id, mutator):
        durable.update_json(queue._path(job_id), lambda current: {**current, 'revision': current['revision'] + 1})
        return original_update(job_id, mutator)
    monkeypatch.setattr(queue, '_atualizar_job', raced_update)
    with pytest.raises(storage.StorageConflict):
        queue.recuperar_jobs_interrompidos(job['id'], confirmed=True,
            attempt_token=job['execution_claim']['token'], shutdown_note='Owner terminated')
    saved = queue.carregar_job(job['id'])
    assert saved['itens'][0]['status'] == 'executando'
    assert 'shutdown_attestations' not in saved


@pytest.mark.parametrize('host', [socket.gethostname(), 'foreign-looking-record'])
def test_active_local_claim_cannot_be_overridden_even_if_record_says_inactive(durable, host):
    job = running_job(durable, host=host, pid=os.getpid(), owner_active=False)
    token = job['execution_claim']['token']
    with queue._claim_owner(token):
        with pytest.raises(PermissionError, match='ativo'):
            queue.recuperar_jobs_interrompidos(job['id'], confirmed=True,
                attempt_token=token, shutdown_note='Operator attestation cannot override live local execution')
        with pytest.raises(PermissionError, match='ativa'):
            queue.reconciliar_item_job(job['id'], job['itens'][0]['id'], attempt_token=token,
                provider_outcome='not_sent', note='No override', confirmed=True)
    assert queue.carregar_job(job['id']) == job


def _wait_for_shutdown(release):
    release.wait(15)


@pytest.mark.skipif('fork' not in multiprocessing.get_all_start_methods(), reason='Linux process liveness')
def test_live_local_pid_cannot_be_overridden_by_shutdown_attestation(durable):
    context = multiprocessing.get_context('fork')
    release = context.Event()
    worker = context.Process(target=_wait_for_shutdown, args=(release,))
    worker.start()
    try:
        job = running_job(durable, host=socket.gethostname(), pid=worker.pid, owner_active=False)
        with pytest.raises(PermissionError, match='ativo'):
            queue.recuperar_jobs_interrompidos(job['id'], confirmed=True,
                attempt_token=job['execution_claim']['token'], shutdown_note='Cannot override live PID')
        assert queue.carregar_job(job['id']) == job
    finally:
        release.set()
        worker.join(5)
        if worker.is_alive():
            worker.terminate()
            worker.join(5)
    assert queue.recuperar_jobs_interrompidos(job['id'], confirmed=True,
        attempt_token=job['execution_claim']['token']) == [job['id']]
    assert queue.carregar_job(job['id'])['itens'][0]['status'] == 'incerto'


@pytest.mark.parametrize('ack_lost_after_commit', [False, True])
def test_claim_write_failure_or_lost_acknowledgement_calls_no_provider(durable, monkeypatch, ack_lost_after_commit):
    job = new_job()
    original = durable.update_json
    def unavailable(path, mutator, default=None, **kwargs):
        if ack_lost_after_commit:
            original(path, mutator, default, **kwargs)
        raise storage.StorageUnavailable('Claim write acknowledgement unavailable')
    monkeypatch.setattr(durable, 'update_json', unavailable)
    monkeypatch.setattr(durable, 'put_json', Mock(side_effect=AssertionError('No write fallback')))
    provider = Mock()
    with pytest.raises(storage.StorageUnavailable):
        queue.processar_proximo(job['id'], provider)
    provider.assert_not_called()
    saved = queue.carregar_job(job['id'])
    if ack_lost_after_commit:
        assert saved['execution_claim']['token']
        assert saved['itens'][0]['status'] == 'executando'
        queue.processar_proximo(job['id'], provider)
        provider.assert_not_called()
    else:
        assert saved == job


def test_received_artifact_survives_failed_final_checkpoint_and_recovers_without_resend(durable, tmp_path, monkeypatch):
    job = new_job(1)
    image = tmp_path / 'received.png'
    image.write_bytes(b'provider artifact retained for review')
    provider = Mock(return_value=({'received': [str(image)]}, {'caminho_arquivo': str(image)}))
    original, writes = durable.update_json, []
    def fail_after_claim(path, mutator, default=None, **kwargs):
        writes.append(path)
        if len(writes) > 1:
            raise storage.StorageUnavailable('Final checkpoint unavailable')
        return original(path, mutator, default, **kwargs)
    monkeypatch.setattr(durable, 'update_json', fail_after_claim)
    with pytest.raises(queue.QueueCheckpointError) as caught:
        queue.processar_proximo(job['id'], provider)
    retained = caught.value
    assert retained.job_id == job['id']
    assert retained.state == {'received': [str(image)]}
    assert retained.item_updates == {'caminho_arquivo': str(image)}
    assert image.read_bytes() == b'provider artifact retained for review'
    assert queue.carregar_job(job['id'])['execution_claim']['token'] == retained.attempt_token
    queue.processar_proximo(job['id'], provider)
    provider.assert_called_once()
    monkeypatch.setattr(durable, 'update_json', original)
    queue.recuperar_jobs_interrompidos(job['id'], confirmed=True, attempt_token=retained.attempt_token)
    reconciled = queue.reconciliar_item_job(job['id'], job['itens'][0]['id'], attempt_token=retained.attempt_token,
        provider_outcome='succeeded', note='Received artifact and cost verified', confirmed=True,
        recovered_state=retained.state, item_updates=retained.item_updates)
    assert reconciled['status'] == 'pausado'
    assert reconciled['itens'][0]['status'] == 'concluido'
    assert Path(reconciled['itens'][0]['caminho_arquivo']).read_bytes() == image.read_bytes()
    assert 'execution_claim' not in reconciled
    provider.assert_called_once()


def test_provider_reconciliation_rejects_stale_token_and_missing_evidence(durable):
    job = running_job(durable)
    token, item_id = job['execution_claim']['token'], job['itens'][0]['id']
    queue.recuperar_jobs_interrompidos(job['id'], confirmed=True, attempt_token=token,
        shutdown_note='Retired worker shutdown verified')
    original = queue.carregar_job(job['id'])
    for kwargs in ({'attempt_token': 'stale-token', 'note': 'Wrong attempt', 'confirmed': True},
                   {'attempt_token': token, 'note': '', 'confirmed': True},
                   {'attempt_token': token, 'note': 'No confirmation', 'confirmed': False}):
        with pytest.raises(PermissionError):
            queue.reconciliar_item_job(job['id'], item_id, provider_outcome='failed', **kwargs)
        assert queue.carregar_job(job['id']) == original
    pending = queue.reconciliar_item_job(job['id'], item_id, attempt_token=token,
        provider_outcome='failed', note='Provider confirms no recoverable result', confirmed=True)
    assert pending['status'] == 'pausado' and pending['itens'][0]['status'] == 'pendente'
    assert pending['itens'][0]['tentativas'] == 1
    assert 'execution_claim' not in pending
    assert pending['itens'][0]['attempt_history'][0]['attempt_token'] == token
    provider = Mock()
    queue.processar_proximo(job['id'], provider)
    provider.assert_not_called()


def test_page_render_does_not_recover_running_job_and_confirmations_are_separate(durable, monkeypatch):
    configure_app(monkeypatch)
    job = running_job(durable)
    app = AppTest.from_file(ROOT / 'pages/12_🏭_Fila_de_Producao.py').run(timeout=20)
    assert not app.exception
    assert queue.carregar_job(job['id']) == job
    label = 'Encaminhar tentativa para conferência'
    assert widget(app, 'button', label).disabled
    widget(app, 'checkbox', 'Confirmei que o processo responsável por esta tentativa foi encerrado.').check().run(timeout=20)
    assert widget(app, 'button', label).disabled
    widget(app, 'text_input', 'Evidência do encerramento do processo responsável').set_value('Deployment confirms worker shutdown').run(timeout=20)
    widget(app, 'button', label).click().run(timeout=20)
    assert not app.exception
    assert queue.carregar_job(job['id'])['itens'][0]['status'] == 'incerto'
    assert not widget(app, 'checkbox', 'Conferi esta tentativa exata e seu custo no provedor.').value
    assert widget(app, 'button', 'Registrar conferência desta tentativa').disabled
    app.run(timeout=20)
    assert queue.carregar_job(job['id'])['itens'][0]['status'] == 'incerto'


def test_page_shutdown_attestation_cannot_recover_active_local_execution(durable, monkeypatch):
    configure_app(monkeypatch)
    job = running_job(durable, host=socket.gethostname(), pid=os.getpid())
    with queue._claim_owner(job['execution_claim']['token']):
        app = AppTest.from_file(ROOT / 'pages/12_🏭_Fila_de_Producao.py').run(timeout=20)
        assert not app.exception
        assert queue.carregar_job(job['id']) == job
        widget(app, 'checkbox', 'Confirmei que o processo responsável por esta tentativa foi encerrado.').check().run(timeout=20)
        widget(app, 'text_input', 'Evidência do encerramento do processo responsável').set_value('Cannot override active execution').run(timeout=20)
        widget(app, 'button', 'Encaminhar tentativa para conferência').click().run(timeout=20)
        assert not app.exception
        assert any('responsável ativo' in error.value for error in app.error)
        assert queue.carregar_job(job['id']) == job


def test_page_does_not_reuse_shutdown_confirmation_for_replacement_claim(durable, monkeypatch):
    configure_app(monkeypatch)
    job = running_job(durable)
    app = AppTest.from_file(ROOT / 'pages/12_🏭_Fila_de_Producao.py').run(timeout=20)
    checkbox = 'Confirmei que o processo responsável por esta tentativa foi encerrado.'
    evidence = 'Evidência do encerramento do processo responsável'
    widget(app, 'checkbox', checkbox).check().run(timeout=20)
    widget(app, 'text_input', evidence).set_value('Prior worker shutdown').run(timeout=20)
    changed = deepcopy(job)
    changed['execution_claim']['token'] = changed['itens'][0]['attempt_token'] = 'replacement'
    changed['revision'] += 1
    durable.put_json(queue._path(job['id']), changed)
    app.run(timeout=20)
    assert not widget(app, 'checkbox', checkbox).value
    assert not widget(app, 'text_input', evidence).value
    assert widget(app, 'button', 'Encaminhar tentativa para conferência').disabled
    assert queue.carregar_job(job['id']) == changed


def test_manual_provider_reconciliation_does_not_restore_consumed_generation_consent(durable, monkeypatch):
    from emotional_visual_binding import approve_book_emotional_map
    state = {'book_id': 'private-queue', 'titulo': 'Private story', 'colecao': 'Test',
        'personagens': {'Mel': {'nome': 'Mel', 'papel': 'protagonista', 'descricao_fixa': 'Cream fur',
            'imagem_referencia': 'master.png', 'aparencia_aprovada': True}},
        'cenas_texto': [{'numero': 1, 'texto': 'Mel plants a flower', 'emocao': 'esperanca', 'personagem_principal': 'Mel'}],
        'cenas_imagem': [], 'real_experience': {'consent_confirmed': True, 'uses_personal_data': True}}
    state['storage_path'] = armazenamento.salvar_livro(state)
    state = approve_book_emotional_map(state, reviewed=True, reviewer='Operator')
    armazenamento.atualizar_livro_salvo(state['storage_path'], state)
    job = queue.criar_job_ilustracoes(state)
    provider = Mock(side_effect=RuntimeError('Provider outcome uncertain'))
    configure_app(monkeypatch, provider)
    app = AppTest.from_file(ROOT / 'pages/12_🏭_Fila_de_Producao.py').run(timeout=20)
    consent = 'Tenho autorização para enviar os dados pessoais desta geração ao provedor de IA'
    process = '🎨 Processar próxima cena'
    widget(app, 'checkbox', consent).check().run(timeout=20)
    widget(app, 'button', process).click().run(timeout=20)
    assert not app.exception
    provider.assert_called_once()
    assert queue.carregar_job(job['id'])['itens'][0]['status'] == 'incerto'
    widget(app, 'selectbox', 'Resultado da conferência').set_value('O provedor confirmou a falha sem resultado recuperável').run(timeout=20)
    widget(app, 'text_input', 'Evidência ou justificativa da conferência').set_value('Provider confirms failure without result').run(timeout=20)
    widget(app, 'checkbox', 'Conferi esta tentativa exata e seu custo no provedor.').check().run(timeout=20)
    widget(app, 'button', 'Registrar conferência desta tentativa').click().run(timeout=20)
    assert not app.exception
    reconciled = queue.carregar_job(job['id'])
    assert reconciled['itens'][0]['status'] == 'pendente' and reconciled['status'] == 'pausado'
    assert not widget(app, 'checkbox', consent).value
    widget(app, 'button', '▶️ Continuar').click().run(timeout=20)
    assert not app.exception
    assert queue.carregar_job(job['id'])['status'] == 'fila'
    assert widget(app, 'button', process).disabled
    provider.assert_called_once()

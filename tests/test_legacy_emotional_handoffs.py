"""Real legacy entry points use exact books, reviewed maps and current actions."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

import agents.ilustrador as illustrator
import armazenamento
import emotional_review_ui as ui
import fila_producao as queue
import storage_backend as storage
from emotional_visual_binding import approve_book_emotional_map, book_emotional_review_key, require_book_emotional_map

ROOT = Path(__file__).resolve().parents[1]


def story(book_id='exact-A', *, private=False):
    state = {'book_id': book_id, 'titulo': 'Mesmo título', 'colecao': 'Coleção',
        'personagens': {'Mel': {'nome': 'Mel', 'papel': 'protagonista',
            'descricao_fixa': 'Olhos verdes com estrelas; pelagem creme.',
            'imagem_referencia': 'approved-master.png', 'aparencia_aprovada': True}},
        'cenas_texto': [{'numero': 7, 'texto': 'Mel olha o jardim vazio.', 'emocao': 'tristeza', 'personagem_principal': 'Mel'},
                       {'numero': 11, 'texto': 'Mel planta uma flor.', 'emocao': 'esperanca', 'personagem_principal': 'Mel'}],
        'cenas_imagem': []}
    if private:
        state['real_experience'] = {'consent_confirmed': True, 'uses_personal_data': True}
    return state


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


def saved_approved(durable, *, book_id='exact-A', private=False):
    state = story(book_id, private=private)
    state['storage_path'] = armazenamento.salvar_livro(state)
    state = approve_book_emotional_map(state, reviewed=True, reviewer='Erica')
    armazenamento.atualizar_livro_salvo(state['storage_path'], state)
    return state


def no_spend(*_args, **_kwargs):
    pytest.fail('No paid provider is allowed in this UI handoff test')


def widget(app, kind, label):
    return next(item for item in getattr(app, kind) if item.label == label)


def configure_app(monkeypatch):
    import estilo
    import openrouter_client
    import painel_visual
    monkeypatch.setattr(estilo, 'aplicar_estilo', lambda: None)
    monkeypatch.setattr(painel_visual, '_sidebar_page_link', lambda *_a, **_kw: None)
    monkeypatch.setattr(openrouter_client, 'gerar_imagem', no_spend)
    monkeypatch.setattr(openrouter_client, 'chamar_llm', no_spend)
    monkeypatch.setattr(openrouter_client, 'gerar_audio', no_spend)


def test_review_returns_only_to_exact_resume_state_preserving_other_open_work():
    unrelated = story('unrelated')
    resumed = story('resumed')
    resumed['cenas_imagem'] = [{'numero': 7, 'caminho_arquivo': 'old.png', 'aprovado': True}]
    session = {'state': deepcopy(unrelated), 'state_r': deepcopy(resumed)}
    ui.begin_emotional_review(session, 'state_r', 'pages/2_📚_Retomar_Livro.py')
    working = ui.review_book(session)
    approved = approve_book_emotional_map(working, reviewed=True, reviewer='Erica')
    ui.commit_reviewed_book(session, approved)
    require_book_emotional_map(session['state_r'])
    assert session['state'] == unrelated
    assert session['state_r']['cenas_imagem'] == resumed['cenas_imagem']
    assert 'emotional_book_binding' not in resumed


@pytest.mark.parametrize('change', ['identity', 'reference', 'story', 'dna', 'style'])
def test_review_rejects_replaced_homonym_or_changed_source(change):
    state = story()
    state['storage_path'] = 'fb://livros/colecao/exact-A.json'
    session = {'state_r': state}
    ui.begin_emotional_review(session, 'state_r', 'pages/2_📚_Retomar_Livro.py')
    approved = approve_book_emotional_map(ui.review_book(session), reviewed=True, reviewer='Erica')
    if change == 'identity': state['book_id'] = 'exact-B'
    elif change == 'reference': state['storage_path'] = 'fb://livros/colecao/exact-B.json'
    elif change == 'story': state['cenas_texto'][0]['texto'] = 'Outra história'
    elif change == 'dna': state['personagens']['Mel']['descricao_fixa'] = 'Outro DNA'
    else: state['style_dna_id'] = 'other-style'
    before = deepcopy(state)
    with pytest.raises(PermissionError):
        ui.commit_reviewed_book(session, approved)
    assert session['state_r'] == before


def test_merge_rejects_same_book_id_at_another_saved_reference():
    target = story()
    target['storage_path'] = 'fb://livros/colecao/first.json'
    other = deepcopy(target)
    other['storage_path'] = 'livros/colecao/second.json'
    approved = approve_book_emotional_map(other, reviewed=True, reviewer='Erica')
    with pytest.raises(PermissionError, match='referência'):
        ui.merge_emotional_approval(target, approved)


def test_rerun_grant_is_single_use_and_never_enters_saved_book():
    state = approve_book_emotional_map(story(private=True), reviewed=True, reviewer='Erica')
    original = deepcopy(state)
    session = {}
    ui.stage_emotional_action(session, state, action='illustrate', consent_confirmed=True)
    assert ui.take_emotional_action(session, state, action='illustrate') is True
    with pytest.raises(PermissionError): ui.take_emotional_action(session, state, action='illustrate')
    assert state == original
    assert '_emotional_pending_generation' not in state


@pytest.mark.parametrize('change', ['book', 'request', 'timeout', 'missing_consent'])
def test_rerun_grant_rejects_changed_context_and_is_burned(change, monkeypatch):
    state = approve_book_emotional_map(story(private=True), reviewed=True, reviewer='Erica')
    session = {}
    ui.stage_emotional_action(session, state, action='illustrate', consent_confirmed=True, request_context='scene-7')
    if change == 'book':
        state = approve_book_emotional_map(story('exact-B', private=True), reviewed=True, reviewer='Erica')
    elif change == 'timeout':
        session['_emotional_pending_generation']['created_at'] -= 121
    elif change == 'missing_consent':
        session['_emotional_pending_generation']['consent_confirmed'] = False
    request = 'scene-11' if change == 'request' else 'scene-7'
    with pytest.raises(PermissionError):
        ui.take_emotional_action(session, state, action='illustrate', request_context=request)
    assert '_emotional_pending_generation' not in session


def test_no_old_consent_or_emotional_approval_can_stage_an_action():
    state = approve_book_emotional_map(story(private=True), reviewed=True, reviewer='Erica')
    session = {}
    with pytest.raises(PermissionError): ui.stage_emotional_action(session, state, action='illustrate')
    assert not session


@pytest.mark.parametrize('missing', ['map', 'consent'])
def test_queue_missing_map_or_current_consent_pauses_before_attempt_or_provider(durable, missing):
    state = saved_approved(durable, private=True)
    if missing == 'map':
        state.pop('emotional_book_binding')
    job = queue.criar_job_ilustracoes(state)
    provider = Mock(return_value='unexpected.png')
    executor = queue.executor_ilustracao_story(provider, consent_confirmed=missing != 'consent', job_id=job['id'])
    blocked = queue.processar_lote(job['id'], executor, 2)
    assert blocked['status'] == 'pausado'
    assert blocked['itens'][0]['tentativas'] == 0
    assert blocked['itens'][1]['status'] == 'pendente'
    provider.assert_not_called()
    assert blocked['state'] == job['state']


def test_queue_valid_batch_preserves_completed_items_masters_history_and_resets_consent(durable):
    state = saved_approved(durable, private=True)
    state['cenas_imagem'] = [{'numero': 7, 'caminho_arquivo': 'old.png', 'origem': 'author', 'aprovado': True}]
    job = queue.criar_job_ilustracoes(state, somente_nao_aprovadas=False)
    job['itens'][0].update(status='concluido', tentativas=2, caminho_arquivo='old.png')
    job = queue.salvar_job(job)
    original_completed = deepcopy(job['itens'][0])
    original_masters = deepcopy(job['state']['personagens'])
    provider = Mock(return_value='candidate.png')
    executor = queue.executor_ilustracao_story(provider, consent_confirmed=True, job_id=job['id'],
        source_fingerprint=book_emotional_review_key(job['state']), max_items=1)
    done = queue.processar_proximo(job['id'], executor)
    assert done['status'] == 'concluido'
    assert done['itens'][0] == original_completed
    assert done['state']['personagens'] == original_masters
    assert done['state']['cenas_imagem'][0]['caminho_arquivo'] == 'old.png'
    assert done['state']['cenas_imagem'][1]['caminho_arquivo'] == 'candidate.png'
    assert done['itens'][1]['caminho_arquivo'] == 'candidate.png'
    provider.assert_called_once()
    assert 'consent_confirmed' not in done
    assert done['state']['real_experience'] == state['real_experience']
    with pytest.raises(PermissionError, match='já foi utilizada'):
        executor(done, done['itens'][1])
    assert provider.call_count == 1


@pytest.mark.parametrize('changed', ['story', 'dna', 'style', 'reference', 'approval'])
def test_queue_stale_durable_source_never_overwrites_book_or_spends(durable, changed):
    state = saved_approved(durable)
    job = queue.criar_job_ilustracoes(state)
    path = state['storage_path'].removeprefix('fb://')
    persisted = durable.get_json(path)
    if changed == 'story': persisted['cenas_texto'][0]['texto'] = 'Nova narrativa salva em outra tela.'
    elif changed == 'dna': persisted['personagens']['Mel']['descricao_fixa'] = 'DNA novo'
    elif changed == 'style': persisted['style_dna_id'] = 'style-new'
    elif changed == 'reference': persisted['personagens']['Mel']['imagem_referencia'] = 'other.png'
    else: persisted.pop('emotional_book_binding')
    durable.put_json(path, persisted)
    before = durable.get_bytes(path)
    provider = Mock()
    result = queue.processar_proximo(job['id'], queue.executor_ilustracao_story(provider, job_id=job['id']))
    assert result['status'] == 'pausado'
    assert result['itens'][0]['tentativas'] == 0
    assert durable.get_bytes(path) == before
    provider.assert_not_called()


def test_review_apply_keeps_queue_results_and_rejects_another_homonymous_book(durable):
    state = story()
    state['storage_path'] = armazenamento.salvar_livro(state)
    job = queue.criar_job_ilustracoes(state)
    job['itens'][0].update(status='concluido', tentativas=1, caminho_arquivo='preserved.png')
    job['state']['cenas_imagem'] = [{'numero': 7, 'caminho_arquivo': 'preserved.png', 'aprovado': True}]
    job = queue.salvar_job(job)
    baseline = book_emotional_review_key(job['state'])
    other = deepcopy(job['state'])
    other['book_id'] = 'exact-B'
    other['storage_path'] = 'fb://livros/colecao/other.json'
    bad = approve_book_emotional_map(other, reviewed=True, reviewer='Erica')
    with pytest.raises(PermissionError):
        queue.aplicar_mapa_emocional_job(job['id'], bad, expected_source_fingerprint=baseline)
    approved = approve_book_emotional_map(job['state'], reviewed=True, reviewer='Erica')
    applied = queue.aplicar_mapa_emocional_job(job['id'], approved, expected_source_fingerprint=baseline)
    assert applied['itens'] == job['itens']
    assert applied['state']['cenas_imagem'] == job['state']['cenas_imagem']
    require_book_emotional_map(applied['state'])
    assert applied['status'] == job['status']


def test_review_apply_rejects_changed_queue_snapshot_even_with_same_book_id(durable):
    job = queue.criar_job_ilustracoes(story())
    baseline = book_emotional_review_key(job['state'])
    approved = approve_book_emotional_map(job['state'], reviewed=True, reviewer='Erica')
    job['state']['cenas_texto'][0]['texto'] = 'Fonte alterada durante revisão.'
    queue.salvar_job(job)
    with pytest.raises(PermissionError, match='mudou durante a revisão'):
        queue.aplicar_mapa_emocional_job(job['id'], approved, expected_source_fingerprint=baseline)


def test_old_queue_gets_identity_only_on_explicit_review_and_no_automatic_approval(durable):
    state = story()
    state.pop('book_id')
    job = queue.criar_job('old', 'story_ilustracoes', [{'numero': 7}], state=state)
    assert 'book_id' not in queue.carregar_job(job['id'])['state']
    reviewed = queue.preparar_revisao_emocional_job(job['id'])
    assert reviewed['state']['book_id']
    assert 'emotional_book_binding' not in reviewed['state']
    assert reviewed['itens'] == job['itens']


def test_direct_stage_selector_opens_exact_homonyms_without_replacing_other_work(durable, monkeypatch):
    configure_app(monkeypatch)
    refs = []
    for mark in ('A', 'B'):
        state = story('exact-' + mark)
        state['cenas_texto'][0]['texto'] = 'Fonte exclusiva ' + mark
        refs.append(armazenamento.salvar_livro(state).removeprefix('fb://'))
    app = AppTest.from_file(ROOT / 'pages/4_🎯_Ir_Direto_para_Etapa.py')
    unrelated = story('unrelated')
    app.session_state['state'] = deepcopy(unrelated)
    app.run(timeout=20)
    assert not app.exception
    assert len(widget(app, 'selectbox', 'Livro').options) == 2
    widget(app, 'selectbox', 'Livro').set_value(refs[1]).run(timeout=20)
    assert not app.exception
    assert app.session_state['state_etapa']['cenas_texto'][0]['texto'] == 'Fonte exclusiva B'
    assert app.session_state['state_etapa']['storage_path'] == 'fb://' + refs[1]
    assert app.session_state['state'] == unrelated
    widget(app, 'selectbox', 'Qual agente rodar?').set_value('Ilustrador (personagens + cenas)').run(timeout=20)
    assert widget(app, 'button', '▶️ Rodar: Ilustrador (personagens + cenas)').disabled
    assert widget(app, 'button', 'Revisar emoção e cores desta história')


def test_direct_stage_personal_consent_is_current_and_consumed(durable, monkeypatch):
    configure_app(monkeypatch)
    state = saved_approved(durable, private=True)
    called = Mock(side_effect=lambda state, _provider, **_kw: state)
    monkeypatch.setattr(illustrator, 'ilustrador_node', called)
    app = AppTest.from_file(ROOT / 'pages/4_🎯_Ir_Direto_para_Etapa.py').run(timeout=20)
    app.session_state['state_etapa'] = state
    widget(app, 'selectbox', 'Qual agente rodar?').set_value('Ilustrador (personagens + cenas)').run(timeout=20)
    label = 'Tenho autorização para enviar os dados pessoais desta geração ao provedor de IA'
    run_label = '▶️ Rodar: Ilustrador (personagens + cenas)'
    assert widget(app, 'button', run_label).disabled
    widget(app, 'checkbox', label).check().run(timeout=20)
    assert not widget(app, 'button', run_label).disabled
    widget(app, 'button', run_label).click().run(timeout=20)
    assert not app.exception
    called.assert_called_once()
    assert called.call_args.kwargs['consent_confirmed'] is True
    app.run(timeout=20)
    assert not widget(app, 'checkbox', label).value
    assert widget(app, 'button', run_label).disabled


def test_queue_ui_cannot_process_before_map_or_consent(durable, monkeypatch):
    configure_app(monkeypatch)
    state = saved_approved(durable, private=True)
    job = queue.criar_job_ilustracoes(state)
    app = AppTest.from_file(ROOT / 'pages/12_🏭_Fila_de_Producao.py').run(timeout=20)
    assert not app.exception
    assert widget(app, 'button', '🎨 Processar próxima cena').disabled
    label = 'Tenho autorização para enviar os dados pessoais desta geração ao provedor de IA'
    widget(app, 'checkbox', label).check().run(timeout=20)
    assert not widget(app, 'button', '🎨 Processar próxima cena').disabled
    changed = queue.carregar_job(job['id'])
    changed['state'].pop('emotional_book_binding')
    queue.salvar_job(changed)
    app.run(timeout=20)
    assert widget(app, 'button', '🎨 Processar próxima cena').disabled
    assert widget(app, 'button', 'Revisar emoção e cores desta fila')
    assert queue.carregar_job(job['id'])['itens'][0]['tentativas'] == 0


def test_create_book_button_requires_review_and_one_use_rerun_consent(durable, monkeypatch):
    configure_app(monkeypatch)
    state = saved_approved(durable, private=True)
    failed_provider = Mock(side_effect=RuntimeError('Stopped after consuming the action'))
    monkeypatch.setattr(illustrator, 'ilustrador_node', failed_provider)
    app = AppTest.from_file(ROOT / 'pages/1_📖_Criar_do_Zero.py')
    app.session_state['state'] = state
    app.session_state['etapa'] = 'aprovar_personagens'
    app.run(timeout=20)
    assert not app.exception
    run_label = '🎬 Personagens aprovados — gerar ilustrações do livro'
    label = 'Tenho autorização para enviar os dados pessoais desta geração ao provedor de IA'
    assert widget(app, 'button', run_label).disabled
    widget(app, 'checkbox', label).check().run(timeout=20)
    assert not widget(app, 'button', run_label).disabled
    widget(app, 'button', run_label).click().run(timeout=20)
    failed_provider.assert_called_once()
    assert failed_provider.call_args.kwargs['consent_confirmed'] is True
    assert '_emotional_pending_generation' not in app.session_state
    # A failed automatic phase cannot silently reuse permission on the next rerun.
    app.run(timeout=20)
    assert not app.exception
    assert app.session_state['etapa'] == 'aprovar_personagens'
    assert failed_provider.call_count == 1
    app.run(timeout=20)
    assert not app.exception
    assert not widget(app, 'checkbox', label).value
    assert widget(app, 'button', run_label).disabled


def test_create_book_missing_map_disables_new_images_and_links_review(durable, monkeypatch):
    configure_app(monkeypatch)
    app = AppTest.from_file(ROOT / 'pages/1_📖_Criar_do_Zero.py')
    app.session_state['state'] = story()
    app.session_state['etapa'] = 'aprovar_personagens'
    app.run(timeout=20)
    assert not app.exception
    assert widget(app, 'button', '🎬 Personagens aprovados — gerar ilustrações do livro').disabled
    assert widget(app, 'button', 'Revisar emoção e cores desta história')


def test_resume_scene_consent_tracks_current_instruction_and_is_consumed(durable, monkeypatch, tmp_path):
    configure_app(monkeypatch)
    import retomar_fluxo
    monkeypatch.setattr(retomar_fluxo, 'aplicar_estilo', lambda: None)
    image = tmp_path / 'existing.png'
    Image.new('RGB', (16, 16), 'green').save(image)
    state = saved_approved(durable, private=True)
    state['cenas_imagem'] = [{'numero': 7, 'caminho_arquivo': str(image), 'aprovado': True}]
    generated = Mock(side_effect=lambda state, *_a, **_kw: state)
    monkeypatch.setattr(retomar_fluxo, 'gerar_cena_unica', generated)
    app = AppTest.from_file(ROOT / 'pages/2_📚_Retomar_Livro.py')
    app.session_state['state_r'] = state
    app.session_state['etapa_r'] = 'cenas'
    unrelated = story('another-open-work')
    app.session_state['state'] = deepcopy(unrelated)
    app.run(timeout=20)
    assert not app.exception
    by_key = lambda kind, key: next(item for item in getattr(app, kind) if item.key == key)
    assert by_key('button', 'r_gen_scene_7').disabled
    consents = [item for item in app.checkbox if item.label == 'Tenho autorização para enviar os dados pessoais desta geração ao provedor de IA']
    assert len(consents) == 2
    consents[0].check().run(timeout=20)
    assert not by_key('button', 'r_gen_scene_7').disabled
    by_key('text_area', 'r_scene_prompt_7').set_value('Mude somente a câmera.').run(timeout=20)
    assert by_key('button', 'r_gen_scene_7').disabled
    consents = [item for item in app.checkbox if item.label == 'Tenho autorização para enviar os dados pessoais desta geração ao provedor de IA']
    consents[0].check().run(timeout=20)
    by_key('button', 'r_gen_scene_7').click().run(timeout=20)
    assert not app.exception
    generated.assert_called_once()
    assert generated.call_args.args[1] == 7
    assert generated.call_args.args[3] == 'Mude somente a câmera.'
    assert generated.call_args.kwargs['consent_confirmed'] is True
    assert by_key('button', 'r_gen_scene_7').disabled
    assert app.session_state['state'] == unrelated


def test_queue_review_apply_button_updates_exact_snapshot_without_touching_other_job(durable, monkeypatch):
    configure_app(monkeypatch)
    job = queue.criar_job_ilustracoes(story('exact-A'))
    other = queue.criar_job_ilustracoes(story('exact-B'))
    original_other = queue.carregar_job(other['id'])
    approved = approve_book_emotional_map(job['state'], reviewed=True, reviewer='Erica')
    app = AppTest.from_file(ROOT / 'pages/12_🏭_Fila_de_Producao.py')
    key = 'queue_emotional_review_' + job['id']
    app.session_state[key] = approved
    app.session_state[key + '_baseline'] = book_emotional_review_key(job['state'])
    app.run(timeout=20)
    assert not app.exception
    next(item for item in app.button if item.key == 'apply_review_' + job['id']).click().run(timeout=20)
    assert not app.exception
    require_book_emotional_map(queue.carregar_job(job['id'])['state'])
    assert queue.carregar_job(other['id']) == original_other

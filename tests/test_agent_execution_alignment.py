"""Execute every declared job with local deterministic inputs and provider spies.

These tests prove dispatch, context and result handling. They do not certify the
quality of provider content, production credentials or deployed integrations.
"""
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock
import hashlib

import pytest
import agent_skills

ROOT = Path(__file__).resolve().parents[1]

# Deliberately enumerate real jobs: a new registry entry must acquire a behavior
# test instead of inheriting a green result from its metadata alone.
BEHAVIOR_ROLES = (
    'idea_generator', 'theme_curator', 'storyteller', 'story_editor', 'story_reviewer',
    'character_creator', 'photo_to_character', 'character_variations', 'illustrator',
    'coloring_idea_generator', 'line_art_specialist', 'coloring_activity_creator',
    'coloring_layout', 'sales_synopsis', 'market_keywords', 'market_categories',
    'marketing_launch', 'cover_specialist', 'diagrammer', 'dedication',
    'translator_localizer', 'audiobook_director', 'narrator', 'pedagogical_editor',
    'scene_director', 'saas_automation_engineer', 'deep_code_review_engineer',
    'ai_governance', 'data_governance', 'it_governance', 'cybersecurity',
)


def book():
    return {
        'titulo': 'Lia e a semente', 'colecao': 'Coleção de Teste', 'faixa_etaria': '6-8',
        'emocao_central': 'esperanca', 'aprendizado_cristao': 'Cuidar com paciência.',
        'licao_final': 'Cuidar também é esperar.', 'versiculo_referencia': 'Salmo 1:1',
        'sinopse_poetica': 'Lia cuida de uma semente.', 'sinopse_vendas_curta': 'Uma aventura sobre cuidado.',
        '_entrada_tema_livre': 'Lia cuida de uma semente.',
        'cenas_texto': [{'numero': i, 'texto': f'Lia esperou junto ao vaso {i}.',
                         'emocao': 'esperanca', 'personagem_principal': 'lia',
                         'contexto_visual': 'jardim', 'figurino': 'vestido amarelo'} for i in range(1, 4)],
        'personagens': {'LIA': {'nome': 'Lia', 'papel': 'protagonista', 'descricao_fixa': 'Olhos verdes brilhantes e cabelo castanho.',
                               'imagem_referencia': 'approved-original-master.png', 'origem_referencia': 'enviada_pela_autora',
                               'aparencia_aprovada': True}},
    }


def _script(state):
    return [{'numero': c['numero'], 'texto_narrado': '[voz suave] ' + c['texto']} for c in state['cenas_texto']]


def _scene_ideas():
    return [{'id': letter, 'titulo': 'Cena ' + letter, 'cenario': 'Jardim ' + letter,
             'acao': 'Lia observa o vaso', 'poses': {'Lia': 'ajoelhada'}, 'emocao': 'esperanca',
             'psicologia_cores': 'Azul e dourado no ambiente', 'iluminacao': 'suave',
             'camera': 'Plano ' + letter, 'por_que_funciona': 'Mostra a espera.'} for letter in 'ABC']


@pytest.fixture(autouse=True)
def isolate_checkpoints(monkeypatch):
    for module in ('agents.ilustrador', 'agents.atividades_colorir', 'agents.audiobook', 'agents.curador_tema'):
        monkeypatch.setattr(module + '.persist_generation_snapshot', lambda *_args, **_kwargs: 'fb://book.json')


def test_every_registered_job_has_an_explicit_behavior_case():
    assert set(BEHAVIOR_ROLES) == set(agent_skills.AGENT_PROFILES)


@pytest.mark.parametrize('role', BEHAVIOR_ROLES)
def test_each_job_executes_its_real_entrypoint_and_returns_reviewable_output(role, monkeypatch, complete_editorial_extras):
    state = book()
    originals = deepcopy(state['personagens'])
    provider = Mock()
    if role == 'idea_generator':
        from agents.gerador_ideias import gerador_ideias_node
        provider.return_value = [{'titulo_sugerido': 'Uma semente', 'situacao': 'Esperar o broto', 'emocao_central': 'esperanca', 'pista_licao': 'Paciência'}]
        result = gerador_ideias_node(1, [], provider, faixa_etaria='6-8')
        assert result[0]['situacao'] == 'Esperar o broto'
    elif role == 'theme_curator':
        from agents.curador_tema import curador_tema_node
        state.pop('titulo'); state.pop('emocao_central'); state.pop('versiculo_referencia'); state.pop('aprendizado_cristao')
        provider.return_value = {'titulo_sugerido': 'Uma semente', 'emocao_central': 'esperanca', 'versiculo_referencia': 'Salmo 1:1', 'aprendizado_cristao': 'Paciência', 'justificativa': 'A espera.'}
        result = curador_tema_node(state, provider)
        assert result['bible_reference_candidate']['status'] == 'candidate_unverified'
    elif role == 'storyteller':
        from agents.roteirista import roteirista_node
        provider.return_value = {'sinopse_poetica': 'Jornada.', 'cenas_texto': deepcopy(state['cenas_texto']), 'licao_final': state['licao_final']}
        result = roteirista_node(state, provider)
        assert result['cenas_texto'][0]['texto'] == 'Lia esperou junto ao vaso 1.'
        assert result['revisao_aprovada'] is False
    elif role == 'story_editor':
        from agents.editor_historia import editar_cena
        provider.return_value = {'texto': 'Lia esperou com carinho.'}
        result = editar_cena(state['cenas_texto'][0], 'Ajustar ritmo.', state, provider)
        assert result['numero'] == 1 and result['texto'] == provider.return_value['texto']
        assert state['cenas_texto'][0]['texto'] != result['texto']
    elif role == 'story_reviewer':
        from agents.revisor import revisor_node
        provider.return_value = {'status': 'APROVADO', 'notas': []}
        assert revisor_node(state, provider)['revisao_aprovada'] is True
    elif role == 'character_creator':
        from agents.criador_personagem import criar_personagem_a_partir_de_ideia
        provider.return_value = {'nome_sugerido': 'Lia', 'descricao_fixa': 'Olhos verdes brilhantes.'}
        result = criar_personagem_a_partir_de_ideia('Menina curiosa', 'protagonista', provider)
        assert result['descricao_fixa'] == 'Olhos verdes brilhantes.'
    elif role == 'photo_to_character':
        from agents.foto_para_personagem import gerar_personagem_a_partir_de_foto
        provider.return_value = 'photo-candidate.png'
        result = gerar_personagem_a_partir_de_foto('authorized-photo.png', 'Lia', 'protagonista', provider, consent_confirmed=True)
        assert result['imagem_referencia'] == 'photo-candidate.png'
        assert provider.call_args.kwargs['imagem_base'] == 'authorized-photo.png'
    elif role == 'character_variations':
        from agents.personagens_variacoes import gerar_variacao
        provider.return_value = 'candidate-variation.png'
        result = gerar_variacao(deepcopy(state['personagens']['LIA']), provider, 'Pose sentada.')
        assert result['imagem_referencia'] == originals['LIA']['imagem_referencia']
        assert result['variacoes_visuais'][-1]['caminho_arquivo'] == 'candidate-variation.png'
        assert not result['aparencia_aprovada']
    elif role == 'illustrator':
        from emotional_visual_binding import approve_book_emotional_map
        state = approve_book_emotional_map(state, reviewed=True, reviewer='Reviewer offline')
        from agents.ilustrador import ilustrador_node
        provider.return_value = 'candidate-scene.png'
        result = ilustrador_node(state, provider)
        assert len(result['cenas_imagem']) == 3 and not result['cenas_imagem'][0]['aprovado']
        assert all(c.kwargs['imagem_base'] == 'approved-original-master.png' for c in provider.call_args_list)
    elif role == 'coloring_idea_generator':
        from agents.gerador_ideias_colorir import gerador_ideias_colorir_node
        provider.return_value = [{'titulo_sugerido': 'Jardim', 'tema_geral': 'Flores', 'precisa_codigo_sexo': False, 'sugestoes_paginas': ['Vaso com flor']}]
        assert gerador_ideias_colorir_node(1, [], provider)[0]['sugestoes_paginas'] == ['Vaso com flor']
    elif role == 'line_art_specialist':
        from agents.line_art_colorir import gerar_pagina_colorir
        provider.return_value = 'line-art.png'
        assert gerar_pagina_colorir('Lia', 'pessoa', 'no jardim', provider, imagem_referencia='approved-original-master.png') == 'line-art.png'
        assert provider.call_args.kwargs['imagem_base'] == 'approved-original-master.png'
    elif role == 'coloring_activity_creator':
        from agents.atividades_colorir import atividades_colorir_node
        provider.return_value = 'activity-line-art.png'
        assert len(atividades_colorir_node(state, provider)['paginas_colorir']) == 3
        assert all(c.kwargs['imagem_base'] == 'approved-original-master.png' for c in provider.call_args_list)
    elif role == 'coloring_layout':
        from agents.diagramador_colorir import diagramador_colorir_node
        result = diagramador_colorir_node({'paginas': [{'caminho_arquivo': f'page-{i}.png'} for i in range(12)]})
        assert result['paginas_fisicas_total'] == 26
        assert sum(p['tipo'] == 'verso_em_branco' for p in result['layout_paginas']) == 12
    elif role == 'sales_synopsis':
        from agents.sinopse import sinopse_node
        provider.return_value = {'sinopse_vendas_curta': 'Aventura de Lia.', 'sinopse_contracapa': 'Lia descobre a espera.'}
        assert sinopse_node(state, provider)['sinopse_contracapa'] == 'Lia descobre a espera.'
    elif role in ('market_keywords', 'market_categories'):
        module = import_module('agents.pesquisa_mercado')
        provider.return_value = [f'Frase {i}' for i in range(7 if role == 'market_keywords' else 3)]
        result = getattr(module, 'pesquisa_palavras_chave_node' if role == 'market_keywords' else 'pesquisa_categorias_node')(state, provider)
        assert len(result['palavras_chave_kdp' if role == 'market_keywords' else 'categorias_sugeridas']) == len(provider.return_value)
        assert result['market_suggestions_provenance']['mode'] == 'model_inference_only'
    elif role == 'marketing_launch':
        from agents.marketing import marketing_lancamento_node
        provider.return_value = {'legenda_instagram': 'Uma aventura.', 'descricao_pinterest': 'Livro sobre espera.', 'email_lancamento': 'Conheça a obra.', 'pedido_avaliacao': 'Compartilhe sua avaliação honesta.'}
        assert marketing_lancamento_node(state, provider)['material_lancamento'] == provider.return_value
    elif role == 'cover_specialist':
        from agents.capa import gerar_artes_capa
        provider.side_effect = ['front-art.png', 'back-art.png']
        result = gerar_artes_capa(state, provider)
        assert (result['arte_capa_frontal'], result['arte_contracapa']) == ('front-art.png', 'back-art.png')
    elif role == 'diagrammer':
        from agents.diagramador import diagramador_node
        result = diagramador_node(state)
        assert result['layout_paginas'][0]['tipo'] == 'boas_vindas'
        assert result['layout_paginas'][-1]['pagina'] % 2 == 0
        assert 'preflight_impressao' in result
    elif role == 'dedication':
        from agents.dedicatoria import dedicatoria_node
        provider.return_value = {'texto': 'A quem cuida com carinho.'}
        assert dedicatoria_node(state, provider)['dedicatoria_texto'] == provider.return_value['texto']
    elif role == 'translator_localizer':
        from agents.tradutor import tradutor_node
        state['idiomas_alvo'] = ['en']
        provider.return_value = {'titulo': 'Lia and the seed', 'cenas_texto': [{'numero': i, 'texto': f'Lia waited near pot {i}.'} for i in range(1, 4)]}
        result = tradutor_node(state, provider)
        assert result['traducoes']['en-US']['cenas_texto'][0]['texto'] == 'Lia waited near pot 1.'
        assert result['cenas_texto'][0]['texto'] == 'Lia esperou junto ao vaso 1.'
        assert not result['traducoes']['en-US']['bible_ai_translation_allowed']
    elif role == 'audiobook_director':
        from agents.audiobook import audiobook_node
        provider.return_value = {'roteiro': _script(state)}
        assert audiobook_node(state, provider)['roteiro_audiobook'] == _script(state)
    elif role == 'narrator':
        from agents.audiobook import narracao_node
        state['roteiro_audiobook'] = _script(state)
        provider.return_value = 'narration.wav'
        result = narracao_node(state, provider)
        assert len(result['audio_gerado']) == 3 and all(item['texto_fingerprint'] for item in result['audio_gerado'])
        assert provider.call_count == 3
        assert provider.call_args_list[0].kwargs['texto_com_marcacoes'] == _script(state)[0]['texto_narrado']
    elif role == 'pedagogical_editor':
        from agents.complementos_editoriais import gerar_complementos_editoriais, aplicar_complementos
        provider.return_value = complete_editorial_extras(reference=state['versiculo_referencia'])
        result = aplicar_complementos(state, gerar_complementos_editoriais(state, provider))
        assert result['ficha_pedagogica']['versiculo_referencia'] == 'Salmo 1:1'
        assert len(result['pais_educadores']['perguntas']) == 3
    elif role == 'scene_director':
        import character_guide
        provider.return_value = {'ideas': _scene_ideas()}
        result = character_guide.suggest_scene_concepts(state['cenas_texto'][0]['texto'], [{'nome': 'Lia', 'dna': {'campos_bloqueados': {'olhos': 'verdes'}}}], project_context=state, text_generator=provider)
        assert [item['id'] for item in result] == list('ABC')
    elif role == 'saas_automation_engineer':
        from agents.engenheiro_saas_automacao import run_diagnostic
        result = run_diagnostic('Auditar os agentes.')
        assert result['role_id'] == role and result['audit']['stats']['python_files'] > 100
        assert not result['code_modified'] and not result['tests_executed'] and not result['deployed']
    elif role == 'deep_code_review_engineer':
        from agents.engenheiro_code_review_profundo import review_sources
        provider.return_value = {'summary': 'Revisar contrato.', 'findings': [{'severity': 'P2', 'module': 'sample.py', 'line': 1, 'evidence': 'return 1', 'problem': 'Contrato incompleto.', 'proposed_fix': 'Verificar retorno.', 'regression_test': 'Cobrir o caso.'}], 'limitations': ['Sem execução.']}
        result = review_sources('Revisar', {'sample.py': 'def sample(): return 1'}, provider)
        assert result['findings'][0]['evidence'] == 'return 1' and not result['code_modified']
    else:
        module_name = {'ai_governance': 'governanca_ia', 'data_governance': 'governanca_dados', 'it_governance': 'governanca_ti', 'cybersecurity': 'ciberseguranca'}[role]
        result = import_module('agents.' + module_name).run_diagnostic(root=ROOT, state=state, context={})
        assert result['role_id'] == role and result['findings']
        assert any(item['status'] in ('UNKNOWN', 'WARN') for item in result['findings'])
        assert state['cenas_texto'][0]['texto'] not in repr(result)
    assert state['personagens'] == originals
    if role not in ('coloring_layout', 'diagrammer', 'saas_automation_engineer', 'ai_governance', 'data_governance', 'it_governance', 'cybersecurity', 'narrator'):
        assert provider.call_count >= 1
        # A profile constant is not evidence: inspect the actual outgoing context.
        assert agent_skills.get_agent_profile(role)['name'] in str(provider.call_args_list)


@pytest.mark.parametrize('response', [{}, [], None, {'cenas_texto': []}, {'cenas_texto': [{'numero': 1, 'texto': ' '}]},
                                      {'cenas_texto': [{'numero': 1, 'texto': 'Nova cena.'}], 'licao_final': ''}])
def test_failed_story_output_never_discards_an_approved_version(response):
    from agents.roteirista import roteirista_node
    state = book(); state['revisao_aprovada'] = True
    before = deepcopy(state)
    with pytest.raises(ValueError, match='preservada'):
        roteirista_node(state, Mock(return_value=response))
    assert state == before


@pytest.mark.parametrize('response', [{'status': 'APROVADO', 'notas': ['Corrigir continuidade.']},
                                      {'status': 'APROVADO', 'notas': 'sem notas'}, {'status': 'APROVADO'}, None])
def test_reviewer_cannot_approve_a_malformed_or_contradictory_report(response):
    from agents.revisor import revisor_node
    result = revisor_node(book(), Mock(return_value=response))
    assert not result['revisao_aprovada'] and result['notas_revisor']


@pytest.mark.parametrize('response', [{}, {'roteiro': []}, {'roteiro': [{'numero': 1, 'texto_narrado': 'Texto inventado.'}]}])
def test_audiobook_does_not_replace_a_script_with_empty_or_rewritten_content(response):
    from agents.audiobook import audiobook_node
    state = book(); state['roteiro_audiobook'] = _script(state)
    before = deepcopy(state)
    with pytest.raises(ValueError): audiobook_node(state, Mock(return_value=response))
    assert state == before


def test_photo_requires_specific_consent_before_any_provider_call():
    from agents.foto_para_personagem import gerar_personagem_a_partir_de_foto
    provider = Mock()
    with pytest.raises(PermissionError):
        gerar_personagem_a_partir_de_foto('private-photo.png', 'Lia', 'protagonista', provider)
    provider.assert_not_called()


def test_narrator_checkpoints_success_and_resumes_without_paying_twice(monkeypatch):
    import agents.audiobook as audio
    state = book(); state['roteiro_audiobook'] = _script(state)
    checkpoints = []
    monkeypatch.setattr(audio, 'persist_generation_snapshot', lambda s, **k: checkpoints.append(deepcopy(s)))
    first = Mock(side_effect=['one.wav', RuntimeError('provider unavailable')])
    with pytest.raises(RuntimeError): audio.narracao_node(state, first)
    assert len(state['audio_gerado']) == len(checkpoints) == 1
    retry = Mock(side_effect=['two.wav', 'three.wav'])
    audio.narracao_node(state, retry)
    assert retry.call_count == 2 and len(state['audio_gerado']) == 3
    assert state['audio_gerado'][0]['caminho_arquivo'] == 'one.wav'
    audio.narracao_node(state, Mock(side_effect=AssertionError('Already completed')))


def test_narrator_stops_after_a_checkpoint_failure_before_another_paid_call(monkeypatch):
    import agents.audiobook as audio
    state = book(); state['roteiro_audiobook'] = _script(state)
    monkeypatch.setattr(audio, 'persist_generation_snapshot', Mock(side_effect=RuntimeError('storage unavailable')))
    provider = Mock(return_value='first.wav')
    with pytest.raises(RuntimeError, match='storage unavailable'): audio.narracao_node(state, provider)
    provider.assert_called_once()
    assert state['audio_gerado'][0]['caminho_arquivo'] == 'first.wav'


def test_narrator_refuses_untraceable_old_audio_instead_of_overwriting_it():
    from agents.audiobook import narracao_node
    state = book(); state['roteiro_audiobook'] = _script(state)
    state['audio_gerado'] = [{'numero': 1, 'caminho_arquivo': 'legacy.wav'}]
    before = deepcopy(state); provider = Mock()
    with pytest.raises(ValueError, match='rastreabilidade'): narracao_node(state, provider)
    assert state == before
    provider.assert_not_called()


def test_coloring_activities_keep_original_master_and_partial_progress(monkeypatch):
    import agents.atividades_colorir as coloring
    state = book(); before = deepcopy(state['personagens']); checkpoints = []
    monkeypatch.setattr(coloring, 'persist_generation_snapshot', lambda s, **k: checkpoints.append(deepcopy(s)))
    provider = Mock(side_effect=['first.png', RuntimeError('image unavailable')])
    with pytest.raises(RuntimeError): coloring.atividades_colorir_node(state, provider)
    assert state['personagens'] == before and len(state['paginas_colorir']) == 1
    assert provider.call_args_list[0].kwargs['imagem_base'] == 'approved-original-master.png'
    assert 'Olhos verdes brilhantes' in provider.call_args_list[0].kwargs['prompt']
    assert len(checkpoints) == 1
    retry = Mock(return_value='resumed.png')
    coloring.atividades_colorir_node(state, retry)
    assert retry.call_count == 2 and state['paginas_colorir'][0]['caminho_arquivo'] == 'first.png'


def test_wrong_character_name_blocks_generic_activity_images_before_provider():
    from agents.atividades_colorir import atividades_colorir_node
    state = book(); state['cenas_texto'][-1]['personagem_principal'] = 'Unknown'; provider = Mock()
    with pytest.raises(ValueError, match='DNA'): atividades_colorir_node(state, provider)
    provider.assert_not_called()


@pytest.mark.parametrize('role,function_name', [('narrator', 'narracao_node'), ('coloring_layout', 'diagramador_colorir_node')])
def test_deterministic_tool_roles_enforce_their_real_skill_gate(role, function_name, monkeypatch):
    profile = deepcopy(agent_skills.AGENT_PROFILES[role]); profile['skills'] = []
    monkeypatch.setitem(agent_skills.AGENT_PROFILES, role, profile)
    if role == 'narrator':
        from agents.audiobook import narracao_node
        provider = Mock(); state = book(); state['roteiro_audiobook'] = _script(state)
        with pytest.raises(agent_skills.SkillReadinessError): narracao_node(state, provider)
        provider.assert_not_called()
    else:
        from agents.diagramador_colorir import diagramador_colorir_node
        state = {'paginas': []}
        with pytest.raises(agent_skills.SkillReadinessError): diagramador_colorir_node(state)
        assert state == {'paginas': []}


@pytest.mark.parametrize('module_name,function_name,keys', [
    ('sinopse', 'sinopse_node', ('sinopse_vendas_curta', 'sinopse_contracapa')),
    ('marketing', 'marketing_lancamento_node', ('material_lancamento',)),
    ('dedicatoria', 'dedicatoria_node', ('dedicatoria_texto',)),
    ('pesquisa_mercado', 'pesquisa_palavras_chave_node', ('palavras_chave_kdp',)),
    ('pesquisa_mercado', 'pesquisa_categorias_node', ('categorias_sugeridas',)),
])
def test_invalid_agent_results_do_not_erase_previous_editorial_work(module_name, function_name, keys):
    state = book()
    for key in keys: state[key] = {'approved': 'Conteúdo anterior.'} if key == 'material_lancamento' else ['Conteúdo anterior.'] if key in ('palavras_chave_kdp', 'categorias_sugeridas') else 'Conteúdo anterior.'
    before = deepcopy(state)
    provider = Mock(return_value={})
    with pytest.raises(ValueError): getattr(import_module('agents.' + module_name), function_name)(state, provider)
    for key in keys: assert state[key] == before[key]
    provider.assert_called_once()


def test_editor_cannot_report_an_empty_reply_as_a_successful_edit():
    from agents.editor_historia import editar_cena
    state = book(); before = deepcopy(state)
    with pytest.raises(ValueError): editar_cena(state['cenas_texto'][0], 'Melhore o ritmo.', state, Mock(return_value={}))
    assert state == before


def test_selected_missing_character_variation_never_falls_back_to_a_different_master():
    from agents.personagens_variacoes import gerar_variacao
    character = book()['personagens']['LIA']; original_master = character['imagem_referencia']; provider = Mock()
    with pytest.raises(ValueError, match='variação-base'): gerar_variacao(character, provider, variacao_base_id='missing-version')
    assert character['imagem_referencia'] == original_master
    provider.assert_not_called()


def test_empty_visual_result_does_not_become_a_character_variation():
    from agents.personagens_variacoes import gerar_variacao, garantir_variacao_inicial
    character = book()['personagens']['LIA']; garantir_variacao_inicial(character)
    before = deepcopy(character)
    with pytest.raises(ValueError, match='Master'): gerar_variacao(character, Mock(return_value=''))
    assert character == before


def test_coloring_cover_uses_the_layout_page_count_instead_of_an_approximation(monkeypatch):
    import agents.line_art_colorir as coloring
    from kdp_rules import calcular_dimensoes_capa_fisica
    state = {'titulo': 'Jardim', 'paginas': [{'nome': f'Vaso {i}', 'categoria': 'objeto', 'caminho_arquivo': f'page-{i}.png'} for i in range(12)]}
    monkeypatch.setattr(coloring, 'carregar_asset_marca', lambda *a: None)
    monkeypatch.setattr(coloring, 'aplicar_faixa_colecao', lambda path, *a: path)
    provider = Mock(return_value='cover-art.png')
    result = coloring.gerar_capa_fisica_wrap_colorir(state, provider)
    assert state['paginas_fisicas_total'] == 26
    assert result['largura_lombada_in'] == calcular_dimensoes_capa_fisica(8.5, 8.5, 26)['largura_lombada_in']
    provider.assert_called_once()


def test_narrator_validates_all_existing_audio_before_the_first_paid_call():
    from agents.audiobook import narracao_node
    state = book(); state['roteiro_audiobook'] = _script(state)
    state['audio_gerado'] = [{'numero': 3, 'caminho_arquivo': 'legacy-third.wav'}]
    provider = Mock()
    with pytest.raises(ValueError, match='rastreabilidade'): narracao_node(state, provider)
    provider.assert_not_called()

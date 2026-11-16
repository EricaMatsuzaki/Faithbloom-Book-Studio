"""Exercise the compiled graph: review cannot consume a recursion budget forever."""
from copy import deepcopy

import pytest

import graph


def _compile(monkeypatch, outcomes, *, limit=2):
    events = []
    monkeypatch.setattr(graph, 'curador_tema_node', lambda state, llm: state)

    def story(state, llm):
        events.append('story')
        state['cenas_texto'] = [{'numero': 1, 'texto': 'Mel esperou.', 'emocao': 'esperanca'}]
        return state

    def review(state, llm):
        events.append('review')
        state['revisao_aprovada'] = next(outcomes)
        state['notas_revisor'] = [] if state['revisao_aprovada'] else ['Cena 1: revisar o conflito.']
        return state

    monkeypatch.setattr(graph, 'roteirista_node', story)
    monkeypatch.setattr(graph, 'revisor_node', review)
    import emotional_visual_binding
    monkeypatch.setattr(emotional_visual_binding, 'require_book_emotional_map', lambda state: {'approved': True}, raising=False)
    import generation_autosave
    checkpoints = []
    monkeypatch.setattr(generation_autosave, 'persist_generation_snapshot', lambda state, **kw: checkpoints.append(deepcopy(state)))
    stages = ['_complementos_node', 'ilustrador_node', 'atividades_colorir_node', 'audiobook_node', 'narracao_node', 'dedicatoria_node', 'tradutor_node', 'sinopse_node', 'pesquisa_palavras_chave_node', 'pesquisa_categorias_node', 'diagramador_node', 'capa_node', 'marketing_lancamento_node']
    for stage in stages:
        def node(state, *args, _stage=stage):
            events.append(_stage)
            return state
        monkeypatch.setattr(graph, stage, node)
    return graph.construir_grafo(None, None, None, max_editorial_reviews=limit), events, checkpoints


def test_repeated_rejection_stops_with_draft_and_notes_before_any_image_or_audio(monkeypatch):
    pipeline, events, checkpoints = _compile(monkeypatch, iter([False, False]))
    result = pipeline.invoke({'titulo': 'Mel'})
    assert events == ['story', 'review', 'story', 'review']
    assert result['pipeline_status'] == 'awaiting_human_review'
    assert result['editorial_review_attempts'] == 2
    assert result['cenas_texto'][0]['texto'] == 'Mel esperou.'
    assert result['notas_revisor'] == ['Cena 1: revisar o conflito.']
    assert len(checkpoints) == 2


def test_approval_continues_through_actual_graph_once(monkeypatch):
    pipeline, events, checkpoints = _compile(monkeypatch, iter([False, True]))
    result = pipeline.invoke({'titulo': 'Mel'})
    assert events[:4] == ['story', 'review', 'story', 'review']
    assert events.count('ilustrador_node') == events.count('narracao_node') == 1
    assert events[-1] == 'marketing_lancamento_node'
    assert result['revisao_aprovada'] is True
    assert len(checkpoints) == 2


@pytest.mark.parametrize('limit', [0, -1, 6, 2.5, True, '2'])
def test_invalid_review_budget_rejected_before_any_stage(limit):
    with pytest.raises(ValueError, match='revisões'):
        graph.construir_grafo(None, None, None, max_editorial_reviews=limit)


def test_release_uses_registry_count_not_a_historical_constant(monkeypatch):
    import agent_skills
    import qa_release
    profiles = dict(agent_skills.AGENT_PROFILES)
    profiles['new_role_for_fixture'] = {}
    monkeypatch.setattr(agent_skills, 'AGENT_PROFILES', profiles)
    monkeypatch.setattr(agent_skills, 'validate_registry', lambda: {'ok': True, 'role_count': len(profiles), 'module_count': 29})
    result = qa_release.verificar_refinamento21()[0]
    assert result['ok']
    assert str(len(profiles)) in str(result)


def test_approved_editorial_text_pauses_before_any_image_if_emotional_map_is_missing(monkeypatch):
    pipeline, events, checkpoints = _compile(monkeypatch, iter([True]))
    import emotional_visual_binding
    def missing(_state):
        raise PermissionError('Aprove o mapa emocional.')
    monkeypatch.setattr(emotional_visual_binding, 'require_book_emotional_map', missing)
    result = pipeline.invoke({'titulo': 'Mel'})
    assert events == ['story', 'review']
    assert result['pipeline_status'] == 'awaiting_emotional_review'
    assert checkpoints[-1]['cenas_texto'][0]['texto'] == 'Mel esperou.'


def test_explicit_resume_preserves_reviewed_draft_and_does_not_regenerate_story(monkeypatch):
    _unused, events, _checkpoints = _compile(monkeypatch, iter([]))
    pipeline = graph.construir_grafo(None, None, None, resume_after_emotional_review=True)
    draft = {'titulo': 'Mel', 'revisao_aprovada': True, 'cenas_texto': [{'numero': 1, 'texto': 'Texto aprovado intacto.'}]}
    result = pipeline.invoke(draft)
    assert 'story' not in events and 'review' not in events
    assert events[0] == '_complementos_node'
    assert result['cenas_texto'] == draft['cenas_texto']

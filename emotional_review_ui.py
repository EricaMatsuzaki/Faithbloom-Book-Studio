"""Exact-book emotional review handoff and action-scoped consent for legacy UIs."""
from __future__ import annotations

from copy import deepcopy
import time
import uuid

from emotional_visual_binding import (
    EMOTIONAL_SCENE_FIELDS, book_emotional_review_key, fingerprint,
    require_book_emotional_map,
)
from governance_callbacks import source_uses_personal_data

CONTEXT = '_emotional_review_context'
REVIEW_BOOK = 'emotional_review_book'
_ALLOWED_PAGES = {'pages/1_📖_Criar_do_Zero.py', 'pages/2_📚_Retomar_Livro.py',
                  'pages/4_🎯_Ir_Direto_para_Etapa.py', 'pages/12_🏭_Fila_de_Producao.py'}


def begin_emotional_review(session, state_key: str, return_page: str) -> None:
    if return_page not in _ALLOWED_PAGES:
        raise ValueError('Destino de revisão desconhecido.')
    state = session.get(state_key)
    if not isinstance(state, dict) or not state.get('cenas_texto'):
        raise ValueError('Abra uma história antes de revisar o mapa emocional.')
    # Identity is not an approval. It prevents replacing an unsaved draft with
    # a different draft having the same title/content while review is open.
    if not state.get('book_id'):
        state['book_id'] = uuid.uuid4().hex
        session[state_key] = state
    session[CONTEXT] = {'state_key': state_key, 'return_page': return_page,
                        'book_id': state['book_id'],
                        'source_fingerprint': book_emotional_review_key(state)}
    session[REVIEW_BOOK] = deepcopy(state)


def _target(session):
    context = session.get(CONTEXT)
    if not context:
        return None
    if context.get('return_page') not in _ALLOWED_PAGES:
        raise PermissionError('O destino da revisão não corresponde ao livro aberto.')
    target = session.get(context.get('state_key'))
    if (not isinstance(target, dict) or target.get('book_id') != context.get('book_id')
            or book_emotional_review_key(target) != context.get('source_fingerprint')):
        raise PermissionError('O livro de origem mudou durante a revisão. Abra o mapa novamente a partir desse livro.')
    return target


def review_book(session):
    if not session.get(CONTEXT):
        return session.get('state')
    target = _target(session)
    reviewed = session.get(REVIEW_BOOK)
    if not isinstance(reviewed, dict) or reviewed.get('book_id') != target.get('book_id'):
        raise PermissionError('A revisão não pertence ao livro de origem.')
    return reviewed


def merge_emotional_approval(target: dict, approved: dict) -> dict:
    require_book_emotional_map(approved)
    if target.get('book_id') and target.get('book_id') != approved.get('book_id'):
        raise PermissionError('O mapa aprovado pertence a outra obra.')
    target_ref = str(target.get('storage_path') or '').removeprefix('fb://')
    approved_ref = str(approved.get('storage_path') or '').removeprefix('fb://')
    if target_ref and approved_ref and target_ref != approved_ref:
        raise PermissionError('O mapa aprovado pertence a outra referência de livro salvo.')
    out = deepcopy(target)
    for key in ('book_id', 'storage_path', 'mapa_emocional', 'paleta_emocional_preset',
                'emotional_book_binding', 'metadata_emocional_confirmada'):
        if key in approved:
            out[key] = deepcopy(approved[key])
    by_number = {row['numero']: row for row in approved.get('cenas_texto', [])}
    if set(by_number) != {row['numero'] for row in out.get('cenas_texto', [])}:
        raise PermissionError('As cenas aprovadas não correspondem à obra atual.')
    for scene in out['cenas_texto']:
        source = by_number[scene['numero']]
        for key in (*EMOTIONAL_SCENE_FIELDS, 'mapa_emocional_aprovado'):
            if key in source:
                scene[key] = deepcopy(source[key])
    # A changed narrative, style or Master cannot acquire approval by copying
    # only the emotional fields. Recompute its actual complete fingerprint.
    require_book_emotional_map(out)
    return out


def commit_reviewed_book(session, approved: dict) -> dict:
    if not session.get(CONTEXT):
        require_book_emotional_map(approved)
        session['state'] = deepcopy(approved)
        return approved
    target = _target(session)
    context = session[CONTEXT]
    merged = merge_emotional_approval(target, approved)
    session[context['state_key']] = merged
    session[REVIEW_BOOK] = deepcopy(merged)
    context['source_fingerprint'] = book_emotional_review_key(merged)
    session[CONTEXT] = context
    return merged


def render_emotional_readiness(st, state_key: str, return_page: str, *, action: str):
    state = st.session_state.get(state_key) or {}
    try:
        require_book_emotional_map(state)
        ready = True
    except (PermissionError, ValueError):
        ready = False
        st.info('Revise e aprove o mapa em Emoção e cores antes de gerar novas imagens. As imagens existentes continuam disponíveis.')
    if st.button('Revisar emoção e cores desta história', key='emotional_review_open_' + action):
        begin_emotional_review(st.session_state, state_key, return_page)
        st.switch_page('pages/17_🎭_Emotional_Color_Director.py')
    return ready


def render_emotional_gate(st, state_key: str, return_page: str, *, action: str, request_context='', include_review_button=True):
    state = st.session_state.get(state_key) or {}
    if include_review_button:
        ready = render_emotional_readiness(st, state_key, return_page, action=action)
    else:
        try:
            require_book_emotional_map(state)
            ready = True
        except (PermissionError, ValueError):
            ready = False
    token = fingerprint({'action': action, 'book': book_emotional_review_key(state), 'request': request_context})
    personal = source_uses_personal_data(state)
    epoch = st.session_state.get('emotional_consent_epoch_' + token, 0)
    consent = st.checkbox('Tenho autorização para enviar os dados pessoais desta geração ao provedor de IA',
                          key='emotional_consent_' + token + '_' + str(epoch)) if personal else False
    return ready and (not personal or consent), consent, token


def consume_emotional_consent(session, token: str) -> None:
    key = 'emotional_consent_epoch_' + token
    session[key] = session.get(key, 0) + 1


_PENDING_ACTION = '_emotional_pending_generation'


def stage_emotional_action(session, state: dict, *, action: str, consent_confirmed=False, request_context='') -> None:
    """Authorize only the next rerun of this exact confirmed generation.

    This capability belongs to the browser action, never to the saved book/job.
    Taking it removes it before any provider call, including failed attempts.
    """
    session.pop(_PENDING_ACTION, None)
    require_book_emotional_map(state)
    if source_uses_personal_data(state) and consent_confirmed is not True:
        raise PermissionError('Autorize os dados pessoais para esta geração antes de continuar.')
    session[_PENDING_ACTION] = {'action': action, 'book': book_emotional_review_key(state),
                                'request': fingerprint(request_context), 'created_at': time.time(),
                                'consent_confirmed': consent_confirmed is True}


def take_emotional_action(session, state: dict, *, action: str, request_context='') -> bool:
    grant = session.pop(_PENDING_ACTION, None)
    require_book_emotional_map(state)
    if (not isinstance(grant, dict) or grant.get('action') != action
            or grant.get('book') != book_emotional_review_key(state)
            or grant.get('request') != fingerprint(request_context)
            or not 0 <= time.time() - grant.get('created_at', 0) <= 120):
        raise PermissionError('Confirme novamente a geração desta história. A autorização vale somente para o próximo clique.')
    if source_uses_personal_data(state) and grant.get('consent_confirmed') is not True:
        raise PermissionError('Autorize os dados pessoais para esta geração antes de continuar.')
    return grant.get('consent_confirmed') is True

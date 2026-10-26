from copy import deepcopy
import streamlit as st
from emotional_visual_binding import (book_emotional_review_key, prepare_book_emotional_map, approve_book_emotional_map, persist_book_emotional_map, require_book_emotional_map)
from emotional_review_ui import review_book, commit_reviewed_book
from editorial_project_updates import load_metadata_snapshot
from project_metadata_ui import open_project_metadata
import storage_backend as storage

from estilo import aplicar_estilo, hero, section_title
from emotion_colors import EMOCOES, EMOCOES_COMPLEMENTARES
from emotional_color_director import (
    PALETAS_PRESET,
    construir_mapa_emocional,
    direcao_emocional,
    normalizar_emocao,
    sugerir_arco,
)

st.set_page_config(page_title='Emotional & Color Director', page_icon='🎭', layout='wide')
aplicar_estilo()
hero(
    'Emotional & Color Director',
    'Planeje emoção, psicologia das cores, intensidade e transições antes de gastar créditos com ilustrações.',
    'FaithBloom · Story Direction',
)

section_title(
    'Mapa emocional',
    'Plutchik organiza família/intensidade emocional; a tabela do Prompt-Mestre Erica Matsuzaki continua sendo a fonte CANÔNICA das cores.',
    'Direção',
)

st.info(
    '🎨 Regra FaithBloom: a cor-base acompanha a emoção página por página, mas a cena nunca deve ficar monocromática. '
    'Cores emocionais atuam em luz, fundo, contraste, saturação e atmosfera — nunca recolorem olhos, pele/pelagem, cabelo ou marcas canônicas.'
)

try:
    state_livro = review_book(st.session_state)
except (PermissionError, ValueError) as exc:
    st.error(str(exc))
    st.stop()


def _reload_review_source(snapshot):
    fresh = deepcopy(snapshot['state'])
    if (state_livro.get('book_id') and fresh.get('book_id')
            and state_livro['book_id'] != fresh['book_id']):
        raise PermissionError('A identidade do livro salvo foi alterada.')
    context = st.session_state.get('_emotional_review_context')
    if context:
        # review_book already validated this return target before the reload.
        st.session_state[context['state_key']] = deepcopy(fresh)
        st.session_state['emotional_review_book'] = deepcopy(fresh)
        context['book_id'] = fresh.get('book_id')
        context['source_fingerprint'] = book_emotional_review_key(fresh)
        st.session_state['_emotional_review_context'] = context
    else:
        st.session_state['state'] = deepcopy(fresh)


map_editor = None
source_mismatch = False
if isinstance(state_livro, dict) and state_livro.get('storage_path'):
    map_editor = open_project_metadata(state_livro['storage_path'],namespace='emotional_map',on_reload=_reload_review_source)
    try:
        observed = deepcopy(map_editor.state)
        opened = deepcopy(state_livro)
        observed['storage_path'] = opened['storage_path'] = map_editor.reference
        source_mismatch = book_emotional_review_key(observed) != book_emotional_review_key(opened)
    except (PermissionError,ValueError,storage.StorageError):
        st.error('Não foi possível conferir a história e os Masters desta revisão. Volte ao livro de origem para reabri-lo.')
        st.stop()
    if source_mismatch:
        st.warning('A história aberta difere da versão salva. Reabra a versão salva antes de aprovar o mapa emocional.')
        if st.button('Reabrir versão salva para a revisão emocional',key=map_editor.key('reopen_review')):
            try:
                _reload_review_source(map_editor.snapshot)
                map_editor.adopt_committed_snapshot(map_editor.snapshot)
                st.rerun()
            except Exception:
                st.error('Não foi possível reabrir a versão salva. Volte ao livro de origem e abra a revisão novamente.')
        map_editor.stale = True
cenas_ativas = (state_livro or {}).get('cenas_texto', []) if isinstance(state_livro, dict) else []

review_stamp = book_emotional_review_key(state_livro)[:20] if cenas_ativas else 'exploration'
if st.session_state.get('_ed_active_source') != review_stamp:
    st.session_state['_ed_active_source'] = review_stamp
    st.session_state.pop('ed_arco', None)
presets = list(PALETAS_PRESET)
active_preset = (state_livro or {}).get('paleta_emocional_preset')
preset = st.selectbox('Paleta editorial', presets, index=presets.index(active_preset) if active_preset in presets else 0, key='ed_preset_' + review_stamp)
emocao_central = st.text_input(
    'Emoção/tema central',
    value=(state_livro or {}).get('emocao_central', 'impaciencia') if isinstance(state_livro, dict) else 'impaciencia',
    help='Ex.: medo, ansiedade, esperança, impaciência, Natal',
)

total_default = len(cenas_ativas) if cenas_ativas else 24
total = st.number_input('Número de cenas', min_value=1, max_value=80, value=max(1, total_default), step=1, disabled=bool(cenas_ativas), key='ed_total_' + review_stamp)

usar_cenas = bool(cenas_ativas) and st.checkbox(
    'Usar as emoções já presentes no livro ativo',
    value=True,
    help='Quando marcado, o mapa começa com as emoções escritas pelo Roteirista. Você pode editar antes de salvar.',
)

if 'ed_arco' not in st.session_state or len(st.session_state.ed_arco) != int(total):
    if usar_cenas:
        st.session_state.ed_arco = [c.get('emocao', 'esperanca') for c in cenas_ativas[: int(total)]]
    else:
        st.session_state.ed_arco = sugerir_arco(emocao_central, int(total))

if st.button('✨ Sugerir arco emocional', type='primary'):
    st.session_state.ed_arco = sugerir_arco(emocao_central, int(total))

arco = list(st.session_state.get('ed_arco', []))
if len(arco) < int(total):
    arco.extend(sugerir_arco(emocao_central, int(total) - len(arco)))
arco = arco[: int(total)]

st.caption('Você pode editar cada cena. Nenhuma mudança aqui gera imagem ou altera o Character DNA.')

edicoes = []
canonicas = list(EMOCOES.keys())
subemocoes = [''] + list(EMOCOES_COMPLEMENTARES.keys())


def _intensidade_segura(valor) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        n = 3
    return max(1, min(5, n))


for i, emocao_sugerida in enumerate(arco, 1):
    cena_existente = cenas_ativas[i - 1] if i - 1 < len(cenas_ativas) else {}
    principal_bruta = cena_existente.get('emocao', emocao_sugerida)
    principal_default = normalizar_emocao(principal_bruta)
    if principal_default not in canonicas:
        principal_default = 'esperanca'

    sub_default = str(cena_existente.get('emocao_secundaria', cena_existente.get('subemocao', '')) or '')
    if sub_default not in subemocoes:
        sub_default = ''

    with st.container(border=True):
        st.markdown(f"### Cena {cena_existente.get('numero', i):02d}")
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        principal = c1.selectbox(
            'Emoção principal canônica',
            canonicas,
            index=canonicas.index(principal_default),
            key=f'ed_em_{review_stamp}_{i}',
        )
        secundaria = c2.selectbox(
            'Subemoção (opcional)',
            subemocoes,
            index=subemocoes.index(sub_default),
            format_func=lambda x: x.replace('_', ' ').title() if x else '— nenhuma —',
            key=f'ed_sub_{review_stamp}_{i}',
        )
        intensidade = c3.slider(
            'Intensidade', 1, 5, _intensidade_segura(cena_existente.get('intensidade_emocional', 3)), key=f'ed_int_{review_stamp}_{i}'
        )
        travar = c4.checkbox('🔒 Travar', value=bool(cena_existente.get('emocao_travada', False)), key=f'ed_lock_{review_stamp}_{i}')

        transicao = st.text_input(
            'Transição emocional (opcional)',
            value=str(cena_existente.get('transicao_emocional', '') or ''),
            key=f'ed_trans_{review_stamp}_{i}',
            placeholder='Ex.: tristeza → começando a surgir esperança',
        )
        extra = st.text_input(
            'Instrução editorial opcional',
            value=str(cena_existente.get('instrucao_emocional', '') or ''),
            key=f'ed_extra_{review_stamp}_{i}',
            placeholder='Ex.: impaciente, mas ainda fofa e levemente engraçada.',
        )

        d = direcao_emocional(principal, preset, intensidade, secundaria, transicao)
        pl = d['plutchik']
        st.write(
            f"🎨 **Base: {d['cor_principal']}** · apoio: {', '.join(d['cores_apoio'])} · "
            f"atmosfera: {d['atmosfera']}"
        )
        st.write(
            f"🎭 **Plutchik:** {pl['familia_principal']} → {pl['nivel']}"
            + (f" · secundária: {pl['familia_secundaria']}" if pl['familia_secundaria'] else '')
            + (f" · combinação: {pl['combinacao']}" if pl['combinacao'] else '')
        )
        st.caption(f"🙏 Uso espiritual/editorial: {d['uso_espiritual']}")
        st.caption('🌈 ' + d['regra_nao_monocromatica'])
        st.caption('🔒 ' + d['regra_character_dna'])

        edicoes.append({
            'numero': cena_existente.get('numero', i),
            'emocao': principal,
            'emocao_secundaria': secundaria,
            'intensidade_emocional': intensidade,
            'transicao_emocional': transicao,
            'emocao_travada': travar,
            'instrucao_emocional': extra,
            'paleta_preset': preset,
        })

if cenas_ativas:
    reviewer = st.text_input('Responsável pela revisão emocional', key='ed_reviewer_' + review_stamp)
    reviewed = st.checkbox('Revisei todas as cenas, a direção emocional e a preservação dos Masters', key='ed_reviewed_' + review_stamp)
    st.caption('A aprovação salva no Book Master exato quando ele já está aberto. Um livro novo recebe identidade própria; nenhum projeto é escolhido pelo título.')
    if st.button('💾 Aplicar e salvar este mapa no livro ativo', type='primary', use_container_width=True,
        disabled=not reviewed or not reviewer.strip() or bool(map_editor and not map_editor.can_save)):
        try:
            working = deepcopy(state_livro)
            by_number = {row['numero']: row for row in edicoes}
            for scene in working['cenas_texto']:
                scene.update(by_number[scene['numero']])
            working['paleta_emocional_preset'] = preset
            working['mapa_emocional'] = construir_mapa_emocional(working['cenas_texto'], preset)
            working = approve_book_emotional_map(working, reviewed=reviewed, reviewer=reviewer)
            if map_editor and not map_editor.can_save:
                map_editor.preserve_pending(working,fields=['cenas_texto','mapa_emocional','paleta_emocional_preset','emotional_book_binding'])
                st.warning('Recarregue o projeto e confira a geração antes de salvar este mapa. Suas escolhas foram preservadas.')
                st.stop()
            # Recheck the exact return target before writing durable data.
            review_book(st.session_state)
            working = persist_book_emotional_map(working,snapshot=map_editor.observed_snapshot if map_editor else None)
            working = commit_reviewed_book(st.session_state, working)
            state_livro = working
            if map_editor:
                try:
                    map_editor.adopt_committed_snapshot(load_metadata_snapshot(map_editor.reference))
                except Exception:
                    map_editor.entry['needs_reload'] = True
                    st.info('O mapa foi salvo. Recarregue os dados do projeto para conferir a versão atual antes de novas alterações.')
            st.success('Mapa emocional revisado, aprovado e salvo nesta obra. O Ilustrador receberá a direção canônica cena por cena.')
        except Exception as exc:
            if map_editor and 'working' in locals():
                map_editor.preserve_pending(working,fields=['cenas_texto','mapa_emocional','paleta_emocional_preset','emotional_book_binding'])
            if isinstance(exc,storage.StorageConflict):
                st.warning('O projeto mudou durante esta revisão. Recarregue a versão salva; suas escolhas foram preservadas para conferência.')
            elif isinstance(exc,storage.AccessDenied):
                st.error('Sua sessão não permite salvar o mapa deste projeto.')
            else:
                st.error(str(exc))
    try:
        require_book_emotional_map(state_livro)
        st.success('A versão atual do mapa emocional está aprovada para novas ilustrações.')
    except Exception as exc:
        st.info(str(exc))
    if map_editor and map_editor.stale:
        map_editor.preserve_form_inputs({'paleta_emocional_preset':preset,'cenas_emocionais':edicoes,
            'reviewer':reviewer,'reviewed':reviewed})
else:
    st.warning('Abra/crie uma história para salvar o mapa diretamente no livro. Aqui você ainda pode explorar o arco sem gerar imagens.')

with st.expander('📚 Ver tabela canônica do Prompt-Mestre'):
    for chave, dados in EMOCOES.items():
        st.markdown(f"**{dados['label']}** — {dados['cor']} · {dados['atmosfera']} · 🙏 {dados['uso_espiritual']}")
        st.caption('Cores de apoio: ' + ', '.join(dados.get('cores_apoio', [])))

with st.expander('🌱 Ver emoções complementares'):
    for chave, dados in EMOCOES_COMPLEMENTARES.items():
        st.markdown(
            f"**{chave.replace('_', ' ').title()}** → base canônica **{dados['base']}** · "
            + ', '.join(dados.get('cores_apoio', []))
        )

with st.expander('🎨 Ver detalhes da paleta selecionada'):
    st.json(PALETAS_PRESET[preset])

context = st.session_state.get('_emotional_review_context') or {}
if context.get('return_page') and st.button('Voltar à geração de imagens'):
    st.switch_page(context['return_page'])

st.info('Nenhuma imagem é gerada nesta tela. A aprovação do mapa emocional acontece antes da geração visual em lote.')

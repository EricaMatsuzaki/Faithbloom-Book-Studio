import streamlit as st

from estilo import aplicar_estilo, hero, section_title
from emotion_colors import EMOCOES, EMOCOES_COMPLEMENTARES
from emotional_color_director import (
    PALETAS_PRESET,
    analisar_plutchik,
    construir_mapa_emocional,
    direcao_emocional,
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

state_livro = st.session_state.get('state')
cenas_ativas = (state_livro or {}).get('cenas_texto', []) if isinstance(state_livro, dict) else []

preset = st.selectbox('Paleta editorial', list(PALETAS_PRESET), index=0)
emocao_central = st.text_input(
    'Emoção/tema central',
    value=(state_livro or {}).get('emocao_central', 'impaciencia') if isinstance(state_livro, dict) else 'impaciencia',
    help='Ex.: medo, ansiedade, esperança, impaciência, Natal',
)

total_default = len(cenas_ativas) if cenas_ativas else 24
total = st.number_input('Número de cenas', min_value=1, max_value=80, value=max(1, total_default), step=1)

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

for i, emocao_sugerida in enumerate(arco, 1):
    cena_existente = cenas_ativas[i - 1] if i - 1 < len(cenas_ativas) else {}
    principal_default = cena_existente.get('emocao', emocao_sugerida)
    if principal_default not in canonicas:
        # Emoção narrativa complementar recebe a base canônica apenas para o seletor principal.
        principal_default = EMOCOES_COMPLEMENTARES.get(principal_default, {}).get('base', 'esperanca')
        if principal_default not in canonicas:
            principal_default = 'esperanca'

    sub_default = cena_existente.get('emocao_secundaria', cena_existente.get('subemocao', ''))
    if sub_default not in subemocoes:
        sub_default = ''

    with st.container(border=True):
        st.markdown(f'### Cena {i:02d}')
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        principal = c1.selectbox(
            'Emoção principal canônica',
            canonicas,
            index=canonicas.index(principal_default),
            key=f'ed_em_{i}',
        )
        secundaria = c2.selectbox(
            'Subemoção (opcional)',
            subemocoes,
            index=subemocoes.index(sub_default),
            format_func=lambda x: x.replace('_', ' ').title() if x else '— nenhuma —',
            key=f'ed_sub_{i}',
        )
        intensidade = c3.slider(
            'Intensidade', 1, 5, int(cena_existente.get('intensidade_emocional', 3) or 3), key=f'ed_int_{i}'
        )
        travar = c4.checkbox('🔒 Travar', value=bool(cena_existente.get('emocao_travada', False)), key=f'ed_lock_{i}')

        transicao = st.text_input(
            'Transição emocional (opcional)',
            value=cena_existente.get('transicao_emocional', ''),
            key=f'ed_trans_{i}',
            placeholder='Ex.: tristeza → começando a surgir esperança',
        )
        extra = st.text_input(
            'Instrução editorial opcional',
            value=cena_existente.get('instrucao_emocional', ''),
            key=f'ed_extra_{i}',
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
            'numero': i,
            'emocao': principal,
            'emocao_secundaria': secundaria,
            'intensidade_emocional': intensidade,
            'transicao_emocional': transicao,
            'emocao_travada': travar,
            'instrucao_emocional': extra,
            'paleta_preset': preset,
        })

if cenas_ativas:
    if st.button('💾 Aplicar e salvar este mapa no livro ativo', type='primary', use_container_width=True):
        for idx, ed in enumerate(edicoes):
            if idx >= len(state_livro['cenas_texto']):
                break
            state_livro['cenas_texto'][idx].update(ed)
        state_livro['paleta_emocional_preset'] = preset
        state_livro['mapa_emocional'] = construir_mapa_emocional(state_livro['cenas_texto'], preset)
        st.session_state.state = state_livro
        st.success('Mapa emocional salvo no livro. O Ilustrador receberá emoção, subemoção, intensidade, transição e psicologia das cores cena por cena.')
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

st.info('Nenhuma imagem é gerada nesta tela. A aprovação do mapa emocional acontece antes da geração visual em lote.')

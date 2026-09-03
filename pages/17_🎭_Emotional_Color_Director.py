import streamlit as st
from estilo import aplicar_estilo, hero, section_title
from emotional_color_director import PALETAS_PRESET, construir_mapa_emocional, sugerir_arco, direcao_emocional

st.set_page_config(page_title='Emotional & Color Director', page_icon='🎭', layout='wide')
aplicar_estilo()
hero('Emotional & Color Director', 'Planeje emoção, psicologia das cores, luz e expressão antes de gastar créditos com todas as ilustrações.', 'FaithBloom · Story Direction')

section_title('Mapa emocional', 'Emoção da história ≠ cor do personagem. A paleta atua no ambiente; Character DNA continua bloqueado.', 'Direção')
preset = st.selectbox('Paleta editorial', list(PALETAS_PRESET), index=0)
emocao_central = st.text_input('Emoção/tema central', value='impaciencia', help='Ex.: medo, ansiedade, esperança, impaciência, Natal')
total = st.number_input('Número de cenas', min_value=1, max_value=80, value=24, step=1)

if 'ed_arco' not in st.session_state:
    st.session_state.ed_arco = sugerir_arco(emocao_central, int(total))

if st.button('✨ Sugerir arco emocional', type='primary'):
    st.session_state.ed_arco = sugerir_arco(emocao_central, int(total))

arco = st.session_state.get('ed_arco', [])
st.caption('Você pode editar cada cena antes de gerar imagens. Nenhuma mudança aqui altera o Character DNA.')

for i, emocao in enumerate(arco, 1):
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1,2,2,1])
        c1.markdown(f'**Cena {i:02d}**')
        nova = c2.text_input('Emoção', value=emocao, key=f'ed_em_{i}')
        intensidade = c3.slider('Intensidade', 1, 5, 3, key=f'ed_int_{i}')
        c4.checkbox('🔒 Travar', key=f'ed_lock_{i}')
        d = direcao_emocional(nova, preset, intensidade)
        st.write(f"🎨 **{d['cor_principal']}** · {d['atmosfera']} · base cromática: `{d['emocao_cromatica_base']}`")
        st.caption(d['regra_character_dna'])
        st.text_input('Instrução editorial opcional', key=f'ed_extra_{i}', placeholder='Ex.: impaciente, mas ainda fofa e levemente engraçada.')

with st.expander('🎨 Ver detalhes da paleta selecionada'):
    st.json(PALETAS_PRESET[preset])

st.info('Próxima integração: este mapa pode ser salvo no projeto e enviado ao Ilustrador cena a cena. O Ilustrador já recebeu a regra de não recolorir características canônicas do personagem.')

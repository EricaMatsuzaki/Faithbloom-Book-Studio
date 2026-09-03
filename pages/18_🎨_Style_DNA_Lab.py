import streamlit as st
from estilo import aplicar_estilo, hero, section_title
from armazenamento import listar_colecoes
from style_dna import criar_style_dna, listar_styles, carregar_style, style_para_prompt

st.set_page_config(page_title='Style DNA Lab', page_icon='🎨', layout='wide')
aplicar_estilo()
hero('Style DNA Lab', 'Salve a linguagem visual de uma coleção para criar novos personagens, cenas, coloring books e activity books no mesmo universo.', 'FaithBloom · Collection Consistency')

colecoes = listar_colecoes()
colecao = st.text_input('Coleção / Universo', value=colecoes[0] if colecoes else 'Cute Friends')
section_title('Style Masters', 'Character DNA define quem é o personagem. Style DNA define como o universo é desenhado.', 'Estilo')

with st.expander('➕ Criar Style DNA oficial', expanded=False):
    nome = st.text_input('Nome do Style DNA', value='Cute Friends · Line Art')
    modo = st.selectbox('Modo', ['geral','line_art','color_master','activity'])
    olhos = st.text_input('Olhos / expressão', placeholder='olhos grandes, brilhantes, infantis...')
    proporcoes = st.text_input('Proporções', placeholder='cabeça grande, corpo pequeno e arredondado...')
    linhas = st.text_input('Linhas/contornos', placeholder='contorno preto limpo, uniforme, sem cinza...')
    composicao = st.text_input('Composição/cenários', placeholder='moldura arredondada, cenários simples...')
    detalhes = st.text_input('Nível de detalhe', placeholder='áreas amplas para colorir, faixa 5–8 anos...')
    extras = st.text_area('Outras regras')
    usos = st.multiselect('Pode ser usado em', ['story','coloring','activity','cover'], default=['coloring','activity','cover'])
    if st.button('⭐ Salvar Style DNA', type='primary', disabled=not nome.strip()):
        regras = {'olhos_expressao': olhos, 'proporcoes': proporcoes, 'linhas_contornos': linhas, 'composicao': composicao, 'nivel_detalhe': detalhes, 'extras': extras}
        criar_style_dna(nome.strip(), colecao, regras, modo, usos)
        st.success('Style DNA oficial salvo.'); st.rerun()

itens = listar_styles(colecao)
if not itens:
    st.info('Ainda não há Style DNA oficial nesta coleção.')
for item in itens:
    s = carregar_style(item['id'])
    with st.container(border=True):
        st.subheader('⭐ ' + s.get('nome',''))
        st.caption(f"{s.get('modo','geral')} · usos: {', '.join(s.get('usos_permitidos', []))}")
        st.json(s.get('regras',{}))
        with st.expander('Prompt técnico gerado'):
            st.code(style_para_prompt(s, (s.get('usos_permitidos') or ['coloring'])[0]), language=None)

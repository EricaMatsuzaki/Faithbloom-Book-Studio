import streamlit as st
from estilo import aplicar_estilo, hero, section_title
from armazenamento import listar_colecoes
from style_dna import criar_style_dna, listar_styles, carregar_style, atualizar_style, style_para_prompt

st.set_page_config(page_title='Style DNA Lab', page_icon='🎨', layout='wide')
aplicar_estilo()
hero('Style DNA Lab', 'Salve a linguagem visual de uma coleção para criar novos personagens, cenas, story books, coloring books e activity books no mesmo universo.', 'FaithBloom · Collection Consistency')

colecoes = listar_colecoes()
colecao = st.text_input('Coleção / Universo', value=colecoes[0] if colecoes else 'Cute Friends')
section_title('Style Masters', 'Character DNA define quem é o personagem. Style DNA define como o universo é desenhado.', 'Estilo')
st.info('📖 Para Story Books e Full Editorial Remaster, o Style DNA precisa ter o uso **story** ativo. Isso mantém o universo visual consistente sem alterar Character DNA ou Color Master.')

with st.expander('➕ Criar Style DNA oficial', expanded=False):
    nome = st.text_input('Nome do Style DNA', value='Cute Friends · Line Art')
    modo = st.selectbox('Modo', ['geral','line_art','color_master','activity'])
    olhos = st.text_input('Olhos / expressão', placeholder='olhos grandes, brilhantes, infantis...')
    proporcoes = st.text_input('Proporções', placeholder='cabeça grande, corpo pequeno e arredondado...')
    linhas = st.text_input('Linhas/contornos', placeholder='contorno preto limpo, uniforme, sem cinza...')
    composicao = st.text_input('Composição/cenários', placeholder='moldura arredondada, cenários simples...')
    detalhes = st.text_input('Nível de detalhe', placeholder='áreas amplas para colorir, faixa 5–8 anos...')
    extras = st.text_area('Outras regras')
    usos = st.multiselect(
        'Pode ser usado em',
        ['story','coloring','activity','cover'],
        default=['story','coloring','activity','cover'],
        help='Deixe story ativo para usar este Style DNA em livros ilustrados, Handoff Visual e Visual Remaster Workbench.',
    )
    if st.button('⭐ Salvar Style DNA', type='primary', disabled=not nome.strip()):
        regras = {'olhos_expressao': olhos, 'proporcoes': proporcoes, 'linhas_contornos': linhas, 'composicao': composicao, 'nivel_detalhe': detalhes, 'extras': extras}
        criar_style_dna(nome.strip(), colecao, regras, modo, usos)
        st.success('Style DNA oficial salvo.'); st.rerun()

itens = listar_styles(colecao)
if not itens:
    st.info('Ainda não há Style DNA oficial nesta coleção.')
for item in itens:
    s = carregar_style(item['id'])
    usos_atuais = list(s.get('usos_permitidos') or [])
    story_ativo = not usos_atuais or 'story' in usos_atuais
    with st.container(border=True):
        st.subheader('⭐ ' + s.get('nome',''))
        st.caption(f"{s.get('modo','geral')} · usos: {', '.join(usos_atuais) if usos_atuais else 'todos'}")
        if story_ativo:
            st.success('✅ Ativo para Story / Editorial Remaster')
        else:
            st.warning('⚠️ Inativo para Story / Editorial Remaster. Hoje este Style DNA não entra no prompt de remasterização de livros de história.')
            if st.button('📖 Ativar para Story / Remaster', key=f"activate_story_{s.get('id')}", use_container_width=True):
                novos_usos = list(dict.fromkeys(usos_atuais + ['story']))
                atualizar_style(s['id'], {'usos_permitidos': novos_usos})
                st.success('Style DNA ativado para Story / Remaster sem alterar suas regras visuais.')
                st.rerun()
        st.json(s.get('regras',{}))
        with st.expander('Prompt técnico para Story / Remaster'):
            prompt_story = style_para_prompt(s, 'story')
            if prompt_story:
                st.code(prompt_story, language=None)
            else:
                st.caption('Ative o uso story para gerar o prompt técnico deste Style DNA no fluxo de Remaster.')

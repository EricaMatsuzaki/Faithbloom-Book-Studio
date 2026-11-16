import streamlit as st
from estilo import aplicar_estilo, hero, section_title
from armazenamento import listar_colecoes
from biblioteca_editorial import criar_projeto_mestre,listar_projetos_mestre,carregar_projeto_mestre,adicionar_edicao
from ui_saved_choices import select_saved_or_new
st.set_page_config(page_title='Biblioteca Editorial',page_icon='📚',layout='wide'); aplicar_estilo()
hero('Biblioteca Editorial','Organize cada obra como Projeto-Mestre e mantenha idiomas, assets e versões ligados ao mesmo livro.','FaithBloom · Master Library')
with st.expander('➕ Novo Projeto-Mestre'):
    t=st.text_input('Título')
    c=select_saved_or_new(
        'Coleção',
        listar_colecoes(),
        current='',
        key='editorial_library_collection_select',
        new_input_label='Nome da nova coleção',
        allow_empty=True,
        help='Escolha uma coleção já salva sempre que este livro pertencer a um universo existente.',
    )
    lang=st.selectbox('Idioma Master',['pt-BR','en-US','en-GB','es','ja-JP','fr','it','de','Outro'])
    if st.button('Criar Projeto-Mestre',type='primary',disabled=not t.strip()): criar_projeto_mestre(t.strip(),c.strip(),lang.strip()); st.success('Projeto-Mestre criado.'); st.rerun()
section_title('Projetos-Mestre','Uma obra pode ter várias edições e idiomas sem duplicar seu universo visual.','Biblioteca')
for item in listar_projetos_mestre():
    p=carregar_projeto_mestre(item['id'])
    with st.container(border=True):
        st.subheader('📖 '+p.get('titulo',''))
        st.caption(f"{p.get('colecao','')} · Master {p.get('idioma_master','')}")
        ed=p.get('edicoes',{}); st.write('Edições:', ', '.join(ed.keys()) if ed else 'nenhuma cadastrada')
        with st.expander('🌍 Adicionar/atualizar edição'):
            loc=st.text_input('Locale (ex.: en-US, ja-JP)',key='loc'+p['id']); status=st.selectbox('Status',['publicada','em revisão','rascunho'],key='st'+p['id'])
            if st.button('Salvar edição',key='save'+p['id'],disabled=not loc.strip()): adicionar_edicao(p['id'],loc.strip(),{'status':status}); st.success('Edição vinculada.'); st.rerun()

import os
import streamlit as st
from estilo import aplicar_estilo, hero, section_title
from armazenamento import listar_colecoes
from character_universe import (
    criar_personagem_oficial, listar_personagens_oficiais, carregar_personagem_oficial,
    adicionar_variacao, salvar_preset, personagem_para_prompt, VARIAVEIS_PADRAO,
    adicionar_referencia, definir_master_visual
)

st.set_page_config(page_title='Character Universe', page_icon='👥', layout='wide')
aplicar_estilo()
hero('Character Universe', 'Crie personagens oficiais uma vez e reutilize-os em histórias, line art, atividades e capas sem perder identidade.', 'FaithBloom · Character Master')
section_title('Personagens oficiais', 'Character DNA bloqueado + Color Master + Line Art Master + Reference Pack + variações preservadas.', 'Coleção')

selected_asset_path = st.session_state.get("faithbloom_selected_asset_path", "")
selected_asset_id = st.session_state.get("faithbloom_selected_asset_id", "")
if selected_asset_path and os.path.exists(selected_asset_path):
    st.success("🖼️ Asset selecionado na Asset Library: você pode adicioná-lo ao Reference Pack ou defini-lo como Master de um personagem abaixo.")


colecoes = listar_colecoes()
colecao = st.text_input('Coleção', value=colecoes[0] if colecoes else 'Pequenas Histórias, Grandes Lições')

with st.expander('➕ Criar Character Master oficial', expanded=False):
    nome = st.text_input('Nome do personagem')
    descricao = st.text_area('Descrição Master', placeholder='Ex.: gatinha creme/pêssego, aparência extremamente doce...')
    st.caption('Preencha campos estruturados quando souber. Eles permitem auditoria objetiva; campos vazios não geram nota fictícia.')
    a,b,c = st.columns(3)
    especie = a.text_input('Espécie/tipo')
    olhos = b.text_input('Olhos')
    paleta = c.text_input('Paleta-base / pelagem / pele')
    d,e,f = st.columns(3)
    rosto = d.text_input('Formato do rosto')
    proporcoes = e.text_input('Proporções')
    marcas = f.text_input('Marcas/acessórios permanentes')
    variaveis = st.multiselect('O que PODE variar por cena', VARIAVEIS_PADRAO, default=VARIAVEIS_PADRAO)
    usos = st.multiselect('Pode ser reutilizado em', ['story','coloring','activity','cover'], default=['story','coloring','activity','cover'])
    color = st.text_input('Caminho do Color Master (opcional)')
    line = st.text_input('Caminho do Line Art Master (opcional)')
    if st.button('⭐ Salvar como personagem oficial', type='primary', disabled=not nome.strip()):
        campos = {k:v for k,v in {'especie':especie,'olhos':olhos,'paleta_base':paleta,'rosto':rosto,'proporcoes':proporcoes,'marcas_permanentes':marcas}.items() if v.strip()}
        dna = {'descricao_master': descricao, 'campos_bloqueados': campos, 'caracteristicas_bloqueadas': descricao, 'variaveis_permitidas': variaveis}
        criar_personagem_oficial(colecao, nome.strip(), dna, color, line, metadata={'usos_permitidos': usos})
        st.success('Character Master oficial salvo.'); st.rerun()

itens = listar_personagens_oficiais(colecao)
if not itens:
    st.info('Ainda não há personagens oficiais nesta coleção.')

for item in itens:
    p = carregar_personagem_oficial(item['id'])
    with st.container(border=True):
        st.subheader('⭐ ' + p.get('nome',''))
        st.caption('Personagem oficial · ' + p.get('colecao','') + ' · usos: ' + ', '.join(p.get('metadata',{}).get('usos_permitidos',[])))
        dna = p.get('dna',{})
        st.write(dna.get('descricao_master') or dna.get('caracteristicas_bloqueadas') or 'DNA ainda não preenchido.')
        if dna.get('campos_bloqueados'):
            st.json(dna['campos_bloqueados'])
        c1,c2,c3,c4 = st.columns(4)
        c1.metric('Color Master','✅' if p.get('color_master') else '—')
        c2.metric('Line Art Master','✅' if p.get('line_art_master') else '—')
        c3.metric('Reference Pack',len(p.get('reference_pack',[])))
        c4.metric('Variações preservadas',len(p.get('variacoes',[])))

        if selected_asset_path and os.path.exists(selected_asset_path):
            with st.expander('🖼️ Usar o asset selecionado da Asset Library neste personagem', expanded=False):
                q1,q2,q3=st.columns(3)
                if q1.button('➕ Reference Pack', key=f"libref_{p['id']}", use_container_width=True):
                    adicionar_referencia(p['id'], selected_asset_path, 'asset_library', 'asset_library', {'asset_library_id': selected_asset_id})
                    st.success('Referência adicionada sem substituir Masters.'); st.rerun()
                if q2.button('⭐ Color Master', key=f"libcolor_{p['id']}", use_container_width=True):
                    definir_master_visual(p['id'], selected_asset_path, 'color')
                    st.success('Color Master atualizado com versionamento.'); st.rerun()
                if q3.button('🖍️ Line Art Master', key=f"libline_{p['id']}", use_container_width=True):
                    definir_master_visual(p['id'], selected_asset_path, 'line_art')
                    st.success('Line Art Master atualizado com versionamento.'); st.rerun()

        tab1,tab2,tab3 = st.tabs(['🎭 Variar sem perder identidade','💾 Presets','🧬 Prompt protegido'])
        with tab1:
            tipo = st.selectbox('Tipo de variação', ['pose','acao','expressao','emocao','figurino','cenario','estacao','festividade'], key=f"tipo_{p['id']}")
            instr = st.text_input('Pedido', placeholder='Ex.: Natal, cachecol vermelho, feliz na neve...', key=f"var_{p['id']}")
            if st.button('➕ Guardar pedido como nova variação', key=f"addvar_{p['id']}", disabled=not instr.strip()):
                adicionar_variacao(p['id'], tipo, instr.strip())
                st.success('Variação preservada sem apagar as anteriores.'); st.rerun()
            for v in p.get('variacoes', [])[-5:]:
                st.caption(f"{v.get('tipo')} · {v.get('instrucao')} · {'✅ aprovada' if v.get('aprovada') else 'rascunho'}")
        with tab2:
            categoria = st.selectbox('Categoria', ['figurinos','cenarios','estacoes','festividades','emocoes'], key=f"pcat_{p['id']}")
            pn = st.text_input('Nome do preset', placeholder='Mel · Christmas Outfit', key=f"pn_{p['id']}")
            pi = st.text_input('Instrução', placeholder='cachecol vermelho, sem alterar rosto/pelagem...', key=f"pi_{p['id']}")
            if st.button('💾 Salvar preset', key=f"sp_{p['id']}", disabled=not pn.strip()):
                salvar_preset(p['id'], categoria, pn.strip(), pi.strip()); st.success('Preset salvo.'); st.rerun()
            presets = p.get('metadata',{}).get('presets',{})
            if presets.get(categoria): st.json(presets[categoria])
        with tab3:
            exemplo = {'expressao':'alegre','figurino':'cachecol vermelho','cenario':'rua nevada','festividade':'Natal'}
            try:
                st.code(personagem_para_prompt(p, 'color', exemplo, 'story'), language=None)
            except Exception as e:
                st.warning(str(e))

        st.caption('Regra: identidade permanente fica bloqueada; roupa, pose, ação, expressão, cenário, estação e festividade podem variar conforme autorização/prompt.')

import os
import streamlit as st
from estilo import aplicar_estilo, hero, section_title
from armazenamento import listar_colecoes
from character_universe import (
    criar_personagem_oficial, listar_personagens_oficiais, carregar_personagem_oficial,
    adicionar_variacao, salvar_preset, personagem_para_prompt, VARIAVEIS_PADRAO,
    adicionar_referencia
)
from asset_library import get_asset, get_thumbnail, list_assets
from character_asset_selector import asset_option_label, asset_preview_details, assets_by_id
from openrouter_client import gerar_imagem
from scene_color_controls import COLOR_TREATMENTS, LIGHTING, SCENE_PRESETS, build_restoration_prompt
from visual_master_manager import (
    IDENTITY_REVIEW_NOTICE, REFERENCE_CATEGORIES, approve_candidate, archive_asset, create_abc,
    promote_master, register_upload,
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
    if st.button('⭐ Salvar como personagem oficial', type='primary', disabled=not nome.strip()):
        campos = {k:v for k,v in {'especie':especie,'olhos':olhos,'paleta_base':paleta,'rosto':rosto,'proporcoes':proporcoes,'marcas_permanentes':marcas}.items() if v.strip()}
        dna = {'descricao_master': descricao, 'campos_bloqueados': campos, 'caracteristicas_bloqueadas': descricao, 'variaveis_permitidas': variaveis}
        criar_personagem_oficial(colecao, nome.strip(), dna, metadata={'usos_permitidos': usos})
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

        if p.get('color_master'):
            st.success('🟢 Color Master oficial e protegido')
        elif any((r.get('metadata') or {}).get('visual_status') == 'MASTER_CANDIDATE' for r in p.get('reference_pack', [])):
            st.warning('🟡 Master Candidate — aguardando aprovação')
        elif p.get('reference_pack'):
            st.warning('🟡 Referência visual recebida — aguardando tratamento/aprovação')
        else:
            st.info('🟡 DNA cadastrado — sem referência visual')

        with st.expander('📤 Fazer upload de referências', expanded=not bool(p.get('reference_pack'))):
            uploads = st.file_uploader('Uma ou várias imagens', type=['png','jpg','jpeg','webp'], accept_multiple_files=True, key=f"uploads_{p['id']}")
            st.caption('O upload entra como referência. Nunca se torna Master automaticamente.')
            upload_categories = []
            for upload_index, upload in enumerate(uploads or []):
                upload_categories.append(st.selectbox(
                    f'Categoria de {upload.name} (opcional)', ['Sem categoria', *REFERENCE_CATEGORIES],
                    key=f"refcat_{p['id']}_{upload_index}_{upload.name}",
                ))
            if st.button('Adicionar ao Reference Pack', key=f"saveuploads_{p['id']}", disabled=not uploads):
                for upload_index, upload in enumerate(uploads):
                    selected_category = upload_categories[upload_index]
                    register_upload(p['id'], upload.name, upload.getvalue(), '' if selected_category == 'Sem categoria' else selected_category)
                st.success('Referências salvas e auditadas, com os originais preservados.'); st.rerun()

        library = list_assets({'media_kind': 'image'}, page_size=100).get('items', [])
        with st.expander('🖼️ Escolher da Asset Library'):
            options = assets_by_id(library)
            chosen_id = st.selectbox(
                'Imagem', [''] + list(options),
                format_func=lambda aid: '—' if not aid else asset_option_label(options[aid]),
                key=f"libpick_{p['id']}",
            )
            if chosen_id:
                chosen = options[chosen_id]
                thumb = get_thumbnail(chosen['id'])
                if thumb: st.image(thumb, width=240)
                st.caption(asset_preview_details(chosen))
                if chosen.get('visual_status') == 'MASTER_CANDIDATE':
                    if st.button('✅ Aprovar como variação', key=f"approve_library_{p['id']}_{chosen['id']}"):
                        approve_candidate(chosen['id']); st.rerun()
                if st.button('Adicionar como referência', key=f"pickref_{p['id']}"):
                    adicionar_referencia(p['id'], chosen.get('storage_uri') or chosen.get('caminho_arquivo',''), 'outra', 'asset_library', {'asset_library_id': chosen['id']})
                    st.success('Adicionada sem substituir o Master.'); st.rerun()

        refs_with_assets = []
        for ref in p.get('reference_pack', []):
            aid = (ref.get('metadata') or {}).get('asset_library_id')
            asset = get_asset(aid) if aid else None
            if asset: refs_with_assets.append((ref, asset))
        if refs_with_assets:
            with st.expander('🛠️ Restaurar / Melhorar', expanded=False):
                source_options = assets_by_id([asset for _, asset in refs_with_assets])
                source_id = st.selectbox(
                    'Imagem original', list(source_options),
                    format_func=lambda aid: asset_option_label(source_options[aid]),
                    key=f"source_{p['id']}",
                )
                source = source_options[source_id]
                source_thumb = get_thumbnail(source_id)
                if source_thumb: st.image(source_thumb, width=240)
                st.caption(asset_preview_details(source))
                action_labels = {
                    'Restauração leve': 'light', 'Controlled Remaster': 'controlled_remaster',
                    'DNA Reconstruction': 'dna_reconstruction', '🌷 Melhorar cenário': 'improve_scene',
                    '🖼️ Trocar cenário': 'replace_scene', 'Modificar somente isto': 'modify_only',
                    'Gerar Line Art Candidate': 'line_art',
                }
                action_name = st.selectbox('Ação', list(action_labels), key=f"action_{p['id']}")
                action = action_labels[action_name]
                scene = st.selectbox('Cenário/preset', ['—'] + list(SCENE_PRESETS), key=f"scene_{p['id']}")
                request = st.text_area('O que deseja alterar?', key=f"request_{p['id']}", placeholder='Ex.: Deixe somente o fundo um pouco mais claro.')
                col1,col2 = st.columns(2)
                color_treatment = col1.selectbox('🎨 Tratamento de cor', COLOR_TREATMENTS, key=f"color_{p['id']}")
                lighting = col2.selectbox('💡 Iluminação', LIGHTING, key=f"light_{p['id']}")
                quantity = st.radio('Resultados independentes', [1, 3], format_func=lambda n: '1 versão' if n == 1 else '🔄 Criar A/B/C', horizontal=True, key=f"qty_{p['id']}")
                prompt = build_restoration_prompt(action, dna=dna, request=request, scene='' if scene == '—' else scene, color=color_treatment, lighting=lighting)
                with st.expander('Identity Lock · detalhes preservados'):
                    st.write('✅ identidade, espécie, rosto, olhos, pelagem/cabelo, proporções, marcas e acessórios permanentes, Style DNA')
                    st.code(prompt)
                if st.button('Gerar candidata(s)', type='primary', key=f"generate_{p['id']}"):
                    references = [a.get('caminho_arquivo','') for _,a in refs_with_assets if a['id'] != source['id']]
                    paths = [gerar_imagem(prompt, imagem_base=source.get('caminho_arquivo'), imagens_referencia=references) for _ in range(quantity)]
                    created = create_abc(source['id'], paths, transformation=action, prompt=prompt, dna_version=str(dna.get('version','')))
                    st.session_state[f"results_{p['id']}"] = [x['id'] for x in created]
                    st.rerun()

        result_ids = st.session_state.get(f"results_{p['id']}", [])
        if result_ids:
            st.markdown('#### ORIGINAL × RESULTADO')
            cols = st.columns(len(result_ids))
            for col, aid in zip(cols, result_ids):
                candidate = get_asset(aid)
                with col:
                    st.image(candidate.get('caminho_arquivo'), caption=candidate.get('version_label'), width="stretch")
                    st.caption(candidate.get('visual_status', 'MASTER_CANDIDATE'))
                    st.warning(IDENTITY_REVIEW_NOTICE)
                    if st.button('✅ Aprovar', key=f"approve_{aid}"):
                        approve_candidate(aid); st.rerun()
                    confirmed = st.checkbox('Confirmo a promoção humana', key=f"confirm_{aid}")
                    if st.button('⭐ Tornar Color Master', key=f"master_{aid}", disabled=not confirmed):
                        promote_master(p['id'], aid, 'color_master', confirmed=confirmed); st.success('Master oficial salvo; histórico anterior preservado.'); st.rerun()
                    if st.button('🖍️ Tornar Line Art Master', key=f"line_master_{aid}", disabled=not confirmed):
                        promote_master(p['id'], aid, 'line_art_master', confirmed=confirmed); st.success('Line Art Master oficial salvo com histórico.'); st.rerun()
                    if st.button('🗄️ Arquivar', key=f"archive_{aid}"):
                        archive_asset(aid); st.rerun()

        if selected_asset_path and os.path.exists(selected_asset_path):
            with st.expander('🖼️ Usar o asset selecionado da Asset Library neste personagem', expanded=False):
                q1,q2,q3=st.columns(3)
                if q1.button('➕ Reference Pack', key=f"libref_{p['id']}", width="stretch"):
                    adicionar_referencia(p['id'], selected_asset_path, 'asset_library', 'asset_library', {'asset_library_id': selected_asset_id})
                    st.success('Referência adicionada sem substituir Masters.'); st.rerun()
                q2.caption('Para virar Master, use o fluxo de candidata + aprovação humana.')
                q3.caption('Line Art também exige candidata, QA e aprovação.')

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

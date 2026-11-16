import streamlit as st
from copy import deepcopy
from estilo import aplicar_estilo, hero, section_title, callout
from fila_producao import (
    listar_jobs, carregar_job, criar_job_ilustracoes, resumo_job,
    pausar_job, continuar_job, cancelar_job, recuperar_jobs_interrompidos,
    processar_proximo, processar_lote, executor_ilustracao_story,
    preparar_revisao_emocional_job, aplicar_mapa_emocional_job,
    QueueCheckpointError, reconciliar_item_job,
)
from storage_backend import StorageError
from armazenamento import listar_livros, carregar_livro, salvar_livro
from openrouter_client import gerar_imagem
from controle_geracao import POLITICA
from emotional_visual_binding import book_emotional_review_key, require_book_emotional_map
from emotional_review_ui import begin_emotional_review, render_emotional_gate, consume_emotional_consent

st.set_page_config(page_title="Fila de Produção", page_icon="🏭", layout="wide")
aplicar_estilo()
hero("Fila de Produção", "Gere livros em etapas recuperáveis: pausar, continuar e cancelar sem perder o que já foi concluído.", "FaithBloom · Production Queue")

def executar_com_recuperacao(job_id, action):
    try:
        action()
    except QueueCheckpointError as exc:
        st.session_state['queue_received_result_' + job_id] = {
            'attempt_token': exc.attempt_token, 'state': exc.state, 'item_updates': exc.item_updates}
        st.error(str(exc))
    except (StorageError, PermissionError, ValueError) as exc:
        st.error(str(exc))
    else:
        st.rerun()

section_title("Criar fila", "A fila salva um checkpoint depois de cada cena. As imagens não são aprovadas automaticamente.", "Produção")
livros=listar_livros()
if livros:
    labels=[f"{x['titulo']} · {x['colecao']}" for x in livros]
    idx=st.selectbox("Livro salvo", range(len(livros)), format_func=lambda i: labels[i])
    somente=st.checkbox("Ignorar cenas já aprovadas", value=True)
    if st.button("➕ Criar fila de ilustrações", type="primary"):
        ref=livros[idx]
        state=carregar_livro(ref["colecao"], ref["storage_path"])
        state['storage_path'] = ref['storage_path'] if ref['storage_path'].startswith('fb://') else 'fb://' + ref['storage_path']
        try:
            job=criar_job_ilustracoes(state, somente)
            st.success(f"Fila criada: {job['nome']}")
            st.rerun()
        except Exception as e:
            st.error(str(e))
else:
    st.info("Salve um Story Book primeiro para criar uma fila de ilustrações.")

st.markdown("---")
section_title("Jobs", "Cada chamada processa no máximo o lote seguro definido na Fase 13.", "Controle")
jobs=listar_jobs()
if not jobs:
    st.caption("Nenhum job criado ainda.")

for job in jobs:
    r=resumo_job(job)
    indefinido = bool(job.get('execution_claim')) or any(
        item.get('status') in {'executando', 'incerto'} for item in job.get('itens', []))
    with st.expander(f"{job.get('nome')} · {job.get('status')} · {r['concluidos']}/{r['total']}", expanded=job.get('status') in {'fila','executando','pausado'}):
        st.progress(r['percentual']/100 if r['total'] else 0, text=f"{r['concluidos']}/{r['total']} concluídos · {r['erros']} erro(s)")
        st.caption(f"ID: {job['id']} · atualizado: {job.get('atualizado_em','')}")
        if job.get("ultimo_erro"):
            st.error(job["ultimo_erro"])
        c1,c2,c3,c4=st.columns(4)
        if c1.button("⏸️ Pausar", key=f"pause_{job['id']}", disabled=job.get('status') in {'pausado','cancelado','concluido'}):
            pausar_job(job['id']); st.rerun()
        if c2.button("▶️ Continuar", key=f"resume_{job['id']}", disabled=indefinido or job.get('status') not in {'pausado','fila'}):
            continuar_job(job['id']); st.rerun()
        if c3.button("⏹️ Cancelar", key=f"cancel_{job['id']}", disabled=job.get('status') in {'cancelado','concluido'}):
            cancelar_job(job['id']); st.rerun()
        if c4.button("💾 Salvar snapshot como livro", key=f"save_{job['id']}", disabled=not bool(job.get('state'))):
            uri=salvar_livro(job['state']); st.success(f"Snapshot salvo: {uri}")
        if indefinido:
            st.warning('Há uma tentativa em execução ou sem resultado confirmado. Confira o provedor antes de gerar novamente; esta fila não reenviará a chamada.')
            if job.get('status') == 'executando' or any(item.get('status') == 'executando' for item in job.get('itens', [])):
                claim_token = (job.get('execution_claim') or {}).get('token')
                recovery_key = job['id'] + '_' + str(claim_token or job.get('revision', 0))
                interrupted = st.checkbox('Confirmei que o processo responsável por esta tentativa foi encerrado.', key='interrupted_' + recovery_key)
                shutdown_note = st.text_input('Evidência do encerramento do processo responsável', key='shutdown_evidence_' + recovery_key)
                st.caption('Em outro host, confirme o encerramento no serviço que executava a tentativa e registre a evidência. Esta etapa apenas encaminha o resultado para conferência.')
                if st.button('Encaminhar tentativa para conferência', key='recover_' + recovery_key, disabled=not interrupted or not shutdown_note.strip()):
                    executar_com_recuperacao(job['id'], lambda: recuperar_jobs_interrompidos(
                        job['id'], confirmed=interrupted, attempt_token=claim_token, shutdown_note=shutdown_note))
        if st.session_state.get('queue_received_result_' + job['id']):
            st.info('O resultado recebido foi mantido nesta sessão. Confira a persistência antes de qualquer nova geração.')

        if job.get('tipo')=='story_ilustracoes' and job.get('status') not in {'cancelado','concluido'}:
            review_key = 'queue_emotional_review_' + job['id']
            baseline_key = review_key + '_baseline'
            try:
                require_book_emotional_map(job.get('state') or {})
            except (PermissionError, ValueError):
                st.info('Esta fila precisa do mapa emocional aprovado antes de gerar novas imagens. Os itens concluídos serão preservados.')
            if st.button('Revisar emoção e cores desta fila', key='review_' + job['id']):
                snapshot = preparar_revisao_emocional_job(job['id'])
                st.session_state[review_key] = deepcopy(snapshot['state'])
                st.session_state[baseline_key] = book_emotional_review_key(snapshot['state'])
                begin_emotional_review(st.session_state, review_key, 'pages/12_🏭_Fila_de_Producao.py')
                st.switch_page('pages/17_🎭_Emotional_Color_Director.py')
            reviewed = st.session_state.get(review_key)
            if reviewed is not None and st.session_state.get(baseline_key):
                try:
                    require_book_emotional_map(reviewed)
                    reviewed_ready = True
                except (PermissionError, ValueError):
                    reviewed_ready = False
                if st.button('Aplicar mapa revisado a esta fila', key='apply_review_' + job['id'], disabled=not reviewed_ready):
                    try:
                        aplicar_mapa_emocional_job(job['id'], reviewed,
                            expected_source_fingerprint=st.session_state[baseline_key])
                        st.session_state.pop(review_key, None)
                        st.session_state.pop(baseline_key, None)
                        st.rerun()
                    except (StorageError, PermissionError, ValueError) as exc:
                        st.error(str(exc))
            execution_key = 'queue_execution_book_' + job['id']
            st.session_state[execution_key] = deepcopy(job.get('state') or {})
            qtd=st.selectbox("Lote seguro", list(range(1, POLITICA.max_imagens_lote+1)), index=0, key=f"qtd_{job['id']}")
            ready, consent, token = render_emotional_gate(
                st, execution_key, 'pages/12_🏭_Fila_de_Producao.py', action='queue_' + job['id'],
                request_context={'job_id': job['id'], 'quantity': qtd, 'pending': [
                    {'id': item['id'], 'number': item.get('numero'), 'instruction': item.get('instrucao')}
                    for item in job.get('itens', []) if item.get('status') in {'pendente', 'erro'}]},
                include_review_button=False)
            a,b=st.columns(2)
            if a.button("🎨 Processar próxima cena", key=f"one_{job['id']}", disabled=indefinido or job.get('status') in {'pausado', 'executando'} or not ready):
                consume_emotional_consent(st.session_state, token)
                executor=executor_ilustracao_story(gerar_imagem, consent_confirmed=consent,
                    job_id=job['id'], source_fingerprint=book_emotional_review_key(job['state']), max_items=1)
                executar_com_recuperacao(job['id'], lambda: processar_proximo(job['id'],executor))
            if b.button("⚙️ Processar lote", key=f"batch_{job['id']}", disabled=indefinido or job.get('status') in {'pausado', 'executando'} or not ready):
                consume_emotional_consent(st.session_state, token)
                executor=executor_ilustracao_story(gerar_imagem, consent_confirmed=consent,
                    job_id=job['id'], source_fingerprint=book_emotional_review_key(job['state']), max_items=qtd)
                with st.spinner(f"Processando até {qtd} cena(s), com checkpoint após cada uma..."):
                    executar_com_recuperacao(job['id'], lambda: processar_lote(job['id'],executor,qtd))

        with st.expander("Itens da fila"):
            for item in job.get('itens',[]):
                icone={'concluido':'✅','executando':'🔄','incerto':'⚠️','erro':'❌','pendente':'⏳'}.get(item.get('status'),'•')
                st.write(f"{icone} Cena {item.get('numero','?')} · {item.get('status')} · tentativas {item.get('tentativas',0)}")
                if item.get('erro'): st.caption(item['erro'])
                if item.get('status') == 'incerto' and item.get('attempt_token'):
                    reconciliation_key = job['id'] + '_' + item['id'] + '_' + item['attempt_token']
                    retained = st.session_state.get('queue_received_result_' + job['id']) or {}
                    choices = {'O provedor confirmou que a chamada não foi enviada': 'not_sent',
                               'O provedor confirmou a falha sem resultado recuperável': 'failed'}
                    if retained.get('attempt_token') == item['attempt_token']:
                        choices['Recuperar o resultado recebido nesta sessão'] = 'succeeded'
                    outcome = st.selectbox('Resultado da conferência', list(choices), key='outcome_' + reconciliation_key)
                    note = st.text_input('Evidência ou justificativa da conferência', key='evidence_' + reconciliation_key)
                    checked = st.checkbox('Conferi esta tentativa exata e seu custo no provedor.', key='checked_' + reconciliation_key)
                    if st.button('Registrar conferência desta tentativa', key='reconcile_' + reconciliation_key, disabled=not checked or not note.strip()):
                        executar_com_recuperacao(job['id'], lambda: reconciliar_item_job(
                            job['id'], item['id'], attempt_token=item['attempt_token'],
                            provider_outcome=choices[outcome], note=note, confirmed=checked,
                            recovered_state=retained.get('state'), item_updates=retained.get('item_updates')))

callout("Como funciona", "Cada fila executa um item por vez e preserva resultados já concluídos. Após uma interrupção, encaminhe a tentativa para conferência e verifique resultado e custo no provedor. Uma tentativa incerta não é repetida automaticamente.", "info")

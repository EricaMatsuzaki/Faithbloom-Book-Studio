from pathlib import Path
import os
import streamlit as st

from estilo import aplicar_estilo, hero, section_title
from book_doctor import listar_projetos, carregar_projeto, carregar_relatorio
from character_universe import (listar_personagens_oficiais, carregar_personagem_oficial, adicionar_referencia, definir_master_visual)
from style_dna import listar_styles, carregar_style
from coloring_presets import listar_presets, preset_para_prompt
from restoration_studio import (
    ACOES, criar_plano_restauracao, carregar_plano_restauracao,
    vincular_character, vincular_style, salvar_vinculos, registrar_decisao,
    melhorar_imagem_tecnicamente, limpar_line_art, montar_prompt_restauracao,
    gerar_variacao_ia, aprovar_versao, resumo_restauracao, auditar_line_art,
)

st.set_page_config(page_title="Restoration Studio", page_icon="✨", layout="wide")
aplicar_estilo()
hero(
    "✨ Restoration Studio",
    "Transforme a auditoria do Book Doctor em correções controladas, preservando o original e criando versões Remastered comparáveis.",
    "Refinamento 04 · Book Doctor × Character Universe × Style DNA",
)
st.info("🔒 Regra absoluta: nenhum botão desta página sobrescreve o arquivo original. Toda correção vira uma nova versão derivada.")
selected_library_path = st.session_state.get("faithbloom_selected_asset_path", "")
if selected_library_path and Path(selected_library_path).exists():
    st.success("🖼️ Há um asset selecionado no Asset Library. Ele poderá ser usado como referência visual adicional nas ações com IA.")

projetos = listar_projetos()
if not projetos:
    st.warning("Nenhum projeto do Book Doctor foi encontrado. Crie uma auditoria primeiro.")
    st.page_link("pages/16_🩺_Book_Doctor.py", label="🩺 Abrir Book Doctor", use_container_width=True)
    st.stop()

# Prefere o projeto recém-criado na sessão, se houver.
sess = st.session_state.get("book_doctor_project") or {}
def idx_inicial():
    for i,p in enumerate(projetos):
        if p.get('id') == sess.get('id'):
            return i
    return 0

rotulos = [f"{p.get('titulo','(sem título)')} · {p.get('id')} · {p.get('tipo_projeto','story')}" for p in projetos]
escolha = st.selectbox("Projeto Book Doctor", range(len(projetos)), index=idx_inicial(), format_func=lambda i: rotulos[i])
projeto = projetos[escolha]
rel = carregar_relatorio(projeto)
plan = carregar_plano_restauracao(projeto) or criar_plano_restauracao(projeto, rel, projeto.get('tipo_projeto'), projeto.get('status_publicacao'), projeto.get('colecao',''))

m1,m2,m3,m4=st.columns(4)
m1.metric("Tipo", projeto.get('tipo_projeto','story'))
m2.metric("Status", projeto.get('status_publicacao',''))
m3.metric("Assets", len(plan.get('assets_detectados',[])))
m4.metric("Política", "🔒 original" if plan.get('politica')=='original_preservado' else 'verificar')

section_title("1 · Vincule a identidade oficial", "Escolha Character Master e Style DNA. O prompt de restauração usa esses vínculos sem modificar a identidade bloqueada.", "DNA")
colecao = projeto.get('colecao') or plan.get('colecao') or ''
characters = listar_personagens_oficiais(colecao or None)
styles = listar_styles(colecao or None)

ca, cb = st.columns(2)
with ca:
    char_options = ['— nenhum —'] + [f"{x.get('nome')} · {x.get('id')}" for x in characters]
    char_sel = st.selectbox("Character Master", range(len(char_options)), format_func=lambda i: char_options[i])
    character_id = '' if char_sel == 0 else characters[char_sel-1]['id']
    if character_id:
        ch = carregar_personagem_oficial(character_id)
        st.caption(ch.get('dna',{}).get('descricao_master',''))
        if st.button("🔗 Vincular Character Master ao projeto", use_container_width=True):
            plan = vincular_character(plan, character_id)
            plan = salvar_vinculos(projeto, plan)
            st.success("Personagem vinculado ao plano sem alterar o Character DNA.")
with cb:
    style_options = ['— nenhum —'] + [f"{x.get('nome')} · {x.get('id')}" for x in styles]
    style_sel = st.selectbox("Style DNA", range(len(style_options)), format_func=lambda i: style_options[i])
    style_id = '' if style_sel == 0 else styles[style_sel-1]['id']
    if style_id:
        sd = carregar_style(style_id)
        st.caption(str(sd.get('regras',{})))
        if st.button("🔗 Vincular Style DNA ao projeto", use_container_width=True):
            plan = vincular_style(plan, style_id)
            plan = salvar_vinculos(projeto, plan)
            st.success("Style DNA vinculado.")

# Usa vínculos persistentes como fallback.
if not character_id:
    chars_link = plan.get('vinculos',{}).get('characters',[])
    character_id = chars_link[-1].get('character_id','') if chars_link else ''
if not style_id:
    style_id = plan.get('vinculos',{}).get('style_id','')

section_title("2 · Escolha a página/imagem", "A primeira versão continua visível; a versão Remastered aparece ao lado para comparação.", "Antes × Depois")
assets = [a for a in plan.get('assets_detectados',[]) if a.get('arquivo') and Path(a.get('arquivo','')).exists()]
if not assets:
    st.warning("Não encontrei imagens extraídas para este projeto. Volte ao Book Doctor e audite o PDF novamente.")
    st.stop()

asset_idx = st.selectbox(
    "Asset",
    range(len(assets)),
    format_func=lambda i: f"{assets[i].get('id')} · {assets[i].get('tipo')} · página {assets[i].get('pagina') or '—'} · {assets[i].get('largura_px')}×{assets[i].get('altura_px')} px",
)
asset = assets[asset_idx]
origem = asset['arquivo']

# Busca a versão mais recente derivada deste original.
plan = carregar_plano_restauracao(projeto)
derivadas = [v for v in plan.get('versoes_assets',[]) if v.get('origem') == origem and Path(v.get('derivado','')).exists()]
ultima = derivadas[-1] if derivadas else None

before, after = st.columns(2)
with before:
    st.markdown("#### 🔒 ORIGINAL")
    st.image(origem, use_container_width=True)
    st.caption(f"{asset.get('largura_px')}×{asset.get('altura_px')} px · status: {asset.get('status_tecnico','indeterminado')}")
if projeto.get('tipo_projeto') == 'coloring':
    qa_line = auditar_line_art(origem)
    q1,q2,q3=st.columns(3)
    q1.metric("Tons de cinza", f"{qa_line['tons_cinza_pct']}%")
    q2.metric("Cobertura de tinta", f"{qa_line['cobertura_tinta_pct']}%")
    q3.metric("Line Art QA", qa_line['status'])
    for aviso in qa_line.get('alertas',[]):
        st.warning("🖍️ " + aviso)
    st.caption(qa_line['nota'])

with after:
    st.markdown("#### ✨ REMASTERED / VARIAÇÃO")
    if ultima:
        st.image(ultima['derivado'], use_container_width=True)
        st.caption(f"{ultima.get('operacao')} · versão {ultima.get('id')} · {'✅ aprovada' if ultima.get('aprovada') else 'aguardando aprovação'}")
        if not ultima.get('aprovada') and st.button("✅ Aprovar esta versão", key=f"approve_{ultima['id']}", use_container_width=True):
            aprovar_versao(projeto, ultima['id']); st.success("Versão aprovada. O original continua preservado."); st.rerun()
    else:
        st.info("Nenhuma versão derivada ainda. Escolha uma ação abaixo.")

with st.expander("👥 Usar este asset no Character Universe", expanded=False):
    st.caption("Use uma página inteira como referência contextual apenas se ela representar bem o personagem. Para um Master definitivo, prefira uma imagem limpa/aprovada do personagem.")
    if character_id:
        c1,c2,c3=st.columns(3)
        if c1.button("➕ Adicionar ao Reference Pack", use_container_width=True):
            adicionar_referencia(character_id, origem, "cena_book_doctor", "book_doctor", {"projeto_id":projeto.get('id'),"pagina":asset.get('pagina')})
            st.success("Referência adicionada sem substituir nenhum Master.")
        if c2.button("⭐ Definir como Color Master", use_container_width=True):
            definir_master_visual(character_id, origem, "color")
            st.success("Color Master atualizado com versionamento.")
        if c3.button("🖍️ Definir como Line Art Master", use_container_width=True):
            definir_master_visual(character_id, origem, "line_art")
            st.success("Line Art Master atualizado com versionamento.")
    else:
        st.info("Selecione/vincule um Character Master acima. Se este personagem ainda não existe, crie-o primeiro no Character Universe e volte aqui.")
        st.page_link("pages/14_👥_Character_Universe.py", label="👥 Abrir Character Universe", use_container_width=True)

section_title("3 · Escolha o que corrigir", "Você decide o nível da intervenção. Melhorias técnicas não mudam o conteúdo; restauração por IA exige aprovação explícita.", "Controle")
action_labels = {
    'manter_original':'🔒 Manter original',
    'melhorar_tecnicamente':'✨ Melhorar tecnicamente',
    'limpar_line_art':'🖍️ Limpar / normalizar line art',
    'corrigir_personagem':'👤 Corrigir somente personagem',
    'reilustrar':'🎨 Reilustrar cena',
    'criar_variacao':'🎲 Criar variação',
}
acao = st.radio("Ação", ACOES, format_func=lambda x: action_labels[x], horizontal=True)

larg_final, alt_final = st.columns(2)
final_w = larg_final.number_input("Largura final impressa deste asset (pol.) — opcional", min_value=0.0, value=0.0, step=0.125)
final_h = alt_final.number_input("Altura final impressa deste asset (pol.) — opcional", min_value=0.0, value=0.0, step=0.125)

if acao == 'manter_original':
    st.write("O asset será marcado para permanecer como está. Nenhuma geração ou filtro será executado.")
    if st.button("🔒 Registrar decisão: manter", type="primary"):
        registrar_decisao(projeto, asset['id'], acao, character_id, style_id)
        st.success("Decisão registrada. Nenhum arquivo foi alterado.")

elif acao == 'melhorar_tecnicamente':
    c1,c2,c3=st.columns(3)
    fator=c1.selectbox("Upscale determinístico", [1,2,3,4], index=1)
    nitidez=c2.slider("Nitidez", 1.0, 1.8, 1.15, 0.05)
    contraste=c3.slider("Contraste", 0.9, 1.3, 1.05, 0.05)
    auto=st.checkbox("Autocontraste", value=False)
    st.caption("Lanczos pode melhorar tamanho/amostragem, mas não recupera detalhe semântico perdido. O FaithBloom registra essa limitação no histórico.")
    if st.button("✨ Criar cópia tecnicamente melhorada", type="primary"):
        registrar_decisao(projeto, asset['id'], acao, character_id, style_id, metadata={'fator':fator})
        out=melhorar_imagem_tecnicamente(projeto, origem, fator, nitidez, contraste, auto, final_w or None, final_h or None)
        st.success(f"Nova versão criada: {out['caminho']}")
        if out.get('ppi_depois',{}).get('ppi_efetivo'):
            st.write(f"PPI efetivo estimado no tamanho informado: **{out['ppi_depois']['ppi_efetivo']}**")
        st.rerun()

elif acao == 'limpar_line_art':
    presets=listar_presets()
    pi=st.selectbox("Preset de faixa etária/traço (referência editorial)", range(len(presets)), format_func=lambda i: f"{presets[i].get('nome')} · {presets[i].get('faixa_etaria')} · {presets[i].get('espessura')}")
    preset=presets[pi]
    st.caption(preset_para_prompt(preset))
    c1,c2,c3=st.columns(3)
    threshold=c1.slider("Corte preto/branco", 140, 240, 205, 5)
    esp=c2.selectbox("Espessura", ['manter','engrossar','afinar'])
    fator=c3.selectbox("Upscale", [1,2,3,4], index=1, key='line_up')
    ruido=st.checkbox("Reduzir pequenos ruídos antes de binarizar", value=True)
    if st.button("🖍️ Criar Line Art Master limpa", type="primary"):
        registrar_decisao(projeto, asset['id'], acao, character_id, style_id, metadata={'preset_id':preset.get('id')})
        out=limpar_line_art(projeto, origem, threshold, ruido, esp, fator, final_w or None, final_h or None)
        st.success("Nova line art criada em preto/branco puro, sem destruir a original.")
        st.rerun()

else:
    contexto = 'coloring' if projeto.get('tipo_projeto') == 'coloring' else ('activity' if projeto.get('tipo_projeto') == 'activity' else 'story')
    emocao = st.text_input("Emoção da cena — opcional", placeholder="ex.: esperança, tristeza, alegria") if contexto == 'story' else ''
    e1,e2,e3=st.columns(3)
    expressao=e1.text_input("Expressão", placeholder="feliz, curiosa...")
    figurino=e2.text_input("Roupa/acessório", placeholder="cachecol vermelho...")
    cenario=e3.text_input("Cenário", placeholder="jardim, neve...")
    instrucao=st.text_area("Sua instrução específica", placeholder="Ex.: corrigir somente o rosto da Mel para ficar igual ao Character Master; manter todo o restante da cena.")
    variaveis={k:v for k,v in {'expressao':expressao,'figurino':figurino,'cenario':cenario}.items() if v.strip()}
    prompt=montar_prompt_restauracao(acao, character_id, style_id, contexto, variaveis, emocao, instrucao_autora=instrucao)
    refs_visuais=[]
    if character_id:
        ch_ref=carregar_personagem_oficial(character_id)
        master_ref=(ch_ref.get('line_art_master') if contexto=='coloring' else ch_ref.get('color_master')) or ch_ref.get('color_master') or ch_ref.get('line_art_master')
        if master_ref and Path(master_ref).exists():
            refs_visuais.append(master_ref)
            st.success("🧬 Character Master visual será enviado junto com a cena-base para reforçar consistência.")
    if selected_library_path and Path(selected_library_path).exists() and selected_library_path not in refs_visuais and selected_library_path != origem:
        usar_asset_extra = st.checkbox("🖼️ Usar também o asset selecionado na Asset Library como referência", value=True)
        if usar_asset_extra:
            refs_visuais.append(selected_library_path)
            st.caption("A referência extra orienta a geração; a cena original continua preservada.")
    st.markdown("#### Prompt protegido gerado")
    st.code(prompt, language=None)
    if not character_id and acao == 'corrigir_personagem':
        st.warning("Para corrigir personagem com segurança, vincule um Character Master acima antes da geração.")
    if st.button("📝 Registrar plano sem gastar créditos", use_container_width=True):
        registrar_decisao(projeto, asset['id'], acao, character_id, style_id, instrucao, {'prompt':prompt})
        st.success("Plano salvo. Nenhum crédito de imagem foi usado.")
    pode_gerar = bool(os.environ.get('OPENROUTER_API_KEY')) and not (acao=='corrigir_personagem' and not character_id)
    if pode_gerar:
        st.warning("A próxima ação chama o modelo de imagem e pode consumir créditos. A saída será salva como nova versão, nunca sobre o original.")
        if st.button("✨ Gerar nova versão com IA", type="primary"):
            from openrouter_client import gerar_imagem
            registrar_decisao(projeto, asset['id'], acao, character_id, style_id, instrucao, {'prompt':prompt})
            with st.spinner("Gerando variação Remastered..."):
                out=gerar_variacao_ia(projeto, origem, prompt, gerar_imagem, acao, refs_visuais)
            st.success("Variação gerada e preservada para comparação.")
            st.rerun()
    else:
        st.caption("🔐 Geração de IA indisponível nesta sessão até configurar OPENROUTER_API_KEY; o prompt e o plano podem ser salvos normalmente.")

section_title("4 · Histórico e Quality Gate", "Nada some: decisões e versões ficam registradas para revisão final.", "Versionamento")
plan=carregar_plano_restauracao(projeto)
res=resumo_restauracao(projeto)
r1,r2,r3,r4=st.columns(4)
r1.metric("Decisões",res['decisoes_total']); r2.metric("Versões",res['versoes_geradas']); r3.metric("Aprovadas",res['versoes_aprovadas']); r4.metric("Original", "✅ preservado" if res['original_preservado'] else "⚠️ verificar")

with st.expander("📜 Versões derivadas"):
    if plan.get('versoes_assets'):
        st.dataframe([{k:v for k,v in x.items() if k not in {'metadata'}} for x in plan['versoes_assets']], use_container_width=True)
    else:
        st.caption("Nenhuma versão derivada ainda.")
with st.expander("🧾 Decisões editoriais"):
    if plan.get('decisoes'):
        st.dataframe([{k:v for k,v in x.items() if k not in {'metadata'}} for x in plan['decisoes']], use_container_width=True)

st.info("Próximo quality gate: somente versões aprovadas pela pessoa responsável devem seguir para diagramação/preflight. O Quality Guardian final continua sendo uma etapa futura e independente.")

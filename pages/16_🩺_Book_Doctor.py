import tempfile
from pathlib import Path
import streamlit as st

from estilo import aplicar_estilo, hero
from book_doctor import (
    criar_projeto, preservar_original, auditar_pdf, auditar_pdf_rapido, auditar_imagem,
    auditar_capa_pdf, gerar_relatorio,
)
from restoration_studio import criar_plano_restauracao

st.set_page_config(page_title="Book Doctor", page_icon="🩺", layout="wide")
aplicar_estilo()
hero(
    "🩺 Book Doctor",
    "Importe Story Books, Coloring/Line Art ou Activity Books, preserve o original e descubra o que merece revisão antes de criar uma edição Remastered.",
)
st.info("🔒 O Book Doctor trabalha em cópia. O arquivo enviado nunca é sobrescrito.")

st.subheader("1 · Identifique o projeto")
a,b,c = st.columns(3)
tipo_label = a.selectbox("Tipo de projeto", ["📖 Livro de História", "🖍️ Coloring / Line Art", "🧩 Livro de Atividades", "📚 Outro"])
tipo_map = {"📖 Livro de História":"story", "🖍️ Coloring / Line Art":"coloring", "🧩 Livro de Atividades":"activity", "📚 Outro":"other"}
status_label = b.selectbox("Status editorial", ["Já publicado", "Ainda não publicado", "Em desenvolvimento"])
status_map = {"Já publicado":"publicado", "Ainda não publicado":"nao_publicado", "Em desenvolvimento":"em_desenvolvimento"}
status_capa = c.selectbox("Situação da capa", ["Capa existente", "Sem capa", "Capa em desenvolvimento"])

titulo=st.text_input("Título do livro", "Quando Mel Aprendeu a Esperar")
colecao=st.text_input("Coleção / universo", "Pequenas Histórias, Grandes Lições")
idioma=st.selectbox("Idioma/edição",["pt-BR","en-US","es","ja-JP","fr","it","de","Outro"])

st.subheader("2 · Envie os arquivos")
miolo=st.file_uploader("📄 PDF do miolo",type=["pdf"])
capa=st.file_uploader("📕 Capa — imagem ou PDF/wrap",type=["png","jpg","jpeg","webp","pdf"])
modo_auditoria = st.radio(
    "Modo de auditoria do miolo",
    ["⚡ Rápida — triagem sem extrair todas as imagens", "🔬 Completa — extrair imagens para restauração"],
    horizontal=True,
    help="A triagem rápida é recomendada para PDFs grandes. A completa é necessária quando você quer levar imagens extraídas ao Restoration Studio.",
)
col1,col2=st.columns(2)
trim_w=col1.number_input("Largura física final da arte/capa (pol.) — opcional",min_value=0.0,value=0.0,step=0.125)
trim_h=col2.number_input("Altura física final da arte/capa (pol.) — opcional",min_value=0.0,value=0.0,step=0.125)

if tipo_map[tipo_label] == "coloring":
    st.caption("🖍️ Coloring Book: além da resolução, o plano de restauração incluirá Line Art QA, preto/branco puro, espessura de traço, complexidade por idade, Style DNA e Cover Doctor.")
if status_capa == "Sem capa":
    st.caption("📕 Sem capa: o projeto será marcado para criação posterior de Cover Master usando personagens/Style DNA aprovados do próprio miolo.")

if st.button("🔎 Criar auditoria + plano de restauração",type="primary",disabled=not bool(miolo or capa)):
    projeto=criar_projeto(
        titulo, idioma,
        tipo_projeto=tipo_map[tipo_label],
        status_publicacao=status_map[status_label],
        colecao=colecao,
        status_capa=status_capa,
    )
    miolo_r=capa_r=None
    if miolo:
        tmp=Path(tempfile.mkdtemp())/miolo.name; tmp.write_bytes(miolo.getvalue())
        orig=preservar_original(projeto,str(tmp),"miolo")
        if modo_auditoria.startswith("⚡"):
            miolo_r=auditar_pdf_rapido(orig)
        else:
            miolo_r=auditar_pdf(orig,str(Path(projeto['pasta'])/'extraidas'))
    if capa:
        tmp=Path(tempfile.mkdtemp())/capa.name; tmp.write_bytes(capa.getvalue())
        orig=preservar_original(projeto,str(tmp),"capa")
        if capa.name.lower().endswith('.pdf'):
            capa_r=auditar_capa_pdf(orig,trim_w or None,trim_h or None,str(Path(projeto['pasta'])/'extraidas'/'capa'))
        else:
            capa_r=auditar_imagem(orig,trim_w or None,trim_h or None)
    rel=gerar_relatorio(projeto,miolo_r,capa_r)
    plano = None
    if not (miolo_r and miolo_r.get("modo_auditoria") == "rapida"):
        plano=criar_plano_restauracao(projeto,rel,tipo_map[tipo_label],status_map[status_label],colecao)
    st.session_state['book_doctor_report']=rel
    st.session_state['book_doctor_project']=projeto
    st.session_state['restoration_plan']=plano

rel=st.session_state.get('book_doctor_report')
projeto=st.session_state.get('book_doctor_project')
if rel:
    st.success("Auditoria criada. O original foi preservado e o plano de restauração foi iniciado.")
    x1,x2,x3,x4=st.columns(4)
    x1.metric("Tipo", rel.get('tipo_projeto','story'))
    x2.metric("Status", rel.get('status_publicacao',''))
    x3.metric("Coleção", rel.get('colecao','') or '—')
    x4.metric("Capa", rel.get('status_capa',''))

    if rel.get('miolo'):
        m=rel['miolo']; a,b,c=st.columns(3)
        image_label = "XObjects de imagem" if m.get("modo_auditoria") == "rapida" else "Imagens extraídas"
        a.metric("Páginas",m['paginas_total']); b.metric(image_label,len(m['imagens'])); c.metric("Tamanho uniforme","Sim" if m['tamanho_uniforme'] else "Não")
        st.caption(m['observacao_ppi'])
        if m.get("modo_auditoria") == "rapida":
            st.info("⚡ Triagem rápida concluída. Nenhuma imagem foi extraída/decodificada. Para restaurar páginas, rode a auditoria completa quando decidir quais assets precisam de intervenção.")
            text_diag = m.get("analise_textual_piloto") or {}
            if text_diag.get("adjacent_text_overlap"):
                st.warning(f"Foram detectados {len(text_diag['adjacent_text_overlap'])} par(es) de páginas com forte sobreposição textual. Confirmar visualmente antes de editar.")
                st.dataframe(text_diag['adjacent_text_overlap'], use_container_width=True, hide_index=True)
        with st.expander("📊 Imagens página por página",expanded=True):
            st.dataframe([{k:v for k,v in x.items() if k not in ('arquivo_extraido',)} for x in m['imagens']],use_container_width=True)

    if rel.get('capa'):
        cp=rel['capa']; st.subheader("📕 Capa")
        if cp.get('tipo') == 'pdf':
            st.write(f"PDF de capa · **{cp.get('paginas_total',0)} página(s)** · status técnico: **{cp.get('status')}**")
            st.caption(cp.get('nota',''))
        else:
            st.write(f"{cp.get('largura_px')} × {cp.get('altura_px')} px · {cp.get('status')}")
            if cp.get('ppi_efetivo'): st.write(f"PPI efetivo no tamanho informado: **{cp['ppi_efetivo']}**")

    st.subheader("🚦 Alertas mensuráveis")
    if not rel['alertas']: st.success("Nenhum alerta técnico automático encontrado nesta primeira passagem.")
    for x in rel['alertas']:
        fn=st.error if x.get('gravidade')=='bloqueante' else st.warning
        fn(f"{x['gravidade'].upper()} · {x['area']}: {x['mensagem']}")

    st.subheader("👀 Revisões visuais/editoriais encaminhadas aos Studios especializados")
    for x in rel['revisoes_pendentes']: st.write("• "+x)

    st.markdown("### ✨ Próxima etapa: Restoration Studio")
    if rel.get("miolo", {}).get("modo_auditoria") == "rapida":
        st.write("A triagem rápida serve para decidir onde investigar. Para levar imagens extraídas ao Restoration Studio, rode a auditoria completa depois — sem alterar o original preservado.")
    else:
        st.write("Agora você pode escolher uma imagem/página, vincular Character Master e Style DNA, decidir **Manter / Melhorar tecnicamente / Limpar line art / Corrigir personagem / Reilustrar / Criar variação** e comparar Antes × Depois.")
        st.page_link("pages/19_✨_Restoration_Studio.py",label="✨ Abrir Restoration Studio →",use_container_width=True)
    if rel.get('tipo_projeto') == 'coloring':
        st.page_link("pages/20_🖍️_Coloring_Book_Doctor.py",label="🖍️ Abrir Coloring Book Doctor — Age/Complexity + Cover Master →",use_container_width=True)
    if projeto:
        st.caption(f"Projeto Book Doctor: {projeto.get('id')} · original protegido por SHA-256 no manifest.")

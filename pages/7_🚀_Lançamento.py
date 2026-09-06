"""
Painel de Lançamento - reúne tudo que ajuda um livro a vender bem,
além da produção em si: palavras-chave, categorias, calculadora de
preço/royalty, e o material de marketing gerado.

IMPORTANTE: nada aqui garante sucesso de vendas sozinho. Palavras-chave
e categorias são sugestões baseadas em boas práticas gerais, não em
dados reais de busca da Amazon (não existe API pública pra isso). A
calculadora de preço usa a fórmula pública da KDP, mas os valores
exatos podem mudar - sempre confira na calculadora oficial antes de
fixar um preço de venda de verdade.
"""

import streamlit as st

from estilo import aplicar_estilo, hero
from armazenamento import listar_livros, carregar_livro, salvar_livro
from openrouter_client import chamar_llm
from agents.pesquisa_mercado import pesquisa_palavras_chave_node, pesquisa_categorias_node
from agents.marketing import marketing_lancamento_node
from kdp_rules import calcular_custo_impressao, calcular_royalty_paperback, sugerir_faixa_de_preco, calcular_royalty_ebook, taxa_royalty_paperback
from qualidade_impressao import preflight_livro, analisar_pdf_miolo
from renderizador_editorial import renderizar_miolo_pdf
from agents.capa import gerar_artes_capa, montar_capa_fisica
from pacote_publicacao import normalizar_metadata, checklist_publicacao, disclosure_ia, gerar_pacote_publicacao
from author_profiles import author_display_from_state, cover_credit_from_state

st.set_page_config(page_title="Lançamento", page_icon="🚀", layout="wide")
aplicar_estilo()
hero("🚀 Painel de Lançamento", "Palavras-chave, categorias, preço e material de divulgação — tudo num lugar só.")
st.page_link("pages/22_📐_Publishing_Platform_Engine.py", label="📐 Comparar KDP com outras plataformas / gerar derivados", use_container_width=True)

livros = listar_livros()
if not livros:
    st.info("Nenhum livro salvo ainda.")
    st.stop()

opcoes = {f"{l['titulo']} ({l['colecao']})": l for l in livros}
escolha = st.selectbox("Livro", list(opcoes.keys()))
livro_info = opcoes[escolha]

if "state_lancamento" not in st.session_state or st.session_state.get("livro_lancamento") != escolha:
    st.session_state.state_lancamento = carregar_livro(livro_info["colecao"], livro_info["arquivo"])
    st.session_state.livro_lancamento = escolha
s = st.session_state.state_lancamento

aba_meta, aba_kw, aba_preco, aba_preflight, aba_pdf, aba_capa, aba_ia, aba_marketing, aba_pacote = st.tabs([
    "📝 Metadados",
    "🔑 Palavras-chave e Categorias",
    "💰 Preço e Royalty",
    "🖨️ Preflight KDP",
    "📄 PDF Print Ready",
    "📕 Capa Física Profissional",
    "🤖 Declaração IA",
    "📣 Material de Divulgação",
    "📦 Pacote Final",
])


with aba_meta:
    st.subheader("📝 Metadados editoriais")
    st.caption("Revise com cuidado: título, subtítulo e autoria precisam permanecer consistentes entre os formatos e plataformas.")
    c1,c2=st.columns(2)
    s["titulo"] = c1.text_input("Título", value=s.get("titulo", ""))
    s["subtitulo"] = c2.text_input("Subtítulo", value=s.get("subtitulo", ""))
    c1,c2=st.columns(2)
    credit = author_display_from_state(s)
    if credit:
        c1.text_input("Autoria estruturada", value=credit, disabled=True)
        s["autora"] = credit
    else:
        s["autora"] = c1.text_input("Autor(a) — legado", value=s.get("autora", ""))
    st.page_link("pages/32_✍️_Autores_e_Colaboradores.py", label="✍️ Gerenciar autores, coautores e colaboradores →", use_container_width=True)
    s["idioma_original"] = c2.text_input("Idioma", value=s.get("idioma_original", "pt-BR"))
    s["sinopse_vendas_curta"] = st.text_area("Descrição KDP", value=s.get("sinopse_vendas_curta", ""), height=220, max_chars=4000)
    st.caption(f"{len(s.get('sinopse_vendas_curta',''))}/4000 caracteres")

with aba_kw:
    if st.button("✨ Gerar/atualizar palavras-chave e categorias"):
        with st.spinner("Pesquisando..."):
            s.update(pesquisa_palavras_chave_node(dict(s), chamar_llm))
            s.update(pesquisa_categorias_node(dict(s), chamar_llm))
        st.session_state.state_lancamento = s

    if s.get("palavras_chave_kdp"):
        st.subheader("7 palavras-chave para o campo de keyword da KDP")
        for i, kw in enumerate(s["palavras_chave_kdp"], 1):
            st.write(f"{i}. {kw}")
    if s.get("categorias_sugeridas"):
        st.subheader("Categorias sugeridas")
        st.caption("A KDP permite selecionar até 3 categorias. Confirme a árvore disponível no marketplace escolhido antes de publicar.")
        for cat in s["categorias_sugeridas"]:
            st.write(f"📁 {cat}")

with aba_preco:
    st.caption("Calculadora baseada na fórmula pública da KDP — confirme os valores exatos na calculadora oficial antes de publicar.")
    col1, col2 = st.columns(2)
    paginas = col1.number_input("Total de páginas do miolo", value=s.get("layout_paginas", [{}])[-1].get("pagina", 24) if s.get("layout_paginas") else 24, step=2)
    tipo_papel = col2.selectbox("Tipo de papel/tinta", ["cor_premium", "cor_padrao", "preto_branco"])

    custo = calcular_custo_impressao(int(paginas), tipo_papel)
    faixa = sugerir_faixa_de_preco(custo)

    st.metric("Custo de impressão estimado", f"US$ {custo:.2f}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Preço mínimo viável", f"US$ {faixa['minimo_viavel']:.2f}")
    col2.metric("Sugestão competitiva", f"US$ {faixa['competitivo_sugerido']:.2f}")
    col3.metric("Sugestão premium", f"US$ {faixa['premium_sugerido']:.2f}")

    preco_teste = st.number_input("Testar um preço específico (US$)", value=faixa["competitivo_sugerido"], step=0.5)
    royalty = calcular_royalty_paperback(preco_teste, custo)
    taxa = taxa_royalty_paperback(preco_teste)
    st.write(f"Royalty estimado nesse preço: **US$ {royalty:.2f} por venda** (Amazon.com, taxa de {taxa*100:.0f}% conforme preço atual)")
    if royalty < 0:
        st.error("Esse preço fica ABAIXO do custo de impressão — você perderia dinheiro em cada venda.")

    st.markdown("---")
    st.caption("eBook (sem custo de impressão)")
    preco_ebook = st.number_input("Preço do eBook (US$)", value=4.99, step=0.5, key="preco_ebook")
    try:
        royalty_ebook = calcular_royalty_ebook(preco_ebook, "alta")
        st.write(f"Royalty a 70% (Amazon.com: preço entre $2.99-$12.99; demais condições se aplicam): **US$ {royalty_ebook:.2f}**")
    except ValueError as e:
        st.warning(str(e))
    st.write(f"Royalty a 35% (qualquer preço): **US$ {calcular_royalty_ebook(preco_ebook, 'baixa'):.2f}**")

with aba_preflight:
    st.subheader("🖨️ Preflight profissional de impressão")
    st.caption("Mede pixels reais e calcula PPI efetivo. Não confia apenas no metadado '300 DPI' do arquivo.")
    bleed = st.checkbox("Miolo com bleed (ilustrações até a borda)", value=True)
    if st.button("🔎 Verificar qualidade para impressão", key="rodar_preflight"):
        s["preflight_impressao"] = preflight_livro(dict(s), bleed=bleed)
        st.session_state.state_lancamento = s
    pf = s.get("preflight_impressao") or preflight_livro(dict(s), bleed=bleed)
    c1,c2,c3 = st.columns(3)
    c1.metric("Trim", f"{pf['trim_in'][0]} × {pf['trim_in'][1]} in")
    c2.metric("Arquivo do miolo", f"{pf['pagina_arquivo_in'][0]} × {pf['pagina_arquivo_in'][1]} in")
    c3.metric("Páginas", pf["total_paginas"])
    st.write(f"**Pixels mínimos por página a 300 PPI:** {pf['checks']['pixels_pagina_300ppi'][0]} × {pf['checks']['pixels_pagina_300ppi'][1]} px")
    st.write(f"**Margem externa mínima:** {pf['checks']['margem_externa_minima_in']} in · **Gutter mínimo:** {pf['checks']['gutter_minimo_in']} in")
    if pf["assets"]:
        for a in pf["assets"]:
            icone={"excelente":"🟢","atencao":"🟡","reprovada":"🔴","ausente":"⚫","erro":"🔴"}.get(a["status"],"⚪")
            nome=f"{a['tipo']}" + (f" #{a['numero']}" if a.get('numero') is not None else "")
            st.write(f"{icone} **{nome}** — {a.get('largura_px',0)}×{a.get('altura_px',0)} px · **{a.get('ppi_efetivo',0)} PPI efetivos**")
            if a["status"] != "excelente": st.caption(a["mensagem"])
    else:
        st.info("Ainda não há imagens locais para medir. O preflight será atualizado quando as artes forem geradas/carregadas.")
    if pf["bloqueios"]:
        st.error("Ainda NÃO está pronto para exportação final de impressão.")
        for b in pf["bloqueios"]: st.write(f"• {b}")
    else:
        st.success("As verificações automáticas disponíveis nesta etapa passaram. Ainda faltam validação do PDF, Print Previewer e prova física.")
    with st.expander("Checklist final que continuará bloqueado até o PDF/prova"):
        st.write("☐ Fontes incorporadas no PDF")
        st.write("☐ Páginas individuais, não spreads")
        st.write("☐ Transparências/layers achatados")
        st.write("☐ Sem crop/trim marks, comentários ou placeholders")
        st.write("☐ Capa validada com template/calculadora KDP")
        st.write("☐ Print Previewer KDP revisado")
        st.write("☐ Prova física revisada")

with aba_pdf:
    st.subheader("📄 Renderizador Editorial - Miolo Print Ready")
    st.caption("Gera páginas individuais em PDF, no trim/bleed correto. A capa física continua sendo um arquivo separado.")
    bleed_pdf = st.checkbox("Exportar miolo com bleed", value=True, key="bleed_pdf")
    pf_pdf = preflight_livro(dict(s), bleed=bleed_pdf)

    if pf_pdf["bloqueios"]:
        st.warning("O preflight encontrou bloqueios. Corrija-os antes do PDF final.")
        for b in pf_pdf["bloqueios"]:
            st.write(f"• {b}")
        permitir_prova = st.checkbox("Gerar mesmo assim apenas para PROVA INTERNA", value=False)
    else:
        permitir_prova = False
        st.success("Assets passaram nas verificações automáticas para iniciar a exportação do miolo.")

    if st.button("📘 Gerar PDF do miolo", key="gerar_pdf_miolo"):
        with st.spinner("Montando páginas, margens, bleed e fontes..."):
            resultado_pdf = renderizar_miolo_pdf(dict(s), bleed=bleed_pdf, forcar=permitir_prova)
        if not resultado_pdf.get("ok"):
            st.error(resultado_pdf.get("motivo", "Não foi possível gerar o PDF."))
        else:
            caminho_pdf = resultado_pdf["caminho"]
            analise_pdf = analisar_pdf_miolo(
                caminho_pdf,
                float(s.get("trim_largura_in") or 8.5),
                float(s.get("trim_altura_in") or 8.5),
                bleed=bleed_pdf,
                paginas_esperadas=resultado_pdf["paginas"],
            )
            s["pdf_miolo"] = caminho_pdf
            s["pdf_miolo_config"] = {
                "bleed": bleed_pdf,
                "paginas": resultado_pdf["paginas"],
                "page_size_in": resultado_pdf["page_size_in"],
                "prova_interna_forcada": bool(permitir_prova),
            }
            s["pdf_miolo_preflight"] = analise_pdf
            st.session_state.state_lancamento = s
            st.success(f"PDF gerado com {resultado_pdf['paginas']} páginas.")
            if resultado_pdf.get("avisos"):
                for aviso in resultado_pdf["avisos"]:
                    st.warning(aviso)

    caminho_pdf = s.get("pdf_miolo", "")
    if caminho_pdf and __import__("os").path.exists(caminho_pdf):
        analise = s.get("pdf_miolo_preflight") or analisar_pdf_miolo(
            caminho_pdf, float(s.get("trim_largura_in") or 8.5), float(s.get("trim_altura_in") or 8.5),
            bleed=bool((s.get("pdf_miolo_config") or {}).get("bleed", True)),
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Páginas PDF", analise.get("paginas", 0))
        c2.metric("Tamanho de página", "OK" if analise.get("page_size_correto") else "REVISAR")
        c3.metric("Fontes incorporadas", "OK" if analise.get("fontes_embutidas") else "REVISAR")
        if analise.get("erros"):
            for erro in analise["erros"]:
                st.warning(erro)
        with open(caminho_pdf, "rb") as fh:
            st.download_button(
                "⬇️ Baixar miolo PDF",
                data=fh.read(),
                file_name=__import__("os").path.basename(caminho_pdf),
                mime="application/pdf",
                use_container_width=True,
            )
        st.info("Depois do download: envie ao KDP Print Previewer e peça uma prova física antes da publicação final.")


with aba_capa:
    import os
    st.subheader("📕 Capa Física Profissional — Paperback")
    st.caption("A IA cria apenas as artes. O FaithBloom monta matematicamente contracapa + lombada + capa frontal no tamanho exato do miolo.")

    c1,c2,c3=st.columns(3)
    trim_w=float(s.get("trim_largura_in") or 8.5); trim_h=float(s.get("trim_altura_in") or 8.5)
    paginas_capa=int((s.get("pdf_miolo_config") or {}).get("paginas") or ((s.get("layout_paginas") or [{"pagina":24}])[-1].get("pagina",24)))
    papel_capa=c1.selectbox("Papel/miolo para cálculo da lombada",["cor_premium","cor_padrao","branco","creme"],index=0,key="papel_capa_prof")
    s["tipo_papel_capa"]=papel_capa
    c2.text_input("Crédito de autoria na capa",value=cover_credit_from_state(s),key="autora_capa",disabled=True)
    s["autora"] = author_display_from_state(s) or s.get("autora", "")
    s["subtitulo"]=c3.text_input("Subtítulo (opcional)",value=s.get("subtitulo",""),key="subtitulo_capa")

    st.write(f"**Trim:** {trim_w} × {trim_h} in · **Páginas usadas para lombada:** {paginas_capa}")
    st.info("Para medida final de produção, confira também o KDP Cover Calculator/Template com exatamente o mesmo trim, papel e total de páginas do PDF final.")

    col_gen,col_upload=st.columns(2)
    with col_gen:
        st.markdown("#### ✨ Gerar artes com IA")
        st.caption("Frente e verso são gerados separadamente, sem texto, para não deixar a IA decidir medidas ou tipografia.")
        if st.button("🎨 Gerar artes de frente e contracapa",use_container_width=True,key="gerar_artes_capa_prof"):
            with st.spinner("Gerando duas artes sem tipografia..."):
                s.update(gerar_artes_capa(dict(s), __import__('openrouter_client').gerar_imagem))
            st.session_state.state_lancamento=s
    with col_upload:
        st.markdown("#### 📤 Usar minhas próprias artes")
        up_front=st.file_uploader("Arte frontal sem texto",type=["png","jpg","jpeg"],key="up_capa_front")
        up_back=st.file_uploader("Arte da contracapa sem texto",type=["png","jpg","jpeg"],key="up_capa_back")
        if up_front:
            os.makedirs("uploads_capa",exist_ok=True); path=os.path.join("uploads_capa","frente_"+up_front.name)
            with open(path,"wb") as fh: fh.write(up_front.getbuffer())
            s["arte_capa_frontal"]=path
        if up_back:
            os.makedirs("uploads_capa",exist_ok=True); path=os.path.join("uploads_capa","verso_"+up_back.name)
            with open(path,"wb") as fh: fh.write(up_back.getbuffer())
            s["arte_contracapa"]=path

    if s.get("arte_capa_frontal") or s.get("arte_contracapa"):
        a,b=st.columns(2)
        if s.get("arte_capa_frontal") and os.path.exists(s["arte_capa_frontal"]): a.image(s["arte_capa_frontal"],caption="Arte frontal (master, sem texto)")
        if s.get("arte_contracapa") and os.path.exists(s["arte_contracapa"]): b.image(s["arte_contracapa"],caption="Arte contracapa (master, sem texto)")

    pronto_artes=bool(s.get("arte_capa_frontal") and s.get("arte_contracapa") and os.path.exists(s.get("arte_capa_frontal","")) and os.path.exists(s.get("arte_contracapa","")))
    if pronto_artes:
        if st.button("📐 Montar capa paperback matematicamente",type="primary",use_container_width=True,key="montar_capa_math"):
            with st.spinner("Calculando lombada, bleed, safe areas, barcode e exportando PDF..."):
                result=montar_capa_fisica(s,paginas_capa,papel=papel_capa,pasta_saida="saida_capas")
            st.session_state.state_lancamento=s
            st.success("Capa física montada sem depender da IA para geometria.")

    if s.get("capa_fisica_preview") and os.path.exists(s["capa_fisica_preview"]):
        st.markdown("#### 🔎 Prévia técnica (guias NÃO entram no PDF final)")
        st.image(s["capa_fisica_preview"],use_container_width=True)
        d=s.get("capa_fisica_dimensoes",{})
        c1,c2,c3=st.columns(3)
        c1.metric("Wrap total",f"{d.get('largura_total_in',0):.4f} × {d.get('altura_total_in',0):.4f} in")
        c2.metric("Lombada",f"{d.get('largura_lombada_in',0):.4f} in")
        c3.metric("Texto na lombada","Permitido" if d.get('texto_na_lombada_permitido') else "Não permitido")
        st.caption("Azul = trim/dobras · verde = safe area · vermelho = reserva do barcode. Essas guias existem apenas na prévia.")

    cover_pdf=s.get("capa_fisica_pdf","")
    if cover_pdf and os.path.exists(cover_pdf):
        pf=s.get("capa_fisica_preflight",{})
        if pf.get("ok"): st.success("PDF da capa: 1 página e dimensão física conferida automaticamente.")
        else:
            st.warning("Revise o preflight do PDF da capa.")
            for e in pf.get("erros",[]): st.write(f"• {e}")
        with open(cover_pdf,"rb") as fh:
            st.download_button("⬇️ Baixar capa física PDF",data=fh.read(),file_name=os.path.basename(cover_pdf),mime="application/pdf",use_container_width=True)
        st.warning("Antes de publicar: compare a capa com o template oficial do KDP Cover Calculator e revise no Print Previewer. A prova física continua recomendada.")

with aba_marketing:
    if st.button("✨ Gerar material de divulgação"):
        with st.spinner("Escrevendo..."):
            s.update(marketing_lancamento_node(dict(s), chamar_llm))
        st.session_state.state_lancamento = s

    material = s.get("material_lancamento", {})
    if material:
        st.subheader("📱 Legenda para Instagram")
        st.text_area("", value=material.get("legenda_instagram", ""), height=150, key="ig")
        st.subheader("📌 Descrição para Pinterest")
        st.text_area("", value=material.get("descricao_pinterest", ""), height=100, key="pin")
        st.subheader("✉️ E-mail de lançamento")
        st.text_area("", value=material.get("email_lancamento", ""), height=180, key="email")
        st.subheader("⭐ Pedido de avaliação")
        st.text_area("", value=material.get("pedido_avaliacao", ""), height=120, key="review")


with aba_ia:
    st.subheader("🤖 Registro de conteúdo gerado por IA")
    st.caption("A KDP exige informar conteúdo GERADO por IA (texto, imagens ou traduções). Conteúdo apenas assistido por IA não precisa ser declarado. A decisão final deve ser revisada por você.")
    atual = disclosure_ia(s)
    texto = st.checkbox("Texto gerado por IA", value=atual["texto_gerado_ia"])
    imagens = st.checkbox("Imagens/ilustrações geradas por IA", value=atual["imagens_geradas_ia"])
    traducoes = st.checkbox("Traduções geradas por IA", value=atual["traducoes_geradas_ia"])
    revisado = st.checkbox("Revisei este registro e confirmo que representa o processo real", value=atual["revisado_pela_autora"])
    obs = st.text_area("Observações internas", value=atual["observacoes"], height=100)
    s["disclosure_ia"]={"texto_gerado_ia":texto,"imagens_geradas_ia":imagens,"traducoes_geradas_ia":traducoes,"revisado_pela_autora":revisado,"observacoes":obs}

with aba_pacote:
    st.subheader("📦 Pacote Final de Publicação")
    ck=checklist_publicacao(s)
    c1,c2=st.columns(2)
    c1.metric("Checks aprovados", f"{sum(ck['checks'].values())}/{len(ck['checks'])}")
    c2.metric("Status", "PRONTO" if ck["pronto"] else "PENDÊNCIAS")
    for nome,ok in ck["checks"].items(): st.write(("✅" if ok else "⚠️")+" "+nome.replace("_"," ").title())
    st.info("O ZIP organiza os arquivos e textos para facilitar o upload manual. Ele não publica automaticamente na Amazon e não substitui o KDP Previewer nem a prova física.")
    if st.button("📦 Gerar pacote organizado", type="primary", use_container_width=True):
        resultado=gerar_pacote_publicacao(s)
        s["pacote_publicacao"]=resultado["zip"]
        st.session_state.state_lancamento=s
    pacote=s.get("pacote_publicacao","")
    if pacote and __import__("os").path.exists(pacote):
        with open(pacote,"rb") as fh:
            st.download_button("⬇️ Baixar Pacote de Publicação", data=fh.read(), file_name=__import__("os").path.basename(pacote), mime="application/zip", use_container_width=True)

if st.button("💾 Salvar alterações neste livro"):
    caminho = salvar_livro(dict(s))
    st.success(f"Salvo em: {caminho}")

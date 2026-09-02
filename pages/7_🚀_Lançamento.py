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
from kdp_rules import calcular_custo_impressao, calcular_royalty_paperback, sugerir_faixa_de_preco, calcular_royalty_ebook

st.set_page_config(page_title="Lançamento", page_icon="🚀")
aplicar_estilo()
hero("🚀 Painel de Lançamento", "Palavras-chave, categorias, preço e material de divulgação — tudo num lugar só.")

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

aba_kw, aba_preco, aba_marketing = st.tabs(["🔑 Palavras-chave e Categorias", "💰 Preço e Royalty", "📣 Material de Divulgação"])

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
        st.caption("Escolha 2 na tela do KDP e peça as outras por e-mail de suporte, se quiser mais de 2.")
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
    st.write(f"Royalty estimado nesse preço: **US$ {royalty:.2f} por venda** (canal direto Amazon, 60%)")
    if royalty < 0:
        st.error("Esse preço fica ABAIXO do custo de impressão — você perderia dinheiro em cada venda.")

    st.markdown("---")
    st.caption("eBook (sem custo de impressão)")
    preco_ebook = st.number_input("Preço do eBook (US$)", value=4.99, step=0.5, key="preco_ebook")
    try:
        royalty_ebook = calcular_royalty_ebook(preco_ebook, "alta")
        st.write(f"Royalty a 70% (preço entre $2.99-$9.99): **US$ {royalty_ebook:.2f}**")
    except ValueError as e:
        st.warning(str(e))
    st.write(f"Royalty a 35% (qualquer preço): **US$ {calcular_royalty_ebook(preco_ebook, 'baixa'):.2f}**")

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

if st.button("💾 Salvar alterações neste livro"):
    caminho = salvar_livro(dict(s))
    st.success(f"Salvo em: {caminho}")

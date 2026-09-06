"""
Analisar Livro - visualizar tudo que foi gerado pra um livro salvo:
texto cena a cena, personagens usados (com referência visual),
dedicatória, sinopse, traduções, checklist da KDP.
"""

import streamlit as st
from estilo import aplicar_estilo, hero

from armazenamento import listar_livros, carregar_livro

st.set_page_config(page_title="Analisar Livro", page_icon="🔍", layout="wide")
aplicar_estilo()
hero("🔍 Analisar Livro", "Veja tudo que foi gerado pra um livro salvo.")

livros = listar_livros()
if not livros:
    st.info("Nenhum livro salvo ainda.")
    st.stop()

opcoes = {f"{l['titulo']} ({l['colecao']})": l for l in livros}
escolha = st.selectbox("Livro", list(opcoes.keys()))
livro_info = opcoes[escolha]
s = carregar_livro(livro_info["colecao"], livro_info["arquivo"])

st.header(s.get("titulo", ""))
st.caption(f"Coleção: {s.get('colecao', '')} • Emoção central: {s.get('emocao_central', '')} • "
           f"Versículo: {s.get('versiculo_referencia', '')}")

aba_texto, aba_personagens, aba_extra, aba_lancamento, aba_kdp = st.tabs(
    ["📝 Texto", "👤 Personagens", "💐 Dedicatória / Sinopse / Traduções", "🚀 Lançamento", "✅ Checklist KDP"]
)

with aba_texto:
    st.subheader("Sinopse poética")
    st.write(s.get("sinopse_poetica", "(ainda não gerada)"))

    st.subheader("Cenas")
    for cena in s.get("cenas_texto", []):
        with st.expander(f"Cena {cena['numero']} — emoção: {cena.get('emocao', '')}"):
            st.write(cena.get("texto", ""))
            st.caption(f"Figurino: {cena.get('figurino', '')} • Contexto: {cena.get('contexto_visual', '')}")
            img = next((c for c in s.get("cenas_imagem", []) if c["numero"] == cena["numero"]), None)
            if img:
                st.image(img["caminho_arquivo"])

    st.subheader("Lição final")
    st.write(s.get("licao_final", "(ainda não gerada)"))

with aba_personagens:
    for nome, p in s.get("personagens", {}).items():
        col1, col2 = st.columns([1, 2])
        if p.get("imagem_referencia"):
            col1.image(p["imagem_referencia"], width=200)
        col2.markdown(f"**{nome}** ({p.get('papel', '')})")
        col2.write(p.get("descricao_fixa", ""))
        origem = "📤 imagem enviada pela autora" if p.get("origem_referencia") == "enviada_pela_autora" else "🤖 gerada pelo agente"
        col2.caption(origem)

with aba_extra:
    st.subheader("Dedicatória")
    st.write(s.get("dedicatoria_texto", "(não gerada)"))

    st.subheader("Sinopse de vendas (KDP)")
    st.write(s.get("sinopse_vendas_curta", "(não gerada)"))

    st.subheader("Sinopse de contracapa")
    st.write(s.get("sinopse_contracapa", "(não gerada)"))

    st.subheader("Traduções")
    for idioma, dados in s.get("traducoes", {}).items():
        with st.expander(idioma):
            st.json(dados)

with aba_lancamento:
    st.subheader("🔑 Palavras-chave (KDP)")
    for kw in s.get("palavras_chave_kdp", []):
        st.write(f"• {kw}")
    if not s.get("palavras_chave_kdp"):
        st.caption("(ainda não geradas — use a página 🚀 Lançamento)")

    st.subheader("📁 Categorias sugeridas")
    for cat in s.get("categorias_sugeridas", []):
        st.write(f"📁 {cat}")
    if not s.get("categorias_sugeridas"):
        st.caption("(ainda não geradas — use a página 🚀 Lançamento)")

    material = s.get("material_lancamento", {})
    if material:
        st.subheader("📣 Material de divulgação")
        for chave, rotulo in [
            ("legenda_instagram", "Instagram"), ("descricao_pinterest", "Pinterest"),
            ("email_lancamento", "E-mail"), ("pedido_avaliacao", "Pedido de avaliação"),
        ]:
            if material.get(chave):
                with st.expander(rotulo):
                    st.write(material[chave])
    else:
        st.caption("(ainda não gerado — use a página 🚀 Lançamento)")

with aba_kdp:
    st.json(s.get("checklist_kdp", {}))
    if s.get("capa_fisica_dimensoes"):
        st.subheader("Dimensões da capa física")
        st.json(s["capa_fisica_dimensoes"])

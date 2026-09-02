"""
Frontend Streamlit para livros de colorir (line art) - projeto
separado dos livros com história.

Rodar com:
    export OPENROUTER_API_KEY="sua-chave-aqui"
    pip install streamlit langgraph requests Pillow --break-system-packages
    streamlit run app_colorir.py
"""

import streamlit as st
from estilo import aplicar_estilo, hero

from state_colorir import LivroColorirState, PaginaColorir
from openrouter_client import chamar_llm, gerar_imagem
from agents.gerador_ideias_colorir import gerador_ideias_colorir_node
from agents.line_art_colorir import gerar_pagina_colorir, gerar_capas_colorir
from agents.diagramador_colorir import diagramador_colorir_node
from armazenamento import (
    salvar_livro_colorir, listar_livros_colorir, temas_colorir_usados, salvar_asset_marca,
)

st.set_page_config(page_title="Livros de Colorir", page_icon="🖍️")
aplicar_estilo()
hero("🖍️ Gerador de Livros de Colorir", "Projetos de line art — bichinhos, princesas, carros, o que for.")

with st.sidebar:
    st.subheader("📚 Meus livros de colorir")
    for livro in listar_livros_colorir():
        st.write(f"🖍️ {livro['titulo']}")
        st.caption(livro["tema_geral"])

if "state_c" not in st.session_state:
    st.session_state.state_c = LivroColorirState(paginas=[])
if "etapa_c" not in st.session_state:
    st.session_state.etapa_c = "entrada"

s = st.session_state.state_c

# ---------------------------------------------------------------- ENTRADA
if st.session_state.etapa_c == "entrada":
    modo = st.radio("Como você quer começar?", ["Já tenho a ideia do tema", "Sem ideia — sugira temas"])

    with st.expander("Tamanho do livro e marca/selo (opcional)"):
        col1, col2 = st.columns(2)
        s["trim_largura_in"] = col1.number_input("Largura (polegadas)", value=s.get("trim_largura_in", 8.5), step=0.5)
        s["trim_altura_in"] = col2.number_input("Altura (polegadas)", value=s.get("trim_altura_in", 8.5), step=0.5)
        s["colecao"] = st.text_input(
            "Nome da marca/selo a reaproveitar (opcional)",
            value=s.get("colecao", ""),
            help="Se você já enviou um selo/faixa com esse nome antes (na tela de livros com história "
                 "ou outro livro de colorir), ele é reaproveitado automaticamente.",
        )
        selo_arquivo = st.file_uploader("Selo/emblema (PNG transparente) — vai na contracapa", type=["png"], key="upload_selo_c")
        faixa_arquivo = st.file_uploader("Faixa com o nome (PNG transparente, opcional)", type=["png"], key="upload_faixa_c")
        if selo_arquivo is not None and s.get("colecao"):
            salvar_asset_marca(s["colecao"], "selo", selo_arquivo.getvalue())
        if faixa_arquivo is not None and s.get("colecao"):
            salvar_asset_marca(s["colecao"], "faixa", faixa_arquivo.getvalue())

    if modo == "Já tenho a ideia do tema":
        s["titulo"] = st.text_input("Título do livro", s.get("titulo", ""))
        s["tema_geral"] = st.text_input("Tema geral", s.get("tema_geral", ""), placeholder="ex: Aviões fofos ao redor do mundo")
        s["precisa_codigo_sexo"] = st.checkbox(
            "Esse tema tem personagens com gênero (bichinhos, princesas, heróis)?",
            value=s.get("precisa_codigo_sexo", False),
        )
        if st.button("Continuar") and s["titulo"] and s["tema_geral"]:
            st.session_state.etapa_c = "paginas"
            st.rerun()
    else:
        if st.button("✨ Sugerir temas de livro de colorir"):
            with st.spinner("Pensando em temas novos..."):
                st.session_state.ideias_colorir = gerador_ideias_colorir_node(
                    4, temas_colorir_usados(), chamar_llm
                )
        for ideia in st.session_state.get("ideias_colorir", []):
            with st.container(border=True):
                st.markdown(f"**{ideia.get('titulo_sugerido', '')}**")
                st.caption(ideia.get("tema_geral", ""))
                st.caption(f"Sugestões: {', '.join(ideia.get('sugestoes_paginas', [])[:4])}...")
                if st.button("Usar este tema", key=f"usar_c_{ideia.get('titulo_sugerido', '')}"):
                    s["titulo"] = ideia.get("titulo_sugerido", "")
                    s["tema_geral"] = ideia.get("tema_geral", "")
                    s["precisa_codigo_sexo"] = ideia.get("precisa_codigo_sexo", False)
                    s["paginas"] = [
                        PaginaColorir(nome=nome, categoria=nome, sexo="", cena=f"{nome}, pose simples e fofa")
                        for nome in ideia.get("sugestoes_paginas", [])
                    ]
                    st.session_state.etapa_c = "paginas"
                    st.rerun()

# ---------------------------------------------------------------- PÁGINAS
elif st.session_state.etapa_c == "paginas":
    st.subheader(f"📖 {s.get('titulo', '')}")
    st.caption(s.get("tema_geral", ""))

    nome = st.text_input("Nome/assunto da página", placeholder="ex: Leãozinho no campo")
    categoria = st.text_input("Categoria", placeholder="ex: leão, avião, princesa")
    sexo = ""
    if s.get("precisa_codigo_sexo"):
        sexo = st.selectbox("Código visual", ["macho", "femea"])
    cena = st.text_area("Cena/pose", placeholder="ex: sentado no campo, sorrindo pro sol")

    if st.button("Adicionar página") and nome:
        s.setdefault("paginas", []).append(
            PaginaColorir(nome=nome, categoria=categoria, sexo=sexo, cena=cena)
        )

    for i, p in enumerate(s.get("paginas", [])):
        st.write(f"{i+1}. {p['nome']} ({p.get('categoria', '')}) {('- ' + p['sexo']) if p.get('sexo') else ''}")

    if st.button("Gerar todas as páginas") and s.get("paginas"):
        st.session_state.etapa_c = "gerando"
        st.rerun()

# ---------------------------------------------------------------- GERANDO
elif st.session_state.etapa_c == "gerando":
    progresso = st.progress(0, text="Gerando páginas de line art...")
    total = len(s["paginas"])
    for i, pagina in enumerate(s["paginas"]):
        caminho = gerar_pagina_colorir(
            pagina["nome"], pagina.get("categoria", ""), pagina.get("cena", ""),
            gerar_imagem, sexo=pagina.get("sexo") or None,
        )
        s["paginas"][i]["caminho_arquivo"] = caminho
        progresso.progress(int((i + 1) / total * 85), text=f"Página {i+1}/{total}...")

    progresso.progress(88, text="Diagramando e validando com a KDP...")
    s.update(diagramador_colorir_node(dict(s)))

    progresso.progress(90, text="Gerando capa eBook e capa física (wraparound)...")
    resultado_capas = gerar_capas_colorir(dict(s), gerar_imagem)
    s["capa_ebook"] = resultado_capas["capa_ebook"]
    s["capa_fisica_wrap"] = resultado_capas["capa_fisica_wrap"]
    s["capa_fisica_dimensoes"] = resultado_capas["capa_fisica_dimensoes"]
    s["pacote_pronto"] = True
    progresso.progress(100, text="Pronto!")

    caminho_salvo = salvar_livro_colorir(dict(s))
    st.session_state.caminho_salvo_c = caminho_salvo
    st.session_state.etapa_c = "resultado"
    st.rerun()

# -------------------------------------------------------------- RESULTADO
elif st.session_state.etapa_c == "resultado":
    st.success("Livro de colorir pronto!")
    st.caption(f"Salvo em: {st.session_state.get('caminho_salvo_c', '')}")
    st.caption(f"Miolo final: {s.get('paginas_fisicas_total', '?')} páginas (cada desenho impresso só na "
               "frente, com verso em branco pra evitar que giz de cera/marcador atravesse o papel — "
               "por isso o total é quase o dobro do nº de desenhos)")
    if s.get("checklist_kdp"):
        st.json(s["checklist_kdp"])

    st.subheader("📕 Capa e Contracapa")
    st.caption("Dois arquivos separados do miolo, como a KDP exige.")
    col1, col2 = st.columns(2)
    if s.get("capa_ebook"):
        col1.image(s["capa_ebook"], caption="Capa para eBook")
        with open(s["capa_ebook"], "rb") as f:
            col1.download_button("⬇️ Baixar capa eBook", f, file_name="capa_ebook_colorir.png")
    if s.get("capa_fisica_wrap"):
        dim = s.get("capa_fisica_dimensoes", {})
        col2.image(s["capa_fisica_wrap"], caption=(
            f"Capa física wraparound — {dim.get('largura_total_in', '?')}\"x"
            f"{dim.get('altura_total_in', '?')}\" ({dim.get('dpi', 300)} DPI)"
        ))
        with open(s["capa_fisica_wrap"], "rb") as f:
            col2.download_button("⬇️ Baixar capa física (wraparound)", f, file_name="capa_fisica_wrap_colorir.png")

    st.subheader("🖍️ Páginas")
    cols = st.columns(3)
    for i, p in enumerate(s.get("paginas", [])):
        if p.get("caminho_arquivo"):
            cols[i % 3].image(p["caminho_arquivo"], caption=p["nome"])

    if st.button("Começar novo livro de colorir"):
        st.session_state.state_c = LivroColorirState(paginas=[])
        st.session_state.etapa_c = "entrada"
        st.rerun()

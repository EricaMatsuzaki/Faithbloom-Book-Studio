"""
Frontend Streamlit para RETOMAR um livro que já tem roteiro pronto
(ex: o livro de Natal que ficou pela metade) - pula Curador de Tema,
Roteirista e Revisor, e vai direto para Ilustrador em diante.

Rodar com:
    export OPENROUTER_API_KEY="sua-chave-aqui"
    pip install streamlit langgraph requests --break-system-packages
    streamlit run app_retomar.py

Como usar:
1. Escreva o roteiro no mesmo formato de historia_natal.py (uma lista
   de CenaTexto + PersonagemDNA + título/versículo/lição) e salve como
   um arquivo .py na pasta do projeto.
2. Rode esta tela e informe o nome do módulo (ex: "historia_natal").
3. Preencha a lista de dedicatória na tela (ou pule, se quiser rodar
   sem dedicatória dinâmica).
4. Aprove a referência visual dos personagens antes de ilustrar tudo.
"""

import importlib
import os

import streamlit as st

from openrouter_client import chamar_llm, gerar_imagem, gerar_audio
from agents.ilustrador import gerar_referencia_personagem, ilustrador_node
from agents.atividades_colorir import atividades_colorir_node
from agents.audiobook import audiobook_node, narracao_node
from agents.dedicatoria import dedicatoria_node
from agents.tradutor import tradutor_node
from agents.sinopse import sinopse_node
from agents.diagramador import diagramador_node
from agents.capa import capa_node
from armazenamento import salvar_livro, listar_livros

st.set_page_config(page_title="Retomar Livro", page_icon="📚")
st.title("📚 Retomar um livro com roteiro pronto")

with st.sidebar:
    st.subheader("📚 Meus livros salvos")
    for livro in listar_livros():
        status = "✅" if livro["pacote_pronto"] else "🔧"
        st.write(f"{status} {livro['titulo']}")
st.caption(
    "Use esta tela quando a história já está escrita e revisada (como o "
    "livro de Natal) - ela pula direto para ilustração, audiobook, "
    "dedicatória, tradução e diagramação."
)

if "state_r" not in st.session_state:
    st.session_state.state_r = None
if "etapa_r" not in st.session_state:
    st.session_state.etapa_r = "carregar"

s = st.session_state.state_r

# --------------------------------------------------------------- CARREGAR
if st.session_state.etapa_r == "carregar":
    nome_modulo = st.text_input(
        "Nome do arquivo com o roteiro (sem .py)",
        value="historia_natal",
        help="O arquivo precisa ter uma variável ESTADO_INICIAL_NATAL "
             "(ou renomeie a variável abaixo) no formato de state.LivroState.",
    )
    nome_variavel = st.text_input("Nome da variável de estado no arquivo", value="ESTADO_INICIAL_NATAL")

    if st.button("Carregar roteiro"):
        try:
            modulo = importlib.import_module(nome_modulo)
            estado_carregado = getattr(modulo, nome_variavel)
            st.session_state.state_r = dict(estado_carregado)
            st.session_state.etapa_r = "revisar_personagens"
            st.rerun()
        except Exception as e:
            st.error(f"Não consegui carregar: {e}")

# ------------------------------------------------- REVISAR PERSONAGENS
elif st.session_state.etapa_r == "revisar_personagens":
    st.subheader(f"📖 {s.get('titulo', '(sem título)')}")
    st.write(f"**{len(s.get('cenas_texto', []))} cenas** carregadas • "
             f"Versículo: {s.get('versiculo_referencia', '-')}")

    st.markdown("### Personagens")
    for nome, p in s.get("personagens", {}).items():
        with st.expander(f"{nome} ({p.get('papel', '')})"):
            nova_descricao = st.text_area(
                f"DNA fixo de {nome}", value=p.get("descricao_fixa", ""), key=f"dna_{nome}"
            )
            s["personagens"][nome]["descricao_fixa"] = nova_descricao

            origem = st.radio(
                f"Referência visual de {nome}",
                ["Deixar o agente criar", "Enviar minha própria imagem"],
                key=f"origem_{nome}",
            )
            if origem == "Enviar minha própria imagem":
                arquivo = st.file_uploader(f"Imagem de {nome}", type=["png", "jpg", "jpeg"], key=f"upload_{nome}")
                if arquivo is not None:
                    caminho = os.path.join("saida_imagens", f"ref_{nome}.png")
                    os.makedirs("saida_imagens", exist_ok=True)
                    with open(caminho, "wb") as f:
                        f.write(arquivo.getbuffer())
                    s["personagens"][nome]["imagem_referencia"] = caminho
                    s["personagens"][nome]["origem_referencia"] = "enviada_pela_autora"

    st.markdown("### Dedicatória (opcional)")
    st.caption("Preencha para gerar a Dedicatória Dinâmica, ou deixe em branco para pular. "
               "Essa lista NÃO é salva no código do projeto — fica só nesta sessão e no "
               "arquivo local do livro salvo (ver README sobre não versionar dados pessoais).")
    texto_dedicatoria = st.text_area(
        "Uma pessoa por linha: Nome - relação - opcional \"in memoriam\" "
        "(ex: Sedinei - mãe / Keiichi - pai - in memoriam)",
        height=120,
    )
    if texto_dedicatoria.strip():
        lista = []
        for linha in texto_dedicatoria.strip().splitlines():
            partes = [p.strip() for p in linha.split("-")]
            if len(partes) >= 2:
                in_memoriam = len(partes) >= 3 and "memoriam" in partes[2].lower()
                lista.append({"pessoa": partes[0], "relacao": partes[1], "in_memoriam": in_memoriam})
        s["lista_dedicatoria"] = lista

    if st.button("Gerar referência visual dos personagens"):
        st.session_state.etapa_r = "gerando_referencia"
        st.rerun()

# -------------------------------------------------- GERANDO REFERÊNCIA
elif st.session_state.etapa_r == "gerando_referencia":
    with st.spinner("Gerando/confirmando referência visual..."):
        for nome, p in s["personagens"].items():
            s["personagens"][nome] = gerar_referencia_personagem(p, gerar_imagem)
    st.session_state.etapa_r = "aprovar_referencia"
    st.rerun()

# --------------------------------------------------- APROVAR REFERÊNCIA
elif st.session_state.etapa_r == "aprovar_referencia":
    st.subheader("Compare com o livro anterior antes de seguir")
    for nome, p in s["personagens"].items():
        st.image(p["imagem_referencia"], caption=nome, width=280)
    col1, col2 = st.columns(2)
    if col1.button("✅ Está consistente, ilustrar o livro inteiro"):
        st.session_state.etapa_r = "processando"
        st.rerun()
    if col2.button("🔁 Gerar de novo"):
        st.session_state.etapa_r = "gerando_referencia"
        st.rerun()

# ------------------------------------------------------------ PROCESSANDO
elif st.session_state.etapa_r == "processando":
    progresso = st.progress(0, text="Ilustrando cada cena...")
    s.update(ilustrador_node(dict(s), gerar_imagem))
    progresso.progress(35, text="Gerando páginas de colorir...")
    s.update(atividades_colorir_node(dict(s), gerar_imagem))
    progresso.progress(45, text="Gerando roteiro de audiobook...")
    s.update(audiobook_node(dict(s), chamar_llm))
    progresso.progress(50, text="Narrando (TTS)...")
    s.update(narracao_node(dict(s), gerar_audio))
    if s.get("lista_dedicatoria"):
        progresso.progress(60, text="Escrevendo a dedicatória...")
        s.update(dedicatoria_node(dict(s), chamar_llm))
    progresso.progress(75, text="Traduzindo...")
    s.update(tradutor_node(dict(s), chamar_llm))
    progresso.progress(88, text="Gerando sinopse de vendas...")
    s.update(sinopse_node(dict(s), chamar_llm))
    progresso.progress(95, text="Diagramando e validando com a KDP...")
    s.update(diagramador_node(dict(s)))
    progresso.progress(97, text="Gerando capa (eBook) e capa física (wraparound)...")
    s.update(capa_node(dict(s), gerar_imagem))
    progresso.progress(100, text="Pronto!")
    caminho_salvo = salvar_livro(dict(s))
    st.session_state.caminho_salvo_r = caminho_salvo
    st.session_state.etapa_r = "resultado"
    st.rerun()

# --------------------------------------------------------------- RESULTADO
elif st.session_state.etapa_r == "resultado":
    st.success("Livro processado!" if s["pacote_pronto"] else "Quase lá — falta ajustar o checklist.")
    st.caption(f"Salvo em: {st.session_state.get('caminho_salvo_r', '')}")
    st.json(s["checklist_kdp"])

    if s.get("capa_ebook") or s.get("capa_fisica_wrap"):
        st.subheader("📕 Capa e Contracapa")
        col1, col2 = st.columns(2)
        if s.get("capa_ebook"):
            col1.image(s["capa_ebook"], caption="Capa para eBook")
        if s.get("capa_fisica_wrap"):
            col2.image(s["capa_fisica_wrap"], caption="Capa física (wraparound)")

    st.subheader("🎨 Ilustrações")
    for cena in s.get("cenas_imagem", []):
        st.image(cena["caminho_arquivo"], caption=f"Cena {cena['numero']}")

    st.subheader("🖍️ Páginas de colorir")
    cols = st.columns(3)
    for col, pagina in zip(cols, s.get("paginas_colorir", [])):
        col.image(pagina["caminho_arquivo"], caption=f"Cena {pagina['numero']} - line-art")

    st.subheader("🎧 Audiobook")
    audios_por_numero = {a["numero"]: a["caminho_arquivo"] for a in s.get("audio_gerado", [])}
    for trecho in s.get("roteiro_audiobook", []):
        st.text(trecho.get("texto_narrado", ""))
        caminho_audio = audios_por_numero.get(trecho["numero"])
        if caminho_audio:
            st.audio(caminho_audio)

    if s.get("dedicatoria_texto"):
        st.subheader("💐 Dedicatória")
        st.write(s["dedicatoria_texto"])

    st.subheader("📝 Sinopse de vendas")
    st.write(s.get("sinopse_vendas_curta", ""))

    if st.button("Retomar outro livro"):
        st.session_state.state_r = None
        st.session_state.etapa_r = "carregar"
        st.rerun()

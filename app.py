"""
Frontend Streamlit para o gerador de livros infantis.

Rodar com:
    export OPENROUTER_API_KEY="sua-chave-aqui"
    pip install streamlit langgraph requests --break-system-packages
    streamlit run app.py

Fluxo da tela:
1. Autora escolhe: "Só tenho um tema/resumo" OU "Quero preencher tudo".
2. Se escolheu tema livre, o Curador de Tema sugere emoção/versículo/
   lição/título - a autora pode ACEITAR ou EDITAR antes de seguir
   (nunca gera a história sem essa confirmação).
3. Roda o restante do pipeline com barra de progresso por etapa.
4. Mostra a character sheet do(s) personagem(ns) para aprovação ANTES
   de gerar as 24+ cenas (evita gastar créditos de imagem à toa).
5. Ao final, mostra o pacote pronto + checklist de publicação KDP.
"""

import os

import streamlit as st

from state import LivroState, PersonagemDNA
from openrouter_client import chamar_llm, gerar_imagem, gerar_audio
from armazenamento import salvar_livro, listar_livros, listar_colecoes, carregar_biblioteca_personagens, salvar_asset_marca
from agents.curador_tema import curador_tema_node
from agents.gerador_ideias import gerador_ideias_node
from agents.criador_personagem import criar_personagem_a_partir_de_ideia
from agents.roteirista import roteirista_node
from agents.revisor import revisor_node
from agents.ilustrador import gerar_referencia_personagem, ilustrador_node
from agents.atividades_colorir import atividades_colorir_node
from agents.audiobook import audiobook_node, narracao_node
from agents.dedicatoria import dedicatoria_node
from agents.tradutor import tradutor_node
from agents.sinopse import sinopse_node
from agents.diagramador import diagramador_node
from agents.capa import capa_node

st.set_page_config(page_title="Pequenas Histórias, Grandes Lições", page_icon="📖")
st.title("📖 Gerador de Livros Infantis - Erica Matsuzaki")

with st.sidebar:
    st.subheader("📚 Meus livros salvos")
    livros = listar_livros()
    if not livros:
        st.caption("Nenhum livro salvo ainda.")
    for livro in livros:
        status = "✅" if livro["pacote_pronto"] else "🔧"
        st.write(f"{status} {livro['titulo']}")
        st.caption(f"— {livro['colecao']}")
    st.caption("Arquivos locais (ver README sobre o roadmap de banco de dados).")

if "state" not in st.session_state:
    st.session_state.state = LivroState(paginas_minimas=24, idiomas_alvo=[])
if "etapa" not in st.session_state:
    st.session_state.etapa = "colecao"

s = st.session_state.state

# --------------------------------------------------------------- COLEÇÃO
if st.session_state.etapa == "colecao":
    st.subheader("Qual coleção é este livro?")
    st.caption("Cada coleção tem sua própria biblioteca de personagens — "
               "personagens de uma coleção não aparecem nas outras.")
    colecoes_existentes = listar_colecoes()

    if colecoes_existentes:
        escolha = st.radio("Coleções existentes", colecoes_existentes + ["Criar nova coleção"])
    else:
        escolha = "Criar nova coleção"

    nome_colecao = None
    if escolha == "Criar nova coleção":
        nome_colecao = st.text_input(
            "Nome da nova coleção",
            placeholder="ex: Aventuras da Floresta Encantada",
        )
    else:
        nome_colecao = escolha

    with st.expander("Tamanho do livro e marca da coleção (opcional)"):
        col1, col2 = st.columns(2)
        largura = col1.number_input("Largura (polegadas)", value=8.5, step=0.5)
        altura = col2.number_input("Altura (polegadas)", value=8.5, step=0.5)
        st.caption("Padrão pra livro infantil ilustrado quadrado é 8.5x8.5\". "
                   "A capa é calculada automaticamente a partir disso.")

        selo_arquivo = st.file_uploader(
            "Selo/emblema da coleção (PNG com fundo transparente) — vai na contracapa",
            type=["png"], key="upload_selo",
        )
        faixa_arquivo = st.file_uploader(
            "Faixa com o nome da coleção (PNG com fundo transparente, opcional) — "
            "se não enviar, o sistema desenha uma faixa simples automaticamente",
            type=["png"], key="upload_faixa",
        )

    if st.button("Começar livro nesta coleção") and nome_colecao:
        s["colecao"] = nome_colecao
        s["trim_largura_in"] = largura
        s["trim_altura_in"] = altura
        if escolha == "Criar nova coleção":
            s["personagens"] = {}
            st.session_state.biblioteca_colecao = {}
        else:
            s["personagens"] = {}
            st.session_state.biblioteca_colecao = carregar_biblioteca_personagens(nome_colecao)
        if selo_arquivo is not None:
            salvar_asset_marca(nome_colecao, "selo", selo_arquivo.getvalue())
        if faixa_arquivo is not None:
            salvar_asset_marca(nome_colecao, "faixa", faixa_arquivo.getvalue())
        st.session_state.etapa = "entrada"
        st.rerun()

# ---------------------------------------------------------------- ENTRADA
elif st.session_state.etapa == "entrada":
    st.caption(f"Coleção: **{s.get('colecao', '')}**")
    modo = st.radio(
        "Como você quer começar?",
        [
            "Só tenho um tema ou resumo livre",
            "Quero preencher tudo manualmente",
            "Não tenho ideia nenhuma — sugira temas",
        ],
    )

    if modo == "Só tenho um tema ou resumo livre":
        entrada = st.text_area(
            "Descreva o tema ou um resumo curto da ideia",
            placeholder="ex: uma gatinha impaciente que precisa aprender a esperar...",
        )
        if st.button("Sugerir versículo, emoção e lição") and entrada:
            with st.spinner("Buscando o versículo e a lição que combinam..."):
                s["_entrada_tema_livre"] = entrada
                s.update(curador_tema_node(dict(s), chamar_llm))
            st.session_state.etapa = "confirmar_curadoria"
            st.rerun()

    elif modo == "Quero preencher tudo manualmente":
        s["titulo"] = st.text_input("Título", s.get("titulo", ""))
        s["emocao_central"] = st.text_input("Emoção central", s.get("emocao_central", ""))
        s["aprendizado_cristao"] = st.text_input("Aprendizado cristão", s.get("aprendizado_cristao", ""))
        s["versiculo_referencia"] = st.text_input("Versículo (referência)", s.get("versiculo_referencia", ""))
        if st.button("Continuar"):
            st.session_state.etapa = "personagens"
            st.rerun()

    else:  # Não tenho ideia nenhuma
        temas_usados = [l["titulo"] for l in listar_livros()]
        if st.button("✨ Sugerir ideias de tema"):
            with st.spinner("Pensando em ideias novas..."):
                st.session_state.ideias_sugeridas = gerador_ideias_node(4, temas_usados, chamar_llm)
        for ideia in st.session_state.get("ideias_sugeridas", []):
            with st.container(border=True):
                st.markdown(f"**{ideia.get('titulo_sugerido', '')}**")
                st.caption(f"Situação: {ideia.get('situacao', '')}")
                st.caption(f"Emoção: {ideia.get('emocao_central', '')} • Lição: {ideia.get('pista_licao', '')}")
                if st.button("Usar esta ideia", key=f"usar_{ideia.get('titulo_sugerido', '')}"):
                    s["titulo"] = ideia.get("titulo_sugerido", "")
                    s["emocao_central"] = ideia.get("emocao_central", "")
                    s["aprendizado_cristao"] = ideia.get("pista_licao", "")
                    s["_entrada_tema_livre"] = ideia.get("situacao", "")
                    with st.spinner("Buscando o versículo que combina..."):
                        s.update(curador_tema_node(dict(s), chamar_llm))
                    st.session_state.etapa = "confirmar_curadoria"
                    st.rerun()

# --------------------------------------------------- CONFIRMAR CURADORIA
elif st.session_state.etapa == "confirmar_curadoria":
    st.subheader("Sugestão do Curador de Tema")
    st.caption(s.get("_justificativa_curadoria", ""))
    s["titulo"] = st.text_input("Título", s.get("titulo", ""))
    s["emocao_central"] = st.text_input("Emoção central", s.get("emocao_central", ""))
    s["aprendizado_cristao"] = st.text_input("Aprendizado cristão", s.get("aprendizado_cristao", ""))
    s["versiculo_referencia"] = st.text_input("Versículo (referência)", s.get("versiculo_referencia", ""))
    st.info("Edite qualquer campo acima se quiser trocar a sugestão antes de seguir.")
    if st.button("Confirmar e continuar"):
        st.session_state.etapa = "personagens"
        st.rerun()

# ------------------------------------------------------------ PERSONAGENS
elif st.session_state.etapa == "personagens":
    st.subheader("Personagens da história")

    biblioteca = st.session_state.get("biblioteca_colecao", {})
    if biblioteca:
        st.markdown("**Personagens já existentes nesta coleção:**")
        for nome_p, dados_p in biblioteca.items():
            ja_incluido = nome_p in s.get("personagens", {})
            incluir = st.checkbox(f"{nome_p} ({dados_p.get('papel', '')})", value=ja_incluido, key=f"incluir_{nome_p}")
            if incluir:
                s.setdefault("personagens", {})[nome_p] = dados_p
            elif nome_p in s.get("personagens", {}):
                del s["personagens"][nome_p]

    st.markdown("**Adicionar um personagem novo:**")
    st.caption("Use isto quando a história pedir alguém que ainda não existe na coleção.")

    papel = st.selectbox("Papel", ["protagonista", "mentor", "guia sábio", "amigo"])

    modo_personagem = st.radio(
        "Como definir este personagem?",
        ["Escrever eu mesma a descrição (DNA)", "Deixar a IA sugerir a partir de uma ideia curta"],
    )

    if modo_personagem == "Escrever eu mesma a descrição (DNA)":
        nome = st.text_input("Nome do personagem")
        descricao = st.text_area("Descrição fixa (DNA - nunca muda entre cenas)")
    else:
        ideia_curta = st.text_input(
            "Ideia curta do personagem",
            placeholder="ex: um coelhinho tímido que tem medo de altura",
        )
        if st.button("✨ Gerar sugestão de personagem") and ideia_curta:
            with st.spinner("Criando o DNA visual do personagem..."):
                sugestao = criar_personagem_a_partir_de_ideia(ideia_curta, papel, chamar_llm)
                st.session_state.personagem_sugerido = sugestao
        sugestao = st.session_state.get("personagem_sugerido")
        if sugestao:
            nome = st.text_input("Nome do personagem", value=sugestao["nome"])
            descricao = st.text_area("Descrição fixa (DNA - edite se quiser)", value=sugestao["descricao_fixa"])
        else:
            nome, descricao = "", ""

    origem = st.radio(
        "Como definir a aparência dele?",
        ["Deixar o agente criar a partir da descrição", "Enviar minha própria imagem de referência"],
    )

    imagem_enviada = None
    if origem == "Enviar minha própria imagem de referência":
        imagem_enviada = st.file_uploader(
            "Imagem de referência (frente, bem iluminada, de preferência)",
            type=["png", "jpg", "jpeg"],
        )

    if st.button("Adicionar personagem") and nome:
        novo = PersonagemDNA(
            nome=nome, descricao_fixa=descricao, imagem_referencia="",
            origem_referencia="", papel=papel,
        )
        if imagem_enviada is not None:
            caminho = os.path.join("saida_imagens", f"ref_{nome}.png")
            os.makedirs("saida_imagens", exist_ok=True)
            with open(caminho, "wb") as f:
                f.write(imagem_enviada.getbuffer())
            novo["imagem_referencia"] = caminho
            novo["origem_referencia"] = "enviada_pela_autora"
        s.setdefault("personagens", {})[nome] = novo

    for p_nome, p in s.get("personagens", {}).items():
        origem_label = "📤 imagem enviada por você" if p.get("origem_referencia") == "enviada_pela_autora" else "🤖 o agente vai criar"
        st.write(f"✅ {p_nome} — {origem_label}")
        if p.get("imagem_referencia"):
            st.image(p["imagem_referencia"], width=150)

    st.markdown("**Dedicatória (opcional):**")
    st.caption("Essa lista NÃO fica salva no código do projeto — só nesta sessão e no "
               "arquivo local do livro (nunca é commitada no repositório).")
    texto_dedicatoria = st.text_area(
        "Uma pessoa por linha: Nome - relação - opcional \"in memoriam\"",
        height=100, key="dedicatoria_zero",
    )
    if texto_dedicatoria.strip():
        lista = []
        for linha in texto_dedicatoria.strip().splitlines():
            partes = [p.strip() for p in linha.split("-")]
            if len(partes) >= 2:
                in_memoriam = len(partes) >= 3 and "memoriam" in partes[2].lower()
                lista.append({"pessoa": partes[0], "relacao": partes[1], "in_memoriam": in_memoriam})
        s["lista_dedicatoria"] = lista

    if st.button("Gerar histórias e ilustrações") and s.get("personagens"):
        st.session_state.etapa = "gerando"
        st.rerun()

# --------------------------------------------------------------- GERANDO
elif st.session_state.etapa == "gerando":
    progresso = st.progress(0, text="Roteirista escrevendo a história...")
    s.update(roteirista_node(dict(s), chamar_llm))
    progresso.progress(50, text="Revisor checando continuidade...")
    s.update(revisor_node(dict(s), chamar_llm))

    if not s.get("revisao_aprovada"):
        st.warning("O Revisor pediu ajustes:")
        st.write(s.get("notas_revisor", []))
        st.session_state.etapa = "entrada"
        st.stop()

    st.session_state.etapa = "revisar_texto"
    st.rerun()

# ----------------------------------------------------- REVISAR TEXTO
elif st.session_state.etapa == "revisar_texto":
    st.subheader("Revise o texto antes de ilustrar")
    st.caption("O Revisor automático já aprovou, mas você pode editar qualquer frase antes de seguir.")
    for cena in s.get("cenas_texto", []):
        with st.expander(f"Cena {cena['numero']} — emoção: {cena.get('emocao', '')}"):
            cena["texto"] = st.text_area(
                "Texto", value=cena.get("texto", ""), key=f"texto_{cena['numero']}"
            )
            cena["figurino"] = st.text_input(
                "Figurino desta cena", value=cena.get("figurino", ""), key=f"figurino_{cena['numero']}"
            )
    if st.button("Aprovar texto e gerar referência dos personagens"):
        st.session_state.etapa = "gerando_referencia"
        st.rerun()

# -------------------------------------------------- GERANDO REFERÊNCIA
elif st.session_state.etapa == "gerando_referencia":
    progresso = st.progress(0, text="Gerando referência visual dos personagens...")
    for nome_p, personagem in s["personagens"].items():
        s["personagens"][nome_p] = gerar_referencia_personagem(personagem, gerar_imagem)

    st.session_state.etapa = "aprovar_personagens"
    st.rerun()

# ------------------------------------------------- APROVAR PERSONAGENS
elif st.session_state.etapa == "aprovar_personagens":
    st.subheader("Aprove a aparência dos personagens antes de continuar")
    st.caption("Isso evita gerar 24+ cenas com um personagem que ainda não ficou bom.")
    for nome_p, personagem in s["personagens"].items():
        st.image(personagem["imagem_referencia"], caption=nome_p, width=300)
    col1, col2 = st.columns(2)
    if col1.button("✅ Aprovado, gerar o livro inteiro"):
        st.session_state.etapa = "finalizando"
        st.rerun()
    if col2.button("🔁 Gerar referência de novo"):
        st.session_state.etapa = "gerando"
        st.rerun()

# ------------------------------------------------------------ FINALIZANDO
elif st.session_state.etapa == "finalizando":
    progresso = st.progress(0, text="Ilustrando cada cena...")
    s.update(ilustrador_node(dict(s), gerar_imagem))
    progresso.progress(35, text="Gerando 3 páginas de colorir (line-art)...")
    s.update(atividades_colorir_node(dict(s), gerar_imagem))
    progresso.progress(42, text="Gerando roteiro de audiobook...")
    s.update(audiobook_node(dict(s), chamar_llm))
    progresso.progress(46, text="Narrando o audiobook (TTS)...")
    s.update(narracao_node(dict(s), gerar_audio))
    progresso.progress(50, text="Escrevendo a dedicatória...")
    s.update(dedicatoria_node(dict(s), chamar_llm))
    progresso.progress(55, text="Traduzindo para os idiomas escolhidos...")
    s.update(tradutor_node(dict(s), chamar_llm))
    progresso.progress(75, text="Gerando sinopse de vendas...")
    s.update(sinopse_node(dict(s), chamar_llm))
    progresso.progress(90, text="Diagramando e validando com a KDP...")
    s.update(diagramador_node(dict(s)))
    progresso.progress(96, text="Gerando capa (eBook) e capa física (wraparound)...")
    s.update(capa_node(dict(s), gerar_imagem))
    progresso.progress(100, text="Pronto!")

    caminho_salvo = salvar_livro(dict(s))
    st.session_state.etapa = "resultado_zero"
    st.session_state.caminho_salvo = caminho_salvo
    st.rerun()

# --------------------------------------------------------------- RESULTADO
elif st.session_state.etapa == "resultado_zero":

    st.success("Pacote pronto para revisão final." if s["pacote_pronto"] else "Quase lá - falta ajustar alguns itens do checklist.")
    st.caption(f"Salvo em: {st.session_state.get('caminho_salvo', '')} "
               "(arquivo local — ver README sobre o roadmap de banco de dados real)")
    st.json(s["checklist_kdp"])

    st.subheader("📕 Capa e Contracapa")
    st.caption("Dois arquivos separados do miolo, como a KDP exige — cada um com o download próprio.")
    col1, col2 = st.columns(2)
    if s.get("capa_ebook"):
        col1.image(s["capa_ebook"], caption="Capa para eBook (arte frontal só)")
        with open(s["capa_ebook"], "rb") as f:
            col1.download_button("⬇️ Baixar capa eBook", f, file_name="capa_ebook.png")
    if s.get("capa_fisica_wrap"):
        dim = s.get("capa_fisica_dimensoes", {})
        col2.image(s["capa_fisica_wrap"], caption=(
            f"Capa física wraparound — {dim.get('largura_total_in', '?')}\"x"
            f"{dim.get('altura_total_in', '?')}\" ({dim.get('dpi', 300)} DPI), "
            f"lombada {dim.get('largura_lombada_in', '?')}\""
        ))
        with open(s["capa_fisica_wrap"], "rb") as f:
            col2.download_button("⬇️ Baixar capa física (wraparound)", f, file_name="capa_fisica_wrap.png")

    for i, cena in enumerate(s.get("cenas_imagem", [])):
        st.image(cena["caminho_arquivo"], caption=f"Cena {cena['numero']}")

    st.subheader("🖍️ Páginas de colorir")
    cols = st.columns(3)
    for col, pagina in zip(cols, s.get("paginas_colorir", [])):
        col.image(pagina["caminho_arquivo"], caption=f"Cena {pagina['numero']} - line-art")

    st.subheader("🎧 Roteiro de audiobook")
    audios_por_numero = {a["numero"]: a["caminho_arquivo"] for a in s.get("audio_gerado", [])}
    for trecho in s.get("roteiro_audiobook", []):
        st.text(trecho.get("texto_narrado", ""))
        caminho_audio = audios_por_numero.get(trecho["numero"])
        if caminho_audio:
            st.audio(caminho_audio)

    if st.button("Começar um novo livro"):
        st.session_state.state = LivroState(paginas_minimas=24, idiomas_alvo=[])
        st.session_state.etapa = "entrada"
        st.rerun()

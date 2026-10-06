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
from family_profiles import assign_saved_project_to_profile
from estilo import aplicar_estilo, hero

from state import LivroState, PersonagemDNA
from author_profiles import list_author_profiles, profile_display_name, set_project_authors, author_display_from_state
from openrouter_client import chamar_llm, gerar_imagem, gerar_audio
from armazenamento import (
    salvar_livro, listar_livros, listar_colecoes, carregar_biblioteca_personagens,
    salvar_asset_marca, salvar_na_galeria,
)
from estilo import badge_status
from agents.curador_tema import curador_tema_node
from agents.gerador_ideias import gerador_ideias_node
from agents.criador_personagem import criar_personagem_a_partir_de_ideia
from agents.roteirista import roteirista_node
from agents.revisor import revisor_node
from agents.ilustrador import ilustrador_node
from agents.foto_para_personagem import gerar_personagem_a_partir_de_foto
from agents.atividades_colorir import atividades_colorir_node
from agents.audiobook import audiobook_node, narracao_node
from agents.dedicatoria import dedicatoria_node
from agents.tradutor import tradutor_node
from agents.sinopse import sinopse_node
from agents.pesquisa_mercado import pesquisa_palavras_chave_node, pesquisa_categorias_node
from agents.diagramador import diagramador_node
from agents.capa import capa_node
from agents.marketing import marketing_lancamento_node
from agents.editor_historia import editar_cena, sugerir_versiculos, sugerir_licoes
from agents.personagens_variacoes import (
    garantir_variacao_inicial, gerar_primeira_referencia, gerar_multiplas_variacoes,
    gerar_variacao, selecionar_variacao, aprovar_variacao, favoritar_variacao,
)
from emotion_colors import EMOCOES

st.set_page_config(page_title="Pequenas Histórias, Grandes Lições", page_icon="📖", layout="wide")
aplicar_estilo()
hero("📖 Story Book Studio", "Escreva uma história nova do zero — do tema à capa pronta, com autoria definida por projeto.")

with st.sidebar:
    st.subheader("📚 Meus livros salvos")
    livros = listar_livros()
    if not livros:
        st.caption("Nenhum livro salvo ainda.")
    for livro in livros:
        st.markdown(f"{badge_status(livro['pacote_pronto'])} &nbsp; {livro['titulo']}", unsafe_allow_html=True)
        st.caption(f"— {livro['colecao']}")
    st.caption("Arquivos locais (ver README sobre o roadmap de banco de dados).")

if "state" not in st.session_state:
    st.session_state.state = LivroState(paginas_minimas=24, idiomas_alvo=[])
if "etapa" not in st.session_state:
    st.session_state.etapa = "colecao"

s = st.session_state.state

def _autoria_rapida(state: dict, key: str):
    profiles = list_author_profiles()
    if profiles:
        pm = {p["id"]: p for p in profiles}
        current = [x.get("profile_id") for x in (state.get("authorship") or {}).get("authors", []) if x.get("profile_id") in pm]
        selected = st.multiselect("Autoria deste livro", options=list(pm), default=current, format_func=lambda pid: profile_display_name(pm[pid]), key=f"authors_{key}", help="O primeiro nome selecionado é o autor principal; os demais são coautores.")
        if selected:
            state.update(set_project_authors(state, selected))
        st.caption("Créditos detalhados (ilustrador, tradutor, narrador etc.) podem ser configurados em Autores & Colaboradores.")
    else:
        legacy = st.text_input("Autor(a) / nome de publicação", value=state.get("autora", ""), key=f"legacy_author_{key}")
        if legacy.strip(): state["autora"] = legacy.strip()
        st.caption("Você pode criar perfis reutilizáveis em ✍️ Autores & Colaboradores.")


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
    _autoria_rapida(s, "entrada")
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
                st.session_state.ideias_sugeridas = gerador_ideias_node(4, temas_usados, chamar_llm, s.get("colecao", ""), author_display_from_state(s))
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
    _autoria_rapida(s, "curadoria")
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
        [
            "Deixar o agente criar a partir da descrição",
            "Enviar minha própria imagem de referência",
            "Transformar uma foto real (photo-to-cartoon)",
        ],
    )

    imagem_enviada = None
    foto_transformada = None
    if origem == "Enviar minha própria imagem de referência":
        imagem_enviada = st.file_uploader(
            "Imagem de referência (frente, bem iluminada, de preferência)",
            type=["png", "jpg", "jpeg"],
        )
    elif origem == "Transformar uma foto real (photo-to-cartoon)":
        foto = st.file_uploader("Foto real (sua, de familiar ou do pet)", type=["png", "jpg", "jpeg"])
        detalhe = st.text_input("Algum detalhe extra a manter? (opcional)")
        if foto is not None and nome and st.button("✨ Transformar foto em personagem"):
            caminho_foto = os.path.join("saida_imagens", f"foto_original_{nome}.png")
            os.makedirs("saida_imagens", exist_ok=True)
            with open(caminho_foto, "wb") as f:
                f.write(foto.getbuffer())
            with st.spinner("Transformando a foto no estilo da coleção..."):
                foto_transformada = gerar_personagem_a_partir_de_foto(caminho_foto, nome, papel, gerar_imagem, detalhe)
            st.image(foto_transformada["imagem_referencia"], width=250)

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
        elif foto_transformada is not None:
            novo = foto_transformada
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

# ----------------------------------------------------- EDITOR EDITORIAL
elif st.session_state.etapa == "revisar_texto":
    st.subheader("✍️ Editor Editorial — revise antes de ilustrar")
    st.caption(
        "Altere só o que quiser. As cenas podem ser travadas, versões anteriores ficam guardadas "
        "e nenhuma ilustração é gerada antes da sua aprovação."
    )

    s.setdefault("cenas_bloqueadas", [])
    s.setdefault("historico_cenas", {})

    # -------------------------- TÍTULO / VERSÍCULO / LIÇÃO
    with st.container(border=True):
        st.markdown("### 📖 Direção da história")
        s["titulo"] = st.text_input("Título", value=s.get("titulo", ""), key="editor_titulo")
        s["versiculo_referencia"] = st.text_input(
            "Versículo atual", value=s.get("versiculo_referencia", ""), key="editor_versiculo"
        )
        s["licao_final"] = st.text_area(
            "Lição de Moral", value=s.get("licao_final", s.get("aprendizado_cristao", "")),
            key="editor_licao_final", height=90,
        )

        c1, c2 = st.columns(2)
        if c1.button("📖 Ver 3 opções de versículo", use_container_width=True):
            with st.spinner("Buscando alternativas coerentes com a história..."):
                st.session_state.versiculos_editor = sugerir_versiculos(dict(s), chamar_llm, 3)
        if c2.button("💡 Ver 3 opções de lição", use_container_width=True):
            with st.spinner("Criando alternativas de lição..."):
                st.session_state.licoes_editor = sugerir_licoes(dict(s), chamar_llm, 3)

        for i, opcao in enumerate(st.session_state.get("versiculos_editor", [])):
            ref = opcao.get("referencia", "") if isinstance(opcao, dict) else str(opcao)
            motivo = opcao.get("motivo", "") if isinstance(opcao, dict) else ""
            if ref:
                col_a, col_b = st.columns([4, 1])
                col_a.markdown(f"**{ref}** — {motivo}")
                if col_b.button("Usar", key=f"usar_versiculo_{i}"):
                    s["versiculo_referencia"] = ref
                    st.session_state.versiculos_editor = []
                    st.rerun()

        for i, opcao in enumerate(st.session_state.get("licoes_editor", [])):
            licao = opcao.get("licao", "") if isinstance(opcao, dict) else str(opcao)
            motivo = opcao.get("motivo", "") if isinstance(opcao, dict) else ""
            if licao:
                col_a, col_b = st.columns([4, 1])
                col_a.markdown(f"**{licao}** — {motivo}")
                if col_b.button("Usar", key=f"usar_licao_{i}"):
                    s["licao_final"] = licao
                    s["aprendizado_cristao"] = licao
                    st.session_state.licoes_editor = []
                    st.rerun()

    st.markdown("### 🎬 Cenas")
    st.caption("🔒 Cena travada = protegida contra alterações automáticas. Você ainda pode destravá-la quando quiser.")

    acoes_rapidas = {
        "— escolher —": "",
        "👶 Simplificar linguagem": "Simplifique a linguagem desta cena para uma criança pequena, mantendo a mesma ação e sentido.",
        "💬 Menos diálogo": "Reduza o diálogo desta cena e dê preferência à narração curta e visual.",
        "❤️ Mais emoção": "Deixe esta cena um pouco mais emocionante usando ações e expressões concretas, sem aumentar muito o texto.",
        "⚡ Mais ação visual": "Torne esta cena mais visual e dinâmica, com uma ação simples que possa ser claramente ilustrada.",
        "🎵 Melhor para leitura em voz alta": "Melhore ritmo e musicalidade para leitura em voz alta, mantendo frases curtas.",
    }

    for idx, cena in enumerate(s.get("cenas_texto", [])):
        numero = cena["numero"]
        bloqueada = numero in s.get("cenas_bloqueadas", [])
        titulo_exp = f"{'🔒' if bloqueada else '🎬'} Cena {numero} — {cena.get('emocao', '')}"
        with st.expander(titulo_exp, expanded=(numero == 1)):
            bloqueio = st.checkbox(
                "🔒 Travar esta cena (não alterar automaticamente)",
                value=bloqueada,
                key=f"bloquear_cena_{numero}",
            )
            if bloqueio and numero not in s["cenas_bloqueadas"]:
                s["cenas_bloqueadas"].append(numero)
            elif not bloqueio and numero in s["cenas_bloqueadas"]:
                s["cenas_bloqueadas"].remove(numero)

            cena["texto"] = st.text_area(
                "Texto", value=cena.get("texto", ""), key=f"texto_{numero}", height=110
            )
            c1, c2 = st.columns(2)
            emocoes = list(EMOCOES.keys())
            emocao_atual = cena.get("emocao", "esperanca")
            cena["emocao"] = c1.selectbox(
                "Emoção", emocoes,
                index=emocoes.index(emocao_atual) if emocao_atual in emocoes else 0,
                key=f"emocao_{numero}",
            )
            cena["figurino"] = c2.text_input(
                "Figurino", value=cena.get("figurino", ""), key=f"figurino_{numero}"
            )
            cena["contexto_visual"] = st.text_input(
                "Ambiente / contexto visual", value=cena.get("contexto_visual", ""), key=f"contexto_{numero}"
            )

            if not bloqueio:
                acao = st.selectbox("Melhoria rápida", list(acoes_rapidas), key=f"acao_cena_{numero}")
                pedido_livre = st.text_area(
                    "Ou escreva exatamente o que quer mudar SOMENTE nesta cena",
                    placeholder="Ex.: Quero menos fala e quero que Téo apareça ao lado da Mel, sem mudar o restante da história.",
                    key=f"pedido_cena_{numero}", height=75,
                )
                instrucao = pedido_livre.strip() or acoes_rapidas.get(acao, "")
                col_ed, col_voltar = st.columns(2)
                if col_ed.button("✨ Aplicar somente nesta cena", key=f"editar_cena_{numero}", use_container_width=True, disabled=not bool(instrucao)):
                    # guarda a versão atual antes de modificar
                    anterior = dict(cena)
                    s.setdefault("historico_cenas", {}).setdefault(numero, []).append(anterior)
                    with st.spinner(f"Editando somente a cena {numero}..."):
                        nova = editar_cena(dict(cena), instrucao, dict(s), chamar_llm)
                    s["cenas_texto"][idx] = nova
                    st.rerun()

                historico = s.get("historico_cenas", {}).get(numero, [])
                if col_voltar.button(
                    "↩️ Restaurar versão anterior", key=f"voltar_cena_{numero}",
                    use_container_width=True, disabled=not bool(historico)
                ):
                    atual = dict(cena)
                    anterior = historico.pop()
                    s["cenas_texto"][idx] = anterior
                    # mantém a versão substituída no fim como segurança de ida/volta manual
                    st.session_state[f"ultima_substituida_{numero}"] = atual
                    st.rerun()
            else:
                st.info("Cena protegida. Desmarque o cadeado para pedir mudanças à IA.")

            st.caption(
                "Já tem a ilustração dessa cena pronta? Envie aqui para preservar sua arte e pular a geração por IA desta cena."
            )
            arquivo_cena = st.file_uploader(
                "Ilustração pronta (opcional)", type=["png", "jpg", "jpeg"], key=f"cena_pronta_{numero}"
            )
            if arquivo_cena is not None:
                caminho = os.path.join("saida_imagens", f"cena_enviada_{numero}.png")
                os.makedirs("saida_imagens", exist_ok=True)
                with open(caminho, "wb") as f:
                    f.write(arquivo_cena.getbuffer())
                s.setdefault("imagens_cenas_enviadas", {})[numero] = caminho
                st.success(f"Cena {numero}: sua imagem será preservada e não será gerada novamente.")

    st.divider()
    st.info(
        f"{len(s.get('cenas_bloqueadas', []))} cena(s) travada(s). "
        "A próxima etapa gera apenas referências dos personagens — ainda NÃO gera o livro inteiro."
    )
    if st.button("✅ Aprovar história e seguir para personagens", type="primary", use_container_width=True):
        st.session_state.etapa = "gerando_referencia"
        st.rerun()

# -------------------------------------------------- GERANDO REFERÊNCIA
elif st.session_state.etapa == "gerando_referencia":
    st.subheader("👥 Preparando referências dos personagens")
    st.caption("O FaithBloom gera somente a primeira opção de cada personagem. Nenhuma cena do livro é criada nesta etapa.")
    progresso = st.progress(0, text="Preparando referências visuais...")
    itens = list(s.get("personagens", {}).items())
    for i, (nome_p, personagem) in enumerate(itens):
        personagem = garantir_variacao_inicial(personagem)
        if not personagem.get("imagem_referencia"):
            personagem = gerar_primeira_referencia(personagem, gerar_imagem)
        else:
            personagem = garantir_variacao_inicial(personagem)
        s["personagens"][nome_p] = personagem
        progresso.progress(int(((i + 1) / max(len(itens), 1)) * 100), text=f"Referência de {nome_p} pronta")

    st.session_state.etapa = "aprovar_personagens"
    st.rerun()

# ------------------------------------------------- APROVAR PERSONAGENS
elif st.session_state.etapa == "aprovar_personagens":
    st.subheader("👥 Galeria de Variações — aprove antes das cenas")
    st.caption(
        "Pedir novas opções nunca apaga as anteriores. Você pode criar variações, escrever exatamente o que quer mudar, "
        "favoritar e salvar imagens bonitas na Galeria para outro livro."
    )

    personagens = s.get("personagens", {})
    for nome_p in list(personagens.keys()):
        personagem = garantir_variacao_inicial(personagens[nome_p])
        variacoes = personagem.get("variacoes_visuais", [])
        selecionada_id = personagem.get("variacao_selecionada_id")
        if not selecionada_id and variacoes:
            selecionada_id = variacoes[0].get("id")
            personagem["variacao_selecionada_id"] = selecionada_id

        with st.container(border=True):
            status = "✅ 🔒 APROVADO" if personagem.get("aparencia_aprovada") else "🟡 aguardando aprovação"
            st.markdown(f"### {nome_p} — {status}")
            st.caption(personagem.get("descricao_fixa", ""))

            # galeria de opções preservadas
            if variacoes:
                cols = st.columns(min(3, max(1, len(variacoes))))
                for i, variacao in enumerate(variacoes):
                    with cols[i % len(cols)]:
                        vid = variacao.get("id", f"v{i}")
                        try:
                            st.image(variacao.get("caminho_arquivo", ""), use_container_width=True)
                        except Exception:
                            st.warning("Imagem desta opção não está disponível.")
                        rotulo = f"Opção {i + 1}"
                        if vid == selecionada_id:
                            rotulo += " · selecionada"
                        if variacao.get("favorita"):
                            rotulo += " 💖"
                        st.markdown(f"**{rotulo}**")
                        if st.button("○ Selecionar" if vid != selecionada_id else "● Selecionada", key=f"sel_{nome_p}_{vid}", use_container_width=True):
                            personagem = selecionar_variacao(personagem, vid)
                            s["personagens"][nome_p] = personagem
                            st.rerun()
                        c_a, c_b = st.columns(2)
                        if c_a.button("💖" if variacao.get("favorita") else "♡", key=f"fav_{nome_p}_{vid}"):
                            personagem = favoritar_variacao(personagem, vid, not bool(variacao.get("favorita")))
                            s["personagens"][nome_p] = personagem
                            st.rerun()
                        if c_b.button("💾", key=f"savegal_{nome_p}_{vid}", help="Salvar na Galeria para futuro uso"):
                            try:
                                salvar_na_galeria(
                                    variacao.get("caminho_arquivo", ""),
                                    nome=f"{nome_p} — opção {i + 1}",
                                    tipo="personagem",
                                    tags=[nome_p, personagem.get("papel", "")],
                                    metadata={
                                        "descricao_fixa": personagem.get("descricao_fixa", ""),
                                        "papel": personagem.get("papel", ""),
                                        "colecao_origem": s.get("colecao", ""),
                                        "variacao_id": vid,
                                    },
                                )
                                st.success("Salva na Galeria sem apagar a original.")
                            except Exception as e:
                                st.error(f"Não foi possível salvar na Galeria: {e}")

            st.markdown("#### ✨ Quero explorar mais opções")
            col_more, col_approve = st.columns(2)
            if col_more.button("✨ Gerar +2 opções", key=f"mais2_{nome_p}", use_container_width=True):
                with st.spinner(f"Gerando mais duas opções de {nome_p} sem apagar as anteriores..."):
                    personagem = gerar_multiplas_variacoes(
                        personagem, gerar_imagem, quantidade=2,
                        variacao_base_id=personagem.get("variacao_selecionada_id"),
                    )
                s["personagens"][nome_p] = personagem
                st.rerun()

            if col_approve.button("✅ Aprovar opção selecionada", key=f"aprovar_{nome_p}", type="primary", use_container_width=True):
                vid = personagem.get("variacao_selecionada_id")
                if not vid:
                    st.warning("Selecione uma opção primeiro.")
                else:
                    personagem = aprovar_variacao(personagem, vid)
                    s["personagens"][nome_p] = personagem
                    st.rerun()

            pedido = st.text_area(
                "✍️ Criar variação da opção selecionada com meu pedido",
                placeholder=(
                    "Ex.: Quero esta mesma coelhinha mais fofuxa, menorzinha e um pouco mais rosinha. "
                    "Mantenha o mesmo rostinho, os olhos e o formato das orelhas."
                ),
                key=f"pedido_var_{nome_p}", height=80,
            )
            if st.button("🎨 Criar variação deste pedido", key=f"var_prompt_{nome_p}", use_container_width=True, disabled=not bool(pedido.strip())):
                with st.spinner("Criando uma nova variação e preservando a anterior..."):
                    personagem = gerar_variacao(
                        personagem, gerar_imagem, pedido, personagem.get("variacao_selecionada_id")
                    )
                s["personagens"][nome_p] = personagem
                st.rerun()

            st.caption("Você também pode substituir/adicionar sua própria referência sem apagar as opções existentes.")
            upload = st.file_uploader("📤 Enviar outra imagem de referência", type=["png", "jpg", "jpeg"], key=f"upload_var_{nome_p}")
            if upload is not None and st.button("Adicionar esta imagem às opções", key=f"add_upload_{nome_p}"):
                import uuid as _uuid
                ext = os.path.splitext(upload.name)[1].lower() or ".png"
                caminho = os.path.join("saida_imagens", f"ref_upload_{_uuid.uuid4().hex}{ext}")
                os.makedirs("saida_imagens", exist_ok=True)
                with open(caminho, "wb") as f:
                    f.write(upload.getbuffer())
                personagem.setdefault("variacoes_visuais", []).append({
                    "id": _uuid.uuid4().hex[:12], "caminho_arquivo": caminho,
                    "origem": "enviada_pela_autora", "prompt": "Imagem enviada pela autora",
                    "base": "", "favorita": False,
                })
                personagem["variacao_selecionada_id"] = personagem["variacoes_visuais"][-1]["id"]
                personagem["aparencia_aprovada"] = False
                s["personagens"][nome_p] = personagem
                st.rerun()

        s["personagens"][nome_p] = personagem

    total = len(personagens)
    aprovados = sum(1 for p in s.get("personagens", {}).values() if p.get("aparencia_aprovada"))
    st.divider()
    st.progress(aprovados / max(total, 1), text=f"{aprovados} de {total} personagem(ns) aprovados")
    if aprovados < total:
        st.warning("A geração das cenas está bloqueada até todos os personagens terem uma aparência aprovada.")
    if st.button(
        "🎬 Personagens aprovados — gerar ilustrações do livro",
        type="primary", use_container_width=True, disabled=(aprovados < total or total == 0),
    ):
        st.session_state.etapa = "finalizando"
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
    progresso.progress(80, text="Pesquisando palavras-chave para a KDP...")
    s.update(pesquisa_palavras_chave_node(dict(s), chamar_llm))
    progresso.progress(83, text="Sugerindo categorias de venda...")
    s.update(pesquisa_categorias_node(dict(s), chamar_llm))
    progresso.progress(90, text="Diagramando e validando com a KDP...")
    s.update(diagramador_node(dict(s)))
    progresso.progress(96, text="Gerando capa (eBook) e capa física (wraparound)...")
    s.update(capa_node(dict(s), gerar_imagem))
    progresso.progress(98, text="Gerando material de lançamento...")
    s.update(marketing_lancamento_node(dict(s), chamar_llm))
    progresso.progress(100, text="Pronto!")

    caminho_salvo = salvar_livro(dict(s))
    assign_saved_project_to_profile(st.session_state.get("faithbloom_workspace_profile_id", ""), "story", caminho_salvo, dict(s))
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

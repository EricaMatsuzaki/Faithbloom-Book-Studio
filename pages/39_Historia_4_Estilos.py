"""Refinamento 24 — Criação da história em quatro estilos.

Fluxo editorial:
1. Define coleção e autoria do projeto.
2. Escolhe a faixa etária oficial do livro.
3. Traz ideia/resumo/relato OU pede ideias à IA.
4. Informa personagens narrativos antes do Character DNA visual.
5. Confirma título, emoção, lição e referência bíblica editáveis.
6. Compara a mesma premissa nos quatro estilos, como amostra ou história completa.
7. A escolha é preservada e segue para personagens/revisão antes de qualquer ilustração.
"""
from __future__ import annotations

import streamlit as st

from state import LivroState
from estilo import aplicar_estilo, hero
from openrouter_client import chamar_llm
from armazenamento import (
    listar_livros,
    listar_colecoes,
    salvar_livro,
    atualizar_livro_salvo,
)
from author_profiles import (
    author_display_from_state,
    list_author_profiles,
    profile_display_name,
    set_project_authors,
)
from agents.curador_tema import curador_tema_node
from agents.gerador_ideias import gerador_ideias_node
from agents.estilos_narrativos import (
    ESTILOS_NARRATIVOS,
    ORDEM_ESTILOS,
    aplicar_estilo_ao_state,
    gerar_comparativo_estilos,
)
from age_profiles import (
    normalizar_faixa_etaria,
    opcoes_faixa_etaria,
    perfil_etario,
)

st.set_page_config(page_title="História em 4 Estilos", page_icon="✍️", layout="wide")
aplicar_estilo()
hero(
    "✍️ História em 4 Estilos",
    "Defina coleção e idade, comece com sua própria ideia ou peça ideias à IA e compare a mesma história nos quatro estilos narrativos.",
)

if "state" not in st.session_state:
    st.session_state.state = LivroState(paginas_minimas=24, idiomas_alvo=[], personagens={})

s = st.session_state.state
s.setdefault("paginas_minimas", 24)
s.setdefault("idiomas_alvo", [])
s.setdefault("personagens", {})
s.setdefault("faixa_etaria", "3-8")
s["faixa_etaria"] = normalizar_faixa_etaria(s.get("faixa_etaria"))
s["age_profile_id"] = s["faixa_etaria"]

st.info(
    "Nesta etapa nenhuma ilustração é gerada. Primeiro você decide coleção, autoria, idade, ideia, personagens narrativos e estilo."
)

# ------------------------------------------------------- COLEÇÃO E AUTORIA
st.subheader("1. Coleção e autoria")

# Se já existem personagens formais ou cenas, a coleção fica protegida para não
# misturar Character Universe entre coleções por um clique acidental.
colecao_travada = bool(s.get("colecao") and (s.get("personagens") or s.get("cenas_texto")))
if colecao_travada:
    st.text_input("Coleção deste projeto", value=s.get("colecao", ""), disabled=True)
    st.caption("A coleção fica protegida depois que personagens formais ou cenas existem, evitando misturar universos de personagens.")
else:
    colecoes = listar_colecoes()
    atual = str(s.get("colecao") or "").strip()
    opcoes_colecao = list(colecoes)
    if atual and atual not in opcoes_colecao:
        opcoes_colecao.insert(0, atual)
    opcoes_colecao.append("➕ Criar nova coleção")
    default_idx = opcoes_colecao.index(atual) if atual in opcoes_colecao else 0
    escolha_colecao = st.selectbox(
        "Coleção",
        options=opcoes_colecao,
        index=default_idx,
        help="Cada coleção mantém seu próprio universo de personagens e identidade editorial.",
    )
    if escolha_colecao == "➕ Criar nova coleção":
        nova_colecao = st.text_input("Nome da nova coleção", value="")
        if nova_colecao.strip():
            s["colecao"] = nova_colecao.strip()
    else:
        s["colecao"] = escolha_colecao

profiles = list_author_profiles()
if profiles:
    profile_map = {p["id"]: p for p in profiles}
    atuais = [
        x.get("profile_id")
        for x in (s.get("authorship") or {}).get("authors", [])
        if isinstance(x, dict) and x.get("profile_id") in profile_map
    ]
    autores = st.multiselect(
        "Autoria deste livro",
        options=list(profile_map),
        default=atuais,
        format_func=lambda pid: profile_display_name(profile_map[pid]),
        help="O primeiro selecionado é o autor principal; os demais entram como coautores. Isso é independente de quem está usando o app.",
    )
    if autores:
        s.update(set_project_authors(dict(s), autores))
else:
    s["autora"] = st.text_input(
        "Autor(a) / nome de publicação",
        value=s.get("autora", ""),
        help="Você pode criar perfis reutilizáveis depois em Autores & Colaboradores.",
    )

credito = author_display_from_state(s)
if credito:
    st.caption(f"Crédito atual: **{credito}**")
else:
    st.warning("A autoria ainda não foi definida. Você pode explorar ideias, mas confirme o crédito antes de salvar/publicar o projeto.")

# --------------------------------------------------------------- FAIXA ETÁRIA
st.divider()
st.subheader("2. Para qual faixa etária é este livro?")
opcoes = opcoes_faixa_etaria()
faixa_atual = normalizar_faixa_etaria(s.get("faixa_etaria"))
idx_atual = opcoes.index(faixa_atual) if faixa_atual in opcoes else opcoes.index("3-8")
faixa_escolhida = st.selectbox(
    "Faixa etária oficial",
    options=opcoes,
    index=idx_atual,
    format_func=lambda x: perfil_etario(x)["label"],
    help=(
        "Para novos livros, 3–5, 6–8 e 9–12 dão resultados mais precisos. "
        "A opção 3–8 é mantida para compatibilidade com a coleção ampla já existente."
    ),
)
faixa_escolhida = normalizar_faixa_etaria(faixa_escolhida)

if faixa_escolhida != faixa_atual:
    s["faixa_etaria"] = faixa_escolhida
    s["age_profile_id"] = faixa_escolhida
    s.pop("comparativo_estilos", None)
    s.pop("estilo_escolhido_no_comparador", None)
    s.pop("modo_comparacao_escolhido", None)
    if s.get("cenas_texto"):
        # Não apaga história anterior. Apenas impede que uma versão escrita para
        # outra idade siga adiante sem ser regenerada/revisada conscientemente.
        s["idade_historia_precisa_regenerar"] = True
        s["revisao_aprovada"] = False
    st.rerun()

perfil = perfil_etario(s["faixa_etaria"])
st.caption(
    f"**{perfil['short_label']}** · {perfil['publico']}. "
    f"{perfil['ritmo'].capitalize()}. {perfil['paginas_recomendadas']}."
)

if s.get("idade_historia_precisa_regenerar"):
    st.warning(
        "A faixa etária foi alterada depois de já existir uma história. A versão anterior foi preservada, "
        "mas precisa ser regenerada ou escolhida novamente nos 4 estilos antes de seguir para aprovação."
    )

# ----------------------------------------------------------------- ORIGEM
st.divider()
st.subheader("3. Como você quer começar a história?")
modo = st.radio(
    "Escolha uma opção",
    [
        "📝 Tenho uma ideia, resumo ou breve relato",
        "✨ Estou sem ideia — quero sugestões da IA",
        "📖 Usar a ideia que já está no projeto",
    ],
    horizontal=False,
)

if modo.startswith("📝"):
    s["origem_ideia"] = "ideia_da_autora"
    ideia = st.text_area(
        "Conte sua ideia do seu jeito",
        value=s.get("_entrada_tema_livre", ""),
        height=180,
        placeholder=(
            "Ex.: Mel quer muito ver a sementinha nascer. Ela olha o vaso várias vezes, fica impaciente, "
            "tenta apressar a planta e depois aprende que existe um tempo certo para cada coisa..."
        ),
        help="Pode ser apenas algumas linhas. Você não precisa saber escrever a história completa.",
    )
    if ideia.strip():
        s["_entrada_tema_livre"] = ideia.strip()

    if st.button("🌱 Preparar minha ideia", disabled=not bool(ideia.strip())):
        with st.spinner("Organizando título, emoção, lição e referência bíblica..."):
            s.update(curador_tema_node(dict(s), chamar_llm))
        st.success("Ideia preparada. Você pode editar tudo antes de gerar as versões.")

elif modo.startswith("✨"):
    s["origem_ideia"] = "ideia_da_ia"
    st.write(
        f"A IA vai sugerir ideias pensadas para **{perfil['short_label']}**, mas nenhuma vira história sem a sua decisão."
    )
    quantidade = st.select_slider("Quantas ideias você quer ver?", options=[3, 4, 5, 6], value=4)
    temas_usados = [l.get("titulo", "") for l in listar_livros(s.get("colecao") or None) if l.get("titulo")]

    if st.button("✨ Sugerir ideias novas"):
        with st.spinner("Criando ideias diferentes para sua coleção e faixa etária..."):
            st.session_state.ideias_4_estilos = gerador_ideias_node(
                quantidade,
                temas_usados,
                chamar_llm,
                s.get("colecao", ""),
                author_display_from_state(s),
                faixa_etaria=s.get("faixa_etaria", "3-8"),
            )

    ideias = st.session_state.get("ideias_4_estilos", [])
    for i, ideia in enumerate(ideias):
        with st.container(border=True):
            st.markdown(f"### {ideia.get('titulo_sugerido', f'Ideia {i + 1}')}")
            st.write(ideia.get("situacao", ""))
            st.caption(
                f"Emoção: {ideia.get('emocao_central', '')}  •  "
                f"Possível lição: {ideia.get('pista_licao', '')}"
            )
            if st.button("Usar esta ideia", key=f"usar_ideia_4_estilos_{i}"):
                s["titulo"] = ideia.get("titulo_sugerido", "")
                s["emocao_central"] = ideia.get("emocao_central", "")
                s["aprendizado_cristao"] = ideia.get("pista_licao", "")
                s["_entrada_tema_livre"] = ideia.get("situacao", "")
                with st.spinner("Preparando a ideia escolhida..."):
                    s.update(curador_tema_node(dict(s), chamar_llm))
                st.session_state.ideia_4_estilos_escolhida = i
                st.rerun()

    if st.session_state.get("ideia_4_estilos_escolhida") is not None:
        st.success("Ideia da IA escolhida. Agora personalize os personagens e os detalhes abaixo.")

else:
    s["origem_ideia"] = "projeto_existente"
    if not (s.get("_entrada_tema_livre") or s.get("titulo")):
        st.warning("Este projeto ainda não possui uma ideia. Use uma das duas opções acima.")
    else:
        st.write(s.get("_entrada_tema_livre") or s.get("titulo"))

# ------------------------------------------------------------- PERSONAGENS
st.divider()
st.subheader("4. Quais personagens você quer nessa história?")

if s.get("personagens"):
    st.markdown("**Personagens já formalizados no projeto:**")
    for nome, dados in s.get("personagens", {}).items():
        papel = dados.get("papel", "") if isinstance(dados, dict) else ""
        st.write(f"✅ {nome}" + (f" — {papel}" if papel else ""))

s["personagens_historia_brief"] = st.text_area(
    "Personagens que quero na narrativa",
    value=s.get("personagens_historia_brief", ""),
    height=150,
    placeholder=(
        "Ex.:\n"
        "Mel — gatinha curiosa e impaciente; protagonista.\n"
        "Manu — amiga carinhosa que ajuda Mel.\n"
        "Téo — passarinho azul divertido que aparece no jardim."
    ),
    help=(
        "Aqui você pode informar apenas nome, papel e personalidade. A aparência visual/Character DNA "
        "pode ser definida depois sem perder a história escolhida."
    ),
)

st.caption(
    "Os quatro estilos usarão os MESMOS personagens. A IA não deve trocar nomes, relações, papéis ou características pedidas."
)

# -------------------------------------------------------------- CURADORIA
st.divider()
st.subheader("5. Confirme a direção da história")

s["titulo"] = st.text_input("Título ou título provisório", value=s.get("titulo", ""))
s["emocao_central"] = st.text_input("Emoção central", value=s.get("emocao_central", ""))
s["aprendizado_cristao"] = st.text_area(
    "Lição / aprendizado cristão",
    value=s.get("aprendizado_cristao", ""),
    height=85,
)
s["versiculo_referencia"] = st.text_input(
    "Versículo — somente a referência nesta etapa",
    value=s.get("versiculo_referencia", ""),
    placeholder="Ex.: Eclesiastes 3:1",
)

premissa_ok = bool(str(s.get("_entrada_tema_livre") or s.get("titulo") or "").strip())
colecao_ok = bool(str(s.get("colecao") or "").strip())
if not colecao_ok:
    st.warning("Escolha ou crie uma coleção antes de gerar os quatro estilos.")
if not premissa_ok:
    st.warning("Defina ou escolha uma ideia antes de gerar os quatro estilos.")

# Salvamento manual: primeira vez cria um rascunho; depois atualiza o mesmo arquivo.
if st.button(
    "💾 Salvar rascunho",
    disabled=not bool(colecao_ok and str(s.get("titulo") or "").strip()),
    help="Salva o estado atual do projeto sem aprovar história nem gerar imagens.",
):
    try:
        caminho = str(s.get("storage_path") or st.session_state.get("historia4_storage_path") or "")
        if caminho:
            caminho = atualizar_livro_salvo(caminho, dict(s))
        else:
            caminho = salvar_livro(dict(s))
        s["storage_path"] = caminho
        st.session_state.historia4_storage_path = caminho
        st.success("Rascunho salvo com sucesso.")
    except Exception as exc:
        st.error(f"Não foi possível salvar o rascunho: {exc}")

# ------------------------------------------------------------ COMPARAÇÃO
st.divider()
st.subheader("6. Veja a MESMA história nos 4 estilos")

st.markdown(
    "**Estilo 1 — Aventura**  •  **Estilo 2 — Poético/Rimado**  •  "
    "**Estilo 3 — Fábula cristã**  •  **Estilo misto**"
)
st.caption(
    f"A premissa, os personagens, a lição cristã, a referência bíblica e a faixa **{perfil['short_label']}** permanecem iguais. "
    "Somente a maneira de contar muda."
)

pode_comparar = bool(premissa_ok and colecao_ok)
c1, c2 = st.columns(2)
if c1.button("✨ Ver amostras dos 4 estilos", use_container_width=True, disabled=not pode_comparar):
    with st.spinner("Criando quatro amostras da mesma história..."):
        s["comparativo_estilos"] = gerar_comparativo_estilos(dict(s), chamar_llm, modo="amostra")
    st.rerun()

if c2.button("📚 Gerar a história COMPLETA nos 4 estilos", use_container_width=True, disabled=not pode_comparar):
    with st.spinner("Criando as quatro histórias completas com a mesma ideia, personagens e faixa etária..."):
        s["comparativo_estilos"] = gerar_comparativo_estilos(dict(s), chamar_llm, modo="completa")
    st.rerun()

comparativo = s.get("comparativo_estilos") or {}
if comparativo:
    tabs = st.tabs([ESTILOS_NARRATIVOS[k]["label"] for k in ORDEM_ESTILOS])
    for tab, estilo in zip(tabs, ORDEM_ESTILOS):
        with tab:
            versao = comparativo.get(estilo) or {}
            st.caption(ESTILOS_NARRATIVOS[estilo]["descricao"])
            if versao.get("titulo"):
                st.markdown(f"### {versao['titulo']}")
            if versao.get("sinopse_poetica"):
                st.write(versao["sinopse_poetica"])

            if versao.get("modo") == "completa" and versao.get("cenas_texto"):
                for cena in versao["cenas_texto"]:
                    if isinstance(cena, dict):
                        st.markdown(f"**Cena {cena.get('numero', '')}**")
                        st.write(cena.get("texto", ""))
                    else:
                        st.write(cena)
            else:
                st.write(versao.get("amostra") or "Amostra não disponível.")

            if versao.get("licao_final"):
                st.markdown(f"**⭐ Lição de Moral:** {versao['licao_final']}")

            if st.button(
                f"✅ Escolher {ESTILOS_NARRATIVOS[estilo]['label']}",
                key=f"escolher_historia_estilo_{estilo}",
                use_container_width=True,
            ):
                novo = aplicar_estilo_ao_state(dict(s), estilo, versao)
                s.clear()
                s.update(novo)
                s["estilo_escolhido_no_comparador"] = True
                s["modo_comparacao_escolhido"] = versao.get("modo", "amostra")
                s["idade_historia_precisa_regenerar"] = False
                st.rerun()

# ------------------------------------------------------------- CONTINUAR
if s.get("estilo_escolhido_no_comparador"):
    st.divider()
    estilo = s.get("estilo_narrativo", "estilo_1")
    modo_escolhido = s.get("modo_comparacao_escolhido", "amostra")
    st.success(
        f"Estilo escolhido: {ESTILOS_NARRATIVOS[estilo]['label']} · Faixa: {perfil_etario(s.get('faixa_etaria'))['short_label']}."
    )

    if modo_escolhido == "completa" and s.get("cenas_texto"):
        st.info(
            "Você escolheu uma história completa. Ela será PRESERVADA: ao seguir para os personagens, "
            "o Roteirista não vai gerar outra história por cima. A próxima passagem é revisão editorial."
        )
    else:
        st.info(
            "Você escolheu o estilo pela amostra. Depois de formalizar os personagens, o Roteirista "
            "gerará a história completa somente nesse estilo e na faixa etária escolhida."
        )

    tem_personagens_formais = bool(s.get("personagens"))
    texto_botao = (
        "➡️ Continuar para revisão da história"
        if tem_personagens_formais
        else "➡️ Continuar para definir os personagens"
    )
    if st.button(
        texto_botao,
        type="primary",
        use_container_width=True,
        disabled=bool(s.get("idade_historia_precisa_regenerar")),
    ):
        st.session_state.etapa = "gerando" if tem_personagens_formais else "personagens"
        st.switch_page("pages/1_#L01f4d6_Criar_do_Zero.py")

st.caption(
    "Nenhuma das quatro versões é aprovada automaticamente. A escolha da autora continua obrigatória antes das ilustrações."
)

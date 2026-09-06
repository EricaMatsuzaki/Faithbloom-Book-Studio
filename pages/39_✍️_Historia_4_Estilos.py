"""Refinamento 24 — Criação e comparação de versões narrativas.

Fluxo editorial:
1. Define coleção e autoria do projeto.
2. Escolhe a faixa etária oficial do livro.
3. Traz ideia/resumo/relato OU pede ideias à IA.
4. Informa personagens narrativos antes do Character DNA visual.
5. Confirma título, emoção, lição e referência bíblica editáveis.
6. Pode ver a visão autoral do Roteirista, comparar os quatro estilos formais
   e gerar uma quinta versão completa usando a skill real de storyteller.
7. Pode explorar estilos adicionais sob demanda, sem aumentar automaticamente
   as quatro chamadas principais.
8. Todas as versões podem ser preservadas na Biblioteca de Versões Narrativas.
9. A versão ativa segue para personagens/revisão antes de qualquer ilustração.
"""
from __future__ import annotations

from copy import deepcopy
import streamlit as st

from state import LivroState
from estilo import aplicar_estilo, hero
from openrouter_client import chamar_llm
from armazenamento import (
    listar_livros,
    listar_colecoes,
    carregar_biblioteca_personagens,
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
    ESTILOS_ADICIONAIS,
    ORDEM_ESTILOS,
    aplicar_estilo_ao_state,
    gerar_comparativo_estilos,
)
from agents.roteirista_autoral import (
    LABEL_ROTEIRISTA,
    gerar_proposta_roteirista,
    gerar_versao_autoral_roteirista,
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
    "Defina coleção e idade, comece com sua própria ideia ou peça ideias à IA, compare quatro estilos formais e, se quiser, veja também a versão autoral do Roteirista.",
)

if "state" not in st.session_state:
    st.session_state.state = LivroState(paginas_minimas=24, idiomas_alvo=[], personagens={})

s = st.session_state.state
s.setdefault("paginas_minimas", 24)
s.setdefault("idiomas_alvo", [])
s.setdefault("personagens", {})
s.setdefault("faixa_etaria", "3-8")
s.setdefault("versoes_narrativas_salvas", {})
s["faixa_etaria"] = normalizar_faixa_etaria(s.get("faixa_etaria"))
s["age_profile_id"] = s["faixa_etaria"]

st.info(
    "Nesta etapa nenhuma ilustração é gerada. Primeiro você decide coleção, autoria, idade, ideia, personagens narrativos e versão da história."
)

DERIVADOS_NARRATIVOS = (
    "revisao_aprovada",
    "notas_revisor",
    "mapa_emocional",
    "cenas_imagem",
    "imagens_cenas_enviadas",
    "cenas_imagem_aprovadas",
    "paginas_colorir",
    "traducoes",
    "roteiro_audiobook",
    "audio_gerado",
    "layout_paginas",
    "pacote_pronto",
    "checklist_kdp",
    "preflight_impressao",
    "pdf_miolo_print_ready",
    "sinopse_vendas_curta",
    "sinopse_contracapa",
    "material_lancamento",
)


def _persistir_estado() -> str:
    """Salva/atualiza o projeto atual, inclusive a biblioteca de versões."""
    caminho = str(s.get("storage_path") or st.session_state.get("historia4_storage_path") or "")
    if caminho:
        caminho = atualizar_livro_salvo(caminho, dict(s))
    else:
        caminho = salvar_livro(dict(s))
    s["storage_path"] = caminho
    st.session_state.historia4_storage_path = caminho
    return caminho


def _sincronizar_biblioteca_versoes() -> None:
    biblioteca = deepcopy(s.get("versoes_narrativas_salvas") or {})
    for chave, versao in (s.get("comparativo_estilos") or {}).items():
        if not isinstance(versao, dict):
            continue
        item = deepcopy(versao)
        item["origem"] = "comparative_story_director"
        item["faixa_etaria"] = s.get("faixa_etaria")
        item["colecao"] = s.get("colecao")
        item["status"] = "atual"
        biblioteca[chave] = item
    autoral = s.get("versao_roteirista_autoral")
    if isinstance(autoral, dict) and autoral:
        item = deepcopy(autoral)
        item["faixa_etaria"] = s.get("faixa_etaria")
        item["colecao"] = s.get("colecao")
        item["status"] = "atual"
        biblioteca["roteirista_autoral"] = item
    s["versoes_narrativas_salvas"] = biblioteca


def _arquivar_derivados_da_versao_ativa() -> None:
    ativa = str(s.get("versao_narrativa_ativa") or "").strip()
    if not ativa:
        return
    snapshot = {}
    for campo in DERIVADOS_NARRATIVOS:
        if campo in s and s.get(campo) not in (None, "", [], {}, False):
            snapshot[campo] = deepcopy(s.get(campo))
    if not snapshot:
        return
    historico = deepcopy(s.get("historico_derivados_por_versao") or {})
    historico.setdefault(ativa, []).append(snapshot)
    s["historico_derivados_por_versao"] = historico


def _ativar_versao(chave: str, versao: dict) -> None:
    """Troca a história ativa sem apagar as outras versões nem seus derivados anteriores."""
    _arquivar_derivados_da_versao_ativa()
    if chave == "roteirista_autoral":
        estilo_base = versao.get("estilo_recomendado") or "misto"
        novo = aplicar_estilo_ao_state(dict(s), estilo_base, versao)
        novo["versao_narrativa_origem"] = "storyteller_skill"
        novo["estilo_narrativo_label"] = LABEL_ROTEIRISTA
    else:
        novo = aplicar_estilo_ao_state(dict(s), chave, versao)
        novo["versao_narrativa_origem"] = (
            "comparative_story_director_additional"
            if chave in ESTILOS_ADICIONAIS
            else "comparative_story_director"
        )

    for campo in DERIVADOS_NARRATIVOS:
        novo.pop(campo, None)
    novo["revisao_aprovada"] = False
    novo["pacote_pronto"] = False
    novo["versao_narrativa_ativa"] = chave
    novo["estilo_escolhido_no_comparador"] = True
    novo["modo_comparacao_escolhido"] = versao.get("modo", "completa")
    novo["idade_historia_precisa_regenerar"] = False
    s.clear()
    s.update(novo)


def _invalidar_comparativo_por_mudanca_editorial() -> None:
    """Arquiva versões antigas se idade/coleção mudar, sem destruí-las."""
    biblioteca = deepcopy(s.get("versoes_narrativas_salvas") or {})
    for item in biblioteca.values():
        if isinstance(item, dict) and item.get("status") == "atual":
            item["status"] = "arquivada_por_mudanca_editorial"
    s["versoes_narrativas_salvas"] = biblioteca
    s.pop("comparativo_estilos", None)
    s.pop("versao_roteirista_autoral", None)
    s.pop("proposta_roteirista", None)
    s.pop("estilo_escolhido_no_comparador", None)
    s.pop("modo_comparacao_escolhido", None)
    st.session_state.pop("ideias_4_estilos", None)
    st.session_state.pop("ideia_4_estilos_escolhida", None)


# ------------------------------------------------------- COLEÇÃO E AUTORIA
st.subheader("1. Coleção e autoria")

colecao_travada = bool(s.get("colecao") and (s.get("personagens") or s.get("cenas_texto")))
colecao_anterior = str(s.get("colecao") or "").strip()

if colecao_travada:
    st.text_input("Coleção deste projeto", value=colecao_anterior, disabled=True)
    st.caption("A coleção fica protegida depois que personagens formais ou cenas existem, evitando misturar universos de personagens.")
    st.session_state.biblioteca_colecao = carregar_biblioteca_personagens(colecao_anterior)
else:
    colecoes = listar_colecoes()
    opcoes_colecao = list(colecoes)
    if colecao_anterior and colecao_anterior not in opcoes_colecao:
        opcoes_colecao.insert(0, colecao_anterior)
    opcoes_colecao.append("➕ Criar nova coleção")
    default_idx = opcoes_colecao.index(colecao_anterior) if colecao_anterior in opcoes_colecao else 0
    escolha_colecao = st.selectbox(
        "Coleção",
        options=opcoes_colecao,
        index=default_idx,
        help="Cada coleção mantém seu próprio universo de personagens e identidade editorial.",
    )

    if escolha_colecao == "➕ Criar nova coleção":
        nova_colecao = st.text_input("Nome da nova coleção", value="")
        colecao_nova = nova_colecao.strip()
        if colecao_nova != colecao_anterior:
            s["colecao"] = colecao_nova
            st.session_state.biblioteca_colecao = {}
            _invalidar_comparativo_por_mudanca_editorial()
            if colecao_nova:
                st.rerun()
    else:
        colecao_nova = escolha_colecao
        if colecao_nova != colecao_anterior:
            s["colecao"] = colecao_nova
            st.session_state.biblioteca_colecao = carregar_biblioteca_personagens(colecao_nova)
            _invalidar_comparativo_por_mudanca_editorial()
            st.rerun()
        else:
            s["colecao"] = colecao_nova
            st.session_state.biblioteca_colecao = carregar_biblioteca_personagens(colecao_nova)

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
    if autores != atuais:
        s.update(set_project_authors(dict(s), autores))
else:
    s["autora"] = st.text_input(
        "Nome de autoria/publicação",
        value=author_display_from_state(s) or str(s.get("autora") or ""),
        help="Nome que deve aparecer como autora/autoria do livro; não use automaticamente o nome de quem está logado.",
    ).strip()

colecao_ok = bool(str(s.get("colecao") or "").strip())
if not colecao_ok:
    st.warning("Defina a coleção antes de avançar.")

# -------------------------------------------------------- FAIXA ETÁRIA
st.subheader("2. Faixa etária oficial")
faixa_anterior = normalizar_faixa_etaria(s.get("faixa_etaria"))
opcoes_idade = opcoes_faixa_etaria()
ids_idade = [x[0] for x in opcoes_idade]
rotulos_idade = {x[0]: x[1] for x in opcoes_idade}
idx_idade = ids_idade.index(faixa_anterior) if faixa_anterior in ids_idade else 0
faixa = st.selectbox(
    "Faixa etária",
    options=ids_idade,
    index=idx_idade,
    format_func=lambda x: rotulos_idade[x],
    help="Esta escolha altera linguagem, densidade, musicalidade, humor, tensão e profundidade da história.",
)
if faixa != faixa_anterior:
    s["faixa_etaria"] = faixa
    s["age_profile_id"] = faixa
    _invalidar_comparativo_por_mudanca_editorial()
    s["idade_historia_precisa_regenerar"] = True
    st.rerun()
else:
    s["faixa_etaria"] = faixa
    s["age_profile_id"] = faixa

# ------------------------------------------------------ ORIGEM DA IDEIA
st.subheader("3. Como você quer começar a história?")
origens = {
    "ideia_propria": "📝 Tenho uma ideia, resumo ou breve relato",
    "sem_ideia": "✨ Estou sem ideia — quero sugestões da IA",
    "projeto": "📖 Usar a ideia que já está no projeto",
}
origem_atual = s.get("origem_ideia") or "ideia_propria"
origem = st.radio(
    "Escolha uma opção",
    options=list(origens),
    index=list(origens).index(origem_atual) if origem_atual in origens else 0,
    format_func=lambda x: origens[x],
)
s["origem_ideia"] = origem

if origem == "ideia_propria":
    texto_ideia = st.text_area(
        "Escreva sua ideia do seu jeito",
        value=str(s.get("_entrada_tema_livre") or ""),
        height=160,
        placeholder="Ex.: Uma gatinha não quer emprestar seus lápis e descobre que compartilhar torna a brincadeira mais bonita.",
    )
    if texto_ideia.strip() != str(s.get("_entrada_tema_livre") or "").strip():
        s["_entrada_tema_livre"] = texto_ideia.strip()
        s.pop("comparativo_estilos", None)
        s.pop("versao_roteirista_autoral", None)
        s.pop("proposta_roteirista", None)
        s.pop("estilo_escolhido_no_comparador", None)
    if st.button("🌱 Preparar minha ideia", disabled=not bool(colecao_ok and texto_ideia.strip())):
        s["_entrada_tema_livre"] = texto_ideia.strip()
        s.update(curador_tema_node(dict(s), chamar_llm))
        st.rerun()

elif origem == "sem_ideia":
    if st.button("✨ Sugerir ideias para este livro", disabled=not colecao_ok):
        resposta = gerador_ideias_node(dict(s), chamar_llm)
        ideias = resposta.get("ideias_geradas") or resposta.get("ideias") or []
        if isinstance(ideias, dict):
            ideias = list(ideias.values())
        st.session_state.ideias_4_estilos = ideias
        st.session_state.pop("ideia_4_estilos_escolhida", None)

    ideias = st.session_state.get("ideias_4_estilos") or []
    if ideias:
        st.caption("Escolha uma ideia. Depois você ainda poderá editar título, emoção, lição e referência bíblica.")
        for i, ideia in enumerate(ideias):
            if isinstance(ideia, dict):
                titulo_ideia = ideia.get("titulo") or ideia.get("nome") or f"Ideia {i + 1}"
                resumo_ideia = ideia.get("resumo") or ideia.get("ideia") or ideia.get("descricao") or ""
            else:
                titulo_ideia = f"Ideia {i + 1}"
                resumo_ideia = str(ideia)
            with st.container(border=True):
                st.markdown(f"**{titulo_ideia}**")
                st.write(resumo_ideia)
                if st.button("Usar esta ideia", key=f"usar_ideia_{i}"):
                    texto_base = f"{titulo_ideia}. {resumo_ideia}".strip()
                    st.session_state.ideia_4_estilos_escolhida = deepcopy(ideia)
                    s["_entrada_tema_livre"] = texto_base
                    s.update(curador_tema_node(dict(s), chamar_llm))
                    st.rerun()

else:
    st.text_area(
        "Ideia do projeto",
        value=str(s.get("_entrada_tema_livre") or s.get("titulo") or ""),
        disabled=True,
        height=120,
    )

# ------------------------------------------------ PERSONAGENS NARRATIVOS
st.subheader("4. Quais personagens você quer nessa história?")
brief_personagens = st.text_area(
    "Personagens narrativos",
    value=str(s.get("personagens_historia_brief") or ""),
    height=150,
    placeholder=(
        "Ex.: Mel — protagonista curiosa, alegre e carinhosa.\n"
        "Manu — amiga gentil e criativa.\n"
        "Aqui descreva PAPEL e comportamento na história; a aparência visual será definida no Character DNA."
    ),
    help="Os mesmos personagens serão usados em todas as versões. Características visuais canônicas pertencem ao Character Universe/Character DNA.",
)
if brief_personagens != str(s.get("personagens_historia_brief") or ""):
    s["personagens_historia_brief"] = brief_personagens
    s.pop("comparativo_estilos", None)
    s.pop("versao_roteirista_autoral", None)
    s.pop("proposta_roteirista", None)
    s.pop("estilo_escolhido_no_comparador", None)

# ------------------------------------------------ DIREÇÃO EDITORIAL
st.subheader("5. Confirme a direção da história")
s["titulo"] = st.text_input("Título / título provisório", value=str(s.get("titulo") or ""))
s["emocao_central"] = st.text_input("Emoção central", value=str(s.get("emocao_central") or ""))
s["aprendizado_cristao"] = st.text_area(
    "Lição cristã",
    value=str(s.get("aprendizado_cristao") or ""),
    height=90,
)
s["versiculo_referencia"] = st.text_input(
    "Referência bíblica (somente referência nesta etapa)",
    value=str(s.get("versiculo_referencia") or ""),
    help="O texto bíblico completo só deve ser usado depois da validação/seleção de tradução apropriada.",
)

pronto_editorial = all(
    str(s.get(k) or "").strip()
    for k in ("titulo", "emocao_central", "aprendizado_cristao")
) and colecao_ok

if st.button("💾 Salvar direção como rascunho", disabled=not bool(pronto_editorial)):
    try:
        _persistir_estado()
        st.success("Direção editorial salva como rascunho.")
    except Exception as exc:
        st.error(f"Não foi possível salvar o rascunho: {exc}")

# ------------------------------------------------------ VISÃO DO ROTEIRISTA
st.subheader("6. ✍️ Visão do Roteirista")
st.caption(
    "Além da comparação formal, você pode perguntar ao Roteirista como ele desenvolveria esta ideia usando sua skill completa de storytelling."
)
if st.button(
    "✍️ Ver a proposta do Roteirista para esta ideia",
    disabled=not bool(pronto_editorial),
    use_container_width=True,
):
    with st.spinner("O Roteirista está estudando a premissa, a idade e os personagens..."):
        s["proposta_roteirista"] = gerar_proposta_roteirista(dict(s), chamar_llm)
    st.rerun()

proposta = s.get("proposta_roteirista") or {}
if proposta:
    with st.expander("✍️ Proposta do Roteirista", expanded=True):
        campos = [
            ("Título alternativo", "titulo_alternativo"),
            ("Gancho", "gancho"),
            ("Direção narrativa", "direcao_narrativa"),
            ("Arco emocional", "arco_emocional"),
            ("Momento de virada", "momento_de_virada"),
            ("Final sugerido", "final_sugerido"),
            ("Justificativa criativa", "justificativa_criativa"),
        ]
        for rotulo, campo in campos:
            if proposta.get(campo):
                st.markdown(f"**{rotulo}:** {proposta[campo]}")
        estilo_rec = proposta.get("estilo_recomendado")
        if estilo_rec in ESTILOS_NARRATIVOS:
            st.markdown(f"**Estilo formal recomendado:** {ESTILOS_NARRATIVOS[estilo_rec]['label']}")

# -------------------------------------------------------- COMPARAÇÃO FORMAL
st.subheader("7. Veja a MESMA história nos 4 estilos")
st.caption(
    "Premissa, personagens, lição cristã, referência bíblica e faixa etária permanecem iguais. "
    "Todos os quatro estilos usam a skill-base do Roteirista; muda apenas a especialização narrativa."
)
col_a, col_b = st.columns(2)
if col_a.button("✨ Ver amostras dos 4 estilos", disabled=not bool(pronto_editorial), use_container_width=True):
    with st.spinner("Criando quatro amostras com a mesma premissa e personagens..."):
        s["comparativo_estilos"] = gerar_comparativo_estilos(dict(s), chamar_llm, modo="amostra")
        s.pop("estilo_escolhido_no_comparador", None)
        _sincronizar_biblioteca_versoes()
    st.rerun()

if col_b.button(
    "📚 Gerar a história COMPLETA nos 4 estilos",
    disabled=not bool(pronto_editorial),
    use_container_width=True,
):
    with st.spinner("Criando as quatro histórias completas com a mesma ideia, personagens e faixa etária..."):
        s["comparativo_estilos"] = gerar_comparativo_estilos(dict(s), chamar_llm, modo="completa")
        s.pop("estilo_escolhido_no_comparador", None)
        _sincronizar_biblioteca_versoes()
    st.rerun()

st.markdown("#### ⭐ Quinta opção — versão autoral do Roteirista")
st.caption(
    "Aqui o Roteirista usa a mesma skill profissional, mas sem ser obrigado a seguir isoladamente Aventura, Poético, Fábula ou Misto."
)
if st.button(
    "⭐ Gerar versão do Roteirista",
    disabled=not bool(pronto_editorial),
    use_container_width=True,
):
    with st.spinner("O Roteirista está escrevendo sua melhor versão autoral completa..."):
        s["versao_roteirista_autoral"] = gerar_versao_autoral_roteirista(dict(s), chamar_llm)
        _sincronizar_biblioteca_versoes()
    st.rerun()

st.markdown("#### ➕ Quer experimentar outra forma de contar?")
st.caption(
    "Os estilos adicionais são opcionais e só usam créditos quando você pedir. O primeiro disponível é 🔁 Cumulativo/Lengalenga, com repetição progressiva, refrão original, musicalidade e humor crescente."
)
st.page_link(
    "pages/40_➕_Explorar_outros_estilos.py",
    label="➕ Explorar outros estilos narrativos",
    icon="➕",
)

# -------------------------------------------------------- EXIBIR VERSÕES
comparativo = s.get("comparativo_estilos") or {}
autoral = s.get("versao_roteirista_autoral") or {}
entradas = []
for chave in ORDEM_ESTILOS:
    versao = comparativo.get(chave)
    if isinstance(versao, dict) and versao:
        entradas.append((chave, ESTILOS_NARRATIVOS[chave]["label"], versao))
if isinstance(autoral, dict) and autoral:
    entradas.append(("roteirista_autoral", LABEL_ROTEIRISTA, autoral))

if entradas:
    tabs = st.tabs([label for _, label, _ in entradas])
    for tab, (chave, label, versao) in zip(tabs, entradas):
        with tab:
            if chave == "roteirista_autoral":
                st.caption("Versão livre gerada pela skill formal do Roteirista; não é obrigada a imitar um dos quatro estilos.")
                estilo_rec = versao.get("estilo_recomendado")
                if estilo_rec in ESTILOS_NARRATIVOS:
                    st.caption(f"Estilo formal mais próximo: {ESTILOS_NARRATIVOS[estilo_rec]['label']}")
                if versao.get("justificativa_criativa"):
                    st.info(versao["justificativa_criativa"])
            else:
                st.caption(ESTILOS_NARRATIVOS[chave]["descricao"])

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
                f"✅ Tornar ativa — {label}",
                key=f"escolher_historia_{chave}",
                use_container_width=True,
            ):
                _ativar_versao(chave, versao)
                st.rerun()

# --------------------------------------------------------- BIBLIOTECA DE VERSÕES
biblioteca = s.get("versoes_narrativas_salvas") or {}
if biblioteca:
    st.divider()
    st.subheader("8. 📚 Biblioteca de Versões Narrativas")
    st.caption(
        "As versões geradas permanecem guardadas no projeto. Escolher uma não apaga as outras. "
        "Se você mudar de ideia depois, pode voltar e tornar outra versão ativa sem regenerar."
    )
    ativa = s.get("versao_narrativa_ativa")
    for chave, versao in biblioteca.items():
        if not isinstance(versao, dict):
            continue
        if chave == "roteirista_autoral":
            label = LABEL_ROTEIRISTA
        elif chave in ESTILOS_ADICIONAIS:
            label = ESTILOS_ADICIONAIS[chave]["label"]
        else:
            label = ESTILOS_NARRATIVOS.get(chave, {}).get("label") or versao.get("label") or chave
        status = versao.get("status", "atual")
        marcador = " ✅ ATIVA" if ativa == chave else ""
        with st.expander(f"{label}{marcador}"):
            st.caption(f"Modo: {versao.get('modo', 'completa')} · Status: {status}")
            if versao.get("titulo"):
                st.write(f"**{versao['titulo']}**")
            if versao.get("sinopse_poetica"):
                st.write(versao["sinopse_poetica"])
            if status == "atual" and st.button(
                f"Tornar {label} a versão ativa",
                key=f"biblioteca_ativar_{chave}",
                disabled=ativa == chave,
            ):
                _ativar_versao(chave, versao)
                st.rerun()

    if st.button(
        "💾 Salvar todas as versões no projeto",
        disabled=not bool(colecao_ok and str(s.get("titulo") or "").strip()),
        use_container_width=True,
    ):
        try:
            _persistir_estado()
            st.success("Biblioteca de versões salva no projeto. Você poderá voltar a ela depois.")
        except Exception as exc:
            st.error(f"Não foi possível salvar a biblioteca: {exc}")

# ------------------------------------------------------------- CONTINUAR
if s.get("estilo_escolhido_no_comparador"):
    st.divider()
    ativa = s.get("versao_narrativa_ativa")
    estilo = s.get("estilo_narrativo", "estilo_1")
    modo_escolhido = s.get("modo_comparacao_escolhido", "amostra")
    if ativa == "roteirista_autoral":
        label_ativa = LABEL_ROTEIRISTA
    elif estilo in ESTILOS_ADICIONAIS:
        label_ativa = ESTILOS_ADICIONAIS[estilo]["label"]
    else:
        label_ativa = ESTILOS_NARRATIVOS.get(estilo, {}).get("label", estilo)
    st.success(
        f"Versão ativa: {label_ativa} · Faixa: {perfil_etario(s.get('faixa_etaria'))['short_label']}."
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
        colecao = str(s.get("colecao") or "").strip()
        st.session_state.biblioteca_colecao = carregar_biblioteca_personagens(colecao) if colecao else {}
        st.session_state.etapa = "gerando" if tem_personagens_formais else "personagens"
        st.switch_page("pages/1_📖_Criar_do_Zero.py")

st.caption(
    "Nenhuma versão é aprovada automaticamente. A escolha da autora continua obrigatória antes das ilustrações."
)

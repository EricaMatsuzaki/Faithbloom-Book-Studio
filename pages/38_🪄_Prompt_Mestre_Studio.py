"""Refinamento 24 — Prompt-Mestre Studio.

Central de conformidade editorial, comparação dos quatro estilos narrativos
e geração de Boas-vindas, Pais/Educadores e Ficha Pedagógica.
"""
from __future__ import annotations

import streamlit as st

from estilo import aplicar_estilo, hero
from openrouter_client import chamar_llm
from agents.estilos_narrativos import (
    ESTILOS_NARRATIVOS,
    ORDEM_ESTILOS,
    aplicar_estilo_ao_state,
    gerar_comparativo_estilos,
    normalizar_estilo,
)
from agents.complementos_editoriais import gerar_complementos_editoriais
from prompt_master_compliance import avaliar_prompt_mestre
from age_profiles import normalizar_faixa_etaria, perfil_etario

st.set_page_config(page_title="Prompt-Mestre Studio", page_icon="🪄", layout="wide")
aplicar_estilo()
hero(
    "🪄 Prompt-Mestre Studio",
    "Compare estilos narrativos, gere complementos editoriais e confira a conformidade do livro.",
)

if "state" not in st.session_state:
    st.warning("Comece ou retome um Story Book primeiro. Este Studio trabalha sobre o livro ativo da sessão.")
    st.stop()

s = st.session_state.state
faixa = normalizar_faixa_etaria(s.get("faixa_etaria"))
perfil = perfil_etario(faixa)
s["faixa_etaria"] = faixa
s["age_profile_id"] = faixa
st.caption(f"Faixa etária oficial deste livro: **{perfil['short_label']}**. Este Studio preserva essa decisão em todos os complementos.")

st.subheader("1. Estilo narrativo oficial do livro")
st.caption(
    "A escolha altera a forma de contar a história, mas deve preservar personagens, premissa, "
    "lição cristã, referência bíblica e faixa etária."
)

chave_atual = normalizar_estilo(s.get("estilo_narrativo"))
opcoes = list(ORDEM_ESTILOS)
chave = st.radio(
    "Escolha o estilo",
    options=opcoes,
    index=opcoes.index(chave_atual),
    format_func=lambda k: ESTILOS_NARRATIVOS[k]["label"],
    horizontal=True,
)
st.info(ESTILOS_NARRATIVOS[chave]["descricao"])

if st.button("✅ Definir este como estilo oficial", type="primary"):
    s["estilo_narrativo"] = chave
    s["estilo_narrativo_label"] = ESTILOS_NARRATIVOS[chave]["label"]
    st.success(f"Estilo oficial definido: {ESTILOS_NARRATIVOS[chave]['label']}.")

st.markdown("### Comparar a mesma história nos quatro estilos")
st.caption(
    "A amostra rápida usa menos texto e serve para decidir o tom. A comparação completa gera "
    "quatro histórias inteiras e deve ser usada somente quando você realmente quiser comparar tudo."
)

c1, c2 = st.columns(2)
gerar_amostra = c1.button("✨ Gerar amostra dos 4 estilos", use_container_width=True)
gerar_completa = c2.button("📚 Gerar história completa nos 4 estilos", use_container_width=True)

if gerar_amostra or gerar_completa:
    modo = "completa" if gerar_completa else "amostra"
    with st.spinner("Criando as quatro versões da mesma história..."):
        s["comparativo_estilos"] = gerar_comparativo_estilos(dict(s), chamar_llm, modo=modo)
    st.success("Comparativo pronto. Leia as quatro versões antes de escolher.")

comparativo = s.get("comparativo_estilos") or {}
if comparativo:
    tabs = st.tabs([ESTILOS_NARRATIVOS[k]["label"] for k in ORDEM_ESTILOS])
    for tab, estilo in zip(tabs, ORDEM_ESTILOS):
        with tab:
            versao = comparativo.get(estilo) or {}
            if versao.get("titulo"):
                st.markdown(f"#### {versao['titulo']}")
            if versao.get("sinopse_poetica"):
                st.caption(versao["sinopse_poetica"])

            if versao.get("modo") == "completa" and versao.get("cenas_texto"):
                for cena in versao["cenas_texto"]:
                    if isinstance(cena, dict):
                        st.markdown(f"**Cena {cena.get('numero','')}**")
                        st.write(cena.get("texto", ""))
                    else:
                        st.write(cena)
            else:
                st.write(versao.get("amostra") or "Amostra não disponível.")

            if versao.get("licao_final"):
                st.markdown(f"**Lição de Moral:** {versao['licao_final']}")

            if st.button(
                f"Usar {ESTILOS_NARRATIVOS[estilo]['label']}",
                key=f"usar_estilo_{estilo}",
                use_container_width=True,
            ):
                novo = aplicar_estilo_ao_state(dict(s), estilo, versao)
                s.clear()
                s.update(novo)
                if versao.get("modo") == "completa" and versao.get("cenas_texto"):
                    st.warning(
                        "A versão completa foi aplicada como novo rascunho. Ela precisa passar novamente "
                        "pela revisão editorial antes das ilustrações."
                    )
                else:
                    st.success(f"Estilo escolhido: {ESTILOS_NARRATIVOS[estilo]['label']}.")

st.divider()
st.subheader("2. Complementos editoriais do Prompt-Mestre")
st.caption(
    f"Estes conteúdos são separados da história, seguem a faixa {perfil['short_label']} e podem ser editados pela autora antes da publicação."
)

if st.button("🌸 Gerar Boas-vindas + Pais/Educadores + Ficha Pedagógica", disabled=not s.get("cenas_texto")):
    try:
        with st.spinner("Preparando os complementos editoriais..."):
            extras = gerar_complementos_editoriais(dict(s), chamar_llm)
    except ValueError as exc:
        st.error(str(exc) + " Os complementos anteriores foram preservados.")
    except Exception:
        st.error("Não foi possível concluir a geração. Confira o provedor e tente novamente; os complementos anteriores foram preservados.")
    else:
        s.update(extras)
        st.success("Complementos gerados e validados. Revise antes de finalizar.")

s["boas_vindas"] = st.text_area(
    "👋 Mensagem de boas-vindas",
    value=s.get("boas_vindas", ""),
    height=150,
)

pais = dict(s.get("pais_educadores") or {})
with st.expander("👨‍👩‍👧 Pais e Educadores", expanded=True):
    pais["mensagem"] = st.text_area("Mensagem", value=pais.get("mensagem", ""), height=130)
    pais["tema"] = st.text_input("Tema", value=pais.get("tema", ""))
    pais["emocao_trabalhada"] = st.text_input("Emoção trabalhada", value=pais.get("emocao_trabalhada", ""))
    pais["principio_biblico"] = st.text_input("Princípio bíblico", value=pais.get("principio_biblico", ""))
    pais["habilidade_socioemocional"] = st.text_input(
        "Habilidade socioemocional",
        value=pais.get("habilidade_socioemocional", ""),
        key="pais_habilidade_socioemocional",
    )
    perguntas = st.text_area(
        "Perguntas para conversar com o leitor — uma por linha",
        value="\n".join(pais.get("perguntas") or []),
        height=110,
    )
    aplicacoes = st.text_area(
        "Aplicações em casa, igreja ou escola — uma por linha",
        value="\n".join(pais.get("aplicacoes") or []),
        height=90,
    )
    pais["perguntas"] = [x.strip() for x in perguntas.splitlines() if x.strip()]
    pais["aplicacoes"] = [x.strip() for x in aplicacoes.splitlines() if x.strip()]
s["pais_educadores"] = pais

ficha = dict(s.get("ficha_pedagogica") or {})
ficha["faixa_etaria"] = perfil["short_label"]
with st.expander("🎓 Ficha Pedagógica", expanded=True):
    st.text_input(
        "Faixa etária",
        value=perfil["short_label"],
        disabled=True,
        help="A faixa é definida no projeto e não deve divergir da ficha pedagógica.",
    )
    ficha["tema_central"] = st.text_input("Tema central", value=ficha.get("tema_central", ""))
    ficha["emocao_principal"] = st.text_input("Emoção principal", value=ficha.get("emocao_principal", ""))
    ficha["habilidade_socioemocional"] = st.text_input(
        "Habilidade socioemocional",
        value=ficha.get("habilidade_socioemocional", ""),
        key="ficha_habilidade_socioemocional",
    )
    ficha["valor_cristao"] = st.text_input("Valor cristão", value=ficha.get("valor_cristao", ""))
    ficha["versiculo_referencia"] = st.text_input(
        "Versículo — referência", value=ficha.get("versiculo_referencia", s.get("versiculo_referencia", ""))
    )
    ficha["objetivo_pedagogico"] = st.text_area(
        "Objetivo pedagógico", value=ficha.get("objetivo_pedagogico", ""), height=90
    )
    ficha["psicologia_das_cores"] = st.text_area(
        "Psicologia das cores", value=ficha.get("psicologia_das_cores", ""), height=90
    )
    reflexao = st.text_area(
        "Perguntas de reflexão — uma por linha",
        value="\n".join(ficha.get("perguntas_reflexao") or []),
        height=110,
    )
    ficha["perguntas_reflexao"] = [x.strip() for x in reflexao.splitlines() if x.strip()]
s["ficha_pedagogica"] = ficha

st.divider()
st.subheader("3. Conformidade com o Prompt-Mestre")

s["licao_final"] = st.text_area(
    "⭐ Lição de Moral — OBRIGATÓRIA",
    value=s.get("licao_final", ""),
    height=100,
    help="Sem Lição de Moral o livro não pode ser marcado como pacote pronto.",
)

relatorio = avaliar_prompt_mestre(dict(s))
s["prompt_mestre_compliance"] = relatorio

if relatorio["bloqueios"]:
    st.error("🔴 Há bloqueio de finalização.")
    for item in relatorio["bloqueios"]:
        st.write(f"• {item['mensagem']}")
else:
    st.success("✅ Nenhum bloqueio do Prompt-Mestre.")

if relatorio["recomendacoes"]:
    st.warning("Itens que ainda merecem revisão:")
    for item in relatorio["recomendacoes"]:
        st.write(f"• {item['mensagem']}")

if relatorio["aprovados"]:
    st.caption("Concluídos: " + " • ".join(relatorio["aprovados"]))

st.info("Padrão atual confirmado: 3 páginas para colorir por Story Book.")

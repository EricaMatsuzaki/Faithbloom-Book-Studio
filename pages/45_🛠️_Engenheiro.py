"""Tela manual do Engenheiro de Code Review Profundo.

Você descreve o bug e aponta o arquivo suspeito; o Engenheiro lê o código
real do repositório, propõe uma correção via IA e — só se tiver confiança
alta — abre um Pull Request (Draft) para você revisar. Nada é mesclado
sozinho.
"""
import streamlit as st

from engenheiro_code_review import GITHUB_TOKEN, investigar_e_corrigir

st.title("🛠️ Engenheiro de Code Review Profundo")
st.caption(
    "Descreva o problema real; o Engenheiro lê o código do repositório, propõe uma correção "
    "e abre um PR para você revisar. Ele nunca mescla sozinho nem mexe na release."
)

if not GITHUB_TOKEN:
    st.warning(
        "GITHUB_TOKEN não está configurado nos Secrets deste ambiente. O Engenheiro pode "
        "diagnosticar, mas não vai conseguir abrir o PR de correção até essa chave existir."
    )

descricao = st.text_area(
    "O que está acontecendo?",
    placeholder="Ex.: Ao clicar em 'Ouvir com Charon', aparece 'A voz ficou indisponível nesta tentativa'.",
    height=120,
)
arquivo = st.text_input(
    "Em qual arquivo você acha que está o problema?",
    placeholder="Ex.: jarvis_voice.py",
)

if st.button("Investigar e corrigir", type="primary", disabled=not (descricao.strip() and arquivo.strip())):
    with st.spinner("Lendo o código real, diagnosticando e preparando uma correção..."):
        resultado = investigar_e_corrigir(descricao.strip(), arquivo.strip())

    if resultado.sucesso:
        st.success("Correção proposta e testável. PR aberto para sua revisão.")
        st.markdown(f"**Diagnóstico:** {resultado.diagnostico}")
        st.markdown(f"**O que mudou:** {resultado.resumo}")
        st.markdown(f"[Abrir o Pull Request para revisar →]({resultado.pr_url})")
        st.caption(f"Branch criada: `{resultado.branch}` — Draft, não mesclado, aguardando você.")
    else:
        st.warning(resultado.diagnostico or "Não consegui diagnosticar com segurança.")
        if resultado.motivo_bloqueio:
            st.info(resultado.motivo_bloqueio)

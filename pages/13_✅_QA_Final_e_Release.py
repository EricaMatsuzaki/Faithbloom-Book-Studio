"""Fase 16 — QA final e Release Candidate."""
import json
import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from qa_release import RELEASE_VERSION, rodar_qa_release, salvar_relatorio

st.set_page_config(page_title="QA Final · FaithBloom", page_icon="✅", layout="wide")
aplicar_estilo()
hero(
    "QA Final & Release Candidate",
    "Último quality gate offline antes do deploy da versão consolidada. Não chama IA e não gasta créditos.",
    f"FaithBloom {RELEASE_VERSION} · Fase 16",
)

callout(
    "O que este gate verifica",
    "Sintaxe, requirements, rotas do Streamlit, higiene do pacote, padrões de segredo, projeto piloto de Natal e testes automatizados. Depois deste gate ainda recomendamos um smoke test real no Streamlit Cloud com a OpenRouter.",
    "✅",
)

if st.button("▶️ Rodar QA final", type="primary", use_container_width=True):
    with st.spinner("Executando verificações offline..."):
        st.session_state["qa16"] = rodar_qa_release(incluir_tests=True)

r = st.session_state.get("qa16")
if r:
    a,b,c = st.columns(3)
    a.metric("Release", r["version"])
    b.metric("Erros bloqueantes", len(r["erros"]))
    c.metric("Avisos", len(r["avisos"]))

    if r["ok"]:
        st.success("✅ Quality gate offline aprovado. Release Candidate apta para smoke test no Streamlit Cloud.")
    else:
        st.error("❌ Existem bloqueios. Corrija-os antes de considerar esta versão candidata a release.")

    for grupo, itens in r["grupos"].items():
        with st.expander(grupo, expanded=not all(x["ok"] for x in itens)):
            for x in itens:
                icone = "✅" if x["ok"] else ("⚠️" if x["nivel"] == "aviso" else "❌")
                st.markdown(f"{icone} **{x['nome']}** — {x.get('detalhe','')}")

    st.download_button(
        "⬇️ Baixar relatório QA em JSON",
        data=json.dumps(r, ensure_ascii=False, indent=2),
        file_name=f"faithbloom-{RELEASE_VERSION}-qa.json",
        mime="application/json",
        use_container_width=True,
    )

section_title("Checklist de smoke test real", "Estes itens dependem do ambiente implantado e/ou de chamadas externas.", "Pós-deploy")
for item in [
    "Abrir dashboard e clicar em todas as rotas principais.",
    "Testar uma chamada mínima de texto na OpenRouter.",
    "Gerar apenas 1 referência de personagem e 1 cena piloto.",
    "Confirmar que o guardrail de custo registra a chamada sem expor a chave.",
    "Salvar e reabrir um projeto usando o backend persistente de produção.",
    "Gerar um PDF de prova e abrir visualmente.",
    "Gerar uma capa de prova e conferir dimensões/área do barcode.",
    "Executar o fluxo Retomar com historia_natal.py sem regenerar cenas aprovadas.",
]:
    st.checkbox(item, key=f"qa16_{item}")

st.info("Quando o smoke test real passar, marque a versão como FaithBloom Book Studio 2.0 estável e crie uma tag/release no GitHub.")

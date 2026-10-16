"""Governança: diagnósticos sob demanda, relatórios seguros e revisão humana."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from governance import list_reports, load_report, run_all_diagnostics, save_report
from agents import governanca_ia, governanca_dados, governanca_ti, ciberseguranca
from estilo import aplicar_estilo

st.set_page_config(page_title="Governança FaithBloom", page_icon="🛡️", layout="wide")
aplicar_estilo()
st.title("🛡️ Governança do FaithBloom")
st.write("Confira os controles de IA, dados, tecnologia e cibersegurança. Os agentes apontam evidências, pendências e próximos passos para revisão do engenheiro.")
st.caption("O diagnóstico não faz chamadas de IA, altera livros ou Masters, nem executa publicação ou deploy.")

try:
    from saas_access import current_actor
    actor = current_actor()
except ImportError:
    actor = None
workspace_id = actor.tenant_id if actor is not None and actor.authenticated else "pilot"

agents = [governanca_ia, governanca_dados, governanca_ti, ciberseguranca]
labels = {agent.ROLE_ID: agent.NAME for agent in agents}
selection = st.selectbox("O que deseja verificar?", ["all", *labels], format_func=lambda key: "Todos os quatro agentes" if key == "all" else labels[key])

state = None
if st.checkbox("Incluir os metadados de um livro salvo", value=False):
    from armazenamento import carregar_livro, listar_livros
    try:
        books = listar_livros()
        if books:
            selected = st.selectbox("Livro para diagnóstico", range(len(books)), format_func=lambda index: f"{books[index].get('titulo', 'Sem título')} · {books[index].get('colecao', '')}")
            record = books[selected]
            state = carregar_livro(record.get("colecao", ""), record.get("storage_path") or record.get("arquivo"))
        else:
            st.info("Ainda não há livros salvos. A verificação do sistema continua disponível.")
    except Exception:
        st.error("Não foi possível abrir a biblioteca. Confira o armazenamento e tente novamente.")

st.info("PASS = o controle descrito foi observado. WARN = requer revisão. FAIL = falha observada. UNKNOWN = faltam evidências. Um PASS de código não confirma funcionamento em produção.")
if st.button("Verificar agora", type="primary", use_container_width=True):
    with st.spinner("Conferindo fontes e metadados…"):
        if selection == "all":
            reports = run_all_diagnostics(Path(__file__).resolve().parents[1], state=state)
        else:
            agent = next(agent for agent in agents if agent.ROLE_ID == selection)
            reports = [agent.run_diagnostic(Path(__file__).resolve().parents[1], state=state)]
        st.session_state["governance_reports"] = reports
        st.session_state["governance_reports_workspace"] = workspace_id

# Não mostrar relatórios de uma identidade anterior após uma troca de sessão.
reports = st.session_state.get("governance_reports", []) if st.session_state.get("governance_reports_workspace") == workspace_id else []
for report in reports:
    st.subheader(report["name"])
    counts = report["counts"]
    columns = st.columns(4)
    for column, status in zip(columns, ("PASS", "WARN", "FAIL", "UNKNOWN")):
        column.metric(status, counts[status])
    st.caption(report["scope"])
    for item in report["findings"]:
        with st.expander(f"{item['status']} · {item['title']}"):
            if item["evidence"]:
                st.write("Evidências: " + "; ".join(item["evidence"]))
            else:
                st.write("Ainda não há evidência para este controle.")
            if item["recommendation"]:
                st.write(item["recommendation"])
    left, right = st.columns(2)
    with left:
        if st.button("Salvar relatório no histórico", key="save_governance_" + report["report_id"], use_container_width=True):
            try:
                save_report(report, workspace_id=workspace_id)
                st.success("Relatório salvo. Livros, Masters e relatórios anteriores foram preservados.")
            except Exception:
                st.error("Não foi possível salvar o relatório. Confira o armazenamento antes de tentar novamente.")
    with right:
        st.download_button("Baixar relatório JSON", data=json.dumps(report, ensure_ascii=False, indent=2), file_name=f"faithbloom-{report['role_id']}-{report['report_id']}.json", mime="application/json", key="download_governance_" + report["report_id"], use_container_width=True)

with st.expander("Histórico de diagnósticos"):
    if st.button("Consultar histórico", key="load_governance_history"):
        try:
            st.session_state["governance_history"] = list_reports(workspace_id=workspace_id)
            st.session_state["governance_history_workspace"] = workspace_id
        except Exception:
            st.error("Não foi possível consultar o histórico. Tente novamente após conferir o armazenamento.")
    history = st.session_state.get("governance_history", []) if st.session_state.get("governance_history_workspace") == workspace_id else []
    if history:
        index = st.selectbox("Relatório salvo", range(len(history)), format_func=lambda value: f"{history[value]['name']} · {history[value]['created_at']} · {history[value]['status']}")
        if st.button("Abrir relatório selecionado", key="open_governance_history"):
            try:
                st.session_state["governance_reports"] = [load_report(history[index]["path"], workspace_id=workspace_id)]
                st.session_state["governance_reports_workspace"] = workspace_id
                st.rerun()
            except Exception:
                st.error("O relatório está indisponível ou sua integridade não pôde ser conferida.")
    else:
        st.caption("Consulte o histórico para ver os relatórios salvos neste workspace.")

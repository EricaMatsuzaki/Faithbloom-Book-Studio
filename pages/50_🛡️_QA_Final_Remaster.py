import json
from pathlib import Path
import streamlit as st

from estilo import aplicar_estilo, hero
from book_doctor import listar_projetos
from editorial_remaster_quality import (
    visual_completion_gate,
    rodar_quality_remaster,
    carregar_quality_remaster,
)
from quality_guardian import (
    record_issue_decision,
    register_author_final_approval,
    issue_internal_certificate,
)

st.set_page_config(page_title="QA Final Remaster", page_icon="🛡️", layout="wide")
aplicar_estilo()
hero(
    "🛡️ QA Final — Full Editorial Remaster",
    "Confirme que texto, mapa emocional e todas as páginas visuais foram resolvidos antes do Quality Guardian e da nova publicação.",
)


def _states(project: dict) -> list[dict]:
    root = Path(project.get("pasta", "")) / "remastered" / "editorial"
    out = []
    if root.exists():
        for path in root.glob("*/editorial_remaster.json"):
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(state, dict):
                state["arquivo_estado"] = str(path)
                out.append(state)
    return sorted(out, key=lambda x: str(x.get("atualizado_em") or x.get("criado_em") or ""), reverse=True)

choices = []
for project in listar_projetos():
    if project.get("tipo_projeto") == "story":
        for state in _states(project):
            choices.append((project, state))

if not choices:
    st.warning("Nenhum Full Editorial Remaster encontrado.")
    st.stop()

labels = [f"{s.get('titulo','Sem título')} · {s.get('remaster_id','—')}" for _, s in choices]
idx = st.selectbox("Remaster", range(len(choices)), format_func=lambda i: labels[i])
project, state = choices[idx]

st.markdown("### 1 · Gate visual")
visual = visual_completion_gate(project)
a, b = st.columns(2)
a.metric("Assets resolvidos", visual.get("assets_resolvidos", 0))
b.metric("Pendências", visual.get("assets_pendentes", len(visual.get("pendentes") or [])))
if not visual.get("ok"):
    st.warning("A revisão visual ainda não está completa. Cada página da história precisa ser explicitamente mantida ou ter uma versão Remastered aprovada.")
    if visual.get("pendentes"):
        st.dataframe(visual["pendentes"], use_container_width=True, hide_index=True)
    st.page_link("pages/19_✨_Restoration_Studio.py", label="✨ Voltar ao Restoration Studio →", use_container_width=True)
    st.stop()
st.success("✅ Todas as páginas visuais detectadas da história possuem uma decisão aprovada.")

st.markdown("### 2 · Quality Guardian")
previous = carregar_quality_remaster(state)
if st.button("🛡️ Rodar / atualizar Quality Guardian", type="primary"):
    try:
        report = rodar_quality_remaster(state, project, previous_report=previous or None)
        st.session_state[f"qa_remaster_{state.get('remaster_id')}"] = report
        st.success("Quality Guardian concluído sem correções silenciosas.")
    except Exception as exc:
        st.error(f"Não foi possível rodar o Quality Guardian: {exc}")

report = st.session_state.get(f"qa_remaster_{state.get('remaster_id')}") or previous
if report:
    summary = report.get("summary") or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("Bloqueios abertos", summary.get("open_blockers", 0))
    c2.metric("Decisões pendentes", summary.get("open_decisions", 0))
    c3.metric("Pronto para assinatura", "Sim" if summary.get("ready_for_author_signoff") else "Não")

    open_issues = [x for x in report.get("issues") or [] if x.get("resolution_status") != "resolved" and x.get("requires_decision")]
    if open_issues:
        st.markdown("### 3 · Decisões da autora")
        issue_labels = [f"{x.get('severity','')} · {x.get('location','')} · {x.get('finding','')[:90]}" for x in open_issues]
        issue_idx = st.selectbox("Alerta", range(len(open_issues)), format_func=lambda i: issue_labels[i])
        issue = open_issues[issue_idx]
        st.write("**Problema:**", issue.get("finding", ""))
        st.write("**Por quê:**", issue.get("why", ""))
        if issue.get("suggestion"):
            st.write("**Sugestão:**", issue.get("suggestion"))
        actions = ["corrigir", "resolvido"]
        if issue.get("severity") != "bloqueante":
            actions += ["manter_com_justificativa", "nao_se_aplica"]
        action = st.selectbox("Decisão", actions)
        note = st.text_area("Observação da decisão", key=f"note_{issue.get('id')}")
        if st.button("💾 Registrar decisão"):
            try:
                report = record_issue_decision(report, issue.get("id"), action, note)
                path = Path(state["arquivo_estado"]).parent / "quality_guardian_remaster.json"
                path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                st.session_state[f"qa_remaster_{state.get('remaster_id')}"] = report
                st.success("Decisão registrada. Se marcou como resolvido/corrigir, rode o Guardian novamente após a correção.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    report = st.session_state.get(f"qa_remaster_{state.get('remaster_id')}") or report
    if (report.get("summary") or {}).get("ready_for_author_signoff"):
        st.markdown("### 4 · Aprovação final")
        confirm = st.checkbox("Aprovo esta edição Remastered após revisar o relatório final do Quality Guardian.")
        if st.button("✅ Registrar aprovação final da autora", disabled=not confirm):
            try:
                report = register_author_final_approval(report, True, "Edição Remastered aprovada pela autora.")
                report = issue_internal_certificate(report)
                path = Path(state["arquivo_estado"]).parent / "quality_guardian_remaster.json"
                path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                st.session_state[f"qa_remaster_{state.get('remaster_id')}"] = report
                st.success("Quality Gate interno aprovado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    certificate = (report or {}).get("certificate")
    if certificate:
        st.success(f"🏆 {certificate.get('status')} · {certificate.get('certificate_id')}")
        st.caption(certificate.get("disclaimer", ""))
        st.markdown("### 5 · Preparar nova publicação")
        st.write("O gate interno foi concluído. Agora siga para os motores existentes de preparação da plataforma e distribuição; nenhum envio à Amazon é automático.")
        st.page_link("pages/22_📐_Publishing_Platform_Engine.py", label="📐 Publishing Platform Engine →", use_container_width=True)
        st.page_link("pages/26_🌐_Publishing_Distribution_Center.py", label="🌐 Publishing Distribution Center →", use_container_width=True)

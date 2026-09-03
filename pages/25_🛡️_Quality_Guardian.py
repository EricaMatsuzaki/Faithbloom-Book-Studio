"""Refinamento 10 — FaithBloom Quality Guardian."""
import json
import os
import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from armazenamento import listar_livros, carregar_livro
from activity_studio import list_activity_projects, load_activity_project
from audiobook_studio import list_audiobook_projects, load_audiobook_project
from quality_guardian import (
    SEVERITIES, DOMAIN_LABELS, run_quality_guardian, record_issue_decision,
    register_author_final_approval, issue_internal_certificate,
    build_specialist_review_prompt, normalize_specialist_review,
    merge_specialist_review, save_guardian_report, list_guardian_reports,
    load_guardian_report, export_guardian_report_json,
)

st.set_page_config(page_title="Quality Guardian · FaithBloom", page_icon="🛡️", layout="wide")
aplicar_estilo()
hero(
    "FaithBloom Quality Guardian",
    "Revisão final independente baseada em evidências. O Guardian aponta onde, o que, por quê e como revisar — mas nunca corrige silenciosamente e nunca inventa notas de qualidade.",
    "Refinamento 10 · Final Independent Review",
)

callout(
    "Gate interno, não certificação da plataforma",
    "Mesmo com o Guardian aprovado, mantenha Previewer oficial, EPUBCheck quando aplicável e prova física/revisão humana antes da publicação. O certificado gerado aqui é interno do FaithBloom.",
    "🛡️",
)

# ---------- Fonte do projeto
section_title("1 · Selecionar a obra", "Use um Story Book salvo. Activity Book e Audiobook podem ser vinculados opcionalmente para uma revisão cruzada.", "Project Master")
books = listar_livros()
if not books:
    st.warning("Ainda não há Story Books salvos na Biblioteca Editorial. Salve/retome uma obra antes de executar o Guardian.")
    st.stop()

book_path = st.selectbox(
    "Story Book Master",
    [b["storage_path"] for b in books],
    format_func=lambda x: next((f"{b.get('titulo')} · {b.get('colecao')}" for b in books if b["storage_path"] == x), x),
)
book_meta = next(b for b in books if b["storage_path"] == book_path)
state = carregar_livro(book_meta.get("colecao", ""), book_path)

activities = list_activity_projects()
audio_projects = list_audiobook_projects()
a1, a2 = st.columns(2)
activity_id = a1.selectbox("Activity Book vinculado (opcional)", [""] + [x["id"] for x in activities], format_func=lambda x: "— Não incluir —" if not x else next((p.get("title", x) for p in activities if p.get("id") == x), x))
audio_id = a2.selectbox("Audiobook vinculado (opcional)", [""] + [x["id"] for x in audio_projects], format_func=lambda x: "— Não incluir —" if not x else next((p.get("title", x) + " · " + p.get("locale", "") for p in audio_projects if p.get("id") == x), x))
activity = load_activity_project(activity_id) if activity_id else None
audio = load_audiobook_project(audio_id) if audio_id else None

# ---------- Executar / recuperar
section_title("2 · Rodar o Guardian", "Rerun após uma correção: bloqueios só desaparecem quando o check deixa de encontrá-los. Versões anteriores ficam no relatório salvo.", "Independent Gate")
previous = st.session_state.get("r10_report")
c1, c2 = st.columns(2)
if c1.button("🛡️ Executar Quality Guardian", type="primary", use_container_width=True):
    report = run_quality_guardian(state, activity_project=activity, audiobook_project=audio, previous_report=previous, project_type="story")
    st.session_state.r10_report = save_guardian_report(report)
    st.rerun()
if c2.button("🔁 Reexecutar após correções", use_container_width=True, disabled=not bool(previous)):
    report = run_quality_guardian(state, activity_project=activity, audiobook_project=audio, previous_report=previous, project_type="story")
    st.session_state.r10_report = save_guardian_report(report)
    st.rerun()

report = st.session_state.get("r10_report")
if not report:
    recent = list_guardian_reports()
    if recent:
        rid = st.selectbox("Ou abrir relatório anterior", [""] + [x["id"] for x in recent], format_func=lambda x: "—" if not x else next((f"{r.get('project_title')} · run {r.get('run_number')} · {r.get('open_blockers')} bloqueios" for r in recent if r["id"] == x), x))
        if rid and st.button("Abrir relatório"):
            st.session_state.r10_report = load_guardian_report(rid); st.rerun()
    st.stop()

# ---------- Resumo
section_title("3 · Painel do Quality Gate", "Sem porcentagens fictícias: o painel mostra somente alertas, decisões e evidências dos checks executados.", "Evidence")
s = report.get("summary", {})
cols = st.columns(5)
cols[0].metric("Run", report.get("run_number", 1))
cols[1].metric("🔴 Bloqueios", s.get("open_blockers", 0))
cols[2].metric("Decisões abertas", s.get("open_decisions", 0))
cols[3].metric("🟠 Recomendados", (s.get("counts") or {}).get("recomendado", 0))
cols[4].metric("Domínios aplicáveis", s.get("applicable_domains", 0))

if s.get("ready_for_author_signoff"):
    st.success("🟢 Não há bloqueios nem decisões pendentes. A obra pode seguir para a aprovação final humana.")
else:
    st.warning("O gate ainda não está pronto para assinatura final. Resolva os bloqueios e registre decisões para os demais alertas aplicáveis.")

st.markdown("#### Domínios")
dcols = st.columns(3)
for i, (key, d) in enumerate(report.get("domains", {}).items()):
    status = d.get("status")
    icon = {"blocked": "🔴", "review": "🟡", "pass": "🟢", "not_applicable": "⚪"}.get(status, "🟡")
    dcols[i % 3].markdown(f"{icon} **{d.get('label', DOMAIN_LABELS.get(key,key))}**  \n`{status}`")

# ---------- Alertas e decisões
section_title("4 · Alertas & decisões", "Cada alerta informa local, achado, motivo, sugestão e evidência. A autora decide; nenhuma alteração é aplicada pelo Guardian.", "Author Control")
issues = sorted(report.get("issues", []), key=lambda x: (-SEVERITIES.get(x.get("severity"), {"rank":0})["rank"], x.get("domain", ""), x.get("location", "")))
filters = st.multiselect("Filtrar severidade", list(SEVERITIES), default=list(SEVERITIES), format_func=lambda x: f"{SEVERITIES[x]['icon']} {SEVERITIES[x]['label']}")
for x in [i for i in issues if i.get("severity") in filters]:
    meta = SEVERITIES[x["severity"]]
    decision = x.get("decision") or {}
    state_label = "✅ decisão concluída" if x.get("resolution_status") == "resolved" else ("🔁 requer recheck" if x.get("resolution_status") == "pending_recheck" else "aberto")
    with st.expander(f"{meta['icon']} {meta['label']} · {DOMAIN_LABELS.get(x.get('domain'), x.get('domain'))} · {x.get('location')} · {state_label}", expanded=x["severity"] == "bloqueante"):
        st.markdown(f"**O que foi encontrado:** {x.get('finding','')}")
        st.markdown(f"**Por que importa:** {x.get('why','')}")
        if x.get("suggestion"): st.markdown(f"**Sugestão:** {x.get('suggestion')}")
        if x.get("before"): st.text_area("Antes / conteúdo sinalizado", value=x.get("before"), disabled=True, key=f"before_{x['id']}")
        if x.get("evidence"):
            with st.popover("Ver evidência estruturada"):
                st.json(x.get("evidence"))
        if decision:
            st.caption(f"Decisão registrada: {decision.get('action')} · {decision.get('note','')}")
        if x.get("requires_decision"):
            dc1, dc2 = st.columns([1, 2])
            action = dc1.selectbox("Decisão", ["corrigir", "resolvido", "manter_com_justificativa", "nao_se_aplica"], key=f"act_{x['id']}", help="‘resolvido’ exige reexecutar o Guardian. Bloqueios não podem ser ignorados por justificativa.")
            note = dc2.text_input("Nota/justificativa", key=f"note_{x['id']}")
            if st.button("Registrar decisão", key=f"dec_{x['id']}"):
                try:
                    report = record_issue_decision(report, x["id"], action, note)
                    st.session_state.r10_report = save_guardian_report(report); st.rerun()
                except Exception as exc: st.error(str(exc))

# ---------- segunda opinião IA
section_title("5 · Revisores independentes opcionais", "A segunda opinião não modifica o livro. Bible Guard envia referência/contexto, nunca o texto bíblico protegido para tradução/paráfrase.", "Specialist Review")
focus = st.selectbox("Especialidade", ["editorial", "child_readability", "biblical_context", "cross_modal"], format_func=lambda x: {"editorial":"Editorial/continuidade", "child_readability":"Legibilidade infantil", "biblical_context":"Contexto bíblico/teológico", "cross_modal":"Texto × imagem / multimodal"}[x])
has_key = bool(os.environ.get("OPENROUTER_API_KEY"))
if st.button("🤖 Solicitar segunda opinião independente", disabled=not has_key):
    try:
        from openrouter_client import chamar_llm
        system, user = build_specialist_review_prompt(state, focus)
        raw = chamar_llm(system, user)
        review = normalize_specialist_review(raw, focus)
        report = merge_specialist_review(report, review)
        # registra no estado em memória para que o check bíblico possa reconhecer a revisão no próximo rerun
        if focus == "biblical_context":
            state.setdefault("guardian_specialist_reviews", {})["biblical"] = {"approved": True, "reviewed_at": review.get("reviewed_at")}
        st.session_state.r10_report = save_guardian_report(report); st.rerun()
    except Exception as exc:
        st.error(f"Revisor independente: {exc}")
if not has_key:
    st.caption("A revisão offline continua disponível. Configure OPENROUTER_API_KEY somente se quiser uma segunda opinião por IA.")

# ---------- assinatura e certificado
section_title("6 · Aprovação final humana", "O Guardian só libera o certificado interno quando não há bloqueios nem alertas que exijam decisão.", "Final Sign-off")
confirm = st.checkbox("Eu revisei os alertas, decisões e evidências e aprovo esta versão para seguir ao gate de publicação.")
final_note = st.text_input("Nota final (opcional)")
if st.button("✅ Registrar aprovação final", disabled=not confirm):
    try:
        report = register_author_final_approval(report, True, final_note)
        st.session_state.r10_report = save_guardian_report(report); st.rerun()
    except Exception as exc: st.error(str(exc))

if (report.get("author_final_approval") or {}).get("approved"):
    st.success("Aprovação final humana registrada.")
    if not report.get("certificate") and st.button("🏅 Emitir certificado interno do Quality Gate"):
        try:
            report = issue_internal_certificate(report)
            st.session_state.r10_report = save_guardian_report(report); st.rerun()
        except Exception as exc: st.error(str(exc))

cert = report.get("certificate")
if cert:
    st.success(f"🏅 {cert.get('certificate_id')} · INTERNAL QUALITY GATE PASSED")
    st.caption(cert.get("disclaimer"))

st.download_button(
    "⬇️ Baixar relatório completo em JSON",
    data=export_guardian_report_json(report),
    file_name=f"faithbloom-quality-guardian-{report.get('id','report')[:10]}.json",
    mime="application/json",
    use_container_width=True,
)

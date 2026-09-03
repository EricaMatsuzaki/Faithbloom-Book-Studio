"""Refinamento 19 — Real Pilot & Bug Fix Center."""
from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from real_pilot import (
    PILOT_PROFILES, run_pilot, list_pilot_runs, register_bug, list_bugs,
    update_bug_status, pilot_readiness,
)

st.set_page_config(page_title="Real Pilot & Bug Fix", page_icon="🧪", layout="wide")
aplicar_estilo()
hero(
    "🧪 Real Pilot & Bug Fix",
    "Atravesse o FaithBloom com livros reais, registre evidências e feche bugs antes da próxima candidata a Stable.",
    "Refinamento 19 · sem IA e sem alterar os originais",
)

callout(
    "Piloto não corrige o livro sozinho",
    "A auditoria rápida mede estrutura, XObjects, página, texto e possíveis repetições. Alertas editoriais/visuais precisam de confirmação antes de qualquer correção.",
    "🔒",
)

pilot_tab, bugs_tab, gate_tab = st.tabs(["📚 Projetos-piloto", "🐞 Bug Registry", "🚦 Readiness"])


def cache_upload(uploaded) -> str:
    data = uploaded.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    ext = Path(uploaded.name).suffix or ".bin"
    folder = Path(".faithbloom_cache") / "pilot_uploads"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest[:24]}{ext}"
    if not path.exists():
        path.write_bytes(data)
    return str(path)


with pilot_tab:
    section_title("Executar piloto real", "Use seus PDFs reais; o arquivo de origem permanece inalterado.", "Real data")
    pid = st.selectbox("Perfil do piloto", list(PILOT_PROFILES), format_func=lambda x: PILOT_PROFILES[x]["label"])
    profile = PILOT_PROFILES[pid]
    st.caption(profile.get("notes", ""))
    interior = st.file_uploader("PDF do miolo *", type=["pdf"], key="pilot_interior")
    cover = st.file_uploader("Capa/wrap PDF (opcional)", type=["pdf"], key="pilot_cover")
    st.caption("Para PDFs grandes, o piloto usa metadados dos XObjects sem decodificar todas as imagens. Isso evita travar a auditoria apenas para contar pixels.")
    if st.button("🧪 Executar piloto", type="primary", use_container_width=True, disabled=interior is None):
        try:
            with st.spinner("Auditando o PDF real sem modificar o original..."):
                ipath = cache_upload(interior)
                cpath = cache_upload(cover) if cover else None
                report = run_pilot(ipath, pid, cover_path=cpath, save=True)
            st.session_state["faithbloom_last_real_pilot"] = report
            st.success("Piloto concluído e evidência registrada.")
        except Exception as exc:
            st.error(f"Falha no piloto: {type(exc).__name__}: {exc}")

    report = st.session_state.get("faithbloom_last_real_pilot")
    if report:
        audit = report.get("interior") or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Páginas", audit.get("pages_total", 0))
        c2.metric("XObjects de imagem", audit.get("image_xobjects_total", 0))
        c3.metric("Sobreposições textuais", len(audit.get("adjacent_text_overlap") or []))
        c4.metric("Gate", report.get("gate", {}).get("status", "—"))
        st.write("**Tamanho(s) de página:**", audit.get("page_sizes_in"))
        st.caption(audit.get("ppi_note", ""))
        alerts = audit.get("alerts") or []
        if alerts:
            st.markdown("#### Alertas")
            for a in alerts:
                icon = "🔴" if a.get("severity") == "blocker" else "🟡"
                st.write(f"{icon} **{a.get('area')}** — {a.get('message')}")
        overlaps = audit.get("adjacent_text_overlap") or []
        if overlaps:
            st.markdown("#### Páginas para inspeção editorial")
            st.dataframe(overlaps, use_container_width=True, hide_index=True)
        repeated = audit.get("repeated_bible_reference") or []
        if repeated:
            st.markdown("#### Bible Guard — camada textual")
            st.dataframe(repeated, use_container_width=True, hide_index=True)
        with st.expander("Evidência completa do piloto"):
            st.json(report)

    runs = list_pilot_runs()
    if runs:
        st.markdown("#### Histórico de pilotos")
        for run in runs[:12]:
            st.write(f"**{run.get('profile', {}).get('label', run.get('profile_id'))}** · {run.get('created_at')} · `{run.get('gate', {}).get('status')}` · {run.get('interior', {}).get('pages_total', 0)} páginas")

with bugs_tab:
    section_title("Bug Registry", "Bug corrigido só fecha o gate depois de reteste com evidência.", "QA")
    with st.form("pilot_bug_form"):
        title = st.text_input("Título do bug *")
        c1, c2 = st.columns(2)
        module = c1.text_input("Módulo", placeholder="Ex.: Book Doctor")
        severity = c2.selectbox("Severidade", ["blocker", "high", "medium", "low"], index=2)
        reproduction = st.text_area("Como reproduzir")
        evidence = st.text_area("Evidência inicial")
        if st.form_submit_button("Registrar bug", use_container_width=True):
            try:
                register_bug(title, module=module, severity=severity, reproduction=reproduction, evidence=evidence)
                st.success("Bug registrado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    bugs = list_bugs(include_closed=True)
    if not bugs:
        st.info("Nenhum bug registrado.")
    for bug in bugs:
        with st.expander(f"{bug.get('severity', '').upper()} · {bug.get('title')} · {bug.get('status')}"):
            st.write("**Módulo:**", bug.get("module") or "—")
            if bug.get("reproduction"): st.write("**Reprodução:**", bug.get("reproduction"))
            if bug.get("evidence"): st.write("**Evidência:**", bug.get("evidence"))
            status = st.selectbox("Novo status", ["open", "investigating", "fixed", "verified", "wont-fix"], index=["open", "investigating", "fixed", "verified", "wont-fix"].index(bug.get("status", "open")), key=f"bug_status_{bug['id']}")
            retest = st.text_area("Evidência do reteste", key=f"bug_evidence_{bug['id']}")
            if st.button("Atualizar bug", key=f"bug_update_{bug['id']}"):
                try:
                    update_bug_status(bug["id"], status, evidence=retest)
                    st.success("Bug atualizado.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

with gate_tab:
    section_title("Readiness para próxima candidata", "Só avança depois dos três pilotos e sem bugs blocker/high abertos.", "Gate")
    ready = pilot_readiness()
    if ready.get("ready_for_next_candidate"):
        st.success("✅ Pilotos mínimos concluídos e nenhum bloqueio conhecido deste gate.")
    else:
        st.warning("Ainda não está pronto para gerar a próxima candidata a Stable.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pilotos concluídos", len(ready.get("profiles_completed") or []))
    c2.metric("Pilotos faltando", len(ready.get("profiles_missing") or []))
    c3.metric("Bugs blocker/high", len(ready.get("open_blocking_bugs") or []))
    if ready.get("profiles_missing"):
        st.write("**Faltam:**", ", ".join(PILOT_PROFILES[x]["label"] for x in ready["profiles_missing"]))
    if ready.get("open_blocking_bugs"):
        st.dataframe(ready["open_blocking_bugs"], use_container_width=True, hide_index=True)
    st.caption(ready.get("note", ""))
    with st.expander("Readiness JSON"):
        st.json(ready)

import json
import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from production_deployment import deployment_readiness, streamlit_oidc_identity
from qa_release import rodar_qa_release
from release_info import VERSION
from stable_candidate import (
    build_evidence_bundle_bytes,
    build_rollback_plan,
    candidate_is_current,
    cloud_launch_checklist,
    create_release_candidate,
    evaluate_cloud_launch_evidence,
    list_release_candidates,
    load_evidence_draft,
    record_manual_signoff,
    release_candidate_gate,
    save_evidence_draft,
    source_release_manifest,
    stable_promotion_gate,
)

st.set_page_config(page_title="Stable Candidate & Cloud Launch", page_icon="🏆", layout="wide")
aplicar_estilo()
hero(
    "Stable Candidate & Cloud Launch",
    "Consolide evidências reais, congele o fingerprint do código e prepare uma candidata auditável antes da tag Stable.",
    "Refinamento 15 · release candidate, não publicação automática",
)

identity = streamlit_oidc_identity(st)
actor = identity.get("email") or identity.get("name") or "owner"

t1, t2, t3, t4, t5 = st.tabs(["🧾 Código & QA", "☁️ Evidências Cloud", "🏆 Criar Candidate", "↩️ Rollback", "✅ Promoção Stable"])

with t1:
    section_title("Manifest da candidata", "O fingerprint cobre código Python, requirements e configuração versionada — não dados runtime nem relatórios gerados.", "Source freeze")
    manifest = source_release_manifest()
    c1, c2, c3 = st.columns(3)
    c1.metric("Arquivos", manifest["file_count"])
    c2.metric("Bytes", manifest["bytes"])
    c3.metric("Fingerprint", manifest["source_fingerprint"][:12])
    with st.expander("Ver manifest completo"):
        st.json(manifest)

    if st.button("Rodar QA offline da candidata", use_container_width=True):
        st.session_state["r15_qa"] = rodar_qa_release(incluir_tests=True)
    qa = st.session_state.get("r15_qa")
    if qa:
        (st.success if qa.get("ok") else st.error)("✅ QA offline aprovado" if qa.get("ok") else "🔴 QA offline encontrou falhas")
        st.json(qa)
    else:
        st.info("Rode o QA offline antes de criar a candidata. O gate da candidata não substitui os testes cloud.")

with t2:
    section_title("Evidências reais de Cloud Launch", "Para os itens obrigatórios, marcar como concluído sem nota ou referência não é suficiente para uma candidata Stable.", "Evidence")
    draft = st.session_state.get("r15_evidence") or load_evidence_draft()
    items = draft.get("items", {})
    for spec in cloud_launch_checklist():
        current = items.get(spec["id"], {})
        with st.container(border=True):
            done = st.checkbox(("Obrigatório · " if spec["required"] else "Opcional · ") + spec["label"], value=bool(current.get("done")), key=f"r15_done_{spec['id']}")
            note = st.text_input("Evidência / observação", value=current.get("note", ""), key=f"r15_note_{spec['id']}", placeholder="Ex.: validado após redeploy; projeto Teste RC recarregado sem perda")
            ref = st.text_input("Referência opcional", value=current.get("reference", ""), key=f"r15_ref_{spec['id']}", placeholder="Ex.: ID interno, screenshot, issue, runbook, data/hora")
            items[spec["id"]] = {"done": done, "note": note, "reference": ref, "actor": actor}
    draft = {"schema": "faithbloom.cloud-launch-evidence.v1", "items": items}
    st.session_state["r15_evidence"] = draft
    if st.button("Salvar rascunho de evidências", use_container_width=True):
        st.session_state["r15_evidence"] = save_evidence_draft(draft, actor=actor)
        st.success("Rascunho salvo no storage atual.")
    ev = evaluate_cloud_launch_evidence(draft)
    (st.success if ev["cloud_launch_evidence_passed"] else st.warning)(
        f"{ev['required_done']}/{ev['required_total']} itens obrigatórios marcados · {len(ev['required_without_detail'])} sem detalhe de evidência"
    )
    st.json(ev)

with t3:
    section_title("Criar Release Candidate registrada", "A candidata congela o fingerprint e guarda as evidências. Não cria tag Git nem publica o app.", "Candidate")
    dep = deployment_readiness()
    qa = st.session_state.get("r15_qa")
    draft = st.session_state.get("r15_evidence") or load_evidence_draft()
    gate = release_candidate_gate(draft, deployment_ready=dep.get("ready_for_cloud_validation"), deployment_detail=dep, qa_ok=bool(qa and qa.get("ok")))
    (st.success if gate["candidate_ready"] else st.error)("✅ Candidate Gate: PASS" if gate["candidate_ready"] else "🔴 Candidate Gate: BLOCKED")
    st.json(gate)
    version = st.text_input("Versão da candidata", value=VERSION)
    previous = st.text_input("Versão anterior preservada", value="2.0.0-rc3-pilot")
    notes = st.text_area("Notas da candidata", placeholder="Mudanças, limitações conhecidas, escopo do smoke test...")
    if st.button("🏆 Criar candidata", type="primary", disabled=not gate["candidate_ready"], use_container_width=True):
        record = create_release_candidate(version=version, evidence=draft, qa_report=qa, deployment_ready=True, deployment_detail=dep, actor=actor, previous_version=previous, notes=notes)
        st.session_state["r15_candidate_id"] = record["candidate_id"]
        st.success(f"Candidata registrada: {record['candidate_id']}")

    candidates = list_release_candidates()
    if candidates:
        idx = st.selectbox("Candidatas registradas", range(len(candidates)), format_func=lambda i: f"{candidates[i].get('version')} · {candidates[i].get('candidate_id')} · {candidates[i].get('status')}")
        c = candidates[idx]
        freshness = candidate_is_current(c)
        (st.success if freshness["current"] else st.warning)("Fingerprint ainda vigente" if freshness["current"] else "Código/configuração mudou desde esta candidata")
        st.download_button("⬇️ Baixar Evidence Bundle", build_evidence_bundle_bytes(c), file_name=f"FaithBloom-{c.get('version','candidate')}-evidence.zip", mime="application/zip")

with t4:
    section_title("Rollback preservado", "Rollback de código e dados são separados; nenhum passo apaga automaticamente storage ou Book Masters.", "Recovery")
    plan = build_rollback_plan(candidate_version=VERSION)
    st.json(plan)
    st.download_button("Baixar plano de rollback", json.dumps(plan, ensure_ascii=False, indent=2), file_name="faithbloom-rollback-plan.json", mime="application/json")
    callout("Regra de segurança", "Se houver problema após deploy, reverta primeiro o código. Só restaure dados quando existir evidência de corrupção ou migração incorreta — e inicialmente como cópia de trabalho.", "🔒")

with t5:
    section_title("Sign-off e Promotion Gate", "Mesmo com todos os checks verdes, a tag Stable é uma decisão humana separada.", "Stable")
    candidates = list_release_candidates()
    if not candidates:
        st.info("Ainda não há candidata registrada.")
    else:
        idx = st.selectbox("Candidate para promoção", range(len(candidates)), format_func=lambda i: f"{candidates[i].get('version')} · {candidates[i].get('candidate_id')}", key="r15_promo_candidate")
        candidate = candidates[idx]
        note = st.text_area("Nota de sign-off", value=(candidate.get("manual_signoff") or {}).get("note", ""))
        approved = st.checkbox("Eu revisei a candidata e aprovo o sign-off humano para promoção manual", value=bool((candidate.get("manual_signoff") or {}).get("approved")))
        if st.button("Registrar sign-off", use_container_width=True):
            candidate = record_manual_signoff(candidate["candidate_id"], approved=approved, actor=actor, note=note)
            st.success("Sign-off registrado.")
        gate = stable_promotion_gate(candidate)
        (st.success if gate["ready_to_tag_stable_manually"] else st.error)("✅ Promotion Gate: PASS" if gate["ready_to_tag_stable_manually"] else "🔴 Promotion Gate: BLOCKED")
        st.json(gate)
        callout("Sem automação de publicação", "PASS significa apenas que a equipe pode criar manualmente a tag Stable depois de revisar o Evidence Bundle. O FaithBloom não cria a tag, não faz deploy e não publica livros automaticamente.", "🏆")

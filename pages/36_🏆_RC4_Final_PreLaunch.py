"""Refinamento 20 — RC4 Final Pre-Launch Gate."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from final_prelaunch import (
    build_prelaunch_test_plan, final_prelaunch_gate, load_prelaunch_evidence,
    save_prelaunch_evidence, create_final_candidate_record, list_final_candidates,
    record_final_signoff, final_stable_promotion_gate, build_final_evidence_bundle_bytes,
)
from production_deployment import deployment_readiness
from qa_release import rodar_qa_release

st.set_page_config(page_title="RC4 Final Pre-Launch", page_icon="🏆", layout="wide")
aplicar_estilo()
hero(
    "🏆 RC4 Final Pre-Launch Gate",
    "A última candidata só pode nascer depois dos pilotos reais, QA, configuração de produção e evidências verdadeiras do Cloud E2E.",
    "Refinamento 20 · Stable continua sendo promoção manual",
)

callout(
    "Este painel não simula o Streamlit Cloud",
    "Evidências de boot, login, storage, OpenRouter, restart/redeploy e persistência devem vir do ambiente real. Sem isso, o gate permanece bloqueado por design.",
    "☁️",
)

tab_plan, tab_evidence, tab_gate, tab_candidates = st.tabs(["🧪 Plano cloud", "📝 Evidências", "🚦 Gate RC4", "🏆 Candidatas"])

with tab_plan:
    section_title("Plano de validação real", "Use esta sequência no deploy de produção e registre uma evidência verificável para cada item obrigatório.", "Cloud")
    for row in build_prelaunch_test_plan():
        icon = "🔴" if row.get("required") else "🔵"
        st.markdown(f"**{icon} {row.get('label')}**")
        st.caption(row.get("how_to_validate", ""))
    plan_json = json.dumps(build_prelaunch_test_plan(), ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("⬇️ Baixar plano de testes cloud", plan_json, file_name="faithbloom-rc4-cloud-test-plan.json", mime="application/json")

with tab_evidence:
    section_title("Evidências do Cloud E2E", "Checkbox sem nota ou referência não passa nos itens obrigatórios.", "Evidence")
    evidence = load_prelaunch_evidence()
    items = evidence.get("items") or {}
    actor = st.text_input("Responsável pela validação", value="")
    for spec in build_prelaunch_test_plan():
        current = items.get(spec["id"], {})
        with st.expander(("🔴 " if spec.get("required") else "🔵 ") + spec["label"], expanded=False):
            done = st.checkbox("Validado no ambiente real", value=bool(current.get("done")), key=f"rc4_done_{spec['id']}")
            note = st.text_area("Nota/evidência", value=current.get("note", ""), key=f"rc4_note_{spec['id']}", placeholder="Ex.: projeto Teste RC4 permaneceu disponível após redeploy de 03/09/2026.")
            reference = st.text_input("Referência (opcional)", value=current.get("reference", ""), key=f"rc4_ref_{spec['id']}", placeholder="Ex.: log interno, issue, screenshot ou identificador de deploy")
            items[spec["id"]] = {**current, "done": done, "note": note, "reference": reference, "actor": actor or current.get("actor", "")}
    if st.button("💾 Salvar evidências", type="primary", use_container_width=True):
        save_prelaunch_evidence({"items": items}, actor=actor)
        st.success("Evidências salvas. Nenhum item foi validado automaticamente.")

with tab_gate:
    section_title("Gate da candidata final", "PASS exige pilotos + QA + readiness de produção + Cloud E2E real.", "Gate")
    qa = rodar_qa_release(incluir_tests=False)
    dep = deployment_readiness()
    evidence = load_prelaunch_evidence()
    gate = final_prelaunch_gate(evidence, qa_ok=qa.get("ok", False), deployment_ready=dep.get("ready_for_cloud_validation", False))
    if gate.get("status") == "PASS":
        st.success("✅ Gate RC4 PASS — uma candidata final pode ser registrada.")
    else:
        st.warning("🔒 Gate RC4 BLOCKED — isso é esperado enquanto faltarem evidências reais de produção.")
    st.dataframe(gate.get("checks") or [], use_container_width=True, hide_index=True)
    with st.expander("Detalhes do gate"):
        st.json(gate)

    st.markdown("#### Registrar RC4")
    c1, c2 = st.columns(2)
    version = c1.text_input("Versão da candidata", value="2.0.0-rc4")
    previous = c2.text_input("Versão anterior preservada", value="2.0.0-rc3-pilot")
    who = st.text_input("Criada por", value="owner")
    notes = st.text_area("Notas da candidata")
    if st.button("🏆 Criar RC4", type="primary", disabled=gate.get("status") != "PASS"):
        try:
            record = create_final_candidate_record(
                version=version, evidence=evidence, qa_report=qa,
                deployment_ready=dep.get("ready_for_cloud_validation", False),
                actor=who, previous_version=previous, notes=notes,
            )
            st.success(f"Candidata registrada: {record['candidate_id']}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

with tab_candidates:
    section_title("Candidatas finais", "A promoção para Stable continua exigindo fingerprint vigente e sign-off humano.", "Release")
    candidates = list_final_candidates()
    if not candidates:
        st.info("Nenhuma RC4 registrada — o gate só permitirá criar uma após o Cloud E2E real.")
    for row in candidates:
        with st.expander(f"{row.get('version')} · {row.get('candidate_id')} · {row.get('status')}"):
            promotion = final_stable_promotion_gate(row)
            st.write("**Promotion Gate:**", promotion.get("status"))
            st.dataframe(promotion.get("checks") or [], use_container_width=True, hide_index=True)
            actor = st.text_input("Responsável pelo sign-off", key=f"sign_actor_{row['candidate_id']}")
            note = st.text_area("Nota do sign-off", key=f"sign_note_{row['candidate_id']}")
            approved = st.checkbox("Aprovo esta candidata após revisar evidências", key=f"sign_approved_{row['candidate_id']}")
            if st.button("Registrar sign-off", key=f"sign_btn_{row['candidate_id']}"):
                try:
                    record_final_signoff(row["candidate_id"], approved=approved, actor=actor, note=note)
                    st.success("Sign-off registrado.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            st.download_button(
                "⬇️ Evidence Bundle RC4",
                build_final_evidence_bundle_bytes(row),
                file_name=f"{row.get('candidate_id')}-evidence.zip",
                mime="application/zip",
                key=f"bundle_{row['candidate_id']}",
            )

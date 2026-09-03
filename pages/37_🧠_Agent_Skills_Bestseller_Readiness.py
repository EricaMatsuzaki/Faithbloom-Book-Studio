"""Refinamento 21 — Agent Skills & Bestseller Readiness System."""
from __future__ import annotations

import streamlit as st

from agent_skills import all_agent_profiles, get_agent_profile, validate_registry
from bestseller_readiness import evaluate_bestseller_readiness
from biblical_reference_validator import (
    create_reference_candidate, validate_reference_candidate, reference_gate,
)
from market_intelligence import (
    OBSERVED_SOURCE_TYPES, make_market_evidence, validate_market_evidence,
    build_market_brief, classify_market_mode,
)
from armazenamento import listar_livros, carregar_livro, atualizar_livro_salvo

st.set_page_config(page_title="Agent Skills & Bestseller Readiness", page_icon="🧠", layout="wide")
st.title("🧠 Agent Skills & Bestseller Readiness")
st.caption(
    "Skills formais por agente + validação bíblica + evidência de mercado + readiness de fatores controláveis. "
    "O FaithBloom não prevê nem garante best-seller."
)

books = listar_livros()
selected_book = None
state = None
if books:
    labels = [f"{x.get('titulo','(sem título)')} · {x.get('colecao','')}" for x in books]
    idx = st.selectbox("Book Master para auditoria", range(len(books)), format_func=lambda i: labels[i])
    selected_book = books[idx]
    state = carregar_livro(selected_book.get("colecao", ""), selected_book.get("storage_path") or selected_book.get("arquivo"))
else:
    st.info("Nenhum Story Book salvo ainda. A biblioteca de skills pode ser auditada mesmo sem projeto.")


def persist(msg: str):
    if selected_book and state is not None:
        atualizar_livro_salvo(selected_book.get("storage_path") or selected_book.get("arquivo"), state)
        st.success(msg)


t1, t2, t3, t4 = st.tabs(["🤖 Skills dos agentes", "📈 Bestseller Readiness", "📖 Referência bíblica", "🔎 Evidência de mercado"])

with t1:
    audit = validate_registry()
    c1, c2, c3 = st.columns(3)
    c1.metric("Papéis especializados", audit.get("role_count", 0))
    c2.metric("Módulos agents/", audit.get("module_count", 0))
    c3.metric("Registry", "PASS" if audit.get("ok") else "BLOCKED")
    if audit.get("ok"):
        st.success("Todos os papéis possuem missão, skills, critérios, limites e handoffs formais.")
    else:
        st.error("O registry possui inconsistências.")
        st.json(audit.get("errors", []))

    profiles = all_agent_profiles()
    role_ids = [x["role_id"] for x in profiles]
    rid = st.selectbox("Ver agente/papel", role_ids, format_func=lambda x: get_agent_profile(x)["name"])
    p = get_agent_profile(rid)
    st.subheader(p["name"])
    st.write(p["mission"])
    a, b = st.columns(2)
    with a:
        st.markdown("**Skills obrigatórias**")
        for x in p["skills"]:
            st.write("•", x)
        st.markdown("**Critérios de qualidade**")
        for x in p["quality_criteria"]:
            st.write("•", x)
    with b:
        st.markdown("**Handoffs esperados**")
        for x in p["required_handoffs"]:
            st.write("•", x)
        st.markdown("**Limites / não fazer**")
        for x in p["forbidden"]:
            st.write("•", x)
        if p["evidence_requirements"]:
            st.markdown("**Evidências necessárias**")
            for x in p["evidence_requirements"]:
                st.write("•", x)
    st.caption(f"Módulo: agents/{p['module']} · execução: {p['execution']}")

with t2:
    if state is None:
        st.info("Salve/abra um Story Book para calcular readiness.")
    else:
        report = evaluate_bestseller_readiness(state)
        status = report["status"]
        if status == "CONTROLLED_FACTORS_READY":
            st.success("🟢 Fatores controláveis prontos para revisão comercial/humana.")
        elif status == "BLOCKED":
            st.error("🔴 Existem fatores controláveis bloqueantes.")
        else:
            st.warning(f"🟡 {status.replace('_', ' ').title()}")
        st.info(report["notice"])
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Critérios", report["counts"]["total"])
        m2.metric("Pass", report["counts"]["pass"])
        m3.metric("Revisar", report["counts"]["needs_review"])
        m4.metric("Evidência pendente", report["counts"]["needs_evidence"])
        for item in report["criteria"]:
            icon = {"PASS": "🟢", "NEEDS_WORK": "🟠", "NEEDS_REVIEW": "🟡", "NEEDS_EVIDENCE": "🔎"}.get(item["status"], "⚪")
            with st.expander(f"{icon} {item['label']} · {item['status']}"):
                st.write(item["detail"])
                if item.get("action"):
                    st.caption("Próxima ação: " + item["action"])
                if item.get("evidence"):
                    st.json(item["evidence"])
        if st.button("💾 Salvar Bestseller Readiness neste projeto", use_container_width=True):
            state["bestseller_readiness_report"] = report
            state["agent_skill_audit"] = validate_registry()
            persist("Readiness e auditoria de skills salvos no Book Master.")

with t3:
    if state is None:
        st.info("Abra um Story Book cristão para validar a referência.")
    else:
        ref = st.text_input("Referência", value=state.get("versiculo_referencia", ""), help="Ex.: Lucas 2:11. O texto bíblico completo não é inserido nem traduzido aqui.")
        existing = state.get("bible_reference_candidate") or create_reference_candidate(ref, suggested_by="manual")
        if existing.get("reference") != ref:
            existing = create_reference_candidate(ref, suggested_by="manual")
        gate = reference_gate({**state, "versiculo_referencia": ref})
        if gate["ok"]:
            st.success("✅ Referência/contexto já validados para este projeto.")
        else:
            st.warning("⚠️ A referência ainda é candidata até fonte + contexto + aprovação humana serem registrados.")

        source_name = st.text_input("Fonte bíblica/consulta aprovada", value=(state.get("bible_reference_validation") or {}).get("source_name", ""), placeholder="Ex.: edição bíblica/portal/licença usada para conferir a referência")
        source_ref = st.text_input("Referência da fonte (URL, ISBN ou identificação)", value=(state.get("bible_reference_validation") or {}).get("source_reference", ""))
        context_note = st.text_area("Nota de contexto", value=(state.get("bible_reference_validation") or {}).get("context_note", ""), placeholder="Explique brevemente por que o contexto do versículo sustenta a aplicação na história. Não copie o texto bíblico.")
        context_verified = st.checkbox("Conferi o contexto da passagem na fonte indicada", value=bool((state.get("bible_reference_validation") or {}).get("context_verified")))
        human_approved = st.checkbox("Aprovo esta referência para esta história", value=bool((state.get("bible_reference_validation") or {}).get("human_approved")))
        approved_by = st.text_input("Aprovado por", value=(state.get("bible_reference_validation") or {}).get("approved_by", ""))
        if st.button("📖 Validar referência/contexto", use_container_width=True):
            candidate = create_reference_candidate(ref, reason=existing.get("reason", ""), suggested_by=existing.get("suggested_by", "manual"))
            validated = validate_reference_candidate(
                candidate, source_name=source_name, source_reference=source_ref,
                context_note=context_note, context_verified=context_verified,
                human_approved=human_approved, approved_by=approved_by,
            )
            state["versiculo_referencia"] = ref
            state["bible_reference_candidate"] = candidate
            state["bible_reference_validation"] = validated
            persist("Registro de referência bíblica atualizado. Nenhum texto bíblico foi traduzido pela IA.")
            if validated["status"] == "validated":
                st.success("✅ Referência/contexto validados.")
            else:
                st.warning("Ainda faltam itens para validação completa.")
                st.json([x for x in validated["checks"] if not x["ok"]])

with t4:
    if state is None:
        st.info("Abra um Story Book para anexar pesquisa de mercado.")
    else:
        evidence = list(state.get("market_evidence") or [])
        mode = classify_market_mode(evidence)
        st.write("**Modo atual:**", mode["label"])
        if evidence:
            for i, ev in enumerate(evidence):
                v = validate_market_evidence(ev)
                with st.expander(f"{'🟢' if v['ok'] else '🟠'} {ev.get('source_name','Fonte')} · {ev.get('market','')}"):
                    st.write(ev.get("observation", ""))
                    st.caption(f"{ev.get('source_type')} · observado em {ev.get('observed_at','')}")
                    if ev.get("metric_name"):
                        st.write(f"{ev.get('metric_name')}: {ev.get('metric_value')}")
                    if not v["ok"]:
                        st.warning("; ".join(v["issues"]))

        st.markdown("#### ➕ Adicionar evidência observada")
        source_type = st.selectbox("Tipo de fonte", sorted(OBSERVED_SOURCE_TYPES))
        source_name = st.text_input("Nome da fonte", key="market_source_name")
        source_url = st.text_input("URL/referência da fonte", key="market_source_url")
        market = st.text_input("Mercado", value="Amazon.com / en-US", key="market_market")
        observation = st.text_area("Observação factual", key="market_observation", placeholder="Ex.: títulos concorrentes observados usam X; faixa de preço observada... Não escreva suposição como fato.")
        observed_at = st.text_input("Data/hora da observação", placeholder="2026-09-03", key="market_observed_at")
        c1, c2 = st.columns(2)
        metric_name = c1.text_input("Métrica (opcional)", key="market_metric_name")
        metric_value = c2.text_input("Valor observado (opcional)", key="market_metric_value")
        verified = st.checkbox("Conferi manualmente esta evidência", key="market_verified")
        if st.button("➕ Adicionar evidência", use_container_width=True):
            item = make_market_evidence(
                source_type=source_type, source_name=source_name, source_url=source_url,
                market=market, observation=observation, observed_at=observed_at,
                metric_name=metric_name, metric_value=metric_value or None,
                verified_by_human=verified,
            )
            v = validate_market_evidence(item)
            if not v["ok"]:
                st.error("Evidência incompleta: " + "; ".join(v["issues"]))
            else:
                evidence.append(item)
                state["market_evidence"] = evidence
                state["market_intelligence_brief"] = build_market_brief(state, evidence=evidence)
                persist("Evidência de mercado salva com proveniência.")
                st.rerun()

        if evidence and st.button("🧾 Atualizar Market Intelligence Brief", use_container_width=True):
            state["market_intelligence_brief"] = build_market_brief(state, evidence=evidence)
            persist("Market Intelligence Brief atualizado.")
            st.json(state["market_intelligence_brief"])

st.divider()
st.caption("FaithBloom 2.0 · Refinamento 21 · Skill contracts não substituem revisão humana especializada; Bestseller Readiness não é previsão de vendas.")

"""FaithBloom Refinamento 11 — Publishing & Distribution Center."""
from __future__ import annotations
import json
from pathlib import Path
import streamlit as st

from armazenamento import listar_livros, carregar_livro, salvar_livro
from estilo import aplicar_estilo, hero, section_title, callout
from platform_registry import list_platforms
from quality_guardian import list_guardian_reports, load_guardian_report
from publishing_distribution import (
    create_distribution_plan, save_distribution_plan, list_distribution_plans,
    load_distribution_plan, update_submission, launch_readiness, build_channel_package,
)

st.set_page_config(page_title="Publishing & Distribution Center", page_icon="🌐", layout="wide")
aplicar_estilo()
hero(
    "🌐 Publishing & Distribution Center",
    "Do Book Master aprovado ao pacote de cada canal. Organize edições, idiomas, formatos, plataformas, readiness e status de distribuição sem confundir arquivo pronto com publicação confirmada.",
    "Refinamento 11 · Release orchestration",
)

section_title("1. Obra aprovada", "A distribuição nasce de um projeto salvo e de um Quality Guardian vigente para a mesma versão.", "Gate")
livros = listar_livros()
if not livros:
    st.info("Salve primeiro um projeto na Biblioteca Editorial/Story Studio.")
    st.stop()
options = {f"{x.get('titulo','(sem título)')} · {x.get('colecao','')}": x for x in livros}
selected = st.selectbox("Book Master", list(options))
info = options[selected]
state = carregar_livro(info.get("colecao", ""), info["arquivo"])

reports = list_guardian_reports()
matching = []
for card in reports:
    r = load_guardian_report(card["id"])
    if r.get("project_title") == (state.get("titulo") or "Projeto sem título"):
        matching.append(r)
report = None
if matching:
    rlabels = {f"Run {r.get('run_number')} · {r.get('updated_at','')} · {(r.get('certificate') or {}).get('status','sem certificado')}": r for r in matching}
    report = rlabels[st.selectbox("Quality Guardian", list(rlabels))]
else:
    st.warning("Não encontrei relatório do Quality Guardian para este título. O Center poderá montar o plano, mas bloqueará a liberação.")

section_title("2. Edições e destinos", "Escolha onde esta versão será preparada. Plataformas personalizadas do Registry aparecem automaticamente aqui.", "Matrix")
platforms = list_platforms()
name_map = {p["name"]: p for p in platforms}
chosen_names = st.multiselect("Plataformas", list(name_map), default=[x for x in ["Amazon KDP"] if x in name_map])
targets = []
for name in chosen_names:
    p = name_map[name]
    c1,c2 = st.columns([2,1])
    with c1:
        product = st.selectbox(f"Produto · {name}", p.get("products") or ["ebook"], key=f"distprod_{p['id']}")
    with c2:
        locale = st.text_input(f"Locale · {name}", value=state.get("idioma_original", "pt-BR"), key=f"distloc_{p['id']}")
    targets.append({"platform_id": p["id"], "product": product, "locale": locale})

if st.button("🧭 Criar / recalcular plano de distribuição", type="primary", disabled=not targets):
    plan = create_distribution_plan(state, targets, report)
    st.session_state.r11_plan = save_distribution_plan(plan)

plan = st.session_state.get("r11_plan")
if plan:
    s = plan.get("summary", {})
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Edições", s.get("total",0)); m2.metric("Prontas", s.get("ready",0)); m3.metric("Bloqueadas", s.get("blocked",0)); m4.metric("Live", s.get("live",0))
    gate = plan.get("quality_gate", {})
    if gate.get("passed"):
        st.success(f"🛡️ Quality Gate vigente · {gate.get('certificate_id','')}")
    else:
        st.error(f"🛡️ Gate bloqueado: {gate.get('message','')}")

    for row in plan.get("editions", []):
        icon = "🟢" if row.get("readiness") == "ready" else "🔴"
        with st.expander(f"{icon} {row.get('platform_name')} · {row.get('product')} · {row.get('locale')} · {row.get('readiness')}", expanded=row.get("readiness") != "ready"):
            spec=row.get("specification",{})
            st.caption(f"Spec {spec.get('spec_version') or '—'} · verificada {spec.get('last_verified') or '—'} · estado {((spec.get('verification') or {}).get('state') or '—')}")
            for b in row.get("blockers", []):
                st.error(f"{b.get('code')}: {b.get('message')}")
            meta=row.get("metadata",{})
            if meta.get("missing_recommended"):
                st.warning("Metadados recomendados pendentes: " + ", ".join(meta["missing_recommended"]))
            st.json(row.get("preflight",{}), expanded=False)
            if row.get("readiness") == "ready":
                try:
                    package = build_channel_package(state, plan, row["edition_id"])
                    data = Path(package["zip"]).read_bytes()
                    st.download_button("📦 Baixar pacote deste canal", data=data, file_name=Path(package["zip"]).name, mime="application/zip", key=f"pkg_{row['edition_id']}")
                except Exception as exc:
                    st.warning(f"Pacote ainda não pôde ser montado: {exc}")

            st.markdown("**Acompanhamento externo**")
            current=(row.get("submission") or {}).get("status","draft")
            statuses=["draft","ready","submitted","processing","live","rejected","paused","withdrawn"]
            new_status=st.selectbox("Status",statuses,index=statuses.index(current) if current in statuses else 0,key=f"status_{row['edition_id']}")
            ext=st.text_input("ID externo / ISBN da listagem / identificador", value=(row.get("submission") or {}).get("external_id", ""), key=f"ext_{row['edition_id']}")
            url=st.text_input("URL pública da loja (somente após existir)", value=(row.get("submission") or {}).get("store_url", ""), key=f"url_{row['edition_id']}")
            notes=st.text_area("Notas", value=(row.get("submission") or {}).get("notes", ""), key=f"notes_{row['edition_id']}")
            if st.button("💾 Salvar status", key=f"save_{row['edition_id']}"):
                try:
                    plan=update_submission(plan,row["edition_id"],new_status,external_id=ext,store_url=url,notes=notes)
                    st.session_state.r11_plan=save_distribution_plan(plan)
                    st.success("Status atualizado. O FaithBloom não infere publicação; este registro veio da sua confirmação.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    section_title("3. Readiness geral", "Pronto internamente não significa aceito/publicado pela loja. O validador oficial de cada canal continua sendo necessário.", "Release")
    readiness=launch_readiness(plan)
    st.json(readiness, expanded=False)
    st.download_button("⬇️ Baixar manifesto de distribuição", data=json.dumps(plan,ensure_ascii=False,indent=2), file_name="faithbloom-distribution-plan.json", mime="application/json")
    if st.button("💾 Vincular plano ao Book Master"):
        state["distribution_plan_id"] = plan["id"]
        state["distribution_summary"] = plan.get("summary", {})
        salvar_livro(state)
        st.success("Plano vinculado ao projeto em uma nova revisão.")

section_title("4. Planos recentes", "Reabra a operação de distribuição sem perder o acompanhamento por canal.", "History")
recent=list_distribution_plans()[:12]
if not recent:
    st.caption("Nenhum plano salvo ainda.")
else:
    for x in recent:
        if st.button(f"Abrir · {x.get('title','')} · {x.get('updated_at','')}", key=f"open_{x['id']}"):
            st.session_state.r11_plan=load_distribution_plan(x["id"])
            st.rerun()

callout(
    "O FaithBloom não publica sozinho nesta versão",
    "O Refinamento 11 prepara e acompanha a distribuição. Envio automático por API só deve ser adicionado futuramente para plataformas que ofereçam integração oficial compatível e com autorização explícita da pessoa responsável.",
    "🔐",
)

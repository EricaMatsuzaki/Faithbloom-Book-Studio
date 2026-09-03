import json
import os
import streamlit as st

from estilo import aplicar_estilo, hero, section_title, callout
from production_deployment import (
    deployment_config_snapshot,
    deployment_readiness,
    evaluate_real_e2e,
    local_storage_inventory,
    production_health,
    real_e2e_checklist,
    streamlit_oidc_identity,
)

st.set_page_config(page_title="Production Deployment & Real E2E", page_icon="☁️", layout="wide")
aplicar_estilo()
hero("Production Deployment & Real E2E", "Prepare e valide a implantação real sem confundir QA offline com evidência do ambiente de produção.", "Refinamento 14")

identity = streamlit_oidc_identity(st)
section_title("Identidade real", "Usa Streamlit OIDC quando disponível; roles internos continuam sendo autorização, não autenticação.", "Security")
if identity["authenticated"]:
    st.success(f"✅ Login OIDC detectado: {identity.get('name') or identity.get('email') or 'usuário autenticado'}")
else:
    st.warning("⚠️ Nenhuma sessão OIDC autenticada detectada nesta execução.")
st.json({k: v for k, v in identity.items() if k != "subject"})

section_title("Configuração de produção", "Secrets são mostrados apenas como presente/ausente; seus valores nunca são exibidos.", "Environment")
snap = deployment_config_snapshot()
st.json(snap)

if st.button("Rodar health check seguro", use_container_width=True):
    st.session_state["prod_health"] = production_health(include_storage_probe=False)
if st.button("Rodar probe real de storage (write/read/delete)", use_container_width=True):
    st.session_state["prod_health"] = production_health(include_storage_probe=True)
if st.session_state.get("prod_health"):
    h = st.session_state["prod_health"]
    (st.success if h["status"] == "healthy" else st.error)(f"Health: {h['status']}")
    st.json(h)

section_title("Inventário local antes de migrar", "Nenhum arquivo é apagado. Use este inventário para conferir quantidade, bytes e hashes antes de enviar ao storage externo.", "Migration")
if st.button("Inventariar .faithbloom_data", use_container_width=True):
    st.session_state["local_inventory"] = local_storage_inventory()
inv = st.session_state.get("local_inventory")
if inv:
    st.metric("Arquivos", inv["count"])
    st.metric("Bytes", inv["bytes"])
    st.dataframe(inv["items"][:500], use_container_width=True, hide_index=True)
    st.download_button("Baixar inventário JSON", json.dumps(inv, ensure_ascii=False, indent=2), "faithbloom-local-inventory.json", "application/json")

section_title("Real E2E no Streamlit Cloud", "Marque somente depois de executar cada prova de verdade no ambiente de destino.", "Cloud validation")
evidence = st.session_state.setdefault("real_e2e_evidence", {})
for spec in real_e2e_checklist():
    evidence[spec["id"]] = st.checkbox(("Obrigatório · " if spec["required"] else "Opcional · ") + spec["label"], value=bool(evidence.get(spec["id"])), key=f"e2e_{spec['id']}")
result = evaluate_real_e2e(evidence)
if result["cloud_e2e_passed"]:
    st.success("✅ Real E2E obrigatório marcado como concluído — registre as evidências antes de promover para Stable.")
else:
    st.warning(f"{result['required_done']}/{result['required_total']} provas obrigatórias concluídas.")
st.json(result)

section_title("Readiness", "Este gate apenas diz se o ambiente está pronto para começar a validação em nuvem.", "Gate")
ready = deployment_readiness()
(st.success if ready["ready_for_cloud_validation"] else st.error)("✅ Pronto para validação cloud" if ready["ready_for_cloud_validation"] else "🔴 Ainda existem bloqueios de configuração")
st.json(ready)

callout("Regra de release", "O FaithBloom só deve receber a tag Stable depois de: configuração de produção + storage persistente + autenticação real + Real E2E com evidências. QA offline sozinho não basta.", "🔒")

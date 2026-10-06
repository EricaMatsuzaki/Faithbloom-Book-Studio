import json
from pathlib import Path
import streamlit as st

from estilo import aplicar_estilo, hero
from book_doctor import listar_projetos
from editorial_visual_handoff import preparar_handoff_visual

st.set_page_config(page_title="Handoff Visual Remaster", page_icon="🎨", layout="wide")
aplicar_estilo()
hero(
    "🎨 Handoff Visual — Remaster",
    "Leve o texto revisado, a página de origem e a direção emocional para o visual remaster sem perder o original.",
)
st.info("🔒 Esta etapa não gera imagens. Ela prepara o plano visual para usar Character Masters oficiais e versões derivadas aprováveis.")


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
    if project.get("tipo_projeto") != "story":
        continue
    for state in _states(project):
        choices.append((project, state))

if not choices:
    st.warning("Nenhum remaster editorial encontrado.")
    st.page_link("pages/45_✨_Editorial_Remaster.py", label="✨ Abrir Full Editorial Remaster →", use_container_width=True)
    st.stop()

labels = [
    f"{s.get('titulo','Sem título')} · {s.get('remaster_id','—')} · {s.get('status','')}"
    for _, s in choices
]
idx = st.selectbox("Remaster", range(len(choices)), format_func=lambda i: labels[i])
project, state = choices[idx]

ready = bool(
    state.get("revisao_aprovada")
    and (state.get("prompt_master_compliance_remaster") or {}).get("ok_para_finalizar")
    and state.get("metadata_emocional_confirmada")
)
if not ready:
    st.warning("Este remaster ainda não concluiu texto + Prompt-Mestre + confirmação do mapa emocional.")
    if not state.get("metadata_emocional_confirmada"):
        st.page_link("pages/49_🎭_Mapa_Emocional_Remaster.py", label="🎭 Confirmar Mapa Emocional →", use_container_width=True)
    st.page_link("pages/46_📝_Mesa_de_Revisao_Remaster.py", label="📝 Voltar à Mesa de Revisão →", use_container_width=True)
    st.stop()

st.success("Texto e mapa emocional aprovados. O handoff visual pode ser preparado.")
if st.button("🎨 Preparar handoff visual", type="primary"):
    try:
        out = preparar_handoff_visual(state, project)
        st.session_state[f"visual_handoff_{state.get('remaster_id')}"] = out
        st.success("Handoff visual salvo no Restoration Plan sem apagar decisões ou versões anteriores.")
    except Exception as exc:
        st.error(f"Não foi possível preparar o handoff: {exc}")

out = st.session_state.get(f"visual_handoff_{state.get('remaster_id')}")
if out:
    handoff = out.get("handoff") or {}
    st.markdown("### Cenas prontas para restauração")
    rows = []
    for cena in handoff.get("cenas") or []:
        rows.append({
            "Cena": cena.get("numero"),
            "Página original": cena.get("pagina_origem"),
            "Texto revisado": cena.get("texto_revisado"),
            "Emoção": cena.get("emocao"),
            "Intensidade": cena.get("intensidade_emocional"),
            "Personagem principal": cena.get("personagem_principal"),
            "Expressão": cena.get("expressao"),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("### Próxima etapa")
    st.write(
        "Abra o Visual Remaster Workbench. Ele usa automaticamente o texto revisado, a direção emocional e o Character Master oficial escolhido para cada intervenção; toda candidata continua exigindo aprovação humana."
    )
    st.page_link("pages/51_🖼️_Visual_Remaster_Workbench.py", label="🖼️ Abrir Visual Remaster Workbench →", use_container_width=True)
    st.caption(f"Handoff fingerprint: {handoff.get('fingerprint','')[:16]}… · original preservado por SHA-256.")

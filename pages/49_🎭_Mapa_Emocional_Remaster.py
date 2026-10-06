import json
from pathlib import Path
import streamlit as st

from estilo import aplicar_estilo, hero
from book_doctor import listar_projetos
from editorial_remaster_emotional import (
    opcoes_emocao,
    metadata_emocional_completa,
    atualizar_metadata_emocional_cena,
)

st.set_page_config(page_title="Mapa Emocional Remaster", page_icon="🎭", layout="wide")
aplicar_estilo()
hero(
    "🎭 Mapa Emocional — Remaster",
    "Confirme emoção, intensidade e transição cena por cena antes da psicologia das cores seguir para as novas ilustrações.",
)
st.info("🎨 A emoção orienta luz, fundo, atmosfera e cores de apoio. O Character DNA continua protegido e não é recolorido.")


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
            if state.get("dossie_editorial_aprovado_para_edicao"):
                choices.append((project, state))

if not choices:
    st.warning("Nenhum remaster editorial disponível para revisar o mapa emocional.")
    st.page_link("pages/46_📝_Mesa_de_Revisao_Remaster.py", label="📝 Abrir Mesa de Revisão →", use_container_width=True)
    st.stop()

labels = [f"{s.get('titulo','Sem título')} · {s.get('remaster_id','—')}" for _, s in choices]
idx = st.selectbox("Remaster", range(len(choices)), format_func=lambda i: labels[i])
project, loaded = choices[idx]
key = f"emotional_state_{loaded.get('remaster_id')}"
state = st.session_state.get(key) or loaded
st.session_state[key] = state

status = metadata_emocional_completa(state)
a, b = st.columns(2)
a.metric("Cenas", len(state.get("cenas_texto") or []))
b.metric("Pendentes", len(status.get("cenas_pendentes") or []))

scenes = state.get("cenas_texto") or []
scene_numbers = [int(x.get("numero") or i + 1) for i, x in enumerate(scenes)]
selected = st.selectbox("Cena", scene_numbers)
scene = next(x for x in scenes if int(x.get("numero") or 0) == int(selected))
st.text_area("Texto da cena", value=scene.get("texto", ""), height=150, disabled=True)

opts = opcoes_emocao()
current = str(scene.get("emocao") or "")
current_index = opts.index(current) if current in opts else 0
emotion = st.selectbox("Emoção principal", opts, index=current_index)
secondary_opts = [""] + opts
secondary_current = str(scene.get("emocao_secundaria") or "")
secondary_index = secondary_opts.index(secondary_current) if secondary_current in secondary_opts else 0
secondary = st.selectbox("Subemoção — opcional", secondary_opts, index=secondary_index)
intensity = st.slider("Intensidade emocional", 1, 5, int(scene.get("intensidade_emocional") or 3))
transition = st.text_input("Transição emocional — opcional", value=str(scene.get("transicao_emocional") or ""), placeholder="ex.: impaciência → esperança")
expression = st.text_input("Expressão visual — opcional", value=str(scene.get("expressao") or ""))

if st.button("✅ Confirmar emoção desta cena", type="primary"):
    try:
        state = atualizar_metadata_emocional_cena(
            state,
            selected,
            emocao=emotion,
            intensidade=intensity,
            emocao_secundaria=secondary,
            transicao_emocional=transition,
            expressao=expression,
        )
        st.session_state[key] = state
        st.success("Metadados emocionais salvos na versão Remastered.")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

status = metadata_emocional_completa(state)
if status["ok"]:
    st.success("✅ Todas as cenas possuem emoção e intensidade confirmadas. O mapa canônico de psicologia das cores foi reconstruído.")
    st.page_link("pages/46_📝_Mesa_de_Revisao_Remaster.py", label="📝 Voltar e rodar a revisão final →", use_container_width=True)
else:
    st.warning("Cenas ainda pendentes: " + ", ".join(str(x) for x in status["cenas_pendentes"]))

with st.expander("🎨 Direção cromática já confirmada", expanded=False):
    for row in state.get("mapa_emocional") or []:
        st.write(row)

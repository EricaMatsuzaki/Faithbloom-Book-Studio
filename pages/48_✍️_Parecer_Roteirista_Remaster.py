import json
from pathlib import Path
import streamlit as st

from estilo import aplicar_estilo, hero
from book_doctor import listar_projetos
from editorial_remaster_storyteller import gerar_parecer_estrutural_roteirista

st.set_page_config(page_title="Parecer do Roteirista", page_icon="✍️", layout="wide")
aplicar_estilo()
hero(
    "✍️ Parecer Estrutural do Roteirista",
    "Use o Roteirista somente quando o Revisor ainda encontrar problemas estruturais depois das correções pontuais.",
)
st.info("O Roteirista não reescreve o livro nesta tela. Ele emite um parecer estrutural para preservar a alma da obra antes de qualquer nova edição.")


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
            if state.get("necessita_intervencao_estrutural_roteirista"):
                choices.append((project, state))

if not choices:
    st.success("Nenhum remaster está aguardando intervenção estrutural do Roteirista.")
    st.page_link("pages/46_📝_Mesa_de_Revisao_Remaster.py", label="📝 Voltar à Mesa de Revisão →", use_container_width=True)
    st.stop()

labels = [f"{s.get('titulo','Sem título')} · {s.get('remaster_id','—')}" for _, s in choices]
idx = st.selectbox("Remaster", range(len(choices)), format_func=lambda i: labels[i])
project, state = choices[idx]

st.markdown("### Obra atual")
st.write(f"**Título:** {state.get('titulo','')}")
st.write(f"**Lição:** {state.get('licao_final','')}")
st.write(f"**Versículo:** {state.get('versiculo_referencia','')}")
st.write(f"**Emoção central:** {state.get('emocao_central','')}")

with st.expander("Ver cenas atuais", expanded=False):
    for cena in state.get("cenas_texto") or []:
        st.markdown(f"**Cena {cena.get('numero')}**")
        st.write(cena.get("texto", ""))

confirm = st.checkbox(
    "Autorizo o Roteirista a analisar a estrutura desta versão Remastered e emitir recomendações, sem aplicar alterações automaticamente."
)
if st.button("✍️ Gerar parecer estrutural", type="primary", disabled=not confirm):
    try:
        from openrouter_client import chamar_llm
        with st.spinner("Roteirista analisando estrutura, Heart Arc e experiência emocional…"):
            review = gerar_parecer_estrutural_roteirista(state, chamar_llm, autorizado=True)
        st.session_state[f"storyteller_review_{state.get('remaster_id')}"] = review
    except Exception as exc:
        st.error(f"Não foi possível gerar o parecer: {exc}")

review = st.session_state.get(f"storyteller_review_{state.get('remaster_id')}")
if review:
    parecer = review.get("parecer") or {}
    st.markdown("### Parecer")
    st.write(parecer.get("diagnostico_geral", ""))
    if parecer.get("heart_arc"):
        st.markdown("#### Heart Arc")
        st.write(parecer.get("heart_arc"))
    if parecer.get("risco_de_perder_alma"):
        st.markdown("#### Risco de perder a alma da obra")
        st.write(parecer.get("risco_de_perder_alma"))

    for key, title in [
        ("manter", "✅ Manter"),
        ("ajustes_pontuais", "📝 Ajustes pontuais"),
        ("ajustes_estruturais", "🧭 Ajustes estruturais"),
        ("cenas_prioritarias", "⭐ Cenas prioritárias"),
        ("ordem_recomendada", "➡️ Ordem recomendada"),
    ]:
        value = parecer.get(key)
        if value:
            st.markdown(f"#### {title}")
            st.write(value)

    st.success("Parecer concluído sem alterar nenhuma cena. Use as recomendações na Mesa de Revisão e aprove cada proposta do Editor individualmente.")
    st.page_link("pages/46_📝_Mesa_de_Revisao_Remaster.py", label="📝 Voltar à Mesa de Revisão →", use_container_width=True)

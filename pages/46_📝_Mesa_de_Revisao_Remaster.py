import json
from pathlib import Path
import streamlit as st

from estilo import aplicar_estilo, hero
from book_doctor import listar_projetos
from editorial_remaster_revision import (
    carregar_dossie,
    aprovar_dossie_para_edicao,
    gerar_proposta_edicao_cena,
    aplicar_proposta_edicao,
    rodar_revisao_final_textual,
)

st.set_page_config(page_title="Mesa de Revisão Remaster", page_icon="📝", layout="wide")
aplicar_estilo()
hero(
    "📝 Mesa de Revisão — Full Editorial Remaster",
    "Compare original × proposta, aprove cena por cena e só então libere a obra para a remasterização visual.",
)
st.info("🔒 Nenhuma proposta altera o PDF original. Alterações entram somente na versão Remastered e exigem aprovação explícita.")


def _states_for_project(project: dict) -> list[dict]:
    root = Path(project.get("pasta", "")) / "remastered" / "editorial"
    if not root.exists():
        return []
    found = []
    for path in root.glob("*/editorial_remaster.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        data["arquivo_estado"] = str(path)
        found.append(data)
    return sorted(found, key=lambda x: str(x.get("criado_em") or ""), reverse=True)


projects = [p for p in listar_projetos() if p.get("tipo_projeto") == "story"]
choices = []
for project in projects:
    for state in _states_for_project(project):
        choices.append((project, state))

if not choices:
    st.warning("Ainda não existe um remaster editorial preparado. Comece em ✨ Full Editorial Remaster.")
    st.page_link("pages/45_✨_Editorial_Remaster.py", label="✨ Abrir Full Editorial Remaster →", use_container_width=True)
    st.stop()

labels = [
    f"{state.get('titulo','Sem título')} · remaster {state.get('remaster_id','—')} · {state.get('status','')}"
    for _, state in choices
]
idx = st.selectbox("Remaster para revisar", range(len(choices)), format_func=lambda i: labels[i])
project, loaded = choices[idx]
key = f"revision_state_{loaded.get('remaster_id')}"
state = st.session_state.get(key) or loaded
st.session_state[key] = state

dossier = carregar_dossie(state)
st.markdown("### 1 · Dossiê Editorial")
if not dossier:
    st.warning("Este remaster ainda não possui Dossiê Editorial. Gere o diagnóstico primeiro.")
    st.page_link("pages/45_✨_Editorial_Remaster.py", label="✨ Voltar ao Full Editorial Remaster →", use_container_width=True)
    st.stop()

status = dossier.get("revisor", {}).get("status", "—")
a, b, c = st.columns(3)
a.metric("Revisor", status)
b.metric("Bloqueios Prompt-Mestre", len((dossier.get("prompt_mestre") or {}).get("bloqueios") or []))
c.metric("Recomendações", len((dossier.get("prompt_mestre") or {}).get("recomendacoes") or []))

for note in dossier.get("revisor", {}).get("notas") or []:
    st.write("• " + (note.get("mensagem") or note.get("problema") or str(note) if isinstance(note, dict) else str(note)))

approved = bool(state.get("dossie_editorial_aprovado_para_edicao"))
if approved:
    st.success("Dossiê já aprovado para edição controlada.")
else:
    confirm = st.checkbox("Li o diagnóstico e autorizo gerar propostas de edição para a versão Remastered.")
    if st.button("✅ Aprovar Dossiê para edição", disabled=not confirm):
        try:
            state = aprovar_dossie_para_edicao(state, dossier, aprovado=True)
            st.session_state[key] = state
            st.success("Dossiê aprovado. O Editor de História pode gerar propostas, mas nada será aplicado sem nova aprovação.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

if state.get("dossie_editorial_aprovado_para_edicao"):
    st.markdown("### 2 · Editor de História — proposta cena por cena")
    scenes = state.get("cenas_texto") or []
    scene_numbers = [int(x.get("numero") or i + 1) for i, x in enumerate(scenes)]
    selected = st.selectbox("Cena", scene_numbers)
    scene = next(x for x in scenes if int(x.get("numero") or 0) == int(selected))
    st.text_area("Texto atual", value=scene.get("texto", ""), height=180, disabled=True)
    instruction = st.text_area(
        "O que deseja melhorar nesta cena?",
        value="Melhore somente o necessário conforme o Dossiê Editorial, preservando a alma da obra, a ação, a moral, o versículo, os personagens e a faixa etária.",
        height=120,
    )

    if st.button("✍️ Gerar proposta do Editor para esta cena"):
        try:
            from openrouter_client import chamar_llm
            with st.spinner("Editor de História preparando uma proposta…"):
                proposal = gerar_proposta_edicao_cena(state, selected, instruction, chamar_llm)
            st.session_state[f"proposal_{state.get('remaster_id')}_{selected}"] = proposal
        except Exception as exc:
            st.error(f"Não foi possível gerar a proposta: {exc}")

    proposal = st.session_state.get(f"proposal_{state.get('remaster_id')}_{selected}")
    if proposal:
        st.markdown("#### Comparação antes × depois")
        left, right = st.columns(2)
        left.text_area("ANTES", value=(proposal.get("antes") or {}).get("texto", ""), height=220, disabled=True)
        right.text_area("DEPOIS — proposta", value=(proposal.get("depois") or {}).get("texto", ""), height=220, disabled=True)
        c1, c2 = st.columns(2)
        if c1.button("✅ Aprovar e aplicar na Remastered", use_container_width=True):
            try:
                state = aplicar_proposta_edicao(state, proposal, aprovado=True)
                st.session_state[key] = state
                st.session_state.pop(f"proposal_{state.get('remaster_id')}_{selected}", None)
                st.success("Proposta aplicada apenas na versão Remastered. Original preservado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if c2.button("❌ Rejeitar proposta", use_container_width=True):
            try:
                state = aplicar_proposta_edicao(state, proposal, aprovado=False)
                st.session_state[key] = state
                st.session_state.pop(f"proposal_{state.get('remaster_id')}_{selected}", None)
                st.info("Proposta rejeitada. Nenhuma cena foi alterada.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    st.markdown("### 3 · Revisor final do texto + motores compartilhados")
    st.caption("Depois das correções que desejar, rode novamente o Revisor. Se aprovado, o FaithBloom gera o mapa emocional/psicologia das cores e confere o Prompt-Mestre.")
    if st.button("🛡️ Rodar revisão final textual"):
        try:
            from openrouter_client import chamar_llm
            with st.spinner("Revisor e motores compartilhados avaliando a nova versão…"):
                result = rodar_revisao_final_textual(state, chamar_llm)
            state = result["estado"]
            st.session_state[key] = state
            st.session_state[f"final_review_{state.get('remaster_id')}"] = result
        except Exception as exc:
            st.error(f"Revisão final não concluída: {exc}")

    result = st.session_state.get(f"final_review_{state.get('remaster_id')}")
    if result:
        if result.get("pronto_para_visual"):
            st.success("✅ Texto aprovado e Prompt-Mestre liberado. A obra está pronta para seguir ao Restoration Studio com os Masters oficiais.")
            st.page_link("pages/19_✨_Restoration_Studio.py", label="✨ Abrir Restoration Studio →", use_container_width=True)
        else:
            st.warning("A obra ainda precisa de revisão textual ou de resolver um bloqueio do Prompt-Mestre.")
            if result.get("necessita_roteirista"):
                st.info("O Revisor ainda encontrou problemas após as edições pontuais. Neste ponto o Roteirista deve entrar somente com autorização específica para intervenção estrutural.")
            for note in result.get("notas") or []:
                st.write("• " + (note.get("mensagem") or note.get("problema") or str(note) if isinstance(note, dict) else str(note)))
            for block in (result.get("prompt_mestre") or {}).get("bloqueios") or []:
                st.error(block.get("mensagem") or str(block))

    st.markdown("### Histórico")
    history = state.get("historico_revisao_textual") or []
    if not history:
        st.caption("Nenhuma proposta aplicada/rejeitada ainda.")
    else:
        st.dataframe([
            {
                "Cena": x.get("numero_cena"),
                "Decisão": "APROVADA" if x.get("aprovado") else "REJEITADA",
                "Quando": x.get("decidido_em"),
                "Pedido": x.get("instrucao"),
            }
            for x in history
        ], use_container_width=True, hide_index=True)

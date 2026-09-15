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
from editorial_remaster_storyteller import (
    gerar_proposta_enriquecimento_roteirista,
    aplicar_proposta_enriquecimento_roteirista,
)

st.set_page_config(page_title="Mesa de Revisão Remaster", page_icon="📝", layout="wide")
aplicar_estilo()
hero(
    "📝 Mesa de Revisão — Full Editorial Remaster",
    "Revise a obra inteira com Editor, Storyteller, Heart Arc, experiência, moral, Bíblia, emoções e cores antes do handoff visual.",
)
st.info(
    "🔒 O PDF original permanece imutável. O fluxo trabalha somente em versões derivadas e exige sua aprovação nos pontos editoriais decisivos."
)


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
            st.success("Dossiê aprovado. O Editor e o Storyteller podem trabalhar na versão derivada; o original continua protegido.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

if state.get("dossie_editorial_aprovado_para_edicao"):
    st.markdown("### 2 · Editor de História — ajustes pontuais opcionais")
    st.caption("Use esta etapa quando quiser corrigir uma cena específica antes da revisão estrutural completa. O Storyteller avaliará o livro inteiro na etapa seguinte.")
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
                st.session_state.pop(f"storyteller_enrichment_{state.get('remaster_id')}", None)
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

    st.markdown("### 3 · Storyteller + Heart Arc — revisão completa da experiência")
    st.caption(
        "Etapa obrigatória do Full Editorial Review. O Storyteller avalia a obra inteira e pode enriquecer cenas ou acrescentar novas experiências quando houver ganho real — sempre preservando essência, personagens, lição de moral, mensagem bíblica e faixa etária."
    )
    storyteller_key = f"storyteller_enrichment_{state.get('remaster_id')}"
    if st.button("✨ Analisar e enriquecer a obra completa", type="primary"):
        try:
            from openrouter_client import chamar_llm
            with st.spinner("Storyteller avaliando Heart Arc, experiência, emoção, descoberta, transformação, moral e fé…"):
                enriched = gerar_proposta_enriquecimento_roteirista(state, chamar_llm)
            st.session_state[storyteller_key] = enriched
        except Exception as exc:
            st.error(f"Storyteller não concluiu a análise: {exc}")

    enriched = st.session_state.get(storyteller_key)
    if enriched:
        analysis = enriched.get("analise") or {}
        gain = bool(enriched.get("ganho_editorial"))
        if gain:
            st.success("O Storyteller encontrou ganho editorial real e criou uma candidata enriquecida.")
        else:
            st.info("O Storyteller analisou a obra e não encontrou ganho suficiente para justificar mudanças estruturais.")
        if analysis.get("diagnostico_geral"):
            st.write("**Diagnóstico:**", analysis.get("diagnostico_geral"))
        col1, col2, col3 = st.columns(3)
        col1.metric("Cenas atuais", len(enriched.get("antes") or []))
        col2.metric("Cenas propostas", len(enriched.get("depois") or []))
        col3.metric("Novas experiências/cenas", len(analysis.get("novas_cenas_adicionadas") or []))
        with st.expander("💗 Heart Arc, experiência e transformação", expanded=True):
            st.write("**Heart Arc:**", analysis.get("heart_arc") or "—")
            st.write("**Experiência:**", analysis.get("experiencia") or "—")
            st.write("**Descoberta/transformação:**", analysis.get("descoberta_transformacao") or "—")
            st.write("**Lição de moral preservada:**", "Sim" if analysis.get("licao_moral_preservada") else "Não")
            st.write("**Mensagem bíblica preservada:**", "Sim" if analysis.get("mensagem_biblica_preservada") else "Não")
            st.write("**Risco de desvio:**", analysis.get("risco_de_desvio") or "—")
        if gain:
            with st.expander("📖 Ver candidata enriquecida", expanded=False):
                for cena in enriched.get("depois") or []:
                    st.markdown(f"**Cena {cena.get('numero')}**")
                    st.write(cena.get("texto", ""))
        a1, a2 = st.columns(2)
        if a1.button("✅ Aprovar etapa Storyteller", use_container_width=True):
            try:
                state = aplicar_proposta_enriquecimento_roteirista(state, enriched, aprovado=True)
                st.session_state[key] = state
                st.session_state.pop(storyteller_key, None)
                st.session_state.pop(f"final_review_{state.get('remaster_id')}", None)
                st.success("Etapa Storyteller aprovada na versão Remastered. Agora o Revisor final, emoções e cores podem validar o resultado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if a2.button("❌ Rejeitar candidata e manter texto atual", use_container_width=True):
            try:
                state = aplicar_proposta_enriquecimento_roteirista(state, enriched, aprovado=False)
                st.session_state[key] = state
                st.session_state.pop(storyteller_key, None)
                st.info("Candidata rejeitada. O texto derivado anterior foi preservado.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    storyteller_done = state.get("storyteller_enrichment_aprovado") is True
    st.markdown("### 4 · Revisor final + Moral/Bíblia Guard + Emoções + Psicologia das Cores")
    if storyteller_done:
        st.caption(
            "O Storyteller já passou pela obra. Agora o Revisor final valida o texto; o Prompt-Mestre e Bible Guard conferem os requisitos; depois o FaithBloom gera/reutiliza emoções e deriva a Psicologia das Cores automaticamente."
        )
    else:
        st.warning("Conclua e aprove a etapa Storyteller acima antes da revisão final. Assim o livro realmente passa pelo fluxo editorial completo.")

    if st.button("🛡️ Rodar revisão final completa", disabled=not storyteller_done):
        try:
            from openrouter_client import chamar_llm
            with st.spinner("Revisor, Prompt-Mestre, Bible Guard, emoções e Psicologia das Cores avaliando a nova versão…"):
                result = rodar_revisao_final_textual(state, chamar_llm)
            state = result["estado"]
            st.session_state[key] = state
            st.session_state[f"final_review_{state.get('remaster_id')}"] = result
        except Exception as exc:
            st.error(f"Revisão final não concluída: {exc}")

    result = st.session_state.get(f"final_review_{state.get('remaster_id')}")
    if result:
        if result.get("pronto_para_visual"):
            st.success("✅ Revisão editorial completa aprovada: texto, Prompt-Mestre, Bíblia, emoções e cores liberados. A obra está pronta para o handoff visual.")
            st.page_link("pages/47_🎨_Handoff_Visual_Remaster.py", label="🎨 Preparar Handoff Visual →", use_container_width=True)
        else:
            st.warning("A obra ainda precisa resolver uma pendência textual ou um bloqueio do Prompt-Mestre/Bible Guard antes do visual.")
            for note in result.get("notas") or []:
                st.write("• " + (note.get("mensagem") or note.get("problema") or str(note) if isinstance(note, dict) else str(note)))
            for block in (result.get("prompt_mestre") or {}).get("bloqueios") or []:
                st.error(block.get("mensagem") or str(block))

    st.markdown("### Histórico")
    text_history = state.get("historico_revisao_textual") or []
    storyteller_history = state.get("historico_storyteller") or []
    if not text_history and not storyteller_history:
        st.caption("Nenhuma decisão editorial registrada ainda.")
    if text_history:
        st.markdown("#### Editor de História")
        st.dataframe([
            {
                "Cena": x.get("numero_cena"),
                "Decisão": "APROVADA" if x.get("aprovado") else "REJEITADA",
                "Quando": x.get("decidido_em"),
                "Pedido": x.get("instrucao"),
            }
            for x in text_history
        ], use_container_width=True, hide_index=True)
    if storyteller_history:
        st.markdown("#### Storyteller")
        st.dataframe([
            {
                "Decisão": "APROVADA" if x.get("aprovado") else "REJEITADA",
                "Ganho editorial": "Sim" if x.get("ganho_editorial") else "Não",
                "Quando": x.get("decidido_em"),
                "Risco de desvio": (x.get("analise") or {}).get("risco_de_desvio", "—"),
            }
            for x in storyteller_history
        ], use_container_width=True, hide_index=True)

import os
from pathlib import Path

import streamlit as st

from estilo import aplicar_estilo, hero
from book_doctor import listar_projetos, carregar_relatorio
from editorial_autopilot_storage import restore_runtime_tree, sync_runtime_tree
from editorial_remaster_autopilot import (
    STAGES, approve_final_remaster, list_runs, load_run, new_run, run_autopilot,
)
from editorial_remaster_visual_autopilot import (
    approve_run_visual_candidates_and_quality,
    run_visual_autopilot,
)
from ai_provider_router import chamar_llm, provider_status

st.set_page_config(page_title="Autopilot Editorial Remaster", page_icon="✨", layout="wide")
aplicar_estilo()
hero(
    "✨ Autopilot Editorial Remaster",
    "Um clique para a equipe FaithBloom revisar, enriquecer, validar e preparar a obra inteira; você entra novamente apenas para a decisão final.",
    "FaithBloom · Full Editorial Review + Recovery",
)
st.info(
    "🔒 O original nunca é sobrescrito. O Autopilot trabalha somente em versão derivada, infere os dados editoriais que faltarem, "
    "usa os especialistas internos e mantém publicação/Masters sob aprovação final da autora."
)


def _advance(project: dict, run: dict) -> dict:
    """Avança o Autopilot e espelha checkpoints no storage persistente."""
    current = run_autopilot(project, run, chamar_llm)
    if current.get("status") == "needs_author_review":
        current = run_visual_autopilot(project, current)
    sync_runtime_tree(project)
    return current


projects = [p for p in listar_projetos() if p.get("tipo_projeto") == "story"]
if not projects:
    st.warning("Ainda não há Story Book importado pelo Book Doctor.")
    st.page_link("pages/16_🩺_Book_Doctor.py", label="🩺 Importar no Book Doctor →", use_container_width=True)
    st.stop()

preferred_project_id = str(st.session_state.get("autopilot_book_doctor_project_id") or "")
default_idx = next((i for i, p in enumerate(projects) if str(p.get("id") or "") == preferred_project_id), 0)
labels = [f"{p.get('titulo','Sem título')} · {p.get('colecao','')} · {p.get('id')}" for p in projects]
idx = st.selectbox("Livro", range(len(projects)), index=default_idx, format_func=lambda i: labels[i])
project = projects[idx]
restore_info = restore_runtime_tree(project)
report = carregar_relatorio(project)
if restore_info.get("restored"):
    st.caption(f"☁️ {restore_info.get('restored')} checkpoint(s)/arquivo(s) do Autopilot foram restaurados do armazenamento persistente.")

st.markdown("### Como o Autopilot trabalha")
st.caption(
    "Book Doctor → mapeamento da história → Revisor → Storyteller + Heart Arc → revisão final + auto-reparo → Moral/Bíblia → "
    "emoções + Psicologia das Cores → Style DNA + Character Masters → handoff visual → candidatas visuais → QA → pacote final."
)

provider = provider_status()
if provider.get("gemini"):
    st.caption("🧠 Texto do Autopilot: Gemini API direto (principal). Groq/OpenRouter ficam apenas como fallbacks quando configurados.")
elif provider.get("groq"):
    st.warning("Gemini ainda não está configurado; o Autopilot usará Groq como provedor de texto. Adicione GEMINI_API_KEY para usar Gemini como principal.")
else:
    st.warning("Configure GEMINI_API_KEY no Streamlit Secrets para o Autopilot usar a Gemini API diretamente e deixar de depender do saldo da OpenRouter para texto.")

runs = list_runs(project)
active = None
preferred_run_id = str(st.session_state.get("autopilot_run_id") or "")
if preferred_run_id:
    active = load_run(project, preferred_run_id)
if not active and runs:
    run_options = [r.get("run_id") for r in runs]
    chosen_run = st.selectbox(
        "Execução existente — opcional",
        [""] + run_options,
        format_func=lambda rid: "— iniciar nova —" if not rid else f"{rid} · {next((r.get('status') for r in runs if r.get('run_id') == rid), '')}",
    )
    if chosen_run:
        active = load_run(project, chosen_run)

if not active:
    st.markdown("### 1 · Iniciar")
    st.write(
        "Você não precisa preencher ficha. O FaithBloom vai inferir da própria obra a lição de moral, aprendizado cristão, "
        "emoção central e demais metadados necessários, validar tudo com os especialistas e seguir sozinho até o pacote final."
    )
    if os.environ.get("OPENROUTER_API_KEY"):
        st.caption(
            "A OpenRouter fica restrita aos recursos que ainda dependem dela, como a geração visual configurada atualmente. "
            "As tarefas editoriais de texto usam o AI Provider Router e priorizam Gemini."
        )
    else:
        st.caption("A geração visual automática ficará pendente se não houver uma chave/modelo de imagem configurado no servidor.")

    if st.button("✨ Iniciar Revisão Completa Automática", type="primary", use_container_width=True):
        active = new_run(
            project,
            report=report,
            settings={
                "faixa_etaria": "3-8",
                "versiculo_referencia": "",
                "licao_final": "",
                "aprendizado_cristao": "",
                "emocao_central": "",
                "auto_apply_safe_editorial_changes": True,
                "allow_paid_image_generation": bool(os.environ.get("OPENROUTER_API_KEY")),
                "infer_missing_editorial_metadata": True,
                "final_human_approval_required": True,
            },
        )
        sync_runtime_tree(project)
        st.session_state["autopilot_run_id"] = active["run_id"]
        with st.spinner("A equipe FaithBloom está trabalhando. Vou avançar automaticamente até o pacote final ou até um bloqueio que realmente não possa ser resolvido internamente…"):
            active = _advance(project, active)
        st.session_state["autopilot_run_id"] = active["run_id"]
        st.rerun()

if active:
    status = active.get("status", "pending")
    incidents = active.get("incidents") or []

    editorial_incidents = [x for x in incidents if x.get("owner") == "editorial_specialist"]
    auto_resume_key = f"autopilot_editorial_autoresume_{active.get('run_id')}"
    if status == "blocked" and len(editorial_incidents) == 1 and not st.session_state.get(auto_resume_key):
        st.session_state[auto_resume_key] = True
        with st.spinner("O especialista editorial encontrou uma pendência e já está corrigindo automaticamente. Retomando do checkpoint…"):
            active = _advance(project, active)
        st.session_state["autopilot_run_id"] = active["run_id"]
        st.rerun()

    st.markdown("### 2 · Progresso automático")
    status = active.get("status", "pending")
    status_label = {
        "pending": "⏳ Aguardando",
        "running": "⚙️ Processando",
        "blocked": "🛠️ Correção/recuperação necessária",
        "failed": "❌ Falha",
        "needs_author_review": "🌸 Pronto para sua revisão final",
        "completed": "✅ Edição aprovada pela autora",
    }.get(status, status)
    st.subheader(status_label)

    cols = st.columns(5)
    icons = {"completed": "✅", "running": "⚙️", "blocked": "🛠️", "failed": "❌", "needs_author_review": "👀", "pending": "○"}
    for i, stage in enumerate(STAGES):
        cp = (active.get("stages") or {}).get(stage) or {}
        cols[i % 5].markdown(f"**{icons.get(cp.get('status'), '○')} {stage.replace('_', ' ').title()}**")
        if cp.get("attempts"):
            cols[i % 5].caption(f"tentativas: {cp.get('attempts')}")

    if status in {"pending", "blocked", "failed", "running"}:
        label = "▶️ Retomar do último checkpoint" if status in {"blocked", "failed"} else "🚀 Continuar Autopilot"
        if st.button(label, type="primary", use_container_width=True):
            with st.spinner("Retomando exatamente do último checkpoint válido…"):
                active = _advance(project, active)
            st.session_state["autopilot_run_id"] = active["run_id"]
            st.rerun()

    incidents = active.get("incidents") or []
    if incidents:
        with st.expander("🛠️ Auto-Recovery / incidentes", expanded=status in {"blocked", "failed"}):
            for item in incidents[-8:]:
                st.write(
                    f"**{item.get('stage')}** · {item.get('owner')} · {item.get('status')}\n\n"
                    f"{item.get('message')}"
                )
                if item.get("engineering_plan"):
                    st.caption("Plano técnico foi preparado e o checkpoint de retomada foi preservado.")
            st.caption(
                "Pendências editoriais revisáveis são tratadas internamente. Falhas transitórias são repetidas automaticamente. "
                "Defeitos reais de código ficam registrados para Engenharia/Full Stack com o checkpoint preservado."
            )

    if status == "needs_author_review":
        package = active.get("final_review_package") or {}
        st.success("🌸 A revisão automática chegou ao pacote consolidado. Agora é sua decisão final.")
        t1, t2, t3, t4 = st.tabs(["📖 História", "💗 Heart Arc & Emoções", "🎨 Visual", "🛡️ QA & Recovery"])
        with t1:
            st.write("**Lição de moral:**", package.get("licao_de_moral") or "—")
            st.write("**Aprendizado cristão:**", package.get("aprendizado_cristao") or "—")
            st.write("**Referência bíblica:**", package.get("referencia_biblica") or "—")
            st.write("**Cenas Remastered:**")
            for scene in package.get("cenas_remastered") or []:
                st.markdown(f"**Cena {scene.get('numero')}**")
                st.write(scene.get("texto", ""))
            story = package.get("storyteller") or {}
            if story:
                st.markdown("#### Enriquecimento Storyteller")
                st.json(story)
        with t2:
            st.write("**Bible Guard:**")
            st.json(package.get("bible_guard") or {})
            st.write("**Prompt-Mestre:**")
            st.json(package.get("prompt_master") or {})
            st.write("**Mapa emocional + direção cromática:**")
            st.json(package.get("mapa_emocional") or [])
        with t3:
            st.write("**Style DNA utilizado:**", package.get("style_dna") or "—")
            st.write("**Character Masters vinculados:**")
            st.json(package.get("character_masters") or [])
            visual_stage = ((active.get("stages") or {}).get("visual_preflight") or {}).get("result") or {}
            generation = visual_stage.get("generation") or {}
            if generation:
                st.caption(
                    f"Geração visual autorizada: {'sim' if generation.get('authorized') else 'não'} · "
                    f"geradas: {generation.get('generated', 0)} · reutilizadas: {generation.get('reused', 0)}"
                )
                if generation.get("unresolved"):
                    st.warning("Algumas cenas ficaram como pendência segura porque não foi possível resolver um Master visual sem ambiguidade.")
                    st.json(generation.get("unresolved"))
            candidates = package.get("visual_versions") or []
            if candidates:
                st.warning("Candidatas visuais derivadas prontas para sua decisão final. Nenhuma foi promovida automaticamente.")
                for i, candidate in enumerate(candidates, 1):
                    path = str(candidate.get("derivado") or "")
                    st.markdown(f"**Candidata {i} · {candidate.get('operacao','Remastered')}**")
                    if path and Path(path).exists():
                        st.image(path, use_container_width=True)
                    else:
                        st.caption("Preview não está acessível nesta sessão.")
                    with st.expander("Detalhes técnicos"):
                        st.json(candidate)
            else:
                st.info("Nenhuma candidata visual foi gerada automaticamente. O preflight visual e os assets extraídos permanecem registrados.")
        with t4:
            st.json(package.get("quality_preflight") or {})
            if package.get("quality_guardian_final"):
                st.write("**Quality Guardian final:**")
                st.json(package.get("quality_guardian_final"))
            st.write("**Histórico de recovery:**")
            st.json(package.get("incidents_and_recovery") or [])

        c1, c2 = st.columns(2)
        if c1.button("✅ Aprovar edição Remastered", type="primary", use_container_width=True):
            prepared = approve_run_visual_candidates_and_quality(project, active)
            visual_after = (
                (((prepared.get("stages") or {}).get("quality_preflight") or {}).get("result") or {})
                .get("visual_after_author_approval") or {}
            )
            if visual_after.get("ok"):
                active = approve_final_remaster(project, prepared, approved=True)
                sync_runtime_tree(project)
                st.success("Edição Remastered aprovada pela autora. QA final executado; nenhum Master foi promovido e nada foi publicado automaticamente.")
                st.rerun()
            else:
                active = prepared
                sync_runtime_tree(project)
                st.error("A aprovação final não foi concluída porque o Quality Gate ainda encontrou uma pendência visual segura. O progresso foi preservado para correção e retomada.")
        if c2.button("✏️ Manter para ajustes pontuais", use_container_width=True):
            active = approve_final_remaster(project, active, approved=False)
            sync_runtime_tree(project)
            st.info("Pacote mantido para ajustes. O original permanece preservado.")

    if status == "completed":
        st.success("✅ Autopilot concluído com aprovação final registrada.")
        st.caption("Publicação, promoção a Master e distribuição continuam gates separados.")

    st.caption(f"Autopilot run: {active.get('run_id')} · projeto: {project.get('id')}")

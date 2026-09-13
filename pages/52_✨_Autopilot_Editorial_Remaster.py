import streamlit as st

from estilo import aplicar_estilo, hero
from book_doctor import listar_projetos, carregar_relatorio
from editorial_remaster_autopilot import (
    STAGES, approve_final_remaster, list_runs, load_run, new_run, run_autopilot,
)
from openrouter_client import chamar_llm

st.set_page_config(page_title="Autopilot Editorial Remaster", page_icon="✨", layout="wide")
aplicar_estilo()
hero(
    "✨ Autopilot Editorial Remaster",
    "Envie o livro uma vez, deixe a equipe editorial trabalhar por checkpoints e receba o pacote consolidado para sua decisão final.",
    "FaithBloom · Full Editorial Review + Recovery",
)
st.info(
    "🔒 O original nunca é sobrescrito. O Autopilot pode aplicar melhorias editoriais seguras somente na versão derivada. "
    "Character/Color Masters, Style DNA e versões visuais não são promovidos silenciosamente."
)

projects = [p for p in listar_projetos() if p.get("tipo_projeto") == "story"]
if not projects:
    st.warning("Ainda não há Story Book importado pelo Book Doctor.")
    st.page_link("pages/16_🩺_Book_Doctor.py", label="🩺 Importar no Book Doctor →", use_container_width=True)
    st.stop()

labels = [f"{p.get('titulo','Sem título')} · {p.get('colecao','')} · {p.get('id')}" for p in projects]
idx = st.selectbox("Livro", range(len(projects)), format_func=lambda i: labels[i])
project = projects[idx]
report = carregar_relatorio(project)

st.markdown("### Como o Autopilot trabalha")
st.caption(
    "Book Doctor → mapeamento da história → Revisor → Storyteller + Heart Arc → revisão final → Moral/Bíblia → "
    "emoções + Psicologia das Cores → Style DNA + Character Masters → handoff visual → QA/preflight → pacote final."
)

runs = list_runs(project)
active = None
if runs:
    run_options = [r.get("run_id") for r in runs]
    chosen_run = st.selectbox(
        "Execução existente — opcional",
        [""] + run_options,
        format_func=lambda rid: "— iniciar nova —" if not rid else f"{rid} · {next((r.get('status') for r in runs if r.get('run_id') == rid), '')}",
    )
    if chosen_run:
        active = load_run(project, chosen_run)

if not active:
    st.markdown("### 1 · Autorize a revisão automática")
    c1, c2 = st.columns(2)
    faixa = c1.selectbox("Faixa etária", ["3-5", "3-8", "6-8", "9-12"], index=1)
    versiculo = c2.text_input("Referência bíblica", value="Eclesiastes 3:1" if "Mel Aprendeu a Esperar" in str(project.get("titulo")) else "")
    licao = st.text_area("Lição de moral / verdade central", height=80)
    aprendizado = st.text_area("Aprendizado cristão", height=80)
    emocao = st.text_input("Emoção central")
    auto_safe = st.checkbox(
        "Autorizar o Autopilot a aplicar melhorias editoriais seguras na versão derivada até a revisão final",
        value=True,
        help="Isso permite aplicar automaticamente uma candidata do Storyteller somente quando os guards confirmarem preservação da essência, moral e mensagem bíblica. O original e os Masters permanecem protegidos.",
    )
    paid = st.checkbox(
        "Autorizar geração visual paga quando o pipeline visual estiver habilitado e todos os Masters estiverem inequívocos",
        value=False,
        help="Nunca aprova automaticamente a imagem gerada. A candidata continua pendente para sua decisão final.",
    )
    consent = st.checkbox(
        "Confirmo que quero iniciar a revisão completa automática e receber o resultado consolidado no final.",
        value=False,
    )
    if st.button("✨ Iniciar Revisão Completa Automática", type="primary", disabled=not consent, use_container_width=True):
        active = new_run(
            project,
            report=report,
            settings={
                "faixa_etaria": faixa,
                "versiculo_referencia": versiculo.strip(),
                "licao_final": licao.strip(),
                "aprendizado_cristao": aprendizado.strip(),
                "emocao_central": emocao.strip(),
                "auto_apply_safe_editorial_changes": bool(auto_safe),
                "allow_paid_image_generation": bool(paid),
                "final_human_approval_required": True,
            },
        )
        st.session_state["autopilot_run_id"] = active["run_id"]
        st.rerun()

if active:
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
        label = "▶️ Continuar do último checkpoint" if status in {"blocked", "failed"} else "🚀 Executar / continuar Autopilot"
        if st.button(label, type="primary", use_container_width=True):
            with st.spinner("A equipe FaithBloom está trabalhando. Etapas concluídas serão reutilizadas automaticamente…"):
                active = run_autopilot(project, active, chamar_llm)
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
                "Falhas transitórias podem ser repetidas automaticamente. Defeitos de código são encaminhados e persistidos para retomada após a correção/deploy; "
                "o aplicativo não modifica seu próprio código silenciosamente."
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
            candidates = package.get("visual_versions") or []
            if candidates:
                st.warning("Há candidatas visuais derivadas aguardando sua decisão. Nenhuma foi promovida automaticamente.")
                st.json(candidates)
            else:
                st.info("Nenhuma candidata visual automática foi promovida. O preflight visual está registrado no pacote.")
        with t4:
            st.json(package.get("quality_preflight") or {})
            st.write("**Histórico de recovery:**")
            st.json(package.get("incidents_and_recovery") or [])

        c1, c2 = st.columns(2)
        if c1.button("✅ Aprovar edição Remastered", type="primary", use_container_width=True):
            active = approve_final_remaster(project, active, approved=True)
            st.success("Edição Remastered aprovada pela autora. Nenhum Master foi promovido e nada foi publicado automaticamente.")
            st.rerun()
        if c2.button("✏️ Manter para ajustes pontuais", use_container_width=True):
            active = approve_final_remaster(project, active, approved=False)
            st.info("Pacote mantido para ajustes. O original permanece preservado.")

    if status == "completed":
        st.success("✅ Autopilot concluído com aprovação final registrada.")
        st.caption("Publicação, promoção a Master e distribuição continuam gates separados.")

    st.caption(f"Autopilot run: {active.get('run_id')} · projeto: {project.get('id')}")

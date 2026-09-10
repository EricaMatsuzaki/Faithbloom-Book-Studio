"""Jarvis MVP — conversational front door for FaithBloom."""
from __future__ import annotations

import streamlit as st

from estilo import aplicar_estilo, hero, section_title
from armazenamento import listar_livros, listar_livros_colorir
from jarvis_assistant import AUTONOMY_MODES, build_status_cards, inspect_project_state, interpret_request

st.set_page_config(page_title="Jarvis · FaithBloom", page_icon="🤖", layout="wide")
aplicar_estilo()

hero(
    "🤖 Jarvis · FaithBloom",
    "Conte sua ideia em uma frase. Eu organizo o caminho e reutilizo os especialistas que o FaithBloom já possui.",
    "Praticidade sem perder o controle · MVP funcional",
)

st.info("🌷 Jarvis já entende sua intenção, verifica a rota, encaminha ao fluxo correto e começa a reconhecer o progresso quando você volta. Ele não publica, não gasta créditos e não altera Masters oficiais sem sua aprovação.")

try:
    recent_story_books = listar_livros()[:3]
except Exception:
    recent_story_books = []
try:
    recent_coloring_books = listar_livros_colorir()[:2]
except Exception:
    recent_coloring_books = []

current_state = st.session_state.get("state")
project_progress = inspect_project_state(current_state) if current_state else None

if st.session_state.get("jarvis_handoff_from_mvp") and project_progress:
    with st.container(border=True):
        st.markdown("### 🤖 Recebi o projeto de volta")
        st.success(project_progress["message"])
        p1, p2, p3, p4, p5 = st.columns(5)
        p1.metric("História", "✅" if project_progress["story_ready"] else "⏳")
        p2.metric("Personagens", "✅" if project_progress["characters_ready"] else "⏳")
        p3.metric("Revisão", "✅" if project_progress["review_ready"] else "⏳")
        p4.metric("Imagens", "✅" if project_progress["visuals_ready"] else "⏳")
        p5.metric("Pacote", "✅" if project_progress["package_ready"] else "⏳")
        st.caption(f"Projeto: {project_progress['title']}" + (f" · Coleção: {project_progress['collection']}" if project_progress["collection"] else ""))
        if project_progress["next_step"] == "characters":
            st.page_link("pages/14_👥_Character_Universe.py", label="👥 Continuar com personagens", use_container_width=True)
        elif project_progress["next_step"] == "story_review":
            st.page_link("pages/1_📖_Criar_do_Zero.py", label="📝 Continuar para revisão editorial", use_container_width=True)
        elif project_progress["next_step"] == "visual_preflight":
            st.page_link("pages/0_🤖_Orquestrador_FaithBloom.py", label="🎬 Continuar para pré-voo visual", use_container_width=True)
        elif project_progress["next_step"] == "layout_and_qa":
            st.page_link("pages/25_🛡️_Quality_Guardian.py", label="✅ Continuar para QA e diagramação", use_container_width=True)
        elif project_progress["next_step"] == "publish_or_distribute":
            st.page_link("pages/26_🌐_Publishing_Distribution_Center.py", label="🚀 Continuar para publicação e distribuição", use_container_width=True)

left, right = st.columns([2.1, 1])
with left:
    st.markdown("### 💬 O que você quer fazer hoje?")
    request = st.text_area(
        "Fale com o Jarvis",
        value=st.session_state.get("jarvis_request", ""),
        height=130,
        placeholder="Ex.: Jarvis, crie uma história infantil cristã para 3–8 anos baseada em Filipenses 4:13 usando a Mel.",
        label_visibility="collapsed",
    )
    examples = st.columns(3)
    if examples[0].button("📖 Criar história", use_container_width=True):
        st.session_state["jarvis_request"] = "Crie uma história infantil cristã para 3–8 anos."
        st.rerun()
    if examples[1].button("🖍️ Livro de colorir", use_container_width=True):
        st.session_state["jarvis_request"] = "Crie um livro de colorir infantil."
        st.rerun()
    if examples[2].button("📚 Material de estudo", use_container_width=True):
        st.session_state["jarvis_request"] = "Crie um livro de estudos para adolescentes."
        st.rerun()

    mode = st.radio(
        "Como o Jarvis deve trabalhar?",
        list(AUTONOMY_MODES),
        format_func=lambda x: {"assistant": "🤝 Assistente", "copilot": "🧭 Copiloto", "manager": "🧠 Gerente"}[x],
        horizontal=True,
        help="O MVP mantém aprovação humana nos pontos críticos em todos os modos.",
    )
    if st.button("✨ Jarvis, organize isso", type="primary", use_container_width=True, disabled=not request.strip()):
        try:
            result = interpret_request(request)
            result["autonomy_mode"] = mode
            st.session_state["jarvis_result"] = result
            st.session_state["jarvis_request"] = request
        except Exception as exc:
            st.error(f"Não consegui organizar este pedido ainda: {exc}")

with right:
    st.markdown("### 🤖 Jarvis Hoje")
    with st.container(border=True):
        st.markdown("**Estado do MVP**")
        st.write("🟢 Entende pedidos em linguagem natural")
        st.write("🟢 Roteia para módulos existentes")
        st.write("🟢 Proteção anti-duplicação")
        st.write("🟢 Encaminhamento com sua confirmação")
        st.write("🟢 Reconhece progresso do Story Book ao retornar")
        st.write("🟡 Voz e briefing diário — próximos")

    if recent_story_books or recent_coloring_books:
        st.markdown("#### 📚 Projetos recentes")
        for item in recent_story_books:
            st.caption(f"📖 {item.get('titulo') or '(sem título)'} · {item.get('colecao') or 'sem coleção'}")
        for item in recent_coloring_books:
            st.caption(f"🖍️ {item.get('titulo') or '(sem título)'}")
    else:
        st.caption("📚 Seus projetos recentes aparecerão aqui quando houver itens salvos.")

    st.markdown("#### ⚡ Acessos rápidos")
    st.page_link("pages/0_🤖_Orquestrador_FaithBloom.py", label="🧠 Orquestrador avançado", use_container_width=True)
    st.page_link("pages/14_👥_Character_Universe.py", label="👥 Personagens", use_container_width=True)
    st.page_link("pages/16_🩺_Book_Doctor.py", label="🩺 Revisar / atualizar livro", use_container_width=True)

result = st.session_state.get("jarvis_result")
if result:
    st.divider()
    section_title("Jarvis entendeu assim", "Confira antes de avançar. Você continua no controle.", "Interpretação")
    cards = build_status_cards(result)
    cols = st.columns(4)
    for col, card in zip(cols, cards):
        col.metric(card["label"], card["value"])

    plan = result["route_plan"]
    audit = result["anti_duplication"]
    if audit["ok"]:
        st.success("♻️ Rota verificada: capacidades existentes serão reutilizadas, sem duplicação.")
    else:
        st.error("⚠️ A rota precisa de revisão antes de continuar.")

    st.markdown("### 🧠 Especialistas/capacidades que Jarvis vai coordenar")
    labels = {
        "storyteller": "✍️ Roteirista",
        "heart_arc": "💗 Heart Arc",
        "emotional_experience_engine": "😊 Emotional Experience Engine",
        "bible_guard": "📖 Bible Guard",
        "originality_guard": "🛡️ Originality Guard",
        "character_universe": "👥 Character Universe",
        "world_masters": "🌎 World Masters",
        "visual_preflight": "🎬 Pré-voo visual",
        "translation_localization": "🌍 Translation & Localization",
        "publishing_platform_engine": "📦 Publishing Platform Engine",
        "publishing_distribution_center": "🚀 Publishing & Distribution Center",
        "activity_book_studio": "🧩 Activity Book Studio",
        "coloring_book_studio": "🖍️ Coloring Book Studio",
        "audiobook_studio": "🎧 Audiobook Studio",
        "quality_guardian": "✅ Quality Guardian",
        "animation_video": "🎬 Animation & Video Studio",
        "music": "🎵 Music Studio",
    }
    st.write(" → ".join(labels.get(x, x.replace("_", " ").title()) for x in plan.get("route", [])))

    st.markdown("### 👀 Próximo checkpoint")
    st.write("Jarvis preparou o caminho. Ao confirmar, ele apenas leva você ao fluxo do FaithBloom que já existe para esse projeto; nada caro ou irreversível começa automaticamente.")
    confirm, advanced = st.columns([1.4, 1])
    if confirm.button("✅ Confirmar e continuar com Jarvis", type="primary", use_container_width=True, disabled=not audit["ok"]):
        st.session_state["jarvis_approved_request"] = result["request"]
        st.session_state["jarvis_approved_route"] = result["route_plan"]
        st.session_state["jarvis_handoff_from_mvp"] = True
        st.switch_page(result.get("next_page") or "pages/0_🤖_Orquestrador_FaithBloom.py")
    advanced.page_link("pages/0_🤖_Orquestrador_FaithBloom.py", label="🧠 Abrir modo avançado", use_container_width=True)

st.caption("Jarvis MVP · FaithBloom · camada conversacional sobre o Orquestrador existente — não duplica Studios ou Guardians.")

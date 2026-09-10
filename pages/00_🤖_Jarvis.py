"""Jarvis MVP — conversational front door for FaithBloom."""
from __future__ import annotations

import streamlit as st

from estilo import aplicar_estilo, hero, section_title
from jarvis_assistant import AUTONOMY_MODES, build_status_cards, interpret_request

st.set_page_config(page_title="Jarvis · FaithBloom", page_icon="🤖", layout="wide")
aplicar_estilo()

hero(
    "🤖 Jarvis · FaithBloom",
    "Conte sua ideia em uma frase. Eu organizo o caminho e reutilizo os especialistas que o FaithBloom já possui.",
    "Praticidade sem perder o controle · MVP funcional",
)

st.info("🌷 Nesta primeira versão, Jarvis entende a intenção e prepara a rota. Ele não publica, não gasta créditos e não altera Masters oficiais sem sua aprovação.")

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
        help="O MVP ainda mantém aprovação humana nos pontos críticos em todos os modos.",
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
        st.write("🟢 Interpretação de intenção")
        st.write("🟢 Roteamento editorial")
        st.write("🟢 Proteção anti-duplicação")
        st.write("🟢 Aprovação humana")
        st.write("🟡 Voz e briefing diário — próximos")
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
    st.write("Jarvis preparou o caminho, mas ainda não iniciou geração cara nem publicação. O próximo passo é confirmar a proposta e entrar no fluxo apropriado.")
    a, b = st.columns(2)
    a.page_link("pages/0_🤖_Orquestrador_FaithBloom.py", label="✅ Continuar no Orquestrador", use_container_width=True)
    b.page_link("pages/38_🪄_Prompt_Mestre_Studio.py", label="🪄 Abrir Prompt Mestre", use_container_width=True)

st.caption("Jarvis MVP · FaithBloom · camada conversacional sobre o Orquestrador existente — não duplica Studios ou Guardians.")

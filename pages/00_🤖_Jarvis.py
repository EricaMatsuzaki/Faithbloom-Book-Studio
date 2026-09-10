"""Jarvis MVP — conversational front door for FaithBloom."""
from __future__ import annotations

import streamlit as st

from estilo import aplicar_estilo
from armazenamento import listar_livros, listar_livros_colorir
from jarvis_assistant import AUTONOMY_MODES, build_status_cards, inspect_project_state, interpret_request

st.set_page_config(page_title="Jarvis · FaithBloom", page_icon="🤖", layout="wide")
aplicar_estilo()

# Visual próprio da Home do Jarvis. Reutiliza o tema global e só adiciona a camada
# de presença do assistente; não cria um segundo design system.
st.markdown(
    """
    <style>
    .jarvis-shell{
      position:relative;overflow:hidden;border-radius:30px;padding:2.1rem 2.2rem;
      background:linear-gradient(125deg,rgba(14,39,61,.98),rgba(24,104,107,.96) 52%,rgba(76,67,151,.95));
      border:1px solid rgba(255,255,255,.18);box-shadow:0 26px 70px rgba(25,72,102,.22);color:white;
    }
    .jarvis-shell:before{content:"";position:absolute;width:440px;height:440px;right:-150px;top:-230px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.23),transparent 65%)}
    .jarvis-shell:after{content:"";position:absolute;width:260px;height:260px;left:42%;bottom:-190px;border-radius:50%;background:radial-gradient(circle,rgba(246,154,200,.24),transparent 68%)}
    .jarvis-grid{position:relative;z-index:2;display:grid;grid-template-columns:1fr 170px;gap:1.5rem;align-items:center}
    .jarvis-kicker{display:inline-block;padding:.34rem .72rem;border-radius:999px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.16);font-size:.72rem;font-weight:800;letter-spacing:.11em;text-transform:uppercase}
    .jarvis-shell h1{color:white!important;font-size:clamp(2.25rem,4vw,4rem);line-height:1;margin:.7rem 0 .55rem;letter-spacing:-.045em}
    .jarvis-shell p{margin:0;color:rgba(255,255,255,.84);font-size:1rem;line-height:1.65;max-width:780px}
    .jarvis-orb-wrap{display:flex;justify-content:center;align-items:center}
    .jarvis-orb{width:132px;height:132px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:4.1rem;background:radial-gradient(circle at 35% 30%,#fff,rgba(186,245,240,.92) 18%,rgba(74,200,198,.72) 44%,rgba(98,103,231,.66) 70%,rgba(27,43,79,.85));box-shadow:0 0 0 12px rgba(255,255,255,.055),0 0 45px rgba(82,222,214,.46),inset 0 0 28px rgba(255,255,255,.45);animation:jarvisPulse 3.2s ease-in-out infinite}
    @keyframes jarvisPulse{0%,100%{transform:scale(1);box-shadow:0 0 0 12px rgba(255,255,255,.055),0 0 42px rgba(82,222,214,.38),inset 0 0 28px rgba(255,255,255,.45)}50%{transform:scale(1.035);box-shadow:0 0 0 16px rgba(255,255,255,.04),0 0 66px rgba(120,116,255,.46),inset 0 0 32px rgba(255,255,255,.48)}}
    .jarvis-status-row{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:1rem}.jarvis-pill{padding:.3rem .65rem;border-radius:999px;font-size:.76rem;font-weight:700;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.13)}
    .jarvis-panel{background:rgba(255,255,255,.79);backdrop-filter:blur(14px);border:1px solid rgba(31,87,105,.12);border-radius:22px;padding:1.15rem 1.25rem;box-shadow:0 12px 34px rgba(41,73,102,.07);margin-bottom:.75rem}
    .jarvis-panel h3,.jarvis-panel h4{margin-top:0}.jarvis-msg{border-radius:20px 20px 20px 6px;padding:1rem 1.1rem;background:linear-gradient(135deg,rgba(34,168,153,.09),rgba(139,108,246,.08));border:1px solid rgba(34,168,153,.17);line-height:1.55}
    .jarvis-timeline{display:grid;grid-template-columns:repeat(5,1fr);gap:.55rem;margin:.7rem 0}.jarvis-step{text-align:center;padding:.7rem .35rem;border-radius:14px;background:rgba(255,255,255,.75);border:1px solid rgba(31,87,105,.1);font-size:.8rem}.jarvis-step strong{display:block;font-size:1.05rem;margin-bottom:.15rem}
    @media(max-width:800px){.jarvis-grid{grid-template-columns:1fr}.jarvis-orb-wrap{order:-1}.jarvis-orb{width:100px;height:100px;font-size:3.2rem}.jarvis-timeline{grid-template-columns:1fr 1fr}}
    </style>
    <div class="jarvis-shell">
      <div class="jarvis-grid">
        <div>
          <span class="jarvis-kicker">FaithBloom Intelligence · MVP</span>
          <h1>🤖 Jarvis</h1>
          <p>Seu assistente central do FaithBloom. Conte o que deseja criar, revisar ou continuar. Eu organizo o caminho, aciono os módulos que já existem e devolvo o projeto para você nos pontos de decisão.</p>
          <div class="jarvis-status-row">
            <span class="jarvis-pill">🟢 Online</span><span class="jarvis-pill">♻️ Anti-duplicação ativa</span><span class="jarvis-pill">👀 Aprovação humana</span><span class="jarvis-pill">🔒 Masters protegidos</span>
          </div>
        </div>
        <div class="jarvis-orb-wrap"><div class="jarvis-orb">🤖</div></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

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

st.markdown("### ✨ Jarvis Hoje")
if project_progress:
    st.markdown(
        f"<div class='jarvis-msg'><strong>🤖 Jarvis:</strong> {project_progress['message']}<br><small>Projeto: {project_progress['title']}"
        + (f" · Coleção: {project_progress['collection']}" if project_progress["collection"] else "")
        + "</small></div>",
        unsafe_allow_html=True,
    )
    timeline = [
        ("História", project_progress["story_ready"]),
        ("Personagens", project_progress["characters_ready"]),
        ("Revisão", project_progress["review_ready"]),
        ("Imagens", project_progress["visuals_ready"]),
        ("Pacote", project_progress["package_ready"]),
    ]
    html = "<div class='jarvis-timeline'>" + "".join(
        f"<div class='jarvis-step'><strong>{'✅' if ready else '⏳'}</strong>{label}</div>" for label, ready in timeline
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

    if project_progress["next_step"] == "characters":
        st.page_link("pages/14_👥_Character_Universe.py", label="👥 Jarvis recomenda: continuar com personagens", use_container_width=True)
    elif project_progress["next_step"] == "story_review":
        st.page_link("pages/1_📖_Criar_do_Zero.py", label="📝 Jarvis recomenda: revisão editorial", use_container_width=True)
    elif project_progress["next_step"] == "visual_preflight":
        st.page_link("pages/0_🤖_Orquestrador_FaithBloom.py", label="🎬 Jarvis recomenda: pré-voo visual", use_container_width=True)
    elif project_progress["next_step"] == "layout_and_qa":
        st.page_link("pages/25_🛡️_Quality_Guardian.py", label="✅ Jarvis recomenda: QA e diagramação", use_container_width=True)
    elif project_progress["next_step"] == "publish_or_distribute":
        st.page_link("pages/26_🌐_Publishing_Distribution_Center.py", label="🚀 Jarvis recomenda: publicação e distribuição", use_container_width=True)
else:
    st.markdown(
        "<div class='jarvis-msg'><strong>🤖 Jarvis:</strong> Estou pronto. Você pode começar com uma ideia simples, pedir um livro, retomar um projeto ou revisar algo que já existe.</div>",
        unsafe_allow_html=True,
    )

left, right = st.columns([2.15, 1])
with left:
    st.markdown("### 💬 Fale comigo")
    request = st.text_area(
        "Fale com o Jarvis",
        value=st.session_state.get("jarvis_request", ""),
        height=145,
        placeholder="Ex.: Jarvis, crie uma história infantil cristã para 3–8 anos baseada em Filipenses 4:13 usando a Mel.",
        label_visibility="collapsed",
    )
    examples = st.columns(3)
    if examples[0].button("📖 Criar história", use_container_width=True):
        st.session_state["jarvis_request"] = "Crie uma história infantil cristã para 3–8 anos."
        st.rerun()
    if examples[1].button("🔄 Continuar projeto", use_container_width=True):
        if project_progress:
            st.session_state["jarvis_request"] = f"Continue o projeto {project_progress['title']} do ponto atual."
        else:
            st.session_state["jarvis_request"] = "Quero continuar um projeto existente."
        st.rerun()
    if examples[2].button("🩺 Revisar livro", use_container_width=True):
        st.session_state["jarvis_request"] = "Quero revisar ou atualizar um livro existente."
        st.rerun()

    mode = st.radio(
        "Como o Jarvis deve trabalhar?",
        list(AUTONOMY_MODES),
        format_func=lambda x: {"assistant": "🤝 Assistente", "copilot": "🧭 Copiloto", "manager": "🧠 Gerente"}[x],
        horizontal=True,
        help="Nesta fase todos os modos mantêm aprovação humana nos pontos críticos.",
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
    with st.container(border=True):
        st.markdown("#### ⚡ Central rápida")
        st.page_link("pages/0_🤖_Orquestrador_FaithBloom.py", label="🧠 Orquestrador", use_container_width=True)
        st.page_link("pages/14_👥_Character_Universe.py", label="👥 Personagens", use_container_width=True)
        st.page_link("pages/16_🩺_Book_Doctor.py", label="🩺 Revisar / atualizar", use_container_width=True)
        st.page_link("pages/26_🌐_Publishing_Distribution_Center.py", label="🚀 Publicar", use_container_width=True)

    with st.container(border=True):
        st.markdown("#### 📚 Projetos recentes")
        if recent_story_books or recent_coloring_books:
            for item in recent_story_books:
                st.caption(f"📖 {item.get('titulo') or '(sem título)'} · {item.get('colecao') or 'sem coleção'}")
            for item in recent_coloring_books:
                st.caption(f"🖍️ {item.get('titulo') or '(sem título)'}")
        else:
            st.caption("Seus projetos salvos aparecerão aqui.")

result = st.session_state.get("jarvis_result")
if result:
    st.divider()
    st.markdown("### 🧠 Entendi seu pedido assim")
    cards = build_status_cards(result)
    cols = st.columns(4)
    for col, card in zip(cols, cards):
        col.metric(card["label"], card["value"])

    plan = result["route_plan"]
    audit = result["anti_duplication"]
    if audit["ok"]:
        st.success("♻️ Rota verificada: vou reutilizar as capacidades existentes, sem criar fluxo paralelo.")
    else:
        st.error("⚠️ A rota precisa de revisão antes de continuar.")

    labels = {
        "storyteller": "✍️ Roteirista", "heart_arc": "💗 Heart Arc",
        "emotional_experience_engine": "😊 Emotional Experience Engine", "bible_guard": "📖 Bible Guard",
        "originality_guard": "🛡️ Originality Guard", "character_universe": "👥 Character Universe",
        "world_masters": "🌎 World Masters", "visual_preflight": "🎬 Pré-voo visual",
        "translation_localization": "🌍 Translation & Localization", "publishing_platform_engine": "📦 Publishing Platform Engine",
        "publishing_distribution_center": "🚀 Publishing & Distribution Center", "activity_book_studio": "🧩 Activity Book Studio",
        "coloring_book_studio": "🖍️ Coloring Book Studio", "audiobook_studio": "🎧 Audiobook Studio",
        "quality_guardian": "✅ Quality Guardian", "animation_video": "🎬 Animation & Video Studio", "music": "🎵 Music Studio",
    }
    with st.expander("Ver a rota que o Jarvis vai coordenar", expanded=False):
        st.write(" → ".join(labels.get(x, x.replace("_", " ").title()) for x in plan.get("route", [])))

    st.markdown("### 👀 Sua decisão")
    st.write("Ao confirmar, eu apenas continuo pelo módulo FaithBloom correto. Geração cara, publicação e alterações de Masters continuam protegidas por aprovação.")
    confirm, advanced = st.columns([1.45, 1])
    if confirm.button("✅ Confirmar e continuar com Jarvis", type="primary", use_container_width=True, disabled=not audit["ok"]):
        st.session_state["jarvis_approved_request"] = result["request"]
        st.session_state["jarvis_approved_route"] = result["route_plan"]
        st.session_state["jarvis_handoff_from_mvp"] = True
        st.switch_page(result.get("next_page") or "pages/0_🤖_Orquestrador_FaithBloom.py")
    advanced.page_link("pages/0_🤖_Orquestrador_FaithBloom.py", label="🧠 Abrir modo avançado", use_container_width=True)

st.caption("Jarvis MVP · FaithBloom · uma única camada conversacional sobre Orquestrador, Studios, Masters e Guardians existentes.")

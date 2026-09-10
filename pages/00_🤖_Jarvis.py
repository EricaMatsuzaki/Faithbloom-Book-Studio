"""Jarvis MVP — conversational front door for FaithBloom."""
from __future__ import annotations

import re
import streamlit as st

from estilo import aplicar_estilo
from armazenamento import listar_livros, listar_livros_colorir
from jarvis_assistant import AUTONOMY_MODES, build_status_cards, inspect_project_state, interpret_request

st.set_page_config(page_title="Jarvis · FaithBloom", page_icon="🤖", layout="wide")
aplicar_estilo()


def _visual_expression(request: str, result: dict | None) -> str:
    """Escolhe apenas a reação visual do avatar; não altera a rota editorial."""
    forced = st.session_state.get("jarvis_visual_expression")
    if forced in {"normal", "heart", "star", "thinking", "attention"}:
        return forced
    text = (request or "").casefold()
    if result and not (result.get("anti_duplication") or {}).get("ok", True):
        return "attention"
    if any(x in text for x in ("incrível", "incrivel", "sensacional", "surpreendente", "original", "criativa", "criativo", "uau")):
        return "star"
    if any(x in text for x in ("amor", "carinho", "amizade", "família", "familia", "gentileza", "esperança", "esperanca", "fé", "fe")):
        return "heart"
    return "normal"


def _eyes_markup(expression: str) -> str:
    if expression == "heart":
        return "<span class='j-eye-symbol'>♥</span><span class='j-eye-symbol'>♥</span>"
    if expression == "star":
        return "<span class='j-eye-symbol star'>★</span><span class='j-eye-symbol star'>★</span>"
    if expression == "thinking":
        return "<span class='j-eye dot'></span><span class='j-eye thinking'></span>"
    if expression == "attention":
        return "<span class='j-eye alert'></span><span class='j-eye alert'></span>"
    return "<span class='j-eye'></span><span class='j-eye'></span>"


# Visual próprio da Home do Jarvis. Reutiliza o tema global e adiciona somente
# a presença animada do assistente, sem criar um segundo design system.
st.markdown(
    """
    <style>
    .jarvis-shell{
      position:relative;overflow:hidden;border-radius:30px;padding:2.15rem 2.25rem;
      background:linear-gradient(125deg,rgba(14,39,61,.98),rgba(24,104,107,.96) 52%,rgba(76,67,151,.95));
      border:1px solid rgba(255,255,255,.18);box-shadow:0 26px 70px rgba(25,72,102,.22);color:white;
    }
    .jarvis-shell:before{content:"";position:absolute;width:440px;height:440px;right:-150px;top:-230px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.23),transparent 65%)}
    .jarvis-shell:after{content:"";position:absolute;width:260px;height:260px;left:42%;bottom:-190px;border-radius:50%;background:radial-gradient(circle,rgba(246,154,200,.24),transparent 68%)}
    .jarvis-grid{position:relative;z-index:2;display:grid;grid-template-columns:1fr 230px;gap:1.5rem;align-items:center}
    .jarvis-kicker{display:inline-block;padding:.34rem .72rem;border-radius:999px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.16);font-size:.72rem;font-weight:800;letter-spacing:.11em;text-transform:uppercase}
    .jarvis-shell h1{color:white!important;font-size:clamp(2.25rem,4vw,4rem);line-height:1;margin:.7rem 0 .55rem;letter-spacing:-.045em}
    .jarvis-shell p{margin:0;color:rgba(255,255,255,.84);font-size:1rem;line-height:1.65;max-width:780px}
    .jarvis-status-row{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:1rem}.jarvis-pill{padding:.3rem .65rem;border-radius:999px;font-size:.76rem;font-weight:700;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.13)}

    .jarvis-avatar-wrap{display:flex;justify-content:center;align-items:center;min-height:210px;animation:jarvisFloat 4s ease-in-out infinite}
    .jarvis-avatar{position:relative;width:185px;height:205px;filter:drop-shadow(0 18px 32px rgba(0,0,0,.24))}
    .j-antenna{position:absolute;left:50%;top:0;transform:translateX(-50%);width:8px;height:28px;border-radius:9px;background:linear-gradient(#dffcff,#65dfe2);box-shadow:0 0 13px rgba(101,223,226,.8)}
    .j-antenna:before{content:"";position:absolute;width:14px;height:14px;border-radius:50%;background:#8ff5ef;left:-3px;top:-7px;box-shadow:0 0 16px #8ff5ef}
    .j-head{position:absolute;left:17px;top:24px;width:151px;height:112px;border-radius:47% 47% 43% 43% / 42% 42% 52% 52%;background:linear-gradient(145deg,#fff,#dbe8f3 62%,#aebed0);border:2px solid rgba(255,255,255,.9);box-shadow:inset -9px -10px 18px rgba(60,79,109,.16),0 0 24px rgba(72,220,224,.22)}
    .j-face{position:absolute;left:12px;top:14px;width:127px;height:82px;border-radius:40px;background:radial-gradient(circle at 50% 28%,#173454,#071421 67%);border:2px solid rgba(101,223,226,.8);box-shadow:inset 0 0 22px rgba(80,203,235,.16),0 0 14px rgba(101,223,226,.34);display:flex;align-items:center;justify-content:center;gap:27px}
    .j-eye{display:block;width:26px;height:13px;border-top:5px solid #74f6f0;border-radius:50%;filter:drop-shadow(0 0 6px #62e9ef);transform:translateY(3px)}
    .j-eye.dot{width:12px;height:12px;border:0;border-radius:50%;background:#74f6f0;transform:none}.j-eye.thinking{width:22px;height:22px;border:4px solid #74f6f0;border-left-color:transparent;border-radius:50%;transform:none;animation:jSpin 1.2s linear infinite}
    .j-eye.alert{width:20px;height:20px;border:0;border-radius:50%;background:#ffd66d;box-shadow:0 0 14px rgba(255,214,109,.8);transform:none}
    .j-eye-symbol{font-size:29px;line-height:1;color:#ff72cb;text-shadow:0 0 9px rgba(255,114,203,.9);animation:jHeart 1.15s ease-in-out infinite}.j-eye-symbol.star{color:#ffd76a;text-shadow:0 0 10px rgba(255,215,106,.95);animation:jStar 1.1s ease-in-out infinite}
    .j-smile{position:absolute;width:28px;height:13px;border-bottom:4px solid #76f7f0;border-radius:0 0 22px 22px;left:50%;bottom:13px;transform:translateX(-50%);filter:drop-shadow(0 0 5px #62e9ef)}
    .j-ear{position:absolute;top:52px;width:22px;height:39px;border-radius:13px;background:linear-gradient(#dff9ff,#8cb1cf);border:2px solid #8eeae8}.j-ear.left{left:-10px}.j-ear.right{right:-10px}
    .j-body{position:absolute;left:40px;top:127px;width:105px;height:72px;border-radius:29px 29px 38px 38px;background:linear-gradient(145deg,#fff,#d9e6f0 68%,#a9bbce);border:2px solid rgba(255,255,255,.92);box-shadow:inset -8px -8px 16px rgba(56,77,105,.13)}
    .j-core{position:absolute;left:50%;top:14px;transform:translateX(-50%);width:43px;height:43px;border-radius:50%;background:#0c2033;border:3px solid #66e9ed;box-shadow:0 0 18px rgba(102,233,237,.62);display:flex;align-items:center;justify-content:center;color:#ff8fd2;font-size:21px}
    .j-arm{position:absolute;top:143px;width:24px;height:54px;border-radius:16px;background:linear-gradient(#eef7fd,#a9bfd1);border:1px solid rgba(255,255,255,.85)}.j-arm.left{left:22px;transform:rotate(18deg)}.j-arm.right{right:22px;transform:rotate(-18deg)}
    .j-bloom{position:absolute;right:-4px;top:19px;font-size:21px;filter:drop-shadow(0 0 7px rgba(246,154,200,.65));animation:jBloom 2.6s ease-in-out infinite}
    @keyframes jarvisFloat{0%,100%{transform:translateY(0) rotate(0deg)}50%{transform:translateY(-9px) rotate(.6deg)}}
    @keyframes jHeart{0%,100%{transform:scale(1)}50%{transform:scale(1.14)}}
    @keyframes jStar{0%,100%{transform:scale(1) rotate(0)}50%{transform:scale(1.14) rotate(8deg)}}
    @keyframes jSpin{to{transform:rotate(360deg)}}
    @keyframes jBloom{0%,100%{transform:rotate(-5deg) scale(1)}50%{transform:rotate(7deg) scale(1.08)}}

    .jarvis-msg{border-radius:20px 20px 20px 6px;padding:1rem 1.1rem;background:linear-gradient(135deg,rgba(34,168,153,.09),rgba(139,108,246,.08));border:1px solid rgba(34,168,153,.17);line-height:1.55}
    .jarvis-timeline{display:grid;grid-template-columns:repeat(5,1fr);gap:.55rem;margin:.7rem 0}.jarvis-step{text-align:center;padding:.7rem .35rem;border-radius:14px;background:rgba(255,255,255,.75);border:1px solid rgba(31,87,105,.1);font-size:.8rem}.jarvis-step strong{display:block;font-size:1.05rem;margin-bottom:.15rem}
    .jarvis-expression-note{font-size:.82rem;color:#5f6b7a;margin-top:.25rem}
    @media(max-width:800px){.jarvis-grid{grid-template-columns:1fr}.jarvis-avatar-wrap{order:-1;min-height:185px}.jarvis-avatar{transform:scale(.88)}.jarvis-timeline{grid-template-columns:1fr 1fr}}
    </style>
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
result = st.session_state.get("jarvis_result")
request_for_visual = st.session_state.get("jarvis_request", "")
expression = _visual_expression(request_for_visual, result)
eyes = _eyes_markup(expression)
expression_label = {
    "normal": "😊 Online",
    "heart": "😍 Amei sua ideia",
    "star": "🤩 Isso ficou incrível",
    "thinking": "🧠 Pensando",
    "attention": "⚠️ Atenção",
}.get(expression, "😊 Online")

st.markdown(
    f"""
    <div class="jarvis-shell">
      <div class="jarvis-grid">
        <div>
          <span class="jarvis-kicker">FaithBloom Intelligence · Bloom Companion</span>
          <h1>Jarvis 🤖</h1>
          <p>Seu assistente central do FaithBloom. Conte o que deseja criar, revisar ou continuar. Eu organizo o caminho, coordeno os módulos existentes e volto para você nos pontos de decisão.</p>
          <div class="jarvis-status-row">
            <span class="jarvis-pill">🟢 Online</span><span class="jarvis-pill">♻️ Anti-duplicação ativa</span><span class="jarvis-pill">👀 Aprovação humana</span><span class="jarvis-pill">🔒 Masters protegidos</span>
          </div>
        </div>
        <div>
          <div class="jarvis-avatar-wrap">
            <div class="jarvis-avatar" aria-label="Avatar animado do Jarvis">
              <div class="j-antenna"></div><div class="j-head"><div class="j-ear left"></div><div class="j-ear right"></div><div class="j-face">{eyes}<div class="j-smile"></div></div><div class="j-bloom">🌷</div></div>
              <div class="j-arm left"></div><div class="j-arm right"></div><div class="j-body"><div class="j-core">♥</div></div>
            </div>
          </div>
          <div style="text-align:center;font-weight:800;color:white;margin-top:-4px">{expression_label}</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("🎭 Ver as expressões do Jarvis", expanded=False):
    st.caption("Prévia visual beta. As reações não mudam o conteúdo do projeto nem gastam créditos.")
    e1, e2, e3, e4, e5 = st.columns(5)
    if e1.button("😊 Normal", use_container_width=True):
        st.session_state["jarvis_visual_expression"] = "normal"; st.rerun()
    if e2.button("😍 Amei!", use_container_width=True):
        st.session_state["jarvis_visual_expression"] = "heart"; st.rerun()
    if e3.button("🤩 Incrível!", use_container_width=True):
        st.session_state["jarvis_visual_expression"] = "star"; st.rerun()
    if e4.button("🧠 Pensando", use_container_width=True):
        st.session_state["jarvis_visual_expression"] = "thinking"; st.rerun()
    if e5.button("⚠️ Atenção", use_container_width=True):
        st.session_state["jarvis_visual_expression"] = "attention"; st.rerun()
    st.markdown("<div class='jarvis-expression-note'>Depois, voz e eventos reais poderão trocar essas expressões automaticamente.</div>", unsafe_allow_html=True)

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
        st.session_state.pop("jarvis_visual_expression", None)
        st.rerun()
    if examples[1].button("🔄 Continuar projeto", use_container_width=True):
        if project_progress:
            st.session_state["jarvis_request"] = f"Continue o projeto {project_progress['title']} do ponto atual."
        else:
            st.session_state["jarvis_request"] = "Quero continuar um projeto existente."
        st.session_state["jarvis_visual_expression"] = "thinking"
        st.rerun()
    if examples[2].button("🩺 Revisar livro", use_container_width=True):
        st.session_state["jarvis_request"] = "Quero revisar ou atualizar um livro existente."
        st.session_state["jarvis_visual_expression"] = "thinking"
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
            st.session_state.pop("jarvis_visual_expression", None)
            st.rerun()
        except Exception as exc:
            st.session_state["jarvis_visual_expression"] = "attention"
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
        st.session_state["jarvis_visual_expression"] = "thinking"
        st.switch_page(result.get("next_page") or "pages/0_🤖_Orquestrador_FaithBloom.py")
    advanced.page_link("pages/0_🤖_Orquestrador_FaithBloom.py", label="🧠 Abrir modo avançado", use_container_width=True)

st.caption("Jarvis MVP · FaithBloom · avatar Bloom Companion animado sobre Orquestrador, Studios, Masters e Guardians existentes.")

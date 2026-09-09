"""FaithBloom Orchestrator — practical author-controlled visual workflow."""
from __future__ import annotations

import uuid
import streamlit as st

from estilo import aplicar_estilo, hero, section_title
from character_universe import listar_personagens_oficiais, carregar_personagem_oficial
from orchestrator_visual import (
    GENERATION_MODES,
    approve_character_candidate,
    approve_story,
    approve_style,
    approve_world_master,
    build_element_lock_instruction,
    cost_gate,
    create_visual_plan,
    create_world_master,
    link_location_approval,
    load_visual_plan,
    scenario_only_instruction,
    visual_preflight_status,
)

st.set_page_config(page_title="Orquestrador FaithBloom", page_icon="🤖", layout="wide")
aplicar_estilo()

hero(
    "🤖 Orquestrador FaithBloom",
    "Praticidade sem perder o controle: história primeiro, depois personagens e cenários aprovados, e só então cenas e ilustrações.",
    "Visual Preflight · World/Location Master · Element Lock · Cost Gate",
)

st.info(
    "🔒 Regra do Orquestrador: nenhum lote visual caro deve começar antes da sua aprovação da história, personagens principais, cenários essenciais e estilo visual. Uma candidata aprovada não vira Character Master oficial automaticamente."
)

with st.expander("💰 Como quero gerar imagens", expanded=True):
    mode_keys = list(GENERATION_MODES)
    selected_mode = st.radio(
        "Modo de geração",
        mode_keys,
        format_func=lambda k: GENERATION_MODES[k]["label"],
        horizontal=True,
        key="orchestrator_generation_mode",
    )
    st.caption(GENERATION_MODES[selected_mode]["description"])
    budget_enabled = st.checkbox("Definir limite de orçamento para este projeto", value=True)
    budget_limit = st.number_input("Limite (US$)", min_value=0.0, value=5.0, step=0.50, disabled=not budget_enabled)
    st.caption("Operações pagas continuam exigindo confirmação; o limite impede estouro silencioso do orçamento.")

section_title("1 · História primeiro", "Escreva/cole a história aprovada ou use o Roteirista. Só depois o Orquestrador abre o pré-voo visual.", "Autoria")
left, right = st.columns([2, 1])
with left:
    title = st.text_input("Título do projeto", value=st.session_state.get("orchestrator_title", ""), placeholder="Ex.: A nova aventura da Mel")
    collection = st.text_input("Coleção", value=st.session_state.get("orchestrator_collection", "Pequenas Histórias, Grandes Lições"))
    story = st.text_area("História / texto-base", height=220, placeholder="Cole aqui a versão que será usada para definir personagens e cenários.")
with right:
    st.markdown("#### Quer criar a história com o FaithBloom?")
    st.page_link("pages/39_✍️_Historia_4_Estilos.py", label="✍️ Abrir Roteirista", use_container_width=True)
    st.page_link("pages/38_🪄_Prompt_Mestre_Studio.py", label="🪄 Abrir Prompt-Mestre", use_container_width=True)

characters_text = st.text_input("Personagens principais (separe por vírgula)", placeholder="Mel, Manu, Téo")
locations_text = st.text_input("Cenários principais (separe por vírgula)", placeholder="Jardim, Casa da Manu, Praça")

if st.button("🌱 Criar pré-voo visual", type="primary", use_container_width=True):
    chars = [x.strip() for x in characters_text.split(",") if x.strip()]
    locs = [x.strip() for x in locations_text.split(",") if x.strip()]
    plan = create_visual_plan(
        project_id=uuid.uuid4().hex,
        title=title or "Novo livro FaithBloom",
        story_text=story,
        characters=[{"id": x, "name": x, "principal": True} for x in chars],
        locations=[{"id": x, "name": x, "required": True} for x in locs],
        generation_mode=selected_mode,
        budget_limit_usd=budget_limit if budget_enabled else None,
    )
    st.session_state["orchestrator_visual_plan_id"] = plan["id"]
    st.session_state["orchestrator_collection"] = collection
    st.success("Pré-voo visual criado. Agora aprove cada etapa antes das cenas.")
    st.rerun()

plan_id = st.session_state.get("orchestrator_visual_plan_id")
if not plan_id:
    st.stop()
plan = load_visual_plan(plan_id)
if not plan:
    st.warning("Não foi possível carregar o pré-voo visual atual.")
    st.stop()

section_title("2 · Checkpoint da história", "Aprovar aqui libera apenas a próxima etapa; ainda não gera imagens.", "Checkpoint")
if plan.get("approvals", {}).get("story"):
    st.success("✅ História aprovada para o pré-voo visual.")
else:
    if st.button("✅ Aprovar história para seguir ao visual", use_container_width=True):
        approve_story(plan)
        st.rerun()

section_title("3 · Personagens antes das cenas", "Use Masters existentes quando houver. Personagem novo deve ser definido e aprovado antes do lote de ilustrações.", "Character Master")
collection = st.session_state.get("orchestrator_collection", "")
officials = listar_personagens_oficiais(collection or None)
by_name = {str(x.get("nome") or "").casefold(): x for x in officials}
for char in plan.get("characters", []):
    cid = str(char.get("id") or char.get("name") or "")
    approval = plan.get("approvals", {}).get("characters", {}).get(cid, {})
    with st.container(border=True):
        st.markdown(f"#### 👤 {char.get('name') or cid}")
        if approval.get("approved"):
            st.success("✅ Referência visual aprovada para este livro.")
            if approval.get("official_master_promoted"):
                st.caption("⭐ Promoção a Master oficial registrada com aprovação humana.")
        else:
            existing = by_name.get((char.get("name") or cid).casefold())
            if existing:
                full = carregar_personagem_oficial(existing["id"])
                st.write(f"Character Master encontrado em **{existing.get('colecao')}**.")
                master = full.get("color_master") or ""
                if master:
                    try:
                        st.image(master, width=220)
                    except Exception:
                        st.caption("Color Master disponível no Character Universe.")
                if st.button(f"✅ Usar Master oficial de {char.get('name') or cid}", key=f"use_char_{cid}", use_container_width=True):
                    approve_character_candidate(plan, cid, f"official:{existing['id']}", master)
                    st.rerun()
            else:
                st.warning("Personagem ainda sem Master oficial nesta coleção.")
                st.page_link("pages/14_👥_Character_Universe.py", label="👥 Criar / melhorar personagem", use_container_width=True)
                candidate = st.text_input("ID/URI de candidata aprovada (opcional, após criar a proposta visual)", key=f"candidate_{cid}")
                if candidate and st.button(f"👀 Aprovar candidata de {char.get('name') or cid}", key=f"approve_candidate_{cid}"):
                    approve_character_candidate(plan, cid, candidate, candidate)
                    st.rerun()

section_title("4 · World / Location Master", "Defina os lugares principais agora. Assim você pode reprovar o jardim ou a casa antes de gastar com todas as cenas.", "Cenários")
for loc in plan.get("locations", []):
    key = str(loc.get("id") or loc.get("name") or "")
    approval = plan.get("approvals", {}).get("locations", {}).get(key, {})
    with st.container(border=True):
        st.markdown(f"#### 🌎 {loc.get('name') or key}")
        if approval.get("approved"):
            st.success("✅ World/Location Master aprovado e vinculado.")
        else:
            description = st.text_area(
                "Como este lugar deve parecer?",
                key=f"world_desc_{key}",
                placeholder="Ex.: jardim de primavera, flores delicadas, caminho de pedras, luz da manhã...",
            )
            if st.button(f"🌿 Criar e aprovar cenário mestre: {loc.get('name') or key}", key=f"world_{key}", use_container_width=True, disabled=not description.strip()):
                world = create_world_master(collection, loc.get("name") or key, description)
                world = approve_world_master(world["id"])
                plan = link_location_approval(plan, key, world["id"])
                st.success("Cenário salvo como World/Location Master aprovado.")
                st.rerun()

section_title("5 · Estilo visual", "A estética do livro também precisa ser aprovada antes de gerar o lote de cenas.", "Style Master")
if plan.get("approvals", {}).get("style"):
    st.success("✅ Style Master aprovado para este projeto.")
else:
    style_name = st.text_input("Descrição do estilo visual", placeholder="Ex.: ilustração infantil 3D suave, cores pastel, iluminação cinematográfica delicada")
    if st.button("🎨 Aprovar estilo visual", use_container_width=True, disabled=not style_name.strip()):
        approve_style(plan, {"name": style_name, "approved_by_author": True})
        st.rerun()

plan = load_visual_plan(plan_id)
status = visual_preflight_status(plan)
section_title("6 · Liberação do Diretor de Cena", "O Orquestrador só libera A/B/C quando tudo que define o universo visual já passou por você.", "Gate")
cols = st.columns(4)
cols[0].metric("História", "✅" if status["story_approved"] else "⏳")
cols[1].metric("Personagens", "✅" if not status["missing_characters"] else f"⏳ {len(status['missing_characters'])}")
cols[2].metric("Cenários", "✅" if not status["missing_locations"] else f"⏳ {len(status['missing_locations'])}")
cols[3].metric("Estilo", "✅" if status["style_approved"] else "⏳")

if status["ready_for_scene_generation"]:
    st.success("🎬 PRONTO: o Diretor de Cena pode preparar opções A/B/C sem reinventar personagens, cenários ou estilo.")
else:
    st.warning("🎬 BLOQUEADO: conclua os checkpoints acima. Isso evita gerar dezenas de imagens antes de você gostar do universo visual.")

section_title("7 · Controle de custo antes do lote", "Teste a regra que o Orquestrador aplicará antes de uma geração paga.", "Cost Gate")
estimate = st.number_input("Estimativa do próximo lote (US$)", min_value=0.0, value=0.0, step=0.10)
paid = st.checkbox("Este lote usa provedor pago", value=True)
gate = cost_gate(plan, estimate, paid)
if gate["over_budget"]:
    st.error("🚨 O lote ultrapassa o limite definido. O Orquestrador deve parar e pedir sua autorização.")
elif gate["requires_author_confirmation"]:
    st.warning(f"👀 Confirmação necessária antes de gastar aproximadamente US$ {gate['estimated_usd']:.2f}.")
else:
    st.success("🆓 Esta operação pode seguir sem cobrança direta, dentro do orçamento configurado.")

section_title("8 · Element Lock — altere somente o que você quiser", "Exemplo: trocar apenas o cenário de uma página preservando personagens, pose, roupa, expressão e estilo.", "Edição localizada")
change = st.text_input("Pedido de alteração", placeholder="Troque somente o jardim da página 14 por um jardim com flores amarelas")
keys = ["characters", "pose_composition", "expressions", "wardrobe", "style", "scenario", "lighting", "text"]
unlock_labels = {
    "characters": "👤 Personagens",
    "pose_composition": "🧍 Pose/composição",
    "expressions": "😊 Expressões",
    "wardrobe": "👗 Roupa",
    "style": "🎨 Estilo",
    "scenario": "🌳 Cenário",
    "lighting": "💡 Iluminação",
    "text": "🔤 Texto",
}
unlock = st.multiselect("O que pode mudar? Todo o restante fica bloqueado.", keys, default=["scenario"], format_func=lambda x: unlock_labels[x])
if change and unlock:
    contract = scenario_only_instruction(change) if unlock == ["scenario"] else build_element_lock_instruction(change, unlock=unlock)
    st.code(contract["instruction"], language="text")
    st.caption("🔒 Este contrato é provider-neutral. Quando conectado ao gerador/editor de imagem, deve ser enviado junto às referências e/ou máscara suportadas pelo provedor.")

st.divider()
st.markdown("### 🤖 Atalhos do Orquestrador")
a, b, c = st.columns(3)
a.page_link("pages/14_👥_Character_Universe.py", label="👥 Character Universe", use_container_width=True)
b.page_link("pages/19_✨_Restoration_Studio.py", label="✨ Restaurar imagem/página", use_container_width=True)
c.page_link("pages/11_🛡️_Custos_e_Seguranca.py", label="🛡️ Custos & Segurança", use_container_width=True)

st.caption("FaithBloom Orchestrator · Visual approval gates · o original e os Masters oficiais permanecem sob aprovação humana.")

import os
from pathlib import Path
import streamlit as st

from estilo import aplicar_estilo, hero
from book_doctor import listar_projetos
from character_universe import listar_personagens_oficiais, carregar_personagem_oficial
from style_dna import listar_styles, carregar_style
from restoration_studio import (
    carregar_plano_restauracao,
    vincular_character,
    vincular_style,
    salvar_vinculos,
    registrar_decisao,
    montar_prompt_restauracao,
    gerar_variacao_ia,
    aprovar_versao,
)
from editorial_visual_handoff import contexto_cena_para_asset

st.set_page_config(page_title="Visual Remaster Workbench", page_icon="🖼️", layout="wide")
aplicar_estilo()
hero(
    "🖼️ Visual Remaster Workbench",
    "Reilustre páginas antigas usando o texto revisado, a psicologia das cores e os Character Masters oficiais — sempre como nova versão derivada.",
)
st.info("🔒 O original nunca é sobrescrito. Toda geração nasce como candidata e precisa ser aprovada antes do Quality Gate.")

projects = []
for project in listar_projetos():
    if project.get("tipo_projeto") != "story":
        continue
    plan = carregar_plano_restauracao(project)
    if plan.get("editorial_remaster_handoff"):
        projects.append(project)

if not projects:
    st.warning("Nenhum projeto possui handoff editorial visual preparado.")
    st.page_link("pages/47_🎨_Handoff_Visual_Remaster.py", label="🎨 Preparar Handoff Visual →", use_container_width=True)
    st.stop()

labels = [f"{p.get('titulo','Sem título')} · {p.get('id')}" for p in projects]
pidx = st.selectbox("Projeto", range(len(projects)), format_func=lambda i: labels[i])
project = projects[pidx]
plan = carregar_plano_restauracao(project)

assets = [a for a in plan.get("assets_detectados") or [] if a.get("arquivo") and Path(a.get("arquivo")).exists()]
if not assets:
    st.warning("Não há imagens extraídas disponíveis. Rode a auditoria completa no Book Doctor.")
    st.page_link("pages/16_🩺_Book_Doctor.py", label="🩺 Abrir Book Doctor →", use_container_width=True)
    st.stop()

asset_idx = st.selectbox(
    "Página / asset",
    range(len(assets)),
    format_func=lambda i: f"{assets[i].get('id')} · página {assets[i].get('pagina') or '—'}",
)
asset = assets[asset_idx]
origin = asset["arquivo"]
context = contexto_cena_para_asset(plan, asset.get("pagina"))

left, right = st.columns(2)
with left:
    st.markdown("#### 🔒 Original")
    st.image(origin, use_container_width=True)
with right:
    st.markdown("#### 📖 Contexto editorial revisado")
    if context:
        st.write(context.get("texto_revisado", ""))
        st.caption(
            f"Emoção: {context.get('emocao') or '—'} · intensidade {context.get('intensidade_emocional') or '—'} · "
            f"expressão: {context.get('expressao') or '—'}"
        )
        direction = context.get("direcao_cor") or {}
        if direction:
            st.write("🎨 Direção cromática:", direction.get("cor_principal") or direction.get("emocao_cromatica_base") or "confirmada")
    else:
        st.warning("Este asset não possui cena revisada associada. Não gere nova arte sem conferir o mapeamento.")

collection = project.get("colecao") or plan.get("colecao") or ""
characters = listar_personagens_oficiais(collection or None)
style_cards = listar_styles(collection or None)
styles = []
inactive_styles = []
for card in style_cards:
    style = carregar_style(card.get("id", ""))
    if not style:
        continue
    usos = style.get("usos_permitidos") or []
    if not usos or "story" in usos:
        styles.append(style)
    else:
        inactive_styles.append(style)

st.markdown("### 1 · Identidade oficial")
char_options = ["— selecione —"] + [f"{x.get('nome')} · {x.get('id')}" for x in characters]
char_idx = st.selectbox("Character Master principal desta intervenção", range(len(char_options)), format_func=lambda i: char_options[i])
character_id = "" if char_idx == 0 else characters[char_idx - 1]["id"]

if not styles:
    if inactive_styles:
        st.warning(
            "🎨 Existe Style DNA nesta coleção, mas ele está **inativo para Story / Remaster**. "
            "Ative o uso `story` no Style DNA Lab antes de gerar novas ilustrações para que a linguagem visual da coleção entre no prompt protegido."
        )
    else:
        st.warning(
            "🎨 Esta coleção ainda não possui Style DNA ativo para Story / Remaster. "
            "Crie ou vincule um Style DNA oficial antes da geração visual para preservar a linguagem da coleção."
        )
    st.page_link("pages/18_🎨_Style_DNA_Lab.py", label="🎨 Abrir Style DNA Lab →", use_container_width=True)
    style_id = ""
elif len(styles) == 1:
    style_id = styles[0]["id"]
    st.success(f"🎨 Style DNA ativo detectado automaticamente: **{styles[0].get('nome','')}**")
    st.caption("Ele será usado no contexto Story/Remaster. O Style DNA não substitui Character DNA nem Color Master.")
else:
    style_options = [f"{x.get('nome')} · {x.get('id')}" for x in styles]
    style_idx = st.selectbox("Style DNA ativo para Story / Remaster", range(len(style_options)), format_func=lambda i: style_options[i])
    style_id = styles[style_idx]["id"]

if character_id and st.button("🔗 Vincular Character Master ao projeto"):
    plan = vincular_character(plan, character_id)
    plan = salvar_vinculos(project, plan)
    st.success("Character Master vinculado sem alterar o DNA.")
if style_id and st.button("🔗 Vincular Style DNA ao projeto"):
    plan = vincular_style(plan, style_id)
    plan = salvar_vinculos(project, plan)
    st.success("Style DNA ativo para Story/Remaster vinculado ao projeto.")

st.markdown("### 2 · Intervenção")
action = st.radio(
    "Ação visual",
    ["corrigir_personagem", "reilustrar", "manter_original"],
    format_func=lambda x: {
        "corrigir_personagem": "👤 Corrigir somente personagem",
        "reilustrar": "🎨 Reilustrar a cena",
        "manter_original": "🔒 Manter a arte original",
    }[x],
    horizontal=True,
)

if action == "manter_original":
    if st.button("🔒 Confirmar: manter esta arte", type="primary"):
        registrar_decisao(project, asset["id"], "manter_original", character_id, style_id, metadata={"editorial_remaster": True})
        st.success("Decisão registrada. Esta página está resolvida sem alterar o original.")
        st.rerun()
else:
    if not context:
        st.error("Handoff editorial ausente para esta página. Corrija o mapeamento antes de gerar.")
        st.stop()
    if not character_id:
        st.warning("Selecione o Character Master oficial antes de gerar a intervenção visual.")
    if not style_id:
        st.error("Style DNA ativo para Story / Remaster é obrigatório para gerar nova arte neste fluxo. Ative-o no Style DNA Lab.")

    author_instruction = st.text_area(
        "Instrução adicional — opcional",
        value=(
            "Preserve a composição e a intenção narrativa da página. Use o Character Master oficial para corrigir a identidade do personagem. "
            "Não insira texto na ilustração."
        ),
        height=110,
    )
    scene_instruction = (
        f"TEXTO REVISADO DA CENA: {context.get('texto_revisado','')}\n"
        f"CONTEXTO VISUAL: {context.get('contexto_visual','')}\n"
        f"FIGURINO: {context.get('figurino','')}\n"
        f"EXPRESSÃO: {context.get('expressao','')}\n"
        f"TRANSIÇÃO EMOCIONAL: {context.get('transicao_emocional','')}\n"
        f"DIREÇÃO DE COR JÁ APROVADA: {context.get('direcao_cor',{})}\n"
        f"PEDIDO DA AUTORA: {author_instruction}"
    )
    variables = {
        k: v for k, v in {
            "expressao": context.get("expressao", ""),
            "figurino": context.get("figurino", ""),
            "cenario": context.get("contexto_visual", ""),
        }.items() if str(v or "").strip()
    }
    prompt = montar_prompt_restauracao(
        action,
        character_id=character_id,
        style_id=style_id,
        contexto="story",
        variaveis=variables,
        emocao=context.get("emocao", ""),
        instrucao_autora=scene_instruction,
    )
    st.markdown("#### Prompt protegido")
    st.code(prompt, language=None)

    refs = []
    if character_id:
        character = carregar_personagem_oficial(character_id)
        master = character.get("color_master") or character.get("line_art_master")
        if master and Path(master).exists():
            refs.append(master)
            st.success("🧬 O Color Master oficial será enviado como referência visual.")
        else:
            st.error("O personagem selecionado não possui Master visual acessível nesta sessão. Geração bloqueada para evitar regressão de identidade.")

    if st.button("📝 Salvar plano sem gerar imagem"):
        registrar_decisao(project, asset["id"], action, character_id, style_id, scene_instruction, {"prompt": prompt, "editorial_remaster": True})
        st.success("Plano registrado sem consumo de créditos.")

    can_generate = bool(os.environ.get("OPENROUTER_API_KEY")) and bool(character_id) and bool(refs) and bool(style_id)
    if can_generate:
        st.warning("A próxima ação chama o modelo de imagem e pode consumir créditos. A candidata não será aprovada automaticamente.")
        if st.button("✨ Gerar candidata Remastered", type="primary"):
            from openrouter_client import gerar_imagem
            registrar_decisao(project, asset["id"], action, character_id, style_id, scene_instruction, {"prompt": prompt, "editorial_remaster": True})
            with st.spinner("Gerando candidata Remastered…"):
                out = gerar_variacao_ia(project, origin, prompt, gerar_imagem, action, refs)
            st.session_state[f"remaster_candidate_{project.get('id')}_{asset.get('id')}"] = out
            st.success("Candidata gerada. Compare e aprove somente se estiver correta.")
            st.rerun()
    else:
        st.caption("Geração disponível somente com OpenRouter configurado, Character Master visual válido e Style DNA ativo para Story/Remaster.")

plan = carregar_plano_restauracao(project)
derivatives = [v for v in plan.get("versoes_assets") or [] if v.get("origem") == origin and Path(v.get("derivado", "")).exists()]
if derivatives:
    latest = derivatives[-1]
    st.markdown("### 3 · Comparação e aprovação")
    a, b = st.columns(2)
    a.image(origin, caption="Original", use_container_width=True)
    b.image(latest["derivado"], caption=f"Remastered · {latest.get('operacao')}", use_container_width=True)
    if latest.get("aprovada"):
        st.success("✅ Esta versão já está aprovada.")
    elif st.button("✅ Aprovar esta versão Remastered", type="primary"):
        aprovar_versao(project, latest["id"])
        st.success("Versão visual aprovada. O original continua preservado.")
        st.rerun()

st.markdown("### 4 · Próximo gate")
st.page_link("pages/50_🛡️_QA_Final_Remaster.py", label="🛡️ Ver pendências / QA Final Remaster →", use_container_width=True)

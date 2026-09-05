"""FaithBloom — Biblioteca Oficial, Character Guide, Looks, Scene Director e Galeria."""
from __future__ import annotations

from copy import deepcopy

import streamlit as st

from asset_library import get_asset, get_thumbnail, list_assets, set_archived, update_asset
from character_guide import (
    MASTER_STATUS, USAGE_LABELS, VARIATION_STATUS, approve_asset_as_variation,
    build_character_free_prompt, build_neutral_base_prompt, character_identity_summary,
    delete_look, generate_character_variations, generate_scene_assets, list_looks,
    save_look, suggest_scene_concepts, create_character_guide,
    update_character_guide, select_gallery_asset,
)
from character_universe import carregar_personagem_oficial, listar_personagens_oficiais
from estilo import aplicar_estilo, hero, section_title

st.set_page_config(page_title="Personagens & Galeria", page_icon="👤", layout="wide")
aplicar_estilo()
hero(
    "👤 Personagens & Galeria",
    "Seu Character Guide reutilizável: identidade oficial, Looks, direção de cena, prompt livre e assets aprovados.",
    "FaithBloom · personagens consistentes para histórias, colorir, atividades, capas e materiais futuros",
)


def _load_official() -> list[dict]:
    out = []
    for item in listar_personagens_oficiais():
        p = carregar_personagem_oficial(item["id"])
        if p:
            out.append(p)
    return out


def _char_label(p: dict) -> str:
    return f"{p.get('colecao','Sem coleção')} · {p.get('nome','Personagem')}"


def _preview_asset(item: dict, width: int | None = None):
    thumb = get_thumbnail(item["id"], 520)
    if thumb:
        st.image(thumb, width=width if width else "stretch")
        return
    full = get_asset(item["id"])
    if full and full.get("caminho_arquivo"):
        st.image(full["caminho_arquivo"], width=width if width else "stretch")
    else:
        st.info("Preview indisponível.")


def _usage_selector(key: str, default: str = "story") -> str:
    options = list(USAGE_LABELS)
    idx = options.index(default) if default in options else 0
    return st.selectbox("Uso pretendido", options, index=idx, format_func=lambda x: USAGE_LABELS[x], key=key)


def _show_result_cards(result_ids: list[str], *, key_prefix: str, allow_master_review: bool = False):
    items = [get_asset(aid) for aid in result_ids]
    items = [x for x in items if x]
    if not items:
        return
    st.markdown("### Resultados")
    cols = st.columns(min(3, len(items)))
    for i, item in enumerate(items):
        with cols[i % len(cols)]:
            with st.container(border=True):
                _preview_asset(item)
                st.markdown(f"**{item.get('nome','Asset')}**")
                st.caption(f"{item.get('visual_status','CANDIDATE')} · ID {item.get('id','')[:8]} · {item.get('version_label','')}")
                new_name = st.text_input("Nome visível", value=item.get("nome", ""), key=f"{key_prefix}_rename_{item['id']}")
                if st.button("✏️ Renomear", key=f"{key_prefix}_rename_btn_{item['id']}", use_container_width=True):
                    update_asset(item["id"], nome=new_name.strip() or item.get("nome", "Asset"))
                    st.success("Nome atualizado; o ID interno não mudou.")
                    st.rerun()

                status = item.get("visual_status")
                if status in {VARIATION_STATUS, MASTER_STATUS, "RESTORATION_CANDIDATE"}:
                    if st.button("✅ Aprovar como variação", key=f"{key_prefix}_approve_{item['id']}", type="primary", use_container_width=True):
                        approve_asset_as_variation(item["id"])
                        st.success("Aprovada no mesmo asset. Não virou Master.")
                        st.rerun()
                elif status == "APPROVED_VARIATION":
                    st.success("✅ APPROVED_VARIATION")

                a, b = st.columns(2)
                if a.button("🔄 Variar", key=f"{key_prefix}_vary_{item['id']}", use_container_width=True):
                    st.session_state["guide_variation_base_id"] = item["id"]
                    st.info("Asset preparado como base. Abra ✍️ Prompt Livre & Variações e ajuste o pedido.")
                if b.button("🖍️ Line Art", key=f"{key_prefix}_line_{item['id']}", use_container_width=True):
                    full = get_asset(item["id"])
                    st.session_state["faithbloom_selected_asset_id"] = item["id"]
                    st.session_state["faithbloom_selected_asset_path"] = (full or {}).get("caminho_arquivo", "")
                    st.switch_page("pages/20_🖍️_Coloring_Book_Doctor.py")

                c, d = st.columns(2)
                if c.button("👁️ Asset Library", key=f"{key_prefix}_detail_{item['id']}", use_container_width=True):
                    st.session_state["asset_library_detail"] = item["id"]
                    st.session_state["faithbloom_selected_asset_id"] = item["id"]
                    st.switch_page("pages/31_🖼️_Asset_Library_Media_Manager.py")
                if d.button("🗄️ Arquivar", key=f"{key_prefix}_archive_{item['id']}", use_container_width=True):
                    set_archived(item["id"], True)
                    st.success("✅ Asset arquivado. O arquivo e o histórico foram preservados.")
                    st.rerun()

                if allow_master_review and item.get("approved"):
                    if st.button("⭐ Revisar para Master", key=f"{key_prefix}_master_{item['id']}", use_container_width=True):
                        st.session_state["faithbloom_selected_asset_id"] = item["id"]
                        full = get_asset(item["id"])
                        st.session_state["faithbloom_selected_asset_path"] = (full or {}).get("caminho_arquivo", "")
                        st.switch_page("pages/14_👥_Character_Universe.py")


characters = _load_official()
char_by_id = {p["id"]: p for p in characters}

tabs = st.tabs([
    "👥 Biblioteca Oficial", "🧬 Character Guide & Looks", "🎬 Scene Director",
    "✍️ Prompt Livre & Variações", "🖼️ Galeria de Imagens",
])

with tabs[0]:
    section_title(
        "Biblioteca oficial de personagens",
        "Aqui entram os personagens do Character Universe. Uma personagem é a identidade; as imagens são representações reutilizáveis dela.",
        "Fonte única de verdade",
    )
    if not characters:
        st.info("Ainda não existem personagens oficiais no Character Universe.")
        st.page_link("pages/14_👥_Character_Universe.py", label="➕ Criar primeiro personagem oficial", use_container_width=True)
    else:
        collections = sorted({p.get("colecao", "") for p in characters if p.get("colecao")})
        selected_collection = st.selectbox("Coleção", ["Todas", *collections], key="guide_library_collection")
        shown = characters if selected_collection == "Todas" else [p for p in characters if p.get("colecao") == selected_collection]
        cols = st.columns(3)
        for i, p in enumerate(shown):
            with cols[i % 3]:
                with st.container(border=True):
                    preview = p.get("color_master") or ""
                    if not preview and p.get("reference_pack"):
                        preview = p["reference_pack"][0].get("asset") or ""
                    if preview:
                        try:
                            st.image(preview, use_container_width=True)
                        except Exception:
                            pass
                    st.markdown(f"### {p.get('nome')}")
                    st.caption(p.get("colecao", ""))
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Color", "✓" if p.get("color_master") else "—")
                    m2.metric("Line", "✓" if p.get("line_art_master") else "—")
                    m3.metric("Refs", len(p.get("reference_pack") or []))
                    m4.metric("Looks", len(list_looks(p)))
                    summary = character_identity_summary(p)
                    if summary["descricao"]:
                        st.write(summary["descricao"])
                    st.caption("🔒 Identity Lock ativo · roupas/acessórios/pose/cenário só mudam quando autorizados.")
                    if st.button("🧬 Abrir Guide", key=f"open_guide_{p['id']}", use_container_width=True):
                        st.session_state["guide_character_id"] = p["id"]
                        st.info("Personagem selecionado. Abra a aba 🧬 Character Guide & Looks.")
        st.caption("APPROVED_VARIATION significa ‘imagem boa e preservada’. Origem em um livro não impede reutilização futura; uso, tema e estação ficam como metadados/tags.")

with tabs[1]:
    section_title(
        "Character Guide",
        "Separe identidade permanente de figurino, acessórios e contexto. Crie uma base neutra e Looks sazonais sem engessar a personagem.",
        "Guide profissional",
    )
    st.info("Personagem = identidade canônica. Assets = imagens/referências/variações desse personagem.")
    action = st.radio("Ação", ["Consultar Guide", "➕ Novo personagem", "✏️ Editar Character Guide atual"], horizontal=True, key="guide_crud_action")
    editing = action.startswith("✏️") and bool(characters)
    if action.startswith("➕") or editing:
        current_edit = None
        if editing:
            edit_ids = [x["id"] for x in characters]
            edit_id = st.selectbox("Personagem para editar", edit_ids, format_func=lambda x: _char_label(char_by_id[x]), key="guide_edit_id")
            current_edit = carregar_personagem_oficial(edit_id)
        defaults = (current_edit or {}).get("dna", {}).get("campos_bloqueados", {})
        with st.form("character_guide_crud_form"):
            name = st.text_input("Nome", value=(current_edit or {}).get("nome", ""))
            collection = st.text_input("Coleção", value=(current_edit or {}).get("colecao", ""))
            c_a, c_b = st.columns(2)
            species = c_a.text_input("Espécie / tipo", value=defaults.get("especie", ""))
            eyes = c_b.text_input("Olhos", value=defaults.get("olhos", ""))
            palette = c_a.text_input("Paleta base / pelagem / pele", value=defaults.get("paleta_base", ""))
            face = c_b.text_input("Rosto", value=defaults.get("rosto", ""))
            hair = c_a.text_input("Cabelo (quando aplicável)", value=defaults.get("cabelo", ""))
            proportions = c_b.text_input("Proporções", value=defaults.get("proporcoes", ""))
            marks = st.text_input("Marcas permanentes", value=defaults.get("marcas_permanentes", ""))
            description = st.text_area("Descrição master", value=(current_edit or {}).get("dna", {}).get("descricao_master", ""))
            controlled_names = ["pose", "acao", "expressao", "emocao", "figurino", "acessorios_temporarios", "cenario", "estacao", "festividade"]
            controlled = st.multiselect("Variáveis controladas", controlled_names, default=(current_edit or {}).get("dna", {}).get("variaveis_permitidas", controlled_names))
            usages = st.multiselect("Usos", list(USAGE_LABELS), default=(current_edit or {}).get("metadata", {}).get("usos_permitidos", list(USAGE_LABELS)), format_func=lambda x: USAGE_LABELS[x])
            submitted = st.form_submit_button("💾 Salvar Character Guide", type="primary", disabled=not name.strip() or not collection.strip())
        if submitted:
            locked = {"especie": species, "olhos": eyes, "paleta_base": palette, "rosto": face, "cabelo": hair, "proporcoes": proportions, "marcas_permanentes": marks}
            try:
                if editing:
                    saved = update_character_guide(edit_id, collection=collection, name=name, locked_identity=locked, description=description, controlled_variables={x: True for x in controlled}, usages=usages)
                else:
                    saved = create_character_guide(collection=collection, name=name, locked_identity=locked, description=description, controlled_variables={x: True for x in controlled}, usages=usages)
                st.session_state["guide_character_id"] = saved["id"]
                st.success("Character Guide salvo no Character Universe. O personagem já pode receber Looks.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível salvar o Character Guide: {exc}")
    elif not characters:
        st.info("Use ➕ Novo personagem para cadastrar o primeiro Character Guide.")
    else:
        default_id = st.session_state.get("guide_character_id")
        ids = [p["id"] for p in characters]
        default_index = ids.index(default_id) if default_id in ids else 0
        pid = st.selectbox("Personagem", ids, index=default_index, format_func=lambda x: _char_label(char_by_id[x]), key="guide_char")
        p = carregar_personagem_oficial(pid)
        summary = character_identity_summary(p)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 🔒 Locked — não muda")
            if summary["locked"]:
                for k, v in summary["locked"].items():
                    st.write(f"**{k.replace('_',' ').title()}:** {v}")
            elif summary["descricao"]:
                st.write(summary["descricao"])
            else:
                st.caption("DNA ainda sem campos estruturados.")
        with c2:
            st.markdown("#### ⚙️ Variável controlada")
            st.write(", ".join(summary["controlled"]) or "—")
            st.caption("Só muda quando a autora pede ou escolhe um Look.")
        with c3:
            st.markdown("#### 🎨 Variável de cena")
            st.write(", ".join(summary["scene_free"]) or "cenário, pose, ação, emoção, iluminação")
            st.caption("Cores emocionais atuam no ambiente/luz, nunca na identidade canônica.")

        st.divider()
        st.markdown("### 👗 Looks salvos")
        looks = list_looks(p)
        if looks:
            lcols = st.columns(min(3, len(looks)))
            for i, look in enumerate(looks):
                with lcols[i % len(lcols)]:
                    with st.container(border=True):
                        st.markdown(f"**{look.get('nome')}**")
                        details = [
                            f"Figurino: {look.get('figurino')}" if look.get("figurino") else "",
                            f"Acessórios: {look.get('acessorios_temporarios')}" if look.get("acessorios_temporarios") else "",
                            f"Estação: {look.get('estacao')}" if look.get("estacao") else "",
                            f"Tema: {look.get('festividade')}" if look.get("festividade") else "",
                        ]
                        st.caption(" · ".join(x for x in details if x) or "Look reutilizável")
                        if st.button("🗑️ Remover Look", key=f"delete_look_{pid}_{look.get('id')}", use_container_width=True):
                            delete_look(pid, look.get("id"))
                            st.rerun()
        else:
            st.caption("Ainda não existem Looks salvos para este personagem.")

        with st.expander("➕ Criar / atualizar Look", expanded=not bool(looks)):
            ln = st.text_input("Nome do Look", placeholder="Natal — Inverno", key=f"look_name_{pid}")
            q1, q2 = st.columns(2)
            lf = q1.text_input("Figurino", placeholder="vestido vermelho de inverno", key=f"look_outfit_{pid}")
            la = q2.text_input("Acessórios", placeholder="cachecol vermelho, laço vermelho", key=f"look_acc_{pid}")
            q3, q4, q5 = st.columns(3)
            ls = q3.text_input("Estação", placeholder="Inverno", key=f"look_season_{pid}")
            lfest = q4.text_input("Tema/festividade", placeholder="Natal", key=f"look_fest_{pid}")
            lem = q5.text_input("Emoção-base opcional", placeholder="alegre", key=f"look_emotion_{pid}")
            lc = st.text_input("Cenário sugerido opcional", placeholder="rua nevada com luzes quentes", key=f"look_scene_{pid}")
            lobs = st.text_area("Observações", placeholder="Pode usar em histórias, capas e marketing...", key=f"look_obs_{pid}")
            lusos = st.multiselect("Usos", list(USAGE_LABELS), format_func=lambda x: USAGE_LABELS[x], key=f"look_usages_{pid}")
            if st.button("💾 Salvar Look", type="primary", disabled=not ln.strip(), key=f"save_look_{pid}"):
                save_look(pid, ln, figurino=lf, acessorios_temporarios=la, estacao=ls, festividade=lfest, emocao=lem, cenario=lc, observacoes=lobs, usos=lusos)
                st.success("Look salvo sem alterar o Character DNA.")
                st.rerun()

        st.divider()
        st.markdown("### 🧍 Base oficial neutra")
        st.caption("Gere uma referência limpa de corpo inteiro/fundo neutro. A saída nasce como MASTER_CANDIDATE e só vira Master por decisão humana no Character Universe.")
        neutral_qty = st.radio("Quantidade", [1, 3], horizontal=True, format_func=lambda n: "1 candidata" if n == 1 else "A/B/C", key=f"neutral_qty_{pid}")
        with st.expander("Ver prompt protegido"):
            st.code(build_neutral_base_prompt(p), language=None)
        if st.button("✨ Criar Base Neutra candidata", type="primary", key=f"neutral_generate_{pid}"):
            with st.spinner("Gerando base neutra com Identity Lock..."):
                results = generate_character_variations(p, build_neutral_base_prompt(p), quantity=neutral_qty, usage="story", neutral_base=True, metadata={"purpose": "neutral_official_base"})
            st.session_state[f"neutral_results_{pid}"] = [x["id"] for x in results]
            st.rerun()
        _show_result_cards(st.session_state.get(f"neutral_results_{pid}", []), key_prefix=f"neutral_{pid}", allow_master_review=True)
        st.page_link("pages/14_👥_Character_Universe.py", label="👥 Abrir Character Universe / Masters", use_container_width=True)

with tabs[2]:
    section_title(
        "Scene Director — trecho da história → 3 direções visuais",
        "Cole uma frase ou parágrafo. Primeiro a IA sugere cenário, pose, emoção, paleta e câmera; nenhuma imagem é gerada até você escolher.",
        "Direção de arte antes da geração",
    )
    if not characters:
        st.info("Cadastre personagens oficiais primeiro.")
    else:
        ids = [p["id"] for p in characters]
        selected_ids = st.multiselect("Personagens presentes na cena", ids, format_func=lambda x: _char_label(char_by_id[x]), key="scene_characters")
        excerpt = st.text_area("Trecho da história", height=140, placeholder="Ex.: Mel se sentou perto do vaso e cochichou: ‘Sementinha… você já pode sair.’", key="scene_excerpt")
        if st.button("🎬 Gerar 3 ideias de cenário e pose", type="primary", disabled=not selected_ids or not excerpt.strip()):
            with st.spinner("O Scene Director está criando 3 direções — sem gerar imagens..."):
                selected_chars = [carregar_personagem_oficial(x) for x in selected_ids]
                ideas = suggest_scene_concepts(excerpt, selected_chars, count=3)
            st.session_state["scene_director_ideas"] = ideas
            st.session_state["scene_director_character_ids"] = selected_ids
            st.session_state["scene_director_excerpt"] = excerpt
            st.rerun()

        ideas = st.session_state.get("scene_director_ideas") or []
        if ideas:
            st.markdown("### 3 ideias — escolha antes de gastar geração de imagem")
            cols = st.columns(3)
            for i, idea in enumerate(ideas):
                with cols[i]:
                    with st.container(border=True):
                        st.markdown(f"### {idea.get('id')} · {idea.get('titulo')}")
                        st.write(f"**Cenário:** {idea.get('cenario')}")
                        st.write(f"**Ação:** {idea.get('acao')}")
                        st.write(f"**Poses:** {idea.get('poses')}")
                        st.write(f"**Emoção:** {idea.get('emocao')}")
                        st.write(f"**Cores:** {idea.get('psicologia_cores')}")
                        st.write(f"**Luz:** {idea.get('iluminacao')}")
                        st.write(f"**Câmera:** {idea.get('camera')}")
                        if idea.get("figurino_acessorios"):
                            st.write(f"**Figurino/acessórios:** {idea.get('figurino_acessorios')}")
                        if idea.get("por_que_funciona"):
                            st.caption(idea.get("por_que_funciona"))

            option_ids = [idea.get("id") for idea in ideas]
            chosen_id = st.radio("Direção escolhida", option_ids, horizontal=True, key="scene_chosen_idea")
            chosen = deepcopy(next(x for x in ideas if x.get("id") == chosen_id))
            adjustment = st.text_area("Ajustar / combinar ideias (opcional)", placeholder="Ex.: use o cenário da A, a pose da C e a iluminação da B; mantenha Manu de vestido amarelo.", key="scene_adjustment")
            st.caption("Você pode combinar elementos das três opções aqui antes de gerar.")
            usage = _usage_selector("scene_usage", "story")
            qty = st.radio("Resultados de imagem", [1, 3], horizontal=True, format_func=lambda n: "1 imagem" if n == 1 else "A/B/C", key="scene_qty")
            base_candidates = list_assets({"media_kind": "image"}, page_size=100).get("items", [])
            base_opts = [""] + [x["id"] for x in base_candidates]
            base_map = {x["id"]: x for x in base_candidates}
            base_id = st.selectbox("Variar a partir de uma imagem/cena existente? (opcional)", base_opts, format_func=lambda x: "— Começar pela direção escolhida —" if not x else f"{base_map[x].get('nome')} · {x[:8]}", key="scene_base_asset")
            if st.button("🎨 Gerar imagem da direção escolhida", type="primary", key="scene_generate_image"):
                current_ids = st.session_state.get("scene_director_character_ids") or selected_ids
                selected_chars = [carregar_personagem_oficial(x) for x in current_ids]
                with st.spinner("Gerando somente agora, com Identity Lock dos personagens..."):
                    results = generate_scene_assets(chosen, selected_chars, quantity=qty, usage=usage, adjustment=adjustment, base_asset_id=base_id, story_excerpt=st.session_state.get("scene_director_excerpt", excerpt))
                st.session_state["scene_generated_results"] = [x["id"] for x in results]
                st.rerun()
            _show_result_cards(st.session_state.get("scene_generated_results", []), key_prefix="scene")

with tabs[3]:
    section_title(
        "Prompt Livre & Variações",
        "Diga exatamente o que quer mudar. O FaithBloom injeta o Identity Lock automaticamente e preserva tudo que você não autorizou alterar.",
        "Liberdade criativa com consistência",
    )
    if not characters:
        st.info("Cadastre personagens oficiais primeiro.")
    else:
        ids = [p["id"] for p in characters]
        selected_ids = st.multiselect("Personagem(ns)", ids, format_func=lambda x: _char_label(char_by_id[x]), key="free_characters")
        selected_chars = [carregar_personagem_oficial(x) for x in selected_ids]
        chosen_look = None
        if len(selected_chars) == 1:
            looks = list_looks(selected_chars[0])
            look_opts = [""] + [x["id"] for x in looks]
            look_map = {x["id"]: x for x in looks}
            look_id = st.selectbox("Look salvo (opcional)", look_opts, format_func=lambda x: "— Sem Look —" if not x else look_map[x].get("nome", "Look"), key="free_look")
            chosen_look = look_map.get(look_id) if look_id else None
            if chosen_look:
                st.caption(f"Look: {chosen_look.get('figurino','')} · {chosen_look.get('acessorios_temporarios','')} · {chosen_look.get('estacao','')} · {chosen_look.get('festividade','')}")

        f1, f2, f3 = st.columns(3)
        pose = f1.text_input("Pose", placeholder="sentada olhando o vaso", key="free_pose")
        emotion = f2.text_input("Emoção", placeholder="curiosa e esperançosa", key="free_emotion")
        season = f3.text_input("Estação/tema", placeholder="primavera", key="free_season")
        f4, f5 = st.columns(2)
        outfit = f4.text_input("Roupa/figurino", placeholder="vestido amarelo", key="free_outfit")
        accessories = f5.text_input("Acessórios", placeholder="chapéu de palha, óculos...", key="free_accessories")
        scenario = st.text_input("Cenário", placeholder="jardim de primavera ao amanhecer", key="free_scenario")
        request = st.text_area("Prompt livre", height=130, placeholder="Ex.: Quero a mesma Manu, preservando exatamente o rosto, com chapéu de palha e uma cesta de flores.", key="free_prompt")
        usage = _usage_selector("free_usage", "story")
        qty = st.radio("Quantidade", [1, 3], horizontal=True, format_func=lambda n: "1 versão" if n == 1 else "A/B/C", key="free_qty")

        prepared_base = st.session_state.get("guide_variation_base_id", "")
        q = " ".join(p.get("nome", "") for p in selected_chars).strip()
        asset_result = list_assets({"media_kind": "image", "q": q} if q else {"media_kind": "image"}, page_size=100)
        bases = asset_result.get("items", [])
        base_map = {x["id"]: x for x in bases}
        base_ids = [""] + list(base_map)
        base_index = base_ids.index(prepared_base) if prepared_base in base_ids else 0
        base_id = st.selectbox("Imagem-base para variar (opcional)", base_ids, index=base_index, format_func=lambda x: "— Usar Character Guide/References —" if not x else f"{base_map[x].get('nome')} · {x[:8]}", key="free_base")
        if prepared_base:
            st.caption("🔄 Uma imagem foi preparada pelo botão Variar. Você pode trocar ou remover a base.")

        save_as_look = False
        look_name = ""
        if len(selected_chars) == 1:
            save_as_look = st.checkbox("💾 Salvar este figurino/contexto como Look reutilizável", key="free_save_look")
            if save_as_look:
                look_name = st.text_input("Nome do novo Look", placeholder="Primavera — Jardim", key="free_look_name")

        if st.button("✨ Gerar variação com Identity Lock", type="primary", disabled=not selected_chars or not request.strip(), key="free_generate"):
            variables = {"pose": pose, "emocao": emotion, "estacao": season, "figurino": outfit, "acessorios_temporarios": accessories, "cenario": scenario}
            if len(selected_chars) == 1:
                p = selected_chars[0]
                prompt = build_character_free_prompt(p, request, usage=usage, variables=variables, look=chosen_look)
                if save_as_look and look_name.strip():
                    save_look(p["id"], look_name.strip(), figurino=outfit or (chosen_look or {}).get("figurino",""), acessorios_temporarios=accessories or (chosen_look or {}).get("acessorios_temporarios",""), estacao=season or (chosen_look or {}).get("estacao",""), cenario=scenario or (chosen_look or {}).get("cenario",""), emocao=emotion or (chosen_look or {}).get("emocao",""), usos=[usage])
                with st.spinner("Gerando variação sem perder a identidade..."):
                    results = generate_character_variations(p, prompt, quantity=qty, usage=usage, base_asset_id=base_id, metadata={"free_request": request, **variables})
            else:
                concept = {
                    "id": "FREE", "titulo": "Prompt livre", "cenario": scenario, "acao": request,
                    "poses": {p.get("nome", ""): pose for p in selected_chars}, "emocao": emotion,
                    "psicologia_cores": "Aplicar psicologia das cores coerente com a emoção, sem alterar cores canônicas dos personagens.",
                    "iluminacao": "", "camera": "", "figurino_acessorios": f"Figurino: {outfit}. Acessórios: {accessories}. Estação/tema: {season}.", "objetos": "",
                }
                with st.spinner("Gerando cena multi-personagem com todos os Identity Locks..."):
                    results = generate_scene_assets(concept, selected_chars, quantity=qty, usage=usage, base_asset_id=base_id)
            st.session_state["free_generated_results"] = [x["id"] for x in results]
            st.session_state.pop("guide_variation_base_id", None)
            st.rerun()
        _show_result_cards(st.session_state.get("free_generated_results", []), key_prefix="free")

with tabs[4]:
    section_title(
        "Galeria visual reutilizável",
        "Veja variações aprovadas, candidatas e line arts. Arquivar tira do fluxo normal sem apagar o histórico.",
        "Assets, não personagens duplicados",
    )
    all_names = sorted({p.get("nome", "") for p in characters if p.get("nome")})
    g1, g2, g3, g4 = st.columns(4)
    name_filter = g1.selectbox("Personagem", ["Todos", *all_names], key="gallery_person")
    status_filter = g2.selectbox("Status visual", ["Todos", "APPROVED_VARIATION", VARIATION_STATUS, MASTER_STATUS, "COLOR_MASTER", "LINEART_MASTER"], key="gallery_status")
    approved_only = g3.checkbox("✅ Só aprovadas", key="gallery_approved")
    state_filter = g4.selectbox("Estado", ["Ativos", "Arquivados", "Todos"], key="gallery_state")
    filters = {"media_kind": "image"}
    filters["status"] = {"Ativos": "active", "Arquivados": "archived", "Todos": ""}[state_filter]
    if name_filter != "Todos":
        filters["q"] = name_filter
    if approved_only:
        filters["approved"] = True
    result = list_assets(filters, page_size=72)
    items = result.get("items", [])
    if status_filter != "Todos":
        items = [x for x in items if x.get("visual_status") == status_filter]
    if not items:
        st.info("Nenhum asset corresponde aos filtros.")
    else:
        cols = st.columns(4)
        for i, item in enumerate(items):
            with cols[i % 4]:
                with st.container(border=True):
                    _preview_asset(item)
                    st.markdown(f"**{item.get('nome','Asset')}**")
                    st.caption(f"{item.get('visual_status','')} · {item.get('id','')[:8]}")
                    tags = item.get("tags") or []
                    if tags:
                        st.caption(" · ".join(tags[:6]))
                    a, b = st.columns(2)
                    if a.button("👁️ Abrir", key=f"gallery_open_{item['id']}", use_container_width=True):
                        try:
                            select_gallery_asset(st.session_state, item["id"])
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível abrir o asset: {exc}")
                    archived = item.get("status") == "archived"
                    if b.button("♻️" if archived else "🗄️", key=f"gallery_archive_{item['id']}", help="Restaurar" if archived else "Arquivar", use_container_width=True):
                        try:
                            set_archived(item["id"], not archived)
                            st.success("Asset restaurado." if archived else "✅ Asset arquivado. O arquivo e o histórico foram preservados.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível {'restaurar' if archived else 'arquivar'} o asset: {exc}")

    detail_id = st.session_state.get("gallery_open_asset_id")
    detail = get_asset(detail_id) if detail_id else None
    if detail:
        st.divider()
        st.markdown("## 👁️ Detalhes do asset")
        try:
            _preview_asset(detail)
            meta = detail.get("metadata") or {}
            new_name = st.text_input("Nome", value=detail.get("nome", ""), key=f"gallery_detail_name_{detail_id}")
            d1, d2, d3 = st.columns(3)
            d1.code(f"ID: {detail.get('id')}")
            d2.write(f"**Status visual:** {detail.get('visual_status', meta.get('visual_status', ''))}")
            d3.write(f"**Aprovado:** {'Sim' if detail.get('approved') else 'Não'}")
            fields = ["personagem", "personagens", "colecao", "livro", "usage", "usos", "asset_role", "cena", "emocao", "estacao", "figurino", "prompt", "origem"]
            for field in fields:
                if meta.get(field) not in (None, "", []):
                    st.write(f"**{field.replace('_', ' ').title()}:** {meta[field]}")
            st.write(f"**Tipo:** {detail.get('tipo', '')}")
            st.write(f"**Tags:** {', '.join(detail.get('tags') or []) or '—'}")
            if detail.get("visual_status") == "APPROVED_VARIATION":
                st.success("APPROVED_VARIATION")
            x1, x2, x3 = st.columns(3)
            if x1.button("✏️ Renomear", key=f"gallery_detail_rename_{detail_id}"):
                update_asset(detail_id, nome=new_name.strip() or detail.get("nome"))
                st.rerun()
            if detail.get("visual_status") in {VARIATION_STATUS, MASTER_STATUS, "RESTORATION_CANDIDATE"} and x2.button("✅ Aprovar variação", key=f"gallery_detail_approve_{detail_id}"):
                approve_asset_as_variation(detail_id)
                st.rerun()
            if x3.button("🔄 Variar", key=f"gallery_detail_vary_{detail_id}"):
                st.session_state["guide_variation_base_id"] = detail_id
                st.info("Asset preparado para a aba Prompt Livre & Variações.")
            y1, y2, y3 = st.columns(3)
            if y1.button("🖍️ Criar/encaminhar Line Art", key=f"gallery_detail_line_{detail_id}"):
                st.session_state["faithbloom_selected_asset_id"] = detail_id
                st.session_state["faithbloom_selected_asset_path"] = detail.get("caminho_arquivo", "")
                st.switch_page("pages/20_🖍️_Coloring_Book_Doctor.py")
            if y2.button("🖼️ Abrir na Asset Library", key=f"gallery_detail_library_{detail_id}"):
                st.session_state["asset_library_detail"] = detail_id
                st.session_state["faithbloom_selected_asset_id"] = detail_id
                st.switch_page("pages/31_🖼️_Asset_Library_Media_Manager.py")
            archived = detail.get("status") == "archived"
            if y3.button("♻️ Restaurar" if archived else "🗄️ Arquivar", key=f"gallery_detail_archive_{detail_id}"):
                set_archived(detail_id, not archived)
                st.success("Asset restaurado." if archived else "✅ Asset arquivado. O arquivo e o histórico foram preservados.")
                st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível exibir ou atualizar o asset: {exc}")

st.divider()
st.caption("Regra FaithBloom: gerar ≠ aprovar ≠ promover Master. Uma candidata pode ser aprovada como variação no mesmo asset; Color/Line Art Master só muda por confirmação humana explícita.")

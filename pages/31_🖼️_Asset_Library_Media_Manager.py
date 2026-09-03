"""Refinamento 16 — Asset Library & Media Manager."""
from __future__ import annotations

import os
import time
from pathlib import Path

import streamlit as st

from estilo import aplicar_estilo, hero, section_title
from armazenamento import salvar_na_galeria, estatisticas_armazenamento
from asset_library import (
    MASTER_ROLES, MEDIA_LABELS, migrate_gallery_index, list_assets, get_asset,
    facet_values, update_asset, set_favorite, set_archived, set_approved,
    set_master_role, versions_for, list_virtual_collections, create_virtual_collection,
    add_to_collection, remove_from_collection, scan_usage, duplicate_groups,
    get_thumbnail, library_stats, backfill_technical_metadata, permanent_delete_allowed,
    permanent_delete, batch_update,
)

st.set_page_config(page_title="Asset Library & Media Manager", page_icon="🖼️", layout="wide")
aplicar_estilo()
hero(
    "🖼️ Asset Library & Media Manager",
    "Visualize, encontre e reutilize imagens, line arts, capas, referências e outros assets sem transformar sua biblioteca em uma pasta impossível de administrar.",
    "Refinamento 16 · Biblioteca visual persistente",
)

migracao = migrate_gallery_index()
st.caption(f"Catálogo v{migracao['schema']} · {migracao['assets']} asset(s) indexado(s). Registros antigos são normalizados sem alterar os arquivos originais.")

stats = library_stats()
a,b,c,d,e = st.columns(5)
a.metric("Assets ativos", stats["active"])
b.metric("Favoritos", stats["favorites"])
c.metric("Masters", stats["masters"])
d.metric("Arquivados", stats["archived"])
e.metric("Coleções virtuais", stats["virtual_collections"])

storage = estatisticas_armazenamento()
if storage.get("persistente_cloud"):
    st.success("☁️ Storage persistente ativo. Miniaturas e catálogo podem sobreviver a redeploys do Streamlit.")
else:
    st.warning("💻 Storage local ativo. Antes de usar esta biblioteca como acervo definitivo no Streamlit Cloud, configure storage persistente.")

# ------------------------------------------------------------------ helpers

def _fmt_bytes(n: int | float | None) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB": return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _collection_map():
    return {x["id"]: x for x in list_virtual_collections()}


def _asset_badges(item: dict) -> str:
    parts=[]
    if item.get("locked_original"): parts.append("🔒 Original")
    if item.get("approved"): parts.append("✅ Aprovada")
    if item.get("favorita"): parts.append("⭐ Favorita")
    for role in item.get("master_roles", []):
        parts.append(MASTER_ROLES.get(role, role))
    if item.get("status") == "archived": parts.append("🗄️ Arquivada")
    return " · ".join(parts)


def _render_preview(item: dict, compact=False):
    if item.get("media_kind") in {"image", "svg"}:
        thumb = get_thumbnail(item["id"], 320 if compact else 520)
        if thumb: st.image(thumb, use_container_width=True)
        else: st.info("Preview indisponível")
    elif item.get("media_kind") == "audio":
        full = get_asset(item["id"])
        if full and full.get("caminho_arquivo"): st.audio(full["caminho_arquivo"])
        else: st.info("🎧 Áudio")
    elif item.get("media_kind") == "pdf": st.info("📄 PDF")
    else: st.info("📦 Asset")


def _select_asset(asset_id: str):
    st.session_state["asset_library_detail"] = asset_id
    st.session_state["faithbloom_selected_asset_id"] = asset_id


def _save_uploaded(upload, *, nome: str, tipo: str, tags: list[str], metadata: dict):
    cache = Path(".faithbloom_cache/asset_uploads")
    cache.mkdir(parents=True, exist_ok=True)
    safe = Path(upload.name).name.replace("/", "_").replace("\\", "_")
    path = cache / f"{int(time.time()*1000)}-{safe}"
    path.write_bytes(upload.getbuffer())
    try:
        return salvar_na_galeria(str(path), nome or Path(upload.name).stem, tipo, tags, metadata)
    finally:
        try: path.unlink()
        except OSError: pass


# ------------------------------------------------------------------ tabs
tab_library, tab_detail, tab_collections, tab_duplicates, tab_storage = st.tabs([
    "🖼️ Biblioteca visual", "👁️ Detalhes & reutilização", "📁 Coleções virtuais", "🧹 Duplicatas", "☁️ Storage Manager"
])

with tab_library:
    section_title("Encontre uma imagem em segundos", "A busca usa nome, tags e metadados como personagem, livro, coleção, emoção, estação e festividade. Arquivos permanecem únicos; filtros não criam cópias.", "Busca")
    q = st.text_input("🔎 Pesquisar", placeholder="Mel neve Max Natal · girafinha line art · capa aprovada...")
    f1,f2,f3,f4 = st.columns(4)
    tipo_values = ["Todos"] + facet_values("tipo", include_archived=True)
    media_values = ["Todos"] + facet_values("media_kind", include_archived=True)
    personagem_values = ["Todos"] + facet_values("personagem", include_archived=True)
    colecao_values = ["Todos"] + facet_values("colecao", include_archived=True)
    tipo = f1.selectbox("Tipo", tipo_values)
    media = f2.selectbox("Mídia", media_values, format_func=lambda x: x if x=="Todos" else MEDIA_LABELS.get(x,x))
    personagem = f3.selectbox("Personagem", personagem_values)
    colecao = f4.selectbox("Coleção editorial", colecao_values)

    f5,f6,f7,f8 = st.columns(4)
    livro_values = ["Todos"] + facet_values("livro", include_archived=True)
    emocao_values = ["Todos"] + facet_values("emocao", include_archived=True)
    estacao_values = ["Todos"] + facet_values("estacao", include_archived=True)
    status_label = f8.selectbox("Estado", ["Ativos", "Arquivados", "Todos"])
    livro = f5.selectbox("Livro", livro_values)
    emocao = f6.selectbox("Emoção", emocao_values)
    estacao = f7.selectbox("Estação", estacao_values)

    g1,g2,g3,g4 = st.columns(4)
    role_options = ["Todos"] + list(MASTER_ROLES)
    master_role = g1.selectbox("Master", role_options, format_func=lambda x: "Todos" if x=="Todos" else MASTER_ROLES[x])
    only_fav = g2.checkbox("⭐ Só favoritas")
    only_approved = g3.checkbox("✅ Só aprovadas")
    collections = list_virtual_collections(); cmap = {x["id"]:x for x in collections}
    collection_options = [""] + [x["id"] for x in collections]
    vcollection = g4.selectbox("Pasta/coleção virtual", collection_options, format_func=lambda x: "Todas" if not x else cmap[x]["name"])

    h1,h2,h3 = st.columns([1,1,2])
    view = h1.radio("Visualização", ["Grade grande", "Grade compacta", "Lista"], horizontal=False)
    page_size = h2.selectbox("Por página", [12,24,48,72], index=1)
    sort = h3.selectbox("Ordenar", ["Mais recentes", "Mais antigos", "Nome", "Favoritos primeiro"])
    sort_map = {"Mais recentes":"newest", "Mais antigos":"oldest", "Nome":"name", "Favoritos primeiro":"favorites"}

    filters = {
        "q": q,
        "tipo": None if tipo=="Todos" else tipo,
        "media_kind": None if media=="Todos" else media,
        "personagem": None if personagem=="Todos" else personagem,
        "colecao": None if colecao=="Todos" else colecao,
        "livro": None if livro=="Todos" else livro,
        "emocao": None if emocao=="Todos" else emocao,
        "estacao": None if estacao=="Todos" else estacao,
        "favorite": True if only_fav else None,
        "approved": True if only_approved else None,
        "master_role": None if master_role=="Todos" else master_role,
        "virtual_collection": vcollection or None,
    }
    if status_label == "Ativos": filters["status"]="active"
    elif status_label == "Arquivados": filters["status"]="archived"
    else: filters["status"] = None

    # page remembered separately from filters; clamp is handled by list_assets.
    page = int(st.session_state.get("asset_library_page", 1))
    result = list_assets(filters, page=page, page_size=page_size, sort=sort_map[sort])
    if result["page"] != page: st.session_state["asset_library_page"] = result["page"]
    p1,p2,p3 = st.columns([1,2,1])
    if p1.button("← Anterior", disabled=result["page"]<=1, use_container_width=True):
        st.session_state["asset_library_page"] = result["page"]-1; st.rerun()
    p2.markdown(f"<div style='text-align:center;padding:.55rem'><b>{result['total']}</b> resultado(s) · página {result['page']} de {result['pages']}</div>", unsafe_allow_html=True)
    if p3.button("Próxima →", disabled=result["page"]>=result["pages"], use_container_width=True):
        st.session_state["asset_library_page"] = result["page"]+1; st.rerun()

    # batch selection/actions
    selected = set(st.session_state.get("asset_library_selected_ids", []))
    with st.expander(f"☑️ Ações em lote · {len(selected)} selecionado(s)", expanded=bool(selected)):
        ba,bb,bc,bd = st.columns(4)
        if ba.button("⭐ Favoritar", disabled=not selected, use_container_width=True):
            batch_update(selected, favorite=True); st.rerun()
        if bb.button("🗄️ Arquivar", disabled=not selected, use_container_width=True):
            batch_update(selected, archived=True); st.session_state["asset_library_selected_ids"]=[]; st.rerun()
        batch_tags = bc.text_input("Adicionar tags", placeholder="Natal, Mel, inverno")
        if bc.button("🏷️ Aplicar tags", disabled=not selected or not batch_tags.strip(), use_container_width=True):
            batch_update(selected, add_tags=[x.strip() for x in batch_tags.split(",")]); st.rerun()
        if collections:
            bid = bd.selectbox("Coleção virtual", [x["id"] for x in collections], format_func=lambda x:cmap[x]["name"], key="batch_collection")
            if bd.button("📁 Adicionar", disabled=not selected, use_container_width=True):
                add_to_collection(selected,bid); st.success("Adicionado sem duplicar arquivos."); st.rerun()
        else: bd.caption("Crie uma coleção virtual na aba 📁.")

    items = result["items"]
    if not items:
        st.info("Nenhum asset corresponde aos filtros atuais.")
    elif view == "Lista":
        for item in items:
            c0,c1,c2,c3 = st.columns([0.35,1.1,4.2,1.2])
            checked = c0.checkbox("", value=item["id"] in selected, key=f"asset_sel_list_{item['id']}", label_visibility="collapsed")
            if checked: selected.add(item["id"])
            else: selected.discard(item["id"])
            with c1: _render_preview(item, compact=True)
            with c2:
                st.markdown(f"**{item.get('nome','Asset')}**")
                st.caption(_asset_badges(item) or f"{item.get('tipo')} · {MEDIA_LABELS.get(item.get('media_kind'), item.get('media_kind'))}")
                st.caption(" · ".join(item.get("tags",[])[:10]))
            with c3:
                if st.button("👁️ Detalhes", key=f"det_list_{item['id']}", use_container_width=True): _select_asset(item["id"]); st.rerun()
                if st.button("⭐" if not item.get("favorita") else "★", key=f"fav_list_{item['id']}", use_container_width=True): set_favorite(item["id"], not item.get("favorita")); st.rerun()
    else:
        ncols = 3 if view == "Grade grande" else 5
        cols = st.columns(ncols)
        for i,item in enumerate(items):
            with cols[i%ncols]:
                with st.container(border=True):
                    checked=st.checkbox("Selecionar", value=item["id"] in selected, key=f"asset_sel_{item['id']}")
                    if checked: selected.add(item["id"])
                    else: selected.discard(item["id"])
                    _render_preview(item, compact=(view=="Grade compacta"))
                    st.markdown(f"**{item.get('nome','Asset')}**")
                    if _asset_badges(item): st.caption(_asset_badges(item))
                    st.caption(" · ".join(item.get("tags",[])[:6]) or item.get("tipo",""))
                    x,y=st.columns(2)
                    if x.button("👁️", key=f"det_{item['id']}", help="Abrir detalhes", use_container_width=True): _select_asset(item["id"]); st.rerun()
                    if y.button("★" if item.get("favorita") else "☆", key=f"fav_{item['id']}", help="Favoritar", use_container_width=True): set_favorite(item["id"], not item.get("favorita")); st.rerun()
    st.session_state["asset_library_selected_ids"] = list(selected)

    st.divider()
    with st.expander("📤 Adicionar arquivo diretamente à biblioteca"):
        up = st.file_uploader("Arquivo", type=["png","jpg","jpeg","webp","gif","svg","pdf","mp3","wav"], key="asset_library_upload")
        u1,u2=st.columns(2)
        unome=u1.text_input("Nome do asset", placeholder="Mel — Christmas Outfit")
        utipo=u2.selectbox("Tipo", ["personagem","cena","line_art","referencia","capa","atividade","fundo","audio","documento"])
        utags=st.text_input("Tags separadas por vírgula", placeholder="Mel, Natal, inverno")
        u3,u4,u5=st.columns(3)
        uperson=u3.text_input("Personagem")
        ucolecao=u4.text_input("Coleção editorial")
        ulivro=u5.text_input("Livro")
        if st.button("💾 Salvar na Asset Library", type="primary", disabled=up is None):
            item=_save_uploaded(up,nome=unome,tipo=utipo,tags=[x.strip() for x in utags.split(",")],metadata={"personagem":uperson,"colecao":ucolecao,"livro":ulivro,"origem":"upload_autora"})
            st.success(f"{item['nome']} salvo. O arquivo pode ser reutilizado por outros Studios.")
            st.rerun()

with tab_detail:
    asset_id = st.session_state.get("asset_library_detail") or st.session_state.get("faithbloom_selected_asset_id")
    if not asset_id:
        st.info("Na Biblioteca visual, clique em 👁️ para abrir um asset aqui.")
    else:
        item = get_asset(asset_id)
        if not item:
            st.warning("O asset selecionado não existe mais no catálogo.")
        else:
            meta = item.get("metadata") or {}
            left,right=st.columns([1.35,1], gap="large")
            with left:
                _render_preview(item)
                st.markdown(f"### {item.get('nome')}")
                st.caption(_asset_badges(item) or "Sem badges especiais")
                if item.get("media_kind") not in {"image","svg","audio"} and item.get("caminho_arquivo"):
                    st.download_button("⬇️ Baixar asset", Path(item["caminho_arquivo"]).read_bytes(), file_name=Path(item["caminho_arquivo"]).name, use_container_width=True)
            with right:
                st.markdown("#### Identidade e organização")
                nome=st.text_input("Nome", value=item.get("nome",""), key=f"detail_name_{asset_id}")
                tags=st.text_input("Tags", value=", ".join(item.get("tags",[])), key=f"detail_tags_{asset_id}")
                d1,d2=st.columns(2)
                personagem=d1.text_input("Personagem", value=str(meta.get("personagem", "")), key=f"detail_person_{asset_id}")
                colecao=d2.text_input("Coleção", value=str(meta.get("colecao", "")), key=f"detail_collection_{asset_id}")
                d3,d4=st.columns(2)
                livro=d3.text_input("Livro", value=str(meta.get("livro", "")), key=f"detail_book_{asset_id}")
                cena=d4.text_input("Cena/página", value=str(meta.get("cena", meta.get("cena_numero", ""))), key=f"detail_scene_{asset_id}")
                d5,d6,d7=st.columns(3)
                emocao=d5.text_input("Emoção", value=str(meta.get("emocao", "")), key=f"detail_emotion_{asset_id}")
                estacao=d6.text_input("Estação", value=str(meta.get("estacao", "")), key=f"detail_season_{asset_id}")
                roupa=d7.text_input("Roupa", value=str(meta.get("roupa", "")), key=f"detail_outfit_{asset_id}")
                prompt=st.text_area("Prompt / observação de origem", value=str(meta.get("prompt", "")), key=f"detail_prompt_{asset_id}")
                if st.button("💾 Salvar metadados", type="primary", use_container_width=True):
                    update_asset(asset_id, nome=nome, tags=[x.strip() for x in tags.split(",")], metadata={"personagem":personagem,"colecao":colecao,"livro":livro,"cena":cena,"emocao":emocao,"estacao":estacao,"roupa":roupa,"prompt":prompt})
                    st.success("Metadados atualizados sem alterar o arquivo."); st.rerun()

                st.markdown("#### Aprovação e Masters")
                aa,ab=st.columns(2)
                if aa.button("✅ Marcar aprovada" if not item.get("approved") else "↩️ Remover aprovação", use_container_width=True): set_approved(asset_id, not item.get("approved")); st.rerun()
                if ab.button("⭐ Favoritar" if not item.get("favorita") else "☆ Desfavoritar", use_container_width=True): set_favorite(asset_id, not item.get("favorita")); st.rerun()
                roles=set(item.get("master_roles",[]))
                for role,label in MASTER_ROLES.items():
                    enabled=st.checkbox(label, value=role in roles, key=f"role_{asset_id}_{role}")
                    if enabled != (role in roles): set_master_role(asset_id, role, enabled); st.rerun()

            st.divider()
            section_title("Reutilização", "Selecione o asset como referência atual. Os Studios podem reutilizar o mesmo arquivo em vez de gerar uma cópia desnecessária.", "Usar existente")
            r1,r2,r3=st.columns(3)
            if r1.button("🎯 Selecionar para uso", type="primary", use_container_width=True):
                st.session_state["faithbloom_selected_asset_id"] = asset_id
                st.session_state["faithbloom_selected_asset_path"] = item.get("caminho_arquivo","")
                st.session_state["faithbloom_selected_asset"] = item
                st.success("Asset selecionado na sessão. Você pode abrir um Studio e reutilizá-lo como referência.")
            if r2.button("🖍️ Abrir Coloring Studio", use_container_width=True):
                st.session_state["faithbloom_selected_asset_id"] = asset_id
                st.session_state["faithbloom_selected_asset_path"] = item.get("caminho_arquivo","")
                st.switch_page("pages/3_#L01f58d#Ufe0f_Livros_de_Colorir.py")
            if r3.button("✨ Abrir Restoration Studio", use_container_width=True):
                st.session_state["faithbloom_selected_asset_id"] = asset_id
                st.session_state["faithbloom_selected_asset_path"] = item.get("caminho_arquivo","")
                st.switch_page("pages/19_✨_Restoration_Studio.py")

            st.markdown("#### Onde esta imagem está sendo usada?")
            if st.button("🔗 Verificar vínculos agora", use_container_width=True):
                with st.spinner("Procurando referências nos projetos persistidos..."):
                    st.session_state[f"asset_usage_{asset_id}"]=scan_usage(asset_id)
            usage=st.session_state.get(f"asset_usage_{asset_id}")
            if usage:
                if usage["records"]:
                    st.dataframe([{"Projeto":x.get("project_title"),"Tipo":x.get("project_type"),"Local":x.get("location"),"Arquivo do projeto":x.get("project_storage_path"),"Fonte":x.get("source")} for x in usage["records"]], use_container_width=True, hide_index=True)
                    st.warning("Este asset possui vínculos. Arquivar é mais seguro do que excluir.")
                else: st.success("Nenhum vínculo foi encontrado na varredura atual.")
                if usage.get("truncated"): st.caption("A varredura atingiu o limite de arquivos; ausência de vínculo não é conclusiva.")

            st.markdown("#### Versões relacionadas")
            versions=versions_for(asset_id)
            if len(versions)<=1: st.caption("Ainda não existem versões A/B/C relacionadas a este asset.")
            else:
                vc=st.columns(min(4,len(versions)))
                for i,v in enumerate(versions):
                    with vc[i%len(vc)]:
                        _render_preview(v, compact=True)
                        st.caption(f"{v.get('version_label')} {'✅' if v.get('approved') else ''}")
                        if st.button("Abrir", key=f"open_version_{v['id']}"): _select_asset(v["id"]); st.rerun()

            st.markdown("#### Dados técnicos")
            tech = item.get("metadata") or {}
            t1,t2,t3,t4=st.columns(4)
            t1.metric("Largura", tech.get("width_px") or "—")
            t2.metric("Altura", tech.get("height_px") or "—")
            t3.metric("Arquivo", _fmt_bytes(tech.get("file_size_bytes")) if tech.get("file_size_bytes") else "—")
            t4.metric("Mídia", MEDIA_LABELS.get(item.get("media_kind"), item.get("media_kind")))
            if st.button("🔬 Atualizar dados técnicos deste asset"):
                out=backfill_technical_metadata([asset_id],limit=1)
                if out["errors"]: st.warning(out["errors"][0])
                else: st.success("Metadados técnicos calculados.")
                st.rerun()

            st.divider()
            danger1,danger2=st.columns(2)
            if item.get("status") != "archived":
                if danger1.button("🗄️ Arquivar asset", use_container_width=True): set_archived(asset_id,True); st.success("Asset arquivado. O arquivo não foi apagado."); st.rerun()
            else:
                if danger1.button("♻️ Restaurar do arquivo", use_container_width=True): set_archived(asset_id,False); st.rerun()
            with danger2.expander("🗑️ Exclusão permanente", expanded=False):
                st.caption("Use somente quando realmente necessário. Masters, originais bloqueados e assets com vínculos não podem ser excluídos por esta tela.")
                usage_now=usage or scan_usage(asset_id)
                allowed,reason=permanent_delete_allowed(asset_id,usage_now)
                st.write(reason)
                confirm=st.checkbox("Confirmo que quero excluir permanentemente o arquivo e o registro", key=f"delete_confirm_{asset_id}")
                if st.button("Excluir permanentemente", disabled=not (allowed and confirm), type="secondary"):
                    permanent_delete(asset_id,confirmed=True); st.session_state.pop("asset_library_detail",None); st.success("Asset excluído."); st.rerun()

with tab_collections:
    section_title("Pastas sem duplicação", "Uma coleção virtual é apenas uma organização do catálogo. O mesmo arquivo pode aparecer em Mel, Natal e Capas aprovadas sem ocupar espaço três vezes.", "Coleções")
    c1,c2=st.columns([1,2])
    with c1:
        nome=st.text_input("Nova coleção", placeholder="Mel — Natal")
        desc=st.text_area("Descrição", placeholder="Assets oficiais e aprovados para o livro de Natal")
        if st.button("➕ Criar coleção virtual", type="primary", disabled=not nome.strip()):
            create_virtual_collection(nome,desc); st.success("Coleção criada."); st.rerun()
    with c2:
        cols=list_virtual_collections()
        if not cols: st.info("Nenhuma coleção virtual criada ainda.")
        else:
            for col in cols:
                count=list_assets({"status":None,"virtual_collection":col["id"]},page_size=1)["total"]
                with st.container(border=True):
                    st.markdown(f"**📁 {col['name']}** · {count} asset(s)")
                    st.caption(col.get("description") or "Sem descrição")
                    st.page_link("pages/31_🖼️_Asset_Library_Media_Manager.py", label="Abrir biblioteca e filtrar manualmente →", use_container_width=True)

with tab_duplicates:
    section_title("Possíveis duplicatas", "O FaithBloom compara fingerprints de conteúdo. Ele não apaga nada automaticamente; versões intencionais permanecem separadas.", "Storage hygiene")
    groups=duplicate_groups(deep=False)
    if not groups:
        st.success("Nenhuma duplicata exata foi detectada pelos fingerprints disponíveis.")
    else:
        st.warning(f"{len(groups)} grupo(s) com conteúdo potencialmente idêntico.")
        for g in groups[:50]:
            with st.expander(f"{g['count']} itens · fingerprint {g['fingerprint'][:16]}…"):
                rows=[]
                for x in g["items"]:
                    rows.append({"Nome":x.get("nome"),"ID":x.get("id"),"Status":x.get("status"),"Master":", ".join(x.get("master_roles",[])),"Storage":x.get("storage_uri")})
                st.dataframe(rows,use_container_width=True,hide_index=True)
                st.caption("Revise o contexto antes de arquivar. Assets visualmente iguais podem representar versões editoriais diferentes.")

with tab_storage:
    section_title("Storage Manager", "Acompanhe crescimento do acervo e preencha metadados técnicos sem excluir rascunhos automaticamente.", "Capacidade")
    stats=library_stats()
    s1,s2,s3,s4=st.columns(4)
    s1.metric("Assets",stats["total"])
    s2.metric("Tamanho conhecido",_fmt_bytes(stats["known_bytes"]))
    s3.metric("Sem tamanho indexado",stats["unknown_sizes"])
    s4.metric("Arquivados",stats["archived"])
    rows=[{"Tipo":MEDIA_LABELS.get(k,k),"Quantidade":v} for k,v in sorted(stats["by_media_kind"].items())]
    st.dataframe(rows,use_container_width=True,hide_index=True)
    st.caption("O tamanho mostrado é a soma dos assets que já possuem metadado técnico. O FaithBloom não baixa todo o bucket automaticamente apenas para calcular espaço.")
    limit=st.slider("Quantos assets com metadados ausentes analisar nesta execução?",1,200,25)
    if st.button("🔬 Preencher dimensões/tamanho/hash", type="primary"):
        with st.spinner("Lendo somente os assets selecionados para esta execução..."):
            out=backfill_technical_metadata(limit=limit)
        st.success(f"{out['processed']} asset(s) processado(s).")
        if out["errors"]: st.warning("Alguns não puderam ser analisados:\n"+"\n".join(out["errors"][:10]))
        st.rerun()
    st.markdown("#### Política de limpeza")
    st.write("• Rascunhos não usados podem ser **arquivados**.\n• Duplicatas são apenas **sinalizadas**.\n• Masters e originais publicados recebem proteção extra.\n• Exclusão permanente exige confirmação e ausência de vínculos encontrados.")

st.caption("FaithBloom 2.0 · Refinamento 16 · Asset Library & Media Manager · biblioteca visual escalável antes da promoção Stable")

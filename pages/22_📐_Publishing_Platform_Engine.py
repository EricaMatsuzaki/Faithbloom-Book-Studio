"""FaithBloom Refinamento 07 — Publishing Platform Engine."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from armazenamento import listar_livros, carregar_livro, salvar_livro
from estilo import aplicar_estilo, hero, section_title
from platform_registry import (
    get_registry,
    get_platform,
    list_platforms,
    register_custom_platform,
    remove_custom_platform,
    registry_snapshot,
    verification_state,
    update_platform_spec,
    platform_history,
)
from platform_format_engine import (
    BookMasterSpec,
    compare_platforms,
    compatibility,
    calculate_print_geometry,
    build_derivative_plan,
    preflight_target,
    inch_to_mm,
)
from epub_exporter import export_epub, inspect_epub
from pacote_publicacao import gerar_pacote_multiplataforma


def _safe_slug(value: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value or "book").strip("-").lower() or "book"

st.set_page_config(page_title="Publishing Platform Engine", page_icon="📐", layout="wide")
aplicar_estilo()
hero(
    "📐 Publishing Platform Engine",
    "Um Book Master, vários destinos. Compare requisitos, crie edições derivadas sem redimensionar silenciosamente e faça preflight por plataforma.",
    "Refinamento 07 · Platform Registry expansível",
)

# -------------------- MASTER
section_title("1. Book Master", "Defina a edição-base. Nenhuma plataforma pode alterar este Master silenciosamente.", "Master")
livros = listar_livros()
source = st.radio("Origem", ["Projeto salvo", "Configurar manualmente"], horizontal=True, disabled=not bool(livros)) if livros else "Configurar manualmente"
state = {}
if source == "Projeto salvo" and livros:
    options = {f"{x.get('titulo','(sem título)')} · {x.get('colecao','')}": x for x in livros}
    selected = st.selectbox("Livro", list(options))
    info = options[selected]
    state = carregar_livro(info.get("colecao", ""), info["arquivo"])

c1,c2,c3,c4 = st.columns(4)
title = c1.text_input("Título", value=state.get("titulo", ""))
language = c2.text_input("Idioma/locale", value=state.get("idioma_original", "pt-BR"))
trim_w = c3.number_input("Trim largura (in)", min_value=3.0, max_value=20.0, value=float(state.get("trim_largura_in", state.get("trim_width_in", 8.5))), step=0.125)
trim_h = c4.number_input("Trim altura (in)", min_value=3.0, max_value=20.0, value=float(state.get("trim_altura_in", state.get("trim_height_in", 8.5))), step=0.125)
c1,c2,c3,c4 = st.columns(4)
page_count = c1.number_input("Páginas físicas", min_value=1, value=int(state.get("paginas_fisicas", state.get("paginas_minimas", 32))), step=1)
interior = c2.selectbox("Interior", ["premium_color", "standard_color", "black_white"], format_func=lambda x: {"premium_color":"Cor premium","standard_color":"Cor padrão","black_white":"Preto & branco"}[x])
binding = c3.selectbox("Produto-base", ["paperback", "hardcover", "ebook"], index=0)
bleed = c4.checkbox("Bleed", value=bool(state.get("usar_bleed", True)))

c1,c2,c3 = st.columns(3)
kdp_select = c1.checkbox("🔒 KDP Select / exclusividade digital ativa", value=bool(state.get("kdp_select_active", False)))
isbn_mode = c2.selectbox("ISBN", ["platform", "own", "none"], format_func=lambda x: {"platform":"Fornecido pela plataforma","own":"ISBN próprio","none":"Sem ISBN / quando permitido"}[x])
isbn = c3.text_input("ISBN próprio", value=state.get("isbn", ""), disabled=isbn_mode != "own")

master = BookMasterSpec(
    title=title, language=language, trim_width_in=float(trim_w), trim_height_in=float(trim_h), page_count=int(page_count),
    interior=interior, binding=binding, bleed=bleed, target_ppi=300, kdp_select_active=kdp_select, isbn_mode=isbn_mode, isbn=isbn,
).to_dict()
st.caption(f"Master físico: {trim_w:.3f} × {trim_h:.3f} in · {inch_to_mm(trim_w):.1f} × {inch_to_mm(trim_h):.1f} mm · política: **nunca redimensionar silenciosamente**.")

# -------------------- DESTINATIONS
section_title("2. Onde quero publicar?", "Marque plataformas e produtos. O FaithBloom compara compatibilidade e registra a versão da especificação usada.", "Destinos")
registry = get_registry()
major_ids = ["amazon_kdp","ingramspark","lulu","kobo_writing_life","apple_books","google_play_books","draft2digital","barnes_noble_press","etsy","hotmart","kiwify"]
selected_targets = []
cols = st.columns(3)
for idx, pid in enumerate(major_ids):
    p = registry[pid]
    with cols[idx % 3]:
        checked = st.checkbox(p["name"], value=pid in {"amazon_kdp"}, key=f"plat_{pid}")
        if checked:
            default_product = "ebook" if "ebook" in p["products"] and p["category"] in {"ebook_store","aggregator"} else ("paperback" if "paperback" in p["products"] else p["products"][0])
            product = st.selectbox(f"Produto · {p['name']}", p["products"], index=p["products"].index(default_product), key=f"prod_{pid}")
            selected_targets.append({"platform_id": pid, "product": product})

other_profiles=[p for p in list_platforms() if p["id"] not in major_ids]
if other_profiles:
    other_names={p["name"]:p for p in other_profiles}
    chosen_extra=st.multiselect("Outras plataformas / personalizadas",list(other_names),help="Inclui perfis adicionais e qualquer plataforma que você cadastrar no Registry.")
    for name in chosen_extra:
        p=other_names[name]
        product=st.selectbox(f"Produto · {p['name']}",p["products"],key=f"prod_extra_{p['id']}")
        selected_targets.append({"platform_id":p["id"],"product":product})

with st.expander("🌐 Ver todas as plataformas cadastradas"):
    for p in list_platforms():
        state_v = verification_state(p)
        icon = "🟢" if state_v["state"] == "current" else ("🟡" if state_v["state"] == "stale" else "⚪")
        st.write(f"{icon} **{p['name']}** · {p['category']} · {', '.join(p['products'])} · spec {p.get('spec_version','')} · {p.get('last_verified') or 'não verificada'}")

if selected_targets:
    st.markdown("#### Matriz de compatibilidade")
    rows = compare_platforms(master, selected_targets)
    for r in rows:
        icon = {"compatible":"🟢","review":"🟡","blocked":"🔴"}.get(r["status"],"⚪")
        with st.expander(f"{icon} {r['platform_name']} · {r['product']} · {r['status']}", expanded=r["status"] != "compatible"):
            st.write("Formatos aceitos no perfil:", ", ".join(r.get("accepted_formats") or []) or "revisão manual")
            st.caption(f"Spec {r.get('spec_version','')} · última verificação {r.get('last_verified') or 'não registrada'}")
            if r.get("nearest_trim"):
                n=r["nearest_trim"]
                st.write(f"Preset mais próximo: **{n['width_in']} × {n['height_in']} in** · delta de proporção {n['aspect_delta_pct']:.2f}%")
            for a in r["alerts"]:
                st.write(f"- **{a['severity']}** · {a['message']}")
            if r["product"] in {"paperback","hardcover"}:
                try:
                    g=calculate_print_geometry(master,r["platform_id"],r["product"])
                    st.json(g,expanded=False)
                except Exception as exc:
                    st.caption(f"Geometria automática parcial: {exc}")

# -------------------- DERIVATIVE PLAN
section_title("3. Plano de edições derivadas", "O Master permanece intacto. Se outro trim ou formato for necessário, o FaithBloom cria um plano explícito antes da conversão.", "Derivatives")
if selected_targets:
    plan=build_derivative_plan(master,selected_targets)
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Destinos",plan["summary"]["targets"])
    m2.metric("Bloqueados",plan["summary"]["blocked"])
    m3.metric("Revisão",plan["summary"]["needs_review"])
    m4.metric("Novo layout",plan["summary"]["layout_derivatives"])
    st.json(plan,expanded=False)
    st.download_button("⬇️ Baixar plano JSON",data=json.dumps(plan,ensure_ascii=False,indent=2),file_name="faithbloom-platform-plan.json",mime="application/json")
    if state and st.button("💾 Salvar plano no projeto como nova revisão"):
        state["publishing_platform_plan"]=plan
        state["publishing_targets"]=selected_targets
        state["kdp_select_active"]=kdp_select
        state["isbn_mode"]=isbn_mode
        state["isbn"]=isbn
        uri=salvar_livro(state)
        st.success(f"Plano salvo em uma nova revisão do projeto: {uri}")
else:
    st.info("Selecione pelo menos uma plataforma para montar o plano.")

# -------------------- EPUB
section_title("4. eBook / EPUB", "Livros digitais recebem arquivo próprio. Para picture books, Fixed Layout pode preservar a composição por página.", "Digital")
if state:
    mode=st.radio("Modo EPUB",["fixed","reflowable"],format_func=lambda x:"Fixed Layout · picture book" if x=="fixed" else "Reflowable · texto fluido",horizontal=True)
    if st.button("📱 Gerar EPUB desta edição"):
        out=Path("exportacoes_multiplataforma")/_safe_slug(title or "book")/f"{_safe_slug(language)}-{mode}.epub"
        try:
            result=export_epub(state,str(out),mode=mode,language=language)
            st.session_state.r07_epub=result
            st.success("EPUB gerado. Ainda precisa de EPUBCheck/preview antes da publicação final.")
        except Exception as exc:
            st.error(f"Não foi possível gerar o EPUB: {type(exc).__name__}: {exc}")
    if st.session_state.get("r07_epub"):
        result=st.session_state.r07_epub
        st.json({**result,"inspection":inspect_epub(result["path"])},expanded=False)
        if Path(result["path"]).exists():
            with open(result["path"],"rb") as f:
                st.download_button("⬇️ Baixar EPUB",f,file_name=Path(result["path"]).name,mime="application/epub+zip")
else:
    st.caption("Selecione um projeto salvo para gerar EPUB a partir das cenas e assets existentes. O modo manual serve para compatibilidade/preflight.")

# -------------------- PREFLIGHT ASSETS
section_title("5. Preflight por plataforma", "Associe os arquivos da edição e veja bloqueios reais por destino.", "Quality Gate")
interior_pdf = state.get("pdf_miolo_print_ready") or state.get("pdf_miolo") or ""
cover_pdf = state.get("capa_fisica_pdf") or ""
epub_path = (st.session_state.get("r07_epub") or {}).get("path") or state.get("epub") or state.get("ebook_epub") or ""
epubcheck_passed = st.checkbox("EPUBCheck passou", value=bool(state.get("epubcheck_passed", False)), help="Marque somente após validar o EPUB com EPUBCheck/validador da plataforma.")
if selected_targets:
    for t in selected_targets:
        check=preflight_target(master,t["platform_id"],t["product"],{"interior_pdf":interior_pdf,"cover_pdf":cover_pdf,"epub":epub_path,"epubcheck_passed":epubcheck_passed,"digital_file":state.get("digital_file")})
        icon="🟢" if check["ready"] else "🔴"
        with st.expander(f"{icon} {check['platform_name']} · {check['product']}",expanded=not check["ready"]):
            for a in check["alerts"]:
                st.write(f"- **{a['severity']}** · {a['message']}")
            if check["ready"]:
                st.success("Verificações automáticas disponíveis passaram. Ainda use o preview/template/prova oficial da plataforma.")

# -------------------- MULTICHANNEL PACKAGE
section_title("6. Pacote multicanal", "Gere um ZIP de controle com Master, metadados, manifesto e preflight por destino. Arquivos incompatíveis ou ausentes continuam bloqueados — nunca são apenas renomeados.", "Distribution Package")
if state and selected_targets:
    state_for_package=dict(state)
    state_for_package.update({"kdp_select_active":kdp_select,"isbn_mode":isbn_mode,"isbn":isbn,"binding":binding,"interior_publicacao":interior,"paginas_fisicas":int(page_count),"trim_largura_in":float(trim_w),"trim_altura_in":float(trim_h),"usar_bleed":bleed})
    if st.session_state.get("r07_epub"):
        state_for_package["epub"]=st.session_state.r07_epub.get("path")
        state_for_package["epubcheck_passed"]=epubcheck_passed
    if st.button("📦 Gerar pacote multicanal",use_container_width=True):
        try:
            package=gerar_pacote_multiplataforma(state_for_package,selected_targets)
            st.session_state.r07_package=package
            st.success("Pacote gerado com manifestos e bloqueios por plataforma.")
        except Exception as exc:
            st.error(f"Falha ao gerar pacote: {exc}")
    if st.session_state.get("r07_package"):
        pkg=st.session_state.r07_package
        st.json(pkg["manifesto"],expanded=False)
        if Path(pkg["zip"]).exists():
            with open(pkg["zip"],"rb") as f:
                st.download_button("⬇️ Baixar pacote multicanal",f,file_name=Path(pkg["zip"]).name,mime="application/zip",use_container_width=True)
else:
    st.info("Selecione um projeto salvo e pelo menos um destino para gerar o pacote multicanal.")

# -------------------- CUSTOM PLATFORM
section_title("7. ➕ Adicionar nova plataforma", "O Registry é expansível: cadastre uma plataforma nova sem precisar reescrever o FaithBloom.", "Platform Registry")
with st.expander("Cadastrar plataforma personalizada",expanded=False):
    name=st.text_input("Nome da plataforma",key="r07_custom_name")
    category=st.selectbox("Categoria",["direct_publishing","ebook_store","distribution_and_pod","aggregator","pod_and_direct_sales","digital_marketplace","digital_product_platform","custom"],key="r07_custom_cat")
    products_raw=st.text_input("Produtos (separados por vírgula)",value="ebook",key="r07_custom_products")
    formats_raw=st.text_input("Formatos para o primeiro produto",value="epub,pdf",key="r07_custom_formats")
    source_url=st.text_input("Documentação oficial / URL",key="r07_custom_url")
    verified=st.text_input("Data de verificação (AAAA-MM-DD)",placeholder="2026-09-03",key="r07_custom_verified")
    notes=st.text_area("Notas/requisitos",key="r07_custom_notes")
    if st.button("➕ Adicionar ao Registry",disabled=not name.strip()):
        products=[x.strip() for x in products_raw.split(",") if x.strip()]
        formats=[x.strip().lower().lstrip(".") for x in formats_raw.split(",") if x.strip()]
        try:
            rec=register_custom_platform(name=name,category=category,products=products,accepted_formats={products[0] if products else "custom":formats},source_urls=[source_url] if source_url else [],notes=[notes] if notes else [],last_verified=verified or None)
            st.success(f"{rec['name']} adicionada como plataforma personalizada.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

custom=[p for p in list_platforms() if not p.get("builtin")]
if custom:
    st.markdown("#### Plataformas personalizadas")
    for p in custom:
        c1,c2=st.columns([4,1])
        c1.write(f"**{p['name']}** · {p['category']} · {', '.join(p['products'])}")
        if c2.button("Remover",key=f"remove_{p['id']}"):
            remove_custom_platform(p["id"]); st.rerun()

with st.expander("🔄 Atualizar especificação versionada", expanded=False):
    st.caption("Use dados da documentação oficial. O baseline do FaithBloom fica preservado e a alteração é salva como override com histórico.")
    allp=list_platforms()
    ids={p["name"]:p["id"] for p in allp}
    sel_name=st.selectbox("Plataforma a atualizar",list(ids),key="r07_update_platform")
    sel_id=ids[sel_name]
    cur=get_platform(sel_id)
    st.caption(f"Atual: {cur.get('spec_version','')} · verificada em {cur.get('last_verified') or 'não informado'}")
    new_ver=st.text_input("Nova versão da especificação",value=f"{cur.get('spec_version','custom')}-rev",key="r07_new_spec_version")
    new_date=st.text_input("Data da verificação",value="2026-09-03",key="r07_new_verify_date")
    new_urls=st.text_area("Fontes oficiais (uma URL por linha)",value="\n".join(cur.get("source_urls") or []),key="r07_new_sources")
    patch_text=st.text_area("Patch JSON de requisitos",value="{}",height=150,key="r07_spec_patch",help='Ex.: {"print":{"bleed_in":0.125,"target_ppi":300}}')
    note=st.text_input("Nota da alteração",placeholder="Ex.: atualização do manual de capa",key="r07_spec_note")
    if st.button("🔄 Salvar nova especificação",key="r07_save_spec"):
        try:
            patch=json.loads(patch_text or "{}")
            rec=update_platform_spec(sel_id,patch,spec_version=new_ver,last_verified=new_date,source_urls=[x.strip() for x in new_urls.splitlines() if x.strip()],note=note)
            st.success(f"{rec['name']} atualizada sem apagar a versão anterior.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível atualizar: {exc}")
    hist=platform_history(sel_id)
    if hist:
        st.write(f"Histórico preservado: **{len(hist)}** versão(ões) anterior(es).")

snapshot=registry_snapshot()
st.download_button("⬇️ Exportar snapshot do Platform Registry",data=json.dumps(snapshot,ensure_ascii=False,indent=2),file_name="faithbloom-platform-registry.json",mime="application/json")
st.caption(f"Registry: {snapshot['official_count']} perfis pré-configurados + {snapshot['custom_count']} personalizados. Perfis 'profile_only' precisam de revalidação/importação de requisitos antes de preflight automático completo.")

st.divider()
st.caption("FaithBloom 2.0 · Refinamento 07 · Publishing Platform Engine · Registry expansível · especificações versionadas · Book Master → derivados · EPUB · preflight por destino.")


def _unused():
    pass

"""Refinamento 05 — Coloring Book Doctor + Cover Master."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import streamlit as st

from estilo import aplicar_estilo, hero, section_title
from book_doctor import listar_projetos, carregar_relatorio
from restoration_studio import criar_plano_restauracao, extrair_assets_relatorio
from coloring_book_doctor import (
    AGE_PROFILES, OPCIONAIS_INTERIOR_COLORING,
    auditar_lote_colorir, carregar_relatorio_colorir, salvar_relatorio_colorir,
    gerar_plano_recuperacao, executar_recuperacao_lote, plano_acabamento_colorir,
    salvar_plano_editorial_colorir, carregar_plano_editorial_colorir,
)
from character_universe import listar_personagens_oficiais
from style_dna import listar_styles
from cover_master import (
    criar_cover_master, carregar_cover_master, montar_prompt_cover_master, referencias_cover,
    registrar_variacao_cover, aprovar_variacao_cover, registrar_edicao_localizada,
    montar_wrap_aprovado, preflight_cover_master,
)

st.set_page_config(page_title="Coloring Book Doctor", page_icon="🖍️", layout="wide")
aplicar_estilo()
hero(
    "🖍️ Coloring Book Doctor",
    "Audite line arts por faixa etária, planeje recuperação em lote, preserve personagens/Style DNA e construa um Cover Master profissional sem alterar o original.",
)
st.info("🔒 Diagnosticar primeiro, corrigir depois. Nenhum lote é alterado automaticamente e nenhuma versão original é sobrescrita.")

projetos = [p for p in listar_projetos() if p.get("tipo_projeto") == "coloring"]
if not projetos:
    st.warning("Ainda não existe um projeto Book Doctor do tipo Coloring / Line Art.")
    st.page_link("pages/16_🩺_Book_Doctor.py", label="🩺 Importar Coloring Book no Book Doctor →", use_container_width=True)
    st.stop()

pid = st.selectbox("Projeto Coloring Book", [p["id"] for p in projetos], format_func=lambda x: next(f"{p.get('titulo')} · {p.get('status_publicacao')}" for p in projetos if p["id"] == x))
projeto = next(p for p in projetos if p["id"] == pid)
rel_base = carregar_relatorio(projeto)
plan_rest = criar_plano_restauracao(projeto, rel_base, "coloring", projeto.get("status_publicacao"), projeto.get("colecao", ""))
assets = [a for a in extrair_assets_relatorio(rel_base) if a.get("tipo") == "miolo" and a.get("arquivo") and Path(a["arquivo"]).exists()]

section_title("1 · Age & Complexity QA", "A faixa etária muda o nível de detalhe, espessura desejada e tolerância a microelementos. As métricas são heurísticas explicadas, não uma nota estética.", "Coloring QA")
perfil_ids = list(AGE_PROFILES)
perfil_id = st.selectbox("Perfil etário", perfil_ids, index=1, format_func=lambda x: AGE_PROFILES[x]["nome"])
st.caption(AGE_PROFILES[perfil_id]["orientacao"])
q1, q2 = st.columns(2)
final_w = q1.number_input("Largura final da página/arte (pol.) — opcional", min_value=0.0, value=0.0, step=0.125)
final_h = q2.number_input("Altura final da página/arte (pol.) — opcional", min_value=0.0, value=0.0, step=0.125)

if st.button("🔬 Auditar todas as line arts extraídas", type="primary", disabled=not assets):
    with st.spinner("Analisando line arts sem alterar arquivos..."):
        rel = auditar_lote_colorir(assets, perfil_id, final_w or None, final_h or None)
        salvar_relatorio_colorir(projeto, rel)
        st.session_state[f"color_report_{pid}"] = rel
    st.success("Auditoria especializada concluída. Nenhuma imagem foi modificada.")

rel = st.session_state.get(f"color_report_{pid}") or carregar_relatorio_colorir(projeto)
if rel:
    resumo = rel.get("resumo", {})
    a,b,c,d = st.columns(4)
    a.metric("🟢 Adequadas", resumo.get("adequada", 0))
    b.metric("🟡 Pequenos ajustes", resumo.get("ajustes", 0))
    c.metric("🟠 Atenção", resumo.get("atencao", 0))
    d.metric("🔴 Bloqueantes", resumo.get("bloqueante", 0))
    rows=[]
    for x in rel.get("assets", []):
        rows.append({
            "asset": x.get("asset_id"), "página": x.get("pagina"), "status": x.get("status"),
            "complexidade": x.get("complexidade_heuristica"), "traço": x.get("espessura_classe"),
            "cinzas %": x.get("cinza_pct"), "tinta borda %": x.get("borda_tinta_pct"),
            "componentes": x.get("componentes"),
            "PPI": (x.get("print_qa") or {}).get("ppi_efetivo"),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("Complexidade/traço são indicadores geométricos de triagem. O FaithBloom não usa esses números como avaliação de beleza ou criatividade.")

section_title("2 · Recuperação em lote", "O FaithBloom cria um plano por página. Você escolhe explicitamente quais assets podem receber correção determinística em cópia separada.", "Restoration")
if not rel:
    st.info("Rode a auditoria especializada para gerar o plano de recuperação.")
else:
    plano = gerar_plano_recuperacao(rel)
    st.dataframe(plano.get("itens", []), use_container_width=True, hide_index=True)
    candidatos = [x["asset_id"] for x in plano.get("itens", []) if x.get("acao_sugerida") == "normalizar_line_art"]
    selecionados = st.multiselect("Selecione line arts para normalizar em lote", candidatos, default=[])
    r1,r2,r3 = st.columns(3)
    threshold = r1.slider("Preto/branco", 150, 240, 205, 5)
    esp = r2.selectbox("Espessura", ["manter", "engrossar", "afinar"])
    fator = r3.selectbox("Upscale determinístico", [1,2,3,4], index=0)
    st.caption("O lote só executa limpeza/normalização determinística. Reilustração ou correção de personagem continuam individuais e exigem aprovação no Restoration Studio.")
    if st.button("🖍️ Criar cópias recuperadas dos selecionados", disabled=not selecionados):
        out = executar_recuperacao_lote(projeto, rel, selecionados, threshold, esp, fator)
        st.success(f"{out['executados']} cópia(s) derivada(s) criada(s). Originais preservados.")
    st.page_link("pages/19_✨_Restoration_Studio.py", label="✨ Abrir Restoration Studio para correções individuais/IA →", use_container_width=True)

section_title("3 · Miolo, opcionais & acabamento", "Escolha os elementos editoriais do Coloring Book antes da montagem final.", "Interior")
plano_salvo = carregar_plano_editorial_colorir(projeto)
opcionais = st.multiselect("Páginas/itens opcionais", OPCIONAIS_INTERIOR_COLORING, default=plano_salvo.get("opcionais_selecionados", []))
paginas_fisicas = st.number_input("Quantidade final prevista de páginas físicas", min_value=1, value=int(plano_salvo.get("paginas_fisicas", rel_base.get("miolo", {}).get("paginas_total", 72) if rel_base else 72)), step=1)
incluir_lombada = paginas_fisicas > 79
acabamento = plano_acabamento_colorir(opcionais, incluir_lombada)
with st.expander("📕 Ver essenciais de capa/acabamento", expanded=True):
    for item in acabamento["essenciais"]: st.write("✅ " + item)
    if incluir_lombada: st.caption("Com mais de 79 páginas, o motor de capa poderá considerar texto de lombada quando houver espaço físico suficiente.")
if st.button("💾 Salvar plano editorial do Coloring Book"):
    salvar_plano_editorial_colorir(projeto, {**acabamento, "paginas_fisicas": int(paginas_fisicas), "perfil_id": perfil_id})
    st.success("Plano editorial salvo no projeto.")

section_title("4 · Cover Master", "A arte da capa é versionada e pode usar personagens oficiais/Style DNA. Título e textos são aplicados depois pelo motor editorial; a IA não calcula o wrap.", "Cover Doctor")
cover = carregar_cover_master(projeto) or criar_cover_master(projeto, {"titulo": projeto.get("titulo"), "colecao": projeto.get("colecao", "")})
colecao = projeto.get("colecao", "")
characters = listar_personagens_oficiais(colecao or None)
styles = listar_styles(colecao or None)
char_ids = st.multiselect("Personagens oficiais na capa", [x["id"] for x in characters], format_func=lambda x: next(c.get("nome", x) for c in characters if c["id"] == x)) if characters else []
style_id = st.selectbox("Style DNA", [""] + [x["id"] for x in styles], format_func=lambda x: "— nenhum —" if not x else next(s.get("nome", x) for s in styles if s["id"] == x))
modo = st.selectbox("Direção da arte", ["colorido_fiel_line_art", "line_art", "preview_lapis"], format_func=lambda x: {"colorido_fiel_line_art":"🎨 Colorida fiel às line arts", "line_art":"🖍️ Line art como identidade", "preview_lapis":"✏️ Preview lápis de cor"}[x])
tema = st.text_input("Tema / cenário", placeholder="ex.: jardim alegre de primavera / Natal na neve / floresta")
instrucao = st.text_area("Instrução livre para a capa", placeholder="ex.: usar leão, girafa, coruja e gatinha; composição alegre, personagens bem visíveis, sem texto dentro da arte")
prompt = montar_prompt_cover_master(projeto.get("titulo", ""), char_ids, style_id, tema, instrucao, modo)
with st.expander("🧠 Prompt protegido de Cover Master"):
    st.code(prompt, language=None)
    st.caption("O prompt bloqueia texto gerado na arte e preserva Character/Style DNA. Tipografia será aplicada pelo motor de capa.")
refs = referencias_cover(char_ids, preferir_line_art=(modo != "colorido_fiel_line_art"))
if refs: st.caption(f"🧬 {len(refs)} referência(s) visual(is) oficial(is) disponível(is) para a geração.")

upload_dir = Path(projeto["pasta"]) / "cover_master" / "uploads"; upload_dir.mkdir(parents=True, exist_ok=True)
u1,u2 = st.columns(2)
front_up = u1.file_uploader("📕 Enviar arte da frente", type=["png","jpg","jpeg","webp"], key=f"front_{pid}")
back_up = u2.file_uploader("📗 Enviar arte da contracapa", type=["png","jpg","jpeg","webp"], key=f"back_{pid}")
for papel, up in (("frente", front_up), ("verso", back_up)):
    if up and st.button(f"➕ Salvar {papel} como nova variação", key=f"save_{papel}_{pid}"):
        ext = Path(up.name).suffix.lower() or ".png"
        path = upload_dir / f"{papel}_{uuid.uuid4().hex[:8]}{ext}"; path.write_bytes(up.getvalue())
        registrar_variacao_cover(projeto, papel, str(path), "upload_autora")
        st.success(f"Variação de {papel} salva sem apagar anteriores."); st.rerun()

if os.environ.get("OPENROUTER_API_KEY"):
    st.warning("Gerar arte com IA pode consumir créditos. A saída será uma nova variação e não substituirá nenhuma capa existente.")
    if st.button("✨ Gerar nova arte de frente com Character/Style DNA"):
        from openrouter_client import gerar_imagem
        with st.spinner("Gerando arte master sem texto..."):
            out = gerar_imagem(prompt=prompt, imagens_referencia=refs)
        registrar_variacao_cover(projeto, "frente", out, "ia_cover_master", {"prompt": prompt, "character_ids": char_ids, "style_id": style_id})
        st.success("Nova variação de frente criada."); st.rerun()
else:
    st.caption("🔐 Sem OPENROUTER_API_KEY nesta sessão: o plano/prompt e uploads funcionam normalmente, sem gasto de créditos.")

cover = carregar_cover_master(projeto)
for papel, titulo_papel in (("frente","Frente"),("verso","Contracapa")):
    itens = [x for x in cover.get("variacoes", []) if x.get("papel") == papel]
    if itens:
        st.markdown(f"#### {titulo_papel} — versões preservadas")
        cols = st.columns(min(3, len(itens)))
        for idx, item in enumerate(itens):
            with cols[idx % len(cols)]:
                if Path(item.get("asset", "")).exists(): st.image(item["asset"], use_container_width=True)
                st.caption(f"{item['id']} · {item.get('origem')} · {'✅ selecionada' if item.get('selecionada') else 'não selecionada'}")
                if st.button("✅ Aprovar/selecionar", key=f"approve_cover_{item['id']}"):
                    aprovar_variacao_cover(projeto, item["id"]); st.rerun()

st.markdown("#### 🌍 Texto localizado sobre a mesma arte Master")
loc1,loc2 = st.columns(2)
locale = loc1.selectbox("Edição", ["pt-BR","en-US","es","ja-JP","fr","it","de"])
titulo_loc = loc2.text_input("Título desta edição", value=projeto.get("titulo", ""), key=f"title_loc_{locale}")
sub_loc = st.text_input("Subtítulo", key=f"sub_loc_{locale}")
sinopse = st.text_area("Texto da contracapa / sinopse", key=f"blurb_{locale}")
if st.button("💾 Salvar textos desta edição"):
    registrar_edicao_localizada(projeto, locale, titulo_loc, sub_loc, sinopse)
    st.success("Edição vinculada ao mesmo Cover Master; a arte não foi duplicada.")

st.markdown("#### 🖨️ Montagem física do wrap")
c1,c2,c3,c4 = st.columns(4)
trim_w = c1.number_input("Trim W (pol.)", min_value=1.0, value=8.5, step=0.125)
trim_h = c2.number_input("Trim H (pol.)", min_value=1.0, value=8.5, step=0.125)
paginas = c3.number_input("Páginas", min_value=24, value=max(24, int(paginas_fisicas)), step=2)
papel = c4.selectbox("Papel", ["cor_premium", "cor_padrao", "branco", "creme"])
autora = st.text_input("Autor(a) / crédito de capa", value="")
colecao_capa = st.text_input("Coleção", value=colecao)
if st.button("📐 Montar capa Print Ready", type="primary"):
    try:
        ed = (carregar_cover_master(projeto).get("edicoes_localizadas", {}) or {}).get(locale, {})
        pasta_saida = str(Path(projeto["pasta"]) / "cover_master" / "print_ready" / locale)
        result = montar_wrap_aprovado(
            projeto, pasta_saida, trim_w, trim_h, int(paginas), papel,
            ed.get("titulo", titulo_loc), ed.get("subtitulo", sub_loc), autora, colecao_capa,
            ed.get("sinopse", sinopse),
        )
        st.success("Wrap criado matematicamente. A IA não posicionou lombada/bleed/barcode.")
        st.image(result["caminho_preview"], use_container_width=True)
        st.write(result.get("pdf_preflight"))
    except Exception as exc:
        st.error(str(exc))

pf = preflight_cover_master(projeto)
st.markdown("#### ✅ Cover Master Quality Gate")
for nome, ok in pf["checks"].items(): st.write(("✅" if ok else "⬜") + " " + nome.replace("_", " ").capitalize())
st.caption(pf["nota"])

st.info("Refinamento 05: este Quality Gate cobre Coloring/Line Art e Cover Master. O FaithBloom Quality Guardian final, independente e multidisciplinar, continua reservado para um refinamento posterior.")

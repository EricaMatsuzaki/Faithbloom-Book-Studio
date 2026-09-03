"""Interface do FaithBloom Coloring Book Studio 2.0 (Fase 8).

Objetivos:
- projetos infantis, juvenis e adultos;
- múltiplas origens para cada página;
- presets ilimitados e reutilizáveis;
- Galeria + Biblioteca de Personagens;
- variações sem apagar a original;
- prompt livre por página;
- aprovação antes de finalizar o livro.
"""
from __future__ import annotations
from author_profiles import author_display_from_state, list_author_profiles, profile_display_name, set_project_authors

import os
import shutil
import uuid

import streamlit as st
from family_profiles import assign_saved_project_to_profile

from state_colorir import LivroColorirState, PaginaColorir
from openrouter_client import chamar_llm, gerar_imagem
from agents.gerador_ideias_colorir import gerador_ideias_colorir_node
from agents.line_art_colorir import gerar_pagina_colorir, gerar_variacao_line_art, criar_registro_variacao
from agents.diagramador_colorir import diagramador_colorir_node
from armazenamento import (
    salvar_livro_colorir, listar_livros_colorir, temas_colorir_usados,
    salvar_asset_marca, listar_galeria, salvar_na_galeria,
    carregar_biblioteca_personagens, listar_colecoes,
)
from capa_profissional import gerar_capa_print_ready

from coloring_presets import (
    PUBLICOS, FAIXAS_ETARIAS, ESPESSURAS, COMPLEXIDADES, FUNDOS,
    listar_presets, obter_preset, salvar_preset, duplicar_preset, excluir_preset,
)

UPLOAD_DIR = "uploads_colorir"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ORIGENS = {
    "🤖 Gerar com IA": "gerar_ia",
    "✍️ Prompt livre": "prompt_livre",
    "🖼️ Usar Line Art pronta": "imagem_enviada",
    "📷 Foto real → Line Art": "foto_real",
    "🎨 Ilustração/Imagem → Line Art": "imagem_enviada_converter",
    "🖼️ Imagem da Galeria → Line Art": "galeria",
    "👥 Personagem da Biblioteca → Line Art": "biblioteca_personagem",
}


def _salvar_upload(upload, prefixo: str) -> str:
    ext = os.path.splitext(upload.name)[1].lower() or ".png"
    caminho = os.path.join(UPLOAD_DIR, f"{prefixo}-{uuid.uuid4().hex}{ext}")
    with open(caminho, "wb") as f:
        f.write(upload.getvalue())
    return caminho


def _preset_atual(state: dict, pagina: dict | None = None) -> dict:
    pid = (pagina or {}).get("preset_id") or state.get("preset_padrao_id")
    preset = obter_preset(pid) if pid else None
    if preset:
        return preset
    presets = listar_presets()
    return presets[0] if presets else {}


def _registrar_variacao_inicial(pagina: dict) -> None:
    caminho = pagina.get("caminho_arquivo")
    if not caminho:
        return
    pagina.setdefault("variacoes", [])
    if not any(v.get("caminho_arquivo") == caminho for v in pagina["variacoes"]):
        v = criar_registro_variacao(caminho, pagina.get("origem", "existente"), base=pagina.get("imagem_referencia", ""))
        pagina["variacoes"].append(v)
        pagina["variacao_selecionada_id"] = v["id"]


def _gerar_uma_pagina(state: dict, pagina: dict) -> str:
    preset = _preset_atual(state, pagina)
    origem = pagina.get("origem", "gerar_ia")
    if origem == "imagem_enviada":
        # Já é uma line art pronta: reutiliza sem crédito.
        return pagina.get("caminho_imagem_enviada") or pagina.get("imagem_referencia", "")

    referencia = pagina.get("imagem_referencia") or pagina.get("caminho_foto_original") or pagina.get("caminho_imagem_enviada")
    transformar = origem in {"foto_real", "imagem_enviada_converter", "galeria", "biblioteca_personagem"}
    return gerar_pagina_colorir(
        pagina.get("nome", ""), pagina.get("categoria", ""), pagina.get("cena", ""), gerar_imagem,
        sexo=pagina.get("sexo") or None,
        imagem_referencia=referencia,
        preset=preset,
        prompt_livre=pagina.get("prompt_livre", ""),
        instrucao_extra=pagina.get("prompt_adicional", ""),
        transformar_referencia=transformar,
    )


def _render_presets(state: dict):
    st.subheader("🎨 Meus estilos de Line Art")
    st.caption("Salve quantos estilos quiser. O preset define o padrão do livro; cada página ainda pode receber um prompt extra sem alterar o estilo salvo.")

    presets = listar_presets()
    nomes = {p["id"]: ("⭐ " if p.get("favorito") else "") + p.get("nome", "Estilo") for p in presets}
    ids = list(nomes)
    atual = state.get("preset_padrao_id") or (ids[0] if ids else "")
    idx = ids.index(atual) if atual in ids else 0
    escolhido = st.selectbox("Estilo padrão deste livro", ids, index=idx, format_func=lambda x: nomes.get(x, x)) if ids else None
    if escolhido:
        state["preset_padrao_id"] = escolhido
        p = obter_preset(escolhido) or {}
        st.info(
            f"**{p.get('publico','')} · {p.get('faixa_etaria','')}** — "
            f"traço {p.get('espessura','').lower()}, complexidade {p.get('complexidade','').lower()}, fundo {p.get('fundo','').lower()}."
        )

    with st.expander("➕ Criar e salvar novo estilo"):
        nome = st.text_input("Nome do estilo", placeholder="ex: Erica — Paisagens Relaxantes")
        c1, c2 = st.columns(2)
        publico = c1.selectbox("Público", PUBLICOS, key="preset_publico")
        faixa = c2.selectbox("Faixa/nível", FAIXAS_ETARIAS, key="preset_faixa")
        c3, c4, c5 = st.columns(3)
        esp = c3.selectbox("Contorno", ESPESSURAS, key="preset_esp")
        comp = c4.selectbox("Complexidade", COMPLEXIDADES, key="preset_comp")
        fundo = c5.selectbox("Fundo", FUNDOS, key="preset_fundo")
        areas = st.text_input("Áreas para colorir", placeholder="ex: grandes e médias; evitar microáreas")
        realismo = st.text_input("Direção visual", placeholder="ex: fofo e arredondado / botânico elegante / geométrico")
        base = st.text_area("Prompt-base do estilo", placeholder="Regras que devem se repetir em todas as páginas desse estilo...")
        fav = st.checkbox("⭐ Favoritar este estilo")
        if st.button("💾 Salvar estilo", type="primary", disabled=not nome.strip()):
            novo = salvar_preset({
                "nome": nome, "publico": publico, "faixa_etaria": faixa,
                "espessura": esp, "complexidade": comp, "fundo": fundo,
                "areas": areas, "nivel_realismo": realismo, "prompt_base": base,
                "favorito": fav,
            })
            state["preset_padrao_id"] = novo["id"]
            st.success("Estilo salvo. Ele poderá ser usado em outros livros.")
            st.rerun()

    if escolhido:
        p = obter_preset(escolhido) or {}
        c1, c2 = st.columns(2)
        if c1.button("📑 Duplicar estilo selecionado"):
            novo = duplicar_preset(escolhido)
            state["preset_padrao_id"] = novo["id"]
            st.success("Cópia criada. Você pode usá-la como base para outro padrão.")
            st.rerun()
        if c2.button("🗑️ Excluir estilo selecionado", disabled=bool(p.get("sistema"))):
            if excluir_preset(escolhido):
                state["preset_padrao_id"] = ""
                st.rerun()


def _pagina_from_form(state: dict) -> dict | None:
    origem_label = st.selectbox("Como você quer criar esta página?", list(ORIGENS))
    origem = ORIGENS[origem_label]
    nome = st.text_input("Nome da página", placeholder="ex: Coelhinha lendo perto da janela")
    categoria = st.text_input("Categoria/assunto", placeholder="ex: coelho, flores, paisagem, mandala")
    sexo = ""
    if state.get("precisa_codigo_sexo"):
        sexo = st.selectbox("Código visual (opcional)", ["", "macho", "femea"])
    cena = st.text_area("Cena/pose", placeholder="Descreva o que acontece na página")
    prompt_livre = ""
    referencia = ""
    uploaded_path = ""
    galeria_id = ""
    personagem_nome = ""

    if origem == "prompt_livre":
        prompt_livre = st.text_area("✍️ Escreva exatamente o desenho que deseja", placeholder="Uma cabana aconchegante entre flores, line art relaxante...")
    elif origem in {"imagem_enviada", "foto_real", "imagem_enviada_converter"}:
        label = "Envie a Line Art pronta" if origem == "imagem_enviada" else ("Envie a foto real" if origem == "foto_real" else "Envie a ilustração/imagem")
        up = st.file_uploader(label, type=["png", "jpg", "jpeg", "webp"], key=f"up_{origem}")
        if up:
            uploaded_path = _salvar_upload(up, origem)
            referencia = uploaded_path
            st.image(up, width=240)
    elif origem == "galeria":
        itens = listar_galeria()
        validos = [i for i in itens if os.path.exists(i.get("caminho_arquivo", ""))]
        if not validos:
            st.warning("Sua Galeria ainda não possui imagens disponíveis neste ambiente.")
        else:
            ids = [i["id"] for i in validos]
            selected_from_library = st.session_state.get("faithbloom_selected_asset_id", "")
            default_idx = ids.index(selected_from_library) if selected_from_library in ids else 0
            if selected_from_library in ids:
                st.caption("🖼️ Asset pré-selecionado no Asset Library & Media Manager.")
            escolhido = st.selectbox("Escolha uma imagem da Galeria / Asset Library", ids, index=default_idx, format_func=lambda x: next(i.get("nome", x) for i in validos if i["id"] == x))
            item = next(i for i in validos if i["id"] == escolhido)
            referencia = item["caminho_arquivo"]; galeria_id = item["id"]
            st.image(referencia, width=240)
    elif origem == "biblioteca_personagem":
        colecoes = listar_colecoes()
        colecao = st.selectbox("Coleção da Biblioteca", colecoes) if colecoes else st.text_input("Nome da coleção")
        biblioteca = carregar_biblioteca_personagens(colecao) if colecao else {}
        personagens = [(k, v) for k, v in biblioteca.items() if v.get("imagem_referencia") and os.path.exists(v.get("imagem_referencia", ""))]
        if not personagens:
            st.warning("Nenhum personagem com referência visual disponível nesta coleção neste ambiente.")
        else:
            keys = [k for k, _ in personagens]
            personagem_nome = st.selectbox("Personagem", keys, format_func=lambda k: biblioteca[k].get("nome", k))
            referencia = biblioteca[personagem_nome]["imagem_referencia"]
            st.image(referencia, width=240)

    prompt_extra = st.text_area(
        "✨ Instrução adicional só para esta página (opcional)",
        placeholder="ex: quero mais delicado, menos detalhes no fundo, flores maiores...",
    )
    presets = listar_presets()
    pids = [p["id"] for p in presets]
    default = state.get("preset_padrao_id")
    idx = pids.index(default) if default in pids else 0
    preset_id = st.selectbox("Estilo desta página", pids, index=idx, format_func=lambda x: next(p["nome"] for p in presets if p["id"] == x)) if pids else ""

    if st.button("➕ Adicionar página ao projeto", type="primary", disabled=not (nome.strip() or prompt_livre.strip())):
        pagina = PaginaColorir(
            nome=nome or "Página sem título", categoria=categoria, sexo=sexo, cena=cena,
            origem=origem, prompt_livre=prompt_livre, prompt_adicional=prompt_extra,
            imagem_referencia=referencia, preset_id=preset_id, variacoes=[], aprovada=False,
            status="pronta" if origem == "imagem_enviada" and referencia else "aguardando",
            galeria_item_id=galeria_id, personagem_nome=personagem_nome,
        )
        if origem == "foto_real": pagina["caminho_foto_original"] = uploaded_path
        if origem in {"imagem_enviada", "imagem_enviada_converter"}: pagina["caminho_imagem_enviada"] = uploaded_path
        if origem == "imagem_enviada" and referencia:
            pagina["caminho_arquivo"] = referencia
            _registrar_variacao_inicial(pagina)
        return pagina
    return None


def _render_pagina_card(state: dict, pagina: dict, i: int):
    with st.container(border=True):
        ctitle, cstatus = st.columns([4, 1])
        ctitle.markdown(f"### {i+1}. {pagina.get('nome','Página')}")
        cstatus.caption("✅ aprovada" if pagina.get("aprovada") else "🟡 em edição")
        st.caption(f"Origem: {pagina.get('origem','')} · Estilo: {(_preset_atual(state,pagina) or {}).get('nome','')}")
        if pagina.get("caminho_arquivo") and os.path.exists(pagina["caminho_arquivo"]):
            st.image(pagina["caminho_arquivo"], width=360)

        c1, c2, c3, c4 = st.columns(4)
        if c1.button("✨ Gerar" if not pagina.get("caminho_arquivo") else "🔄 Nova versão", key=f"gen_c_{i}"):
            with st.spinner("Criando line art..."):
                caminho = _gerar_uma_pagina(state, pagina)
            pagina["caminho_arquivo"] = caminho
            pagina["status"] = "pronta"
            pagina["aprovada"] = False
            _registrar_variacao_inicial(pagina)
            st.rerun()

        if c2.button("✅ Aprovar", key=f"ap_c_{i}", disabled=not pagina.get("caminho_arquivo")):
            pagina["aprovada"] = True; pagina["status"] = "aprovada"; st.rerun()
        if c3.button("💾 Galeria", key=f"gal_c_{i}", disabled=not pagina.get("caminho_arquivo")):
            item = salvar_na_galeria(
                pagina["caminho_arquivo"], pagina.get("nome", "Line Art"), tipo="line_art",
                tags=[pagina.get("categoria", ""), state.get("publico", "")],
                metadata={"origem": "coloring_studio", "titulo_livro": state.get("titulo", "")},
            )
            st.success(f"Salva na Galeria: {item['nome']}")
        if c4.button("🗑️ Remover", key=f"del_c_{i}"):
            state["paginas"].pop(i); st.rerun()

        if pagina.get("caminho_arquivo"):
            with st.expander("🔀 Criar variação desta imagem"):
                instr = st.text_area(
                    "O que deseja mudar?",
                    placeholder="Mantenha a composição; deixe o coelhinho menor, mais fofo e com menos detalhes no fundo...",
                    key=f"var_prompt_{i}",
                )
                if st.button("✨ Criar variação sem apagar a atual", key=f"var_btn_{i}", disabled=not instr.strip()):
                    preset = _preset_atual(state, pagina)
                    with st.spinner("Criando variação..."):
                        v = gerar_variacao_line_art(pagina, gerar_imagem, preset=preset, instrucao=instr)
                    pagina.setdefault("variacoes", []).append(v)
                    pagina["caminho_arquivo"] = v["caminho_arquivo"]
                    pagina["variacao_selecionada_id"] = v["id"]
                    pagina["aprovada"] = False
                    st.rerun()

            variacoes = pagina.get("variacoes", [])
            if len(variacoes) > 1:
                st.markdown("**Histórico de versões — nenhuma é apagada automaticamente**")
                cols = st.columns(min(4, len(variacoes)))
                for vi, v in enumerate(variacoes):
                    col = cols[vi % len(cols)]
                    if os.path.exists(v.get("caminho_arquivo", "")):
                        col.image(v["caminho_arquivo"], caption=f"Opção {vi+1}")
                        if col.button("Usar esta", key=f"usar_var_{i}_{v['id']}"):
                            pagina["caminho_arquivo"] = v["caminho_arquivo"]
                            pagina["variacao_selecionada_id"] = v["id"]
                            pagina["aprovada"] = False
                            st.rerun()


def render_coloring_studio():
    with st.sidebar:
        st.subheader("🖍️ Coloring Book Studio")
        for livro in listar_livros_colorir()[:8]:
            st.caption(f"• {livro['titulo']}")

    if "state_c" not in st.session_state:
        st.session_state.state_c = LivroColorirState(paginas=[])
    if "etapa_c" not in st.session_state:
        st.session_state.etapa_c = "entrada"
    s = st.session_state.state_c

    if st.session_state.etapa_c == "entrada":
        st.subheader("Novo projeto")
        c1, c2 = st.columns(2)
        s["publico"] = c1.selectbox("Público", PUBLICOS, index=PUBLICOS.index(s.get("publico", "Infantil")) if s.get("publico") in PUBLICOS else 0)
        faixas = FAIXAS_ETARIAS
        s["faixa_etaria"] = c2.selectbox("Faixa etária / nível", faixas, index=faixas.index(s.get("faixa_etaria", "4–8 anos")) if s.get("faixa_etaria") in faixas else 3)
        s["titulo"] = st.text_input("Título do livro", s.get("titulo", ""))
        profiles = list_author_profiles()
        if profiles:
            pm={p["id"]:p for p in profiles}
            current=[x.get("profile_id") for x in (s.get("authorship") or {}).get("authors",[]) if x.get("profile_id") in pm]
            selected=st.multiselect("Autoria deste livro",options=list(pm),default=current,format_func=lambda pid:profile_display_name(pm[pid]),key="coloring_authors")
            if selected:
                s.update(set_project_authors(s,selected))
        else:
            s["autora"] = st.text_input("Autor(a) / nome de publicação", value=s.get("autora", ""), key="coloring_legacy_author")
            st.caption("Crie perfis reutilizáveis em ✍️ Autores & Colaboradores.")
        s["tema_geral"] = st.text_input("Tema geral", s.get("tema_geral", ""), placeholder="ex: Casinhas aconchegantes na floresta")
        s["precisa_codigo_sexo"] = st.checkbox("Usar código visual de personagens macho/fêmea", value=s.get("precisa_codigo_sexo", False))

        with st.expander("📐 Formato e marca"):
            c3,c4=st.columns(2)
            s["trim_largura_in"] = c3.number_input("Largura (in)", value=float(s.get("trim_largura_in",8.5)), step=.25)
            s["trim_altura_in"] = c4.number_input("Altura (in)", value=float(s.get("trim_altura_in",8.5)), step=.25)
            s["colecao"] = st.text_input("Coleção / selo", s.get("colecao", ""))
            selo=st.file_uploader("Selo PNG", type=["png"], key="c_selo8")
            faixa=st.file_uploader("Faixa PNG", type=["png"], key="c_faixa8")
            if selo and s.get("colecao"): salvar_asset_marca(s["colecao"],"selo",selo.getvalue())
            if faixa and s.get("colecao"): salvar_asset_marca(s["colecao"],"faixa",faixa.getvalue())

        _render_presets(s)

        st.divider()
        modo = st.radio("Ideia do projeto", ["Já tenho a ideia", "✨ Quero sugestões da IA"], horizontal=True)
        if modo.startswith("✨") and st.button("Sugerir 4 temas"):
            with st.spinner("Criando ideias..."):
                resp = gerador_ideias_colorir_node(4, temas_colorir_usados(), chamar_llm)
            st.session_state.ideias_colorir = resp if isinstance(resp, list) else resp.get("ideias", [])
        for ideia in st.session_state.get("ideias_colorir", []):
            with st.container(border=True):
                st.markdown(f"**{ideia.get('titulo_sugerido','')}**")
                st.write(ideia.get("tema_geral", ""))
                if st.button("Usar esta ideia", key=f"tema8_{ideia.get('titulo_sugerido','')}"):
                    s["titulo"] = ideia.get("titulo_sugerido", "")
                    s["tema_geral"] = ideia.get("tema_geral", "")
                    st.rerun()

        if st.button("Continuar para as páginas", type="primary", disabled=not s.get("titulo") or not s.get("tema_geral")):
            st.session_state.etapa_c="paginas"; st.rerun()

    elif st.session_state.etapa_c == "paginas":
        st.subheader(f"🖍️ {s.get('titulo','')}")
        st.caption(f"{s.get('publico','')} · {s.get('faixa_etaria','')} · {s.get('tema_geral','')}")
        cback, cstyle = st.columns([1,3])
        if cback.button("← Configurações"): st.session_state.etapa_c="entrada"; st.rerun()
        with cstyle.expander("🎨 Trocar/criar estilos"):
            _render_presets(s)

        st.markdown("### ➕ Adicionar página")
        nova = _pagina_from_form(s)
        if nova:
            s.setdefault("paginas", []).append(nova); st.rerun()

        st.divider()
        st.markdown(f"### Páginas do projeto ({len(s.get('paginas',[]))})")
        for i,p in list(enumerate(s.get("paginas", []))):
            _render_pagina_card(s,p,i)

        aprovadas=sum(1 for p in s.get("paginas",[]) if p.get("aprovada"))
        st.progress(aprovadas/max(1,len(s.get("paginas",[]))), text=f"{aprovadas}/{len(s.get('paginas',[]))} páginas aprovadas")
        if st.button("📐 Diagramar projeto aprovado", type="primary", disabled=not s.get("paginas") or aprovadas != len(s.get("paginas",[]))):
            s.update(diagramador_colorir_node(dict(s)))
            caminho=salvar_livro_colorir(dict(s)); assign_saved_project_to_profile(st.session_state.get("faithbloom_workspace_profile_id", ""), "coloring", caminho, dict(s)); st.session_state.caminho_salvo_c=caminho
            st.session_state.etapa_c="resultado"; st.rerun()

    elif st.session_state.etapa_c == "resultado":
        st.success("Projeto de colorir diagramado e salvo.")
        st.caption(st.session_state.get("caminho_salvo_c", ""))
        if s.get("checklist_kdp"): st.json(s["checklist_kdp"])
        st.subheader("🖍️ Páginas aprovadas")
        cols=st.columns(3)
        for i,p in enumerate(s.get("paginas",[])):
            if p.get("caminho_arquivo") and os.path.exists(p["caminho_arquivo"]):
                cols[i%3].image(p["caminho_arquivo"], caption=p.get("nome",""))
        st.divider()
        st.subheader("📕 Capa física profissional")
        st.caption("A arte é gerada separadamente; o FaithBloom monta contracapa + lombada + frente matematicamente, preservando as melhorias da Fase 7.")
        if st.button("✨ Gerar artes e montar capa paperback", disabled=not s.get("paginas")):
            referencia = next((p.get("caminho_arquivo") for p in s.get("paginas", []) if p.get("caminho_arquivo")), None)
            prompt_frente = (
                f"Arte COLORIDA original para capa de livro de colorir chamado '{s.get('titulo','')}'. "
                f"Tema: {s.get('tema_geral','')}. Manter coerência visual com a referência do miolo, "
                "cores planas/limpas, composição atraente, SEM texto, título, logotipo ou barcode. "
                "Deixar respiro visual na parte superior para tipografia posterior."
            )
            prompt_verso = (
                f"Arte COLORIDA original e mais discreta para CONTRACAPA do livro '{s.get('titulo','')}', "
                f"tema {s.get('tema_geral','')}. Mesma linguagem visual da capa e do miolo, SEM texto, "
                "sem barcode desenhado, com áreas calmas para sinopse e código de barras serem colocados depois."
            )
            with st.spinner("Gerando artes de frente e verso..."):
                frente = gerar_imagem(prompt=prompt_frente, imagem_base=referencia)
                verso = gerar_imagem(prompt=prompt_verso, imagem_base=referencia)
                pasta_saida = os.path.join("exportacoes_kdp", "colorir-" + uuid.uuid4().hex[:10])
                capa = gerar_capa_print_ready(
                    frente, verso, pasta_saida,
                    trim_w=float(s.get("trim_largura_in", 8.5)),
                    trim_h=float(s.get("trim_altura_in", 8.5)),
                    paginas=int(s.get("paginas_fisicas_total") or max(24, len(s.get("paginas", []))*2)),
                    papel="cor_premium", titulo=s.get("titulo", ""), subtitulo=s.get("tema_geral", ""),
                    autora=author_display_from_state(s), colecao=s.get("colecao", ""),
                    sinopse="Livro de colorir criado no FaithBloom Book Studio.",
                    reservar_barcode=True,
                )
            s["capa_fisica_wrap"] = capa["caminho_pdf"]
            s["capa_fisica_dimensoes"] = capa
            st.session_state.capa_colorir_phase8 = capa
            st.rerun()

        capa = st.session_state.get("capa_colorir_phase8") or s.get("capa_fisica_dimensoes")
        if isinstance(capa, dict) and capa.get("caminho_preview") and os.path.exists(capa["caminho_preview"]):
            st.image(capa["caminho_preview"], caption="Prévia técnica da capa com guias", use_container_width=True)
            if capa.get("caminho_pdf") and os.path.exists(capa["caminho_pdf"]):
                with open(capa["caminho_pdf"], "rb") as f:
                    st.download_button("⬇️ Baixar capa física Print Ready (PDF)", f, file_name="capa_colorir_print_ready.pdf")

        st.info("A Fase 6 continua sendo o motor do PDF Print Ready do miolo; a Fase 8 concentra a criação, reutilização, variações e aprovação das line arts.")
        if st.button("Novo Coloring Book"):
            st.session_state.state_c=LivroColorirState(paginas=[]); st.session_state.etapa_c="entrada"; st.rerun()

"""Specialist product studio: author brief, generation, review and shared exports."""
from copy import deepcopy
from pathlib import Path

import streamlit as st

from ai_provider_router import provider_status
from controle_geracao import estimar_custo
from editorial_products import (
    PRODUCT_DNAS, MAX_UNITS, create_product, generate_product, validate_product,
    save_product, load_product, list_products, revise_unit, approve_product,
    restore_version, export_product, compatible_audiences,
)
from estilo import aplicar_estilo, hero, section_title
from orchestrator_editorial import AUDIENCES, EDITORIAL_LINES, ORIGINS, PROJECT_TYPES
from storage_backend import materializar

st.set_page_config(page_title="Produtos Editoriais · FaithBloom", page_icon="📚", layout="wide")
aplicar_estilo()
hero("Produtos Editoriais", "Conselhos, devocionais, estudos, exercícios e cartões — com estruturas próprias, versões e revisão humana.", "Estúdio editorial")
st.caption("A IA propõe conteúdo. Você confere precisão, adequação ao público, fontes e gabaritos antes de aprovar.")

# The central dispatcher can open either a canonical saved ref or the book ID.
requested = st.session_state.get("editorial_product_id")
if requested and requested != st.session_state.get("editorial_product_opened_id"):
    try:
        saved_ref = requested if str(requested).startswith(("fb://", "livros/")) else next(
            (item["storage_path"] for item in list_products() if load_product(item["storage_path"])["book_id"] == requested), None)
        if not saved_ref:
            raise ValueError("Produto solicitado não foi encontrado na biblioteca.")
        st.session_state.editorial_product_state = load_product(saved_ref)
        st.session_state.editorial_product_opened_id = requested
    except Exception as exc:
        st.error(f"Não foi possível abrir o produto vindo do Orquestrador: {exc}")

mode = st.radio("Projeto", ["Criar novo", "Abrir existente"], horizontal=True)
if mode == "Abrir existente":
    try:
        saved = list_products()
    except Exception as exc:
        saved = []
        st.error(f"Não foi possível acessar a biblioteca: {exc}")
    if saved:
        chosen = st.selectbox("Produto salvo", [item["storage_path"] for item in saved],
                              format_func=lambda ref: next(f"{item['titulo']} · {item.get('colecao') or 'Sem coleção'} · {item['status']}" for item in saved if item["storage_path"] == ref))
        if st.button("Abrir produto"):
            try:
                st.session_state.editorial_product_state = load_product(chosen)
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível abrir o produto: {exc}")
    else:
        st.info("Ainda não há produtos especializados salvos.")
else:
    with st.expander("Criar um produto", expanded=not bool(st.session_state.get("editorial_product_state"))):
        kind = st.selectbox("Tipo de produto", list(PRODUCT_DNAS), format_func=lambda key: PROJECT_TYPES[key]["label"])
        hybrid = st.multiselect("Combinar com outros tipos (opcional)", [key for key in PRODUCT_DNAS if key != kind], format_func=lambda key: PROJECT_TYPES[key]["label"])
        a, b = st.columns(2)
        title = a.text_input("Título")
        collection = b.text_input("Coleção (opcional)")
        brief = st.text_area("O que este produto deve abordar?", placeholder="Tema, objetivo, contexto e o que a pessoa deve conseguir fazer após a leitura.")
        objectives = st.text_area("Objetivos de aprendizagem ou reflexão", placeholder="Um objetivo por linha.")
        a, b, c = st.columns(3)
        allowed_audiences = compatible_audiences([kind, *hybrid])
        if not allowed_audiences:
            st.warning("Esta combinação mistura DNAs infantis e adolescentes. Selecione tipos com um público em comum.")
        audience_options = allowed_audiences or [PRODUCT_DNAS[kind]["audience"]]
        default_audience = PRODUCT_DNAS[kind]["audience"]
        audience = a.selectbox("Público", audience_options, index=audience_options.index(default_audience) if default_audience in audience_options else 0, format_func=lambda key: AUDIENCES[key], key=f"editorial_audience_{kind}_{','.join(hybrid)}")
        line = b.selectbox("Linha editorial", list(EDITORIAL_LINES), format_func=lambda key: EDITORIAL_LINES[key])
        origin = c.selectbox("Origem", list(ORIGINS), format_func=lambda key: ORIGINS[key])
        a, b = st.columns(2)
        count = a.number_input("Unidades", min_value=len(hybrid) + 1, max_value=MAX_UNITS,
                               value=max(3, len(hybrid) + 1), step=1)
        language = b.text_input("Idioma", value="pt-BR")
        bible = st.text_input("Referência bíblica fornecida por você", placeholder="Ex.: Salmo 27:14") if any("devotional" in key for key in [kind, *hybrid]) else ""
        custom = st.text_area("Nomes dos blocos do produto personalizado", placeholder="Um nome por linha, na ordem desejada.") if "other" in [kind, *hybrid] else ""
        with st.expander("Fontes e materiais de referência", expanded=any(PRODUCT_DNAS[key]["family"] in {"study", "workbook", "flashcards"} for key in [kind, *hybrid])):
            st.caption("Cole os trechos que o produto pode usar. Links ficam registrados; esta etapa não baixa páginas da internet. Produtos de estudo, exercícios e cartões exigem fontes fornecidas.")
            source_count = st.number_input("Quantidade de fontes", min_value=0, max_value=10, value=0, step=1)
            sources = []
            for i in range(int(source_count)):
                label = st.text_input(f"Nome da fonte {i + 1}", key=f"editorial_source_label_{i}")
                url = st.text_input(f"Link da fonte {i + 1} (opcional)", key=f"editorial_source_url_{i}")
                content = st.text_area(f"Trecho ou conteúdo da fonte {i + 1}", key=f"editorial_source_content_{i}")
                sources.append({"id": f"source_{i + 1}", "label": label, "url": url, "content": content})
        if st.button("Criar e salvar projeto", type="primary", disabled=not title.strip() or not brief.strip() or not allowed_audiences):
            try:
                product = create_product(kind, title, brief, audience=audience, editorial_line=line, origin=origin,
                                         collection=collection, unit_count=int(count), sources=sources,
                                         bible_reference=bible, custom_blocks=[item.strip() for item in custom.splitlines() if item.strip()],
                                         hybrid_types=hybrid, language=language,
                                         objectives=[item.strip() for item in objectives.splitlines() if item.strip()] or None)
                st.session_state.editorial_product_state = product
                save_product(product)
                st.success("Projeto salvo. Gere as unidades quando estiver pronta.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível criar/salvar o projeto: {exc}")

project = st.session_state.get("editorial_product_state")
if not project:
    st.stop()
meta = project["editorial_product"]
section_title(project["titulo"], f"{AUDIENCES[meta['spec']['audience']]} · {project['idioma_original']} · {meta['status']}", "Seu produto")
with st.expander("Brief, objetivos e fontes do projeto"):
    st.write(meta["spec"]["brief"])
    for objective in meta["spec"]["objectives"]:
        st.write("• " + objective)
    for source in meta["spec"]["sources"]:
        st.write(source["label"])
        st.caption(source["content"])

section_title("Geração e retomada", "Cada unidade válida é salva antes da próxima. Ao retomar, unidades já concluídas são reutilizadas.", "Versões")
pending = len(meta["unit_plan"]) - len((meta.get("draft") or {}).get("units", []))
new_version = st.checkbox("Gerar uma nova versão preservando a atual", key=f"editorial_new_{project['book_id']}") if meta["units"] and not meta.get("draft") else False
st.caption(f"Plano: {len(meta['unit_plan'])} unidades · próximas chamadas: {pending if not meta['units'] or meta.get('draft') or new_version else 0} · estimativa do lote: US$ {estimar_custo('texto', pending):.2f}. A cobrança real depende do provedor.")
status = provider_status()
ready = any(status[key] for key in ("gemini", "groq", "openrouter"))
authorized = st.checkbox("Autorizo a geração das unidades pendentes e o custo do provedor", key=f"editorial_generation_confirm_{project['book_id']}")
personal_consent = False
personal_data_required = meta["spec"].get("origin") == "real_experience"
if personal_data_required:
    personal_consent = st.checkbox("Confirmo que tenho autorização para usar os dados pessoais destas fontes com o provedor de IA", key=f"editorial_data_consent_{project['book_id']}")
if not ready:
    st.info("Configure um provedor de texto para gerar com IA. Projetos existentes continuam disponíveis para revisão e exportação.")
if st.button("Gerar / retomar unidades", type="primary", disabled=not ready or not authorized or (personal_data_required and not personal_consent) or (bool(meta["units"]) and not meta.get("draft") and not new_version)):
    try:
        with st.spinner("Gerando e salvando cada unidade…"):
            generate_product(project, new_version=new_version, confirmed=authorized, consent_confirmed=personal_consent)
        st.success("Conteúdo gerado. Revise as unidades antes da aprovação.")
        st.rerun()
    except Exception as exc:
        st.error(f"A geração parou: {exc}")
        st.info("As unidades já recebidas permanecem neste projeto. Retome para salvar e continuar sem refazer os resultados preservados.")
if st.button("Salvar estado atual"):
    try:
        save_product(project)
        st.success("Estado salvo no mesmo projeto.")
    except Exception as exc:
        st.error(f"Não foi possível salvar: {exc}")

if meta.get("draft"):
    st.write(f"Versão em andamento: {len(meta['draft']['units'])}/{len(meta['unit_plan'])} unidades concluídas.")
    for unit in meta["draft"]["units"]:
        with st.expander(f"Rascunho · {unit['number']} · {unit['title']}"):
            st.write(unit["title"])
            for field, value in unit.items():
                if field not in {"title", "number", "family", "project_type", "source_refs"}:
                    if isinstance(value, str):
                        st.write(value)
                    elif field == "objectives":
                        for objective in value:
                            st.write("• " + objective)

if meta["units"]:
    section_title("Revisar as unidades", "Confira também os gabaritos e as referências; o validador automático verifica estrutura, sem certificar precisão.", "Revisão humana")
    for unit in meta["units"]:
        n = unit["number"]
        prefix = f"ed_{project['book_id']}_{meta['active_version']}_{n}"
        with st.expander(f"{n} · {unit['title']} · {PROJECT_TYPES[unit['project_type']]['label']}"):
            with st.form(prefix):
                revised = deepcopy(unit)
                revised["title"] = st.text_input("Título da unidade", value=unit["title"], key=prefix + "_title")
                revised["objectives"] = [item.strip() for item in st.text_area("Objetivos (um por linha)", value="\n".join(unit["objectives"]), key=prefix + "_objectives").splitlines() if item.strip()]
                source_ids = [source["id"] for source in meta["spec"]["sources"]]
                revised["source_refs"] = st.multiselect("Fontes utilizadas", source_ids, default=unit["source_refs"],
                                                         format_func=lambda ref: next(source["label"] for source in meta["spec"]["sources"] if source["id"] == ref), key=prefix + "_sources")
                labels = {"situation": "Situação", "advice": "Conselho", "reflection": "Reflexão", "activity": "Atividade",
                          "bible_reference": "Referência bíblica", "application": "Aplicação", "prayer": "Oração", "challenge": "Desafio",
                          "body": "Conteúdo", "progress_question": "Pergunta de acompanhamento", "instructions": "Instruções"}
                for field, label in labels.items():
                    if field in unit:
                        revised[field] = st.text_area(label, value=unit[field], key=prefix + "_" + field)
                if "action_plan" in unit:
                    revised["action_plan"] = [item.strip() for item in st.text_area("Plano de ação (uma ação por linha)", value="\n".join(unit["action_plan"]), key=prefix + "_actions").splitlines() if item.strip()]
                if "response_lines" in unit:
                    revised["response_lines"] = int(st.number_input("Linhas para responder", min_value=1, max_value=30, value=unit["response_lines"], key=prefix + "_lines"))
                for i, question in enumerate(unit.get("questions", [])):
                    st.write(f"Exercício {i + 1}")
                    for field, label in (("question", "Pergunta"), ("answer", "Gabarito"), ("explanation", "Explicação")):
                        revised["questions"][i][field] = st.text_area(label, value=question[field], key=f"{prefix}_q{i}_{field}")
                for i, card in enumerate(unit.get("cards", [])):
                    st.write(f"Cartão {i + 1}")
                    revised["cards"][i]["front"] = st.text_area("Frente", value=card["front"], key=f"{prefix}_card{i}_front")
                    revised["cards"][i]["back"] = st.text_area("Verso", value=card["back"], key=f"{prefix}_card{i}_back")
                    revised["cards"][i]["source_refs"] = st.multiselect("Fontes do cartão", source_ids, default=card["source_refs"], key=f"{prefix}_card{i}_sources")
                for i, block in enumerate(unit.get("blocks", [])):
                    revised["blocks"][i]["text"] = st.text_area(block["label"], value=block["text"], key=f"{prefix}_block{i}")
                if st.form_submit_button("Salvar revisão desta unidade", disabled=bool(meta.get("draft"))):
                    try:
                        revise_unit(project, n, revised)
                        st.success("Revisão salva e versão anterior preservada. A aprovação precisa ser renovada.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"A revisão não foi salva: {exc}")
    if meta["versions"]:
        with st.expander("Versões anteriores"):
            version_ids = list(dict.fromkeys(version["id"] for version in meta["versions"]))
            selected_version = st.selectbox("Versão para restaurar", version_ids)
            if st.button("Restaurar como proposta para revisão", disabled=bool(meta.get("draft"))):
                try:
                    restore_version(project, selected_version)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    report = validate_product(project)
    for error in report["errors"]:
        st.error(error)
    section_title("Aprovação e arquivos", "A aprovação registra sua revisão. A publicação continua passando pelas verificações da plataforma escolhida.", "Finalização")
    reviewer = st.text_input("Responsável pela revisão", key=f"editorial_reviewer_{project['book_id']}")
    reviewed = st.checkbox("Revisei conteúdo, linguagem e adequação ao público", key=f"editorial_content_review_{meta['active_version']}")
    accuracy = st.checkbox("Conferi precisão, fontes, referências bíblicas e gabaritos aplicáveis", key=f"editorial_accuracy_review_{meta['active_version']}")
    if st.button("Aprovar esta versão", disabled=not report["ok"] or not reviewer.strip() or not reviewed or not accuracy or bool(meta.get("draft"))):
        try:
            approve_product(project, reviewer, content_reviewed=reviewed, accuracy_reviewed=accuracy)
            st.success("Sua aprovação foi registrada nesta versão.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    st.write("Versão aprovada para exportação." if report["ready_for_final_export"] else "Versão ainda precisa da revisão humana para exportação final.")
    draft_export = st.checkbox("Exportar prévia de rascunho para revisão", value=not report["ready_for_final_export"], key=f"editorial_preview_{meta['active_version']}")
    export_format = st.selectbox("Formato", ["pdf", "epub"], format_func=str.upper)
    if st.button("Preparar arquivo", disabled=not report["ok"] or (not draft_export and not report["ready_for_final_export"])):
        try:
            result = export_product(project, export_format, draft=draft_export)
            st.success("Arquivo preparado e salvo no projeto.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível preparar o arquivo: {exc}")
    for index, artifact in enumerate(reversed(meta.get("exports", []))):
        try:
            local = materializar(artifact["storage_ref"])
            st.download_button(f"Baixar {artifact['format'].upper()} · {'rascunho' if artifact['draft'] else 'revisado'} · {artifact['at']}",
                               data=Path(local).read_bytes(), file_name=f"produto-{index + 1}.{artifact['format']}",
                               mime="application/pdf" if artifact["format"] == "pdf" else "application/epub+zip", key=f"editorial_download_{index}")
        except Exception as exc:
            st.error(f"Não foi possível recuperar um arquivo salvo: {exc}")
    st.caption("PDF de texto: conferir layout e prova física. EPUB: executar EPUBCheck e o preview da loja. Arquivos são preparados, sem publicação automática.")

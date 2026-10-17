"""Reviewable comic production from an exact source book, with real exports."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import tempfile

import streamlit as st

from armazenamento import carregar_livro, listar_livros
from comic_studio import (
    SCHEMA, approve_panel_image, approve_script, attach_panel_image, comic_readiness,
    create_comic, export_comic, generate_panel_images, generate_panel_options,
    generate_script, link_visual_plan, list_comics, load_comic, prepare_visual_plan,
    revise_panel, save_comic, select_panel_direction, link_panel_emotion, set_script, source_status, uses_personal_data,
)
from controle_geracao import estimar_custo
from estilo import aplicar_estilo, hero, section_title
from openrouter_client import texto_provedor_ativo
from orchestrator_visual import GENERATION_MODES, load_visual_plan, visual_preflight_status
from storage_backend import materializar, tenant_local_directory
from visual_execution import estimate_visual_operation


st.set_page_config(page_title="Quadrinhos · FaithBloom", page_icon="🗯️", layout="wide")
aplicar_estilo()
hero("Quadrinhos / HQ", "Da história escolhida aos painéis, balões editáveis e arquivos PDF e EPUB.", "Comic Studio")
st.caption("A HQ é uma obra derivada com identificação própria. A história de origem e os Masters oficiais são preservados.")


def action(callback):
    try:
        with st.spinner("Preparando e salvando..."):
            callback()
        st.rerun()
    except Exception as exc:
        st.error(str(exc))
        st.info("Os resultados concluídos permanecem no projeto. Salve novamente antes de solicitar outra geração.")


def data_consent(label, key, required):
    if not required:
        return False
    epoch = st.session_state.get(key + "_epoch", 0)
    return st.checkbox(label, key=f"{key}_{epoch}")


def provider_action(callback, consent_key):
    # A checked box authorizes this click only. A later version/panel request
    # displays a new unchecked control, including after a failed attempt.
    st.session_state[consent_key + "_epoch"] = st.session_state.get(consent_key + "_epoch", 0) + 1
    action(callback)


def canonical_source(reference):
    state = carregar_livro("", str(reference).removeprefix("fb://"))
    state["storage_path"] = "fb://" + str(reference).removeprefix("fb://")
    if not state.get("cenas_texto"):
        raise ValueError("A história escolhida ainda não contém texto para adaptar.")
    return state


# The dispatcher passes an exact reference/ID, never a title lookup.
requested = st.session_state.get("comic_project_id")
if requested and requested != st.session_state.get("comic_project_opened_id"):
    try:
        reference = str(requested) if str(requested).startswith(("fb://", "livros/")) else next(
            (item["storage_path"] for item in list_comics() if item["book_id"] == requested), "")
        if not reference:
            raise ValueError("A HQ solicitada não foi encontrada na biblioteca.")
        st.session_state.comic_project_state = load_comic(reference)
        st.session_state.comic_project_opened_id = requested
    except Exception as exc:
        st.error(f"Não foi possível abrir a HQ solicitada: {exc}")
        st.stop()

source_request = st.session_state.get("comic_source_ref")
if source_request and source_request != st.session_state.get("comic_source_opened_ref"):
    try:
        st.session_state.comic_source_state = canonical_source(source_request)
        st.session_state.comic_source_opened_ref = source_request
    except Exception as exc:
        st.error(f"Não foi possível abrir a história de origem: {exc}")
        st.stop()

mode = st.radio("Projeto de HQ", ["Criar a partir de uma história", "Abrir HQ salva"], horizontal=True)
if mode == "Abrir HQ salva":
    try:
        saved = list_comics()
    except Exception as exc:
        saved = []
        st.error(f"Não foi possível acessar a biblioteca: {exc}")
    if saved:
        by_ref = {item["storage_path"]: item for item in saved}
        selected = st.selectbox("HQ salva", list(by_ref), format_func=lambda ref: f"{by_ref[ref]['titulo']} · {by_ref[ref].get('colecao') or 'Sem coleção'} · {by_ref[ref]['book_id'][:8]}")
        if st.button("Abrir esta HQ"):
            def open_selected():
                st.session_state.comic_project_state = load_comic(selected)
                st.session_state.comic_project_id = selected
                st.session_state.comic_project_opened_id = selected
            action(open_selected)
    else:
        st.info("Ainda não há HQs salvas.")
else:
    with st.expander("Escolher a história e criar a adaptação", expanded=not bool(st.session_state.get("comic_project_state"))):
        source = st.session_state.get("comic_source_state")
        if source:
            st.write(f"História selecionada: **{source.get('titulo') or 'Sem título'}**")
            st.caption(f"Origem: {source.get('storage_path') or source.get('book_id') or 'rascunho atual'}")
        source_mode = st.radio("Origem da história", ["História selecionada / sessão atual", "Biblioteca"], horizontal=True)
        if source_mode == "Biblioteca":
            try:
                books = listar_livros()
            except Exception as exc:
                books = []
                st.error(str(exc))
            if books:
                by_ref = {item["storage_path"]: item for item in books}
                selected = st.selectbox("História de origem", list(by_ref), format_func=lambda ref: f"{by_ref[ref]['titulo']} · {by_ref[ref].get('colecao') or 'Sem coleção'} · {Path(ref).stem[-12:]}")
                if st.button("Selecionar esta história"):
                    def choose_source():
                        st.session_state.comic_source_state = canonical_source(selected)
                    action(choose_source)
        else:
            active = st.session_state.get("state")
            if isinstance(active, dict) and active.get("cenas_texto") and not active.get("comic_product"):
                if st.button("Usar a história aberta nesta sessão"):
                    st.session_state.comic_source_state = deepcopy(active)
                    st.rerun()
            if not source:
                st.info("Escolha uma história da biblioteca ou abra uma história no Roteirista.")
        source_key = sha256(str((source or {}).get("storage_path") or (source or {}).get("book_id") or "none").encode()).hexdigest()[:12]
        title = st.text_input("Título da HQ", value=(source.get("titulo", "") + " · HQ") if source else "", key="comic_new_title_" + source_key)
        if st.button("Criar HQ sem alterar a história", disabled=not source or not title.strip(), type="primary"):
            def create():
                project = create_comic(source, source.get("storage_path", ""), title=title)
                st.session_state.comic_project_state = project
                save_comic(project)
                st.session_state.comic_project_id = project["storage_path"]
                st.session_state.comic_project_opened_id = project["storage_path"]
            action(create)

project = st.session_state.get("comic_project_state")
if not project:
    st.stop()
meta = project.get("comic_product") or {}
if meta.get("schema") != SCHEMA:
    st.error("A seleção atual não é uma HQ válida.")
    st.stop()
try:
    source_status(project)
except Exception as exc:
    st.error(str(exc))
    st.stop()

section_title(project["titulo"], "O roteiro e cada imagem ficam sujeitos à sua revisão.", "Projeto de HQ")
st.caption(f"Projeto {project['book_id']} · Origem {meta.get('source_ref') or meta.get('source_book_id') or 'snapshot da sessão'}")
if st.button("Salvar projeto atual"):
    action(lambda: save_comic(project))
with st.expander("Conferir a história de origem preservada"):
    for scene in project["cenas_texto"]:
        st.write(scene["texto"])
    st.caption("Esta é a versão usada na adaptação. Revisar outra história exige criar uma nova HQ.")

section_title("1 · Roteiro de páginas e painéis", "Edite ações, falas, narração e sons antes de aprovar.", "Roteiro")
try:
    personal_source = uses_personal_data(project)
except Exception:
    personal_source = None
    st.warning("Não foi possível verificar a origem para envio à IA. Recupere a história de origem; a revisão manual e os arquivos salvos continuam disponíveis.")
if personal_source:
    st.info("Esta HQ deriva de relato real ou conteúdo com dados pessoais. Cada envio à IA exige consentimento específico, separado da confirmação de créditos.")
with st.expander("Adaptar com IA ou inserir roteiro manual", expanded=not bool(meta.get("script"))):
    provider = texto_provedor_ativo()
    st.caption(f"Adaptação de texto: estimativa US$ {estimar_custo('texto', 1):.4f} por chamada. Provedor: {provider}.")
    new_version = st.checkbox("Criar outra versão do roteiro com IA", value=False, disabled=not bool(meta.get("script")), key=f"comic_new_version_{project['book_id']}")
    confirmed = st.checkbox("Confirmo adaptar a história com IA e consumir os créditos indicados", key=f"comic_script_confirm_{project['book_id']}")
    script_consent_key = f"comic_script_data_consent_{project['book_id']}"
    script_consent = data_consent("Autorizo enviar os dados pessoais desta história ao provedor de IA somente para esta adaptação do roteiro", script_consent_key, personal_source)
    if st.button("Gerar roteiro da HQ", disabled=not confirmed or provider == "indisponível" or personal_source is None or (personal_source and not script_consent) or (bool(meta.get("script")) and not new_version)):
        provider_action(lambda: generate_script(project, confirmed=confirmed, consent_confirmed=script_consent, new_version=new_version), script_consent_key)
    st.caption("Você também pode inserir um roteiro sem usar IA. São aceitos de 1 a 6 painéis por página.")
    template = {"paginas": [{"numero": 1, "paineis": [{"numero": 1, "acao_visual": "", "dialogos": [], "narracao": "", "sfx": "", "emocao": "", "personagem_foco": ""}]}]}
    manual = st.text_area("Roteiro em JSON", value=json.dumps(template, ensure_ascii=False, indent=2), height=250, key=f"comic_script_manual_{project['book_id']}")
    if st.button("Salvar roteiro manual"):
        action(lambda: set_script(project, json.loads(manual)))

if not meta.get("script"):
    st.info("Crie ou insira o roteiro para revisar os painéis.")
    st.stop()

script_key = sha256(json.dumps(meta["script"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
reviewer = st.text_input("Responsável pela revisão e aprovação", key=f"comic_reviewer_{project['book_id']}")
for page in meta["script"]["paginas"]:
    st.markdown(f"**Página {page['numero']}**")
    for panel in page["paineis"]:
        panel_id = f"{page['numero']}:{panel['numero']}"
        prefix = f"comic_{project['book_id']}_{panel_id}_{script_key}"
        with st.expander(f"Painel {panel_id} · {panel['acao_visual'][:80]}"):
            with st.form(prefix + "_edit"):
                revised = deepcopy(panel)
                for field, label in (("acao_visual", "Ação visual"), ("narracao", "Narração"), ("sfx", "Onomatopeia / SFX"), ("emocao", "Emoção"), ("personagem_foco", "Personagem em foco")):
                    revised[field] = st.text_area(label, value=panel[field], key=prefix + field)
                dialogue_json = st.text_area("Diálogos em JSON (personagem e fala)", value=json.dumps(panel["dialogos"], ensure_ascii=False, indent=2), key=prefix + "dialogues")
                if st.form_submit_button("Salvar revisão do painel"):
                    def revise():
                        revised["dialogos"] = json.loads(dialogue_json)
                        revise_panel(project, panel_id, revised)
                    action(revise)

reviewed = st.checkbox("Revisei o roteiro, as falas e a fidelidade à história e aos personagens de origem", key=f"comic_reviewed_{project['book_id']}_{script_key}")
if st.button("Aprovar esta versão do roteiro", disabled=not reviewed or not reviewer.strip()):
    action(lambda: approve_script(project, reviewer, reviewed=reviewed))
script_approved = bool(meta.get("script_approval")) and meta["script_approval"].get("fingerprint") == sha256(json.dumps(meta["script"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
if script_approved:
    st.success("Roteiro revisado e aprovado nesta versão.")
else:
    st.info("Aprovação do roteiro pendente. Você pode enviar imagens e preparar prévias enquanto revisa.")

section_title("2 · Imagens dos painéis", "Envie imagens próprias ou gere candidatas após o pré-voo visual.", "Ilustrações")
with st.expander("Pré-voo visual para geração com IA"):
    existing_plan = st.text_input("ID de um pré-voo desta HQ ou da história de origem", value=meta.get("visual_plan_id", ""), key=f"comic_plan_id_{project['book_id']}")
    if st.button("Vincular pré-voo existente", disabled=not existing_plan.strip()):
        action(lambda: link_visual_plan(project, existing_plan.strip()))
    locations_text = st.text_input("Cenários principais (um por linha ou separados por vírgula)", key=f"comic_locations_{project['book_id']}")
    generation_mode = st.selectbox("Modo visual", list(GENERATION_MODES), index=list(GENERATION_MODES).index("economy"), format_func=lambda key: GENERATION_MODES[key]["label"], key=f"comic_generation_mode_{project['book_id']}")
    budget = st.number_input("Limite estimado de geração visual (US$)", min_value=0.0, value=5.0, step=.5, key=f"comic_budget_{project['book_id']}")
    if st.button("Preparar novo pré-voo desta HQ", disabled=not script_approved or not locations_text.strip()):
        action(lambda: prepare_visual_plan(project, [name.strip() for name in locations_text.replace("\n", ",").split(",") if name.strip()], generation_mode=generation_mode, budget_limit_usd=budget))
    plan = load_visual_plan(meta["visual_plan_id"]) if meta.get("visual_plan_id") else {}
    status = visual_preflight_status(plan) if plan else {}
    if plan:
        from visual_execution_ui import render_emotional_review
        render_emotional_review(plan["id"])
        st.write("Pré-voo aprovado para geração." if status.get("ready_for_scene_generation") else "Conclua a aprovação do conteúdo, personagens, cenários e estilo no Orquestrador.")
        if st.button("Revisar pré-voo no Orquestrador"):
            st.session_state.orchestrator_visual_plan_id = plan["id"]
            st.session_state.pop("editorial_run_id", None)
            st.session_state.pop("run_saved_selection", None)
            st.session_state.orchestrator_collection = project.get("colecao", "")
            st.session_state.orchestrator_project_type = "comic"
            st.switch_page("pages/0_🤖_Orquestrador_FaithBloom.py")

for page in meta["script"]["paginas"]:
    for panel in page["paineis"]:
        panel_id = f"{page['numero']}:{panel['numero']}"
        entry = meta["panels"][panel_id]
        prefix = f"comic_art_{project['book_id']}_{panel_id}_{script_key}"
        with st.expander(f"Imagem do painel {panel_id}"):
            st.write(panel["acao_visual"])
            origin_numbers = [row["numero"] for row in project["cenas_texto"]]
            selected_number = (entry.get("emotional_source") or {}).get("scene_number")
            origin_number = st.selectbox("Cena de origem da direção emocional deste painel", origin_numbers, index=origin_numbers.index(selected_number) if selected_number in origin_numbers else None, key=prefix + "_emotional_source", placeholder="Escolha a cena de origem")
            st.caption("O painel herdará emoção, intensidade, paleta, transição e instrução da cena aprovada, sem modificar os Masters.")
            if st.button("Confirmar vínculo emocional do painel", disabled=origin_number is None or not script_approved, key=prefix + "_emotional_link"):
                action(lambda: link_panel_emotion(project, panel_id, origin_number, reviewed=True))
            upload = st.file_uploader("Enviar imagem candidata sem IA", type=["png", "jpg", "jpeg", "webp"], key=prefix + "_upload")
            if st.button("Adicionar imagem enviada", disabled=upload is None, key=prefix + "_attach"):
                def attach():
                    directory = tenant_local_directory("outputs") / "comic_uploads"
                    directory.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile(dir=directory, suffix=Path(upload.name).suffix.lower(), delete=False) as temporary:
                        temporary.write(upload.getvalue())
                        local_path = temporary.name
                    try:
                        attach_panel_image(project, panel_id, local_path)
                    finally:
                        Path(local_path).unlink(missing_ok=True)
                action(attach)
            plan_id = meta.get("visual_plan_id")
            if plan_id and script_approved:
                try:
                    text_estimate = estimate_visual_operation(plan_id, "texto", 1)
                    st.caption(f"Direção A/B/C: estimativa US$ {text_estimate['estimated_usd']:.4f}, {text_estimate['provider']} · {text_estimate['model']}.")
                    confirm_options = st.checkbox("Confirmo gerar as propostas de direção deste painel", key=prefix + "_confirm_options")
                    options_consent_key = prefix + "_options_data_consent"
                    options_consent = data_consent("Autorizo enviar os dados pessoais deste painel ao provedor de IA somente para gerar estas propostas", options_consent_key, personal_source)
                    if st.button("Gerar direção A/B/C", disabled=not confirm_options or text_estimate["over_budget"] or personal_source is None or (personal_source and not options_consent), key=prefix + "_options"):
                        provider_action(lambda: generate_panel_options(project, panel_id, confirmed=confirm_options, consent_confirmed=options_consent), options_consent_key)
                except Exception as exc:
                    st.caption(str(exc))
                for option in entry.get("options", []):
                    option_id = str(option.get("id") or option.get("option_id") or "")
                    st.write(option.get("titulo") or option_id)
                    st.json(option)
                    adjustment = st.text_input("Ajuste da direção (opcional)", key=prefix + "_adjust_" + option_id)
                    if st.button("Escolher esta direção", key=prefix + "_choose_" + option_id):
                        action(lambda: select_panel_direction(project, panel_id, option_id, adjustment=adjustment))
                if entry.get("selected_direction"):
                    quantity = st.selectbox("Quantidade de candidatas", [1, 3], key=prefix + "_quantity")
                    try:
                        image_estimate = estimate_visual_operation(plan_id, "imagem", quantity)
                        st.caption(f"Imagens: estimativa US$ {image_estimate['estimated_usd']:.4f}, {image_estimate['provider']} · {image_estimate['model']}.")
                        confirm_images = st.checkbox("Confirmo gerar as imagens candidatas dentro do limite do projeto", key=prefix + "_confirm_images")
                        images_consent_key = prefix + "_images_data_consent"
                        images_consent = data_consent("Autorizo enviar os dados pessoais deste painel ao provedor de IA somente para gerar estas imagens candidatas", images_consent_key, personal_source)
                        if st.button("Gerar imagens deste painel", disabled=not confirm_images or image_estimate["over_budget"] or personal_source is None or (personal_source and not images_consent), key=prefix + "_images"):
                            provider_action(lambda: generate_panel_images(project, panel_id, quantity=quantity, confirmed=confirm_images, consent_confirmed=images_consent), images_consent_key)
                    except Exception as exc:
                        st.caption(str(exc))
            for candidate in entry.get("candidates", []):
                try:
                    st.image(materializar(candidate["storage_uri"]), caption=f"Candidata {candidate.get('label', '')} · {candidate['asset_id'][:8]}", width=320)
                except Exception as exc:
                    st.warning(f"A imagem não pôde ser aberta: {exc}")
                selected_approval = entry.get("approval") or {}
                if selected_approval.get("asset_id") == candidate["asset_id"]:
                    st.caption("Imagem aprovada por " + selected_approval["reviewer"])
                if st.button("Aprovar esta imagem para o painel", disabled=not script_approved or not reviewer.strip(), key=prefix + "_approve_" + candidate["asset_id"]):
                    action(lambda: approve_panel_image(project, panel_id, candidate["asset_id"], reviewer))

section_title("3 · Diagramação e arquivos", "Balões, narração e SFX são diagramados como texto, separados da arte.", "Exportação")
readiness = comic_readiness(project)
for error in readiness["errors"]:
    st.info(error)
st.caption(f"{readiness['panels']} painel(is). As versões anteriores e os arquivos já preparados ficam preservados.")
draft = st.checkbox("Preparar prévia de rascunho para revisão", value=not readiness["ok"], key=f"comic_draft_{project['book_id']}_{script_key}")
panels_per_page = st.selectbox("Painéis por página na diagramação", [1, 2, 4, 6], index=1, key=f"comic_density_{project['book_id']}")
export_format = st.selectbox("Formato do arquivo", ["pdf", "epub"], format_func=str.upper)
if st.button("Preparar arquivo da HQ", disabled=not draft and not readiness["ok"]):
    action(lambda: export_comic(project, export_format, panels_per_page=panels_per_page, draft=draft))
for index, artifact in enumerate(reversed(meta.get("exports", []))):
    try:
        data = Path(materializar(artifact["storage_ref"])).read_bytes()
        st.download_button(f"Baixar {artifact['format'].upper()} · {'rascunho' if artifact['draft'] else 'revisado'} · {artifact['at']}",
                           data=data, file_name=f"hq-{index + 1}.{artifact['format']}", mime="application/pdf" if artifact["format"] == "pdf" else "application/epub+zip", key=f"comic_download_{project['book_id']}_{index}")
    except Exception as exc:
        st.error(f"Não foi possível recuperar um arquivo salvo: {exc}")
st.caption("PDF: conferir resolução, layout e prova de impressão. EPUB: conferir EPUBCheck e o visualizador da loja. A exportação não publica automaticamente nem certifica aprovação para impressão.")

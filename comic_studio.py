"""Comic production: source-preserving scripts, gated panel art and real layout.

The existing comic adapter and visual executor own AI work. This studio owns
panel review and typesets speech/narration/SFX outside generated artwork.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import html
import json
import math
from pathlib import Path
import uuid
import zipfile

SCHEMA = "faithbloom.comic-studio.v1"


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _meta(project):
    meta = project.get("comic_product")
    if not isinstance(meta, dict) or meta.get("schema") != SCHEMA:
        raise ValueError("Projeto não pertence ao Comic Studio.")
    return meta


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: informe texto não vazio.")
    return value.strip()


def _source_fingerprint(state):
    """Media bytes, rather than cache paths, identify the inherited character DNA."""
    from storage_backend import materializar
    def stable(value):
        if isinstance(value, dict):
            return {key: stable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [stable(item) for item in value]
        if isinstance(value, str) and Path(value).suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}:
            path = materializar(value)
            return {"media_sha256": sha256(Path(path).read_bytes()).hexdigest()}
        return value
    return _hash(stable({"scenes": state.get("cenas_texto"), "characters": state.get("personagens"),
                         "reference": state.get("versiculo_referencia")}))


def _source_data_marker(state):
    """Keep only origin/risk flags, never a second copy of a private account."""
    inherited = (state.get("comic_product") or {}).get("source_data") or {}
    spec = (state.get("editorial_product") or {}).get("spec") or {}
    origins = (state.get("origin"), state.get("origem"), spec.get("origin"),
               (state.get("route_plan") or {}).get("origin"), inherited.get("origin"))
    real = any(value in {"real_experience", "real_life", "experiencia_real"} for value in origins if isinstance(value, str))
    real = real or bool(state.get("real_experience")) or bool(state.get("real_life_brief"))
    return {"origin": "real_experience" if real else "story",
            "uses_personal_data": real or state.get("uses_personal_data") is True or inherited.get("uses_personal_data") is True}


def uses_personal_data(project):
    """Also recover the risk flag for older HQs from their exact saved origin.

    Historical consent in either document is deliberately not returned: each
    new provider action requires its own current, explicit confirmation.
    """
    meta = _meta(project)
    flagged = _source_data_marker(project)["uses_personal_data"]
    if meta.get("source_ref"):
        import storage_backend as storage
        reference = str(meta["source_ref"])
        path = storage.uri_to_path(reference if storage.is_storage_uri(reference) else storage.storage_uri(reference))
        source = storage.BACKEND.get_json(path, None)
        if not isinstance(source, dict):
            raise ValueError("Recupere a história de origem antes de enviar esta HQ a um provedor de IA.")
        if meta.get("source_book_id") and source.get("book_id") != meta["source_book_id"]:
            raise ValueError("A identidade da história de origem mudou; nenhum conteúdo foi enviado à IA.")
        flagged = flagged or _source_data_marker(source)["uses_personal_data"]
    return flagged


def _require_source_intact(project):
    if _source_fingerprint(project) != _meta(project)["source_fingerprint"]:
        raise ValueError("O conteúdo ou os personagens de origem desta HQ foram alterados. Crie uma nova adaptação para a outra versão.")


def source_status(project, current_source=None, source_ref=None):
    """Audit a snapshot without silently replacing it with another book's text."""
    _require_source_intact(project)
    meta = _meta(project)
    if current_source is not None:
        expected = str(meta.get("source_ref") or "").removeprefix("fb://")
        supplied = str(source_ref or current_source.get("storage_path") or "").removeprefix("fb://")
        if expected and supplied != expected:
            raise ValueError("A história selecionada não é a origem canônica desta HQ.")
        if meta.get("source_book_id") and current_source.get("book_id") != meta["source_book_id"]:
            raise ValueError("O identificador da história de origem não confere.")
        if _source_fingerprint(current_source) != meta["source_fingerprint"]:
            raise ValueError("A história de origem foi revisada. Esta HQ conserva a versão anterior; crie uma nova adaptação para usar a revisão.")
    return {"ok": True, "source_ref": meta.get("source_ref", ""), "source_book_id": meta.get("source_book_id", ""),
            "source_fingerprint": meta["source_fingerprint"]}


def create_comic(source_state: dict, source_ref: str = "", *, title: str = "", script: dict | None = None) -> dict:
    """Create a distinct derived book, retaining the source story and its ID."""
    if not isinstance(source_state, dict):
        raise ValueError("Escolha uma história de origem válida.")
    scenes = source_state.get("cenas_texto") or []
    if not isinstance(scenes, list) or not scenes or any(not isinstance(scene, dict) or not isinstance(scene.get("texto"), str) or not scene["texto"].strip() for scene in scenes):
        raise ValueError("Escolha uma história completa com texto antes de criar a HQ.")
    if source_ref and source_state.get("storage_path") and str(source_ref).removeprefix("fb://") != str(source_state["storage_path"]).removeprefix("fb://"):
        raise ValueError("A referência canônica não corresponde à história selecionada.")
    project = {key: deepcopy(source_state[key]) for key in (
        "colecao", "faixa_etaria", "age_profile_id", "idioma_original", "personagens", "autora", "authorship",
        "versiculo_referencia", "licao_final", "aprendizado_cristao", "cenas_texto", "versao_narrativa_ativa") if key in source_state}
    project.update(book_id=uuid.uuid4().hex, project_type="comic", tipo_projeto="comic",
                   titulo=title.strip() or _text(source_state.get("titulo"), "Título") + " · HQ",
                   trim_largura_in=6.0, trim_altura_in=9.0, revisao_aprovada=False, pacote_pronto=False)
    inherited_script = script if script is not None else (source_state.get("roteiro_quadrinhos") or (source_state.get("formatos_narrativos_salvos") or {}).get("quadrinhos_hq_infantil"))
    project["comic_product"] = {"schema": SCHEMA, "source_ref": source_ref or source_state.get("storage_path", ""),
                                "source_book_id": source_state.get("book_id", ""),
                                "source_fingerprint": _source_fingerprint(source_state),
                                "source_data": _source_data_marker(source_state),
                                "script": None, "script_versions": [], "script_approval": None,
                                "panels": {}, "visual_plan_id": "", "exports": [], "created_at": _now()}
    if inherited_script is not None:
        set_script(project, inherited_script, checkpoint=lambda _: None)
    return project


def validate_script(script):
    if not isinstance(script, dict) or not isinstance(script.get("paginas"), list) or not script["paginas"]:
        raise ValueError("O roteiro deve conter páginas e painéis estruturados.")
    if len(script["paginas"]) > 200:
        raise ValueError("Divida roteiros acima de 200 páginas em volumes.")
    out = deepcopy(script)
    page_numbers = set()
    for page in out["paginas"]:
        if not isinstance(page, dict) or not isinstance(page.get("numero"), int) or isinstance(page["numero"], bool) or page["numero"] <= 0:
            raise ValueError("Cada página precisa de um número inteiro positivo.")
        if page["numero"] in page_numbers:
            raise ValueError("Números de página duplicados no roteiro.")
        page_numbers.add(page["numero"])
        panels = page.get("paineis")
        if not isinstance(panels, list) or not 1 <= len(panels) <= 6:
            raise ValueError("Cada página precisa de 1 a 6 painéis.")
        panel_numbers = set()
        for panel in panels:
            if not isinstance(panel, dict) or not isinstance(panel.get("numero"), int) or isinstance(panel["numero"], bool) or panel["numero"] <= 0:
                raise ValueError("Cada painel precisa de um número inteiro positivo.")
            if panel["numero"] in panel_numbers:
                raise ValueError("Números de painel duplicados na página.")
            panel_numbers.add(panel["numero"])
            panel["acao_visual"] = _text(panel.get("acao_visual"), "Ação visual do painel")
            for key in ("narracao", "sfx", "emocao", "personagem_foco"):
                value = panel.get(key, "")
                if not isinstance(value, str):
                    raise ValueError(f"{key}: use texto.")
                panel[key] = value.strip()
            if not isinstance(panel.get("dialogos", []), list):
                raise ValueError("Diálogos devem ser uma lista de personagem e fala.")
            if any(not isinstance(item, dict) for item in panel.get("dialogos", [])):
                raise ValueError("Cada diálogo precisa conter personagem e fala.")
            panel["dialogos"] = [{"personagem": _text(item.get("personagem"), "Personagem da fala"),
                                 "fala": _text(item.get("fala"), "Fala")} for item in panel.get("dialogos", [])]
    return out


def _panel_items(project):
    script = _meta(project).get("script") or {}
    return [(f"{page['numero']}:{panel['numero']}", panel) for page in script.get("paginas", []) for panel in page["paineis"]]


def _panel(project, panel_id):
    item = next((panel for key, panel in _panel_items(project) if key == panel_id), None)
    if item is None:
        raise ValueError("Painel não encontrado.")
    return item


def _panel_hash(project, panel_id):
    return _hash({"panel": _panel(project, panel_id), "source": _meta(project)["source_fingerprint"]})


def save_comic(project):
    from armazenamento import salvar_livro, atualizar_livro_salvo
    meta = _meta(project)
    _require_source_intact(project)
    if project.get("storage_path") and str(project["storage_path"]).removeprefix("fb://") == str(meta.get("source_ref") or "").removeprefix("fb://"):
        raise ValueError("A HQ deve ser salva em um projeto próprio; a história de origem fica preservada.")
    if project.get("storage_path"):
        project["storage_path"] = atualizar_livro_salvo(project["storage_path"], project)
    else:
        # The generic new-story writer also updates the legacy character library.
        # A derivative HQ must not rewrite that library or promote any Master.
        project["storage_path"] = salvar_livro({**project, "personagens": {}})
        atualizar_livro_salvo(project["storage_path"], project)
    return project["storage_path"]


def load_comic(storage_ref):
    from armazenamento import _json
    # Candidate/approval/export references are durable identities. The generic
    # story loader materializes all media recursively and would replace those
    # identities with cache filenames, preventing a valid approval from reopening.
    project = _json(str(storage_ref).removeprefix("fb://"), None)
    if not isinstance(project, dict):
        raise ValueError("A HQ solicitada não foi encontrada na biblioteca.")
    _meta(project)
    project["storage_path"] = "fb://" + storage_ref.replace("fb://", "", 1)
    _require_source_intact(project)
    return project


def list_comics():
    from armazenamento import listar_livros, _json
    out = []
    for item in listar_livros():
        state = _json(item["storage_path"].removeprefix("fb://"), {})
        if isinstance(state.get("comic_product"), dict) and state["comic_product"].get("schema") == SCHEMA:
            out.append({**item, "book_id": state["book_id"], "storage_path": "fb://" + item["storage_path"].replace("fb://", "", 1)})
    return out


def set_script(project, script, *, checkpoint=None):
    _require_source_intact(project)
    normalized = validate_script(script)
    meta = _meta(project)
    if meta["script"]:
        meta["script_versions"].append({"script": deepcopy(meta["script"]), "panels": deepcopy(meta["panels"]),
                                        "approval": deepcopy(meta["script_approval"]), "at": _now()})
    meta["script"] = normalized
    meta["script_approval"] = None
    meta["panels"] = {key: {"candidates": [], "approval": None} for key, _ in _panel_items(project)}
    project["revisao_aprovada"] = False
    project["pacote_pronto"] = False
    (checkpoint or save_comic)(project)
    return project


def generate_script(project, chamar_llm=None, *, confirmed=False, consent_confirmed=False, new_version=False, checkpoint=None):
    _require_source_intact(project)
    if _meta(project).get("script") and not new_version:
        (checkpoint or save_comic)(project)
        return project
    if not confirmed:
        raise PermissionError("Confirme a adaptação da história e a estimativa de custo antes de gerar o roteiro.")
    from agents.formato_quadrinhos import gerar_roteiro_quadrinhos
    from controle_geracao import estimar_custo, validar_orcamento
    from governance_runtime import authorize_generation
    from openrouter_client import texto_provedor_ativo
    estimate = estimar_custo("texto", 1)
    validar_orcamento(estimate)
    (checkpoint or save_comic)(project)
    _meta(project)["script_governance_receipt"] = authorize_generation(
        "comic.script", confirmed=confirmed, projected_cost=estimate,
        provider_configured=chamar_llm is not None or texto_provedor_ativo() != "indisponível",
        operation_id=uuid.uuid4().hex, source_module="comic_studio.py", state=project,
        uses_personal_data=uses_personal_data(project), consent_confirmed=consent_confirmed)
    (checkpoint or save_comic)(project)
    if chamar_llm is None:
        from openrouter_client import chamar_llm as provider
        def chamar_llm(sistema, instrucao):
            return provider(sistema, instrucao, no_paid_fallback=True, no_retries=True)
    # The adapter may autosave; give it only the new book's path, never source_ref.
    working = deepcopy(project)
    script = gerar_roteiro_quadrinhos(working, chamar_llm)
    set_script(project, script, checkpoint=checkpoint)
    return project


def approve_script(project, reviewer, *, reviewed=False, checkpoint=None):
    _require_source_intact(project)
    meta = _meta(project)
    validate_script(meta.get("script"))
    if not reviewed:
        raise ValueError("Confirme a revisão do roteiro e a fidelidade à história de origem.")
    meta["script_approval"] = {"reviewer": _text(reviewer, "Responsável pela revisão"), "fingerprint": _hash(meta["script"]), "at": _now()}
    project["revisao_aprovada"] = True
    (checkpoint or save_comic)(project)
    return project


def _require_script_review(project):
    _require_source_intact(project)
    meta = _meta(project)
    approval = meta.get("script_approval") or {}
    if not approval.get("reviewer") or approval.get("fingerprint") != _hash(meta.get("script")):
        raise PermissionError("Revise e aprove a versão atual do roteiro da HQ antes de gerar painéis ou exportar o final.")


def _validate_visual_plan_source(project, plan):
    """Accept central run IDs only through their exact, current saved source."""
    meta = _meta(project)
    _require_source_intact(project)
    allowed_ids = {str(value) for value in (project["book_id"], meta.get("source_book_id")) if value}
    central_run = str(plan.get("editorial_run_id") or "") if plan else ""
    if not plan or (str(plan.get("project_id") or "") not in allowed_ids
                    and not (central_run and str(plan.get("project_id") or "") == central_run)):
        raise ValueError("O pré-voo visual precisa pertencer a esta HQ ou à sua história de origem.")
    scenes = [scene["texto"].strip() for scene in project["cenas_texto"]]
    # The central dispatcher separates scenes with a blank line; standalone HQ
    # plans use a single newline. Scene content itself must still match exactly.
    expected_stories = {separator.join(scenes) for separator in ("\n", "\n\n")}
    if str(plan.get("story_text") or "").strip() not in expected_stories:
        raise ValueError("O pré-voo visual pertence a outra versão da história. Use o conteúdo de origem desta HQ.")
    if central_run or plan.get("source_ref") or plan.get("source_fingerprint"):
        import storage_backend as storage
        from editorial_dispatch import content_fingerprint, validate_visual_source
        reference = str(plan.get("source_ref") or "")
        if not reference or not plan.get("source_fingerprint"):
            raise ValueError("O pré-voo visual precisa da referência canônica e do hash da origem salva.")

        def canonical_path(value):
            value = str(value)
            return storage.uri_to_path(value if storage.is_storage_uri(value) else storage.storage_uri(value))

        source_path = canonical_path(reference)
        original_path = canonical_path(meta["source_ref"]) if meta.get("source_ref") else None
        comic_path = canonical_path(project["storage_path"]) if project.get("storage_path") else None
        if source_path not in {original_path, comic_path}:
            raise ValueError("O pré-voo visual precisa pertencer à referência canônica desta HQ ou da sua história.")
        source = validate_visual_source(plan) if central_run else storage.BACKEND.get_json(source_path, None)
        if not isinstance(source, dict) or content_fingerprint(source) != plan["source_fingerprint"]:
            raise ValueError("O conteúdo salvo mudou em relação ao hash do pré-voo visual.")
        expected_id = meta.get("source_book_id") if source_path == original_path else project["book_id"]
        if expected_id and source.get("book_id") != expected_id:
            raise ValueError("A identidade da origem salva não corresponde à HQ.")
        if plan.get("source_book_id") and source.get("book_id") != plan["source_book_id"]:
            raise ValueError("A identidade da origem salva não corresponde ao pré-voo visual.")
        if _source_fingerprint(source) != meta["source_fingerprint"]:
            raise ValueError("O conteúdo ou os personagens da história de origem mudaram. Crie uma nova adaptação.")


def link_visual_plan(project, plan_id, *, checkpoint=None):
    import orchestrator_visual as ov
    plan = ov.load_visual_plan(plan_id)
    _validate_visual_plan_source(project, plan)
    meta = _meta(project)
    meta["visual_plan_id"] = plan_id
    (checkpoint or save_comic)(project)
    return project


def prepare_visual_plan(project, locations, *, generation_mode="economy", budget_limit_usd=5.0, checkpoint=None):
    """Create a project-specific preflight; approvals remain separate human actions."""
    _require_script_review(project)
    import orchestrator_visual as ov
    if not isinstance(locations, list) or not locations:
        raise ValueError("Informe os cenários da HQ antes de preparar o pré-voo visual.")
    names = list(dict.fromkeys(_text(name, "Cenário") for name in locations))
    (checkpoint or save_comic)(project)
    characters = [{"id": name, "name": name, "principal": True} for name in (project.get("personagens") or {})]
    plan = ov.create_visual_plan(project["book_id"], project["titulo"],
                                 "\n".join(scene["texto"] for scene in project["cenas_texto"]),
                                 characters=characters, locations=[{"id": name, "name": name, "required": True} for name in names],
                                 generation_mode=generation_mode, budget_limit_usd=budget_limit_usd)
    if project.get("storage_path"):
        import storage_backend as storage
        from editorial_dispatch import content_fingerprint
        persisted = storage.BACKEND.get_json(str(project["storage_path"]).removeprefix("fb://"), None)
        if not isinstance(persisted, dict) or persisted.get("book_id") != project["book_id"]:
            raise ValueError("Salve esta HQ antes de vincular o pré-voo visual.")
        plan.update(source_ref=project["storage_path"], source_book_id=project["book_id"],
                    source_fingerprint=content_fingerprint(persisted), comic_source_ref=_meta(project).get("source_ref", ""),
                    comic_source_fingerprint=_meta(project)["source_fingerprint"])
        plan = ov.save_visual_plan(plan)
    link_visual_plan(project, plan["id"], checkpoint=checkpoint)
    return plan


def _scene_key(project, panel_id):
    return f"comic:{project['book_id']}:{panel_id}:{_panel_hash(project, panel_id)[:16]}"


def _visual_gate(project):
    _require_script_review(project)
    meta = _meta(project)
    if not meta.get("visual_plan_id"):
        raise PermissionError("Vincule o pré-voo visual aprovado desta HQ/história antes de gerar imagens.")
    import orchestrator_visual as ov
    plan = ov.load_visual_plan(meta["visual_plan_id"])
    try:
        _validate_visual_plan_source(project, plan)
    except (ValueError, PermissionError) as exc:
        raise ValueError("O pré-voo visual não corresponde à identidade e ao conteúdo de origem desta HQ.") from exc
    ov.require_scene_generation_ready(plan)
    return meta["visual_plan_id"]


def _authorize_personal_visual(project, plan_id, action, modality, quantity, confirmed, consent_confirmed, checkpoint):
    # The visual executor retains its budget/reservation/retry gates. This
    # additional boundary checks the HQ's private origin, which standalone
    # visual plans do not otherwise carry. No consent is stored for later reuse.
    if not uses_personal_data(project):
        return
    from visual_execution import estimate_visual_operation
    from governance_runtime import authorize_generation
    estimate = estimate_visual_operation(plan_id, modality, quantity)
    available = None if estimate["budget_limit_usd"] is None else (
        float(estimate["budget_limit_usd"]) - estimate["estimated_spent_usd"] - estimate["reserved_usd"])
    receipt = authorize_generation(
        action, confirmed=confirmed, projected_cost=estimate["estimated_usd"],
        provider_configured=bool(estimate.get("provider")), operation_id=uuid.uuid4().hex,
        source_module="comic_studio.py", state=project, budget_remaining=available,
        uses_personal_data=True, consent_confirmed=consent_confirmed)
    _meta(project)["last_personal_visual_receipt"] = receipt
    (checkpoint or save_comic)(project)


def generate_panel_options(project, panel_id, *, confirmed=False, consent_confirmed=False, checkpoint=None):
    from visual_execution import generate_scene_options
    panel = _panel(project, panel_id)
    plan_id = _visual_gate(project)
    _authorize_personal_visual(project, plan_id, "comic.panel_options", "texto", 1,
                               confirmed, consent_confirmed, checkpoint)
    excerpt = panel["acao_visual"] + "\nEmoção: " + panel["emocao"] + "\nPersonagem em foco: " + panel["personagem_foco"]
    excerpt += "\nContexto de fala (somente expressão; nunca desenhar texto): " + " | ".join(item["fala"] for item in panel["dialogos"])
    result = generate_scene_options(plan_id, _scene_key(project, panel_id), excerpt, confirmed=confirmed)
    _meta(project)["panels"][panel_id]["options"] = deepcopy(result["results"][0]["ideas"])
    (checkpoint or save_comic)(project)
    return result


def select_panel_direction(project, panel_id, option_id, *, adjustment="", checkpoint=None):
    from visual_execution import select_scene_option
    plan_id = _visual_gate(project)
    select_scene_option(plan_id, _scene_key(project, panel_id), option_id, adjustment=adjustment)
    _meta(project)["panels"][panel_id]["selected_direction"] = option_id
    (checkpoint or save_comic)(project)
    return project


def _attach_results(project, panel_id, results):
    entry = _meta(project)["panels"][panel_id]
    for item in results:
        if not any(candidate["asset_id"] == item["asset_id"] for candidate in entry["candidates"]):
            entry["candidates"].append({**deepcopy(item), "panel_fingerprint": _panel_hash(project, panel_id)})


def generate_panel_images(project, panel_id, *, quantity=1, confirmed=False, consent_confirmed=False, checkpoint=None):
    from visual_execution import generate_selected_scene, VisualExecutionError
    plan_id = _visual_gate(project)
    _authorize_personal_visual(project, plan_id, "comic.panel_images", "imagem", quantity,
                               confirmed, consent_confirmed, checkpoint)
    try:
        result = generate_selected_scene(plan_id, _scene_key(project, panel_id), quantity=quantity, confirmed=confirmed)
    except VisualExecutionError as exc:
        _attach_results(project, panel_id, exc.operation.get("results", []))
        (checkpoint or save_comic)(project)
        raise
    _attach_results(project, panel_id, result["results"])
    (checkpoint or save_comic)(project)
    return result


def attach_panel_image(project, panel_id, local_path, *, checkpoint=None):
    """Import a candidate without changing/promoting any existing Master."""
    from PIL import Image
    from armazenamento import salvar_na_galeria
    from asset_library import get_asset_by_uri, create_version
    from storage_backend import persistir_arquivo, materializar
    _require_source_intact(project)
    _panel(project, panel_id)
    original_path = materializar(str(local_path))
    with Image.open(original_path) as image:
        image.verify()
    uri = persistir_arquivo(original_path, f"assets/comics/{project['book_id']}/panels")
    metadata = {"origin": "comic_panel_upload", "comic_id": project["book_id"], "panel_id": panel_id,
                "visual_status": "VARIATION_CANDIDATE", "contains_text": False}
    existing = get_asset_by_uri(uri)
    if existing:
        candidate = create_version(existing["id"], storage_uri_value=uri, name=f"{project['titulo']} · Painel {panel_id}", metadata=metadata)
    else:
        candidate = salvar_na_galeria(uri, f"{project['titulo']} · Painel {panel_id}", "cena", metadata=metadata)
    result = {"asset_id": candidate["id"], "storage_uri": uri, "label": "Enviada", "approved": False}
    _attach_results(project, panel_id, [result])
    (checkpoint or save_comic)(project)
    return result


def approve_panel_image(project, panel_id, asset_id, reviewer, *, checkpoint=None):
    from asset_library import get_asset, update_asset
    from storage_backend import materializar
    _require_script_review(project)
    reviewer = _text(reviewer, "Responsável pela aprovação")
    meta = _meta(project)
    entry = meta["panels"].get(panel_id, {})
    candidate = next((item for item in entry.get("candidates", []) if item["asset_id"] == asset_id), None)
    asset = get_asset(asset_id, materialize_file=False)
    if not candidate or not asset or asset.get("status") == "archived":
        raise ValueError("Escolha uma imagem candidata disponível deste painel.")
    if candidate["panel_fingerprint"] != _panel_hash(project, panel_id):
        raise ValueError("A imagem candidata pertence a uma versão anterior deste painel.")
    uri = asset.get("storage_uri") or asset.get("caminho_arquivo")
    path = materializar(uri)
    with open(path, "rb") as file:
        digest = sha256(file.read()).hexdigest()
    if asset.get("master_roles") or asset.get("visual_status") in {"COLOR_MASTER", "LINEART_MASTER", "WORLD_MASTER"}:
        raise ValueError("A imagem do painel deve ser uma cópia candidata, sem alterar um Master oficial.")
    from PIL import Image
    with Image.open(path) as image:
        image.verify()
    update_asset(asset_id, approved=True, visual_status="APPROVED_IMAGE", metadata={"comic_panel_approval": "human"})
    entry["approval"] = {"asset_id": asset_id, "storage_uri": uri, "reviewer": reviewer,
                         "panel_fingerprint": _panel_hash(project, panel_id), "asset_digest": digest, "at": _now()}
    (checkpoint or save_comic)(project)
    return project


def revise_panel(project, panel_id, revised_panel, *, checkpoint=None):
    _require_source_intact(project)
    meta = _meta(project)
    _panel(project, panel_id)
    prior = deepcopy(meta["script"])
    candidate_script = deepcopy(prior)
    page_no, panel_no = map(int, panel_id.split(":"))
    for page in candidate_script["paginas"]:
        for i, panel in enumerate(page["paineis"]):
            if page["numero"] == page_no and panel["numero"] == panel_no:
                if revised_panel.get("numero") != panel_no:
                    raise ValueError("O número do painel deve ser preservado.")
                page["paineis"][i] = deepcopy(revised_panel)
    candidate_script = validate_script(candidate_script)
    meta["script_versions"].append({"script": prior, "panels": deepcopy(meta["panels"]), "approval": deepcopy(meta["script_approval"]), "at": _now()})
    meta["script"] = candidate_script
    meta["script_approval"] = None
    meta["panels"][panel_id]["approval"] = None
    project["revisao_aprovada"] = False
    project["pacote_pronto"] = False
    (checkpoint or save_comic)(project)
    return project


def _image_for_panel(project, panel_id, *, draft=False):
    from asset_library import get_asset
    from storage_backend import materializar
    entry = _meta(project)["panels"][panel_id]
    approval = entry.get("approval") or {}
    if approval.get("panel_fingerprint") != _panel_hash(project, panel_id):
        if draft:
            candidates = [item for item in entry["candidates"] if item["panel_fingerprint"] == _panel_hash(project, panel_id)]
            return materializar(candidates[-1]["storage_uri"]) if candidates else ""
        raise ValueError(f"Painel {panel_id}: escolha e aprove a imagem desta versão.")
    asset = get_asset(approval["asset_id"], materialize_file=False)
    if not asset or asset.get("status") == "archived" or not asset.get("approved"):
        raise ValueError(f"Painel {panel_id}: a imagem aprovada não está disponível.")
    if (asset.get("storage_uri") or asset.get("caminho_arquivo")) != approval["storage_uri"]:
        raise ValueError(f"Painel {panel_id}: a referência da imagem foi alterada após a aprovação.")
    path = materializar(approval["storage_uri"])
    if sha256(Path(path).read_bytes()).hexdigest() != approval["asset_digest"]:
        raise ValueError(f"Painel {panel_id}: a imagem foi alterada após a aprovação.")
    return path


def comic_readiness(project):
    errors = []
    try:
        validate_script(_meta(project).get("script"))
        _require_script_review(project)
        for key, _ in _panel_items(project):
            _image_for_panel(project, key)
    except (ValueError, PermissionError, OSError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "errors": errors, "panels": len(_panel_items(project)),
            "publication_ready": False, "automatic_master_promotion": False}


def _typeset_layout(project, *, panels_per_page=2, draft=False):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from renderizador_editorial import _registrar_fontes, _fontes_para_texto
    _require_source_intact(project)
    validate_script(_meta(project).get("script"))
    if isinstance(panels_per_page, bool) or panels_per_page not in {1, 2, 4, 6}:
        raise ValueError("Escolha 1, 2, 4 ou 6 painéis por página.")
    if not draft:
        _require_script_review(project)
    _registrar_fontes()
    page_w, page_h = float(project["trim_largura_in"]) * 72, float(project["trim_altura_in"]) * 72
    if not all(math.isfinite(value) and 144 <= value <= 1440 for value in (page_w, page_h)):
        raise ValueError("As dimensões da página precisam ficar entre 2 e 20 polegadas.")
    margin, gap, font_size = 32, 12, 11
    columns = 2 if panels_per_page in {4, 6} else 1
    rows = math.ceil(panels_per_page / columns)
    cell_w = (page_w - margin * 2 - gap * (columns - 1)) / columns
    cell_h = (page_h - margin * 2 - 40 - gap * (rows - 1)) / rows
    pages = []
    for original_page in _meta(project)["script"]["paginas"]:
        panels = original_page["paineis"]
        for offset in range(0, len(panels), panels_per_page):
            cells = []
            for index, panel in enumerate(panels[offset:offset + panels_per_page]):
                key = f"{original_page['numero']}:{panel['numero']}"
                path = _image_for_panel(project, key, draft=draft)
                balloons = []
                entries = [("narration", panel["narracao"])] if panel["narracao"] else []
                entries += [("speech", f"{dialogue['personagem']}: {dialogue['fala']}") for dialogue in panel["dialogos"]]
                if panel["sfx"]:
                    entries.append(("sfx", panel["sfx"]))
                for kind, text in entries:
                    font, _ = _fontes_para_texto(text)
                    style = ParagraphStyle("comic-balloon", fontName=font, fontSize=font_size, leading=font_size * 1.25)
                    paragraph = Paragraph(html.escape(text).replace("\n", "<br/>"), style)
                    _, height = paragraph.wrap(cell_w - 20, cell_h)
                    balloons.append({"kind": kind, "text": text, "paragraph": paragraph, "height": height + 12})
                text_h = sum(item["height"] + 4 for item in balloons)
                art_h = cell_h - text_h - 12
                if art_h < 90:
                    raise ValueError(f"Painel {key}: o texto não cabe com legibilidade. Reduza os painéis por página ou encurte as falas.")
                x = margin + (index % columns) * (cell_w + gap)
                y = page_h - margin - 30 - (index // columns + 1) * cell_h - (index // columns) * gap
                cells.append({"key": key, "panel": panel, "path": path, "x": x, "y": y,
                              "width": cell_w, "height": cell_h, "art_height": art_h, "balloons": balloons})
            pages.append({"source_page": original_page["numero"], "cells": cells})
    return pages, page_w, page_h


def export_comic(project, format, *, output_path=None, panels_per_page=2, draft=False, checkpoint=None):
    """Typeset reviewed art and editable balloons into PDF and fixed-layout EPUB."""
    from storage_backend import persistir_arquivo, tenant_local_directory
    if format not in {"pdf", "epub"}:
        raise ValueError("Formato precisa ser pdf ou epub.")
    pages, page_w, page_h = _typeset_layout(project, panels_per_page=panels_per_page, draft=draft)
    if output_path is None:
        directory = tenant_local_directory("outputs") / "comics" / project["book_id"] / uuid.uuid4().hex
        directory.mkdir(parents=True, exist_ok=True)
        output_path = str(directory / f"comic.{format}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    title = ("RASCUNHO · " if draft else "") + project["titulo"]
    if format == "pdf":
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from renderizador_editorial import _fontes_para_texto
        from author_profiles import author_display_from_state
        from qualidade_impressao import analisar_pdf_miolo
        canvas_pdf = canvas.Canvas(output_path, pagesize=(page_w, page_h), initialFontName=_fontes_para_texto(title)[0])
        canvas_pdf.setTitle(title)
        canvas_pdf.setAuthor(author_display_from_state(project))
        for page_index, page in enumerate(pages, 1):
            canvas_pdf.setFont(_fontes_para_texto(title)[0], 11)
            canvas_pdf.drawString(32, page_h - 24, title[:60])
            canvas_pdf.drawRightString(page_w - 32, 16, str(page_index))
            for cell in page["cells"]:
                x, y, width = cell["x"], cell["y"], cell["width"]
                art_y = y + cell["height"] - cell["art_height"]
                canvas_pdf.setStrokeColorRGB(.65, .65, .7)
                canvas_pdf.rect(x, y, width, cell["height"], stroke=1, fill=0)
                if cell["path"]:
                    canvas_pdf.drawImage(ImageReader(cell["path"]), x + 4, art_y + 4, width=width - 8,
                                         height=cell["art_height"] - 8, preserveAspectRatio=True, anchor="c", mask="auto")
                else:
                    canvas_pdf.drawCentredString(x + width / 2, art_y + cell["art_height"] / 2, "Ilustração pendente")
                cursor = art_y - 6
                for balloon in cell["balloons"]:
                    height = balloon["height"]
                    canvas_pdf.setFillColorRGB(1, 1, 1)
                    canvas_pdf.setStrokeColorRGB(.65, .65, .7)
                    canvas_pdf.roundRect(x + 4, cursor - height, width - 8, height, 6, stroke=1, fill=1)
                    if balloon["kind"] == "speech":
                        tail = canvas_pdf.beginPath()
                        tail.moveTo(x + 16, cursor)
                        tail.lineTo(x + 23, cursor + 5)
                        tail.lineTo(x + 30, cursor)
                        canvas_pdf.drawPath(tail, stroke=1, fill=1)
                    canvas_pdf.setFillColorRGB(.18, .13, .25)
                    balloon["paragraph"].drawOn(canvas_pdf, x + 10, cursor - height + 6)
                    cursor -= height + 4
            canvas_pdf.showPage()
        canvas_pdf.save()
        inspection = analisar_pdf_miolo(output_path, project["trim_largura_in"], project["trim_altura_in"],
                                       bleed=False, paginas_esperadas=len(pages))
        if inspection["erros"]:
            raise ValueError("PDF da HQ não passou na inspeção: " + "; ".join(inspection["erros"]))
    else:
        inspection = _export_epub_layout(project, pages, page_w, page_h, output_path, title)
    uri = persistir_arquivo(output_path, f"assets/comics/{project['book_id']}/exports/{uuid.uuid4().hex}")
    artifact = {"format": format, "storage_ref": uri, "draft": draft, "panels_per_page": panels_per_page,
                "script_fingerprint": _hash(_meta(project)["script"]), "pages": len(pages), "at": _now(),
                "publication_ready": False, "epubcheck_passed": False, "print_ready": False}
    _meta(project)["exports"].append(artifact)
    (checkpoint or save_comic)(project)
    return {**artifact, "path": output_path, "inspection": inspection}


def _export_epub_layout(project, pages, page_w, page_h, output_path, title):
    """Reuse EPUB packaging; replace fixed pages with the real comic cell layout."""
    from epub_exporter import export_epub, inspect_epub
    state = deepcopy(project)
    state["titulo"] = title
    state.pop("capa_ebook", None)
    state["cenas_texto"] = [{"numero": index, "texto": ""} for index in range(1, len(pages) + 1)]
    image_names = {}
    images = []
    for page in pages:
        for cell in page["cells"]:
            if cell["path"] and cell["path"] not in image_names:
                n = len(images) + 1
                images.append({"numero": n, "arquivo": cell["path"]})
                image_names[cell["path"]] = f"images/img_{n:03d}{Path(cell['path']).suffix.lower()}"
    state["cenas_imagem"] = images
    export_epub(state, output_path, mode="fixed", page_width_px=round(page_w), page_height_px=round(page_h))
    with zipfile.ZipFile(output_path) as original:
        files = {name: original.read(name) for name in original.namelist()}
    for index, page in enumerate(pages, 1):
        cells = []
        for cell in page["cells"]:
            image = f'<img src="{html.escape(image_names[cell["path"]])}" alt="{html.escape(cell["panel"]["acao_visual"], quote=True)}"/>' if cell["path"] else '<div class="placeholder">Ilustração pendente</div>'
            text = "".join(f'<div class="{balloon["kind"]}">{html.escape(balloon["text"]).replace(chr(10), "<br/>")}</div>' for balloon in cell["balloons"])
            top = page_h - cell["y"] - cell["height"]
            cells.append(f'<section class="panel" style="left:{cell["x"]}px;top:{top}px;width:{cell["width"]}px;height:{cell["height"]}px"><div class="art" style="height:{cell["art_height"]}px">{image}</div><div class="text">{text}</div></section>')
        lang = html.escape(project.get("idioma_original", "pt-BR"), quote=True)
        files[f"EPUB/page_{index:03d}.xhtml"] = (f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" lang="{lang}" xml:lang="{lang}"><head><title>{html.escape(title)}</title><meta name="viewport" content="width={round(page_w)}, height={round(page_h)}"/><link rel="stylesheet" type="text/css" href="styles.css"/></head><body><h1>{html.escape(title)}</h1>{"".join(cells)}</body></html>').encode()
    files["EPUB/styles.css"] = (f'html,body{{margin:0;padding:0;width:{page_w}px;height:{page_h}px;background:white;color:#302039;font-family:sans-serif;font-size:11px;line-height:1.25}}h1{{position:absolute;top:8px;left:32px;font-size:11px}}.panel{{position:absolute;box-sizing:border-box;border:1px solid #aaa}}.art img{{display:block;width:100%;height:100%;object-fit:contain}}.text{{padding:6px 4px}}.text>div{{padding:6px;margin-bottom:4px;border:1px solid #aaa;border-radius:6px}}.sfx{{color:#7031b0;font-weight:bold}}.narration{{background:#faf5fc}}.placeholder{{padding:30px;text-align:center}}').encode()
    with zipfile.ZipFile(output_path, "w") as target:
        target.writestr("mimetype", files.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
        for name, contents in files.items():
            target.writestr(name, contents, compress_type=zipfile.ZIP_DEFLATED)
    inspection = inspect_epub(output_path)
    if not inspection["ok"]:
        raise ValueError("EPUB da HQ não passou na inspeção estrutural.")
    return inspection

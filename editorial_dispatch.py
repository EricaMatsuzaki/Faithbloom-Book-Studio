"""Persistent handoffs from the central orchestrator to the existing studios.

Each project owns its source and checkpoints. Opening a studio never launches a
provider, approves a Master or publishes an edition. Paid generation is explicit.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import uuid
import threading
from collections import Counter
from functools import wraps

from orchestrator_editorial import PROJECT_TYPES, build_editorial_route
import storage_backend as storage
from storage_backend import storage_uri
from storage_updates import update_json_document

SCHEMA = "faithbloom.editorial-execution.v1"
PREFIX = "orchestrator_runs"
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _serialized(function):
    """Serialize one project's actions within this Streamlit worker."""
    @wraps(function)
    def wrapped(run_id: str, *args, **kwargs):
        with _LOCKS_GUARD:
            lock = _LOCKS.setdefault(run_id, threading.RLock())
        with lock:
            return function(run_id, *args, **kwargs)
    return wrapped
SPECIALIZED_TYPES = {
    "children_advice", "teen_advice", "children_devotional", "teen_devotional",
    "personal_development", "study_book", "exam_prep", "workbook", "study_guide",
    "flashcards", "other",
}
STUDIO_PAGES = {
    "children_story": "pages/39_✍️_Historia_4_Estilos.py",
    "real_life_story": "pages/42_🌿_Historias_Inspiradas_na_Vida_Real.py",
    "comic": "pages/39_✍️_Historia_4_Estilos.py",
    "coloring_book": "pages/3_🖍️_Livros_de_Colorir.py",
    "activity_book": "pages/23_🧩_Activity_Book_Studio.py",
    **{kind: "pages/55_📚_Produtos_Editoriais.py" for kind in SPECIALIZED_TYPES},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(run_id: str) -> str:
    if not isinstance(run_id, str) or len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        raise ValueError("Identificador de projeto inválido.")
    return f"{PREFIX}/{run_id}.json"


def content_fingerprint(state: dict) -> str:
    fields = ("book_id", "project_id", "id", "colecao", "titulo", "cenas_texto", "licao_final", "units", "unidades", "editorial_units", "paginas", "pages", "brief", "personagens",
              "title", "collection", "audience_id", "faixa_etaria", "editorial_audience", "idioma_original", "language", "editorial_line", "publico", "theme", "mapa_emocional", "paleta_emocional_preset", "style_dna", "style_dna_id")
    content = {k: state.get(k) for k in fields}
    if isinstance(state.get("editorial_product"), dict):
        content["editorial_product"] = {k: state["editorial_product"].get(k) for k in ("spec", "units")}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save_run(run: dict) -> dict:
    saved = deepcopy(run)
    if saved.get("schema") != SCHEMA or saved.get("project_type") not in PROJECT_TYPES:
        raise ValueError("Projeto editorial inválido.")
    saved["updated_at"] = _now()
    saved["storage_ref"] = storage_uri(_path(saved["id"]))
    expected = saved.get("revision", 0)
    def replace(current):
        if current is not None:
            if not isinstance(current, dict) or current.get("id") != saved["id"] or current.get("schema") != SCHEMA:
                raise ValueError("Registro de projeto inválido; nenhuma alteração foi feita.")
            if current.get("revision", 0) != expected:
                raise storage.StorageConflict(expected, current.get("revision", 0))
            if (current.get("generation") or {}).get("status") == "running":
                raise PermissionError("A execução editorial está em andamento. Aguarde ou confira a tentativa antes de alterar seu registro.")
        elif expected:
            raise storage.StorageConflict(expected, None)
        result = deepcopy(saved)
        result["revision"] = expected + 1
        return result
    return update_json_document(storage.BACKEND, _path(saved["id"]), replace,
                                allow_legacy_pilot=True)


def _update_run(run_id, mutator):
    now = _now()
    def update(current):
        if not isinstance(current, dict) or current.get("id") != run_id or current.get("schema") != SCHEMA:
            raise ValueError("Registro de projeto inválido; nenhuma alteração foi feita.")
        updated = mutator(deepcopy(current))
        updated["revision"] = current.get("revision", 0) + 1
        updated["updated_at"] = now
        return updated
    return update_json_document(storage.BACKEND, _path(run_id), update,
                                allow_legacy_pilot=True)


def load_run(run_id: str) -> dict:
    value = storage.BACKEND.get_json(_path(run_id), None)
    if value is None:
        raise ValueError("Projeto editorial não encontrado.")
    if not isinstance(value, dict) or value.get("id") != run_id or value.get("schema") != SCHEMA:
        raise ValueError("Registro de projeto inválido; nenhuma alteração foi feita.")
    return value


def list_runs() -> list[dict]:
    rows = []
    for path in storage.BACKEND.list(PREFIX):
        if not path.endswith(".json"):
            continue
        value = storage.BACKEND.get_json(path, None)
        if isinstance(value, dict) and value.get("schema") == SCHEMA:
            rows.append(value)
    return sorted(rows, key=lambda row: row.get("updated_at", ""), reverse=True)


def create_editorial_run(project_type: str, title: str, brief: str, *, origin: str = "own_idea", audience: str = "3_8", editorial_line: str = "christian", collection: str = "", derived_outputs: list[str] | None = None, unit_count: int = 3, sources: list | None = None, bible_reference: str = "", custom_blocks: list | None = None) -> dict:
    if not title.strip() or not brief.strip():
        raise ValueError("Informe o título e o conteúdo ou objetivo do projeto.")
    route = build_editorial_route(project_type, origin=origin, audience=audience, editorial_line=editorial_line, derived_outputs=derived_outputs)
    # The route is saved before initializing a specialist so a storage failure
    # cannot silently launch generation or lose the author's input.
    run = {
        "schema": SCHEMA, "id": uuid.uuid4().hex, "project_type": project_type,
        "title": title.strip(), "brief": brief.strip(), "collection": collection.strip(),
        "route_plan": route, "status": "draft", "created_at": _now(),
        "studio_page": STUDIO_PAGES[project_type], "source": {}, "source_ref": "",
        "generation": {"status": "not_started"}, "history": [],
        "human_content_approval": None, "visual_plan_id": "",
        "unit_count": int(unit_count), "sources": deepcopy(sources or []),
        "bible_reference": bible_reference, "custom_blocks": deepcopy(custom_blocks or []),
    }
    return save_run(run)


@_serialized
def initialize_specialist(run_id: str) -> dict:
    run = load_run(run_id)
    kind = run["project_type"]
    route = run["route_plan"]
    if kind in {"children_story", "real_life_story"} and route["audience"] not in {"3_5", "3_8", "6_8", "9_12"}:
        raise ValueError("Este Studio narrativo ainda atende apenas às faixas infantis. O público escolhido foi preservado; use um produto editorial com DNA adolescente/adulto em vez de converter o projeto para infantil.")
    if run.get("source"):
        return run
    if kind in SPECIALIZED_TYPES:
        from editorial_products import create_product, save_product
        source = create_product(kind, run["title"], run["brief"], audience=route["audience"], editorial_line=route["editorial_line"], origin=route["origin"], collection=run["collection"], unit_count=run["unit_count"], sources=run["sources"], bible_reference=run["bible_reference"], custom_blocks=run["custom_blocks"])
        save_product(source)
        run["source"] = source
        run["source_ref"] = source.get("storage_path", "")
    elif kind == "activity_book":
        from activity_studio import create_activity_project
        audience = {"3_5": "3-4", "3_8": "5-6", "6_8": "7-8", "9_12": "9-12"}.get(route["audience"], route["audience"])
        source = create_activity_project(run["title"], audience, theme=run["brief"], collection=run["collection"])
        run["source"] = source
        run["source_ref"] = storage_uri(f"activity_studio/projects/{source['id']}.json")
    elif kind == "coloring_book":
        from armazenamento import salvar_livro_colorir
        source = {"titulo": run["title"], "colecao": run["collection"], "tema_geral": run["brief"], "publico": {"teen": "Juvenil", "adult": "Adulto", "custom": "Personalizado"}.get(route["audience"], "Infantil"), "faixa_etaria": {"3_5": "3–5 anos", "3_8": "4–8 anos", "6_8": "6–8 anos", "9_12": "8–12 anos", "teen": "13+", "adult": "Adulto", "custom": "Personalizado"}[route["audience"]], "editorial_audience": route["audience"], "paginas": []}
        source["storage_path"] = salvar_livro_colorir(source)
        run["source"] = source
        run["source_ref"] = source["storage_path"]
    else:
        from armazenamento import salvar_livro
        source = {"titulo": run["title"], "colecao": run["collection"], "_entrada_tema_livre": run["brief"], "faixa_etaria": route["audience"].replace("_", "-"), "editorial_line": route["editorial_line"], "versiculo_referencia": run["bible_reference"], "paginas_minimas": 24, "personagens": {}, "cenas_texto": []}
        if kind == "real_life_story":
            # Privacy and consent must still be reviewed in the native studio.
            source["real_life_brief"] = {"raw_experience": run["brief"], "consent_reviewed": False}
            source["real_experience"] = {"original_account": run["brief"], "consent_confirmed": False}
        if kind == "comic":
            source["formato_narrativo"] = "quadrinhos"
        source["storage_path"] = salvar_livro(source)
        run["source"] = source
        run["source_ref"] = source["storage_path"]
    run["status"] = "in_studio"
    return save_run(run)


def _strict_llm(sistema: str, instrucao: str):
    from ai_provider_router import chamar_llm
    return chamar_llm(sistema, instrucao, no_paid_fallback=True, no_retries=True)


@_serialized
def execute_editorial_generation(run_id: str, *, confirmed: bool = False, chamar_llm=None, resume_confirmed: bool = False, consent_confirmed: bool = False) -> dict:
    if not confirmed:
        raise PermissionError("Confirme a geração e o consumo de créditos antes de continuar.")
    run = initialize_specialist(run_id)
    if run["project_type"] not in SPECIALIZED_TYPES:
        raise ValueError("Use o Studio do projeto para gerar, revisar e aprovar seu conteúdo.")
    status = run["generation"].get("status")
    if status in {"running", "interrupted", "save_failed", "needs_reconciliation"} and not resume_confirmed:
        raise PermissionError("A geração anterior foi interrompida. Revise as unidades salvas e confirme a retomada; uma chamada sem resposta pode ter consumido créditos.")
    from editorial_products import generate_product, load_product
    from editorial_generation_runtime import generation_status
    execution = generation_status(run["source_ref"])
    if (execution.get("claim") or {}).get("owner_active") or any(
            a["state"] in {"running", "uncertain"} for a in execution["attempts"]):
        raise PermissionError("A execução anterior ainda está ativa ou precisa de conferência no provedor. A confirmação de retomada não libera outra chamada.")
    source = load_product(run["source_ref"])
    dispatch_token, started = uuid.uuid4().hex, _now()
    observed_revision = run.get("revision", 0)
    def start(current):
        if current.get("revision", 0) != observed_revision:
            raise storage.StorageConflict(observed_revision, current.get("revision", 0))
        current["generation"] = {"status": "running", "started_at": started, "dispatch_token": dispatch_token}
        return current
    _update_run(run_id, start)

    def checkpoint(updated: dict):
        # The canonical product checkpoint has already committed. This is a
        # secondary projection, never the authority for paid retry decisions.
        payload = deepcopy(updated)
        def merge(current):
            if (current.get("generation") or {}).get("dispatch_token") != dispatch_token:
                raise storage.StorageConflict(dispatch_token, (current.get("generation") or {}).get("dispatch_token"))
            current["source"] = deepcopy(payload)
            current["source_ref"] = payload.get("storage_path", current["source_ref"])
            return current
        _update_run(run_id, merge)

    try:
        source = generate_product(source, chamar_llm, checkpoint=checkpoint, confirmed=confirmed, consent_confirmed=consent_confirmed)
        payload = deepcopy(source)
        def complete(current):
            if (current.get("generation") or {}).get("dispatch_token") != dispatch_token:
                raise storage.StorageConflict(dispatch_token, (current.get("generation") or {}).get("dispatch_token"))
            current["source"] = deepcopy(payload)
            current["source_ref"] = payload.get("storage_path", current["source_ref"])
            current["generation"]["status"] = "completed"
            current["status"] = "awaiting_review"
            return current
        return _update_run(run_id, complete)
    except Exception:
        # Keep every completed unit, never report a partially completed project
        # as approved, and never automatically repeat an uncertain paid call.
        payload = deepcopy(source)
        def interrupt(current):
            if (current.get("generation") or {}).get("dispatch_token") == dispatch_token:
                current["source"] = deepcopy(payload)
                current["generation"]["status"] = "interrupted"
                current["status"] = "needs_attention"
            return current
        try:
            _update_run(run_id, interrupt)
        except Exception:
            # The canonical product retains its claim/received response. Never
            # replace it or buy a second response after a projection failure.
            pass
        raise


@_serialized
def sync_source(run_id: str) -> dict:
    run = load_run(run_id)
    if not run.get("source"):
        return run
    old_fingerprint = content_fingerprint(run["source"])
    if run["project_type"] in SPECIALIZED_TYPES:
        from editorial_products import load_product
        source = load_product(run["source_ref"])
    elif run["project_type"] == "activity_book":
        from activity_studio import load_activity_project
        source = load_activity_project(run["source"]["id"])
        # Upgrade the old opaque activity:<id> reference using its own stored ID,
        # never a title search. Existing source/history remain in place.
        old_reference = run["source_ref"]
        run["source_ref"] = storage_uri(f"activity_studio/projects/{run['source']['id']}.json")
        if old_reference == f"activity:{run['source']['id']}" and run.get("visual_plan_id"):
            from orchestrator_visual import load_visual_plan, save_visual_plan
            plan = load_visual_plan(run["visual_plan_id"])
            if plan and plan.get("source_ref") == old_reference and plan.get("editorial_run_id") == run["id"]:
                plan["source_ref"] = run["source_ref"]
                plan.setdefault("history", []).append({"event": "source_reference_migrated", "at": _now()})
                save_visual_plan(plan)
    else:
        source = storage.BACKEND.get_json(run["source_ref"].removeprefix("fb://"), None)
    if not isinstance(source, dict) or not source:
        raise ValueError("A fonte do projeto não está disponível; sua referência foi preservada.")
    if run["project_type"] in SPECIALIZED_TYPES:
        from editorial_generation_runtime import _execution
        if (_execution(source).get("claim") or {}).get("owner_active"):
            raise PermissionError("A geração ainda está ativa. Aguarde o responsável antes de atualizar a projeção do Orquestrador.")
    run["source"] = source
    current_fingerprint = content_fingerprint(source)
    plan_stale = False
    if run.get("visual_plan_id"):
        from orchestrator_visual import load_visual_plan
        active_plan = load_visual_plan(run["visual_plan_id"])
        plan_stale = bool(active_plan and active_plan.get("source_fingerprint") != current_fingerprint)
    if old_fingerprint != current_fingerprint or plan_stale:
        run["human_content_approval"] = None
        if run.get("visual_plan_id"):
            from orchestrator_visual import load_visual_plan, save_visual_plan
            old_plan = load_visual_plan(run["visual_plan_id"])
            if old_plan:
                old_plan.setdefault("approvals", {})["story"] = False
                old_plan.setdefault("history", []).append({"event": "source_changed", "at": _now()})
                save_visual_plan(old_plan)
            run["history"].append({"visual_plan_id": run["visual_plan_id"], "reason": "source_changed", "at": _now()})
            run["visual_plan_id"] = ""
        run["status"] = "awaiting_review"
    if run["project_type"] in SPECIALIZED_TYPES and run["generation"].get("status") == "running":
        # A product recovery may finish before the secondary run projection was
        # acknowledged. Repair only that projection; never release a paid claim.
        expected_revision = run.get("revision", 0)
        execution = _execution(source)
        meta = source["editorial_product"]
        projected_status = ("needs_reconciliation" if execution.get("legacy_review_required") or any(
            a["state"] in {"running", "uncertain"} for a in execution["attempts"]) else
            "completed" if meta.get("units") and not meta.get("draft") else "interrupted")
        payload = deepcopy(run)
        def repair(current):
            if current.get("revision", 0) != expected_revision:
                raise storage.StorageConflict(expected_revision, current.get("revision", 0))
            for field in ("source", "source_ref", "human_content_approval", "visual_plan_id", "history", "status"):
                current[field] = deepcopy(payload[field])
            current["generation"]["status"] = projected_status
            return current
        return _update_run(run_id, repair)
    return save_run(run)


@_serialized
def bind_visual_plan_to_run(run_id: str, *, characters: list[dict], locations: list[dict], generation_mode: str = "economy", budget_limit_usd: float | None = 5.0) -> dict:
    from orchestrator_visual import create_visual_plan, save_visual_plan
    run = sync_source(run_id)
    if run["project_type"] not in {"children_story", "real_life_story", "comic", "activity_book", "coloring_book"}:
        raise ValueError("Este projeto não precisa de pré-voo visual obrigatório.")
    if run.get("visual_plan_id"):
        raise ValueError("Este projeto já possui pré-voo. Continue o plano salvo; mudanças de conteúdo preservam o histórico e exigem novo pré-voo.")
    source = run["source"]
    texts = [str(row.get("texto") or "").strip() for row in source.get("cenas_texto", []) if isinstance(row, dict)]
    if run["project_type"] in {"children_story", "real_life_story", "comic"} and not any(texts):
        raise ValueError("Gere e salve a história no Studio antes de iniciar o pré-voo visual.")
    if run["project_type"] == "activity_book":
        texts = [str(row.get("instruction") or row.get("title") or "") for row in source.get("pages") or []]
    if run["project_type"] == "coloring_book":
        texts = [str(row.get("cena") or row.get("prompt_livre") or row.get("nome") or "") for row in source.get("paginas") or []]
    if not any(texts):
        raise ValueError("Salve o conteúdo do projeto no Studio antes de criar o plano visual.")
    plan = create_visual_plan(project_id=run["id"], title=run["title"], story_text="\n\n".join(texts), characters=characters, locations=locations, generation_mode=generation_mode, budget_limit_usd=budget_limit_usd)
    plan.update(editorial_run_id=run["id"], source_ref=run["source_ref"], source_fingerprint=content_fingerprint(source), collection=run["collection"])
    from emotional_visual_binding import prepare_emotional_binding
    plan = save_visual_plan(prepare_emotional_binding(plan, source))
    run["visual_plan_id"] = plan["id"]
    save_run(run)
    return plan


def validate_visual_source(plan: dict) -> dict:
    """Check the persisted canonical source even when the UI has not synchronized."""
    if not plan.get("editorial_run_id"):
        return plan  # Historical standalone plans retain their existing contract.
    run = load_run(plan["editorial_run_id"])
    if run.get("visual_plan_id") != plan.get("id") or run.get("source_ref") != plan.get("source_ref"):
        raise PermissionError("Este pré-voo não pertence ao projeto ativo salvo.")
    source = storage.BACKEND.get_json(str(plan["source_ref"]).removeprefix("fb://"), None)
    if not isinstance(source, dict) or content_fingerprint(source) != plan.get("source_fingerprint"):
        raise PermissionError("O conteúdo salvo mudou. Atualize o projeto no Orquestrador e aprove o novo pré-voo antes de gerar.")
    return source


@_serialized
def approve_run_content(run_id: str) -> dict:
    from orchestrator_visual import load_visual_plan, approve_story
    run = load_run(run_id)
    plan = load_visual_plan(run.get("visual_plan_id", ""))
    if not plan:
        raise ValueError("Crie o pré-voo vinculado ao projeto primeiro.")
    source = validate_visual_source(plan)
    run["human_content_approval"] = {"fingerprint": content_fingerprint(source), "approved_at": _now(), "scope": "visual_preflight"}
    run = save_run(run)
    approve_story(plan)
    return run


def studio_session_context(run: dict) -> dict:
    kind = run["project_type"]
    source = deepcopy(run.get("source") or {})
    if not source:
        raise ValueError("Inicialize o projeto antes de abrir o Studio.")
    if kind in {"children_story", "real_life_story", "comic"} and run["route_plan"]["audience"] not in {"3_5", "3_8", "6_8", "9_12"}:
        raise ValueError("Este Studio narrativo ainda atende apenas às faixas infantis; o público escolhido não será convertido.")
    if kind in {"children_story", "real_life_story", "comic"}:
        require_child_translation_source(source, studio="Studio narrativo")
    if kind == "real_life_story" and not source.get("real_experience"):
        source["real_experience"] = {"original_account": (source.get("real_life_brief") or {}).get("raw_experience") or run["brief"], "consent_confirmed": False}
    if kind in SPECIALIZED_TYPES:
        return {"editorial_product_id": run["source_ref"]}
    if kind == "activity_book":
        return {"r08_project_id": source["id"], "r08_handoff_project_id": source["id"]}
    if kind == "coloring_book":
        return {"state_c": source, "caminho_salvo_c": run["source_ref"], "etapa_c": "entrada", "preview_c_path": None, "capa_colorir_phase8": None, "coloring_profile_link_pending": None, "coloring_save_error": None, "ideias_colorir": []}
    source["storage_path"] = run["source_ref"]
    return {"state": source, "caminho_salvo": run["source_ref"], "historia4_storage_path": run["source_ref"], "ideias_4_estilos": [], "ideia_4_estilos_escolhida": None, "biblioteca_colecao": {}}


def apply_native_studio_context(session, run: dict) -> None:
    """Reset explicit project-owned widgets before opening a different source."""
    context = studio_session_context(run)
    if run["project_type"] == "coloring_book":
        for key in ("coloring_authors", "coloring_legacy_author", "c_selo8", "c_faixa8", "coloring_pdf_bleed"):
            session.pop(key, None)
    elif run["project_type"] == "real_life_story":
        # This native collection selector has an explicit persistent widget key.
        session.pop("real_experience_collection_select", None)
        session.pop("real_experience_collection_select__new", None)
    for key, value in context.items():
        session[key] = value


def prepare_comic_handoff(session, run_id: str) -> dict:
    """Open the HQ studio with the exact saved story, clearing only UI context."""
    run = sync_source(run_id)
    source = deepcopy(run.get("source") or {})
    if run["project_type"] not in {"children_story", "real_life_story", "comic"}:
        raise ValueError("Escolha uma história narrativa salva para adaptar em quadrinhos.")
    require_child_translation_source(source, studio="Studio de HQ")
    if not any(isinstance(row, dict) and str(row.get("texto") or "").strip() for row in source.get("cenas_texto", [])):
        raise ValueError("Gere e salve a história-base antes de abrir a adaptação em quadrinhos.")
    for key in ("comic_project_id", "comic_project_opened_id", "comic_project_state", "comic_source_opened_ref"):
        session.pop(key, None)
    source["storage_path"] = run["source_ref"]
    session["comic_source_ref"] = run["source_ref"]
    session["comic_source_state"] = source
    return run


def book_source_key(reference: str) -> str:
    """Compare storage identities without treating a title as an identifier."""
    return str(reference or "").removeprefix("fb://").strip("/")


def book_selection_labels(books: list[dict]) -> dict[str, dict]:
    counts = Counter(f"{b.get('titulo')} · {b.get('colecao', '')}" for b in books)
    result = {}
    for book in books:
        label = f"{book.get('titulo')} · {book.get('colecao', '')}"
        if counts[label] > 1:
            label += f" · {book.get('storage_path') or book.get('arquivo', '')}"
        if label in result:
            raise ValueError("A biblioteca contém referências duplicadas. Atualize os registros antes de selecionar uma obra.")
        result[label] = book
    return result


def apply_studio_book_handoff(session, target: str, options: dict[str, dict], widget_key: str) -> bool:
    """Consume a newly selected context once; fail closed if its source is absent.

    A manual selection after a successful handoff stays editable. A fresh handoff
    always wins over previous widget state, even for same-title books.
    """
    from integration_ux import PROJECT_CONTEXT_KEY
    context = session.get(PROJECT_CONTEXT_KEY) or {}
    request = session.get("editorial_studio_handoff") or {}
    if request and request.get("target") == target:
        context = request.get("project") or {}
        token = request.get("token")
    else:
        token = hashlib.sha256(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()
    if not context.get("storage_path") or session.get(f"{target}_handoff_seen") == token:
        return False
    wanted = book_source_key(context["storage_path"])
    matches = [label for label, card in options.items() if book_source_key(card.get("storage_path") or card.get("arquivo")) == wanted]
    if len(matches) != 1:
        raise ValueError("A fonte exata enviada pelo Orquestrador não está disponível nesta biblioteca. Nenhum outro livro foi aberto. Atualize o projeto de origem e tente novamente.")
    session[widget_key] = matches[0]
    session[f"{target}_handoff_seen"] = token
    return True


def require_child_translation_source(source: dict, *, studio: str = "Studio de tradução") -> None:
    """The native Japanese/translation guard has only child reading profiles."""
    spec = (source.get("editorial_product") or {}).get("spec") or {}
    audience = source.get("editorial_audience") or spec.get("audience") or source.get("audience_id") or source.get("faixa_etaria") or source.get("publico") or "3-8"
    normalized = str(audience).lower().replace("_", "-").replace("–", "-").replace("—", "-").replace("anos", "").strip()
    if normalized not in {"3-5", "3-8", "6-8", "9-12", "infantil"}:
        raise ValueError(f"O {studio} ainda usa perfis de leitura infantis. A obra mantém seu público adolescente, adulto ou personalizado; esta operação está bloqueada até existir um perfil adequado, sem convertê-la para infantil.")

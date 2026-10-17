"""Execute the author-approved visual workflow with durable recovery checkpoints.

Candidates never replace Character Masters. A World Master changes only through
``select_world_candidate``. Provider calls use an explicit configured route,
one HTTP attempt and no paid fallback. Monetary totals are conservative estimates
unless a cost is explicitly reconciled; they are not a billing ledger.

The storage backend has no compare-and-swap primitive. The lock protects sessions
in one application worker; checkpoints protect restarts. Distributed workers need
a transactional lease/ledger before this executor can claim cross-worker dedupe.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import threading
import time

import character_guide as guide
import orchestrator_visual as ov
import openrouter_client as client
import storage_backend as storage
from emotional_visual_binding import require_emotional_binding, scene_direction, direction_prompt, source_scene_text, IDENTITY_RULE
from armazenamento import salvar_na_galeria
from asset_library import create_version, get_asset, get_asset_by_uri, update_asset
from character_universe import carregar_personagem_oficial
from controle_geracao import estimar_custo, sanitizar_texto, validar_lote_imagens, validar_orcamento

_LOCK = threading.RLock()


class VisualExecutionError(RuntimeError):
    def __init__(self, message: str, operation: dict | None = None):
        super().__init__(message)
        self.operation = deepcopy(operation or {})


def _fingerprint(value) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _plan(plan_id: str) -> dict:
    plan = ov.load_visual_plan(str(plan_id))
    if not plan or not str(plan.get("project_id") or "").strip():
        raise ValueError("Pré-voo visual/projeto não encontrado.")
    if plan.get("editorial_run_id"):
        from editorial_dispatch import validate_visual_source
        validate_visual_source(plan)
    return plan


def _ledger_path(plan: dict) -> str:
    return f"orchestrator/visual_budgets/{_fingerprint(str(plan['project_id']))}.json"


def _ledger(plan: dict) -> dict:
    """A failed read must never be mistaken for an empty project budget."""
    try:
        raw = storage.BACKEND.get_bytes(_ledger_path(plan))
    except FileNotFoundError:
        return {"project_id": plan["project_id"], "operations": {}}
    except storage.StorageError as exc:
        if str(exc) == "Supabase download falhou (404)":
            return {"project_id": plan["project_id"], "operations": {}}
        raise VisualExecutionError("Não foi possível ler o orçamento persistido. Nenhuma geração foi enviada.") from exc
    try:
        ledger = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise VisualExecutionError("O orçamento persistido precisa de recuperação antes de gerar.") from exc
    if not isinstance(ledger, dict) or not isinstance(ledger.get("operations"), dict) or ledger.get("project_id") != plan["project_id"]:
        raise VisualExecutionError("O orçamento persistido não corresponde a este projeto.")
    return ledger


def _totals(ledger: dict) -> dict:
    spent = reserved = actual_known = 0.0
    all_actual = True
    for operation in ledger.get("operations", {}).values():
        for item in operation.get("items", []):
            if item.get("state") in {"raw", "succeeded", "reconciled_failed"}:
                actual = item.get("actual_usd")
                spent += item["estimated_usd"] if actual is None else actual
                if actual is None:
                    all_actual = False
                else:
                    actual_known += actual
            elif item.get("reserved"):
                reserved += item["estimated_usd"]
    return {"estimated_spent_usd": round(spent, 6), "reserved_usd": round(reserved, 6),
            "actual_known_usd": round(actual_known, 6), "actual_total_usd": round(actual_known, 6) if all_actual else None}


def _save_ledger(plan: dict, ledger: dict) -> None:
    ledger["updated_at"] = int(time.time())
    ov._save_json(_ledger_path(plan), ledger)


def _sync_budget(plan_id: str, ledger: dict) -> dict:
    plan = _plan(plan_id)
    totals = _totals(ledger)
    plan.update(budget_spent_usd=totals["estimated_spent_usd"], budget_reserved_usd=totals["reserved_usd"],
                budget_actual_usd=totals["actual_total_usd"], budget_cost_basis="estimated_until_reconciled")
    return ov.save_visual_plan(plan)


def _route(plan: dict, modality: str) -> dict:
    mode = plan.get("generation_mode", "free_first")
    if mode == "free_first":
        raise PermissionError("Não há uma rota visual/textual certificada como gratuita. Escolha Econômico, Premium ou Automático e confirme a estimativa antes de gerar.")
    has_gemini = client.gemini_client.gemini_disponivel()
    has_router = bool(client.OPENROUTER_API_KEY)
    forced = client.PROVEDOR_TEXTO
    if forced == "gemini":
        provider = "gemini" if has_gemini else ""
    elif forced == "openrouter":
        provider = "openrouter" if has_router else ""
    elif mode == "premium" and has_router:
        provider = "openrouter"
    else:
        provider = "gemini" if has_gemini else ("openrouter" if has_router else "")
    if not provider:
        raise PermissionError("Configure Gemini ou OpenRouter antes de gerar. Nenhuma chamada foi enviada.")
    resolution = "2K" if modality == "imagem" and mode == "premium" and provider == "openrouter" else None
    return {"provider": provider, "resolution": resolution,
            "model": (client.gemini_client.MODELO_IMAGEM_PADRAO if modality == "imagem" else client.gemini_client.MODELO_TEXTO_PADRAO) if provider == "gemini" else (client.MODELO_IMAGEM if modality == "imagem" else client.MODELO_TEXTO),
            "single_attempt": True, "paid_fallback": False}


def estimate_visual_operation(plan_id: str, modality: str = "imagem", quantity: int = 1) -> dict:
    if modality not in {"imagem", "texto"}:
        raise ValueError("Modalidade visual inválida.")
    quantity = int(quantity)
    if quantity < 1:
        raise ValueError("Informe uma quantidade positiva.")
    plan = _plan(plan_id)
    route = _route(plan, modality)
    if modality == "imagem":
        validar_lote_imagens(quantity)
    total = estimar_custo(modality, quantity)
    # A premium image has a larger reservation; this remains a configurable
    # estimate, not a claim about a provider's official price or invoice.
    if route["resolution"] == "2K":
        total *= 2
    if not math.isfinite(total) or total < 0:
        raise PermissionError("A estimativa de custo configurada é inválida. Corrija-a antes de gerar.")
    totals = _totals(_ledger(plan))
    limit = plan.get("budget_limit_usd")
    if limit is not None and (not math.isfinite(float(limit)) or float(limit) < 0):
        raise PermissionError("O orçamento do projeto é inválido. Corrija-o antes de gerar.")
    over = limit is not None and totals["estimated_spent_usd"] + totals["reserved_usd"] + total > float(limit) + 1e-9
    return {**route, **totals, "quantity": quantity, "estimated_usd": round(total, 6),
            "actual_usd": None, "cost_basis": "configurable_estimate", "requires_author_confirmation": True,
            "over_budget": over, "budget_limit_usd": limit}


def _asset_path(value: str) -> str:
    try:
        path = storage.materializar(value) if storage.is_storage_uri(value) else str(value or "")
    except Exception as exc:
        raise ValueError("Uma referência aprovada não está disponível no armazenamento.") from exc
    if not path or not os.path.isfile(path):
        raise ValueError("Uma referência aprovada não está disponível. Recupere-a antes de gerar.")
    from PIL import Image
    try:
        with Image.open(path) as image:
            image.verify()
    except Exception as exc:
        raise ValueError("Uma imagem de referência/resultado não é um arquivo de imagem válido.") from exc
    return path


def _asset_digest(path: str) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _characters(plan: dict) -> list[dict]:
    out = []
    for declaration in plan.get("characters", []):
        cid = str(declaration.get("id") or declaration.get("name") or "")
        approval = (plan.get("approvals", {}).get("characters") or {}).get(cid, {})
        if not approval.get("approved"):
            raise PermissionError(f"A referência de {cid} precisa ser aprovada antes de gerar.")
        candidate_id = str(approval.get("candidate_id") or "")
        official_id = candidate_id.removeprefix("official:") if candidate_id.startswith("official:") else str(declaration.get("character_universe_id") or declaration.get("official_id") or "")
        character = carregar_personagem_oficial(official_id) if official_id else deepcopy(declaration)
        if not character or character.get("status") == "arquivado":
            raise PermissionError(f"O Character DNA de {cid} está ausente ou arquivado.")
        character.setdefault("nome", declaration.get("name") or cid)
        if not guide.character_identity_summary(character).get("descricao") and not guide.character_identity_summary(character).get("locked"):
            raise PermissionError(f"Cadastre o Character DNA de {cid} antes de gerar.")
        allowed = (character.get("metadata") or {}).get("usos_permitidos")
        if allowed is not None and "story" not in allowed:
            raise PermissionError(f"O personagem {cid} não está autorizado para ilustrações de histórias.")
        value = str(approval.get("asset_uri") or character.get("color_master") or "")
        asset = get_asset(candidate_id, materialize_file=False) if not candidate_id.startswith("official:") else None
        asset = asset or get_asset_by_uri(value, materialize_file=False)
        if asset:
            if asset.get("status") == "archived" or asset.get("visual_status") == "ARCHIVED":
                raise PermissionError(f"A referência de {cid} foi arquivada.")
            owners = (asset.get("metadata") or {}).get("personagens") or []
            owner = (asset.get("metadata") or {}).get("character_id")
            if owners and character["nome"].casefold() not in {str(x).casefold() for x in owners}:
                raise PermissionError("A candidata visual pertence a outro personagem.")
            if owner and official_id and owner != official_id:
                raise PermissionError("A candidata visual pertence a outro Character DNA.")
            if candidate_id.startswith("official:") and not asset.get("approved"):
                raise PermissionError("O Master oficial vinculado não está aprovado no catálogo.")
            value = asset.get("storage_uri") or asset.get("caminho_arquivo") or value
        reference = _asset_path(value)
        # A project-approved candidate is a project-only copy, never an update
        # to the canonical Character Universe entity or its original bytes.
        character["color_master"] = reference
        character["reference_pack"] = []
        out.append(character)
    return out


def _worlds(plan: dict) -> list[dict]:
    out = []
    for loc in plan.get("locations", []):
        key = str(loc.get("id") or loc.get("name") or "")
        approval = (plan.get("approvals", {}).get("locations") or {}).get(key, {})
        if not approval.get("approved"):
            if not loc.get("required", True):
                continue
            raise PermissionError(f"O cenário {key} precisa ser aprovado.")
        world = ov.load_world_master(approval.get("world_master_id", ""))
        if not world or world.get("status") != "approved":
            raise PermissionError("World Master aprovado não encontrado.")
        refs = world.get("reference_assets") or []
        if not refs:
            raise PermissionError(f"O cenário {key} ainda não tem imagem aprovada. Gere A/B/C e escolha um candidato.")
        selected = get_asset(world["selected_asset_id"], materialize_file=False) if world.get("selected_asset_id") else None
        if world.get("selected_asset_id") and (not selected or selected.get("status") == "archived" or not selected.get("approved")):
            raise PermissionError("A imagem selecionada do World Master foi removida, arquivada ou perdeu a aprovação.")
        world["resolved_references"] = [_asset_path(str(x)) for x in refs]
        out.append(world)
    return out


def _scene_context(plan: dict) -> tuple[list[dict], list[dict], dict, str]:
    ov.require_scene_generation_ready(plan)
    characters, worlds = _characters(plan), _worlds(plan)
    if not characters:
        raise PermissionError("Selecione e aprove ao menos um personagem com DNA e imagem de referência.")
    style = deepcopy(plan.get("style_master") or {})
    if not str(style.get("name") or style.get("nome") or style.get("description") or style.get("id") or "").strip():
        raise PermissionError("O estilo aprovado precisa conter uma descrição ou Style DNA oficial.")
    context = {"titulo": plan.get("title"), "colecao": plan.get("collection", ""),
               "style_dna": style, "world_masters": [{k: w.get(k) for k in ("id", "name", "description", "reference_assets", "selected_asset_id")} for w in worlds],
               "faixa_etaria": plan.get("faixa_etaria", "4-8"), "cenas_texto": plan.get("story_text", ""),
               "mapa_emocional": require_emotional_binding(plan)["scenes"]}
    style_id = style.get("style_dna_id")
    if style_id:
        from style_dna import carregar_style
        canonical = carregar_style(style_id)
        if not canonical or canonical.get("status") != "oficial":
            raise PermissionError("O Style DNA aprovado não está disponível como estilo oficial.")
        context["style_dna_id"] = style_id
        context["style_dna"] = canonical
    signature = _fingerprint({"story": plan.get("story_text"), "emotional_map": context["mapa_emocional"], "style": context["style_dna"],
                              "characters": [{"id": c.get("id"), "dna": c.get("dna"), "reference_digest": _asset_digest(c["color_master"])} for c in characters],
                              "worlds": [{"id": w["id"], "description": w.get("description"), "refs": [_asset_digest(p) for p in w["resolved_references"]]} for w in worlds]})
    return characters, worlds, context, signature


def _snapshot(operation: dict, ledger: dict) -> dict:
    out = deepcopy(operation)
    out["results"] = [deepcopy(x["result"]) for x in operation["items"] if x.get("state") == "succeeded"]
    out["budget"] = _totals(ledger)
    return out


def list_visual_operations(plan_id: str) -> list[dict]:
    plan = _plan(plan_id)
    ledger = _ledger(plan)
    return [_snapshot(x, ledger) for x in ledger["operations"].values() if x.get("plan_id") == plan_id]


def _run(plan_id: str, kind: str, payload: dict, count: int, modality: str, confirmed: bool,
         operation_key: str | None, produce, persist, *, consent_confirmed: bool = False) -> dict:
    with _LOCK:
        plan = _plan(plan_id)
        ledger = _ledger(plan)
        input_fingerprint = _fingerprint({"kind": kind, "payload": payload, "quantity": count})
        operation_id = _fingerprint({"plan_id": plan_id, "input": input_fingerprint, "key": operation_key or "default"})[:32]
        operation = ledger["operations"].get(operation_id)
        if operation is None:
            ambiguous = next((x for x in ledger["operations"].values() if x.get("input_fingerprint") == input_fingerprint and any(item.get("state") in {"running", "uncertain"} for item in x.get("items", []))), None)
            if ambiguous:
                raise VisualExecutionError("A tentativa anterior pode ter chegado ao provedor. Alterar a chave da operação não permite reenviar antes da reconciliação.", _snapshot(ambiguous, ledger))
        if operation and operation.get("status") == "complete":
            _sync_budget(plan_id, ledger)
            return _snapshot(operation, ledger)
        if operation and any(x.get("state") in {"running", "uncertain"} for x in operation["items"]):
            raise VisualExecutionError("A tentativa anterior pode ter chegado ao provedor. Confira o resultado/custo antes de enviar outra geração.", _snapshot(operation, ledger))
        estimate = estimate_visual_operation(plan_id, modality, count)
        if not confirmed:
            raise PermissionError(f"Confirme a operação e a estimativa de US$ {estimate['estimated_usd']:.2f} antes de gerar.")
        if operation is None and estimate["over_budget"]:
            raise PermissionError("A operação ultrapassa o orçamento do projeto. Ajuste o limite explicitamente antes de gerar.")
        # Recovered raw images can be saved without buying or authorizing them
        # again. Only calls that have never started require fresh action evidence.
        pending_items = [x for x in operation["items"] if x["state"] == "pending"] if operation else []
        pending_cost = sum(x["estimated_usd"] for x in pending_items) if operation else estimate["estimated_usd"]
        governance_receipt = None
        if operation is None or pending_items:
            from governance_runtime import authorize_generation
            totals = _totals(ledger)
            limit = plan.get("budget_limit_usd")
            # Reservations already owned by these pending calls are available
            # to them, not to a second operation. The ledger remains the meter.
            available = None if limit is None else (
                float(limit) - totals["estimated_spent_usd"] - totals["reserved_usd"]
                + sum(x["estimated_usd"] for x in pending_items if x.get("reserved"))
            )
            from emotional_visual_binding import source_for_plan
            canonical_source = source_for_plan(plan)
            source_markers = (canonical_source.get("comic_product") or {}).get("source_data") or {}
            uses_personal = bool(canonical_source.get("real_experience") or canonical_source.get("real_life_brief") or canonical_source.get("uses_personal_data") or source_markers.get("uses_personal_data"))
            governance_receipt = authorize_generation(
                "visual." + kind, confirmed=confirmed, projected_cost=pending_cost,
                provider_configured=bool(estimate.get("provider")), operation_id=operation_id,
                source_module="visual_execution.py", state=plan, budget_remaining=available,
                uses_personal_data=uses_personal, consent_confirmed=consent_confirmed,
            )
        if operation is None:
            if estimate["over_budget"]:
                raise PermissionError("A operação ultrapassa o orçamento do projeto. Ajuste o limite explicitamente antes de gerar.")
            validar_orcamento(estimate["estimated_usd"])
            unit = estimate["estimated_usd"] / count
            operation = {"id": operation_id, "input_fingerprint": input_fingerprint, "plan_id": plan_id, "kind": kind, "status": "reserved", "route": {k: estimate[k] for k in ("provider", "model", "resolution")},
                         "created_at": int(time.time()), "cost_basis": "estimated_until_reconciled",
                         "items": [{"index": i, "state": "pending", "reserved": True, "estimated_usd": unit, "actual_usd": None} for i in range(count)]}
            ledger["operations"][operation_id] = operation
            _save_ledger(plan, ledger)  # A failed reservation prevents every provider call.
            _sync_budget(plan_id, ledger)
        remaining = [x for x in operation["items"] if x["state"] == "pending" and not x.get("reserved")]
        if remaining:
            totals = _totals(ledger)
            limit = plan.get("budget_limit_usd")
            needed = sum(x["estimated_usd"] for x in remaining)
            if limit is not None and totals["estimated_spent_usd"] + totals["reserved_usd"] + needed > float(limit) + 1e-9:
                raise PermissionError("O saldo do projeto não permite retomar este lote.")
            validar_orcamento(needed)
            for item in remaining:
                item["reserved"] = True
            _save_ledger(plan, ledger)
        if governance_receipt is not None:
            operation["governance_receipt"] = governance_receipt
            _save_ledger(plan, ledger)
        for item in operation["items"]:
            if item["state"] in {"succeeded", "reconciled_failed"}:
                continue
            try:
                if item["state"] == "pending":
                    item["state"] = "running"
                    _save_ledger(plan, ledger)
                    raw = produce(item["index"], operation["route"])
                    item.update(raw=raw, state="raw", reserved=False)
                    _save_ledger(plan, ledger)  # Store response before media/catalog work.
                    _sync_budget(plan_id, ledger)
                item["result"] = persist(item["raw"], item["index"], operation_id)
                item["state"] = "succeeded"
                _save_ledger(plan, ledger)
            except BaseException as exc:
                if item["state"] == "running":
                    item["state"] = "uncertain"
                operation["status"] = "needs_reconciliation" if item["state"] == "uncertain" else "persistence_pending"
                operation["error"] = sanitizar_texto(str(exc))[:400]
                # Release only calls that were never started. A timed-out call
                # retains its reservation until an explicit reconciliation.
                for untouched in operation["items"]:
                    if untouched["state"] == "pending":
                        untouched["reserved"] = False
                try:
                    _save_ledger(plan, ledger)
                    _sync_budget(plan_id, ledger)
                except Exception:
                    pass  # The durable pre-call checkpoint still blocks a duplicate.
                if not isinstance(exc, Exception):
                    raise
                raise VisualExecutionError("O lote foi interrompido. Resultados já recebidos foram preservados; nenhuma tentativa automática foi enviada. " + sanitizar_texto(str(exc))[:300], _snapshot(operation, ledger)) from exc
        operation["status"] = "complete" if all(x["state"] == "succeeded" for x in operation["items"]) else "reconciled_partial"
        _save_ledger(plan, ledger)
        _sync_budget(plan_id, ledger)
        return _snapshot(operation, ledger)


def _generate_image(prompt: str, refs: list[str], route: dict) -> str:
    return client.gerar_imagem(prompt, imagem_base=refs[0] if refs else None, imagens_referencia=refs[1:],
                              strict_provider=route["provider"], no_paid_fallback=True, no_retries=True,
                              resolution=route.get("resolution"))


def _persist_candidate(raw: str, *, name: str, kind: str, metadata: dict, operation_id: str, index: int) -> dict:
    # Reuse a saved gallery row after a failure saving the later checkpoint.
    from asset_library import list_assets
    first = list_assets({"status": "active"}, page_size=100)
    existing = list(first.get("items", []))
    for page in range(2, int(first.get("pages", 1)) + 1):
        existing.extend(list_assets({"status": "active"}, page=page, page_size=100).get("items", []))
    item = next((x for x in existing if (x.get("metadata") or {}).get("visual_operation_id") == operation_id and (x.get("metadata") or {}).get("visual_item_index") == index), None)
    if item is None:
        path = _asset_path(raw)
        meta = {**metadata, "visual_operation_id": operation_id, "visual_item_index": index,
                "visual_status": "VARIATION_CANDIDATE", "contains_text": False, "text_policy": guide.TEXT_POLICY}
        uri = storage.persistir_arquivo(path, "assets/galeria")
        same_bytes_asset = get_asset_by_uri(uri, materialize_file=False)
        if same_bytes_asset:
            # A provider can echo an input image. Gallery byte dedup must not
            # demote/relabel an original Master or an earlier approved result.
            item = create_version(same_bytes_asset["id"], storage_uri_value=uri, name=name, version_label="ABC"[index % 3], metadata=meta)
        else:
            item = salvar_na_galeria(uri, name, kind, ["visual-orchestrator", "candidate"], meta)
        item = update_asset(item["id"], approved=False, visual_status="VARIATION_CANDIDATE", version_label="ABC"[index % 3]) or item
    return {"id": item["id"], "asset_id": item["id"], "storage_uri": item.get("storage_uri") or item.get("caminho_arquivo"),
            "label": "ABC"[index % 3], "visual_status": item.get("visual_status", "VARIATION_CANDIDATE"), "approved": bool(item.get("approved"))}


def generate_world_candidates(plan_id: str, world_master_id: str, *, confirmed: bool = False, operation_key: str | None = None, consent_confirmed: bool = False) -> dict:
    plan, world = _plan(plan_id), ov.load_world_master(world_master_id)
    if not world or not str(world.get("description") or "").strip():
        raise ValueError("Cadastre a descrição do cenário antes de gerar A/B/C.")
    if not plan.get("approvals", {}).get("story") or not plan.get("approvals", {}).get("style"):
        raise PermissionError("Aprove o conteúdo-base e o estilo antes de gerar cenários.")
    emotional = require_emotional_binding(plan)
    emotional_context = "\n".join(direction_prompt(item) for item in emotional["scenes"])
    refs = [_asset_path(str(x)) for x in (world.get("reference_assets") or [])]
    style = plan.get("style_master") or {}
    if not style:
        raise PermissionError("Estilo aprovado não encontrado.")
    payload = {"world": world_master_id, "description": world["description"], "style": style, "emotional_map": emotional["scenes"], "references": [_asset_digest(x) for x in refs]}

    def produce(index, route):
        direction = ["composição ampla com ponto de vista acolhedor", "novo ângulo, mantendo a mesma arquitetura e identidade", "detalhes ambientais claros e profundidade editorial"][index]
        prompt = f"WORLD / LOCATION CANDIDATE {'ABC'[index]}. {world.get('name', '')}. {world['description']}\nSTYLE MASTER: {json.dumps(style, ensure_ascii=False)}\nDireção: {direction}. Sem personagens nem alterações em referências originais.\nCONTEXTO EMOCIONAL APROVADO DA OBRA (não aplicar todas as paletas ao mesmo tempo nem recolorir o Master; representar uma base neutra coerente com materiais, cores e identidade do lugar; aplicar a iluminação emocional específica somente nas cenas vinculadas):\n{emotional_context}\n{guide.artwork_text_policy()}"
        return _generate_image(prompt, refs, route)

    def persist(raw, index, operation_id):
        item = _persist_candidate(raw, name=f"{world.get('name', 'Cenário')} — Proposta {'ABC'[index]}", kind="cenario",
                                  metadata={"world_master_id": world_master_id, "collection": world.get("collection"), "origin": "world_director"}, operation_id=operation_id, index=index)
        fresh = ov.load_world_master(world_master_id)
        candidates = fresh.setdefault("candidates", [])
        if not any(x.get("asset_id") == item["asset_id"] for x in candidates):
            candidates.append({**item, "operation_id": operation_id, "created_at": int(time.time())})
            ov.save_world_master(fresh)
        return item

    return _run(plan_id, "world_candidates", payload, 3, "imagem", confirmed, operation_key, produce, persist, consent_confirmed=consent_confirmed)


def select_world_candidate(world_master_id: str, asset_id: str) -> dict:
    """Explicit author selection promotes this location, never a Character Master."""
    with _LOCK:
        world = ov.load_world_master(world_master_id)
        candidate = next((x for x in world.get("candidates", []) if x.get("asset_id") == asset_id), None)
        asset = get_asset(asset_id, materialize_file=False)
        if not candidate or not asset or asset.get("status") == "archived":
            raise ValueError("Selecione uma candidata ativa deste World Master.")
        uri = asset.get("storage_uri") or asset.get("caminho_arquivo")
        _asset_path(uri)
        if world.get("selected_asset_id") == asset_id and world.get("status") == "approved":
            update_asset(asset_id, approved=True, visual_status="WORLD_MASTER", metadata={"approval": "human", "world_master_id": world_master_id})
            return world
        snapshot = {k: deepcopy(v) for k, v in world.items() if k != "versions"}
        world.setdefault("versions", []).append({"saved_at": int(time.time()), "snapshot": snapshot})
        world.update(selected_asset_id=asset_id, reference_assets=[uri], status="approved")
        world.setdefault("history", []).append({"event": "candidate_selected_by_author", "asset_id": asset_id, "at": int(time.time())})
        result = ov.save_world_master(world)
        update_asset(asset_id, approved=True, visual_status="WORLD_MASTER", metadata={"approval": "human", "world_master_id": world_master_id})
        return result


def generate_scene_options(plan_id: str, scene_key: str, excerpt: str, *, confirmed: bool = False, operation_key: str | None = None, source_scene_number: int | None = None, consent_confirmed: bool = False) -> dict:
    scene_key, excerpt = str(scene_key).strip(), str(excerpt).strip()
    if not scene_key or not excerpt:
        raise ValueError("Informe a identificação da cena e seu trecho aprovado.")
    plan = _plan(plan_id)
    characters, _world, context, signature = _scene_context(plan)
    emotional_item = scene_direction(plan, scene_key, source_scene_number=source_scene_number, excerpt=excerpt)
    context["direcao_emocional_aprovada"] = emotional_item
    canonical_excerpt = source_scene_text(plan, emotional_item["numero"])
    payload = {"scene_key": scene_key, "excerpt": excerpt, "context_fingerprint": signature, "source_scene_number": emotional_item["numero"], "emotional_direction": emotional_item}

    def produce(_index, route):
        def one_shot(system, instruction):
            return client.chamar_llm(system, instruction, strict_provider=route["provider"], no_paid_fallback=True, no_retries=True)
        ideas = guide.suggest_scene_concepts("TEXTO CANÔNICO DA CENA: " + canonical_excerpt + "\nDIREÇÃO ADICIONAL DA PROPOSTA/PAINEL: " + excerpt, characters, project_context=context, text_generator=one_shot)
        for idea in ideas:
            idea.setdefault("editorial_context", {}).update(style_dna=context["style_dna"], direcao_emocional_aprovada=deepcopy(emotional_item))
            idea["emocao"] = emotional_item["direcao"]["emocao_narrativa"]
            idea["psicologia_cores"] = direction_prompt(emotional_item)
            idea["iluminacao"] = emotional_item["direcao"]["luz_emocional"]
        return ideas

    def persist(ideas, _index, operation_id):
        fresh = _plan(plan_id)
        scenes = fresh.setdefault("scene_execution", {})
        current = scenes.get(scene_key) or {}
        if current.get("options_operation_id") != operation_id:
            scenes[scene_key] = {"scene_key": scene_key, "excerpt": excerpt, "options": ideas, "context_fingerprint": signature,
                                "source_scene_number": emotional_item["numero"], "emotional_direction": deepcopy(emotional_item),
                                "options_operation_id": operation_id, "history": [*current.get("history", []), {"event": "scene_options_generated", "operation_id": operation_id}], "assets": []}
            fresh.setdefault("approvals", {}).setdefault("scene_options", {}).pop(scene_key, None)
            ov.save_visual_plan(fresh)
        return {"scene_key": scene_key, "ideas": ideas, "options": ideas, "context_fingerprint": signature}

    return _run(plan_id, "scene_options", payload, 1, "texto", confirmed, operation_key, produce, persist, consent_confirmed=consent_confirmed)


def select_scene_option(plan_id: str, scene_key: str, option_id: str, *, adjustment: str = "") -> dict:
    with _LOCK:
        plan = _plan(plan_id)
        _, _, _, signature = _scene_context(plan)
        scene = (plan.get("scene_execution") or {}).get(str(scene_key), {})
        if scene.get("context_fingerprint") != signature:
            raise PermissionError("Conteúdo, DNA, cenário ou estilo mudou. Gere e aprove novas propostas para esta cena.")
        chosen = next((x for x in scene.get("options", []) if x.get("id") == option_id), None)
        if not chosen:
            raise ValueError("Selecione uma proposta A/B/C existente.")
        plan.setdefault("approvals", {}).setdefault("scene_options", {})[str(scene_key)] = {
            "approved": True, "option_id": option_id, "concept": deepcopy(chosen), "adjustment": str(adjustment).strip(),
            "context_fingerprint": signature, "approved_at": int(time.time())}
        scene["selected_option_id"] = option_id
        return ov.save_visual_plan(plan)


def _selected_scene(plan: dict, scene_key: str, signature: str) -> tuple[dict, dict]:
    scene = (plan.get("scene_execution") or {}).get(str(scene_key), {})
    approval = (plan.get("approvals", {}).get("scene_options") or {}).get(str(scene_key), {})
    if not approval.get("approved") or not approval.get("concept"):
        raise PermissionError(f"Escolha e aprove uma proposta A/B/C para a cena {scene_key}.")
    if approval.get("context_fingerprint") != signature or scene.get("context_fingerprint") != signature:
        raise PermissionError("A aprovação da cena ficou desatualizada após alteração do conteúdo/DNA/estilo/cenário.")
    return scene, approval


def generate_selected_scene(plan_id: str, scene_key: str, *, quantity: int = 1, confirmed: bool = False, operation_key: str | None = None, consent_confirmed: bool = False) -> dict:
    if int(quantity) not in {1, 3}:
        raise ValueError("Escolha uma imagem ou três variações A/B/C.")
    return _generate_scenes(plan_id, [str(scene_key)] * int(quantity), confirmed=confirmed, operation_key=operation_key, consent_confirmed=consent_confirmed)


def generate_scene_batch(plan_id: str, scene_keys: list[str], *, confirmed: bool = False, operation_key: str | None = None, consent_confirmed: bool = False) -> dict:
    keys = [str(x) for x in scene_keys]
    if len(set(keys)) != len(keys):
        raise ValueError("Uma cena não pode aparecer duas vezes no mesmo lote.")
    validar_lote_imagens(len(keys))
    return _generate_scenes(plan_id, keys, confirmed=confirmed, operation_key=operation_key, consent_confirmed=consent_confirmed)


def _generate_scenes(plan_id: str, keys: list[str], *, confirmed: bool, operation_key: str | None, consent_confirmed: bool = False) -> dict:
    plan = _plan(plan_id)
    characters, worlds, context, signature = _scene_context(plan)
    selected = [_selected_scene(plan, key, signature) for key in keys]
    refs = list(dict.fromkeys([*(c["color_master"] for c in characters), *(p for w in worlds for p in w["resolved_references"])]))
    payload = {"scene_keys": keys, "context_fingerprint": signature,
               "selected": [{k: v for k, v in x[1].items() if k != "approved_at"} for x in selected]}

    def produce(index, route):
        _scene, approval = selected[index]
        emotional_item = scene_direction(plan, keys[index], source_scene_number=_scene.get("source_scene_number"))
        concept = deepcopy(approval["concept"])
        concept.setdefault("editorial_context", {}).update(style_dna=context["style_dna"], world_masters=context["world_masters"])
        concept["emocao"] = emotional_item["direcao"]["emocao_narrativa"]
        concept["psicologia_cores"] = direction_prompt(emotional_item)
        concept["iluminacao"] = emotional_item["direcao"]["luz_emocional"]
        concept["editorial_context"]["direcao_emocional_aprovada"] = deepcopy(emotional_item)
        prompt = guide.compose_scene_prompt(concept, characters, adjustment=approval.get("adjustment", ""))
        prompt += "\nDIREÇÃO CANÔNICA OBRIGATÓRIA (prevalece sobre sugestões livres de cor):\n" + direction_prompt(emotional_item)
        prompt += f"\nComposição candidata {'ABC'[index % 3]}. STYLE MASTER aprovado: {json.dumps(context['style_dna'], ensure_ascii=False)}. Preserve identidade e geografia dos World Masters de referência."
        return _generate_image(prompt, refs, route)

    def persist(raw, index, operation_id):
        key = keys[index]
        item = _persist_candidate(raw, name=f"{plan['title']} — Cena {key} — {'ABC'[index % 3]}", kind="cena",
                                  metadata={"project_id": plan["project_id"], "scene_key": key, "scene_concept": selected[index][1]["concept"],
                                            "personagens": [c.get("nome") for c in characters], "origin": "orchestrator_scene_director"}, operation_id=operation_id, index=index)
        fresh = _plan(plan_id)
        scene = fresh.setdefault("scene_execution", {}).setdefault(key, {})
        if not any(x.get("asset_id") == item["asset_id"] for x in scene.setdefault("assets", [])):
            scene["assets"].append({**item, "operation_id": operation_id})
            ov.save_visual_plan(fresh)
        return {**item, "scene_key": key}

    return _run(plan_id, "scene_images", payload, len(keys), "imagem", confirmed, operation_key, produce, persist, consent_confirmed=consent_confirmed)


def apply_scene_asset(plan_id: str, scene_key: str, asset_id: str, *, scene_number: int,
                      confirmed: bool = False, state: dict | None = None) -> dict:
    """Approve/use one candidate in the exact persisted Story Book source.

    ``state`` is an optional identity cross-check, never the save payload. The
    source is loaded afresh from plan.source_ref so another open book, stale
    session or same-title project cannot be overwritten. A manual plan without
    an explicit source remains a reusable gallery workflow.
    """
    if not confirmed:
        raise PermissionError("Confirme a escolha desta ilustração para o livro e o número da cena.")
    with _LOCK:
        plan = _plan(plan_id)
        reference = str(plan.get("source_ref") or "")
        if not reference or not plan.get("source_fingerprint"):
            raise PermissionError("Vincule este pré-voo a um livro salvo antes de aplicar uma ilustração. A candidata permanece na galeria.")
        canonical_ref = reference if storage.is_storage_uri(reference) else storage.storage_uri(reference)
        path = storage.uri_to_path(canonical_ref)
        # A tenant-qualified URI is authorized by uri_to_path before checking
        # the product namespace. Never guess a collection or find by title.
        logical_path = path.split("/", 2)[2] if path.startswith("tenants/") else path
        if not logical_path.startswith("livros/") or not logical_path.endswith(".json"):
            raise PermissionError("Esta aplicação de ilustração exige uma fonte Story Book salva.")
        source = json.loads(storage.BACKEND.get_bytes(path).decode("utf-8"))
        if not isinstance(source, dict):
            raise ValueError("O livro de origem não está disponível.")
        from editorial_dispatch import content_fingerprint
        if content_fingerprint(source) != plan["source_fingerprint"]:
            raise PermissionError("O conteúdo/DNA do livro mudou. Aprove novamente a fonte e as propostas antes de aplicar.")
        source_book_id = source.get("book_id") or source.get("project_id") or source.get("id")
        if plan.get("source_book_id") and source_book_id != plan["source_book_id"]:
            raise PermissionError("A identidade do livro de origem mudou.")
        if state is not None:
            supplied = str(state.get("storage_path") or state.get("source_ref") or "")
            supplied_ref = supplied if storage.is_storage_uri(supplied) else storage.storage_uri(supplied)
            if not supplied or storage.uri_to_path(supplied_ref) != path:
                raise PermissionError("O estado fornecido pertence a outro livro. Nenhum projeto foi alterado.")
            supplied_book_id = state.get("book_id") or state.get("project_id") or state.get("id")
            if source_book_id is not None and supplied_book_id != source_book_id:
                raise PermissionError("O estado fornecido tem outra identidade de livro.")
        number = int(scene_number)
        matching = [x for x in source.get("cenas_texto", []) if int(x.get("numero", -1)) == number]
        if len(matching) != 1:
            raise ValueError("O número deve identificar exatamente uma cena existente neste livro.")
        _, _, _, signature = _scene_context(plan)
        scene, approval = _selected_scene(plan, str(scene_key), signature)
        if scene.get("source_scene_number") != number:
            raise PermissionError("A ilustração pertence a outra cena do mapa emocional aprovado. Gere uma direção para a cena de destino.")
        candidate = next((x for x in scene.get("assets", []) if x.get("asset_id") == asset_id), None)
        asset = get_asset(asset_id, materialize_file=False)
        if not candidate or not asset or asset.get("status") == "archived":
            raise PermissionError("Escolha uma candidata ativa gerada para esta cena do projeto.")
        uri = asset.get("storage_uri") or asset.get("caminho_arquivo")
        _asset_path(uri)
        from agents.ilustrador import definir_imagem_cena, obter_imagem_cena
        from armazenamento import atualizar_livro_salvo
        fresh = deepcopy(source)
        current = obter_imagem_cena(fresh, number)
        if not current or current.get("visual_asset_id") != asset_id or not current.get("aprovado"):
            prompt = guide.compose_scene_prompt(approval["concept"], _characters(plan), adjustment=approval.get("adjustment", ""))
            definir_imagem_cena(fresh, number, uri, prompt, "orchestrator_author_selected", aprovado=True)
            selected = obter_imagem_cena(fresh, number)
            selected["visual_asset_id"] = asset_id
            selected["visual_plan_id"] = plan_id
            selected["visual_scene_key"] = str(scene_key)
            fresh["storage_path"] = canonical_ref
            # Check again immediately before writing; storage has no CAS, so
            # distributed concurrent updates still require a transaction.
            newest = json.loads(storage.BACKEND.get_bytes(path).decode("utf-8"))
            if _fingerprint(newest) != _fingerprint(source):
                raise PermissionError("O livro foi atualizado durante a seleção. Recarregue antes de aplicar.")
            saved_ref = atualizar_livro_salvo(canonical_ref, fresh)
            if storage.uri_to_path(saved_ref) != path:
                raise VisualExecutionError("A persistência retornou uma identidade diferente para o livro.")
        else:
            saved_ref = canonical_ref
        # Project use is an approved variation, never Character Universe
        # promotion. Save succeeded before marking this downstream checkpoint.
        if asset.get("visual_status") not in {"COLOR_MASTER", "LINEART_MASTER", "WORLD_MASTER"}:
            guide.approve_asset_as_variation(asset_id)
        scene["selected_asset_id"] = asset_id
        scene["book_scene_number"] = number
        scene["applied_source_ref"] = canonical_ref
        ov.save_visual_plan(plan)
        return {"state": fresh, "storage_path": saved_ref, "asset_id": asset_id,
                "scene_number": number, "plan": plan}


def reconcile_visual_attempt(plan_id: str, operation_id: str, item_index: int, *, actual_cost_usd: float,
                             recovered_asset_id: str = "", confirmed: bool = False) -> dict:
    """Explicitly reconcile an ambiguous call from provider evidence, never retry it."""
    if not confirmed:
        raise PermissionError("Confirme a conferência do resultado e custo no provedor.")
    cost = float(actual_cost_usd)
    if not math.isfinite(cost) or cost < 0:
        raise ValueError("Informe um custo confirmado, finito e não negativo.")
    with _LOCK:
        plan = _plan(plan_id)
        ledger = _ledger(plan)
        operation = ledger["operations"].get(operation_id)
        if not operation:
            raise ValueError("Operação não encontrada.")
        item = next((x for x in operation["items"] if x["index"] == int(item_index)), None)
        if item is None or item["state"] not in {"uncertain", "running"}:
            raise ValueError("A tentativa não precisa de reconciliação.")
        result = None
        if recovered_asset_id:
            asset = get_asset(recovered_asset_id, materialize_file=False)
            if not asset or asset.get("status") == "archived":
                raise ValueError("Asset recuperado não encontrado.")
            uri = asset.get("storage_uri") or asset.get("caminho_arquivo")
            _asset_path(uri)
            result = {"asset_id": recovered_asset_id, "id": recovered_asset_id, "storage_uri": uri, "recovered": True}
        item.update(state="succeeded" if result else "reconciled_failed", actual_usd=cost, reserved=False,
                    reconciled_at=int(time.time()), reconciliation="human_provider_evidence")
        if result:
            item["result"] = result
        operation["status"] = "reconciled_partial"
        _save_ledger(plan, ledger)
        _sync_budget(plan_id, ledger)
        return _snapshot(operation, ledger)


def element_lock_capability() -> dict:
    return {"available": False, "status": "provider_mask_edit_unavailable",
            "reason": "Os clientes de imagem atuais não expõem edição com máscara e preservação de pixels fora da máscara. Uma instrução em texto não garante Element Lock."}


def execute_element_lock(*_args, **_kwargs) -> dict:
    """Fail closed until an existing provider supports a real mask-edit API."""
    return element_lock_capability()

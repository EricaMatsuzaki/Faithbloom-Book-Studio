"""FaithBloom Orchestrator — visual approval gates and controlled image edits.

This module keeps author control before expensive visual generation:
story -> characters -> locations -> style -> scene options -> illustrations.
It also defines generation cost modes, World/Location Masters and Element Lock.
"""
from __future__ import annotations

import time
import uuid
from copy import deepcopy

from armazenamento import _json, _save_json, _slug

VISUAL_PLAN_INDEX = "orchestrator/visual_plans/index.json"
WORLD_MASTER_INDEX = "orchestrator/world_masters/index.json"

GENERATION_MODES = {
    "free_first": {
        "label": "🆓 Gratuito primeiro",
        "description": "Tenta primeiro uma opção sem cobrança direta disponível; se não houver, para antes de gastar.",
        "requires_paid_confirmation": True,
    },
    "economy": {
        "label": "💰 Econômico",
        "description": "Prioriza o menor custo compatível com a qualidade mínima definida.",
        "requires_paid_confirmation": True,
    },
    "premium": {
        "label": "💎 Premium",
        "description": "Prioriza consistência e qualidade visual, sempre mostrando a estimativa antes de lotes caros.",
        "requires_paid_confirmation": True,
    },
    "automatic": {
        "label": "🤖 Automático",
        "description": "O Orquestrador escolhe entre grátis, econômico e premium respeitando orçamento e qualidade.",
        "requires_paid_confirmation": True,
    },
}

VISUAL_STAGES = (
    "story",
    "characters",
    "locations",
    "style",
    "scene_options",
    "illustrations",
    "qa",
    "layout",
    "publish",
)

DEFAULT_LOCKS = {
    "characters": True,
    "pose_composition": True,
    "expressions": True,
    "wardrobe": True,
    "style": True,
    "scenario": True,
    "lighting": True,
    "text": True,
}


def _index(path: str) -> list[dict]:
    value = _json(path, [])
    return value if isinstance(value, list) else []


def _save_index(path: str, item: dict, keys: tuple[str, ...] = ("id",)) -> None:
    items = _index(path)
    def same(existing: dict) -> bool:
        return all(existing.get(k) == item.get(k) for k in keys)
    items = [x for x in items if not same(x)]
    items.append(item)
    _save_json(path, items)


def create_visual_plan(
    project_id: str,
    title: str,
    story_text: str = "",
    characters: list[dict] | None = None,
    locations: list[dict] | None = None,
    generation_mode: str = "free_first",
    budget_limit_usd: float | None = None,
) -> dict:
    if generation_mode not in GENERATION_MODES:
        raise ValueError("Modo de geração visual inválido.")
    plan_id = uuid.uuid4().hex
    now = int(time.time())
    plan = {
        "id": plan_id,
        "project_id": project_id,
        "title": title.strip() or "Projeto sem título",
        "story_text": story_text,
        "generation_mode": generation_mode,
        "budget_limit_usd": budget_limit_usd,
        "budget_spent_usd": 0.0,
        "approvals": {
            "story": False,
            "characters": {},
            "locations": {},
            "style": False,
            "scene_options": {},
        },
        "characters": deepcopy(characters or []),
        "locations": deepcopy(locations or []),
        "style_master": {},
        "status": "visual_preflight",
        "created_at": now,
        "updated_at": now,
        "history": [],
    }
    _save_json(f"orchestrator/visual_plans/{plan_id}.json", plan)
    _save_index(VISUAL_PLAN_INDEX, {"id": plan_id, "project_id": project_id, "title": plan["title"], "status": plan["status"]})
    return plan


def load_visual_plan(plan_id: str) -> dict:
    plan = _json(f"orchestrator/visual_plans/{plan_id}.json", {})
    return plan if isinstance(plan, dict) else {}


def save_visual_plan(plan: dict) -> dict:
    plan = deepcopy(plan)
    plan["updated_at"] = int(time.time())
    _save_json(f"orchestrator/visual_plans/{plan['id']}.json", plan)
    _save_index(VISUAL_PLAN_INDEX, {"id": plan["id"], "project_id": plan.get("project_id", ""), "title": plan.get("title", ""), "status": plan.get("status", "")})
    return plan


def approve_story(plan: dict, approved: bool = True) -> dict:
    plan = deepcopy(plan)
    plan.setdefault("approvals", {})["story"] = bool(approved)
    plan.setdefault("history", []).append({"event": "story_approval", "approved": bool(approved), "at": int(time.time())})
    return save_visual_plan(plan)


def approve_character_candidate(plan: dict, character_id: str, candidate_id: str, asset_uri: str = "") -> dict:
    plan = deepcopy(plan)
    approvals = plan.setdefault("approvals", {}).setdefault("characters", {})
    approvals[character_id] = {
        "approved": True,
        "candidate_id": candidate_id,
        "asset_uri": asset_uri,
        "official_master_promoted": False,
        "approved_at": int(time.time()),
    }
    plan.setdefault("history", []).append({"event": "character_candidate_approved", "character_id": character_id, "candidate_id": candidate_id, "at": int(time.time())})
    return save_visual_plan(plan)


def mark_character_master_promoted(plan: dict, character_id: str) -> dict:
    """Records explicit human promotion; this function never promotes Character Universe assets itself."""
    plan = deepcopy(plan)
    record = plan.setdefault("approvals", {}).setdefault("characters", {}).get(character_id)
    if not record or not record.get("approved"):
        raise PermissionError("A referência do personagem precisa ser aprovada antes de virar Master oficial.")
    record["official_master_promoted"] = True
    record["promoted_at"] = int(time.time())
    plan.setdefault("history", []).append({"event": "character_master_promotion_confirmed", "character_id": character_id, "at": int(time.time())})
    return save_visual_plan(plan)


def create_world_master(collection: str, name: str, description: str, reference_assets: list[str] | None = None, metadata: dict | None = None) -> dict:
    wid = uuid.uuid4().hex
    now = int(time.time())
    obj = {
        "id": wid,
        "collection": collection,
        "name": name.strip(),
        "status": "draft",
        "description": description.strip(),
        "reference_assets": list(reference_assets or []),
        "metadata": deepcopy(metadata or {}),
        "versions": [],
        "created_at": now,
        "updated_at": now,
    }
    _save_json(f"orchestrator/world_masters/{wid}.json", obj)
    _save_index(WORLD_MASTER_INDEX, {"id": wid, "collection": collection, "name": obj["name"], "status": obj["status"]})
    return obj


def load_world_master(world_master_id: str) -> dict:
    obj = _json(f"orchestrator/world_masters/{world_master_id}.json", {})
    return obj if isinstance(obj, dict) else {}


def approve_world_master(world_master_id: str) -> dict:
    obj = load_world_master(world_master_id)
    if not obj:
        raise ValueError("World/Location Master não encontrado.")
    snapshot = {k: deepcopy(v) for k, v in obj.items() if k != "versions"}
    obj.setdefault("versions", []).append({"saved_at": int(time.time()), "snapshot": snapshot})
    obj["status"] = "approved"
    obj["updated_at"] = int(time.time())
    _save_json(f"orchestrator/world_masters/{world_master_id}.json", obj)
    _save_index(WORLD_MASTER_INDEX, {"id": obj["id"], "collection": obj.get("collection", ""), "name": obj.get("name", ""), "status": obj["status"]})
    return obj


def link_location_approval(plan: dict, location_key: str, world_master_id: str) -> dict:
    master = load_world_master(world_master_id)
    if master.get("status") != "approved":
        raise PermissionError("O cenário precisa ser aprovado como World/Location Master antes de entrar no lote de cenas.")
    plan = deepcopy(plan)
    plan.setdefault("approvals", {}).setdefault("locations", {})[location_key] = {
        "approved": True,
        "world_master_id": world_master_id,
        "approved_at": int(time.time()),
    }
    return save_visual_plan(plan)


def approve_style(plan: dict, style_master: dict) -> dict:
    plan = deepcopy(plan)
    plan["style_master"] = deepcopy(style_master)
    plan.setdefault("approvals", {})["style"] = True
    plan.setdefault("history", []).append({"event": "style_approved", "at": int(time.time())})
    return save_visual_plan(plan)


def visual_preflight_status(plan: dict) -> dict:
    approvals = plan.get("approvals") or {}
    characters = plan.get("characters") or []
    locations = plan.get("locations") or []
    missing_characters = []
    for c in characters:
        if not c.get("principal", True):
            continue
        cid = str(c.get("id") or c.get("name") or "").strip()
        if not (approvals.get("characters") or {}).get(cid, {}).get("approved"):
            missing_characters.append(cid)
    missing_locations = []
    for loc in locations:
        if not loc.get("required", True):
            continue
        key = str(loc.get("id") or loc.get("name") or "").strip()
        if not (approvals.get("locations") or {}).get(key, {}).get("approved"):
            missing_locations.append(key)
    result = {
        "story_approved": bool(approvals.get("story")),
        "style_approved": bool(approvals.get("style")),
        "missing_characters": missing_characters,
        "missing_locations": missing_locations,
    }
    result["ready_for_scene_generation"] = (
        result["story_approved"] and result["style_approved"]
        and not missing_characters and not missing_locations
    )
    return result


def require_scene_generation_ready(plan: dict) -> None:
    status = visual_preflight_status(plan)
    if status["ready_for_scene_generation"]:
        return
    reasons = []
    if not status["story_approved"]:
        reasons.append("história não aprovada")
    if status["missing_characters"]:
        reasons.append("personagens sem aprovação: " + ", ".join(status["missing_characters"]))
    if status["missing_locations"]:
        reasons.append("cenários sem aprovação: " + ", ".join(status["missing_locations"]))
    if not status["style_approved"]:
        reasons.append("estilo visual não aprovado")
    raise PermissionError("Geração de cenas bloqueada: " + "; ".join(reasons) + ".")


def cost_gate(plan: dict, estimated_usd: float, paid: bool) -> dict:
    """Returns a decision object; paid operations are never silently approved here."""
    estimated = max(0.0, float(estimated_usd or 0.0))
    spent = float(plan.get("budget_spent_usd") or 0.0)
    limit = plan.get("budget_limit_usd")
    over_budget = limit is not None and (spent + estimated) > float(limit)
    return {
        "estimated_usd": estimated,
        "paid": bool(paid),
        "over_budget": over_budget,
        "requires_author_confirmation": bool(paid) or over_budget,
        "remaining_after_usd": None if limit is None else float(limit) - spent - estimated,
    }


def build_element_lock_instruction(
    requested_change: str,
    unlock: list[str] | None = None,
    locks: dict | None = None,
) -> dict:
    """Builds a provider-neutral edit contract for localized visual edits."""
    effective = deepcopy(DEFAULT_LOCKS)
    if locks:
        for key, value in locks.items():
            if key in effective:
                effective[key] = bool(value)
    for key in unlock or []:
        if key not in effective:
            raise ValueError(f"Elemento desconhecido para desbloqueio: {key}")
        effective[key] = False
    locked = [k for k, v in effective.items() if v]
    unlocked = [k for k, v in effective.items() if not v]
    if not unlocked:
        raise ValueError("Desbloqueie ao menos um elemento para editar a imagem.")
    instruction = (
        "EDICAO LOCALIZADA FAITHBLOOM. Preserve rigorosamente os elementos bloqueados: "
        + ", ".join(locked)
        + ". Modifique somente os elementos desbloqueados: "
        + ", ".join(unlocked)
        + ". Pedido da autora: " + requested_change.strip()
        + ". Nao regenere nem redesenhe elementos bloqueados; preserve identidade, geometria e continuidade visual sempre que o provedor suportar edicao por referencia/mascara."
    )
    return {"locks": effective, "locked": locked, "unlocked": unlocked, "instruction": instruction}


def scenario_only_instruction(requested_change: str) -> dict:
    return build_element_lock_instruction(requested_change, unlock=["scenario"])

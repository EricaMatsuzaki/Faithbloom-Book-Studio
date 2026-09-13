"""Visual automation bridge for Full Editorial Remaster Autopilot.

This module extends the existing Restoration Studio instead of replacing it. It
can selectively extract one dominant embedded image per story page from a large
PDF, prepare protected prompts with official Character/Style DNA, and — only
when the author explicitly authorized paid visual generation at the beginning
of the Autopilot run — create derived visual candidates. Candidates are never
approved or promoted to Master automatically.
"""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import os
from pathlib import Path
import re
from typing import Any

from PIL import Image
from pypdf import PdfReader

from character_universe import carregar_personagem_oficial
from editorial_remaster_autopilot import build_final_review_package, record_incident, save_run
from editorial_remaster_quality import rodar_quality_remaster, visual_completion_gate
from editorial_visual_handoff import contexto_cena_para_asset
from openrouter_client import gerar_imagem
from restoration_studio import (
    aprovar_versao,
    carregar_plano_restauracao,
    gerar_variacao_ia,
    montar_prompt_restauracao,
    registrar_decisao,
    salvar_vinculos,
)


def _existing_file(path: str) -> bool:
    return bool(path and Path(path).exists() and Path(path).is_file())


def _safe_ext(name: str) -> str:
    ext = Path(name or "").suffix.lower()
    return ext if ext in {".png", ".jpg", ".jpeg", ".webp"} else ".png"


def _image_size(data: bytes) -> tuple[int, int]:
    try:
        with Image.open(BytesIO(data)) as im:
            return im.size
    except Exception:
        return (0, 0)


def _dominant_page_image(page: Any) -> tuple[bytes, str, tuple[int, int]] | None:
    """Returns the largest decodable embedded image on the page.

    This is intentionally conservative: for a quick-audit PDF we extract only
    one dominant candidate per story page instead of decoding the entire book.
    """
    candidates: list[tuple[int, bytes, str, tuple[int, int]]] = []
    try:
        images = page.images
    except Exception:
        images = []
    for image_obj in images:
        try:
            data = image_obj.data
            size = _image_size(data)
            area = int(size[0]) * int(size[1])
            if data and area > 0:
                candidates.append((area, data, str(image_obj.name or "image.png"), size))
        except Exception:
            continue
    if not candidates:
        return None
    _, data, name, size = max(candidates, key=lambda row: row[0])
    return data, name, size


def ensure_story_visual_assets(project: dict, state: dict) -> dict:
    """Selectively materializes dominant image assets for mapped story pages."""
    plan = carregar_plano_restauracao(project)
    if not plan:
        raise RuntimeError("Restoration Plan ausente antes da preparação visual automática.")
    handoff = plan.get("editorial_remaster_handoff") or {}
    scenes = handoff.get("cenas") or []
    pages = sorted({int(x.get("pagina_origem")) for x in scenes if x.get("pagina_origem") is not None})
    if not pages:
        return {"extracted": 0, "already_available": 0, "unresolved_pages": [], "assets": []}

    original = state.get("original") or {}
    pdf_path = str(original.get("arquivo") or "")
    if not _existing_file(pdf_path):
        raise RuntimeError("PDF original não está acessível para extração visual seletiva.")

    existing = list(plan.get("assets_detectados") or [])
    usable_by_page = {
        int(a.get("pagina")): a
        for a in existing
        if a.get("pagina") is not None and _existing_file(str(a.get("arquivo") or ""))
    }
    out_dir = Path(project["pasta"]) / "extraidas" / "autopilot"
    out_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(pdf_path)
    extracted: list[dict] = []
    unresolved: list[int] = []
    already = 0

    for page_number in pages:
        if page_number in usable_by_page:
            already += 1
            extracted.append(deepcopy(usable_by_page[page_number]))
            continue
        if page_number < 1 or page_number > len(reader.pages):
            unresolved.append(page_number)
            continue
        dominant = _dominant_page_image(reader.pages[page_number - 1])
        if not dominant:
            unresolved.append(page_number)
            continue
        data, original_name, size = dominant
        ext = _safe_ext(original_name)
        destination = out_dir / f"pagina_{page_number:03d}_dominante{ext}"
        destination.write_bytes(data)
        asset = {
            "id": f"p{page_number:03d}-autopilot",
            "tipo": "miolo",
            "pagina": page_number,
            "indice": 1,
            "arquivo": str(destination),
            "largura_px": size[0],
            "altura_px": size[1],
            "ppi_estimado": None,
            "status_tecnico": "extraido_seletivamente",
            "metadata": {
                "source": "autopilot_selective_pdf_extraction",
                "selection_policy": "largest_decodable_embedded_image_on_story_page",
                "original_object_name": original_name,
            },
        }
        extracted.append(asset)

    # Keep non-story assets such as cover, but replace quick-audit placeholders
    # on mapped story pages with exactly one dominant visual asset per page.
    kept = [
        deepcopy(a) for a in existing
        if a.get("pagina") is None or int(a.get("pagina") or 0) not in set(pages)
    ]
    plan["assets_detectados"] = kept + extracted
    plan.setdefault("autopilot_visual", {})["selective_extraction"] = {
        "pages_requested": pages,
        "pages_unresolved": unresolved,
        "assets_available": len(extracted),
    }
    salvar_vinculos(project, plan)
    return {
        "extracted": max(0, len(extracted) - already),
        "already_available": already,
        "unresolved_pages": unresolved,
        "assets": extracted,
    }


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9à-ÿ]+", " ", str(value or "").casefold()).strip()


def _characters_for_context(plan: dict, context: dict) -> list[dict]:
    linked = (plan.get("vinculos") or {}).get("characters") or []
    characters: list[dict] = []
    for link in linked:
        character = carregar_personagem_oficial(str(link.get("character_id") or ""))
        if character:
            characters.append(character)
    if not characters:
        return []

    primary_text = _normalize(context.get("personagem_principal", ""))
    scene_text = _normalize(
        " ".join([
            str(context.get("personagem_principal") or ""),
            str(context.get("texto_revisado") or ""),
            str(context.get("contexto_visual") or ""),
        ])
    )
    matched = []
    for character in characters:
        name = _normalize(character.get("nome", ""))
        if not name:
            continue
        if name == primary_text or re.search(rf"(?<!\w){re.escape(name)}(?!\w)", scene_text):
            matched.append(character)
    if matched:
        matched.sort(key=lambda ch: 0 if _normalize(ch.get("nome", "")) == primary_text else 1)
        return matched
    if len(characters) == 1:
        return characters
    return []


def _master_refs(characters: list[dict]) -> list[str]:
    refs = []
    for character in characters:
        master = str(character.get("color_master") or character.get("line_art_master") or "")
        if _existing_file(master) and master not in refs:
            refs.append(master)
    return refs


def _existing_run_version(plan: dict, run_id: str, asset_id: str) -> dict:
    for version in plan.get("versoes_assets") or []:
        metadata = version.get("metadata") or {}
        if metadata.get("autopilot_run_id") == run_id and metadata.get("autopilot_asset_id") == asset_id:
            return version
    return {}


def _tag_version(project: dict, version_id: str, *, run_id: str, asset_id: str, scene_number: int | None) -> dict:
    plan = carregar_plano_restauracao(project)
    for version in plan.get("versoes_assets") or []:
        if version.get("id") == version_id:
            metadata = dict(version.get("metadata") or {})
            metadata.update({
                "autopilot_run_id": run_id,
                "autopilot_asset_id": asset_id,
                "autopilot_scene_number": scene_number,
                "final_human_approval_required": True,
            })
            version["metadata"] = metadata
            break
    return salvar_vinculos(project, plan)


def generate_visual_candidates(project: dict, run: dict) -> dict:
    """Generates unapproved visual candidates only after explicit paid consent."""
    settings = run.get("settings") or {}
    if not settings.get("allow_paid_image_generation"):
        return {
            "authorized": False,
            "generated": 0,
            "reused": 0,
            "unresolved": [],
            "note": "Geração visual paga não foi autorizada no início do Autopilot.",
        }
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY não está configurada para geração visual automática.")

    plan = carregar_plano_restauracao(project)
    handoff = plan.get("editorial_remaster_handoff") or {}
    style_id = str((plan.get("vinculos") or {}).get("style_id") or "")
    run_id = str(run.get("run_id") or "")
    assets = [a for a in (plan.get("assets_detectados") or []) if a.get("pagina") is not None and _existing_file(str(a.get("arquivo") or ""))]
    generated = 0
    reused = 0
    unresolved: list[dict] = []

    for asset in assets:
        asset_id = str(asset.get("id") or "")
        plan = carregar_plano_restauracao(project)
        if _existing_run_version(plan, run_id, asset_id):
            reused += 1
            continue
        context = contexto_cena_para_asset(plan, asset.get("pagina"))
        if not context:
            unresolved.append({"asset_id": asset_id, "pagina": asset.get("pagina"), "motivo": "contexto_editorial_ausente"})
            continue
        characters = _characters_for_context(plan, context)
        refs = _master_refs(characters)
        if not characters or not refs:
            unresolved.append({
                "asset_id": asset_id,
                "pagina": asset.get("pagina"),
                "motivo": "character_master_inequivoco_nao_resolvido",
            })
            continue
        primary = characters[0]
        scene_instruction = (
            f"TEXTO REVISADO DA CENA: {context.get('texto_revisado','')}\n"
            f"CONTEXTO VISUAL: {context.get('contexto_visual','')}\n"
            f"FIGURINO: {context.get('figurino','')}\n"
            f"EXPRESSÃO: {context.get('expressao','')}\n"
            f"TRANSIÇÃO EMOCIONAL: {context.get('transicao_emocional','')}\n"
            f"DIREÇÃO DE COR APROVADA: {context.get('direcao_cor',{})}\n"
            "Não inserir texto editorial na ilustração. Preserve a intenção narrativa e os Masters oficiais."
        )
        variables = {
            key: value for key, value in {
                "expressao": context.get("expressao", ""),
                "figurino": context.get("figurino", ""),
                "cenario": context.get("contexto_visual", ""),
            }.items() if str(value or "").strip()
        }
        prompt = montar_prompt_restauracao(
            "reilustrar",
            character_id=str(primary.get("id") or ""),
            style_id=style_id,
            contexto="story",
            variaveis=variables,
            emocao=str(context.get("emocao") or ""),
            instrucao_autora=scene_instruction,
        )
        decisions = plan.get("decisoes") or []
        if not any(
            (d.get("metadata") or {}).get("autopilot_run_id") == run_id
            and d.get("asset_id") == asset_id
            for d in decisions
        ):
            registrar_decisao(
                project,
                asset_id,
                "reilustrar",
                str(primary.get("id") or ""),
                style_id,
                scene_instruction,
                {"autopilot_run_id": run_id, "prompt": prompt, "editorial_remaster": True},
            )
        output = gerar_variacao_ia(
            project,
            str(asset.get("arquivo") or ""),
            prompt,
            gerar_imagem,
            "autopilot_remaster",
            refs,
        )
        version = output.get("versao") or {}
        _tag_version(
            project,
            str(version.get("id") or ""),
            run_id=run_id,
            asset_id=asset_id,
            scene_number=context.get("numero"),
        )
        generated += 1

    return {
        "authorized": True,
        "generated": generated,
        "reused": reused,
        "unresolved": unresolved,
        "visual_candidates_auto_approved": False,
    }


def run_visual_autopilot(project: dict, run: dict) -> dict:
    """Completes selective visual preparation and refreshes the final package."""
    current = deepcopy(run)
    if current.get("status") not in {"needs_author_review", "running", "blocked", "failed"}:
        return current
    try:
        extraction = ensure_story_visual_assets(project, current.get("remaster_state") or {})
        generation = generate_visual_candidates(project, current)
        visual_gate = visual_completion_gate(project)
        stage = (current.get("stages") or {}).setdefault("visual_preflight", {})
        stage["status"] = "completed"
        stage["result"] = {
            "selective_extraction": extraction,
            "generation": generation,
            "visual_completion_before_final_author_approval": visual_gate,
            "visual_candidates_auto_approved": False,
        }
        current["status"] = "needs_author_review"
        current.setdefault("audit_trail", []).append({
            "event": "visual_autopilot_prepared",
            "generated": generation.get("generated", 0),
            "unresolved": len(generation.get("unresolved") or []),
        })
        current["final_review_package"] = build_final_review_package(
            current, current.get("remaster_state") or {}, project
        )
        return save_run(project, current)
    except Exception as exc:
        record_incident(project, current, "visual_preflight", exc)
        current = deepcopy(current)
        stage = (current.get("stages") or {}).setdefault("visual_preflight", {})
        stage["status"] = "blocked"
        stage["error"] = str(exc)
        current["status"] = "blocked"
        return save_run(project, current)


def approve_run_visual_candidates_and_quality(project: dict, run: dict) -> dict:
    """One final human decision can approve all candidates from this run, then QA."""
    current = deepcopy(run)
    run_id = str(current.get("run_id") or "")
    plan = carregar_plano_restauracao(project)
    candidate_ids = [
        str(v.get("id") or "")
        for v in plan.get("versoes_assets") or []
        if (v.get("metadata") or {}).get("autopilot_run_id") == run_id and not v.get("aprovada")
    ]
    for version_id in candidate_ids:
        if version_id:
            aprovar_versao(project, version_id)

    quality_report = {}
    visual_gate = visual_completion_gate(project)
    if visual_gate.get("ok"):
        quality_report = rodar_quality_remaster(current.get("remaster_state") or {}, project)
    current.setdefault("audit_trail", []).append({
        "event": "final_visual_candidates_approved_by_author",
        "versions": candidate_ids,
        "visual_gate_ok": bool(visual_gate.get("ok")),
    })
    quality_stage = (current.get("stages") or {}).setdefault("quality_preflight", {})
    quality_stage["result"] = {
        **dict(quality_stage.get("result") or {}),
        "visual_after_author_approval": visual_gate,
        "quality_guardian_final": deepcopy(quality_report),
    }
    current["final_review_package"] = build_final_review_package(
        current, current.get("remaster_state") or {}, project
    )
    current["final_review_package"]["quality_guardian_final"] = deepcopy(quality_report)
    return save_run(project, current)

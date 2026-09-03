"""FaithBloom Refinamento 11 — Publishing & Distribution Center.

Orquestra uma obra já revisada pelo Quality Guardian em edições/destinos de
publicação. Este módulo NÃO publica automaticamente em lojas externas: ele
organiza readiness, arquivos, metadados, conflitos de direitos/exclusividade,
snapshot das especificações e pacotes por canal.

Princípios:
- Book Master nunca é alterado silenciosamente.
- Quality Guardian é gate de release, não certificação de terceiros.
- cada destino usa a versão da especificação registrada no Platform Registry.
- nenhum status "live" é inferido: precisa ser registrado explicitamente.
- KDP Select/exclusividade digital bloqueia destinos digitais concorrentes.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid
import zipfile
from typing import Any

from platform_registry import get_platform, registry_snapshot, verification_state
from platform_format_engine import normalizar_master, preflight_target, compatibility
from storage_backend import BACKEND, is_storage_uri, materializar
from pacote_publicacao import normalizar_metadata, disclosure_ia

DATA_PREFIX = "publishing_distribution"
INDEX_PATH = f"{DATA_PREFIX}/index.json"

STATUS_ORDER = ["draft", "blocked", "ready", "submitted", "processing", "live", "rejected", "paused", "withdrawn"]

DIGITAL_PRODUCTS = {"ebook", "digital_pdf", "printable", "audiobook"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9À-ÿ_-]+", "-", value or "book").strip("-").lower()
    return value or "book"


def _read_json(path: str, default: Any) -> Any:
    return BACKEND.get_json(path, default)


def _save_json(path: str, value: Any) -> str:
    return BACKEND.put_json(path, value)


def _exists_file(value: str | None) -> bool:
    if not value:
        return False
    if is_storage_uri(value):
        try:
            return BACKEND.exists(value.replace("fb://", "", 1))
        except Exception:
            return False
    return Path(str(value)).exists()


def _materialize_if_needed(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return materializar(value) if is_storage_uri(value) else value
    except Exception:
        return value


def project_fingerprint(state: dict) -> str:
    """Fingerprint editorial para ligar distribuição ao Quality Guardian.

    Usa os campos que alteram a obra/edição, sem incluir status operacionais de
    distribuição. A implementação espelha o propósito do Guardian sem depender
    de detalhes privados do relatório.
    """
    from quality_guardian import project_fingerprint as guardian_fingerprint
    return guardian_fingerprint(state or {})


def guardian_gate(state: dict, report: dict | None) -> dict:
    """Valida se há Quality Gate interno vigente para o conteúdo atual."""
    if not report:
        return {"passed": False, "status": "missing", "message": "Quality Guardian ainda não foi concluído para esta obra."}
    current = project_fingerprint(state)
    if report.get("project_fingerprint") != current:
        return {"passed": False, "status": "stale", "message": "O conteúdo mudou depois da revisão do Quality Guardian. Execute o Guardian novamente."}
    cert = report.get("certificate") or {}
    if cert.get("status") != "INTERNAL_QUALITY_GATE_PASSED":
        return {"passed": False, "status": "not_certified", "message": "O relatório ainda não possui INTERNAL QUALITY GATE PASSED."}
    if not (report.get("author_final_approval") or {}).get("approved"):
        return {"passed": False, "status": "author_not_approved", "message": "A aprovação final humana não está registrada."}
    return {
        "passed": True,
        "status": "passed",
        "message": "Quality Gate interno vigente para esta versão.",
        "certificate_id": cert.get("certificate_id"),
        "report_id": report.get("id"),
        "run_number": report.get("run_number"),
    }


def _master_from_state(state: dict) -> dict:
    return normalizar_master({
        "title": state.get("titulo", ""),
        "language": state.get("idioma_original", "pt-BR"),
        "trim_width_in": state.get("trim_largura_in", state.get("trim_width_in", 8.5)),
        "trim_height_in": state.get("trim_altura_in", state.get("trim_height_in", 8.5)),
        "page_count": state.get("paginas_fisicas", state.get("paginas_minimas", 32)),
        "interior": state.get("interior_publicacao", "premium_color"),
        "binding": state.get("binding", "paperback"),
        "bleed": state.get("usar_bleed", True),
        "target_ppi": state.get("target_ppi", 300),
        "kdp_select_active": state.get("kdp_select_active", False),
        "isbn_mode": state.get("isbn_mode", "platform"),
        "isbn": state.get("isbn", ""),
    })


def _default_assets(state: dict, product: str) -> dict:
    """Seleciona somente assets explicitamente registrados para a edição."""
    base = {
        "interior_pdf": state.get("pdf_miolo_print_ready") or state.get("pdf_miolo"),
        "cover_pdf": state.get("capa_fisica_pdf") or state.get("capa_fisica_wrap"),
        "epub": state.get("epub") or state.get("ebook_epub"),
        "epubcheck_passed": bool(state.get("epubcheck_passed")),
        "digital_file": state.get("digital_file"),
        "audiobook_master": state.get("audiobook_master") or state.get("audiobook_final"),
        "cover_ebook": state.get("capa_ebook"),
    }
    return base


def exclusivity_conflicts(master: dict, targets: list[dict]) -> list[dict]:
    """Detecta conflitos explícitos de distribuição digital."""
    if not master.get("kdp_select_active"):
        return []
    conflicts = []
    for t in targets:
        pid = t.get("platform_id")
        product = t.get("product")
        if product in DIGITAL_PRODUCTS and pid != "amazon_kdp":
            conflicts.append({
                "platform_id": pid,
                "product": product,
                "code": "kdp_select_digital_exclusivity",
                "severity": "blocked",
                "message": "KDP Select/exclusividade digital está ativa; este destino digital concorrente não pode ser liberado enquanto a exclusividade estiver vigente.",
            })
    return conflicts


def metadata_readiness(state: dict, *, locale: str = "") -> dict:
    md = normalizar_metadata(state)
    locale = locale or state.get("idioma_original") or "pt-BR"
    missing = []
    recommended = []
    if not str(md.get("titulo") or "").strip(): missing.append("titulo")
    if not str(md.get("autora") or "").strip(): missing.append("autoria")
    if not str(md.get("descricao_kdp") or "").strip(): recommended.append("descricao")
    if not (md.get("palavras_chave") or []): recommended.append("palavras_chave")
    if not (md.get("categorias") or []): recommended.append("categorias")
    return {
        "locale": locale,
        "ready_minimum": not missing,
        "missing_required": missing,
        "missing_recommended": recommended,
        "metadata": md,
    }


def ai_disclosure_readiness(state: dict) -> dict:
    d = disclosure_ia(state)
    # O FaithBloom prepara registro interno; a exigência exata varia por canal.
    return {
        "recorded": bool(d),
        "record": d,
        "note": "Confirmar no formulário atual de cada plataforma quais declarações de IA são exigidas no momento da submissão.",
    }


def create_distribution_plan(state: dict, targets: list[dict], guardian_report: dict | None = None,
                             edition_overrides: dict | None = None) -> dict:
    """Cria matriz de distribuição por destino sem executar publicação externa."""
    state = deepcopy(state or {})
    targets = deepcopy(targets or [])
    master = _master_from_state(state)
    gate = guardian_gate(state, guardian_report)
    conflicts = {(x["platform_id"], x["product"]): x for x in exclusivity_conflicts(master, targets)}
    edition_overrides = edition_overrides or {}
    rows = []

    for target in targets:
        pid = target["platform_id"]
        product = target.get("product") or master.get("binding") or "paperback"
        platform = get_platform(pid)
        assets = _default_assets(state, product)
        override = edition_overrides.get(f"{pid}:{product}") or {}
        assets.update(override.get("assets") or {})
        edition_master = deepcopy(master)
        edition_master.update(override.get("master") or {})
        comp = compatibility(edition_master, pid, product)
        pf = preflight_target(edition_master, pid, product, assets)
        spec_state = verification_state(platform)
        meta = metadata_readiness(state, locale=target.get("locale") or edition_master.get("language"))
        blockers = []
        if not gate["passed"]:
            blockers.append({"code": "quality_guardian_gate", "message": gate["message"]})
        if (pid, product) in conflicts:
            blockers.append({"code": conflicts[(pid, product)]["code"], "message": conflicts[(pid, product)]["message"]})
        if not pf.get("ready"):
            blockers.append({"code": "platform_preflight", "message": "O preflight técnico da plataforma ainda possui pendências/bloqueios."})
        if not meta["ready_minimum"]:
            blockers.append({"code": "metadata_required", "message": "Metadados mínimos obrigatórios estão incompletos."})
        if spec_state.get("state") == "stale":
            blockers.append({"code": "stale_platform_spec", "message": "A especificação registrada está desatualizada pelo limiar interno; revisar a fonte oficial antes da submissão."})
        elif spec_state.get("state") in {"unverified", "needs_verification"}:
            blockers.append({"code": "unverified_platform_spec", "message": "Esta plataforma ainda não possui especificação oficial verificada no Registry."})

        ready = not blockers
        rows.append({
            "edition_id": uuid.uuid5(uuid.NAMESPACE_URL, f"{state.get('titulo','')}|{edition_master.get('language')}|{pid}|{product}").hex,
            "platform_id": pid,
            "platform_name": platform.get("name", pid),
            "category": platform.get("category"),
            "product": product,
            "locale": target.get("locale") or edition_master.get("language"),
            "master": edition_master,
            "assets": assets,
            "compatibility": comp,
            "preflight": pf,
            "metadata": meta,
            "specification": {
                "spec_version": platform.get("spec_version"),
                "last_verified": platform.get("last_verified"),
                "source_urls": platform.get("source_urls") or [],
                "verification": spec_state,
            },
            "blockers": blockers,
            "readiness": "ready" if ready else "blocked",
            "submission": {
                "status": "draft",
                "external_id": "",
                "store_url": "",
                "submitted_at": None,
                "live_at": None,
                "notes": "",
                "updated_at": _now(),
            },
        })

    plan_id = "FB-DIST-" + uuid.uuid4().hex[:12].upper()
    return {
        "id": plan_id,
        "title": state.get("titulo") or "Projeto sem título",
        "collection": state.get("colecao", ""),
        "created_at": _now(),
        "updated_at": _now(),
        "project_fingerprint": project_fingerprint(state),
        "quality_gate": gate,
        "master": master,
        "policy": {
            "no_silent_resize": True,
            "no_auto_publish": True,
            "manual_external_status_confirmation": True,
            "platform_specs_versioned": True,
            "kdp_select_guard": True,
        },
        "ai_disclosure": ai_disclosure_readiness(state),
        "editions": rows,
        "summary": summarize_distribution(rows),
        "registry_snapshot": registry_snapshot(),
    }


def summarize_distribution(editions: list[dict]) -> dict:
    return {
        "total": len(editions),
        "ready": sum(1 for x in editions if x.get("readiness") == "ready"),
        "blocked": sum(1 for x in editions if x.get("readiness") != "ready"),
        "submitted": sum(1 for x in editions if (x.get("submission") or {}).get("status") in {"submitted", "processing"}),
        "live": sum(1 for x in editions if (x.get("submission") or {}).get("status") == "live"),
        "rejected": sum(1 for x in editions if (x.get("submission") or {}).get("status") == "rejected"),
    }


def update_submission(plan: dict, edition_id: str, status: str, *, external_id: str = "",
                      store_url: str = "", notes: str = "") -> dict:
    if status not in STATUS_ORDER:
        raise ValueError("Status de distribuição inválido.")
    out = deepcopy(plan)
    row = next((x for x in out.get("editions", []) if x.get("edition_id") == edition_id), None)
    if not row:
        raise KeyError(edition_id)
    if status in {"submitted", "processing", "live"} and row.get("readiness") != "ready":
        raise ValueError("Esta edição ainda está bloqueada e não pode ser marcada como submetida/live.")
    sub = row.setdefault("submission", {})
    sub.update({"status": status, "external_id": external_id.strip(), "store_url": store_url.strip(), "notes": notes.strip(), "updated_at": _now()})
    if status == "submitted" and not sub.get("submitted_at"): sub["submitted_at"] = _now()
    if status == "live" and not sub.get("live_at"): sub["live_at"] = _now()
    out["updated_at"] = _now()
    out["summary"] = summarize_distribution(out.get("editions", []))
    return out


def launch_readiness(plan: dict) -> dict:
    """Resumo editorial/operacional; não confunde pacote pronto com loja publicada."""
    editions = plan.get("editions") or []
    gate = plan.get("quality_gate") or {}
    return {
        "quality_gate_passed": bool(gate.get("passed")),
        "all_targets_ready": bool(editions) and all(x.get("readiness") == "ready" for x in editions),
        "ready_targets": [x.get("edition_id") for x in editions if x.get("readiness") == "ready"],
        "blocked_targets": [x.get("edition_id") for x in editions if x.get("readiness") != "ready"],
        "live_targets": [x.get("edition_id") for x in editions if (x.get("submission") or {}).get("status") == "live"],
        "note": "Ready significa que o FaithBloom não encontrou bloqueios internos conhecidos. A plataforma ainda pode executar validações próprias e exigir correções.",
    }


def _copy_asset(src: str | None, dst: Path) -> bool:
    if not src:
        return False
    actual = _materialize_if_needed(src)
    if not actual or not Path(actual).exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(actual, dst)
    return True


def build_channel_package(state: dict, plan: dict, edition_id: str, output_root: str = "saida_distribuicao") -> dict:
    """Gera pacote de UMA edição somente se ela estiver pronta internamente."""
    row = next((x for x in plan.get("editions", []) if x.get("edition_id") == edition_id), None)
    if not row:
        raise KeyError(edition_id)
    if row.get("readiness") != "ready":
        raise ValueError("Edição bloqueada: resolva o preflight/Quality Gate antes de gerar o pacote final do canal.")

    platform_id = row["platform_id"]
    product = row["product"]
    root = Path(output_root) / _slug(state.get("titulo") or "book") / f"{platform_id}__{product}__{_slug(row.get('locale') or 'locale')}"
    if root.exists(): shutil.rmtree(root)
    (root / "FILES").mkdir(parents=True)
    (root / "METADATA").mkdir(parents=True)
    (root / "RECORDS").mkdir(parents=True)

    assets = row.get("assets") or {}
    copied = []
    if product in {"paperback", "hardcover"}:
        if _copy_asset(assets.get("interior_pdf"), root / "FILES" / "interior.pdf"): copied.append("FILES/interior.pdf")
        if _copy_asset(assets.get("cover_pdf"), root / "FILES" / "cover.pdf"): copied.append("FILES/cover.pdf")
    elif product == "ebook":
        if _copy_asset(assets.get("epub"), root / "FILES" / "book.epub"): copied.append("FILES/book.epub")
        if _copy_asset(assets.get("cover_ebook"), root / "FILES" / ("cover" + Path(str(_materialize_if_needed(assets.get('cover_ebook')) or '.jpg')).suffix)): copied.append("FILES/cover")
    elif product == "audiobook":
        if _copy_asset(assets.get("audiobook_master"), root / "FILES" / "audiobook_master.mp3"): copied.append("FILES/audiobook_master.mp3")
    else:
        if _copy_asset(assets.get("digital_file"), root / "FILES" / Path(str(_materialize_if_needed(assets.get("digital_file")) or "digital_file.pdf")).name): copied.append("FILES/digital")

    (root / "METADATA" / "metadata.json").write_text(json.dumps(row.get("metadata", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "RECORDS" / "preflight.json").write_text(json.dumps(row.get("preflight", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "RECORDS" / "platform_spec_snapshot.json").write_text(json.dumps(row.get("specification", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "RECORDS" / "quality_gate.json").write_text(json.dumps(plan.get("quality_gate", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "RECORDS" / "ai_disclosure.json").write_text(json.dumps(plan.get("ai_disclosure", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "README.txt").write_text(
        f"FaithBloom Distribution Package\nPlatform: {row.get('platform_name')}\nProduct: {product}\nLocale: {row.get('locale')}\n\n"
        "READY = aprovado pelo gate interno conhecido do FaithBloom. Ainda use o preview/validador/formulário oficial da plataforma e confirme requisitos atuais antes de publicar.\n",
        encoding="utf-8",
    )
    zip_path = root.with_suffix(".zip")
    if zip_path.exists(): zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if p.is_file(): z.write(p, p.relative_to(root.parent))
    return {"folder": str(root), "zip": str(zip_path), "copied": copied, "edition_id": edition_id}


def save_distribution_plan(plan: dict) -> dict:
    out = deepcopy(plan)
    out["updated_at"] = _now()
    pid = out.get("id") or ("FB-DIST-" + uuid.uuid4().hex[:12].upper())
    out["id"] = pid
    _save_json(f"{DATA_PREFIX}/plans/{pid}.json", out)
    idx = _read_json(INDEX_PATH, []) or []
    card = {"id": pid, "title": out.get("title", ""), "updated_at": out.get("updated_at"), "summary": out.get("summary", {})}
    idx = [x for x in idx if x.get("id") != pid] + [card]
    _save_json(INDEX_PATH, idx[-300:])
    return out


def load_distribution_plan(plan_id: str) -> dict:
    return _read_json(f"{DATA_PREFIX}/plans/{plan_id}.json", {}) or {}


def list_distribution_plans() -> list[dict]:
    return sorted(_read_json(INDEX_PATH, []) or [], key=lambda x: x.get("updated_at", ""), reverse=True)

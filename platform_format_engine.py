"""FaithBloom Refinamento 07 — motor de compatibilidade e preflight por plataforma.

O objetivo é transformar um BOOK MASTER em um plano explícito de derivados.
O motor nunca redimensiona/corta silenciosamente: incompatibilidades de aspecto,
formatos ausentes e regras não verificadas viram alertas para decisão da autora.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from platform_registry import get_platform, list_platforms, verification_state

MM_PER_IN = 25.4
PT_PER_IN = 72.0


def inch_to_mm(value: float) -> float:
    return round(float(value) * MM_PER_IN, 3)


def mm_to_in(value: float) -> float:
    return round(float(value) / MM_PER_IN, 4)


@dataclass
class BookMasterSpec:
    title: str = ""
    language: str = "pt-BR"
    trim_width_in: float = 8.5
    trim_height_in: float = 8.5
    page_count: int = 32
    interior: str = "premium_color"  # premium_color, standard_color, black_white
    binding: str = "paperback"
    bleed: bool = True
    target_ppi: int = 300
    kdp_select_active: bool = False
    isbn_mode: str = "platform"  # own, platform, none
    isbn: str = ""
    ai_disclosure_required_review: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def normalizar_master(data: dict | BookMasterSpec) -> dict:
    if isinstance(data, BookMasterSpec):
        return data.to_dict()
    base = BookMasterSpec().to_dict()
    base.update({k: v for k, v in dict(data or {}).items() if v is not None})
    base["trim_width_in"] = float(base["trim_width_in"])
    base["trim_height_in"] = float(base["trim_height_in"])
    base["page_count"] = int(base["page_count"])
    base["target_ppi"] = int(base["target_ppi"])
    return base


def _aspect(w: float, h: float) -> float:
    return float(w) / float(h) if h else 0.0


def aspect_delta_percent(a_w: float, a_h: float, b_w: float, b_h: float) -> float:
    a, b = _aspect(a_w, a_h), _aspect(b_w, b_h)
    if not a or not b:
        return 100.0
    return round(abs(a - b) / a * 100, 3)


def nearest_trim(platform: dict, width_in: float, height_in: float) -> dict | None:
    presets = (platform.get("print") or {}).get("common_trim_presets_in") or []
    if not presets:
        return None
    current_aspect = _aspect(width_in, height_in)
    ranked = []
    for w, h in presets:
        aspect_penalty = abs(_aspect(w, h) - current_aspect) * 100
        size_penalty = abs(w - width_in) + abs(h - height_in)
        ranked.append((aspect_penalty * 4 + size_penalty, float(w), float(h)))
    _, w, h = sorted(ranked)[0]
    return {
        "width_in": w,
        "height_in": h,
        "width_mm": inch_to_mm(w),
        "height_mm": inch_to_mm(h),
        "aspect_delta_pct": aspect_delta_percent(width_in, height_in, w, h),
    }


def _product_for_master(master: dict, requested_product: str | None = None) -> str:
    return requested_product or str(master.get("binding") or "paperback")


def compatibility(master: dict | BookMasterSpec, platform_id: str, product: str | None = None) -> dict:
    m = normalizar_master(master)
    p = get_platform(platform_id)
    prod = _product_for_master(m, product)
    supported = prod in (p.get("products") or [])
    alerts: list[dict] = []
    if not supported:
        alerts.append({"severity": "blocker", "code": "product_not_supported", "message": f"{p['name']} não possui perfil para {prod}."})
    verify = verification_state(p)
    if verify["state"] != "current":
        alerts.append({"severity": "warning", "code": "spec_verification", "message": verify["message"]})

    print_like = prod in {"paperback", "hardcover", "coil_bound", "saddle_stitch", "print_distribution", "photo_book"}
    digital_like = prod in {"ebook", "digital_download"}
    nearest = None
    if print_like:
        nearest = nearest_trim(p, m["trim_width_in"], m["trim_height_in"])
        if nearest:
            d = nearest["aspect_delta_pct"]
            exact = abs(nearest["width_in"] - m["trim_width_in"]) < 0.005 and abs(nearest["height_in"] - m["trim_height_in"]) < 0.005
            if not exact:
                sev = "warning" if d <= 1.0 else "review"
                alerts.append({
                    "severity": sev,
                    "code": "derived_trim_needed",
                    "message": f"O Master {m['trim_width_in']}×{m['trim_height_in']} in não está entre os presets carregados. Próximo preset: {nearest['width_in']}×{nearest['height_in']} in (diferença de proporção {d:.2f}%). Não redimensionar silenciosamente.",
                })
        elif supported:
            alerts.append({"severity": "review", "code": "trim_matrix_manual", "message": "Esta plataforma usa matriz/template oficial; confirme o trim selecionado antes da exportação."})

    if digital_like:
        formats = (p.get("accepted_formats") or {}).get(prod, [])
        if "epub" in formats:
            alerts.append({"severity": "info", "code": "epub_recommended", "message": "Gerar EPUB específico para leitura digital; não reutilizar automaticamente o PDF de impressão."})

    # KDP Select: exclusividade é uma propriedade da edição digital, não do físico.
    if m.get("kdp_select_active") and platform_id != "amazon_kdp" and prod == "ebook":
        alerts.append({"severity": "blocker", "code": "digital_exclusivity", "message": "KDP Select está marcado como ativo: não preparar distribuição digital concorrente enquanto a exclusividade estiver vigente."})

    status = "blocked" if any(a["severity"] == "blocker" for a in alerts) else ("review" if any(a["severity"] in {"warning", "review"} for a in alerts) else "compatible")
    return {
        "platform_id": platform_id,
        "platform_name": p["name"],
        "product": prod,
        "supported": supported,
        "status": status,
        "master": m,
        "nearest_trim": nearest,
        "accepted_formats": (p.get("accepted_formats") or {}).get(prod, []),
        "spec_version": p.get("spec_version", ""),
        "last_verified": p.get("last_verified", ""),
        "alerts": alerts,
    }


def compare_platforms(master: dict | BookMasterSpec, targets: list[dict]) -> list[dict]:
    results = []
    for target in targets:
        pid = target["platform_id"] if isinstance(target, dict) else str(target)
        product = target.get("product") if isinstance(target, dict) else None
        results.append(compatibility(master, pid, product))
    return results


def calculate_print_geometry(master: dict | BookMasterSpec, platform_id: str, product: str = "paperback") -> dict:
    m = normalizar_master(master)
    p = get_platform(platform_id)
    spec = p.get("print") or {}
    if product not in p.get("products", []):
        raise ValueError(f"{p['name']} não suporta {product} no perfil atual.")

    # KDP: reaproveita o cálculo já consolidado no projeto.
    if platform_id == "amazon_kdp" and product == "paperback":
        from kdp_rules import calcular_dimensoes_capa_fisica
        paper_map = {"premium_color": "cor_premium", "standard_color": "cor_padrao", "black_white": "branco"}
        g = calcular_dimensoes_capa_fisica(m["trim_width_in"], m["trim_height_in"], m["page_count"], paper_map.get(m["interior"], "cor_premium"))
        return {
            "platform": p["name"], "product": product,
            "trim_width_in": m["trim_width_in"], "trim_height_in": m["trim_height_in"],
            "bleed_in": spec.get("bleed_in", 0.125),
            "cover_width_in": g["largura_total_in"], "cover_height_in": g["altura_total_in"],
            "spine_width_in": g["largura_lombada_in"], "target_ppi": g["dpi"],
            "cover_px": [g["largura_total_px"], g["altura_total_px"]],
            "calculation": "faithbloom_kdp_formula",
            "warning": "Conferir o resultado com a calculadora/template oficial do KDP antes do upload final.",
        }

    if platform_id == "lulu" and product == "paperback":
        bleed = float(spec.get("bleed_in", 0.125))
        spine = round(m["page_count"] / 444.0 + 0.06, 4)
        total_w = 2 * m["trim_width_in"] + spine + 2 * bleed
        total_h = m["trim_height_in"] + 2 * bleed
        return {
            "platform": p["name"], "product": product,
            "trim_width_in": m["trim_width_in"], "trim_height_in": m["trim_height_in"],
            "bleed_in": bleed, "cover_width_in": round(total_w, 4), "cover_height_in": round(total_h, 4),
            "spine_width_in": spine, "target_ppi": int(spec.get("target_ppi", 300)),
            "cover_px": [round(total_w * 300), round(total_h * 300)],
            "calculation": "lulu_paperback_formula",
            "warning": "Confirmar com o template/calculadora oficial da Lulu para a combinação exata de papel e encadernação.",
        }

    # IngramSpark e outros: não inventamos a lombada. A saída é um envelope
    # técnico parcial e exige template oficial específico do título.
    bleed = float(spec.get("cover_bleed_in", spec.get("bleed_in", 0.125)))
    return {
        "platform": p["name"], "product": product,
        "trim_width_in": m["trim_width_in"], "trim_height_in": m["trim_height_in"],
        "bleed_in": bleed,
        "cover_width_in": None, "cover_height_in": None, "spine_width_in": None,
        "target_ppi": int(spec.get("target_ppi", 300)),
        "cover_px": None,
        "calculation": "official_template_required",
        "warning": "FaithBloom não inventou a largura da lombada. Importe/use o template oficial da plataforma para esta edição.",
    }


def _pdf_dimensions(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {"exists": False}
    try:
        r = PdfReader(path)
        dims = []
        for page in r.pages[: min(len(r.pages), 20)]:
            dims.append((round(float(page.mediabox.width) / PT_PER_IN, 4), round(float(page.mediabox.height) / PT_PER_IN, 4)))
        unique = sorted(set(dims))
        return {"exists": True, "pages": len(r.pages), "sample_dimensions_in": unique}
    except Exception as exc:
        return {"exists": True, "error": f"{type(exc).__name__}: {exc}"}


def preflight_target(master: dict | BookMasterSpec, platform_id: str, product: str, assets: dict | None = None) -> dict:
    m = normalizar_master(master)
    assets = dict(assets or {})
    comp = compatibility(m, platform_id, product)
    alerts = list(comp["alerts"])
    p = get_platform(platform_id)
    accepted = set((p.get("accepted_formats") or {}).get(product, []))

    if product in {"paperback", "hardcover", "coil_bound", "saddle_stitch", "print_distribution", "photo_book"}:
        path = assets.get("interior_pdf") or assets.get("pdf_miolo")
        pdf = _pdf_dimensions(path) if path else {"exists": False}
        if not path:
            alerts.append({"severity": "blocker", "code": "missing_interior_pdf", "message": "Miolo PDF ainda não foi associado a esta edição."})
        elif not pdf.get("exists") or pdf.get("error"):
            alerts.append({"severity": "blocker", "code": "invalid_interior_pdf", "message": "Não foi possível validar o PDF do miolo."})
        else:
            if pdf.get("pages") != m["page_count"]:
                alerts.append({"severity": "warning", "code": "page_count_mismatch", "message": f"Master informa {m['page_count']} páginas, mas o PDF possui {pdf.get('pages')}."})
        cover = assets.get("cover_pdf") or assets.get("capa_fisica_pdf")
        if not cover:
            alerts.append({"severity": "blocker", "code": "missing_cover_pdf", "message": "Capa física PDF ainda não foi associada a esta edição."})
        if m["target_ppi"] < int((p.get("print") or {}).get("target_ppi", 300)):
            alerts.append({"severity": "warning", "code": "ppi_target_low", "message": f"Target do Master ({m['target_ppi']} PPI) está abaixo do perfil de impressão desta plataforma."})
    elif product == "ebook":
        epub = assets.get("epub") or assets.get("ebook_epub")
        if "epub" in accepted and not epub:
            alerts.append({"severity": "blocker", "code": "missing_epub", "message": "EPUB ainda não foi gerado/associado para esta edição digital."})
        elif epub and not str(epub).lower().endswith(".epub"):
            alerts.append({"severity": "warning", "code": "ebook_format", "message": "O arquivo associado não é EPUB; confira os formatos aceitos pela plataforma."})
        if platform_id == "apple_books" and not assets.get("epubcheck_passed"):
            alerts.append({"severity": "blocker", "code": "epubcheck_required", "message": "Apple Books exige EPUB validado; marque somente após passar pelo EPUBCheck."})
        if platform_id == "kobo_writing_life" and epub and os.path.exists(epub):
            size_mb = os.path.getsize(epub) / (1024 * 1024)
            if size_mb > float((p.get("digital") or {}).get("max_book_file_mb", 100)):
                alerts.append({"severity": "blocker", "code": "ebook_size", "message": f"Arquivo tem {size_mb:.1f} MB e excede o limite carregado no perfil Kobo."})
    elif product == "digital_download":
        if not assets.get("digital_file"):
            alerts.append({"severity": "review", "code": "missing_digital_file", "message": "Selecione o PDF/ZIP/EPUB que será vendido como download."})

    # Metadados que ajudam qualquer canal.
    if not m.get("title"):
        alerts.append({"severity": "blocker", "code": "missing_title", "message": "Título do Book Master está vazio."})
    if m.get("isbn_mode") == "own" and not m.get("isbn"):
        alerts.append({"severity": "blocker", "code": "missing_isbn", "message": "ISBN próprio foi selecionado, mas o número não foi informado."})

    blockers = [a for a in alerts if a["severity"] == "blocker"]
    warnings = [a for a in alerts if a["severity"] in {"warning", "review"}]
    return {
        "platform_id": platform_id, "platform_name": p["name"], "product": product,
        "ready": not blockers, "blockers": blockers, "warnings": warnings, "alerts": alerts,
        "spec_version": p.get("spec_version"), "last_verified": p.get("last_verified"),
    }


def build_derivative_plan(master: dict | BookMasterSpec, targets: list[dict]) -> dict:
    m = normalizar_master(master)
    editions = []
    for target in targets:
        pid = target["platform_id"]
        product = target.get("product") or m["binding"]
        c = compatibility(m, pid, product)
        derivative = {
            "platform_id": pid,
            "platform_name": c["platform_name"],
            "product": product,
            "status": c["status"],
            "source_master_trim_in": [m["trim_width_in"], m["trim_height_in"]],
            "target_trim_in": [m["trim_width_in"], m["trim_height_in"]],
            "needs_layout_derivative": False,
            "output": "pdf" if product in {"paperback", "hardcover", "coil_bound", "saddle_stitch", "print_distribution", "photo_book"} else ("epub" if product == "ebook" else "digital_asset"),
            "alerts": c["alerts"],
        }
        if c.get("nearest_trim"):
            n = c["nearest_trim"]
            exact = abs(n["width_in"] - m["trim_width_in"]) < 0.005 and abs(n["height_in"] - m["trim_height_in"]) < 0.005
            if not exact:
                derivative["target_trim_in"] = [n["width_in"], n["height_in"]]
                derivative["needs_layout_derivative"] = True
        editions.append(derivative)
    return {
        "master": m,
        "policy": "never_resize_silently",
        "editions": editions,
        "summary": {
            "targets": len(editions),
            "blocked": sum(1 for e in editions if e["status"] == "blocked"),
            "needs_review": sum(1 for e in editions if e["status"] == "review"),
            "layout_derivatives": sum(1 for e in editions if e["needs_layout_derivative"]),
        },
    }

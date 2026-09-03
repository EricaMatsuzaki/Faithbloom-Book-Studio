"""FaithBloom Refinamento 07 — Platform Registry versionado e expansível.

A matriz não finge que requisitos de terceiros são eternos. Cada perfil possui
fonte, data de verificação e nível de confiança. Plataformas personalizadas são
persistidas fora do código em ``.faithbloom_data/platform_registry_custom.json``.

O Registry descreve requisitos e capacidades. Regras matemáticas específicas
ficam em ``platform_format_engine.py`` para não misturar catálogo com cálculo.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(".faithbloom_data")
CUSTOM_PATH = DATA_DIR / "platform_registry_custom.json"
OVERRIDE_PATH = DATA_DIR / "platform_registry_overrides.json"
HISTORY_PATH = DATA_DIR / "platform_registry_history.json"
REGISTRY_SCHEMA = 1
VERIFIED_AT = "2026-09-03"


def _profile(
    platform_id: str,
    name: str,
    category: str,
    products: list[str],
    *,
    regions: list[str] | None = None,
    formats: dict[str, list[str]] | None = None,
    print_spec: dict | None = None,
    digital_spec: dict | None = None,
    source_urls: list[str] | None = None,
    notes: list[str] | None = None,
    status: str = "verified",
    builtin: bool = True,
) -> dict:
    return {
        "id": platform_id,
        "name": name,
        "category": category,
        "products": products,
        "regions": regions or ["global"],
        "accepted_formats": formats or {},
        "print": print_spec or {},
        "digital": digital_spec or {},
        "source_urls": source_urls or [],
        "notes": notes or [],
        "status": status,
        "builtin": builtin,
        "spec_version": f"2026.09-{REGISTRY_SCHEMA}",
        "last_verified": VERIFIED_AT if status == "verified" else "",
        "created_at": "2026-09-03T00:00:00+09:00",
        "updated_at": "2026-09-03T00:00:00+09:00",
    }


# Perfis pré-configurados. Quando não temos regra numérica confiável, o perfil
# deliberadamente diz ``manual_or_template`` em vez de inventar dimensões.
BUILTIN_PLATFORMS: dict[str, dict] = {
    "amazon_kdp": _profile(
        "amazon_kdp", "Amazon KDP", "direct_publishing",
        ["paperback", "hardcover", "ebook"],
        regions=["global"],
        formats={
            "paperback": ["pdf"], "hardcover": ["pdf"], "ebook": ["epub", "kpf", "docx"]
        },
        print_spec={
            "target_ppi": 300,
            "bleed_in": 0.125,
            "cover_geometry": "kdp_formula_or_official_calculator",
            "trim_mode": "official_product_matrix",
            "common_trim_presets_in": [[5.0, 8.0], [5.5, 8.5], [6.0, 9.0], [7.0, 10.0], [8.0, 10.0], [8.5, 8.5], [8.5, 11.0]],
            "page_count_requires_even": True,
            "cover_template_recommended": True,
        },
        digital_spec={"preferred": "epub", "fixed_layout_supported": True},
        source_urls=[
            "https://kdp.amazon.com/cover-calculator",
            "https://kdp.amazon.com/en_US/help/topic/G201857950",
        ],
        notes=["Valide a combinação binding/interior/paper/trim/page count na calculadora oficial antes do upload final."],
    ),
    "ingramspark": _profile(
        "ingramspark", "IngramSpark", "distribution_and_pod",
        ["paperback", "hardcover", "ebook"],
        formats={"paperback": ["pdf"], "hardcover": ["pdf"], "ebook": ["epub"]},
        print_spec={
            "target_ppi": 300,
            "interior_bleed_outer_in": 0.125,
            "interior_bleed_bind_in": 0.0,
            "cover_bleed_in": 0.125,
            "safe_margin_in": 0.5,
            "barcode_clear_w_in": 1.75,
            "barcode_clear_h_in": 1.0,
            "cover_geometry": "official_template_required",
            "trim_mode": "official_product_matrix",
        },
        digital_spec={"preferred": "epub"},
        source_urls=[
            "https://www.ingramspark.com/blog/file-requirements-for-print-books",
            "https://www.ingramspark.com/blog/understanding-ingramspark-title-processing",
        ],
        notes=["Para capa, preferir template oficial específico do título; não reutilizar wrap KDP."],
    ),
    "lulu": _profile(
        "lulu", "Lulu", "pod_and_direct_sales",
        ["paperback", "hardcover", "coil_bound", "saddle_stitch", "ebook"],
        formats={"paperback": ["pdf"], "hardcover": ["pdf"], "coil_bound": ["pdf"], "saddle_stitch": ["pdf"], "ebook": ["epub"]},
        print_spec={
            "target_ppi": 300,
            "bleed_in": 0.125,
            "safe_margin_global_distribution_in": 0.5,
            "paperback_spine_formula": "page_count/444 + 0.06",
            "trim_mode": "official_product_matrix",
            "cover_template_recommended": True,
            "common_trim_presets_in": [[5.0, 8.0], [5.5, 8.5], [5.83, 8.27], [6.0, 9.0], [8.5, 11.0]],
        },
        digital_spec={"preferred": "epub"},
        source_urls=[
            "https://www.lulu.com/create",
            "https://help.lulu.com/en/support/solutions/articles/64000255584-what-is-full-bleed-",
            "https://assets.lulu.com/media/guides/en/lulu-book-creation-guide.pdf",
        ],
    ),
    "kobo_writing_life": _profile(
        "kobo_writing_life", "Rakuten Kobo Writing Life", "ebook_store",
        ["ebook", "audiobook"],
        formats={"ebook": ["epub", "doc", "docx", "odt", "mobi"], "audiobook": ["audio_upload"]},
        digital_spec={
            "preferred": "epub",
            "fixed_layout_supported": True,
            "max_book_file_mb": 100,
            "image_target_ppi": 300,
        },
        source_urls=[
            "https://kobowritinglife.zendesk.com/hc/en-us/articles/360059386271-File-Types-Sizes",
            "https://kobowritinglife.zendesk.com/hc/en-us/articles/360058975812-What-is-an-ePub",
        ],
    ),
    "apple_books": _profile(
        "apple_books", "Apple Books", "ebook_store",
        ["ebook", "audiobook"],
        formats={"ebook": ["epub"], "audiobook": ["audio_delivery"]},
        digital_spec={
            "preferred": "epub",
            "epubcheck_required": True,
            "children_interest_age_required": True,
            "fixed_layout_supported": True,
        },
        source_urls=[
            "https://authors.apple.com/support/4574-publish-book-from-web",
            "https://authors.apple.com/prepare",
        ],
        notes=["Uploads diretos de eBook exigem EPUB validado; PDF requer parceiro/conversão em vez de upload direto padrão."],
    ),
    "google_play_books": _profile(
        "google_play_books", "Google Play Books", "ebook_store",
        ["ebook", "audiobook"],
        formats={"ebook": ["epub", "pdf"], "audiobook": ["audio_upload"]},
        digital_spec={"preferred": "epub", "fixed_layout_supported": True, "pdf_supported": True},
        source_urls=[
            "https://support.google.com/books/partner/answer/166501",
            "https://support.google.com/books/partner/answer/3424254",
        ],
    ),
    "draft2digital": _profile(
        "draft2digital", "Draft2Digital", "aggregator",
        ["ebook", "print_distribution"],
        formats={"ebook": ["epub", "doc", "docx", "odt", "rtf", "txt"], "print_distribution": ["doc", "docx", "odt", "rtf", "txt"]},
        digital_spec={"preferred": "epub", "epub_passthrough": True, "epub_size_note": "EPUB muito grande pode não ser aceito; validar no serviço."},
        source_urls=["https://draft2digital.com/faq/", "https://draft2digital.com/knowledge-base/"],
        notes=["Evitar duplicar a mesma loja quando um título já é distribuído diretamente por outro canal."],
    ),
    "barnes_noble_press": _profile(
        "barnes_noble_press", "Barnes & Noble Press", "direct_publishing",
        ["paperback", "hardcover", "ebook"],
        regions=["US"],
        formats={"paperback": ["pdf", "docx"], "hardcover": ["pdf", "docx"], "ebook": ["epub", "docx"]},
        print_spec={
            "trim_mode": "official_product_matrix",
            "cover_geometry": "official_template_required",
            "common_trim_presets_in": [[5.0, 8.0], [5.5, 8.5], [6.0, 9.0], [7.0, 10.0], [8.0, 10.0], [8.5, 11.0]],
        },
        digital_spec={"preferred": "epub"},
        source_urls=[
            "https://press.barnesandnoble.com/book-cover-template-generator",
            "https://press.barnesandnoble.com/bnpress-blog/may-2026-policy-updates/",
        ],
        notes=["Regras comerciais e preços mínimos mudam; verificar política vigente antes do lançamento."],
    ),
    # Perfis abaixo são canais importantes, mas as regras de arquivo variam ou
    # não são um motor de impressão editorial. Mantemos como 'profile_only'.
    "streetlib": _profile(
        "streetlib", "StreetLib", "aggregator", ["ebook", "print_distribution", "audiobook"],
        formats={"ebook": ["epub"]}, status="profile_only",
        source_urls=["https://www.streetlib.com/"], notes=["Perfil de canal: importar/revalidar especificações antes do preflight automático."],
    ),
    "publishdrive": _profile(
        "publishdrive", "PublishDrive", "aggregator", ["ebook", "print_distribution", "audiobook"],
        formats={"ebook": ["epub"]}, status="profile_only",
        source_urls=["https://publishdrive.com/"], notes=["Perfil de canal: importar/revalidar especificações antes do preflight automático."],
    ),
    "bookbaby": _profile(
        "bookbaby", "BookBaby", "publishing_services", ["ebook", "print_distribution"],
        formats={}, status="profile_only", source_urls=["https://www.bookbaby.com/"],
    ),
    "blurb": _profile(
        "blurb", "Blurb", "pod_and_direct_sales", ["paperback", "hardcover", "photo_book", "ebook"],
        formats={}, status="profile_only", source_urls=["https://www.blurb.com/"],
    ),
    "etsy": _profile(
        "etsy", "Etsy", "digital_marketplace", ["digital_download"],
        formats={"digital_download": ["pdf", "png", "jpg", "zip"]}, status="profile_only",
        source_urls=["https://www.etsy.com/seller-handbook"], notes=["Canal útil para printable packs, atividades e páginas de colorir; não é POD editorial por si só."],
    ),
    "hotmart": _profile(
        "hotmart", "Hotmart", "digital_product_platform", ["digital_download", "course_bundle"],
        formats={"digital_download": ["pdf", "zip"]}, status="profile_only", source_urls=["https://hotmart.com/"],
    ),
    "kiwify": _profile(
        "kiwify", "Kiwify", "digital_product_platform", ["digital_download", "course_bundle"],
        formats={"digital_download": ["pdf", "zip"]}, status="profile_only", source_urls=["https://kiwify.com/"],
    ),
    "gumroad": _profile(
        "gumroad", "Gumroad", "digital_product_platform", ["digital_download"],
        formats={"digital_download": ["pdf", "epub", "zip"]}, status="profile_only", source_urls=["https://gumroad.com/"],
    ),
    "payhip": _profile(
        "payhip", "Payhip", "digital_product_platform", ["digital_download"],
        formats={"digital_download": ["pdf", "epub", "zip"]}, status="profile_only", source_urls=["https://payhip.com/"],
    ),
}


def _slugify(value: str) -> str:
    s = (value or "platform").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "platform"


def _load_custom() -> dict[str, dict]:
    if not CUSTOM_PATH.exists():
        return {}
    try:
        payload = json.loads(CUSTOM_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("platforms"), dict):
            return payload["platforms"]
    except Exception:
        pass
    return {}


def _save_custom(custom: dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"schema": REGISTRY_SCHEMA, "updated_at": datetime.now().isoformat(), "platforms": custom}
    CUSTOM_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json_map(path: Path, key: str) -> dict:
    if not path.exists():
        return {}
    try:
        payload=json.loads(path.read_text(encoding="utf-8"))
        value=payload.get(key,{}) if isinstance(payload,dict) else {}
        return value if isinstance(value,dict) else {}
    except Exception:
        return {}


def _deep_merge(base: dict, patch: dict) -> dict:
    out=copy.deepcopy(base)
    for k,v in (patch or {}).items():
        if isinstance(v,dict) and isinstance(out.get(k),dict):
            out[k]=_deep_merge(out[k],v)
        else:
            out[k]=copy.deepcopy(v)
    return out


def get_registry(include_custom: bool = True) -> dict[str, dict]:
    out = copy.deepcopy(BUILTIN_PLATFORMS)
    # Overrides versionados permitem atualizar especificações oficiais sem
    # editar o código-fonte. O perfil original continua recuperável.
    for pid, patch in _load_json_map(OVERRIDE_PATH, "overrides").items():
        if pid in out:
            out[pid]=_deep_merge(out[pid],patch)
            out[pid]["builtin"]=True
            out[pid]["overridden"]=True
    if include_custom:
        for pid, item in _load_custom().items():
            item = copy.deepcopy(item)
            item["builtin"] = False
            out[pid] = item
    return out


def list_platforms(include_custom: bool = True, category: str | None = None) -> list[dict]:
    values = list(get_registry(include_custom).values())
    if category:
        values = [x for x in values if x.get("category") == category]
    return sorted(values, key=lambda x: x.get("name", "").lower())


def get_platform(platform_id: str) -> dict:
    p = get_registry().get(platform_id)
    if not p:
        raise KeyError(f"Plataforma não cadastrada: {platform_id}")
    return p


def register_custom_platform(
    *,
    name: str,
    category: str = "custom",
    products: list[str] | None = None,
    accepted_formats: dict[str, list[str]] | None = None,
    source_urls: list[str] | None = None,
    notes: list[str] | None = None,
    specs: dict[str, Any] | None = None,
    platform_id: str | None = None,
    last_verified: str | None = None,
) -> dict:
    pid = platform_id or _slugify(name)
    if pid in BUILTIN_PLATFORMS:
        raise ValueError("Plataforma oficial é protegida. Crie uma cópia personalizada com outro ID.")
    custom = _load_custom()
    now = datetime.now().isoformat()
    existing = custom.get(pid, {})
    record = {
        "id": pid,
        "name": name.strip() or pid,
        "category": category,
        "products": products or ["custom"],
        "regions": list((specs or {}).get("regions") or ["global"]),
        "accepted_formats": accepted_formats or {},
        "print": dict((specs or {}).get("print") or {}),
        "digital": dict((specs or {}).get("digital") or {}),
        "source_urls": source_urls or [],
        "notes": notes or [],
        "status": "custom",
        "builtin": False,
        "spec_version": str((specs or {}).get("spec_version") or "custom-1"),
        "last_verified": last_verified or "",
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    custom[pid] = record
    _save_custom(custom)
    return copy.deepcopy(record)


def remove_custom_platform(platform_id: str) -> bool:
    if platform_id in BUILTIN_PLATFORMS:
        raise ValueError("Plataformas oficiais não podem ser removidas do Registry.")
    custom = _load_custom()
    existed = platform_id in custom
    custom.pop(platform_id, None)
    _save_custom(custom)
    return existed



def update_platform_spec(platform_id: str, patch: dict, *, spec_version: str, last_verified: str, source_urls: list[str] | None = None, note: str = "") -> dict:
    """Aplica override versionado a um perfil oficial ou personalizado.

    Para oficiais, o baseline do código não é alterado. Para personalizados,
    reutilizamos o registro customizado. Toda mudança ganha snapshot no histórico.
    """
    current=get_platform(platform_id)
    now=datetime.now().isoformat()
    history_payload={"schema":REGISTRY_SCHEMA,"history":[]}
    if HISTORY_PATH.exists():
        try:
            x=json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            if isinstance(x,dict) and isinstance(x.get("history"),list): history_payload=x
        except Exception:
            pass
    history_payload["history"].append({"platform_id":platform_id,"saved_at":now,"previous":current,"note":note})
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history_payload,ensure_ascii=False,indent=2),encoding="utf-8")

    patch=copy.deepcopy(patch or {})
    patch["spec_version"]=spec_version
    patch["last_verified"]=last_verified
    patch["updated_at"]=now
    if source_urls is not None: patch["source_urls"]=source_urls
    if platform_id in BUILTIN_PLATFORMS:
        payload={"schema":REGISTRY_SCHEMA,"updated_at":now,"overrides":_load_json_map(OVERRIDE_PATH,"overrides")}
        payload["overrides"][platform_id]=_deep_merge(payload["overrides"].get(platform_id,{}),patch)
        OVERRIDE_PATH.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        return get_platform(platform_id)
    custom=_load_custom()
    if platform_id not in custom: raise KeyError(f"Plataforma não cadastrada: {platform_id}")
    custom[platform_id]=_deep_merge(custom[platform_id],patch)
    _save_custom(custom)
    return get_platform(platform_id)


def platform_history(platform_id: str | None = None) -> list[dict]:
    if not HISTORY_PATH.exists(): return []
    try:
        payload=json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        items=payload.get("history",[]) if isinstance(payload,dict) else []
    except Exception:
        return []
    if platform_id: items=[x for x in items if x.get("platform_id")==platform_id]
    return items


def registry_snapshot() -> dict:
    reg = get_registry()
    return {
        "schema": REGISTRY_SCHEMA,
        "generated_at": datetime.now().isoformat(),
        "official_count": len(BUILTIN_PLATFORMS),
        "custom_count": len(reg) - len(BUILTIN_PLATFORMS),
        "platforms": reg,
    }


def verification_state(platform: dict, stale_after_days: int = 180) -> dict:
    raw = platform.get("last_verified") or ""
    if not raw:
        return {"state": "needs_verification", "days": None, "message": "Sem data de verificação registrada."}
    try:
        d = date.fromisoformat(raw[:10])
        days = (date.today() - d).days
    except Exception:
        return {"state": "needs_verification", "days": None, "message": "Data de verificação inválida."}
    if days > stale_after_days:
        return {"state": "stale", "days": days, "message": f"Especificação verificada há {days} dias; revalidar antes de publicar."}
    return {"state": "current", "days": days, "message": f"Verificada há {days} dias."}

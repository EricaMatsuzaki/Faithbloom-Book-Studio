"""FaithBloom Refinamento 16 — Asset Library & Media Manager.

Camada de catálogo visual sobre a Galeria existente. Mantém compatibilidade com
``armazenamento.salvar_na_galeria/listar_galeria`` e acrescenta:
- metadados/facetas e busca rica;
- Masters e versões;
- coleções virtuais sem duplicar arquivos;
- arquivamento em vez de exclusão destrutiva;
- rastreio de uso em projetos;
- thumbnails persistentes;
- triagem de duplicatas;
- inventário de storage.

Nenhuma operação desta camada altera automaticamente um Book Master.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from armazenamento import _ler_indice_galeria, _salvar_indice_galeria
from storage_backend import BACKEND, is_storage_uri, materializar, storage_uri, uri_to_path

ASSET_SCHEMA_VERSION = 2
ASSET_USAGES = {"story", "coloring", "activity", "cover", "marketing", "printable"}
ASSET_SCOPES = {"reusable", "collection", "book_specific"}
ASSET_ROLES = {
    "character_reference", "approved_variation", "scene", "cover_art",
    "line_art", "activity_asset", "background",
}
COLLECTIONS_INDEX = "asset_library/collections.json"
USAGE_INDEX = "asset_library/usage.json"
THUMB_PREFIX = "asset_library/thumbnails"

MASTER_ROLES = {
    "character_master": "⭐ Character Master",
    "color_master": "🎨 Color Master",
    "line_art_master": "🖍️ Line Art Master",
    "cover_master": "📕 Cover Master",
    "style_reference": "🧬 Style Reference",
}

MEDIA_LABELS = {
    "image": "🖼️ Imagem",
    "audio": "🎧 Áudio",
    "pdf": "📄 PDF",
    "svg": "✒️ SVG",
    "other": "📦 Outro",
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def _now() -> int:
    return int(time.time())


def _unique(values: Iterable[str]) -> list[str]:
    return sorted({str(v).strip() for v in values if str(v).strip()}, key=str.lower)


def _storage_path(item: dict) -> str:
    uri = item.get("storage_uri") or ""
    return uri_to_path(uri) if is_storage_uri(uri) else ""


def _extension(item: dict) -> str:
    path = _storage_path(item) or str(item.get("caminho_arquivo") or "")
    return Path(path).suffix.lower()


def infer_media_kind(item: dict) -> str:
    meta = item.get("metadata") or {}
    explicit = item.get("media_kind") or meta.get("media_kind")
    if explicit:
        return str(explicit)
    ext = _extension(item)
    if ext in IMAGE_EXTS:
        return "image"
    if ext == ".svg":
        return "svg"
    if ext == ".pdf":
        return "pdf"
    if ext in AUDIO_EXTS:
        return "audio"
    return "other"


def normalize_asset(item: dict) -> dict:
    """Normaliza registros antigos sem apagar campos desconhecidos."""
    out = dict(item or {})
    out.setdefault("id", uuid.uuid4().hex)
    out.setdefault("nome", "Asset sem nome")
    out["tags"] = _unique(out.get("tags") or [])
    out.setdefault("tipo", "referencia")
    out.setdefault("favorita", False)
    out.setdefault("criada_em", _now())
    out.setdefault("atualizada_em", out.get("criada_em") or _now())
    out.setdefault("status", "active")  # active | archived
    out.setdefault("asset_schema_version", ASSET_SCHEMA_VERSION)
    out.setdefault("master_roles", [])
    out["master_roles"] = [x for x in _unique(out.get("master_roles") or []) if x in MASTER_ROLES]
    out.setdefault("virtual_collections", [])
    out["virtual_collections"] = _unique(out.get("virtual_collections") or [])
    out.setdefault("version_group", out.get("id"))
    out.setdefault("version_label", "Original")
    out.setdefault("parent_asset_id", "")
    out.setdefault("approved", bool((out.get("metadata") or {}).get("aprovada", False)))
    out.setdefault("locked_original", bool((out.get("metadata") or {}).get("original_publicado", False)))
    out["media_kind"] = infer_media_kind(out)
    meta = dict(out.get("metadata") or {})
    meta.setdefault("origem", meta.get("source", ""))
    # Defaults are additive: old assets stay valid and unknown metadata survives.
    usages = meta.get("usos", meta.get("usage", []))
    if isinstance(usages, str):
        usages = [usages]
    usages = _unique(usages or [])
    meta["usos"] = usages
    meta["usage"] = usages[0] if usages else str(meta.get("usage") or "")
    meta.setdefault("scope", "reusable")
    meta.setdefault("asset_role", "")
    meta.setdefault("contains_text", False)
    out["metadata"] = meta
    return out


def _all_assets(write_back: bool = False) -> list[dict]:
    raw = _ler_indice_galeria()
    normalized = [normalize_asset(x) for x in raw]
    if write_back and normalized != raw:
        _salvar_indice_galeria(normalized)
    return normalized


def migrate_gallery_index() -> dict:
    raw = _ler_indice_galeria()
    normalized = [normalize_asset(x) for x in raw]
    changed = sum(1 for a, b in zip(raw, normalized) if a != b)
    if normalized != raw:
        _salvar_indice_galeria(normalized)
    return {"assets": len(normalized), "migrated": changed, "schema": ASSET_SCHEMA_VERSION}


def get_asset(asset_id: str, materialize_file: bool = True) -> dict | None:
    item = next((x for x in _all_assets() if x.get("id") == asset_id), None)
    if not item:
        return None
    if materialize_file:
        uri = item.get("storage_uri") or item.get("caminho_arquivo") or ""
        if uri:
            try:
                item["caminho_arquivo"] = materializar(uri)
            except Exception:
                item["caminho_arquivo"] = uri
    return item


def get_asset_by_uri(uri: str, materialize_file: bool = False) -> dict | None:
    """Resolve referências legadas que guardavam somente a URI/caminho."""
    if not uri:
        return None
    item = next((x for x in _all_assets() if uri in {x.get("storage_uri"), x.get("caminho_arquivo")}), None)
    # Character Universe materializa fb:// ao carregar. Reconhece o nome
    # determinístico do cache sem persistir nem baixar novamente o arquivo.
    if not item and not is_storage_uri(uri):
        incoming_name = Path(uri).name
        for candidate in _all_assets():
            candidate_uri = candidate.get("storage_uri") or ""
            if not is_storage_uri(candidate_uri):
                continue
            storage_path = uri_to_path(candidate_uri)
            expected = hashlib.sha256(storage_path.encode("utf-8")).hexdigest()[:24] + (Path(storage_path).suffix or ".bin")
            if incoming_name == expected:
                item = candidate
                break
    if not item:
        return None
    return get_asset(item["id"], materialize_file=materialize_file)


def _search_blob(item: dict) -> str:
    meta = item.get("metadata") or {}
    values = [
        item.get("nome", ""), item.get("tipo", ""), item.get("media_kind", ""),
        *item.get("tags", []), *item.get("master_roles", []),
        meta.get("personagem", ""), meta.get("colecao", ""), meta.get("livro", ""),
        meta.get("emocao", ""), meta.get("estacao", ""), meta.get("roupa", ""),
        meta.get("festividade", ""), meta.get("origem", ""), meta.get("prompt", ""),
        meta.get("cena", ""), meta.get("cena_numero", ""), meta.get("idioma", ""),
    ]
    return " ".join(str(x) for x in values if x is not None).lower()


def _matches(item: dict, filters: dict) -> bool:
    meta = item.get("metadata") or {}
    q = str(filters.get("q") or "").strip().lower()
    if q:
        tokens = [t for t in q.split() if t]
        blob = _search_blob(item)
        if not all(t in blob for t in tokens):
            return False
    if filters.get("tipo") and item.get("tipo") != filters["tipo"]:
        return False
    if filters.get("media_kind") and item.get("media_kind") != filters["media_kind"]:
        return False
    if filters.get("favorite") is True and not item.get("favorita"):
        return False
    if filters.get("status") and item.get("status") != filters["status"]:
        return False
    if filters.get("approved") is True and not item.get("approved"):
        return False
    if filters.get("master_role") and filters["master_role"] not in item.get("master_roles", []):
        return False
    if filters.get("virtual_collection") and filters["virtual_collection"] not in item.get("virtual_collections", []):
        return False
    for f in ("personagem", "colecao", "livro", "emocao", "estacao", "roupa", "festividade", "idioma", "origem"):
        wanted = filters.get(f)
        if wanted and str(meta.get(f, "")).lower() != str(wanted).lower():
            return False
    return True


def list_assets(filters: dict | None = None, page: int = 1, page_size: int = 24, sort: str = "newest") -> dict:
    filters = dict(filters or {})
    filters.setdefault("status", "active")
    items = [x for x in _all_assets() if _matches(x, filters)]
    if sort == "oldest":
        items.sort(key=lambda x: (x.get("criada_em", 0), x.get("nome", "").lower()))
    elif sort == "name":
        items.sort(key=lambda x: x.get("nome", "").lower())
    elif sort == "favorites":
        items.sort(key=lambda x: (not bool(x.get("favorita")), -int(x.get("criada_em", 0))))
    else:
        items.sort(key=lambda x: x.get("criada_em", 0), reverse=True)
    total = len(items)
    page_size = max(1, min(int(page_size or 24), 100))
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(page or 1), pages))
    start = (page - 1) * page_size
    subset = items[start:start + page_size]
    return {"items": subset, "total": total, "page": page, "pages": pages, "page_size": page_size}


def facet_values(field: str, include_archived: bool = False) -> list[str]:
    vals: list[str] = []
    for item in _all_assets():
        if not include_archived and item.get("status") == "archived":
            continue
        if field in {"tipo", "media_kind"}:
            v = item.get(field)
        else:
            v = (item.get("metadata") or {}).get(field)
        if isinstance(v, list):
            vals.extend(str(x) for x in v)
        elif v not in (None, ""):
            vals.append(str(v))
    return _unique(vals)


def update_asset(asset_id: str, **changes) -> dict | None:
    items = _all_assets()
    found = None
    for i, item in enumerate(items):
        if item.get("id") != asset_id:
            continue
        updated = dict(item)
        if "metadata" in changes:
            merged = dict(updated.get("metadata") or {})
            merged.update(changes.pop("metadata") or {})
            changes["metadata"] = merged
        if "tags" in changes:
            changes["tags"] = _unique(changes["tags"] or [])
        if "master_roles" in changes:
            changes["master_roles"] = [x for x in _unique(changes["master_roles"] or []) if x in MASTER_ROLES]
        if "virtual_collections" in changes:
            changes["virtual_collections"] = _unique(changes["virtual_collections"] or [])
        updated.update(changes)
        updated["atualizada_em"] = _now()
        updated = normalize_asset(updated)
        items[i] = updated
        found = updated
        break
    if found:
        _salvar_indice_galeria(items)
    return found


def set_favorite(asset_id: str, value: bool = True) -> dict | None:
    return update_asset(asset_id, favorita=bool(value))


def set_archived(asset_id: str, archived: bool = True) -> dict | None:
    """Arquiva/restaura com uma única gravação, preservando identidade e versões."""
    asset = get_asset(asset_id, materialize_file=False)
    if not asset:
        return None
    if archived:
        previous = asset.get("visual_status") or (asset.get("metadata") or {}).get("visual_status") or "REFERENCE"
        return update_asset(
            asset_id, status="archived", visual_status="ARCHIVED",
            metadata={"visual_status": "ARCHIVED", "visual_status_before_archive": previous},
        )
    previous = (asset.get("metadata") or {}).get("visual_status_before_archive")
    if not previous:
        previous = "APPROVED_VARIATION" if asset.get("approved") else "REFERENCE"
    return update_asset(
        asset_id, status="active", visual_status=previous,
        metadata={"visual_status": previous},
    )


def set_approved(asset_id: str, approved: bool = True) -> dict | None:
    return update_asset(asset_id, approved=bool(approved))


def set_master_role(asset_id: str, role: str, enabled: bool = True) -> dict | None:
    if role not in MASTER_ROLES:
        raise ValueError(f"Master role inválido: {role}")
    item = get_asset(asset_id, materialize_file=False)
    if not item:
        return None
    roles = set(item.get("master_roles", []))
    if enabled:
        roles.add(role)
    else:
        roles.discard(role)
    return update_asset(asset_id, master_roles=sorted(roles))


def create_version(asset_id: str, *, storage_uri_value: str, name: str | None = None, version_label: str | None = None, metadata: dict | None = None) -> dict:
    base = get_asset(asset_id, materialize_file=False)
    if not base:
        raise KeyError(asset_id)
    if not storage_uri_value:
        raise ValueError("storage_uri_value é obrigatório")
    version = normalize_asset({
        **base,
        "id": uuid.uuid4().hex,
        "nome": name or base.get("nome", "Asset"),
        "storage_uri": storage_uri_value,
        "favorita": False,
        "approved": False,
        "status": "active",
        "master_roles": [],
        "parent_asset_id": base["id"],
        "version_group": base.get("version_group") or base["id"],
        "version_label": version_label or f"Versão {int(time.time())}",
        "criada_em": _now(),
        "atualizada_em": _now(),
        "metadata": {**(base.get("metadata") or {}), **(metadata or {})},
    })
    items = _all_assets(); items.append(version); _salvar_indice_galeria(items)
    return version


def versions_for(asset_id: str) -> list[dict]:
    item = get_asset(asset_id, materialize_file=False)
    if not item:
        return []
    group = item.get("version_group") or item["id"]
    return sorted([x for x in _all_assets() if (x.get("version_group") or x.get("id")) == group], key=lambda x: x.get("criada_em", 0))


def _read_json(path: str, default):
    return BACKEND.get_json(path, default)


def _write_json(path: str, value) -> None:
    BACKEND.put_json(path, value)


def list_virtual_collections() -> list[dict]:
    data = _read_json(COLLECTIONS_INDEX, [])
    return data if isinstance(data, list) else []


def create_virtual_collection(name: str, description: str = "") -> dict:
    name = str(name or "").strip()
    if not name:
        raise ValueError("Nome da coleção é obrigatório")
    items = list_virtual_collections()
    existing = next((x for x in items if x.get("name", "").lower() == name.lower()), None)
    if existing:
        return existing
    obj = {"id": uuid.uuid4().hex, "name": name, "description": str(description or "").strip(), "created_at": _now()}
    items.append(obj); _write_json(COLLECTIONS_INDEX, items)
    return obj


def rename_virtual_collection(collection_id: str, name: str) -> dict | None:
    items = list_virtual_collections(); found = None
    for x in items:
        if x.get("id") == collection_id:
            x["name"] = str(name).strip() or x.get("name")
            found = x; break
    if found: _write_json(COLLECTIONS_INDEX, items)
    return found


def add_to_collection(asset_ids: Iterable[str], collection_id: str) -> int:
    valid = {x.get("id") for x in list_virtual_collections()}
    if collection_id not in valid:
        raise KeyError(collection_id)
    count = 0
    for asset_id in set(asset_ids):
        item = get_asset(asset_id, materialize_file=False)
        if not item: continue
        cols = set(item.get("virtual_collections", [])); before = len(cols); cols.add(collection_id)
        if len(cols) != before:
            update_asset(asset_id, virtual_collections=sorted(cols)); count += 1
    return count


def remove_from_collection(asset_ids: Iterable[str], collection_id: str) -> int:
    count = 0
    for asset_id in set(asset_ids):
        item = get_asset(asset_id, materialize_file=False)
        if not item: continue
        cols = set(item.get("virtual_collections", []))
        if collection_id in cols:
            cols.remove(collection_id); update_asset(asset_id, virtual_collections=sorted(cols)); count += 1
    return count


def register_usage(asset_id: str, *, project_title: str, project_type: str, location: str = "", project_storage_path: str = "", status: str = "linked") -> dict:
    records = _read_json(USAGE_INDEX, [])
    if not isinstance(records, list): records = []
    obj = {
        "id": uuid.uuid4().hex,
        "asset_id": asset_id,
        "project_title": project_title,
        "project_type": project_type,
        "location": location,
        "project_storage_path": project_storage_path,
        "status": status,
        "registered_at": _now(),
    }
    records.append(obj); _write_json(USAGE_INDEX, records)
    return obj


def _find_refs(value: Any, targets: set[str], prefix: str = "$", out: list[str] | None = None) -> list[str]:
    out = out if out is not None else []
    if isinstance(value, dict):
        for k, v in value.items():
            _find_refs(v, targets, f"{prefix}.{k}", out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _find_refs(v, targets, f"{prefix}[{i}]", out)
    elif isinstance(value, str) and value in targets:
        out.append(prefix)
    return out


def scan_usage(asset_id: str, max_json_files: int = 1500) -> dict:
    """Procura referências por asset_id/storage_uri nos JSONs persistidos.

    É executado sob demanda para não tornar a galeria lenta. Não declara ausência
    absoluta se o limite de arquivos for atingido.
    """
    asset = get_asset(asset_id, materialize_file=False)
    if not asset:
        return {"records": [], "scanned": 0, "truncated": False}
    targets = {asset_id}
    if asset.get("storage_uri"): targets.add(asset["storage_uri"])
    manual = [x for x in (_read_json(USAGE_INDEX, []) or []) if x.get("asset_id") == asset_id and x.get("status") != "removed"]
    records = [{**x, "source": "registered"} for x in manual]
    paths = [p for p in BACKEND.list("") if p.endswith(".json") and p not in {"galeria/index.json", USAGE_INDEX, COLLECTIONS_INDEX}]
    truncated = len(paths) > max_json_files
    paths = paths[:max_json_files]
    for path in paths:
        data = BACKEND.get_json(path, None)
        if data is None: continue
        refs = _find_refs(data, targets)
        if not refs: continue
        title = ""
        ptype = path.split("/", 1)[0]
        if isinstance(data, dict):
            title = str(data.get("titulo") or data.get("title") or data.get("nome") or "")
        records.append({
            "id": f"scan:{path}", "asset_id": asset_id, "project_title": title or Path(path).name,
            "project_type": ptype, "location": ", ".join(refs[:8]), "project_storage_path": path,
            "status": "linked", "source": "scan",
        })
    # dedupe manual/scan representations
    seen = set(); unique = []
    for r in records:
        key = (r.get("project_storage_path"), r.get("location"), r.get("project_title"))
        if key in seen: continue
        seen.add(key); unique.append(r)
    return {"records": unique, "scanned": len(paths), "truncated": truncated}


def _asset_digest(item: dict, deep: bool = False) -> str:
    if item.get("sha256"):
        return str(item["sha256"])
    path = _storage_path(item)
    name = Path(path).stem
    # persistir_arquivo já usa 20 chars de SHA-256 no nome; útil como fingerprint leve.
    if len(name) == 20 and all(c in "0123456789abcdef" for c in name.lower()):
        return name.lower()
    if deep and path:
        try: return hashlib.sha256(BACKEND.get_bytes(path)).hexdigest()
        except Exception: pass
    return ""


def duplicate_groups(deep: bool = False) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in _all_assets():
        if item.get("status") == "archived": continue
        digest = _asset_digest(item, deep=deep)
        if digest:
            groups[digest].append(item)
    out = []
    for digest, items in groups.items():
        if len(items) > 1:
            out.append({"fingerprint": digest, "count": len(items), "items": items})
    return sorted(out, key=lambda x: x["count"], reverse=True)


def _technical_metadata(item: dict, compute_hash: bool = False) -> dict:
    meta = dict(item.get("metadata") or {})
    uri = item.get("storage_uri") or ""
    path = _storage_path(item)
    if not path:
        local = item.get("caminho_arquivo") or ""
        p = Path(local)
        if p.exists() and p.is_file():
            data = p.read_bytes()
        else:
            return meta
    else:
        try: data = BACKEND.get_bytes(path)
        except Exception: return meta
    meta["file_size_bytes"] = len(data)
    meta["mime_type"] = mimetypes.guess_type(path or str(item.get("caminho_arquivo") or ""))[0] or "application/octet-stream"
    if compute_hash:
        meta["sha256"] = hashlib.sha256(data).hexdigest()
    if item.get("media_kind") == "image":
        try:
            from PIL import Image
            import io
            with Image.open(io.BytesIO(data)) as im:
                meta["width_px"], meta["height_px"] = im.size
                meta["image_mode"] = im.mode
        except Exception:
            pass
    return meta


def backfill_technical_metadata(asset_ids: Iterable[str] | None = None, limit: int = 100) -> dict:
    wanted = set(asset_ids or [])
    items = [x for x in _all_assets() if not wanted or x.get("id") in wanted]
    done = 0; errors = []
    for item in items[:max(1, int(limit))]:
        try:
            meta = _technical_metadata(item, compute_hash=True)
            update_asset(item["id"], metadata=meta, sha256=meta.get("sha256", item.get("sha256", "")))
            done += 1
        except Exception as exc:
            errors.append(f"{item.get('nome')}: {exc}")
    return {"processed": done, "errors": errors, "limited": len(items) > limit}


def get_thumbnail(asset_id: str, max_px: int = 480) -> str | None:
    item = get_asset(asset_id, materialize_file=False)
    if not item or item.get("media_kind") not in {"image", "svg"}:
        return None
    if item.get("media_kind") == "svg":
        try: return materializar(item.get("storage_uri") or item.get("caminho_arquivo") or "")
        except Exception: return None
    digest = _asset_digest(item) or hashlib.sha256(asset_id.encode()).hexdigest()[:20]
    thumb_path = f"{THUMB_PREFIX}/{digest}-{int(max_px)}.jpg"
    if not BACKEND.exists(thumb_path):
        source = _storage_path(item)
        try:
            data = BACKEND.get_bytes(source) if source else Path(item.get("caminho_arquivo") or "").read_bytes()
            from PIL import Image, ImageOps
            import io
            with Image.open(io.BytesIO(data)) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((max_px, max_px))
                buf = io.BytesIO(); im.save(buf, format="JPEG", quality=82, optimize=True)
                BACKEND.put_bytes(thumb_path, buf.getvalue(), "image/jpeg")
        except Exception:
            try: return materializar(item.get("storage_uri") or item.get("caminho_arquivo") or "")
            except Exception: return None
    try: return materializar(storage_uri(thumb_path))
    except Exception: return None


def library_stats() -> dict:
    items = _all_assets()
    active = [x for x in items if x.get("status") != "archived"]
    archived = [x for x in items if x.get("status") == "archived"]
    kinds = Counter(x.get("media_kind", "other") for x in active)
    known_bytes = sum(int((x.get("metadata") or {}).get("file_size_bytes") or 0) for x in items)
    unknown_sizes = sum(1 for x in items if not (x.get("metadata") or {}).get("file_size_bytes"))
    return {
        "total": len(items), "active": len(active), "archived": len(archived),
        "favorites": sum(1 for x in active if x.get("favorita")),
        "masters": sum(1 for x in active if x.get("master_roles")),
        "known_bytes": known_bytes, "unknown_sizes": unknown_sizes,
        "by_media_kind": dict(kinds), "virtual_collections": len(list_virtual_collections()),
    }


def permanent_delete_allowed(asset_id: str, usage: dict | None = None) -> tuple[bool, str]:
    item = get_asset(asset_id, materialize_file=False)
    if not item:
        return False, "Asset não encontrado."
    if item.get("locked_original"):
        return False, "Original publicado/bloqueado: arquive em vez de excluir."
    if item.get("master_roles"):
        return False, "Este asset é um Master. Remova o papel Master antes de considerar exclusão."
    uri = item.get("storage_uri") or ""
    if uri and any(x.get("id") != asset_id and x.get("storage_uri") == uri for x in _all_assets()):
        return False, "O mesmo arquivo físico está referenciado por outro registro do catálogo. Arquive/mescle os registros antes de excluir bytes."
    usage = usage or scan_usage(asset_id)
    if usage.get("records"):
        return False, f"Asset está vinculado a {len(usage['records'])} uso(s). Arquivar é recomendado."
    return True, "Sem vínculos encontrados na varredura atual."


def permanent_delete(asset_id: str, confirmed: bool = False) -> bool:
    if not confirmed:
        raise PermissionError("Confirmação explícita é obrigatória.")
    usage = scan_usage(asset_id)
    allowed, reason = permanent_delete_allowed(asset_id, usage)
    if not allowed:
        raise PermissionError(reason)
    items = _all_assets(); target = next((x for x in items if x.get("id") == asset_id), None)
    if not target: return False
    uri = target.get("storage_uri") or ""
    if is_storage_uri(uri):
        try: BACKEND.delete(uri_to_path(uri))
        except Exception: pass
    _salvar_indice_galeria([x for x in items if x.get("id") != asset_id])
    return True


def batch_update(asset_ids: Iterable[str], *, favorite: bool | None = None, archived: bool | None = None, add_tags: Iterable[str] | None = None) -> int:
    count = 0
    for asset_id in set(asset_ids):
        item = get_asset(asset_id, materialize_file=False)
        if not item: continue
        changes: dict[str, Any] = {}
        if favorite is not None: changes["favorita"] = bool(favorite)
        if archived is not None: changes["status"] = "archived" if archived else "active"
        if add_tags:
            changes["tags"] = _unique([*item.get("tags", []), *list(add_tags)])
        if changes:
            update_asset(asset_id, **changes); count += 1
    return count

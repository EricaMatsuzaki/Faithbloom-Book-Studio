"""FaithBloom Refinamento 17 — Author & Contributor Profiles.

Separa a identidade de quem usa o SaaS da autoria/crédito editorial de cada
projeto. Perfis são reutilizáveis e os créditos do livro guardam snapshots,
para que uma alteração futura no perfil não reescreva silenciosamente uma
edição já publicada.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
import uuid
from typing import Any

from storage_backend import BACKEND

PROFILE_SCHEMA = "faithbloom.author-profile.v1"
AUTHORSHIP_SCHEMA = "faithbloom.project-authorship.v1"
INDEX_PATH = "authors/index.json"
PROFILE_PREFIX = "authors/profiles"

CONTRIBUTOR_ROLES = {
    "author": "Autor(a)",
    "coauthor": "Coautor(a)",
    "illustrator": "Ilustrador(a)",
    "translator": "Tradutor(a)",
    "editor": "Editor(a)",
    "narrator": "Narrador(a)",
    "cover_designer": "Designer de capa",
    "activity_creator": "Criador(a) de atividades",
    "proofreader": "Revisor(a)",
    "other": "Outro crédito",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _index() -> list[dict]:
    rows = BACKEND.get_json(INDEX_PATH, []) or []
    return rows if isinstance(rows, list) else []


def _save_index(rows: list[dict]) -> None:
    BACKEND.put_json(INDEX_PATH, rows)


def _profile_path(profile_id: str) -> str:
    return f"{PROFILE_PREFIX}/{profile_id}.json"


def profile_display_name(profile: dict | None) -> str:
    p = profile or {}
    return _clean(p.get("pen_name") or p.get("display_name") or p.get("legal_name"))


def create_author_profile(
    display_name: str,
    *,
    legal_name: str = "",
    pen_name: str = "",
    bio: str = "",
    locales: list[str] | None = None,
    website: str = "",
    social_links: list[str] | None = None,
    photo_asset_id: str = "",
    notes: str = "",
) -> dict:
    display_name = _clean(display_name)
    if not display_name:
        raise ValueError("Informe o nome de publicação do perfil.")
    pid = uuid.uuid4().hex
    profile = {
        "schema": PROFILE_SCHEMA,
        "id": pid,
        "display_name": display_name,
        "legal_name": _clean(legal_name),
        "pen_name": _clean(pen_name),
        "bio": str(bio or "").strip(),
        "locales": sorted({_clean(x) for x in (locales or []) if _clean(x)}),
        "website": _clean(website),
        "social_links": [_clean(x) for x in (social_links or []) if _clean(x)],
        "photo_asset_id": _clean(photo_asset_id),
        "notes": str(notes or "").strip(),
        "active": True,
        "created_at": _now(),
        "updated_at": _now(),
        "version": 1,
    }
    BACKEND.put_json(_profile_path(pid), profile)
    rows = _index()
    rows.append({
        "id": pid,
        "display_name": profile_display_name(profile),
        "active": True,
        "updated_at": profile["updated_at"],
    })
    _save_index(rows)
    return profile


def get_author_profile(profile_id: str) -> dict | None:
    value = BACKEND.get_json(_profile_path(profile_id), None)
    return value if isinstance(value, dict) else None


def list_author_profiles(*, include_archived: bool = False) -> list[dict]:
    out = []
    for row in _index():
        p = get_author_profile(row.get("id", ""))
        if not p:
            continue
        if not include_archived and not p.get("active", True):
            continue
        out.append(p)
    return sorted(out, key=lambda p: profile_display_name(p).casefold())


def update_author_profile(profile_id: str, **changes) -> dict:
    p = get_author_profile(profile_id)
    if not p:
        raise KeyError("Perfil de autoria não encontrado.")
    allowed = {"display_name", "legal_name", "pen_name", "bio", "locales", "website", "social_links", "photo_asset_id", "notes", "active"}
    for key, value in changes.items():
        if key not in allowed:
            continue
        if key in {"display_name", "legal_name", "pen_name", "website", "photo_asset_id"}:
            value = _clean(value)
        elif key == "locales":
            value = sorted({_clean(x) for x in (value or []) if _clean(x)})
        elif key == "social_links":
            value = [_clean(x) for x in (value or []) if _clean(x)]
        p[key] = value
    if not profile_display_name(p):
        raise ValueError("O perfil precisa manter um nome de publicação.")
    p["updated_at"] = _now()
    p["version"] = int(p.get("version") or 1) + 1
    BACKEND.put_json(_profile_path(profile_id), p)
    rows = _index()
    for row in rows:
        if row.get("id") == profile_id:
            row.update({"display_name": profile_display_name(p), "active": bool(p.get("active", True)), "updated_at": p["updated_at"]})
    _save_index(rows)
    return p


def archive_author_profile(profile_id: str, archived: bool = True) -> dict:
    return update_author_profile(profile_id, active=not archived)


def make_credit(profile: dict, *, role: str = "author", order: int = 1, credit_as: str = "") -> dict:
    if role not in CONTRIBUTOR_ROLES:
        role = "other"
    name = _clean(credit_as) or profile_display_name(profile)
    if not name:
        raise ValueError("O crédito precisa de um nome de publicação.")
    return {
        "profile_id": profile.get("id", ""),
        "role": role,
        "order": int(order),
        "credit_as": name,
        "profile_version_snapshot": int(profile.get("version") or 1),
        "display_name_snapshot": profile_display_name(profile),
        "created_at": _now(),
    }


def _legacy_credit(name: str, order: int = 1) -> dict:
    name = _clean(name)
    return {
        "profile_id": "",
        "role": "author" if order == 1 else "coauthor",
        "order": order,
        "credit_as": name,
        "profile_version_snapshot": 0,
        "display_name_snapshot": name,
        "created_at": _now(),
        "legacy_snapshot": True,
    }


def ensure_project_authorship(state: dict) -> dict:
    """Normaliza autoria numa cópia e preserva o campo legado ``autora``."""
    s = deepcopy(state or {})
    auth = s.get("authorship") if isinstance(s.get("authorship"), dict) else {}
    authors = auth.get("authors") if isinstance(auth.get("authors"), list) else []
    contributors = auth.get("contributors") if isinstance(auth.get("contributors"), list) else []
    if not authors:
        legacy = _clean(s.get("autora") or s.get("author"))
        if legacy:
            authors = [_legacy_credit(legacy)]
    auth = {
        "schema": AUTHORSHIP_SCHEMA,
        "authors": sorted([dict(x) for x in authors if isinstance(x, dict) and _clean(x.get("credit_as") or x.get("display_name_snapshot"))], key=lambda x: int(x.get("order") or 999)),
        "contributors": sorted([dict(x) for x in contributors if isinstance(x, dict) and _clean(x.get("credit_as") or x.get("display_name_snapshot"))], key=lambda x: (str(x.get("role") or ""), int(x.get("order") or 999))),
        "cover_credit_override": _clean(auth.get("cover_credit_override")),
        "updated_at": auth.get("updated_at") or _now(),
    }
    s["authorship"] = auth
    display = author_display_from_authorship(auth)
    if display:
        s["autora"] = display  # compatibilidade com renderizadores legados
    return s


def author_display_from_authorship(authorship: dict | None) -> str:
    authors = list((authorship or {}).get("authors") or [])
    authors.sort(key=lambda x: int(x.get("order") or 999))
    names = [_clean(x.get("credit_as") or x.get("display_name_snapshot")) for x in authors]
    names = [x for x in names if x]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return ", ".join(names[:-1]) + f" & {names[-1]}"


def author_display_from_state(state: dict | None) -> str:
    s = ensure_project_authorship(state or {})
    return author_display_from_authorship(s.get("authorship")) or _clean((state or {}).get("autora"))


def set_project_authors(state: dict, profile_ids: list[str], *, credit_overrides: dict[str, str] | None = None) -> dict:
    s = ensure_project_authorship(state)
    overrides = credit_overrides or {}
    authors = []
    for idx, pid in enumerate(profile_ids, 1):
        p = get_author_profile(pid)
        if not p:
            raise KeyError(f"Perfil de autoria não encontrado: {pid}")
        authors.append(make_credit(p, role="author" if idx == 1 else "coauthor", order=idx, credit_as=overrides.get(pid, "")))
    s["authorship"]["authors"] = authors
    s["authorship"]["updated_at"] = _now()
    s["autora"] = author_display_from_authorship(s["authorship"])
    return s


def add_project_contributor(state: dict, profile_id: str, role: str, *, credit_as: str = "") -> dict:
    s = ensure_project_authorship(state)
    p = get_author_profile(profile_id)
    if not p:
        raise KeyError("Perfil de colaborador não encontrado.")
    existing = [x for x in s["authorship"]["contributors"] if not (x.get("profile_id") == profile_id and x.get("role") == role)]
    order = 1 + sum(1 for x in existing if x.get("role") == role)
    existing.append(make_credit(p, role=role, order=order, credit_as=credit_as))
    s["authorship"]["contributors"] = existing
    s["authorship"]["updated_at"] = _now()
    return s


def remove_project_credit(state: dict, *, profile_id: str, role: str) -> dict:
    s = ensure_project_authorship(state)
    key = "authors" if role in {"author", "coauthor"} else "contributors"
    s["authorship"][key] = [x for x in s["authorship"][key] if not (x.get("profile_id") == profile_id and x.get("role") == role)]
    if key == "authors":
        for idx, x in enumerate(sorted(s["authorship"][key], key=lambda x: int(x.get("order") or 999)), 1):
            x["order"] = idx
            x["role"] = "author" if idx == 1 else "coauthor"
        s["autora"] = author_display_from_authorship(s["authorship"])
    s["authorship"]["updated_at"] = _now()
    return s


def set_cover_credit_override(state: dict, value: str = "") -> dict:
    s = ensure_project_authorship(state)
    s["authorship"]["cover_credit_override"] = _clean(value)
    s["authorship"]["updated_at"] = _now()
    return s


def cover_credit_from_state(state: dict | None) -> str:
    s = ensure_project_authorship(state or {})
    return _clean(s["authorship"].get("cover_credit_override")) or author_display_from_authorship(s["authorship"])


def publishing_contributors(state: dict | None) -> list[dict]:
    s = ensure_project_authorship(state or {})
    rows = []
    for x in s["authorship"]["authors"] + s["authorship"]["contributors"]:
        rows.append({
            "profile_id": x.get("profile_id", ""),
            "name": _clean(x.get("credit_as") or x.get("display_name_snapshot")),
            "role": x.get("role") or "other",
            "role_label": CONTRIBUTOR_ROLES.get(x.get("role") or "other", "Outro crédito"),
            "order": int(x.get("order") or 1),
        })
    return [x for x in rows if x["name"]]


def project_credit_lines(state: dict | None) -> list[str]:
    rows = publishing_contributors(state)
    if not rows:
        return []
    authors = [x for x in rows if x["role"] in {"author", "coauthor"}]
    out = []
    if authors:
        out.append("Autoria: " + author_display_from_state(state or {}))
    grouped: dict[str, list[str]] = {}
    for x in rows:
        if x["role"] in {"author", "coauthor"}:
            continue
        grouped.setdefault(x["role_label"], []).append(x["name"])
    for label, names in grouped.items():
        out.append(f"{label}: " + ", ".join(names))
    return out


def authorship_summary(state: dict | None) -> dict:
    s = ensure_project_authorship(state or {})
    rows = publishing_contributors(s)
    return {
        "author_display": author_display_from_state(s),
        "cover_credit": cover_credit_from_state(s),
        "authors": [x for x in rows if x["role"] in {"author", "coauthor"}],
        "contributors": [x for x in rows if x["role"] not in {"author", "coauthor"}],
        "has_primary_author": any(x["role"] == "author" and x["name"] for x in rows),
    }

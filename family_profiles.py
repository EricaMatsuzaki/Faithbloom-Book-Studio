"""FaithBloom Refinamento 18 — Family/Workspace Profiles.

Perfis de workspace tornam o dashboard pessoal sem confundir três conceitos:
- autenticação real (OIDC/usuário da aplicação);
- perfil de workspace/família (preferências e organização de projetos);
- perfil editorial de autoria (quem assina um livro).

Um perfil de workspace NÃO é uma fronteira de segurança. Em produção, isolamento
real entre contas continua dependendo da autenticação/ACL do backend.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
import uuid
from typing import Any

from storage_backend import BACKEND

PROFILE_SCHEMA = "faithbloom.workspace-profile.v1"
PROJECT_LINK_SCHEMA = "faithbloom.workspace-project-link.v1"
INDEX_PATH = "workspace/profiles/index.json"
PROFILE_PREFIX = "workspace/profiles"
PROJECT_LINKS_PATH = "workspace/project-links.json"

DASHBOARD_MODES = {"simple", "advanced"}
AGE_PROFILES = {"3-4", "5-6", "7-8", "9-12", "teen", "adult", "60+", "3-8", "custom"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _profile_path(profile_id: str) -> str:
    return f"{PROFILE_PREFIX}/{profile_id}.json"


def _index() -> list[dict]:
    rows = BACKEND.get_json(INDEX_PATH, []) or []
    return rows if isinstance(rows, list) else []


def _save_index(rows: list[dict]) -> None:
    BACKEND.put_json(INDEX_PATH, rows)


def create_workspace_profile(
    display_name: str,
    *,
    relationship: str = "",
    linked_author_profile_id: str = "",
    default_locale: str = "pt-BR",
    default_age_profile: str = "3-8",
    default_visual_style: str = "",
    publication_markets: list[str] | None = None,
    dashboard_mode: str = "simple",
    avatar_asset_id: str = "",
    notes: str = "",
) -> dict:
    name = _clean(display_name)
    if not name:
        raise ValueError("Informe um nome para o perfil do workspace.")
    mode = dashboard_mode if dashboard_mode in DASHBOARD_MODES else "simple"
    age = default_age_profile if default_age_profile in AGE_PROFILES else "custom"
    pid = uuid.uuid4().hex
    profile = {
        "schema": PROFILE_SCHEMA,
        "id": pid,
        "display_name": name,
        "relationship": _clean(relationship),
        "linked_author_profile_id": _clean(linked_author_profile_id),
        "preferences": {
            "default_locale": _clean(default_locale) or "pt-BR",
            "default_age_profile": age,
            "default_visual_style": _clean(default_visual_style),
            "publication_markets": sorted({_clean(x) for x in (publication_markets or []) if _clean(x)}),
            "dashboard_mode": mode,
        },
        "avatar_asset_id": _clean(avatar_asset_id),
        "notes": str(notes or "").strip(),
        "active": True,
        "created_at": _now(),
        "updated_at": _now(),
        "version": 1,
    }
    BACKEND.put_json(_profile_path(pid), profile)
    rows = _index()
    rows.append({"id": pid, "display_name": name, "active": True, "updated_at": profile["updated_at"]})
    _save_index(rows)
    return profile


def get_workspace_profile(profile_id: str) -> dict | None:
    value = BACKEND.get_json(_profile_path(profile_id), None)
    return value if isinstance(value, dict) else None


def list_workspace_profiles(*, include_archived: bool = False) -> list[dict]:
    out = []
    for row in _index():
        p = get_workspace_profile(row.get("id", ""))
        if not p:
            continue
        if not include_archived and not p.get("active", True):
            continue
        out.append(p)
    return sorted(out, key=lambda p: _clean(p.get("display_name")).casefold())


def update_workspace_profile(profile_id: str, **changes) -> dict:
    p = get_workspace_profile(profile_id)
    if not p:
        raise KeyError("Perfil do workspace não encontrado.")
    allowed = {"display_name", "relationship", "linked_author_profile_id", "avatar_asset_id", "notes", "active"}
    pref_allowed = {"default_locale", "default_age_profile", "default_visual_style", "publication_markets", "dashboard_mode"}
    for key, value in changes.items():
        if key in allowed:
            p[key] = bool(value) if key == "active" else (_clean(value) if key != "notes" else str(value or "").strip())
        elif key in pref_allowed:
            prefs = p.setdefault("preferences", {})
            if key == "publication_markets":
                prefs[key] = sorted({_clean(x) for x in (value or []) if _clean(x)})
            elif key == "dashboard_mode":
                prefs[key] = value if value in DASHBOARD_MODES else "simple"
            elif key == "default_age_profile":
                prefs[key] = value if value in AGE_PROFILES else "custom"
            else:
                prefs[key] = _clean(value)
    if not _clean(p.get("display_name")):
        raise ValueError("O perfil precisa manter um nome.")
    p["updated_at"] = _now()
    p["version"] = int(p.get("version") or 1) + 1
    BACKEND.put_json(_profile_path(profile_id), p)
    rows = _index()
    for row in rows:
        if row.get("id") == profile_id:
            row.update({"display_name": p["display_name"], "active": bool(p.get("active", True)), "updated_at": p["updated_at"]})
    _save_index(rows)
    return p


def archive_workspace_profile(profile_id: str, archived: bool = True) -> dict:
    return update_workspace_profile(profile_id, active=not archived)


def _links() -> list[dict]:
    rows = BACKEND.get_json(PROJECT_LINKS_PATH, []) or []
    return rows if isinstance(rows, list) else []


def _save_links(rows: list[dict]) -> None:
    BACKEND.put_json(PROJECT_LINKS_PATH, rows)


def normalize_project_ref(kind: str, storage_path: str) -> tuple[str, str]:
    k = _clean(kind).lower()
    if k not in {"story", "coloring"}:
        raise ValueError("kind precisa ser story ou coloring.")
    path = _clean(storage_path).replace("fb://", "", 1).strip("/")
    if not path:
        raise ValueError("storage_path do projeto é obrigatório.")
    return k, path


def assign_project(
    profile_id: str,
    kind: str,
    storage_path: str,
    *,
    title: str = "",
    collection: str = "",
    shared_profile_ids: list[str] | None = None,
    thumbnail_asset_id: str = "",
) -> dict:
    if not get_workspace_profile(profile_id):
        raise KeyError("Perfil proprietário não encontrado.")
    k, path = normalize_project_ref(kind, storage_path)
    shared = [x for x in dict.fromkeys(shared_profile_ids or []) if x and x != profile_id and get_workspace_profile(x)]
    rows = _links()
    existing = next((x for x in rows if x.get("kind") == k and x.get("storage_path") == path), None)
    now = _now()
    if existing:
        existing.update({
            "owner_profile_id": profile_id,
            "shared_profile_ids": shared,
            "title": _clean(title) or existing.get("title", ""),
            "collection": _clean(collection) or existing.get("collection", ""),
            "thumbnail_asset_id": _clean(thumbnail_asset_id) or existing.get("thumbnail_asset_id", ""),
            "updated_at": now,
        })
        link = existing
    else:
        link = {
            "schema": PROJECT_LINK_SCHEMA,
            "id": uuid.uuid4().hex,
            "kind": k,
            "storage_path": path,
            "owner_profile_id": profile_id,
            "shared_profile_ids": shared,
            "title": _clean(title),
            "collection": _clean(collection),
            "thumbnail_asset_id": _clean(thumbnail_asset_id),
            "last_opened_by": {},
            "created_at": now,
            "updated_at": now,
        }
        rows.append(link)
    _save_links(rows)
    return deepcopy(link)


def update_project_sharing(kind: str, storage_path: str, shared_profile_ids: list[str]) -> dict:
    k, path = normalize_project_ref(kind, storage_path)
    rows = _links()
    link = next((x for x in rows if x.get("kind") == k and x.get("storage_path") == path), None)
    if not link:
        raise KeyError("Projeto ainda não foi atribuído a um perfil.")
    owner = link.get("owner_profile_id")
    link["shared_profile_ids"] = [x for x in dict.fromkeys(shared_profile_ids or []) if x and x != owner and get_workspace_profile(x)]
    link["updated_at"] = _now()
    _save_links(rows)
    return deepcopy(link)


def set_project_thumbnail(kind: str, storage_path: str, asset_id: str) -> dict:
    k, path = normalize_project_ref(kind, storage_path)
    rows = _links()
    link = next((x for x in rows if x.get("kind") == k and x.get("storage_path") == path), None)
    if not link:
        raise KeyError("Atribua o projeto a um perfil antes de definir thumbnail.")
    link["thumbnail_asset_id"] = _clean(asset_id)
    link["updated_at"] = _now()
    _save_links(rows)
    return deepcopy(link)


def project_link(kind: str, storage_path: str) -> dict | None:
    try:
        k, path = normalize_project_ref(kind, storage_path)
    except ValueError:
        return None
    return next((deepcopy(x) for x in _links() if x.get("kind") == k and x.get("storage_path") == path), None)


def project_links_for_profile(profile_id: str, *, include_shared: bool = True) -> list[dict]:
    rows = []
    for x in _links():
        owned = x.get("owner_profile_id") == profile_id
        shared = profile_id in (x.get("shared_profile_ids") or [])
        if owned or (include_shared and shared):
            row = deepcopy(x)
            row["access"] = "owner" if owned else "shared"
            row["last_opened_at"] = (x.get("last_opened_by") or {}).get(profile_id, "")
            rows.append(row)
    return sorted(rows, key=lambda x: (x.get("last_opened_at") or x.get("updated_at") or ""), reverse=True)


def touch_project(profile_id: str, kind: str, storage_path: str, *, title: str = "", collection: str = "") -> dict | None:
    k, path = normalize_project_ref(kind, storage_path)
    rows = _links()
    link = next((x for x in rows if x.get("kind") == k and x.get("storage_path") == path), None)
    if not link:
        return None
    if profile_id != link.get("owner_profile_id") and profile_id not in (link.get("shared_profile_ids") or []):
        return None
    link.setdefault("last_opened_by", {})[profile_id] = _now()
    if _clean(title): link["title"] = _clean(title)
    if _clean(collection): link["collection"] = _clean(collection)
    link["updated_at"] = _now()
    _save_links(rows)
    return deepcopy(link)


def visible_project_cards(cards: list[dict], profile_id: str, *, include_shared: bool = True, show_all: bool = False) -> list[dict]:
    """Filtra cards listados por ``storage_path`` sem alterar os projetos.

    ``show_all`` é útil para owners/admins durante migração. Não representa ACL.
    """
    if show_all or not profile_id:
        return [deepcopy(x) for x in cards]
    allowed = {(x.get("kind"), x.get("storage_path")) for x in project_links_for_profile(profile_id, include_shared=include_shared)}
    out = []
    for card in cards:
        kind = card.get("kind") or ("coloring" if str(card.get("storage_path", "")).startswith("livros_colorir/") else "story")
        path = str(card.get("storage_path") or card.get("arquivo") or "").replace("fb://", "", 1).strip("/")
        if (kind, path) in allowed:
            out.append(deepcopy(card))
    return out


def profile_summary(profile: dict | None) -> dict:
    p = profile or {}
    prefs = p.get("preferences") or {}
    return {
        "id": p.get("id", ""),
        "name": p.get("display_name", ""),
        "linked_author_profile_id": p.get("linked_author_profile_id", ""),
        "locale": prefs.get("default_locale", "pt-BR"),
        "age": prefs.get("default_age_profile", "3-8"),
        "style": prefs.get("default_visual_style", ""),
        "markets": list(prefs.get("publication_markets") or []),
        "dashboard_mode": prefs.get("dashboard_mode", "simple"),
        "projects": len(project_links_for_profile(p.get("id", ""))) if p.get("id") else 0,
        "security_boundary": False,
    }


def assign_saved_project_to_profile(profile_id: str, kind: str, storage_uri: str, state: dict) -> dict | None:
    """Vincula explicitamente um projeto recém-salvo ao perfil ativo.

    É uma conveniência de UX. Se não houver perfil ativo, não faz nada. O livro
    salvo continua independente do workspace.
    """
    if not profile_id or not get_workspace_profile(profile_id):
        return None
    return assign_project(
        profile_id,
        kind,
        storage_uri,
        title=(state or {}).get("titulo") or (state or {}).get("title") or "",
        collection=(state or {}).get("colecao") or (state or {}).get("tema_geral") or "",
    )

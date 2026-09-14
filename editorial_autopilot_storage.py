"""Persistência do runtime do Editorial Remaster Autopilot.

O engine mantém checkpoints em arquivos locais dentro do projeto Book Doctor.
No Streamlit Cloud esses arquivos podem desaparecer em reboot/redeploy, então
esta ponte espelha ``planos`` e ``remastered`` no backend persistente do
FaithBloom (Supabase quando configurado) e os reidrata antes de retomar.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from storage_backend import BACKEND


RUNTIME_SUBTREES = ("planos", "remastered")


def _prefix(project: dict) -> str:
    project_id = str(project.get("id") or "").strip()
    if not project_id:
        raise ValueError("Projeto Book Doctor sem id para persistência do Autopilot.")
    return f"book_doctor_projects/{project_id}"


def sync_runtime_tree(project: dict) -> dict:
    """Espelha checkpoints/planos/derivados do projeto no backend persistente."""
    root = Path(str(project.get("pasta") or ""))
    if not root.exists():
        return {"synced": 0, "errors": ["project_root_missing"]}
    synced = 0
    errors: list[str] = []
    base = _prefix(project)
    for subtree in RUNTIME_SUBTREES:
        local_root = root / subtree
        if not local_root.exists():
            continue
        for path in local_root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            try:
                BACKEND.put_bytes(
                    f"{base}/{rel}",
                    path.read_bytes(),
                    mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                )
                synced += 1
            except Exception as exc:
                errors.append(f"{rel}: {exc}")
    return {"synced": synced, "errors": errors}


def restore_runtime_tree(project: dict) -> dict:
    """Reidrata checkpoints/planos/derivados cloud no cache local do projeto."""
    root = Path(str(project.get("pasta") or ""))
    root.mkdir(parents=True, exist_ok=True)
    restored = 0
    errors: list[str] = []
    base = _prefix(project)
    for subtree in RUNTIME_SUBTREES:
        remote_prefix = f"{base}/{subtree}"
        try:
            remote_paths = BACKEND.list(remote_prefix)
        except Exception as exc:
            errors.append(f"{subtree}: {exc}")
            continue
        for remote in remote_paths:
            if not remote.startswith(base + "/"):
                continue
            rel = remote[len(base) + 1 :]
            local = root / rel
            if local.exists():
                continue
            try:
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(BACKEND.get_bytes(remote))
                restored += 1
            except Exception as exc:
                errors.append(f"{rel}: {exc}")
    return {"restored": restored, "errors": errors}

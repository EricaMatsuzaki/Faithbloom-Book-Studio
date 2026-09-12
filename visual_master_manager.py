"""Orquestracao do Visual Master sobre Asset Library e storage existentes."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from armazenamento import salvar_na_galeria
from asset_library import create_version, get_asset, get_asset_by_uri, set_archived, set_master_role, update_asset, versions_for
from character_universe import adicionar_referencia, atualizar_personagem_oficial, carregar_personagem_oficial
from storage_backend import persistir_arquivo
from visual_image_audit import audit_image

VISUAL_STATUSES = {"UPLOADED", "REFERENCE", "AUDITED", "RESTORATION_CANDIDATE", "MASTER_CANDIDATE", "APPROVED_VARIATION", "COLOR_MASTER", "LINEART_MASTER", "ARCHIVED", "REJECTED"}
REFERENCE_CATEGORIES = ("frente", "3/4", "perfil", "corpo inteiro", "close", "feliz", "triste", "surpresa", "ação", "outra")
IDENTITY_REVIEW_NOTICE = "Traits protegidos foram enviados como restrições ao modelo, mas a consistência visual precisa de revisão/aprovação humana."


def _set_visual(asset_id: str, status: str, **metadata) -> dict:
    if status not in VISUAL_STATUSES:
        raise ValueError("Status visual invalido.")
    return update_asset(asset_id, visual_status=status, metadata={"visual_status": status, **metadata})


def register_upload(pid: str, filename: str, data: bytes, category: str = "outra") -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Formato aceito: PNG, JPG/JPEG ou WEBP.")
    audit = audit_image(data, filename)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data); temp_path = tmp.name
    try:
        p = carregar_personagem_oficial(pid)
        asset = salvar_na_galeria(temp_path, Path(filename).stem, "referencia_personagem", ["character-reference"], {
            "personagem": p.get("nome", ""), "colecao": p.get("colecao", ""), "origem": "character_upload",
            "reference_category": category, "visual_status": "REFERENCE", "audit": audit,
        })
    finally:
        Path(temp_path).unlink(missing_ok=True)
    _set_visual(asset["id"], "REFERENCE", audit=audit, audited_at=int(time.time()))
    adicionar_referencia(pid, asset.get("storage_uri") or asset.get("caminho_arquivo", ""), category, "character_upload", {"asset_library_id": asset["id"]})
    return get_asset(asset["id"], materialize_file=False)


def create_candidate(source_asset_id: str, result_path: str, *, transformation: str, prompt: str, label: str = "A", dna_version: str = "") -> dict:
    uri = persistir_arquivo(result_path, "assets/visual_master")
    candidate = create_version(source_asset_id, storage_uri_value=uri, version_label=label, metadata={
        "transformation": transformation, "prompt": prompt, "visual_status": "MASTER_CANDIDATE",
        "character_dna_version": dna_version, "origin_asset_id": source_asset_id,
        "visual_identity_validated": False, "identity_review_notice": IDENTITY_REVIEW_NOTICE,
    })
    return _set_visual(candidate["id"], "MASTER_CANDIDATE")


def create_abc(source_asset_id: str, result_paths: list[str], *, transformation: str, prompt: str, dna_version: str = "") -> list[dict]:
    if len(result_paths) not in {1, 3}:
        raise ValueError("Escolha 1 resultado ou 3 resultados A/B/C.")
    return [create_candidate(source_asset_id, path, transformation=transformation, prompt=prompt, label=label, dna_version=dna_version) for path, label in zip(result_paths, ("A", "B", "C"))]


def approve_candidate(asset_id: str) -> dict:
    asset = get_asset(asset_id, materialize_file=False)
    if asset and asset.get("visual_status") == "APPROVED_VARIATION":
        return asset
    if not asset or asset.get("visual_status") not in {"MASTER_CANDIDATE", "RESTORATION_CANDIDATE"}:
        raise ValueError("Somente uma candidata pode ser aprovada.")
    return update_asset(asset_id, approved=True, visual_status="APPROVED_VARIATION", metadata={"visual_status": "APPROVED_VARIATION", "approved_at": int(time.time()), "approval": "human"})


def _reference_files_for_dna(character: dict, preferred_asset_id: str = "") -> list[dict]:
    """Materializa Color Master + Reference Pack para analise visual do DNA."""
    ordered_ids: list[str] = []
    if preferred_asset_id:
        ordered_ids.append(preferred_asset_id)
    for ref in character.get("reference_pack", []) or []:
        asset_id = str((ref.get("metadata") or {}).get("asset_library_id") or "")
        if asset_id and asset_id not in ordered_ids:
            ordered_ids.append(asset_id)

    files: list[dict] = []
    for asset_id in ordered_ids:
        asset = get_asset(asset_id, materialize_file=True)
        if not asset or asset.get("status") == "archived":
            continue
        path = str(asset.get("caminho_arquivo") or "")
        if not path or not Path(path).is_file():
            continue
        try:
            raw = Path(path).read_bytes()
        except OSError:
            continue
        suffix = Path(path).suffix.lower() or ".png"
        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "image/png")
        files.append({
            "name": Path(path).name,
            "mime_type": mime,
            "kind": "image",
            "data": raw,
            "sha256": asset_id,
        })
    return files


def autofill_visual_dna_from_saved_references(pid: str, *, preferred_asset_id: str = "") -> dict:
    """Completa lacunas do DNA a partir do Color Master e referencias ja salvas.

    Reutiliza o analisador visual do Jarvis Auto-Setup; nao substitui campos de DNA
    ja preenchidos/aprovados e nao cria personagem, referencia ou Master novo.
    """
    character = carregar_personagem_oficial(pid)
    if not character:
        raise KeyError(pid)
    files = _reference_files_for_dna(character, preferred_asset_id=preferred_asset_id)
    if not files:
        raise ValueError("Nao ha imagens materializaveis no Color Master/Reference Pack para preencher o DNA visual.")

    # Import local evita dependencia circular no carregamento dos modulos.
    from jarvis_character_auto_setup import analyze_character_images, merge_visual_dna

    analysis = analyze_character_images(
        str(character.get("nome") or ""),
        str(character.get("colecao") or ""),
        files,
        "Complete automaticamente o DNA visual usando o Color Master atual e as referencias salvas, sem alterar a identidade do personagem.",
    )
    dna = merge_visual_dna(character.get("dna"), analysis)
    metadata = dict(character.get("metadata") or {})
    metadata["dna_auto_fill"] = {
        "status": "completed",
        "filled_at": int(time.time()),
        "trigger": "color_master_approved",
        "preferred_asset_id": preferred_asset_id,
        "reference_count": len(files),
    }
    return atualizar_personagem_oficial(pid, {"dna": dna, "metadata": metadata})


def _autofill_visual_dna_best_effort(pid: str, asset_id: str) -> None:
    """Color Master nunca e desfeito se a IA do DNA falhar; registra o erro para retry."""
    try:
        autofill_visual_dna_from_saved_references(pid, preferred_asset_id=asset_id)
    except Exception as exc:
        try:
            character = carregar_personagem_oficial(pid)
            metadata = dict(character.get("metadata") or {})
            metadata["dna_auto_fill"] = {
                "status": "failed",
                "failed_at": int(time.time()),
                "trigger": "color_master_approved",
                "preferred_asset_id": asset_id,
                "error": str(exc)[:500],
            }
            atualizar_personagem_oficial(pid, {"metadata": metadata})
        except Exception:
            pass


def promote_master(pid: str, asset_id: str, role: str, *, confirmed: bool = False) -> dict:
    if not confirmed:
        raise PermissionError("Confirmacao humana explicita e obrigatoria.")
    if role not in {"color_master", "line_art_master"}:
        raise ValueError("Papel Master invalido.")
    asset = get_asset(asset_id, materialize_file=False)
    if not asset or not asset.get("approved"):
        raise PermissionError("A candidata precisa ser aprovada antes de virar Master.")
    if role == "line_art_master" and (asset.get("metadata") or {}).get("transformation") != "line_art":
        raise PermissionError("Line Art Master exige uma Line Art Candidate aprovada em QA.")
    p = carregar_personagem_oficial(pid)
    field = "color_master" if role == "color_master" else "line_art_master"
    old = p.get(field)
    current_ids = dict(p.get("metadata", {}).get("current_master_asset_ids", {}))
    old_asset_id = current_ids.get(role, "")
    old_asset = get_asset(old_asset_id, materialize_file=False) if old_asset_id else get_asset_by_uri(old, materialize_file=False)
    history = list(p.get("metadata", {}).get("master_history", []))
    old_uri = old or (old_asset or {}).get("storage_uri", "")
    if old_uri or old_asset:
        history.append({"role": role, "asset": old_uri, "asset_id": (old_asset or {}).get("id", ""), "superseded_at": int(time.time())})
    if old_asset and old_asset.get("id") != asset_id:
        set_master_role(old_asset["id"], role, False)
    uri = asset.get("storage_uri") or asset.get("caminho_arquivo", "")
    meta = dict(p.get("metadata") or {}); meta["master_history"] = history
    current_ids[role] = asset_id
    meta["current_master_asset_ids"] = current_ids
    atualizar_personagem_oficial(pid, {field: uri, "metadata": meta})
    set_master_role(asset_id, role, True)
    promoted = update_asset(asset_id, visual_status="COLOR_MASTER" if role == "color_master" else "LINEART_MASTER", metadata={"visual_status": "COLOR_MASTER" if role == "color_master" else "LINEART_MASTER", "master_approved_at": int(time.time())})
    if role == "color_master":
        _autofill_visual_dna_best_effort(pid, asset_id)
    return promoted


def promote_reference_color_master(pid: str, asset_id: str, *, confirmed: bool = False) -> dict:
    """Approve an existing character reference without regenerating its image."""
    if not confirmed:
        raise PermissionError("Confirme a revisão visual antes de definir o Color Master.")
    character = carregar_personagem_oficial(pid)
    reference_ids = {(ref.get("metadata") or {}).get("asset_library_id")
                     for ref in character.get("reference_pack", [])}
    if asset_id not in reference_ids:
        raise ValueError("Escolha uma referência vinculada a este personagem.")
    asset = get_asset(asset_id, materialize_file=False)
    if not asset or asset.get("visual_status") not in {"REFERENCE", "AUDITED", "APPROVED_VARIATION", "COLOR_MASTER"} or asset.get("status") == "archived":
        raise ValueError("Esta referência não está disponível para aprovação como Color Master.")
    if (character.get("metadata") or {}).get("current_master_asset_ids", {}).get("color_master") == asset_id:
        # Mesmo quando ja e o Master atual, permite completar DNA faltante automaticamente.
        _autofill_visual_dna_best_effort(pid, asset_id)
        return asset
    if not asset.get("approved"):
        update_asset(asset_id, approved=True, metadata={"approved_at": int(time.time()), "approval": "human"})
    return promote_master(pid, asset_id, "color_master", confirmed=True)


def archive_asset(asset_id: str) -> dict | None:
    _set_visual(asset_id, "ARCHIVED")
    return set_archived(asset_id, True)


def version_history(asset_id: str) -> list[dict]:
    return versions_for(asset_id)


def current_color_master_details(character: dict) -> dict:
    """Resolve the saved master link without changing asset metadata."""
    uri = character.get("color_master") or ""
    recorded_id = (character.get("metadata") or {}).get("current_master_asset_ids", {}).get("color_master", "")
    if not uri:
        return {"asset": None, "recorded_id": recorded_id, "consistent": False}
    resolved = get_asset_by_uri(uri, materialize_file=False)
    consistent = bool(resolved) and (not recorded_id or resolved.get("id") == recorded_id)
    return {"asset": resolved, "recorded_id": recorded_id, "consistent": consistent}

"""Identidade e apresentação de assets nos seletores do Character Universe."""
from __future__ import annotations


def asset_id(asset: dict) -> str:
    """Retorna a identidade única usada internamente pelo seletor."""
    return str((asset or {}).get("id") or "").strip()


def asset_option_label(asset: dict) -> str:
    """Cria um rótulo amigável sem usá-lo como identidade da opção."""
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    identifier = asset_id(asset)
    name = str(asset.get("nome") or "Asset sem nome")
    status = str(asset.get("visual_status") or metadata.get("visual_status") or "asset")
    collection = str(asset.get("colecao") or metadata.get("colecao") or "—")
    return f"{name} · {status} · {collection} · [{identifier[:8] or 'sem id'}]"


def asset_preview_details(asset: dict) -> str:
    """Resume os dados que permitem conferir o asset mostrado no preview."""
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    identifier = asset_id(asset)
    status = str(asset.get("visual_status") or metadata.get("visual_status") or "asset")
    details = [f"ID: {identifier[:8] or '—'}", f"Status: {status}"]
    version = asset.get("version_label")
    if version:
        details.append(f"Versão: {version}")
    origin = metadata.get("origem") or metadata.get("origin_asset_id") or asset.get("origem")
    parent = asset.get("parent_asset_id")
    if origin:
        details.append(f"Origem: {origin}")
    if parent:
        details.append(f"Parent asset: {parent}")
    return " · ".join(details)


def assets_by_id(assets: list[dict]) -> dict[str, dict]:
    """Indexa assets pelo ID completo; labels repetidos nunca descartam opções."""
    return {identifier: asset for asset in assets if (identifier := asset_id(asset))}

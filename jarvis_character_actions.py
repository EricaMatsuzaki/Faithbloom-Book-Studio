"""Acoes seguras do Jarvis sobre personagens ja existentes.

Este modulo conecta pedidos explicitos de preenchimento de DNA ao Character Universe
sem criar Character Master, registrar novas referencias ou alterar Masters. A regra e
fail-closed: nome ausente, personagem inexistente ou duplicidade interrompem a acao.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from character_universe import buscar_personagens_por_nome, carregar_personagem_oficial
from jarvis_character_auto_setup import VISUAL_FIELDS
from visual_master_manager import autofill_visual_dna_from_saved_references, current_color_master_details

_FILL_MARKERS = (
    "complete o dna",
    "complete meu dna",
    "complete automaticamente o dna",
    "preencha o dna",
    "preencher o dna",
    "preenche o dna",
    "complete o dna visual",
    "preencha o dna visual",
    "preencher o dna visual",
)


def extract_character_name(text: str) -> str:
    """Extrai o nome em frases como 'DNA do Téo', 'DNA da Manu' e 'DNA de Mel'."""
    match = re.search(
        r"\bdna(?:\s+visual)?\s+d(?:o|a|e)\s+([A-Za-zÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ-]*)",
        str(text or ""),
        flags=re.I,
    )
    return match.group(1).strip() if match else ""


def is_missing_dna_fill_command(text: str) -> bool:
    """Somente comandos explicitos de preenchimento podem executar a mutacao aditiva."""
    value = " ".join(str(text or "").casefold().split())
    if not value or not extract_character_name(text):
        return False
    return any(marker in value for marker in _FILL_MARKERS)


def _reference_signature(character: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    signature: list[tuple[str, str, str]] = []
    for ref in character.get("reference_pack", []) or []:
        metadata = ref.get("metadata") if isinstance(ref.get("metadata"), dict) else {}
        signature.append((
            str(ref.get("id") or ""),
            str(metadata.get("asset_library_id") or ""),
            str(ref.get("asset") or ""),
        ))
    return tuple(signature)


def _master_signature(character: dict[str, Any]) -> tuple[str, str]:
    metadata = character.get("metadata") if isinstance(character.get("metadata"), dict) else {}
    current = metadata.get("current_master_asset_ids") if isinstance(metadata.get("current_master_asset_ids"), dict) else {}
    return str(character.get("color_master") or ""), str(current.get("color_master") or "")


def _dna_fields(character: dict[str, Any]) -> dict[str, str]:
    dna = character.get("dna") if isinstance(character.get("dna"), dict) else {}
    fields = dna.get("campos_bloqueados") if isinstance(dna.get("campos_bloqueados"), dict) else {}
    return {str(key): str(value or "").strip() for key, value in fields.items()}


def _missing_visual_fields(character: dict[str, Any]) -> list[str]:
    fields = _dna_fields(character)
    return [field for field in VISUAL_FIELDS if not fields.get(field, "").strip()]


def _preferred_color_master_asset_id(character: dict[str, Any]) -> str:
    metadata = character.get("metadata") if isinstance(character.get("metadata"), dict) else {}
    current = metadata.get("current_master_asset_ids") if isinstance(metadata.get("current_master_asset_ids"), dict) else {}
    recorded = str(current.get("color_master") or "")
    if recorded:
        return recorded
    details = current_color_master_details(character)
    asset = details.get("asset") if isinstance(details, dict) else None
    return str((asset or {}).get("id") or "")


def resolve_existing_character(name: str, *, collection: str = "") -> dict[str, Any]:
    """Resolve exatamente um Character Master ativo; nunca cria fallback silencioso."""
    wanted = str(name or "").strip()
    if not wanted:
        raise ValueError("Não consegui identificar o nome do personagem no pedido.")
    matches = list(buscar_personagens_por_nome(wanted, incluir_arquivados=False))
    if collection:
        matches = [m for m in matches if str(m.get("colecao") or "").strip() == str(collection).strip()]
    if not matches:
        raise LookupError(f"Não encontrei um Character Master ativo chamado {wanted}.")
    if len(matches) != 1:
        collections = sorted({str(m.get("colecao") or "Sem coleção") for m in matches}, key=str.casefold)
        raise ValueError(
            f"Encontrei mais de um Character Master ativo chamado {wanted} ({', '.join(collections)}). "
            "Escolha a coleção correta antes de preencher o DNA."
        )
    pid = str(matches[0].get("id") or "")
    character = carregar_personagem_oficial(pid)
    if not character:
        raise LookupError(f"O cadastro de {wanted} não pôde ser carregado.")
    return character


def execute_missing_dna_fill(text: str, *, collection: str = "") -> dict[str, Any]:
    """Preenche somente lacunas do DNA de um personagem existente.

    Invariantes auditadas apos a operacao:
    - mesmo Character Master / mesmo id;
    - mesma assinatura do Color Master;
    - mesmo Reference Pack, sem referencias novas;
    - todos os campos de DNA previamente preenchidos permanecem identicos.
    """
    if not is_missing_dna_fill_command(text):
        raise ValueError("O pedido não contém uma autorização explícita para preencher o DNA visual.")

    name = extract_character_name(text)
    before = resolve_existing_character(name, collection=collection)
    pid = str(before.get("id") or "")
    before_master = _master_signature(before)
    before_refs = _reference_signature(before)
    before_fields = _dna_fields(before)
    missing_before = _missing_visual_fields(before)

    if not missing_before:
        return {
            "status": "already_complete",
            "character_id": pid,
            "character_name": str(before.get("nome") or name),
            "collection": str(before.get("colecao") or ""),
            "filled_fields": [],
            "remaining_missing_fields": [],
            "reference_count": len(before_refs),
            "color_master_preserved": True,
            "references_preserved": True,
            "character_preserved": True,
        }

    preferred_asset_id = _preferred_color_master_asset_id(before)
    updated = autofill_visual_dna_from_saved_references(pid, preferred_asset_id=preferred_asset_id)
    after = carregar_personagem_oficial(pid) or updated

    if str(after.get("id") or "") != pid:
        raise RuntimeError("Safety gate: o preenchimento de DNA tentou trocar o Character Master.")
    if _master_signature(after) != before_master:
        raise RuntimeError("Safety gate: o Color Master foi alterado durante o preenchimento de DNA.")
    if _reference_signature(after) != before_refs:
        raise RuntimeError("Safety gate: o Reference Pack foi alterado durante o preenchimento de DNA.")

    after_fields = _dna_fields(after)
    for key, old_value in before_fields.items():
        if old_value and after_fields.get(key, "") != old_value:
            raise RuntimeError(f"Safety gate: o campo de DNA já aprovado '{key}' foi alterado.")

    filled_fields = [
        field for field in missing_before
        if after_fields.get(field, "").strip()
    ]
    remaining = [field for field in missing_before if not after_fields.get(field, "").strip()]
    return {
        "status": "completed",
        "character_id": pid,
        "character_name": str(after.get("nome") or name),
        "collection": str(after.get("colecao") or ""),
        "filled_fields": filled_fields,
        "remaining_missing_fields": remaining,
        "reference_count": len(before_refs),
        "color_master_preserved": True,
        "references_preserved": True,
        "character_preserved": True,
    }


def format_dna_fill_reply(result: dict[str, Any]) -> str:
    """Converte resultado persistido em resposta publica curta e verificavel."""
    name = str(result.get("character_name") or "o personagem")
    if result.get("status") == "already_complete":
        return f"O DNA visual de {name} já estava completo. Mantive o mesmo Character Master, Color Master e Reference Pack."
    filled = list(result.get("filled_fields") or [])
    remaining = list(result.get("remaining_missing_fields") or [])
    if remaining:
        return (
            f"Atualizei o DNA visual de {name}: preenchi {len(filled)} campo(s) que estavam vazios e preservei o mesmo Character Master, "
            f"Color Master e as {result.get('reference_count', 0)} referências. Ainda faltam {len(remaining)} campo(s) que não puderam ser confirmados pelas imagens."
        )
    return (
        f"Atualizei o DNA visual de {name}: preenchi somente os campos que estavam vazios e preservei o mesmo Character Master, "
        f"Color Master e as {result.get('reference_count', 0)} referências já cadastradas."
    )

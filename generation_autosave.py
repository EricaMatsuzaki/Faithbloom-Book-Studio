"""FaithBloom — AutoSave de gerações valiosas.

Protege resultados que consomem chamadas de IA contra perda por rerun, troca de
página ou redeploy. Atualiza somente a referência explícita do projeto; sem ela,
cria um Book Master. Títulos não identificam uma obra com segurança.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from armazenamento import atualizar_livro_salvo, salvar_livro


def _texto(value: Any) -> str:
    return str(value or "").strip()


def persist_generation_snapshot(
    state: dict,
    *,
    reason: str,
    updates: dict | None = None,
) -> str:
    """Persiste um snapshot de geração e devolve o caminho do Book Master.

    `updates` permite salvar o resultado recém-gerado sem exigir que a tela já
    tenha copiado esses campos para o session_state.
    """
    if not isinstance(state, dict):
        return ""

    snapshot = deepcopy(state)
    if updates:
        snapshot.update(deepcopy(updates))

    if not _texto(snapshot.get("colecao")) or not _texto(snapshot.get("titulo")):
        return ""

    caminho = _texto(snapshot.get("storage_path"))
    if caminho:
        caminho = atualizar_livro_salvo(caminho, snapshot)
    else:
        caminho = salvar_livro(snapshot)

    state["storage_path"] = caminho
    state["autosave_status"] = "saved"
    state["autosave_last_reason"] = reason
    state["autosave_last_path"] = caminho
    return caminho


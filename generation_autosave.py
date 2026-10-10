"""FaithBloom — AutoSave de gerações valiosas.

Protege resultados que consomem chamadas de IA contra perda por rerun, troca de
página ou redeploy. O AutoSave procura primeiro um projeto existente com a mesma
coleção+título; se não encontrar, cria um Book Master. Assim a autora não precisa
lembrar de clicar em Salvar depois de cada geração.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from armazenamento import atualizar_livro_salvo, listar_livros, salvar_livro


def _texto(value: Any) -> str:
    return str(value or "").strip()


def _achar_projeto_existente(state: dict) -> str:
    colecao = _texto(state.get("colecao"))
    titulo = _texto(state.get("titulo"))
    if not colecao or not titulo:
        return ""
    alvo = titulo.casefold()
    for item in listar_livros(colecao):
        if _texto(item.get("titulo")).casefold() == alvo:
            return _texto(item.get("storage_path"))
    return ""


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

    caminho = _texto(snapshot.get("storage_path")) or _achar_projeto_existente(snapshot)
    if caminho:
        caminho = atualizar_livro_salvo(caminho, snapshot)
    else:
        caminho = salvar_livro(snapshot)

    state["storage_path"] = caminho
    state["autosave_status"] = "saved"
    state["autosave_last_reason"] = reason
    state["autosave_last_path"] = caminho
    return caminho

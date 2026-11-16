"""FaithBloom — AutoSave de gerações valiosas.

Protege resultados que consomem chamadas de IA contra perda por rerun, troca de
página ou redeploy. Atualiza somente a referência explícita do projeto; sem ela,
cria um Book Master. Títulos não identificam uma obra com segurança.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from armazenamento import (BOOK_SAVE_CONTEXT_KEY, BookSaveConflict,
                           atualizar_livro_salvo, salvar_livro, carregar_livro,
                           get_book_read_context,
                           _book_payload, _book_read_path, _field_changes, _set_field, _MISSING)

_CONTROL_FIELDS = {"autosave_status", "autosave_error", "autosave_last_reason", "autosave_last_path"}


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

    if updates:
        # Some generators return an output without first assigning it to state.
        # Preserve that received result even when storage rejects the checkpoint.
        state.update(deepcopy(updates))
    snapshot = deepcopy(state)
    caminho = _texto(snapshot.get("storage_path"))
    observed = {}
    if caminho:
        try:
            observed = get_book_read_context(snapshot, caminho)["view"]
        except Exception:
            # Preserve the received result even after worker eviction. The
            # writer below rejects a missing baseline before inspecting assets.
            pass
    for key in _CONTROL_FIELDS:
        if key in observed:
            snapshot[key] = deepcopy(observed[key])
        else:
            snapshot.pop(key, None)

    if not _texto(snapshot.get("colecao")) or not _texto(snapshot.get("titulo")):
        return ""

    previous = state.get("autosave_pending")
    draft = {key: deepcopy(value) for key, value in snapshot.items()
             if key not in {BOOK_SAVE_CONTEXT_KEY, "autosave_pending"}}
    changes = ([{"path": list(field), "delete": wanted is _MISSING,
                 **({"value": deepcopy(wanted)} if wanted is not _MISSING else {})}
                for field, wanted in _field_changes(observed, draft)
                if field[0] not in _CONTROL_FIELDS] if observed else None)
    pending = {"reason": reason, "storage_path": caminho, "draft": draft,
               "changes": changes, "received_fields": sorted(updates) if updates else None}
    if isinstance(previous, dict):
        history = deepcopy(previous.get("history") or [])
        old = {key: deepcopy(value) for key, value in previous.items() if key != "history"}
        if old.get("draft") != draft:
            history.append(old)
        if history:
            pending["history"] = history
    state["autosave_pending"] = pending
    try:
        if caminho:
            caminho = atualizar_livro_salvo(caminho, snapshot)
        else:
            caminho = salvar_livro(snapshot)
    except Exception as exc:
        state["autosave_status"] = "conflict" if isinstance(exc, BookSaveConflict) else "error"
        state["autosave_error"] = str(exc)
        raise

    # The committed record may contain edits from another session. Keep those
    # alongside the new baseline; a refreshed baseline with an old draft would
    # otherwise make the next save overwrite those edits.
    state.clear()
    state.update(snapshot)
    state.pop("autosave_pending", None)
    state.pop("autosave_error", None)
    state["storage_path"] = caminho
    state["autosave_status"] = "saved"
    state["autosave_last_reason"] = reason
    state["autosave_last_path"] = caminho
    return caminho


def retry_pending_generation_save(state: dict) -> str:
    """Retry persistence only; this function never invokes an AI provider."""
    pending = state.get("autosave_pending")
    if not isinstance(pending, dict):
        raise ValueError("Não há um resultado aguardando salvamento neste projeto.")
    if state.get("autosave_status") == "needs_review":
        raise PermissionError("Confira a versão reaberta e use a confirmação para reaplicar o resultado recebido.")
    return persist_generation_snapshot(state, reason=str(pending.get("reason") or "recovered_generation"))


def reload_pending_generation_source(state: dict) -> dict:
    """Read the current source for review, retaining the received draft separately."""
    pending = state.get("autosave_pending")
    if not isinstance(pending, dict) or not pending.get("storage_path"):
        raise ValueError("Este resultado ainda não possui um livro salvo para reabrir. Tente salvar o rascunho.")
    reference = str(pending["storage_path"])
    if _book_read_path(reference) != _book_read_path(str(state.get("storage_path") or reference)):
        raise BookSaveConflict(("storage_path",))
    fresh = carregar_livro("", reference)
    if BOOK_SAVE_CONTEXT_KEY not in fresh:
        raise BookSaveConflict(missing_baseline=True)
    state.clear()
    state.update(fresh)
    state["autosave_pending"] = deepcopy(pending)
    state["autosave_status"] = "needs_review"
    return state


def apply_pending_generation_result(state: dict, *, confirmed: bool = False) -> str:
    """Apply a received draft to the version the author explicitly reopened.

    No late read is used to manufacture a baseline. A subsequent competing edit
    still conflicts with the baseline displayed during the prior review.
    """
    pending = state.get("autosave_pending")
    if confirmed is not True or state.get("autosave_status") != "needs_review":
        raise PermissionError("Reabra o livro e confirme a conferência antes de reaplicar o resultado recebido.")
    if not isinstance(pending, dict) or not isinstance(pending.get("draft"), dict):
        raise ValueError("O resultado recebido precisa de recuperação manual.")
    context = get_book_read_context(state, str(state.get("storage_path") or ""))
    if _book_read_path(str(pending.get("storage_path") or "")) != context.get("path"):
        raise BookSaveConflict(("storage_path",))
    draft = _book_payload(pending["draft"])
    changes = pending.get("changes")
    if not isinstance(changes, list):
        fields = pending.get("received_fields")
        if not isinstance(fields, list) or not fields:
            raise PermissionError("Não foi possível separar as alterações deste rascunho. Baixe a cópia recebida para revisão manual.")
        changes = [{"path": [key], "value": draft[key]} for key in fields if key in draft]
    work = deepcopy(state)
    for change in changes:
        field = tuple(change["path"])
        if field[0] in _CONTROL_FIELDS:
            continue
        wanted = _MISSING if change.get("delete") else change["value"]
        _set_field(work, field, wanted if wanted is _MISSING else deepcopy(wanted))
    work.pop("autosave_pending", None)
    try:
        result = persist_generation_snapshot(work, reason=str(pending.get("reason") or "recovered_generation"))
    except Exception:
        state.clear()
        state.update(work)
        raise
    state.clear()
    state.update(work)
    return result


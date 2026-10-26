"""Checkpoint sequential UI work before allowing the next paid step."""
from __future__ import annotations

import streamlit as st

from generation_autosave import persist_generation_snapshot
from generation_save_ui import render_generation_save_recovery


def start_generation_pipeline(state: dict, *, flow: str) -> None:
    """An explicit Finalize click starts a fresh set of step checkpoints."""
    state["generation_pipeline_checkpoint"] = {"flow": flow, "completed": []}


def save_generation_pipeline(state: dict, *, reason: str, key_prefix: str) -> str:
    try:
        reference = persist_generation_snapshot(state, reason=reason)
    except Exception:
        if render_generation_save_recovery(state, key_prefix=key_prefix):
            st.stop()
        st.error("Não foi possível confirmar o salvamento. A próxima etapa foi pausada.")
        st.stop()
    if not reference:
        st.error("Confira o título e a coleção do livro antes de continuar a geração.")
        st.stop()
    return reference


def run_generation_step(state: dict, step: str, node, *args, flow: str, **kwargs) -> None:
    """Keep received data in the session, then persist before the next step.

    Internal image/audio AutoSave can raise after receiving an asset. Passing
    the original state preserves its pending draft. Committed steps are skipped
    after recovery, so an earlier successful LLM request is not bought again.
    """
    # A button rendered after a mid-step failure is handled on the next rerun
    # by the page's top recovery guard. Both renders need the same widget keys.
    prefix = f"{flow}_save"
    if render_generation_save_recovery(state, key_prefix=prefix):
        st.stop()
    if not str(state.get("titulo") or "").strip() or not str(state.get("colecao") or "").strip():
        st.error("Confira o título e a coleção do livro antes de continuar a geração.")
        st.stop()
    checkpoint = state.get("generation_pipeline_checkpoint")
    if not isinstance(checkpoint, dict) or checkpoint.get("flow") != flow:
        start_generation_pipeline(state, flow=flow)
        checkpoint = state["generation_pipeline_checkpoint"]
    if step in checkpoint.get("completed", []):
        return
    try:
        result = node(state, *args, **kwargs)
    except Exception:
        if render_generation_save_recovery(state, key_prefix=prefix):
            st.stop()
        raise
    if isinstance(result, dict) and result is not state:
        state.update(result)
    if render_generation_save_recovery(state, key_prefix=prefix):
        st.stop()
    # A node can refresh state during its own AutoSave, so reacquire the record.
    checkpoint = state.setdefault("generation_pipeline_checkpoint", {"flow": flow, "completed": []})
    checkpoint.setdefault("completed", []).append(step)
    save_generation_pipeline(state, reason=f"pipeline_step:{flow}:{step}", key_prefix=prefix)

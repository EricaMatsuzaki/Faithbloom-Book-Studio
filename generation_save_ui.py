"""Recover a received narrative result without invoking another provider."""
from __future__ import annotations

import hashlib
import json

import streamlit as st

from generation_autosave import (apply_pending_generation_result,
                                 reload_pending_generation_source,
                                 retry_pending_generation_save)


def _preview(state):
    parts = []
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"titulo", "texto", "amostra", "sinopse_poetica", "licao_final"} and isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(state)
    return "\n\n".join(parts)[:16000] or "O resultado completo está disponível no arquivo para baixar."


def render_generation_save_recovery(state: dict, *, key_prefix="generation_save") -> bool:
    """Return True while actions that could buy another result must stay paused."""
    pending = state.get("autosave_pending") if isinstance(state, dict) else None
    if not isinstance(pending, dict):
        return False
    context = state.get("_book_save_context") or {}
    identity = hashlib.sha256(json.dumps([pending.get("storage_path"), pending.get("draft"), context.get("token")],
                                        ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]
    key = f"{key_prefix}_{identity}"
    st.warning("Há um resultado recebido aguardando salvamento. Confira-o antes de pedir outra geração.")
    if state.get("autosave_error"):
        st.info(str(state["autosave_error"]))
    with st.expander("Conferir o resultado recebido", expanded=True):
        st.text_area("Resultado recebido", _preview(pending.get("draft") or {}), disabled=True,
                     height=220, key=key + "_received")
        st.download_button("Baixar cópia do resultado recebido",
                           data=json.dumps(pending.get("draft") or {}, ensure_ascii=False, indent=2).encode(),
                           file_name="faithbloom-resultado-recebido.json", mime="application/json", key=key + "_download")
    left, right = st.columns(2)
    if left.button("Tentar salvar resultado recebido", key=key + "_retry"):
        try:
            retry_pending_generation_save(state)
        except Exception as exc:
            st.error(str(exc))
        else:
            st.success("Resultado salvo. Nenhuma nova geração foi solicitada.")
            st.rerun()
    if right.button("Reabrir livro para conferir", disabled=not bool(pending.get("storage_path")), key=key + "_reload"):
        try:
            reload_pending_generation_source(state)
        except Exception as exc:
            st.error(str(exc))
        else:
            st.rerun()
    if state.get("autosave_status") == "needs_review":
        st.text_area("Versão salva atual", _preview({k: v for k, v in state.items()
                                                    if k not in {"_book_save_context", "autosave_pending"}}),
                     disabled=True, height=220, key=key + "_current")
        confirmed = st.checkbox("Conferi a versão atual e quero reaplicar o resultado recebido.", key=key + "_confirmed")
        if st.button("Salvar o resultado conferido", disabled=not confirmed, key=key + "_apply"):
            try:
                apply_pending_generation_result(state, confirmed=confirmed)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success("Resultado conferido e salvo. Nenhuma nova geração foi solicitada.")
                st.rerun()
    return True

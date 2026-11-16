"""Reusable UI selectors for saved FaithBloom entities.

The goal is to prefer canonical saved values over free typing while preserving an
explicit "other/new" path when creation is intentional. This reduces accidental
duplicates caused by spelling, accents or capitalization differences.
"""
from __future__ import annotations

from typing import Iterable

import streamlit as st

NEW_SENTINEL = "__faithbloom_new__"
EMPTY_SENTINEL = "__faithbloom_empty__"


def normalize_saved_choices(values: Iterable[object], current: str = "") -> list[str]:
    """Return unique, non-empty choices preserving first spelling/order."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in [*list(values or []), current]:
        value = str(raw or "").strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def select_saved_or_new(
    label: str,
    saved_values: Iterable[object],
    *,
    current: str = "",
    key: str,
    new_label: str = "➕ Outra / nova…",
    new_input_label: str | None = None,
    placeholder: str = "",
    allow_empty: bool = False,
    empty_label: str = "— Nenhum / definir depois —",
    help: str | None = None,
) -> str:
    """Streamlit selectbox backed by canonical saved values plus explicit new path."""
    values = normalize_saved_choices(saved_values, current=current)
    options: list[str] = []
    if allow_empty:
        options.append(EMPTY_SENTINEL)
    options.extend(values)
    options.append(NEW_SENTINEL)

    current_clean = str(current or "").strip()
    if current_clean:
        current_idx = next(
            (i for i, item in enumerate(options) if item not in {NEW_SENTINEL, EMPTY_SENTINEL} and item.casefold() == current_clean.casefold()),
            0,
        )
    elif allow_empty:
        current_idx = 0
    else:
        current_idx = 0 if values else len(options) - 1

    selected = st.selectbox(
        label,
        options,
        index=current_idx,
        key=key,
        format_func=lambda item: new_label if item == NEW_SENTINEL else empty_label if item == EMPTY_SENTINEL else item,
        help=help,
    )
    if selected == EMPTY_SENTINEL:
        return ""
    if selected == NEW_SENTINEL:
        return st.text_input(
            new_input_label or f"Novo valor para {label}",
            value="" if current_clean.casefold() in {x.casefold() for x in values} else current_clean,
            placeholder=placeholder,
            key=f"{key}__new",
        ).strip()
    return str(selected).strip()


def select_many_saved_plus_new(
    label: str,
    saved_values: Iterable[object],
    *,
    current: Iterable[object] | None = None,
    key: str,
    new_input_label: str = "Outros / novos (separe por vírgula)",
    placeholder: str = "",
    help: str | None = None,
) -> list[str]:
    """Select multiple canonical values and optionally append explicitly new names."""
    values = normalize_saved_choices(saved_values)
    wanted = {str(x or "").strip().casefold() for x in (current or []) if str(x or "").strip()}
    defaults = [x for x in values if x.casefold() in wanted]
    selected = st.multiselect(label, values, default=defaults, key=key, help=help)
    extras = st.text_input(new_input_label, placeholder=placeholder, key=f"{key}__new").strip()
    combined = list(selected)
    if extras:
        combined.extend(x.strip() for x in extras.split(",") if x.strip())
    return normalize_saved_choices(combined)

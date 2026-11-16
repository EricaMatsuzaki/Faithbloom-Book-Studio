"""Keep the observed project baseline until an explicit reload or confirmed save."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any

import streamlit as st

from editorial_project_updates import load_metadata_snapshot, metadata_edit_status, update_metadata_fields
import storage_backend as storage


_SESSION_KEY = "project_metadata_editors"


def _fingerprint(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()[:16]


@dataclass
class ProjectMetadataEditor:
    namespace: str
    kind: str
    snapshot: dict
    entry: dict
    state: dict
    stale: bool
    pending_slot: Any = None

    @property
    def reference(self) -> str:
        return self.snapshot["reference"]

    @property
    def can_save(self) -> bool:
        return not self.stale and self.snapshot.get("edit_status", {}).get("allowed") is True

    def key(self, name: str) -> str:
        scope = hashlib.sha256(self.reference.encode()).hexdigest()[:12]
        return f"{self.namespace}_metadata_{scope}_{_fingerprint(self.entry['baseline'])}_{name}"

    @property
    def observed_snapshot(self) -> dict:
        return deepcopy(self.entry["observed_snapshot"])

    def preserve_pending(self, updated: dict, *, fields: list[str]) -> None:
        self.entry["pending"] = {"reference": self.reference, "fields": list(fields),
                                 "changes": {field: deepcopy(updated[field]) for field in fields if field in updated}}
        self.entry["needs_reload"] = True
        self.stale = True
        _render_pending(self.entry, self.key("pending_after_save"),self.pending_slot)

    def preserve_form_inputs(self, inputs: dict) -> None:
        pending = self.entry.setdefault("pending", {"reference": self.reference})
        pending["form_inputs"] = deepcopy(inputs)
        _render_pending(self.entry,self.key("pending_inputs"),self.pending_slot)

    def adopt_committed_snapshot(self, snapshot: dict) -> None:
        if snapshot["reference"] != self.reference:
            raise storage.AccessDenied("A confirmação pertence a outro projeto.")
        self.entry.update(baseline=deepcopy(snapshot["baseline"]), state=deepcopy(snapshot["state"]),
                          observed_snapshot=deepcopy(snapshot), needs_reload=False)
        self.entry.pop("pending", None)
        if self.pending_slot is not None:
            self.pending_slot.empty()
        self.snapshot = deepcopy(snapshot)
        self.snapshot["edit_status"] = metadata_edit_status(snapshot)
        self.stale = False
        self.state.clear()
        self.state.update(deepcopy(snapshot["state"]))

    def save(self, updated: dict, *, fields: list[str], watched_fields: tuple[str, ...] = ()) -> bool:
        if not self.can_save:
            st.warning("Recarregue o projeto ou conclua a conferência da geração antes de salvar alterações.")
            self.preserve_pending(updated,fields=fields)
            return False
        try:
            updates = {field: deepcopy(updated[field]) for field in fields if field in updated}
            observed = {**self.entry["observed_snapshot"], "baseline": deepcopy(self.entry["baseline"])}
            saved = update_metadata_fields(observed, updates, watched_fields=watched_fields)
        except Exception as exc:
            if isinstance(exc, storage.AccessDenied):
                st.error("Sua sessão não permite salvar este projeto. As alterações não foram confirmadas.")
            elif isinstance(exc, storage.StorageConflict):
                st.warning("O projeto foi alterado durante o salvamento. Recarregue os dados salvos antes de continuar; suas alterações foram preservadas abaixo.")
            elif isinstance(exc, PermissionError):
                st.warning("A geração deste projeto precisa ser concluída ou conferida antes desta alteração. Seus dados foram preservados para revisão.")
            else:
                st.error("Não foi possível confirmar o salvamento. Preserve suas alterações e recarregue os dados salvos antes de tentar novamente.")
            self.preserve_pending(updated,fields=fields)
            return False
        self.adopt_committed_snapshot(saved)
        return True


def _render_pending(entry: dict, key: str, slot=None) -> None:
    pending = entry.get("pending")
    if slot is not None:
        slot.empty()
    if pending and slot is not None:
        with slot.container():
            st.download_button("Baixar alterações não salvas", json.dumps(pending, ensure_ascii=False, indent=2),
                file_name="faithbloom_alteracoes_projeto.json", mime="application/json", key=key)
    elif pending:
        st.download_button("Baixar alterações não salvas", json.dumps(pending, ensure_ascii=False, indent=2),
            file_name="faithbloom_alteracoes_projeto.json", mime="application/json", key=key)


def open_project_metadata(reference: str, *, kind: str = "story", namespace: str, on_reload=None) -> ProjectMetadataEditor:
    # This read authorizes the current reference before any cached book is used.
    try:
        snapshot = load_metadata_snapshot(reference, kind=kind)
        if (not isinstance(snapshot, dict) or not isinstance(snapshot.get("baseline"), dict)
                or not isinstance(snapshot.get("state"), dict) or not snapshot.get("reference")):
            raise storage.StorageCorrupt("Invalid project metadata snapshot")
        _fingerprint(snapshot["baseline"])
        snapshot["edit_status"] = metadata_edit_status(snapshot)
    except Exception as exc:
        if isinstance(exc, storage.AccessDenied):
            st.session_state.pop(_SESSION_KEY, None)
            st.error("Você não tem acesso a este projeto nesta sessão.")
        else:
            st.error("Não foi possível abrir os dados salvos deste projeto. Atualize a página para conferir o acesso e o armazenamento.")
        st.stop()

    contexts = st.session_state.setdefault(_SESSION_KEY, {})
    entry = contexts.get(namespace)
    if not isinstance(entry, dict) or entry.get("reference") != snapshot["reference"]:
        entry = {"reference": snapshot["reference"], "baseline": deepcopy(snapshot["baseline"]),
                 "state": deepcopy(snapshot["state"]), "observed_snapshot": deepcopy(snapshot), "needs_reload": False}
        contexts[namespace] = entry
    stale = bool(entry.get("needs_reload")) or entry["baseline"] != snapshot["baseline"]
    editor = ProjectMetadataEditor(namespace, kind, snapshot, entry, deepcopy(entry["state"]), stale,st.empty())
    if stale:
        st.warning("Este projeto foi atualizado em outra ação. Recarregue os dados salvos antes de continuar.")
    if snapshot["edit_status"].get("allowed") is not True:
        st.info(snapshot["edit_status"].get("message") or "Aguarde a geração terminar ou confira o resultado antes de alterar o projeto.")
    if stale or snapshot["edit_status"].get("allowed") is not True:
        if st.button("Recarregar dados salvos do projeto", key=editor.key("reload")):
            if on_reload is not None:
                try:
                    on_reload(deepcopy(snapshot))
                except Exception:
                    st.error("Não foi possível reabrir esta versão no projeto ativo. Volte ao livro de origem e abra a revisão novamente.")
                    return editor
            entry.update(baseline=deepcopy(snapshot["baseline"]), state=deepcopy(snapshot["state"]),
                         observed_snapshot=deepcopy(snapshot), needs_reload=False)
            st.rerun()
    _render_pending(entry, editor.key("pending"),editor.pending_slot)
    return editor

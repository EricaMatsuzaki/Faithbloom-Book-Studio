"""Field-scoped updates for saved projects; paid execution remains authoritative.

The snapshot comes from the document actually shown to the editor. Asset work
stays outside retryable callbacks. Legacy pilot locking remains same-host only.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import storage_backend as storage
from storage_updates import update_json_document


METADATA_FIELDS = frozenset({
    "authorship", "autora", "bestseller_readiness_report", "agent_skill_audit",
    "versiculo_referencia", "bible_reference_candidate", "bible_reference_validation",
    "market_evidence", "market_intelligence_brief", "mapa_emocional",
    "paleta_emocional_preset", "emotional_book_binding", "cenas_texto",
    "cenas_imagem", "cenas_imagem_aprovadas", "historico_imagens_cenas", "book_id",
})


class ProjectMetadataConflict(storage.StorageConflict):
    def __init__(self, fields=()):
        self.fields = tuple(sorted(fields))
        super().__init__("projeto observado", "projeto atualizado")
        self.args = ("Este projeto foi atualizado em outra tela. Suas alterações não foram substituídas; recarregue o projeto antes de tentar novamente.",)


def _reference(reference, kind, *, action):
    prefix = {"story": "livros", "coloring": "livros_colorir"}.get(kind)
    if not prefix:
        raise ValueError("Tipo de projeto salvo inválido.")
    path = (storage.uri_to_path(reference) if storage.is_storage_uri(reference)
            else storage._normalize_storage_path(reference, allow_empty=False))
    path = storage._tenant_path(path, action=action)
    logical = path.split("/", 2)[-1] if path.startswith("tenants/") else path
    if not logical.startswith(prefix + "/") or not logical.endswith(".json"):
        raise ValueError("A referência não corresponde ao tipo deste projeto.")
    return path


def _document(value):
    if value is None:
        raise storage.StorageNotFound("O projeto salvo não foi encontrado. Nenhum novo livro foi criado.")
    if not isinstance(value, dict):
        raise storage.StorageCorrupt("O projeto salvo precisa de recuperação.")
    return value


def _same_field(first, second, key):
    return (key in first) == (key in second) and first.get(key) == second.get(key)


def _assert_identity(current, snapshot, path):
    _document(current)
    baseline = snapshot.get("baseline")
    if not isinstance(baseline, dict):
        raise ValueError("Reabra o projeto para recuperar a versão observada.")
    if not _same_field(current, baseline, "book_id"):
        raise ProjectMetadataConflict(("book_id",))
    declared = current.get("storage_path")
    if declared and _reference(declared, snapshot["kind"], action="storage.read") != path:
        raise PermissionError("O documento salvo declara outra referência de projeto.")


def _assert_editable(current):
    if "editorial_product" not in current:
        return
    from editorial_generation_runtime import _execution
    execution = _execution(current)
    if (execution.get("legacy_review_required") or execution.get("claim")
            or execution.get("status") in {"running", "needs_reconciliation", "legacy_needs_review"}
            or any(a["state"] in {"running", "uncertain", "raw"} for a in execution["attempts"])):
        raise PermissionError("Conclua ou confira a geração em andamento no Studio antes de alterar este projeto. Suas alterações foram preservadas.")


def _snapshot(path, kind, raw):
    raw = deepcopy(_document(raw))
    view = storage.materializar_assets_em_objeto(deepcopy(raw))
    reference = storage.storage_uri(path)
    view["storage_path"] = reference
    if not isinstance(raw.get("editorial_product"), dict):
        from armazenamento import bind_book_read_context
        bind_book_read_context(view, reference, raw)
    return {"reference": reference, "kind": kind, "book_id": raw.get("book_id"),
            "baseline": raw, "state": view}


def load_metadata_snapshot(reference, kind="story"):
    path = _reference(reference, kind, action="storage.read")
    raw = _document(storage.BACKEND.get_json(path, None))
    snapshot = {"baseline": raw, "kind": kind}
    _assert_identity(raw, snapshot, path)
    return _snapshot(path, kind, raw)


def metadata_edit_status(snapshot):
    try:
        path = _reference(snapshot["reference"], snapshot["kind"], action="storage.write")
        current = _document(storage.BACKEND.get_json(path, None))
        _assert_identity(current, snapshot, path)
        _assert_editable(current)
    except storage.AccessDenied:
        return {"allowed": False, "message": "Esta sessão permite apenas consultar este projeto. Use uma conta autorizada para salvar alterações."}
    except ProjectMetadataConflict as exc:
        return {"allowed": False, "message": str(exc)}
    except storage.StorageError:
        return {"allowed": False, "message": "Não foi possível confirmar o estado salvo deste projeto. Recarregue antes de editar."}
    except (PermissionError, ValueError, KeyError) as exc:
        return {"allowed": False, "message": str(exc)}
    return {"allowed": True, "message": ""}


def update_metadata_fields(snapshot, updates, *, watched_fields=()):
    """Merge intended fields against their observed values, retaining other edits.

    `watched_fields` binds a generated report/map/image to the source observed
    before its preparation. No provider or upload runs in the mutation.
    """
    if not isinstance(updates, dict) or set(updates) - METADATA_FIELDS:
        raise ValueError("Esta ação não pode substituir os dados completos do projeto.")
    json.dumps(updates, allow_nan=False)  # Reject malformed input before asset work.
    path = _reference(snapshot["reference"], snapshot["kind"], action="storage.write")
    baseline = deepcopy(snapshot["baseline"])
    watched_fields = tuple(watched_fields)

    def check(current, prepared=None):
        _assert_identity(current, snapshot, path)
        _assert_editable(current)
        conflicts = [key for key in watched_fields if not _same_field(current, baseline, key)]
        for key in updates:
            if not _same_field(current, baseline, key):
                # A repeated acknowledgement may confirm the already-saved value.
                if prepared is None or not (key in current and current[key] == prepared[key]):
                    conflicts.append(key)
        if conflicts:
            raise ProjectMetadataConflict(conflicts)
        if "book_id" in updates:
            proposed = updates["book_id"]
            if (not isinstance(proposed, str) or not proposed.strip()
                    or current.get("book_id") and current["book_id"] != proposed
                    or "editorial_product" in current and current.get("book_id") != proposed):
                raise PermissionError("A identidade do livro não pode ser substituída.")

    check(_document(storage.BACKEND.get_json(path, None)))
    prepared = storage.persistir_assets_em_objeto(deepcopy(updates),
        "assets/project_metadata/" + sha256(path.encode()).hexdigest()[:20])

    def merge(current):
        check(current, prepared)
        result = deepcopy(current)
        result.update(deepcopy(prepared))
        return result

    if "editorial_product" in baseline:
        from editorial_generation_runtime import _update
        saved = _update(snapshot["reference"], snapshot["book_id"], merge)
    else:
        # Prevent a legacy snapshot from changing a source converted to a product
        # while assets were prepared. The callback decides from the latest value.
        def ordinary(value):
            if "editorial_product" in _document(value):
                raise ProjectMetadataConflict(("editorial_product",))
            return merge(value)
        saved = update_json_document(storage.BACKEND, path, ordinary, allow_legacy_pilot=True)
    return _snapshot(path, snapshot["kind"], saved)

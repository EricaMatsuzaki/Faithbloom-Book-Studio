"""Paid editorial attempts share their canonical product's atomic document.

No provider, asset upload or secondary document write runs in a retryable
callback. Local/RPC semantics are strict; legacy pilot coordination is limited
to processes sharing one host/cache. No timeout releases a paid attempt.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
import socket
import threading
import uuid

import storage_backend as storage
from storage_updates import update_json_document

SCHEMA = "faithbloom.editorial-paid-execution.v1"
_OWNER = ContextVar("editorial_paid_owner", default=None)
_ACTIVE: set[str] = set()
_GUARD = threading.Lock()


class EditorialCheckpointError(RuntimeError):
    """Keep a received response if its durable acknowledgement is unavailable."""
    def __init__(self, message, *, product_ref, execution_token, attempt_token, response):
        super().__init__(message)
        self.product_ref = product_ref
        self.execution_token = execution_token
        self.attempt_token = attempt_token
        self.response = deepcopy(response)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _path(reference):
    path = (storage.uri_to_path(reference) if storage.is_storage_uri(reference)
            else storage._normalize_storage_path(reference, allow_empty=False))
    logical = path.split("/", 2)[-1] if path.startswith("tenants/") else path
    if not logical.startswith("livros/") or not path.endswith(".json"):
        raise ValueError("A geração editorial exige a referência canônica de um livro salvo.")
    return path


def _execution(project):
    from editorial_products import _metadata
    meta = _metadata(project)
    execution = meta.get("execution")
    if execution is None:
        legacy = meta.get("draft") is not None
        return {"schema": SCHEMA, "revision": 0, "status": "legacy_needs_review" if legacy else "ready",
                "attempts": [], "legacy_review_required": legacy}
    if (not isinstance(execution, dict) or execution.get("schema") != SCHEMA
            or not isinstance(execution.get("revision"), int)
            or isinstance(execution.get("revision"), bool) or execution["revision"] < 0
            or not isinstance(execution.get("attempts"), list)):
        raise ValueError("O registro de tentativas editoriais precisa de recuperação.")
    status = execution.get("status")
    if status not in {"ready", "running", "needs_reconciliation", "save_failed", "completed", "legacy_needs_review"}:
        raise ValueError("O estado da execução editorial precisa de recuperação.")
    claim = execution.get("claim")
    if claim is not None and (not isinstance(claim, dict) or not isinstance(claim.get("token"), str)
            or not claim["token"] or not isinstance(claim.get("host"), str) or not claim["host"]
            or not isinstance(claim.get("pid"), int) or isinstance(claim.get("pid"), bool)
            or claim["pid"] <= 0 or claim.get("owner_active") is not True):
        raise ValueError("O responsável da execução editorial precisa de recuperação.")
    if (status == "running") != bool(claim):
        raise ValueError("O estado e o responsável editorial não correspondem.")
    tokens = set()
    for attempt in execution["attempts"]:
        if (not isinstance(attempt, dict) or not isinstance(attempt.get("token"), str)
                or not attempt["token"] or attempt["token"] in tokens
                or attempt.get("state") not in {"running", "uncertain", "raw", "applied", "reconciled_failed"}
                or not isinstance(attempt.get("index"), int) or isinstance(attempt.get("index"), bool)
                or attempt["index"] < 0):
            raise ValueError("Uma tentativa editorial persistida é inválida.")
        tokens.add(attempt["token"])
        for field in ("estimated_usd", "actual_usd"):
            value = attempt.get(field)
            if value is None and field == "actual_usd":
                continue
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(value) or value < 0):
                raise ValueError("O custo de uma tentativa editorial é inválido.")
        if attempt["state"] == "raw" and "response" not in attempt:
            raise ValueError("A tentativa recebida não possui resposta para recuperar.")
    unresolved = [a["state"] for a in execution["attempts"] if a["state"] in {"running", "uncertain", "raw"}]
    if (len(unresolved) > 1 or "running" in unresolved and status != "running"
            or "uncertain" in unresolved and status != "needs_reconciliation"
            or status == "needs_reconciliation" and "uncertain" not in unresolved
            or unresolved and status in {"ready", "completed", "legacy_needs_review"}):
        raise ValueError("As tentativas e o estado editorial precisam de recuperação.")
    return execution


def _validate(project, book_id):
    if not isinstance(project, dict) or project.get("book_id") != book_id:
        raise ValueError("A referência salva não corresponde a este produto editorial.")
    _execution(project)


def _update(reference, book_id, mutator):
    now = _now()
    def update(project):
        _validate(project, book_id)
        project["editorial_product"]["execution"] = deepcopy(_execution(project))
        revision = project["editorial_product"]["execution"]["revision"]
        updated = mutator(project)
        _validate(updated, book_id)
        updated["editorial_product"]["execution"].update(revision=revision + 1, updated_at=now)
        return updated
    return update_json_document(storage.BACKEND, _path(reference), update,
                                allow_legacy_pilot=True)


def _owner_alive(execution):
    claim = execution.get("claim") or {}
    if not claim:
        return False
    with _GUARD:
        if claim.get("token") in _ACTIVE:
            return True
    if claim.get("host") != socket.gethostname():
        return claim.get("owner_active") is not False
    pid = claim.get("pid")
    if pid == os.getpid():
        return False
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return claim.get("owner_active") is not False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _assert_owner(project, execution_token):
    execution = _execution(project)
    claim = execution.get("claim") or {}
    if claim.get("token") != execution_token or claim.get("owner_active") is not True:
        raise PermissionError("Esta execução foi atualizada em outra sessão. Reabra o projeto antes de continuar.")
    return execution


def _merge_generated(current, payload, baseline=None):
    """The generator owns content fields, not another writer's annotations."""
    from editorial_products import _spec_fingerprint
    if _spec_fingerprint(current) != _spec_fingerprint(payload):
        raise ValueError("Brief/fontes/plano mudou durante a geração. A resposta foi preservada para conferência.")
    saved = deepcopy(current)
    for key in ("draft", "units", "versions", "active_version", "active_governance", "approval", "status"):
        if key in payload["editorial_product"]:
            if baseline is not None:
                old = baseline["editorial_product"].get(key)
                if payload["editorial_product"][key] == old:
                    continue
                if current["editorial_product"].get(key) != old:
                    raise storage.StorageConflict(_execution(baseline)["revision"], _execution(current)["revision"])
            saved["editorial_product"][key] = deepcopy(payload["editorial_product"][key])
    for key in ("cenas_texto", "licao_final", "revisao_aprovada", "pacote_pronto"):
        if key in payload:
            if baseline is not None:
                if payload[key] == baseline.get(key):
                    continue
                if current.get(key) != baseline.get(key):
                    raise storage.StorageConflict(_execution(baseline)["revision"], _execution(current)["revision"])
            saved[key] = deepcopy(payload[key])
    return saved


@contextmanager
def _owner(reference, token):
    value = _OWNER.set((_path(reference), token))
    with _GUARD:
        _ACTIVE.add(token)
    try:
        yield
    finally:
        with _GUARD:
            _ACTIVE.discard(token)
        _OWNER.reset(value)


def save_existing_project(project, prepared):
    """Only this writer may replace an editorial product's current snapshot.

    Assets/schema preparation is performed by the caller before this callback.
    Other legacy book writers still require their own migration.
    """
    reference = project["storage_path"]
    incoming_revision = _execution(project)["revision"]
    owner = _OWNER.get()
    def save(current):
        execution = _execution(current)
        if execution.get("legacy_review_required"):
            raise PermissionError("Confira a interrupção do rascunho antigo antes de salvar ou retomar este produto.")
        active = bool((execution.get("claim") or {}).get("owner_active"))
        unresolved = any(a["state"] in {"running", "uncertain", "raw"} for a in execution["attempts"])
        owned = owner and owner[0] == _path(reference) and owner[1] == (execution.get("claim") or {}).get("token")
        if (active or unresolved) and not owned:
            raise PermissionError("A geração deste produto possui uma tentativa em andamento ou para conferência. Recupere-a antes de salvar outra cópia.")
        if execution["revision"] != incoming_revision:
            raise storage.StorageConflict(incoming_revision, execution["revision"])
        if owned:
            # commit() already stored the generated source atomically. This
            # secondary save acknowledges it; it cannot rewrite a human edit
            # that landed between the source checkpoint and this callback.
            for key in ("draft", "units", "versions", "active_version", "active_governance", "approval", "status"):
                if prepared["editorial_product"].get(key) != current["editorial_product"].get(key):
                    raise storage.StorageConflict(incoming_revision, execution["revision"])
            for key in ("cenas_texto", "licao_final", "revisao_aprovada", "pacote_pronto"):
                if prepared.get(key) != current.get(key):
                    raise storage.StorageConflict(incoming_revision, execution["revision"])
            saved = deepcopy(current)
        else:
            saved = deepcopy(prepared)
        saved["editorial_product"]["execution"] = deepcopy(execution)
        return saved
    saved = _update(reference, project["book_id"], save)
    project["editorial_product"]["execution"] = deepcopy(_execution(saved))
    return reference


def generation_status(reference):
    project = storage.BACKEND.get_json(_path(reference), None)
    if not isinstance(project, dict):
        raise ValueError("Produto editorial não encontrado.")
    execution = deepcopy(_execution(project))
    if "execution" not in project["editorial_product"] and project["editorial_product"].get("draft") is not None:
        execution["status"] = "legacy_needs_review"
    return execution


def execute(project, provider, checkpoint, body, *, new_version=False):
    """Run the existing generator under a canonical, per-product paid claim."""
    from editorial_products import _spec_fingerprint, save_product
    if not project.get("storage_path"):
        checkpoint(project)  # An initial persistence failure cannot spend credits.
        if not project.get("storage_path"):
            save_product(project)
    reference, book_id = project["storage_path"], project["book_id"]
    incoming = deepcopy(project)
    incoming_revision = _execution(incoming)["revision"]
    execution_token, now = uuid.uuid4().hex, _now()
    claim = {"token": execution_token, "host": socket.gethostname(), "pid": os.getpid(),
             "owner_active": True, "started_at": now}

    def acquire(current):
        execution = _execution(current)
        if execution.get("legacy_review_required"):
            raise PermissionError("Este rascunho antigo não registra a tentativa paga. Confirme o encerramento e confira o provedor antes de migrar a retomada.")
        if _spec_fingerprint(incoming) != _spec_fingerprint(current):
            raise ValueError("Brief/fontes/plano mudou. Salve e confira o projeto antes de gerar.")
        if (execution.get("claim") or {}).get("owner_active"):
            raise PermissionError("Este produto já possui uma execução ativa. Confirme seu encerramento antes de recuperar.")
        if any(a["state"] in {"running", "uncertain"} for a in execution["attempts"]):
            raise PermissionError("Uma chamada editorial pode ter consumido créditos. Confira a tentativa no provedor antes de retomar.")
        # A stale local draft never replaces received canonical units/responses.
        # A completed product can be edited only through its guarded save writer.
        if incoming_revision > execution["revision"]:
            raise storage.StorageConflict(incoming_revision, execution["revision"])
        if new_version and incoming_revision != execution["revision"]:
            raise storage.StorageConflict(incoming_revision, execution["revision"])
        execution.update(status="running", claim=deepcopy(claim))
        return current

    with _owner(reference, execution_token):
        # Do not catch/retry this mutation: a lost acknowledgement authorizes
        # zero provider calls, even if the claim actually landed.
        current = _update(reference, book_id, acquire)
        project.clear()
        project.update(deepcopy(current))
        known_source = deepcopy(project)

        def commit(updated):
            nonlocal known_source
            payload = deepcopy(updated)
            baseline = deepcopy(known_source)
            def checkpoint_source(current):
                execution = _assert_owner(current, execution_token)
                meta = payload["editorial_product"]
                draft = meta.get("draft") or {}
                version = draft.get("id") or meta.get("active_version")
                completed = len(draft.get("units", []) if draft else meta.get("units", []))
                for attempt in execution["attempts"]:
                    if (attempt["state"] == "raw" and attempt.get("draft_id") == version
                            and attempt["index"] < completed):
                        attempt["state"] = "applied"
                saved = _merge_generated(current, payload, baseline)
                saved["editorial_product"]["execution"] = deepcopy(execution)
                return saved
            saved = _update(reference, book_id, checkpoint_source)
            # Keep the generator's existing meta/draft references alive while
            # adopting unrelated current edits that this checkpoint preserved.
            for key in ("draft", "units", "versions", "active_version", "active_governance", "approval", "status"):
                if key in saved["editorial_product"]:
                    old = updated["editorial_product"].get(key)
                    new = deepcopy(saved["editorial_product"][key])
                    if key == "draft" and isinstance(old, dict) and isinstance(new, dict):
                        old.clear()
                        old.update(new)
                    else:
                        updated["editorial_product"][key] = new
            for key in ("cenas_texto", "licao_final", "revisao_aprovada", "pacote_pronto"):
                if key in saved:
                    updated[key] = deepcopy(saved[key])
            updated["editorial_product"]["execution"] = deepcopy(_execution(saved))
            known_source = deepcopy(updated)
            checkpoint(updated)  # Secondary run/library work stays outside CAS.

        def paid_provider(*, sistema, instrucao):
            from controle_geracao import estimar_custo
            draft = project["editorial_product"]["draft"]
            index, draft_id = len(draft["units"]), draft["id"]
            attempt_token, started = uuid.uuid4().hex, _now()
            estimate = estimar_custo("texto", 1)
            source_fingerprint = _spec_fingerprint(project)
            prompt_hash = sha256(json.dumps([sistema, instrucao], ensure_ascii=False).encode()).hexdigest()
            attempt = {"token": attempt_token, "index": index, "draft_id": draft_id,
                       "state": "running", "estimated_usd": estimate, "actual_usd": None,
                       "prompt_fingerprint": prompt_hash, "started_at": started}
            def reserve(current):
                execution = _assert_owner(current, execution_token)
                if _spec_fingerprint(current) != source_fingerprint:
                    raise ValueError("Brief/fontes/plano mudou antes da chamada ao provedor.")
                previous = next((a for a in reversed(execution["attempts"])
                                 if a.get("draft_id") == draft_id and a["index"] == index
                                 and a["state"] != "reconciled_failed"), None)
                if previous:
                    if previous["state"] != "raw" or previous.get("prompt_fingerprint") != prompt_hash:
                        raise PermissionError("Esta unidade já possui uma tentativa. Confira seu estado antes de gerar.")
                else:
                    execution["attempts"].append(deepcopy(attempt))
                return current
            saved = _update(reference, book_id, reserve)
            project["editorial_product"]["execution"] = deepcopy(_execution(saved))
            committed = next(a for a in reversed(_execution(saved)["attempts"])
                             if a.get("draft_id") == draft_id and a["index"] == index
                             and a["state"] != "reconciled_failed")
            if committed["state"] == "raw":
                return deepcopy(committed["response"])
            if committed["token"] != attempt_token or committed["state"] != "running":
                raise PermissionError("A tentativa paga não foi confirmada para esta execução.")
            response = provider(sistema=sistema, instrucao=instrucao)
            received = _now()
            def record_raw(current):
                execution = _assert_owner(current, execution_token)
                target = next((a for a in execution["attempts"] if a["token"] == attempt_token), None)
                if not target or target["state"] != "running":
                    raise PermissionError("A resposta pertence a uma tentativa já conferida. Nenhum resultado foi substituído.")
                target.update(state="raw", response=deepcopy(response), received_at=received)
                return current
            try:
                saved = _update(reference, book_id, record_raw)
            except Exception as exc:
                raise EditorialCheckpointError(
                    "A resposta foi recebida, mas a confirmação de salvamento falhou. Preserve-a e confira a tentativa; não gere novamente.",
                    product_ref=reference, execution_token=execution_token,
                    attempt_token=attempt_token, response=response) from exc
            project["editorial_product"]["execution"] = deepcopy(_execution(saved))
            return response

        active_draft = (project["editorial_product"].get("draft") or {}).get("id")
        paid_provider.received_unit_indexes = frozenset(
            a["index"] for a in _execution(project)["attempts"]
            if a["state"] == "raw" and a.get("draft_id") == active_draft)

        try:
            result = body(paid_provider, commit)
            def complete(current):
                execution = _assert_owner(current, execution_token)
                if any(a["state"] in {"running", "uncertain", "raw"} for a in execution["attempts"]):
                    raise PermissionError("Uma tentativa ainda precisa ser salva ou conferida.")
                execution.update(status="completed")
                execution["last_claim"] = execution.pop("claim")
                execution["last_claim"]["owner_active"] = False
                return current
            saved = _update(reference, book_id, complete)
            result.clear()
            result.update(deepcopy(saved))
            return result
        except Exception:
            def fail(current):
                execution = _execution(current)
                if (execution.get("claim") or {}).get("token") != execution_token:
                    return current
                if not execution["claim"].get("owner_active"):
                    return current
                for attempt in execution["attempts"]:
                    if attempt["state"] == "running":
                        attempt["state"] = "uncertain"
                execution["last_claim"] = execution.pop("claim")
                execution["last_claim"]["owner_active"] = False
                execution["status"] = ("needs_reconciliation" if any(a["state"] == "uncertain" for a in execution["attempts"])
                                       else "save_failed")
                return current
            try:
                saved = _update(reference, book_id, fail)
                project["editorial_product"]["execution"] = deepcopy(_execution(saved))
            except Exception:
                # Durable claim/raw state is retained; no fallback write/retry.
                pass
            raise


def recover_generation(reference, *, execution_token, confirmed=False, shutdown_note=""):
    """Stop a dead owner's claim; provider reconciliation is a separate action."""
    if confirmed is not True or not execution_token:
        raise PermissionError("Confirme a interrupção e informe a execução exata.")
    current = storage.BACKEND.get_json(_path(reference), None)
    execution = _execution(current)
    claim = execution.get("claim") or {}
    if claim.get("token") != execution_token or claim.get("owner_active") is not True:
        raise PermissionError("Esta execução não corresponde ao responsável atual.")
    alive = _owner_alive(execution)
    with _GUARD:
        locally_held = execution_token in _ACTIVE
    if alive and (claim.get("host") == socket.gethostname() or locally_held):
        raise PermissionError("O responsável local ainda está ativo. Aguarde seu encerramento.")
    note = str(shutdown_note or "").strip()
    if alive and not note:
        raise PermissionError("Registre a evidência de encerramento do responsável no outro host.")
    revision, now = execution["revision"], _now()
    def recover(product):
        latest = _execution(product)
        if latest["revision"] != revision:
            raise storage.StorageConflict(revision, latest["revision"])
        if (latest.get("claim") or {}).get("token") != execution_token:
            raise PermissionError("O responsável mudou; reabra o projeto.")
        for attempt in latest["attempts"]:
            if attempt["state"] == "running":
                attempt["state"] = "uncertain"
        latest["last_claim"] = latest.pop("claim")
        latest["last_claim"]["owner_active"] = False
        latest["status"] = ("needs_reconciliation" if any(a["state"] == "uncertain" for a in latest["attempts"])
                            else "save_failed")
        latest.setdefault("shutdown_attestations", []).append({"execution_token": execution_token,
            "host": claim.get("host"), "pid": claim.get("pid"), "note": note[:1000], "at": now})
        return product
    return _update(reference, current["book_id"], recover)


def adopt_legacy_interruption(reference, *, confirmed=False, shutdown_note=""):
    """A legacy draft has no owner/receipt; require shutdown evidence first.

    This records an uncertain attempt, never evidence that a provider was not
    called. A separate reconciliation is required before buying that unit.
    """
    note = str(shutdown_note or "").strip()
    if confirmed is not True or not note:
        raise PermissionError("Confirme o encerramento das execuções antigas e registre a evidência antes de migrar a retomada.")
    current = storage.BACKEND.get_json(_path(reference), None)
    execution = _execution(current)
    if not execution.get("legacy_review_required"):
        raise PermissionError("Este produto não possui uma interrupção legada para migrar.")
    from editorial_products import build_generation_prompt
    from controle_geracao import estimar_custo
    meta = current["editorial_product"]
    draft = meta["draft"]
    if (not isinstance(draft, dict) or not isinstance(draft.get("id"), str) or not draft["id"]
            or not isinstance(draft.get("units"), list) or len(draft["units"]) > len(meta["unit_plan"])):
        raise ValueError("O rascunho antigo está inválido; preserve o original e repare sua estrutura antes de migrar a retomada.")
    index, token, now = len(draft["units"]), uuid.uuid4().hex, _now()
    attempt = None
    if index < len(meta["unit_plan"]):
        system, instruction = build_generation_prompt(current, meta["unit_plan"][index])
        attempt = {"token": token, "index": index, "draft_id": draft["id"], "state": "uncertain",
                   "estimated_usd": estimar_custo("texto", 1), "actual_usd": None,
                   "prompt_fingerprint": sha256(json.dumps([system, instruction], ensure_ascii=False).encode()).hexdigest(),
                   "started_at": now, "legacy": True}
    def adopt(product):
        latest = _execution(product)
        if not latest.get("legacy_review_required") or latest["revision"] != execution["revision"]:
            raise storage.StorageConflict(execution["revision"], latest["revision"])
        latest["legacy_review_required"] = False
        latest["status"] = "needs_reconciliation" if attempt else "save_failed"
        if attempt:
            latest["attempts"].append(deepcopy(attempt))
        latest.setdefault("shutdown_attestations", []).append({"legacy": True, "note": note[:1000], "at": now})
        return product
    return _update(reference, current["book_id"], adopt)


def reconcile_attempt(reference, *, attempt_token, provider_outcome, note, confirmed=False,
                      recovered_response=None, actual_usd=None):
    """Record human provider evidence; this function never executes a provider."""
    if confirmed is not True or not attempt_token or not str(note or "").strip():
        raise PermissionError("Confirme o resultado no provedor e registre a justificativa da conferência.")
    if provider_outcome not in {"not_sent", "failed", "succeeded"}:
        raise ValueError("Resultado da conferência inválido.")
    if actual_usd is not None and (not isinstance(actual_usd, (int, float)) or isinstance(actual_usd, bool)
                                   or not math.isfinite(actual_usd) or actual_usd < 0):
        raise ValueError("Informe um custo real finito e não negativo.")
    current = storage.BACKEND.get_json(_path(reference), None)
    execution = _execution(current)
    if (execution.get("claim") or {}).get("owner_active") or _owner_alive(execution):
        raise PermissionError("A execução ainda está ativa. Confirme seu encerramento antes da conferência.")
    target = next((a for a in execution["attempts"] if a["token"] == attempt_token), None)
    if not target or target["state"] not in {"uncertain", "raw"}:
        raise PermissionError("Esta tentativa não está aguardando conferência.")
    response = None
    if provider_outcome == "succeeded":
        from editorial_products import validate_unit
        response = deepcopy(recovered_response if recovered_response is not None else target.get("response"))
        if not isinstance(response, dict):
            raise ValueError("Recupere a resposta estruturada antes de concluir a conferência.")
        meta = current["editorial_product"]
        validate_unit(response.get("unit", response), meta["unit_plan"][target["index"]], meta["spec"])
        storage._json_bytes(response)
    expected_revision, previous_state, now = execution["revision"], target["state"], _now()
    evidence = {"attempt_token": attempt_token, "provider_outcome": provider_outcome,
                "note": str(note).strip()[:1000], "actual_usd": actual_usd, "at": now}
    def reconcile(product):
        latest = _execution(product)
        if latest["revision"] != expected_revision:
            raise storage.StorageConflict(expected_revision, latest["revision"])
        attempt = next((a for a in latest["attempts"] if a["token"] == attempt_token), None)
        if not attempt or attempt["state"] != previous_state:
            raise PermissionError("A tentativa mudou durante a conferência; recarregue o projeto.")
        attempt.update(state="raw" if provider_outcome == "succeeded" else "reconciled_failed", actual_usd=actual_usd)
        if provider_outcome == "succeeded":
            attempt["response"] = deepcopy(response)
        attempt.setdefault("reconciliations", []).append(deepcopy(evidence))
        latest["status"] = "save_failed"
        return product
    return _update(reference, current["book_id"], reconcile)

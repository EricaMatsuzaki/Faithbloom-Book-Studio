"""Updates for business records without hiding the pilot's storage limits.

Local and RPC backends use their strict atomic update API. The author's legacy
Supabase pilot can explicitly serialize a migrated caller on one shared host.
This compatibility path does not provide a transaction across hosts or records,
does not activate RPC, and never catches a failed atomic update to downgrade it.
Callbacks must be pure: no provider calls, uploads, or other document writes.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any, Callable

from saas_access import access_mode
import storage_backend as storage


_LEGACY_CONCURRENCY = "read_modify_write_without_cross_worker_CAS"


def json_update_mode(backend, *, allow_legacy_pilot: bool = False) -> str:
    legacy = (getattr(backend, "name", None) == "supabase"
              and getattr(backend, "json_concurrency", None) == _LEGACY_CONCURRENCY)
    if legacy and allow_legacy_pilot is True and access_mode() == "pilot":
        return "pilot_same_host_file_lock"
    return "strict_backend_atomic_update"


def update_json_document(
    backend,
    path: str,
    mutator: Callable[[Any], Any],
    default: Any = None,
    *,
    allow_legacy_pilot: bool = False,
    max_attempts: int = 5,
) -> Any:
    """Return the committed document; transport uncertainty is never retried here.

    ``allow_legacy_pilot`` is a deliberate opt-in by a migrated pilot consumer.
    Its file lock coordinates processes sharing the same cache directory only.
    Unknown backends and customer mode always require the backend's atomic API.
    """
    if not callable(mutator):
        raise TypeError("A atualização precisa de uma função de transformação.")
    if (not isinstance(max_attempts, int) or isinstance(max_attempts, bool)
            or not 1 <= max_attempts <= 20):
        raise ValueError("Número de tentativas deve estar entre 1 e 20.")
    if json_update_mode(backend, allow_legacy_pilot=allow_legacy_pilot) != "pilot_same_host_file_lock":
        update = getattr(backend, "update_json", None)
        if not callable(update):
            raise storage.StorageConcurrencyUnsupported("Este backend exige uma API de atualização atômica.")
        return update(path, mutator, default, max_attempts=max_attempts)

    clean = storage._normalize_storage_path(path, allow_empty=False)
    # Colliding namespaces only serialize unrelated pilots; they never grant
    # access or mix data. No credential is used in the lock identity or file.
    scope = str(getattr(backend, "bucket", "")) + ":" + clean
    lock_id = sha256(scope.encode("utf-8")).hexdigest() + ".json"
    locks = storage.LocalStorageBackend(str(storage.CACHE_DIR / "pilot_json_updates"))
    with locks._locked(lock_id):
        current = backend.get_json(clean, deepcopy(default))
        value = mutator(deepcopy(current))
        storage._json_bytes(value)  # Reject invalid/nonfinite JSON before writing.
        backend.put_json(clean, value)
        return deepcopy(value)

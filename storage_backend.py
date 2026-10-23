"""FaithBloom 2.0 — camada de armazenamento persistente.

Modos suportados:
- local (padrão para desenvolvimento): grava em .faithbloom_data/
- supabase: grava em um bucket privado do Supabase Storage via REST.

No Streamlit Cloud, use Supabase para não perder livros/imagens ao reiniciar.
Secrets esperados no modo Supabase:
    FAITHBLOOM_STORAGE_MODE = "supabase"
    SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
    SUPABASE_SECRET_KEY = "sb_secret_..."  # recomendado; guardar SOMENTE em Secrets
    # Compatibilidade temporária com projetos antigos:
    # SUPABASE_SERVICE_ROLE_KEY = "..."
    FAITHBLOOM_SUPABASE_BUCKET = "faithbloom"  # opcional
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import uuid
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, RLock, local
from typing import Any, Callable
from urllib.parse import quote, urlsplit

import requests

from saas_access import AccessDenied, access_mode, current_actor, require_action


class StorageError(RuntimeError):
    pass


class StorageNotFound(StorageError, FileNotFoundError):
    """Only an explicitly absent object permits default/empty index creation."""


class StorageUnavailable(StorageError):
    """Transport, permission or backend error; never equivalent to absence."""


class StorageCorrupt(StorageError):
    """Existing data cannot be decoded; original must remain untouched."""


class StorageConflict(StorageError):
    """A stale revision was rejected before replacing a newer document."""

    def __init__(self, expected_revision=None, current_revision=None):
        super().__init__("O registro foi atualizado em outra sessão. Recarregue e reaplique a alteração.")
        self.expected_revision = expected_revision
        self.current_revision = current_revision


class StorageConcurrencyUnsupported(StorageError):
    """No cross-worker atomic update is available; never silently downgrade."""


class StorageMigrationRequired(StorageError):
    """An existing legacy JSON must be imported before enabling RPC storage."""


@dataclass(frozen=True)
class JsonSnapshot:
    value: Any
    revision: str | int | None
    exists: bool


def _decode_json(data: bytes, default: Any = None) -> Any:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StorageCorrupt("JSON armazenado inválido; o registro original foi preservado.") from None
    if isinstance(default, (dict, list)) and not isinstance(value, type(default)):
        raise StorageCorrupt("Estrutura JSON armazenada incompatível; o registro original foi preservado.")
    return value


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


class StorageBackend:
    name = "base"
    json_concurrency = "unsupported"

    def put_bytes(self, path: str, data: bytes, content_type: str | None = None) -> str:
        raise NotImplementedError

    def get_bytes(self, path: str) -> bytes:
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        try:
            self.get_bytes(path)
            return True
        except (StorageNotFound, FileNotFoundError):
            return False

    def list(self, prefix: str = "") -> list[str]:
        raise NotImplementedError

    def delete(self, path: str) -> None:
        raise NotImplementedError

    def put_json(self, path: str, value: Any) -> str:
        return self.put_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"), "application/json")

    def get_json(self, path: str, default: Any = None) -> Any:
        try:
            return _decode_json(self.get_bytes(path), default)
        except (StorageNotFound, FileNotFoundError):
            return default

    def get_json_snapshot(self, path: str, default: Any = None) -> JsonSnapshot:
        raise StorageConcurrencyUnsupported("Este backend não oferece revisões JSON atômicas.")

    def compare_and_swap_json(self, path: str, expected_revision, value: Any) -> JsonSnapshot:
        raise StorageConcurrencyUnsupported("Este backend não oferece atualização JSON atômica entre processos.")

    def update_json(self, path: str, mutator: Callable[[Any], Any], default: Any = None, *, max_attempts: int = 5) -> Any:
        """Atomic read/modify/write. The pure callback may run again on conflict.

        Do not perform paid calls, publish files, or mutate caller state inside
        the callback. Only CAS conflicts are retried; transport errors are not.
        """
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or not 1 <= max_attempts <= 20:
            raise ValueError("Número de tentativas deve estar entre 1 e 20.")
        for attempt in range(max_attempts):
            snapshot = self.get_json_snapshot(path, default)
            value = mutator(deepcopy(snapshot.value))
            try:
                return self.compare_and_swap_json(path, snapshot.revision, value).value
            except StorageConflict:
                if attempt + 1 == max_attempts:
                    raise


_LOCAL_LOCKS: dict[str, RLock] = {}
_LOCAL_LOCKS_GUARD = Lock()
_LOCAL_HELD_LOCKS = local()


class LocalStorageBackend(StorageBackend):
    name = "local"
    json_concurrency = "local_file_lock_and_content_CAS"

    def __init__(self, root: str | None = None):
        self.root = Path(root or os.environ.get("FAITHBLOOM_LOCAL_DATA_DIR", ".faithbloom_data")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, path: str) -> Path:
        clean = _normalize_storage_path(path)
        if clean.split("/", 1)[0] == ".faithbloom_locks":
            raise StorageError("Diretório interno de controle não é um objeto de armazenamento.")
        p = (self.root / clean).resolve()
        if self.root not in p.parents and p != self.root:
            raise StorageError("Caminho inválido no armazenamento local")
        return p

    @contextmanager
    def _locked(self, path: str):
        """Thread lock plus flock shared by separate workers on the same disk."""
        target = self._p(path)
        lock_key = str(target)
        held = getattr(_LOCAL_HELD_LOCKS, "paths", set())
        if lock_key in held:
            raise StorageError("Uma atualização JSON não pode iniciar outra gravação no mesmo registro.")
        with _LOCAL_LOCKS_GUARD:
            thread_lock = _LOCAL_LOCKS.setdefault(lock_key, RLock())
        try:
            import fcntl
        except ImportError:
            raise StorageConcurrencyUnsupported("Atualizações atômicas locais exigem suporte a file lock.") from None
        lock_dir = self.root / ".faithbloom_locks"
        if lock_dir.is_symlink():
            raise StorageError("Diretório de controle local inválido.")
        lock_dir.mkdir(exist_ok=True)
        lock_path = lock_dir / (hashlib.sha256(lock_key.encode()).hexdigest() + ".lock")
        with thread_lock:
            flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(lock_path, flags, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                _LOCAL_HELD_LOCKS.paths = held | {lock_key}
                yield
            finally:
                _LOCAL_HELD_LOCKS.paths = held
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def put_bytes(self, path: str, data: bytes, content_type: str | None = None) -> str:
        with self._locked(path):
            return self._write_bytes(path, data)

    def _write_bytes(self, path: str, data: bytes) -> str:
        p = self._p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".{p.name}.tmp-{uuid.uuid4().hex}")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, p)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        return path

    def get_json_snapshot(self, path: str, default: Any = None) -> JsonSnapshot:
        try:
            data = self.get_bytes(path)
        except StorageNotFound:
            return JsonSnapshot(deepcopy(default), None, False)
        return JsonSnapshot(_decode_json(data, default), hashlib.sha256(data).hexdigest(), True)

    def compare_and_swap_json(self, path: str, expected_revision, value: Any) -> JsonSnapshot:
        data = _json_bytes(value)
        with self._locked(path):
            current = self.get_json_snapshot(path)
            if current.revision != expected_revision:
                raise StorageConflict(expected_revision, current.revision)
            self._write_bytes(path, data)
        return JsonSnapshot(deepcopy(value), hashlib.sha256(data).hexdigest(), True)

    def update_json(self, path: str, mutator: Callable[[Any], Any], default: Any = None, *, max_attempts: int = 5) -> Any:
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or not 1 <= max_attempts <= 20:
            raise ValueError("Número de tentativas deve estar entre 1 e 20.")
        with self._locked(path):
            snapshot = self.get_json_snapshot(path, default)
            value = mutator(deepcopy(snapshot.value))
            self._write_bytes(path, _json_bytes(value))
            return deepcopy(value)

    def get_bytes(self, path: str) -> bytes:
        try:
            return self._p(path).read_bytes()
        except FileNotFoundError:
            raise StorageNotFound("Objeto não encontrado no armazenamento.") from None
        except OSError:
            raise StorageUnavailable("Não foi possível ler o armazenamento local.") from None

    def list(self, prefix: str = "") -> list[str]:
        base = self._p(prefix)
        if base.is_file():
            return [prefix.strip("/")]
        if not base.exists():
            return []
        items = []
        for p in base.rglob("*"):
            if p.is_file():
                if p.relative_to(self.root).parts[0] == ".faithbloom_locks":
                    continue
                resolved = p.resolve()
                if self.root not in resolved.parents:
                    raise StorageError("Link fora do armazenamento local não permitido.")
                items.append(str(p.relative_to(self.root)).replace(os.sep, "/"))
        return sorted(items)

    def delete(self, path: str) -> None:
        with self._locked(path):
            p = self._p(path)
            if p.exists() and p.is_file():
                p.unlink()


def _normalize_storage_path(value: str, *, allow_empty: bool = True) -> str:
    """Normaliza prefixos/objetos sem permitir traversal ou segmentos inválidos."""
    raw = str(value or "").replace("\\", "/").strip()
    raw = re.sub(r"/+", "/", raw).strip("/")
    if not raw:
        if allow_empty:
            return ""
        raise StorageError("Caminho vazio no Supabase Storage.")
    parts = []
    for part in raw.split("/"):
        clean = part.strip()
        if not clean or clean in {".", ".."}:
            if clean in {".", ".."}:
                raise StorageError("Caminho inválido no Supabase Storage.")
            continue
        if any(ord(ch) < 32 for ch in clean):
            raise StorageError("Caminho contém caracteres de controle inválidos.")
        parts.append(clean)
    return "/".join(parts)


def _normalize_supabase_url(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        return raw
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise StorageError("SUPABASE_URL inválida. Use a Project URL, por exemplo https://xxxx.supabase.co")
    # O secret deve receber a Project URL, não uma rota /storage/v1 já anexada.
    return f"{parsed.scheme}://{parsed.netloc}"


class SupabaseStorageBackend(StorageBackend):
    name = "supabase"

    def __init__(self, url: str, service_key: str, bucket: str = "faithbloom", *, json_mode: str = "storage"):
        self.url = _normalize_supabase_url(url)
        self.key = str(service_key or "").strip()
        self.bucket = _normalize_storage_path(str(bucket or "faithbloom"), allow_empty=False)
        if "/" in self.bucket:
            raise StorageError("FAITHBLOOM_SUPABASE_BUCKET deve conter somente o nome do bucket, sem pastas ou URL.")
        self.key_kind = "secret" if self.key.startswith("sb_secret_") else "legacy_service_role"
        # sb_secret_* usa apikey. Authorization Bearer fica somente para service_role JWT legado.
        self.headers = {"apikey": self.key}
        if self.key_kind == "legacy_service_role":
            self.headers["Authorization"] = f"Bearer {self.key}"
        self.json_mode = str(json_mode).strip().lower()
        if self.json_mode not in {"storage", "rpc_cas"}:
            raise StorageError("Modo JSON do Supabase inválido. Use storage ou rpc_cas.")
        self.json_concurrency = "postgres_RPC_CAS" if self.json_mode == "rpc_cas" else "read_modify_write_without_cross_worker_CAS"

    def _rpc(self, operation: str, **payload) -> dict:
        if self.json_mode != "rpc_cas":
            raise StorageConcurrencyUnsupported("O Supabase Storage legado não oferece CAS. A migração RPC precisa ser aplicada e habilitada explicitamente.")
        response = self._request(requests.post,
            f"{self.url}/rest/v1/rpc/faithbloom_json_{operation}",
            headers={**self.headers, "Content-Type": "application/json"},
            json={"p_bucket": self.bucket, **payload}, timeout=60)
        if response.status_code != 200:
            # In particular, an absent RPC/schema is never retried as an upload.
            raise StorageUnavailable(f"Atualização JSON transacional indisponível (HTTP {response.status_code}). Nenhum fallback de gravação foi realizado.")
        try:
            result = response.json()
        except ValueError:
            raise StorageCorrupt("Resposta JSON transacional inválida.") from None
        if not isinstance(result, dict):
            raise StorageCorrupt("Estrutura de resposta JSON transacional inválida.")
        return result

    def _json_path(self, path: str) -> str:
        clean = _normalize_storage_path(path, allow_empty=False)
        if not clean.lower().endswith(".json"):
            raise StorageError("A API JSON transacional exige um objeto .json.")
        return clean

    @staticmethod
    def _revision(result: dict) -> int:
        revision = result.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise StorageCorrupt("Revisão JSON transacional inválida.")
        return revision

    def get_json_snapshot(self, path: str, default: Any = None) -> JsonSnapshot:
        clean = self._json_path(path)
        result = self._rpc("get", p_path=clean)
        revision = self._revision(result)
        found = result.get("found")
        if not isinstance(found, bool) or (found and revision == 0):
            raise StorageCorrupt("Estado JSON transacional inválido.")
        if not found:
            if revision == 0:
                # Prevent a newly-enabled empty table from replacing an old
                # private Storage index with an apparently empty catalog.
                try:
                    self._get_storage_bytes(clean)
                except StorageNotFound:
                    pass
                else:
                    raise StorageMigrationRequired("JSON legado ainda não importado. A ativação transacional foi interrompida sem substituir o original.")
            return JsonSnapshot(deepcopy(default), revision, False)
        if "value" not in result:
            raise StorageCorrupt("Conteúdo JSON transacional ausente.")
        value = result["value"]
        if isinstance(default, (dict, list)) and not isinstance(value, type(default)):
            raise StorageCorrupt("Estrutura JSON armazenada incompatível; o registro original foi preservado.")
        return JsonSnapshot(value, revision, True)

    def compare_and_swap_json(self, path: str, expected_revision, value: Any) -> JsonSnapshot:
        clean = self._json_path(path)
        if not isinstance(expected_revision, int) or isinstance(expected_revision, bool) or expected_revision < 0:
            raise StorageError("Revisão esperada inválida para CAS Supabase.")
        _json_bytes(value)  # reject NaN/non-JSON before any outbound call
        if expected_revision == 0:
            current = self.get_json_snapshot(clean)
            if current.revision != 0:
                raise StorageConflict(expected_revision, current.revision)
        result = self._rpc("cas", p_path=clean, p_expected_revision=expected_revision, p_value=value)
        revision = self._revision(result)
        if result.get("written") is False:
            raise StorageConflict(expected_revision, revision)
        if result.get("written") is not True or revision != expected_revision + 1:
            raise StorageCorrupt("Confirmação de gravação JSON transacional inválida.")
        return JsonSnapshot(deepcopy(value), revision, True)

    def get_json(self, path: str, default: Any = None) -> Any:
        if self.json_mode == "rpc_cas":
            return self.get_json_snapshot(path, default).value
        return super().get_json(path, default)

    def put_json(self, path: str, value: Any) -> str:
        if self.json_mode == "rpc_cas":
            # Replacement is atomic, but stale read/modify/write callers still
            # need update_json or a revision supplied to CAS for lost-update safety.
            snapshot = self.get_json_snapshot(path)
            self.compare_and_swap_json(path, snapshot.revision, value)
            return _normalize_storage_path(path, allow_empty=False)
        return super().put_json(path, value)

    def _object_url(self, path: str) -> str:
        clean = _normalize_storage_path(path, allow_empty=False)
        return f"{self.url}/storage/v1/object/{quote(self.bucket, safe='')}/{quote(clean, safe='/')}"

    def _list_endpoint(self) -> str:
        return f"{self.url}/storage/v1/object/list/{quote(self.bucket, safe='')}"

    @staticmethod
    def _request(method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except requests.RequestException:
            # The raw exception may include a URL, headers or credentials.
            raise StorageUnavailable("Falha de comunicação com o armazenamento.") from None

    def put_bytes(self, path: str, data: bytes, content_type: str | None = None) -> str:
        clean = _normalize_storage_path(path, allow_empty=False)
        if self.json_mode == "rpc_cas" and clean.lower().endswith(".json"):
            return self.put_json(clean, _decode_json(data))
        headers = {**self.headers, "x-upsert": "true", "Content-Type": content_type or "application/octet-stream"}
        r = self._request(requests.post, self._object_url(clean), headers=headers, data=data, timeout=120)
        if r.status_code not in (200, 201):
            raise StorageUnavailable(f"Supabase upload falhou (HTTP {r.status_code}).")
        return clean

    def get_bytes(self, path: str) -> bytes:
        clean = _normalize_storage_path(path, allow_empty=False)
        if self.json_mode == "rpc_cas" and clean.lower().endswith(".json"):
            snapshot = self.get_json_snapshot(clean)
            if not snapshot.exists:
                raise StorageNotFound("Objeto não encontrado no armazenamento.")
            return _json_bytes(snapshot.value)
        return self._get_storage_bytes(clean)

    def _get_storage_bytes(self, path: str) -> bytes:
        r = self._request(requests.get, self._object_url(path), headers=self.headers, timeout=120)
        missing = r.status_code == 404
        if r.status_code == 400:
            # Older Supabase gateways used HTTP 400 with their explicit object
            # not-found code. Never use message substring matching, and never
            # interpret a 403/timeout/server error as absence.
            try:
                detail = r.json()
                missing = isinstance(detail, dict) and str(detail.get("statusCode")) == "404" and detail.get("error") in {"not_found", "NoSuchKey"}
            except (ValueError, AttributeError):
                missing = False
        if missing:
            raise StorageNotFound("Objeto não encontrado no armazenamento.")
        if r.status_code != 200:
            raise StorageUnavailable(f"Supabase download falhou (HTTP {r.status_code}).")
        return r.content

    def _list_level(self, prefix: str, offset: int = 0) -> list[dict]:
        current = _normalize_storage_path(prefix, allow_empty=True)
        payload = {
            "prefix": current,
            "limit": 1000,
            "offset": offset,
            "sortBy": {"column": "name", "order": "asc"},
        }
        r = self._request(requests.post,
            self._list_endpoint(),
            headers={**self.headers, "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if r.status_code != 200:
            raise StorageUnavailable(f"Supabase list falhou (HTTP {r.status_code}).")
        try:
            data = r.json()
        except ValueError:
            raise StorageCorrupt("Resposta inválida ao listar o armazenamento.") from None
        if not isinstance(data, list) or any(not isinstance(x, dict) for x in data):
            raise StorageCorrupt("Formato inválido ao listar o armazenamento.")
        return data

    @staticmethod
    def _join_list_item(current: str, name: str) -> str:
        """Aceita tanto nomes relativos quanto nomes completos retornados pelo Storage."""
        current = _normalize_storage_path(current, allow_empty=True)
        name = _normalize_storage_path(name, allow_empty=True)
        if not name:
            return current
        if current and (name == current or name.startswith(current + "/")):
            return name
        return _normalize_storage_path(f"{current}/{name}" if current else name, allow_empty=True)

    def list(self, prefix: str = "") -> list[str]:
        """Lista recursivamente sem deixar um prefixo malformado derrubar o app.

        O Storage passou a devolver formas diferentes de entradas de pasta entre
        versões. Por isso usamos id/metadata para distinguir diretórios, evitamos
        loops e aceitamos nomes relativos ou já prefixados.
        """
        start = _normalize_storage_path(prefix, allow_empty=True)
        out: list[str] = []
        queue = [start]
        visited: set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            # A partial listing must never become input for a catalog rewrite.
            items = []
            offset = 0
            while True:
                page = self._list_level(current, offset)
                items.extend(page)
                if len(page) < 1000:
                    break
                offset += len(page)
            for item in items:
                raw_name = str(item.get("name") or "").strip()
                if not raw_name:
                    raise StorageCorrupt("Objeto sem nome na listagem do armazenamento.")
                try:
                    full = self._join_list_item(current, raw_name)
                except StorageError:
                    raise StorageCorrupt("Nome de objeto inválido na listagem do armazenamento.") from None
                if not full or full == current:
                    continue
                is_folder = item.get("id") in {None, ""} and item.get("metadata") is None
                if is_folder:
                    if full not in visited:
                        queue.append(full)
                else:
                    out.append(full)
        if self.json_mode == "rpc_cas":
            rows = self._list_rpc_json(start)
            # Media stays in Storage; JSONs have one canonical source in SQL.
            media = [path for path in out if not path.lower().endswith(".json")]
            for path in out:
                if path.lower().endswith(".json") and path not in rows:
                    snapshot = self.get_json_snapshot(path)
                    rows[path] = not snapshot.exists
            out = media + [path for path, deleted in rows.items() if not deleted]
        return sorted(set(out))

    def _list_rpc_json(self, prefix: str) -> dict[str, bool]:
        rows: dict[str, bool] = {}
        offset = 0
        while True:
            result = self._rpc("list", p_prefix=prefix, p_offset=offset)
            items = result.get("items")
            if not isinstance(items, list) or not isinstance(result.get("has_more"), bool):
                raise StorageCorrupt("Listagem JSON transacional inválida.")
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("deleted"), bool):
                    raise StorageCorrupt("Registro JSON transacional inválido.")
                path = self._json_path(item.get("path", ""))
                if prefix and path != prefix and not path.startswith(prefix + "/"):
                    raise StorageCorrupt("Listagem JSON fora do prefixo solicitado.")
                if path in rows:
                    raise StorageCorrupt("Paginação JSON transacional repetiu registros; a listagem foi interrompida.")
                rows[path] = item["deleted"]
            if not result["has_more"]:
                return rows
            if not items:
                raise StorageCorrupt("Paginação JSON transacional sem progresso.")
            offset += len(items)

    def delete(self, path: str) -> None:
        clean = _normalize_storage_path(path, allow_empty=False)
        if self.json_mode == "rpc_cas" and clean.lower().endswith(".json"):
            snapshot = self.get_json_snapshot(clean)
            if not snapshot.exists:
                return
            result = self._rpc("delete", p_path=clean, p_expected_revision=snapshot.revision)
            revision = self._revision(result)
            if result.get("written") is False:
                raise StorageConflict(snapshot.revision, revision)
            if result.get("written") is not True or revision != snapshot.revision + 1:
                raise StorageCorrupt("Confirmação de exclusão JSON transacional inválida.")
            return
        endpoint = f"{self.url}/storage/v1/object/{quote(self.bucket, safe='')}"
        r = self._request(requests.delete,
            endpoint,
            headers={**self.headers, "Content-Type": "application/json"},
            json={"prefixes": [clean]},
            timeout=60,
        )
        if r.status_code not in (200, 204):
            raise StorageUnavailable(f"Supabase delete falhou (HTTP {r.status_code}).")


def get_backend() -> StorageBackend:
    mode = os.environ.get("FAITHBLOOM_STORAGE_MODE", "auto").strip().lower()
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if mode == "supabase" or (mode == "auto" and url and key):
        if not (url and key):
            raise StorageError(
                "Modo Supabase escolhido, mas SUPABASE_URL e SUPABASE_SECRET_KEY "
                "(ou SUPABASE_SERVICE_ROLE_KEY legado) não foram definidos."
            )
        return SupabaseStorageBackend(
            url,
            key,
            os.environ.get("FAITHBLOOM_SUPABASE_BUCKET", "faithbloom"),
            json_mode=os.environ.get("FAITHBLOOM_SUPABASE_JSON_MODE", "storage"),
        )
    return LocalStorageBackend()


def _tenant_path(path: str, *, action: str, allow_empty: bool = False) -> str:
    """Resolve a logical path or validate an already-qualified own-tenant path."""
    clean = _normalize_storage_path(path, allow_empty=allow_empty)
    if access_mode() == "pilot":
        return clean
    actor = require_action(action)
    assert actor is not None
    prefix = f"tenants/{actor.tenant_id}"
    if clean == "tenants" or clean.startswith("tenants/"):
        parts = clean.split("/", 2)
        resource_id = parts[1] if len(parts) > 1 else ""
        require_action(action, resource_tenant_id=resource_id)
        if clean == prefix:
            if allow_empty:
                return prefix
            raise AccessDenied("O namespace não é um objeto de armazenamento.")
        if not clean.startswith(prefix + "/"):
            raise AccessDenied("Acesso não autorizado a este recurso.")
        return clean
    return f"{prefix}/{clean}" if clean else prefix


class TenantStorageBackend(StorageBackend):
    """Stable imported object; authorizes each call using the current request actor.

    No authenticated customer can list or mutate the author's root namespace.
    Returned listings are logical paths so existing catalog code keeps working;
    durable URIs carry the tenant qualifier and cannot be replayed by another user.
    The underlying private backend is not a customer-facing capability.
    """
    def __init__(self, backend: StorageBackend):
        self._backend = backend

    @property
    def name(self):
        return self._backend.name

    @property
    def bucket(self):
        return getattr(self._backend, "bucket", "local")

    @property
    def key_kind(self):
        return getattr(self._backend, "key_kind", "local")

    @property
    def json_concurrency(self):
        return self._backend.json_concurrency

    def put_bytes(self, path: str, data: bytes, content_type: str | None = None) -> str:
        qualified = _tenant_path(path, action="storage.write")
        self._backend.put_bytes(qualified, data, content_type)
        return qualified if access_mode() == "multi_tenant" else path

    def get_bytes(self, path: str) -> bytes:
        return self._backend.get_bytes(_tenant_path(path, action="storage.read"))

    def get_json_snapshot(self, path: str, default: Any = None) -> JsonSnapshot:
        return self._backend.get_json_snapshot(_tenant_path(path, action="storage.read"), default)

    def compare_and_swap_json(self, path: str, expected_revision, value: Any) -> JsonSnapshot:
        qualified = _tenant_path(path, action="storage.write")
        _tenant_path(path, action="storage.read")
        return self._backend.compare_and_swap_json(qualified, expected_revision, value)

    def update_json(self, path: str, mutator: Callable[[Any], Any], default: Any = None, *, max_attempts: int = 5) -> Any:
        qualified = _tenant_path(path, action="storage.write")
        _tenant_path(path, action="storage.read")
        return self._backend.update_json(qualified, mutator, default, max_attempts=max_attempts)

    def exists(self, path: str) -> bool:
        qualified = _tenant_path(path, action="storage.read")
        return self._backend.exists(qualified)

    def list(self, prefix: str = "") -> list[str]:
        qualified = _tenant_path(prefix, action="storage.list", allow_empty=True)
        paths = self._backend.list(qualified)
        if access_mode() == "pilot":
            return paths
        actor = require_action("storage.list")
        assert actor is not None
        base = f"tenants/{actor.tenant_id}/"
        logical = []
        for path in paths:
            # Never trust a misconfigured backend or API to return own objects.
            normalized = _normalize_storage_path(path, allow_empty=False)
            _tenant_path(normalized, action="storage.list")
            if not normalized.startswith(base):
                raise AccessDenied("Resposta de armazenamento fora do namespace autorizado.")
            logical.append(normalized[len(base):])
        return sorted(set(logical))

    def delete(self, path: str) -> None:
        self._backend.delete(_tenant_path(path, action="storage.delete"))


BACKEND = TenantStorageBackend(get_backend())
CACHE_DIR = Path(os.environ.get("FAITHBLOOM_CACHE_DIR", ".faithbloom_cache")).resolve()
CACHE_DIR.mkdir(parents=True, exist_ok=True)
URI_PREFIX = "fb://"


def backend_status() -> dict:
    return {
        "modo": BACKEND.name,
        "persistente_cloud": BACKEND.name == "supabase",
        "bucket": getattr(BACKEND, "bucket", "local"),
        "auth": getattr(BACKEND, "key_kind", "local"),
        "access_mode": access_mode(),
        "tenant_scoped": access_mode() == "multi_tenant",
        "index_concurrency": BACKEND.json_concurrency,
        "index_concurrency_requires_update_api": True,
    }


def storage_uri(path: str) -> str:
    return URI_PREFIX + _tenant_path(path, action="storage.read")


def is_storage_uri(value: str) -> bool:
    return isinstance(value, str) and value.startswith(URI_PREFIX)


def uri_to_path(uri: str) -> str:
    if not is_storage_uri(uri):
        raise StorageError("Referência de armazenamento inválida.")
    path = _normalize_storage_path(uri[len(URI_PREFIX):], allow_empty=False)
    if access_mode() == "multi_tenant":
        if not path.startswith("tenants/"):
            # Legacy pilot assets are not implicitly adopted by a customer.
            raise AccessDenied("Referência sem namespace de conta autorizado.")
        return _tenant_path(path, action="storage.read")
    return path


_ASSET_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp3", ".wav", ".pdf", ".epub", ".svg"}


def _own_local_roots(tenant_id: str) -> list[Path]:
    base = CACHE_DIR.resolve()
    roots = [base / "tenants" / tenant_id / kind for kind in ("cache", "outputs")]
    if any(root.resolve() != root for root in roots):
        raise AccessDenied("Diretório local da conta não autorizado.")
    return roots


def tenant_local_directory(kind: str = "outputs") -> Path:
    """Own cache/scratch root for future adapters; no global legacy export grant."""
    if kind not in {"outputs", "cache"}:
        raise StorageError("Tipo de diretório local inválido.")
    actor = require_action("storage.write" if kind == "outputs" else "storage.read")
    if actor is None:
        return CACHE_DIR
    roots = _own_local_roots(actor.tenant_id)
    root = roots[1 if kind == "outputs" else 0]
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_local_output(path: str | os.PathLike | None = None, *,
                         default_path: str | os.PathLike) -> str:
    """Authorize a local export destination without creating directories.

    Pilot callers retain their existing paths. In tenant mode a relative
    default is placed below the current account's outputs directory; explicit
    destinations must already name that directory or one of its descendants.
    Recheck on every export, even when a caller supplies a previously resolved
    path. Cache inputs and another account's outputs are never write grants.
    """
    actor = require_action("storage.write")
    value = os.fspath(default_path if path is None else path)
    if actor is None:
        return value
    if not value or "\\" in value or "\x00" in value:
        raise AccessDenied("Destino local não autorizado.")
    candidate = Path(value)
    if ".." in candidate.parts:
        raise AccessDenied("Destino local não autorizado.")
    root = _own_local_roots(actor.tenant_id)[1]
    if path is None and not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.absolute()
    # Check lexical containment before inspecting a supplied filesystem path.
    if candidate != root and root not in candidate.parents:
        raise AccessDenied("Destino local fora da conta autorizada.")
    try:
        if any(part.is_symlink() for part in (candidate, *candidate.parents)):
            raise AccessDenied("Destino local não autorizado.")
        if candidate.resolve() != candidate:
            raise AccessDenied("Destino local não autorizado.")
    except (OSError, ValueError, RuntimeError):
        raise AccessDenied("Destino local não autorizado.") from None
    return str(candidate)


def _authorize_local_asset(value: str, *, action: str = "storage.read") -> None:
    if access_mode() != "multi_tenant":
        return
    actor = require_action(action)
    assert actor is not None
    try:
        path = Path(value).resolve()
        roots = _own_local_roots(actor.tenant_id)
    except (OSError, ValueError):
        raise AccessDenied("Caminho local não autorizado.") from None
    if not any(path == root or root in path.parents for root in roots):
        raise AccessDenied("Arquivo local fora da conta autorizada.")


def _local_asset_path(value: str) -> Path | None:
    """Retorna Path apenas quando a string pode representar um asset local real."""
    if not isinstance(value, str) or not value or is_storage_uri(value):
        return None
    try:
        p = Path(value)
        if p.suffix.lower() not in _ASSET_EXTS:
            return None
        _authorize_local_asset(value)
        if not p.exists() or not p.is_file():
            return None
        return p
    except AccessDenied:
        raise
    except (OSError, ValueError):
        return None


def persistir_arquivo(caminho_local: str, prefixo: str = "assets") -> str:
    if is_storage_uri(caminho_local):
        uri_to_path(caminho_local)  # ownership before returning an existing URI
        return caminho_local
    p = _local_asset_path(caminho_local)
    if p is None:
        return caminho_local
    digest = hashlib.sha256(p.read_bytes()).hexdigest()[:20]
    ext = p.suffix.lower() or ".bin"
    destino = f"{prefixo.strip('/')}/{digest}{ext}"
    ctype = mimetypes.guess_type(str(p))[0]
    BACKEND.put_bytes(destino, p.read_bytes(), ctype)
    return storage_uri(destino)


def materializar(uri_ou_caminho: str) -> str:
    if not is_storage_uri(uri_ou_caminho):
        _authorize_local_asset(uri_ou_caminho)
        return uri_ou_caminho
    # uri_to_path authorizes ownership before any cache existence/read check.
    storage_path = uri_to_path(uri_ou_caminho)
    ext = Path(storage_path).suffix or ".bin"
    digest = hashlib.sha256(storage_path.encode("utf-8")).hexdigest()[:24]
    cache_root = tenant_local_directory("cache") if access_mode() == "multi_tenant" else CACHE_DIR
    local = cache_root / f"{digest}{ext}"
    _authorize_local_asset(str(local))
    if not local.exists():
        local.write_bytes(BACKEND.get_bytes(storage_path))
    return str(local)


def persistir_assets_em_objeto(value: Any, prefixo: str) -> Any:
    """Copia arquivos locais referenciados por um state para o backend e grava fb:// URIs."""
    if isinstance(value, dict):
        return {k: persistir_assets_em_objeto(v, prefixo) for k, v in value.items()}
    if isinstance(value, list):
        return [persistir_assets_em_objeto(v, prefixo) for v in value]
    if isinstance(value, tuple):
        return [persistir_assets_em_objeto(v, prefixo) for v in value]
    if isinstance(value, str):
        if is_storage_uri(value):
            uri_to_path(value)
            return value
        if _local_asset_path(value) is not None:
            return persistir_arquivo(value, prefixo)
    return value


def materializar_assets_em_objeto(value: Any) -> Any:
    """Materializa arquivos de mídia sem transformar referências de projetos JSON.

    Campos como storage_path e source_ref identificam um registro persistido;
    uma cópia desse JSON no cache não pode substituir sua identidade.
    """
    if isinstance(value, dict):
        return {k: materializar_assets_em_objeto(v) for k, v in value.items()}
    if isinstance(value, list):
        return [materializar_assets_em_objeto(v) for v in value]
    if isinstance(value, str) and is_storage_uri(value):
        if Path(uri_to_path(value)).suffix.casefold() == ".json":
            return value
        try:
            return materializar(value)
        except AccessDenied:
            raise
        except StorageError:
            # Media can remain a durable URI during a temporary outage. The
            # same exception on JSON/catalog data is propagated by get_json.
            return value
    if isinstance(value, str) and Path(value).suffix.casefold() in _ASSET_EXTS:
        _authorize_local_asset(value)
    return value


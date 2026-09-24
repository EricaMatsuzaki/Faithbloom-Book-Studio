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
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import requests


class StorageError(RuntimeError):
    pass


class StorageBackend:
    name = "base"

    def put_bytes(self, path: str, data: bytes, content_type: str | None = None) -> str:
        raise NotImplementedError

    def get_bytes(self, path: str) -> bytes:
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        try:
            self.get_bytes(path)
            return True
        except Exception:
            return False

    def list(self, prefix: str = "") -> list[str]:
        raise NotImplementedError

    def delete(self, path: str) -> None:
        raise NotImplementedError

    def put_json(self, path: str, value: Any) -> str:
        return self.put_bytes(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"), "application/json")

    def get_json(self, path: str, default: Any = None) -> Any:
        try:
            return json.loads(self.get_bytes(path).decode("utf-8"))
        except Exception:
            return default


class LocalStorageBackend(StorageBackend):
    name = "local"

    def __init__(self, root: str | None = None):
        self.root = Path(root or os.environ.get("FAITHBLOOM_LOCAL_DATA_DIR", ".faithbloom_data")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, path: str) -> Path:
        clean = path.strip("/")
        p = (self.root / clean).resolve()
        if self.root not in p.parents and p != self.root:
            raise StorageError("Caminho inválido no armazenamento local")
        return p

    def put_bytes(self, path: str, data: bytes, content_type: str | None = None) -> str:
        p = self._p(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".{p.name}.tmp-{os.getpid()}-{hashlib.sha256(data).hexdigest()[:8]}")
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

    def get_bytes(self, path: str) -> bytes:
        return self._p(path).read_bytes()

    def list(self, prefix: str = "") -> list[str]:
        base = self._p(prefix)
        if base.is_file():
            return [prefix.strip("/")]
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)).replace(os.sep, "/") for p in base.rglob("*") if p.is_file())

    def delete(self, path: str) -> None:
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

    def __init__(self, url: str, service_key: str, bucket: str = "faithbloom"):
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

    def _object_url(self, path: str) -> str:
        clean = _normalize_storage_path(path, allow_empty=False)
        return f"{self.url}/storage/v1/object/{quote(self.bucket, safe='')}/{quote(clean, safe='/')}"

    def _list_endpoint(self) -> str:
        return f"{self.url}/storage/v1/object/list/{quote(self.bucket, safe='')}"

    def put_bytes(self, path: str, data: bytes, content_type: str | None = None) -> str:
        clean = _normalize_storage_path(path, allow_empty=False)
        headers = {**self.headers, "x-upsert": "true", "Content-Type": content_type or "application/octet-stream"}
        r = requests.post(self._object_url(clean), headers=headers, data=data, timeout=120)
        if r.status_code not in (200, 201):
            raise StorageError(f"Supabase upload falhou ({r.status_code}): {r.text[:300]}")
        return clean

    def get_bytes(self, path: str) -> bytes:
        r = requests.get(self._object_url(path), headers=self.headers, timeout=120)
        if r.status_code != 200:
            raise StorageError(f"Supabase download falhou ({r.status_code})")
        return r.content

    def _list_level(self, prefix: str) -> list[dict]:
        current = _normalize_storage_path(prefix, allow_empty=True)
        payload = {
            "prefix": current,
            "limit": 1000,
            "offset": 0,
            "sortBy": {"column": "name", "order": "asc"},
        }
        r = requests.post(
            self._list_endpoint(),
            headers={**self.headers, "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if r.status_code != 200:
            detail = r.text[:300]
            raise StorageError(
                f"Supabase list falhou ({r.status_code}) no bucket '{self.bucket}' "
                f"prefixo '{current or '/'}': {detail}"
            )
        data = r.json() or []
        return [x for x in data if isinstance(x, dict)]

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
            try:
                items = self._list_level(current)
            except StorageError as exc:
                # Um único prefixo histórico/corrompido não deve impedir o app de
                # listar os demais objetos. O prefixo inicial continua fail-closed.
                if current != start:
                    continue
                raise exc
            for item in items:
                raw_name = str(item.get("name") or "").strip()
                if not raw_name:
                    continue
                try:
                    full = self._join_list_item(current, raw_name)
                except StorageError:
                    continue
                if not full or full == current:
                    continue
                is_folder = item.get("id") in {None, ""} and item.get("metadata") is None
                if is_folder:
                    if full not in visited:
                        queue.append(full)
                else:
                    out.append(full)
        return sorted(set(out))

    def delete(self, path: str) -> None:
        clean = _normalize_storage_path(path, allow_empty=False)
        endpoint = f"{self.url}/storage/v1/object/{quote(self.bucket, safe='')}"
        r = requests.delete(
            endpoint,
            headers={**self.headers, "Content-Type": "application/json"},
            json={"prefixes": [clean]},
            timeout=60,
        )
        if r.status_code not in (200, 204):
            raise StorageError(f"Supabase delete falhou ({r.status_code})")


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
        )
    return LocalStorageBackend()


BACKEND = get_backend()
CACHE_DIR = Path(os.environ.get("FAITHBLOOM_CACHE_DIR", ".faithbloom_cache")).resolve()
CACHE_DIR.mkdir(parents=True, exist_ok=True)
URI_PREFIX = "fb://"


def backend_status() -> dict:
    return {
        "modo": BACKEND.name,
        "persistente_cloud": BACKEND.name == "supabase",
        "bucket": getattr(BACKEND, "bucket", "local"),
        "auth": getattr(BACKEND, "key_kind", "local"),
    }


def storage_uri(path: str) -> str:
    return URI_PREFIX + path.strip("/")


def is_storage_uri(value: str) -> bool:
    return isinstance(value, str) and value.startswith(URI_PREFIX)


def uri_to_path(uri: str) -> str:
    return uri[len(URI_PREFIX):].strip("/")


_ASSET_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp3", ".wav", ".pdf", ".svg"}


def _local_asset_path(value: str) -> Path | None:
    """Retorna Path apenas quando a string pode representar um asset local real."""
    if not isinstance(value, str) or not value or is_storage_uri(value):
        return None
    try:
        p = Path(value)
        if p.suffix.lower() not in _ASSET_EXTS:
            return None
        if not p.exists() or not p.is_file():
            return None
        return p
    except (OSError, ValueError):
        return None


def persistir_arquivo(caminho_local: str, prefixo: str = "assets") -> str:
    if is_storage_uri(caminho_local):
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
        return uri_ou_caminho
    storage_path = uri_to_path(uri_ou_caminho)
    ext = Path(storage_path).suffix or ".bin"
    digest = hashlib.sha256(storage_path.encode("utf-8")).hexdigest()[:24]
    local = CACHE_DIR / f"{digest}{ext}"
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
            return value
        if _local_asset_path(value) is not None:
            return persistir_arquivo(value, prefixo)
    return value


def materializar_assets_em_objeto(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: materializar_assets_em_objeto(v) for k, v in value.items()}
    if isinstance(value, list):
        return [materializar_assets_em_objeto(v) for v in value]
    if isinstance(value, str) and is_storage_uri(value):
        try:
            return materializar(value)
        except Exception:
            return value
    return value

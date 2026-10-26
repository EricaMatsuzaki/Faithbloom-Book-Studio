"""FaithBloom 2.0 — persistência de projetos, personagens, galeria e marca.

A API pública deste módulo foi mantida para não quebrar as telas existentes.
Por baixo, os dados usam storage_backend.py:
- local no desenvolvimento;
- Supabase Storage no Streamlit Cloud, quando configurado.
"""
from __future__ import annotations

from copy import deepcopy
from collections import OrderedDict
import json
import os
import re
import time
import threading
import uuid
from pathlib import Path

from storage_backend import (
    BACKEND, backend_status, is_storage_uri, materializar,
    materializar_assets_em_objeto, persistir_arquivo, persistir_assets_em_objeto,
    storage_uri,
)
from stable_hardening import ensure_project_schema
import storage_backend as storage
from storage_updates import update_json_document


class ProtectedBookUpdate(PermissionError):
    """A legacy snapshot cannot replace a product's paid-execution record."""


BOOK_SAVE_CONTEXT_KEY = "_book_save_context"
_BOOK_TRANSIENT_FIELDS = {BOOK_SAVE_CONTEXT_KEY, "autosave_pending"}
_MISSING = object()
_BLOCKED = object()
_BOOK_READ_SCHEMA = "faithbloom.book-read.v2"
# Baselines remain server-side. The graph/session carries only an unguessable
# handle, so an old raw book is never copied into provider prompts or exports.
_BOOK_READ_CONTEXTS = OrderedDict()
_BOOK_READ_LOCK = threading.RLock()
_BOOK_READ_MAX_CONTEXTS = 256
_BOOK_READ_MAX_BYTES = 32 * 1024 * 1024


class BookSaveConflict(storage.StorageConflict):
    """The received/edited draft is retained while a field conflict is resolved."""
    def __init__(self, fields=(), *, missing_baseline=False):
        super().__init__()
        self.fields = tuple(fields)
        self.missing_baseline = missing_baseline
        self.args = (("Reabra o livro salvo antes de continuar esta edição. O rascunho recebido foi preservado."
                      if missing_baseline else
                      "Outra edição alterou os mesmos campos. O rascunho recebido foi preservado; confira a versão atual antes de salvar."),)


def _book_payload(state: dict) -> dict:
    """Strip the in-memory read carrier; normalize JSON keys before field diffs."""
    value = {key: value for key, value in state.items() if key not in _BOOK_TRANSIENT_FIELDS}
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _book_read_path(reference: str) -> str:
    path = storage.uri_to_path(reference) if is_storage_uri(reference) else storage._tenant_path(
        storage._normalize_storage_path(reference, allow_empty=False), action="storage.read")
    logical = path.split("/", 2)[-1] if path.startswith("tenants/") else path
    if not logical.endswith(".json") or not logical.startswith(("livros/", "livros_colorir/")):
        raise ValueError("A referência não corresponde a um livro salvo.")
    return path


def bind_book_read_context(state: dict, reference: str, raw_document: dict) -> dict:
    """Bind the EXACT document already read; this function never fetches a baseline.

    Generic loaders do not attach this carrier to editorial products, whose
    runtime has its own snapshot contract. Explicit callers may bind a draft;
    the legacy writer still rejects every persisted editorial execution record.
    """
    path = _book_read_path(reference)
    if not isinstance(raw_document, dict) or not isinstance(state, dict):
        raise storage.StorageCorrupt("O livro salvo precisa de recuperação.")
    state.pop(BOOK_SAVE_CONTEXT_KEY, None)
    state["storage_path"] = storage_uri(path)
    context = {"schema": _BOOK_READ_SCHEMA, "path": path,
               "raw": _book_payload(raw_document), "view": _book_payload(state)}
    token = uuid.uuid4().hex
    size = len(json.dumps(context, ensure_ascii=False).encode("utf-8"))
    with _BOOK_READ_LOCK:
        _BOOK_READ_CONTEXTS[token] = (context, size)
        while (len(_BOOK_READ_CONTEXTS) > _BOOK_READ_MAX_CONTEXTS
               or sum(item[1] for item in _BOOK_READ_CONTEXTS.values()) > _BOOK_READ_MAX_BYTES):
            _BOOK_READ_CONTEXTS.popitem(last=False)
    state[BOOK_SAVE_CONTEXT_KEY] = {"schema": _BOOK_READ_SCHEMA, "path": path, "token": token}
    return state


def get_book_read_context(state: dict, reference: str) -> dict:
    """Return a copy of the exact observed baseline after current authorization.

    Eviction, a worker restart, or a mismatched handle requires an explicit
    reload. Never reconstruct a baseline from a late storage read.
    """
    path = _book_read_path(reference)
    carrier = state.get(BOOK_SAVE_CONTEXT_KEY) if isinstance(state, dict) else None
    if (not isinstance(carrier, dict) or carrier.get("schema") != _BOOK_READ_SCHEMA
            or carrier.get("path") != path or not isinstance(carrier.get("token"), str)):
        raise BookSaveConflict(missing_baseline=True)
    with _BOOK_READ_LOCK:
        entry = _BOOK_READ_CONTEXTS.get(carrier["token"])
        if entry is None or entry[0].get("path") != path:
            raise BookSaveConflict(missing_baseline=True)
        _BOOK_READ_CONTEXTS.move_to_end(carrier["token"])
        return deepcopy(entry[0])


def _field_changes(before, after, prefix=()):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            if not prefix and key == "storage_path":
                continue
            old, new = before.get(key, _MISSING), after.get(key, _MISSING)
            if old is _MISSING and isinstance(new, dict) and new:
                yield from _field_changes({}, new, (*prefix, key))
            elif old is not _MISSING and new is not _MISSING and isinstance(old, dict) and isinstance(new, dict):
                yield from _field_changes(old, new, (*prefix, key))
            elif old is _MISSING or new is _MISSING or old != new:
                yield (*prefix, key), new


def _field_value(value, path):
    for key in path:
        if not isinstance(value, dict):
            return _BLOCKED
        if key not in value:
            return _MISSING
        value = value[key]
    return value


def _set_field(value, path, wanted):
    for key in path[:-1]:
        if key not in value:
            value[key] = {}
        value = value[key]
    if wanted is _MISSING:
        value.pop(path[-1], None)
    else:
        value[path[-1]] = deepcopy(wanted)


def _fill_missing(target: dict, defaults: dict) -> None:
    for key, value in defaults.items():
        if key not in target:
            target[key] = deepcopy(value)
        elif isinstance(target[key], dict) and isinstance(value, dict):
            _fill_missing(target[key], value)


def _reuse_read_values(value, observed, raw):
    """Keep durable media URIs for leaves unchanged from the materialized read."""
    if raw is not _MISSING and value == observed:
        return deepcopy(raw)
    if isinstance(value, dict) and isinstance(observed, dict) and isinstance(raw, dict):
        return {key: _reuse_read_values(item, observed.get(key, _MISSING), raw.get(key, _MISSING))
                for key, item in value.items()}
    if isinstance(value, list) and isinstance(observed, list) and isinstance(raw, list):
        return [_reuse_read_values(item, observed[index] if index < len(observed) else _MISSING,
                                  raw[index] if index < len(raw) else _MISSING)
                for index, item in enumerate(value)]
    return deepcopy(value)


def _refresh_book_working_state(state: dict, raw: dict, reference: str, *, materialize=True) -> None:
    if isinstance(raw.get("editorial_product"), dict):
        state.pop(BOOK_SAVE_CONTEXT_KEY, None)
        state["storage_path"] = reference
        return
    materialize = materialize and not isinstance(raw.get("comic_product"), dict)
    view = materializar_assets_em_objeto(ensure_project_schema(deepcopy(raw))) if materialize else deepcopy(raw)
    state.clear()
    state.update(view)
    bind_book_read_context(state, reference, raw)


def _book_update_path(reference: str, prefix: str) -> str:
    if not reference:
        raise ValueError("O caminho do projeto salvo não foi informado.")
    path = (storage.uri_to_path(reference) if is_storage_uri(reference)
            else storage._normalize_storage_path(reference, allow_empty=False))
    # Authorize WRITE before inspecting the document or preparing any assets.
    # uri_to_path authorizes reading a canonical URI, which is not enough for
    # a read-only actor trying to save a book.
    path = storage._tenant_path(path, action="storage.write")
    if path.startswith("tenants/"):
        if storage.access_mode() != "multi_tenant":
            raise storage.AccessDenied("Uma referência de conta exige o contexto autorizado dessa conta.")
        logical = path.split("/", 2)[-1]
    else:
        logical = path
    if not logical.startswith(prefix + "/") or not logical.endswith(".json"):
        raise ValueError("O caminho não corresponde ao tipo de projeto salvo.")
    return path


def _assert_legacy_book_update(current, incoming: dict) -> None:
    if current is None:
        raise storage.StorageNotFound("O projeto salvo não foi encontrado. Nenhum novo livro foi criado.")
    if not isinstance(current, dict):
        raise storage.StorageCorrupt("O projeto salvo precisa de recuperação antes de ser atualizado.")
    for value in (current, incoming):
        product = value.get("editorial_product")
        if isinstance(product, dict) and "execution" in product:
            # Even an empty/invalid/terminal execution record belongs to the
            # specialized runtime. Retaining only its ledger while replacing
            # units/approvals with a stale snapshot would also be unsafe.
            raise ProtectedBookUpdate(
                "Este produto usa salvamento protegido. Abra-o no Studio de Produtos Editoriais; "
                "esta cópia não foi gravada. Preserve qualquer resultado já recebido."
            )
    existing_id = current.get("book_id")
    if existing_id and incoming.get("book_id") != existing_id:
        raise ValueError("A identidade da cópia não corresponde ao livro salvo. Recarregue o projeto antes de salvar.")


def _update_existing_book(reference: str, state: dict, *, prefix: str, assets_prefix: str) -> str:
    """Merge only edits since the actual read, preserving other sessions' fields."""
    if not isinstance(state, dict):
        raise TypeError("O projeto precisa ser um objeto de dados.")
    incoming = _book_payload(state)
    path = _book_update_path(reference, prefix)
    declared = incoming.get("storage_path")
    if declared and _book_update_path(declared, prefix) != path:
        raise ValueError("A cópia pertence a outro caminho de projeto. Nenhum livro foi alterado.")
    current = BACKEND.get_json(path, None)
    _assert_legacy_book_update(current, incoming)
    context = get_book_read_context(state, reference)
    baseline_raw, baseline_view = _book_payload(context["raw"]), _book_payload(context["view"])
    _assert_legacy_book_update(baseline_raw, incoming)
    changes = list(_field_changes(baseline_view, incoming))
    # Detect an existing conflict before reading/uploading any new media.
    def validate_fields(document, prepared=None):
        conflicts = []
        for field, new in changes:
            now = _field_value(document, field)
            old = _field_value(baseline_raw, field)
            observed = _field_value(baseline_view, field)
            wanted = _field_value(prepared, field) if prepared is not None and new is not _MISSING else new
            if now is _BLOCKED or not (now == old or (old is _MISSING and now == observed) or now == wanted):
                conflicts.append(".".join(field))
        if conflicts:
            raise BookSaveConflict(conflicts)
    validate_fields(current)
    prepared = ensure_project_schema(_reuse_read_values(ensure_project_schema(incoming), baseline_view, baseline_raw))
    changed_values = {}
    for field, new in changes:
        if new is not _MISSING:
            _set_field(changed_values, field, _field_value(prepared, field))
    persisted_changes = persistir_assets_em_objeto(changed_values, assets_prefix)
    for field, new in changes:
        if new is not _MISSING:
            _set_field(prepared, field, _field_value(persisted_changes, field))
    canonical = storage_uri(path)

    def replace_current(current):
        _assert_legacy_book_update(current, prepared)
        validate_fields(current, prepared)
        result = deepcopy(current)
        schema_defaults = {key: prepared[key] for key in ("_faithbloom_schema", "_faithbloom_schema_version",
            "_faithbloom_migrations", "project_meta", "workflow", "content_protection", "stable_release", "authorship")
            if key in prepared}
        _fill_missing(result, schema_defaults)
        for field, new in changes:
            wanted = _MISSING if new is _MISSING else _field_value(prepared, field)
            _set_field(result, field, wanted)
        result["storage_path"] = canonical
        result.pop(BOOK_SAVE_CONTEXT_KEY, None)
        result.pop("autosave_pending", None)
        return result

    committed = update_json_document(BACKEND, path, replace_current, allow_legacy_pilot=True)
    _refresh_book_working_state(state, committed, canonical)
    return canonical


def _slug(titulo: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (titulo or "").lower()).strip("-")
    return slug or "sem-titulo"


def _json(path: str, default):
    return BACKEND.get_json(path, default)


def _save_json(path: str, data) -> str:
    BACKEND.put_json(path, data)
    return path


def salvar_livro(state: dict) -> str:
    original = state
    state = ensure_project_schema(_book_payload(state))
    colecao_slug = _slug(state.get("colecao", "sem-colecao"))
    slug = _slug(state.get("titulo", ""))
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = f"livros/{colecao_slug}/{slug}-{timestamp}-{uuid.uuid4().hex[:12]}.json"
    serializavel = persistir_assets_em_objeto(dict(state), f"assets/livros/{colecao_slug}/{slug}")
    _save_json(path, serializavel)
    if state.get("personagens"):
        atualizar_biblioteca_personagens(state.get("colecao", "sem-colecao"), state["personagens"])
    reference = storage_uri(path)
    _refresh_book_working_state(original, serializavel, reference)
    return reference


def atualizar_livro_salvo(storage_path: str, state: dict) -> str:
    """Atualiza explicitamente um projeto salvo no MESMO caminho.

    Usado por telas editoriais que precisam persistir metadados estruturados
    (ex.: autoria). Não cria uma nova versão e nunca é chamado silenciosamente.
    """
    if not isinstance(state, dict):
        raise TypeError("O projeto precisa ser um objeto de dados.")
    return _update_existing_book(storage_path, state, prefix="livros",
        assets_prefix=f"assets/livros/{_slug(state.get('colecao','sem-colecao'))}/{_slug(state.get('titulo',''))}")


def listar_livros(colecao: str | None = None) -> list[dict]:
    prefix = f"livros/{_slug(colecao)}" if colecao else "livros"
    itens = []
    for path in reversed(BACKEND.list(prefix)):
        if not path.endswith(".json"):
            continue
        dados = _json(path, {}) or {}
        itens.append({
            "arquivo": path.split("/")[-1],
            "storage_path": path,
            "colecao": dados.get("colecao", ""),
            "titulo": dados.get("titulo", "(sem título)"),
            "pacote_pronto": dados.get("pacote_pronto", False),
        })
    return itens


def carregar_livro(colecao: str, nome_arquivo: str) -> dict:
    path = nome_arquivo if "/" in nome_arquivo else f"livros/{_slug(colecao)}/{nome_arquivo}"
    path = _book_read_path(path)
    dados = _json(path, {}) or {}
    # Compatibilidade: projetos antigos são migrados apenas na cópia carregada.
    # A versão persistida só muda quando a autora salvar explicitamente uma nova versão.
    view = materializar_assets_em_objeto(ensure_project_schema(deepcopy(dados)))
    if isinstance(view.get("editorial_product"), dict):
        view["storage_path"] = storage_uri(path)
        return view
    return bind_book_read_context(view, path, dados)


def listar_colecoes() -> list[str]:
    nomes = set()
    for livro in listar_livros():
        if livro.get("colecao"):
            nomes.add(livro["colecao"])
    # bibliotecas podem existir antes de um livro finalizado
    for path in BACKEND.list("bibliotecas_personagens"):
        if path.endswith(".json"):
            dados = _json(path, {}) or {}
            nome = dados.get("_colecao_nome") if isinstance(dados, dict) else None
            if nome:
                nomes.add(nome)
    return sorted(nomes)


def atualizar_biblioteca_personagens(colecao: str, personagens: dict) -> None:
    path = f"bibliotecas_personagens/{_slug(colecao)}.json"
    biblioteca = _json(path, {}) or {}
    biblioteca.pop("_colecao_nome", None)
    incoming = persistir_assets_em_objeto(personagens, f"assets/personagens/{_slug(colecao)}")
    biblioteca.update(incoming)
    biblioteca["_colecao_nome"] = colecao
    _save_json(path, biblioteca)


def carregar_biblioteca_personagens(colecao: str) -> dict:
    path = f"bibliotecas_personagens/{_slug(colecao)}.json"
    biblioteca = _json(path, {}) or {}
    if isinstance(biblioteca, dict):
        biblioteca.pop("_colecao_nome", None)
    return materializar_assets_em_objeto(biblioteca)


def salvar_asset_marca(colecao: str, tipo: str, conteudo_bytes: bytes) -> str:
    path = f"marca_colecoes/{_slug(colecao)}/{tipo}.png"
    BACKEND.put_bytes(path, conteudo_bytes, "image/png")
    return materializar(storage_uri(path))


def carregar_asset_marca(colecao: str, tipo: str) -> str | None:
    path = f"marca_colecoes/{_slug(colecao)}/{tipo}.png"
    if not BACKEND.exists(path):
        return None
    return materializar(storage_uri(path))


def salvar_livro_colorir(state: dict) -> str:
    original = state
    state = ensure_project_schema(_book_payload(state))
    slug = _slug(state.get("titulo", ""))
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = f"livros_colorir/{slug}-{timestamp}-{uuid.uuid4().hex[:12]}.json"
    serializavel = persistir_assets_em_objeto(dict(state), f"assets/colorir/{slug}")
    _save_json(path, serializavel)
    reference = storage_uri(path)
    _refresh_book_working_state(original, serializavel, reference)
    return reference


def atualizar_livro_colorir_salvo(storage_path: str, state: dict) -> str:
    """Atualiza explicitamente um Coloring Book já salvo, preservando o caminho."""
    if not isinstance(state, dict):
        raise TypeError("O projeto precisa ser um objeto de dados.")
    return _update_existing_book(storage_path, state, prefix="livros_colorir",
        assets_prefix=f"assets/colorir/{_slug(state.get('titulo',''))}")


def listar_livros_colorir() -> list[dict]:
    livros = []
    for path in reversed(BACKEND.list("livros_colorir")):
        if not path.endswith(".json"):
            continue
        dados = _json(path, {}) or {}
        livros.append({"arquivo": path.split("/")[-1], "storage_path": path, "titulo": dados.get("titulo", "(sem título)"), "tema_geral": dados.get("tema_geral", "")})
    return livros


def carregar_livro_colorir(nome_arquivo: str) -> dict:
    path = nome_arquivo if "/" in nome_arquivo else f"livros_colorir/{nome_arquivo}"
    path = _book_read_path(path)
    raw = _json(path, {}) or {}
    view = materializar_assets_em_objeto(ensure_project_schema(deepcopy(raw)))
    if isinstance(view.get("editorial_product"), dict):
        view["storage_path"] = storage_uri(path)
        return view
    return bind_book_read_context(view, path, raw)


def temas_colorir_usados() -> list[str]:
    return [l["titulo"] for l in listar_livros_colorir()]


# ------------------------- Galeria permanente -------------------------
GALERIA_INDEX = "galeria/index.json"


def _ler_indice_galeria() -> list[dict]:
    dados = _json(GALERIA_INDEX, [])
    return dados if isinstance(dados, list) else []


def _salvar_indice_galeria(itens: list[dict]) -> None:
    _save_json(GALERIA_INDEX, itens)


def salvar_na_galeria(caminho_origem: str, nome: str, tipo: str = "personagem", tags: list[str] | None = None, metadata: dict | None = None) -> dict:
    """Salva um asset no catálogo visual sem duplicar bytes idênticos.

    O índice continua compatível com as telas antigas, mas já nasce com os
    campos do Asset Library & Media Manager (Refinamento 16). Se a mesma URI
    já existir, apenas une tags/metadados e reutiliza o registro.
    """
    if not caminho_origem:
        raise FileNotFoundError("Nenhuma imagem foi informada.")
    if is_storage_uri(caminho_origem):
        uri = caminho_origem
    else:
        if not os.path.exists(caminho_origem):
            raise FileNotFoundError("A imagem escolhida não existe nesta sessão.")
        uri = persistir_arquivo(caminho_origem, "assets/galeria")
    agora = int(time.time())
    itens = _ler_indice_galeria()
    existente = next((x for x in itens if x.get("storage_uri") == uri), None)
    if existente:
        existente["tags"] = sorted(set([*existente.get("tags", []), *[t for t in (tags or []) if t]]))
        merged = dict(existente.get("metadata") or {}); merged.update(metadata or {})
        existente["metadata"] = merged
        existente["atualizada_em"] = agora
        existente["status"] = "active"
        existente.setdefault("asset_schema_version", 2)
        existente.setdefault("status", "active")
        existente.setdefault("master_roles", [])
        existente.setdefault("virtual_collections", [])
        existente.setdefault("version_group", existente.get("id"))
        existente.setdefault("version_label", "Original")
        existente.setdefault("approved", bool(merged.get("aprovada", False)))
        _salvar_indice_galeria(itens)
        return {**existente, "caminho_arquivo": materializar(uri)}
    ext = Path(uri[5:] if is_storage_uri(uri) else uri).suffix.lower()
    media_kind = "image" if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"} else ("svg" if ext == ".svg" else ("pdf" if ext == ".pdf" else ("audio" if ext in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"} else "other")))
    item_id = uuid.uuid4().hex
    item = {
        "id": item_id,
        "nome": nome or "Imagem sem nome",
        "tipo": tipo,
        "tags": sorted(set(t for t in (tags or []) if t)),
        "storage_uri": uri,
        "metadata": metadata or {},
        "favorita": False,
        "criada_em": agora,
        "atualizada_em": agora,
        "status": "active",
        "asset_schema_version": 2,
        "master_roles": [],
        "virtual_collections": [],
        "version_group": item_id,
        "version_label": "Original",
        "parent_asset_id": "",
        "approved": bool((metadata or {}).get("aprovada", False)),
        "locked_original": bool((metadata or {}).get("original_publicado", False)),
        "media_kind": media_kind,
    }
    itens.append(item); _salvar_indice_galeria(itens)
    return {**item, "caminho_arquivo": materializar(uri)}


def listar_galeria(tipo: str | None = None, somente_favoritas: bool = False, busca: str = "") -> list[dict]:
    """Lista assets ativos para compatibilidade com todos os Studios antigos."""
    itens = [i for i in _ler_indice_galeria() if i.get("status", "active") != "archived"]
    if tipo:
        itens = [i for i in itens if i.get("tipo") == tipo]
    if somente_favoritas:
        itens = [i for i in itens if i.get("favorita")]
    q = busca.strip().lower()
    if q:
        def blob(i):
            m = i.get("metadata") or {}
            vals = [i.get("nome", ""), *i.get("tags", []), i.get("tipo", ""), m.get("personagem", ""), m.get("colecao", ""), m.get("livro", ""), m.get("emocao", ""), m.get("estacao", ""), m.get("festividade", "")]
            return " ".join(str(x) for x in vals).lower()
        tokens = [x for x in q.split() if x]
        itens = [i for i in itens if all(t in blob(i) for t in tokens)]
    out = []
    for item in sorted(itens, key=lambda i: i.get("criada_em", 0), reverse=True):
        uri = item.get("storage_uri") or item.get("caminho_arquivo", "")
        caminho = ""
        if uri:
            try: caminho = materializar(uri)
            except Exception: caminho = uri
        out.append({**item, "caminho_arquivo": caminho})
    return out


def favoritar_item_galeria(item_id: str, favorita: bool = True) -> None:
    itens = _ler_indice_galeria()
    for item in itens:
        if item.get("id") == item_id:
            item["favorita"] = bool(favorita); break
    _salvar_indice_galeria(itens)


def excluir_item_galeria(item_id: str, excluir_arquivo: bool = True) -> bool:
    itens = _ler_indice_galeria(); alvo = next((i for i in itens if i.get("id") == item_id), None)
    if not alvo: return False
    if excluir_arquivo and is_storage_uri(alvo.get("storage_uri", "")):
        try: BACKEND.delete(alvo["storage_uri"][5:])
        except Exception: pass
    _salvar_indice_galeria([i for i in itens if i.get("id") != item_id])
    return True


def estatisticas_armazenamento() -> dict:
    return {
        **backend_status(),
        "livros": len(listar_livros()),
        "livros_colorir": len(listar_livros_colorir()),
        "colecoes": len(listar_colecoes()),
        "galeria": len(_ler_indice_galeria()),
    }


def migrar_dados_locais_legados() -> dict:
    """Importa pastas da V1/V2 local para o backend atual. Seguro para rodar mais de uma vez."""
    resumo = {"json": 0, "assets": 0, "erros": []}
    mappings = [
        ("livros_salvos", "livros"), ("livros_colorir_salvos", "livros_colorir"),
        ("bibliotecas_personagens", "bibliotecas_personagens"), ("marca_colecoes", "marca_colecoes"),
    ]
    for src_root, dest_root in mappings:
        base = Path(src_root)
        if not base.exists(): continue
        for p in base.rglob("*"):
            if not p.is_file(): continue
            rel = p.relative_to(base).as_posix(); dest = f"{dest_root}/{rel}"
            try:
                BACKEND.put_bytes(dest, p.read_bytes())
                resumo["json" if p.suffix.lower()==".json" else "assets"] += 1
            except Exception as e: resumo["erros"].append(f"{p}: {e}")
    # galeria antiga: converte index + arquivos para o novo formato
    old_index = Path("galeria_imagens/index.json")
    if old_index.exists():
        try:
            old = json.loads(old_index.read_text(encoding="utf-8"))
            existentes = {i.get("id") for i in _ler_indice_galeria()}
            novos = _ler_indice_galeria()
            for item in old if isinstance(old, list) else []:
                if item.get("id") in existentes: continue
                path = item.get("caminho_arquivo", "")
                if path and Path(path).exists():
                    uri = persistir_arquivo(path, "assets/galeria")
                    item = {k:v for k,v in item.items() if k != "caminho_arquivo"}; item["storage_uri"] = uri
                    novos.append(item); resumo["assets"] += 1
            _salvar_indice_galeria(novos)
        except Exception as e: resumo["erros"].append(f"galeria: {e}")
    return resumo


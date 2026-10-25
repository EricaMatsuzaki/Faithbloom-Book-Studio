"""Legacy book snapshots cannot erase canonical paid claims or cross identities."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
import multiprocessing
from threading import Event

import pytest

import armazenamento as books
import editorial_generation_runtime as runtime
import editorial_products as studio
import saas_access as access
import storage_backend as storage
from test_editorial_generation_atomic import durable, product, provider
from test_storage_atomic_updates import rpc
from test_storage_updates import LegacyBucket


@pytest.fixture
def local(durable, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    return durable


def book(backend, path="livros/audit/book.json", **changes):
    state = {"book_id": "audit-book", "titulo": "Livro próprio", "colecao": "Auditoria", **changes}
    backend.put_json(path, state)
    return state


def forbid_assets(monkeypatch):
    monkeypatch.setattr(books, "persistir_assets_em_objeto",
                        lambda *_: pytest.fail("rejected book must not inspect or upload assets"))


@pytest.mark.parametrize("record", [None, {}, {"status": "ready"}, {"status": "running"},
                                      {"status": "needs_reconciliation"}, {"status": "save_failed"},
                                      {"status": "completed"}])
def test_existing_execution_is_protected_including_invalid_and_terminal_records(local, monkeypatch, record):
    state = book(local, editorial_product={"execution": record, "units": [{"text": "received"}]})
    before = local.get_bytes("livros/audit/book.json")
    stale = {**state, "editorial_product": {"units": []}}
    forbid_assets(monkeypatch)
    with pytest.raises(books.ProtectedBookUpdate, match="salvamento protegido"):
        books.atualizar_livro_salvo("fb://livros/audit/book.json", stale)
    assert local.get_bytes("livros/audit/book.json") == before


def test_legacy_writer_cannot_introduce_its_own_execution_record(local, monkeypatch):
    state = book(local)
    before = local.get_bytes("livros/audit/book.json")
    forbid_assets(monkeypatch)
    with pytest.raises(books.ProtectedBookUpdate):
        books.atualizar_livro_salvo("livros/audit/book.json", {**state, "editorial_product": {"execution": {}}})
    assert local.get_bytes("livros/audit/book.json") == before


def test_legacy_save_cannot_reset_live_claim_or_buy_a_second_unit(local, monkeypatch):
    source = product()
    stale = studio.load_product(source["storage_path"])
    entered, release = Event(), Event()
    calls = []

    def paid(**kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(8)
        return provider(**kwargs)

    with ThreadPoolExecutor(max_workers=1) as workers:
        first = workers.submit(studio.generate_product, source, paid, confirmed=True)
        try:
            assert entered.wait(5)
            path = runtime._path(source["storage_path"])
            active_bytes = local.get_bytes(path)
            assert runtime.generation_status(source["storage_path"])["attempts"][-1]["state"] == "running"
            with monkeypatch.context() as guarded:
                forbid_assets(guarded)
                with pytest.raises(books.ProtectedBookUpdate):
                    books.atualizar_livro_salvo(source["storage_path"], stale)
            assert local.get_bytes(path) == active_bytes
            with pytest.raises(PermissionError):
                studio.generate_product(studio.load_product(source["storage_path"]), paid, confirmed=True)
            assert calls == [1]
        finally:
            release.set()
        first.result(timeout=5)
    saved = studio.load_product(source["storage_path"])
    assert len(saved["editorial_product"]["units"]) == 1
    assert [item["state"] for item in saved["editorial_product"]["execution"]["attempts"]] == ["applied"]


def _active_paid_worker(root, reference, entered, release, calls, results):
    backend = storage.LocalStorageBackend(root)
    storage.BACKEND = books.BACKEND = backend
    source = studio.load_product(reference)
    def paid(**kwargs):
        with calls.get_lock():
            calls.value += 1
        entered.set()
        assert release.wait(15)
        return provider(**kwargs)
    try:
        studio.generate_product(source, paid, confirmed=True)
        results.put("completed")
    except Exception as exc:
        results.put(type(exc).__name__)


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="Linux shared-file workers")
def test_another_process_cannot_erase_active_claim_through_legacy_writer(local, monkeypatch):
    source = product()
    stale = studio.load_product(source["storage_path"])
    context = multiprocessing.get_context("fork")
    entered, release = context.Event(), context.Event()
    calls, results = context.Value("i", 0), context.Queue()
    worker = context.Process(target=_active_paid_worker,
        args=(str(local.root), source["storage_path"], entered, release, calls, results))
    worker.start()
    try:
        assert entered.wait(10)
        path = runtime._path(source["storage_path"])
        protected_bytes = local.get_bytes(path)
        with monkeypatch.context() as guarded:
            forbid_assets(guarded)
            with pytest.raises(books.ProtectedBookUpdate):
                books.atualizar_livro_salvo(source["storage_path"], stale)
        assert local.get_bytes(path) == protected_bytes
        with pytest.raises(PermissionError):
            studio.generate_product(studio.load_product(source["storage_path"]),
                                    lambda **_: pytest.fail("another paid request"), confirmed=True)
        release.set()
        assert results.get(timeout=10) == "completed"
        worker.join(10)
        assert worker.exitcode == 0 and calls.value == 1
    finally:
        release.set()
        if worker.is_alive():
            worker.terminate()
            worker.join(5)
        results.close()


@pytest.mark.parametrize("case,error", [("missing", storage.StorageNotFound),
                                        ("wrong_id", ValueError), ("missing_id", ValueError),
                                        ("wrong_declared_path", ValueError),
                                        ("corrupt", storage.StorageCorrupt),
                                        ("wrong_shape", storage.StorageCorrupt)])
def test_rejection_precedes_assets_and_never_creates_or_replaces_book(local, monkeypatch, case, error):
    path = "livros/audit/book.json"
    state = book(local)
    if case == "missing":
        local.delete(path)
    elif case == "wrong_id":
        state["book_id"] = "another-book"
    elif case == "missing_id":
        state.pop("book_id")
    elif case == "wrong_declared_path":
        state["storage_path"] = "fb://livros/audit/other.json"
    elif case == "corrupt":
        local.put_bytes(path, b"broken JSON")
    elif case == "wrong_shape":
        local.put_json(path, ["not a book"])
    before = local.get_bytes(path) if local.exists(path) else None
    forbid_assets(monkeypatch)
    with pytest.raises(error):
        books.atualizar_livro_salvo("fb://" + path, state)
    assert (local.get_bytes(path) if local.exists(path) else None) == before


@pytest.mark.parametrize("prefix,update", [("livros", books.atualizar_livro_salvo),
                                          ("livros_colorir", books.atualizar_livro_colorir_salvo)])
def test_legacy_books_without_identity_still_update_and_can_adopt_first_explicit_id(local, prefix, update):
    path = prefix + "/audit/book.json"
    state = {"titulo": "Legado", "colecao": "Auditoria", "text": "old"}
    local.put_json(path, state)
    reference = update(path, {**state, "text": "new"})
    assert reference == "fb://" + path
    assert local.get_json(path)["text"] == "new"
    update(reference, {**state, "text": "identified", "book_id": "first-explicit-id"})
    assert local.get_json(path)["book_id"] == "first-explicit-id"


@pytest.mark.parametrize("path,update", [("livros/audit/book.json", books.atualizar_livro_colorir_salvo),
                                        ("livros_colorir/audit/book.json", books.atualizar_livro_salvo)])
def test_book_type_boundary_is_checked_before_assets(local, monkeypatch, path, update):
    state = book(local, path)
    before = local.get_bytes(path)
    forbid_assets(monkeypatch)
    with pytest.raises(ValueError):
        update("fb://" + path, state)
    assert local.get_bytes(path) == before


def test_execution_added_during_asset_preparation_is_rechecked_at_commit(local, monkeypatch):
    source = studio.create_product("other", "Livro", "Observar uma flor", unit_count=1, custom_blocks=["Abertura"])
    source["storage_path"] = books.salvar_livro(source)
    stale = deepcopy(source)
    prepared = []

    def prepare(value, _prefix):
        prepared.append(1)
        runtime.save_existing_project(source, deepcopy(source))
        return deepcopy(value)

    monkeypatch.setattr(books, "persistir_assets_em_objeto", prepare)
    with pytest.raises(books.ProtectedBookUpdate):
        books.atualizar_livro_salvo(source["storage_path"], stale)
    assert prepared == [1]
    status = runtime.generation_status(source["storage_path"])
    assert status["status"] == "ready" and status["revision"] == 1


@pytest.mark.parametrize("change,error", [("delete", storage.StorageNotFound), ("identity", ValueError)])
def test_destination_deleted_or_reidentified_during_preparation_is_not_replaced(local, monkeypatch, change, error):
    path = "livros/audit/book.json"
    state = book(local)
    def prepare(value, _prefix):
        if change == "delete":
            local.delete(path)
        else:
            local.put_json(path, {**state, "book_id": "replacement-book", "text": "preserve replacement"})
        return deepcopy(value)
    monkeypatch.setattr(books, "persistir_assets_em_objeto", prepare)
    with pytest.raises(error):
        books.atualizar_livro_salvo(path, {**state, "text": "old received copy"})
    if change == "delete":
        assert not local.exists(path)
    else:
        assert local.get_json(path)["text"] == "preserve replacement"


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://identity.example")
    monkeypatch.delenv("FAITHBLOOM_ACCESS_ROLES", raising=False)
    actors = [access.actor_from_trusted_claims({"authenticated": True, "iss": "https://identity.example", "sub": name})
              for name in ("account-a", "account-b")]
    raw = storage.LocalStorageBackend(str(tmp_path / "private"))
    wrapper = storage.TenantStorageBackend(raw)
    monkeypatch.setattr(storage, "BACKEND", wrapper)
    monkeypatch.setattr(books, "BACKEND", wrapper)
    monkeypatch.setattr(storage, "CACHE_DIR", tmp_path / "cache")
    return *actors, raw, wrapper


@pytest.mark.parametrize("prefix,update", [("livros", books.atualizar_livro_salvo),
                                          ("livros_colorir", books.atualizar_livro_colorir_salvo)])
def test_own_account_can_update_canonical_uri_and_logical_alias(accounts, prefix, update):
    a, _, _, backend = accounts
    path = prefix + "/audit/book.json"
    with access.access_context(a):
        state = book(backend, path)
        reference = storage.storage_uri(path)
        assert update(reference, {**state, "storage_path": path, "text": "own updated"}) == reference
        assert backend.get_json(path)["text"] == "own updated"
        assert update(path, {**state, "storage_path": reference, "text": "logical updated"}) == reference
        assert backend.get_json(path)["book_id"] == state["book_id"]


@pytest.mark.parametrize("who", ["other", "missing", "viewer", "unqualified_uri"])
def test_unauthorized_reference_fails_before_document_or_asset_io(accounts, monkeypatch, who):
    a, b, raw, backend = accounts
    path = "livros/audit/book.json"
    with access.access_context(a):
        state = book(backend, path)
        reference = storage.storage_uri(path)
        before = backend.get_bytes(path)
    actor = {"other": b, "missing": None, "viewer": replace(a, role="viewer"), "unqualified_uri": a}[who]
    if who == "unqualified_uri":
        reference = "fb://" + path
    with monkeypatch.context() as guarded:
        guarded.setattr(raw, "get_bytes", lambda *_: pytest.fail("denied destination read before authorization"))
        forbid_assets(guarded)
        with access.access_context(actor) if actor is not None else nullcontext():
            with pytest.raises(access.AccessDenied):
                books.atualizar_livro_salvo(reference, state)
    with access.access_context(a):
        assert backend.get_bytes(path) == before


def configure_rpc(rpc, monkeypatch):
    backend, database = rpc
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(books, "BACKEND", backend)
    return backend, database


@pytest.mark.parametrize("protect", [False, True])
def test_rpc_conflict_replays_only_guard_and_never_asset_upload(rpc, monkeypatch, protect):
    backend, _ = configure_rpc(rpc, monkeypatch)
    path = "livros/audit/book.json"
    state = book(backend, path)
    uploads, attempts = [], []
    monkeypatch.setattr(books, "persistir_assets_em_objeto", lambda value, _: uploads.append(1) or deepcopy(value))
    original = backend.compare_and_swap_json
    def concurrent(path, revision, value):
        attempts.append(1)
        if len(attempts) == 1:
            other = deepcopy(state)
            if protect:
                other["editorial_product"] = {"execution": {"token": "concurrent-claim"}}
            original(path, revision, other)
        return original(path, revision, value)
    monkeypatch.setattr(backend, "compare_and_swap_json", concurrent)
    if protect:
        with pytest.raises(books.ProtectedBookUpdate):
            books.atualizar_livro_salvo(path, {**state, "text": "received"})
        assert backend.get_json(path)["editorial_product"]["execution"] == {"token": "concurrent-claim"}
        assert attempts == [1]
    else:
        books.atualizar_livro_salvo(path, {**state, "text": "received"})
        assert backend.get_json(path)["text"] == "received"
        assert attempts == [1, 1]
    assert uploads == [1]


def test_lost_rpc_ack_does_not_repeat_or_downgrade_to_unconditional_write(rpc, monkeypatch):
    backend, _ = configure_rpc(rpc, monkeypatch)
    path = "livros/audit/book.json"
    state = book(backend, path)
    uploads, commits = [], []
    monkeypatch.setattr(books, "persistir_assets_em_objeto", lambda value, _: uploads.append(1) or deepcopy(value))
    original = backend.compare_and_swap_json
    def lost_ack(*args):
        commits.append(1)
        original(*args)
        raise storage.StorageUnavailable("confirmation lost")
    monkeypatch.setattr(backend, "compare_and_swap_json", lost_ack)
    monkeypatch.setattr(backend, "put_json", lambda *_: pytest.fail("must not downgrade after lost CAS acknowledgement"))
    with pytest.raises(storage.StorageUnavailable):
        books.atualizar_livro_salvo(path, {**state, "text": "received"})
    assert uploads == commits == [1]
    assert backend.get_json(path)["text"] == "received"


def test_legacy_pilot_uses_explicit_same_host_helper_without_changing_backend_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    backend = LegacyBucket(tmp_path / "data")
    monkeypatch.setattr(books, "BACKEND", backend)
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(storage, "CACHE_DIR", tmp_path / "cache")
    state = book(backend)
    books.atualizar_livro_salvo("livros/audit/book.json", {**state, "text": "same-host pilot"})
    assert backend.get_json("livros/audit/book.json")["text"] == "same-host pilot"
    assert backend.json_concurrency == "read_modify_write_without_cross_worker_CAS"

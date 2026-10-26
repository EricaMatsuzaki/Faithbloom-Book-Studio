"""Profile catalogs and dashboard links preserve concurrent edits and retries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import multiprocessing
from threading import Barrier
from types import SimpleNamespace

import pytest

import author_profiles as authors
import family_profiles as workspace
import storage_backend as storage


def _api(kind):
    if kind == "author":
        return authors, authors.create_author_profile, authors.update_author_profile, authors.get_author_profile
    return workspace, workspace.create_workspace_profile, workspace.update_workspace_profile, workspace.get_workspace_profile


def _create_profiles_worker(root, worker, barrier, count):
    backend = storage.LocalStorageBackend(root)
    authors.BACKEND = backend
    workspace.BACKEND = backend
    barrier.wait(timeout=10)
    for number in range(count):
        name = f"worker-{worker}-{number}"
        authors.create_author_profile(name)
        workspace.create_workspace_profile(name)


@pytest.fixture
def backend(tmp_path, monkeypatch):
    value = storage.LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(authors, "BACKEND", value)
    monkeypatch.setattr(workspace, "BACKEND", value)
    return value


@pytest.mark.parametrize("kind", ["author", "workspace"])
def test_threads_preserve_every_created_profile_in_catalog(backend, kind):
    module, create, _update, _get = _api(kind)
    start = Barrier(3)

    def worker(number):
        start.wait(timeout=5)
        return [create(f"worker-{number}-{i}") for i in range(12)]

    with ThreadPoolExecutor(max_workers=3) as pool:
        batches = list(pool.map(worker, range(3)))
    profiles = [profile for batch in batches for profile in batch]
    rows = backend.get_json(module.INDEX_PATH, [])
    assert {row["id"] for row in rows} == {profile["id"] for profile in profiles}
    assert len(rows) == 36
    assert all(row["profile_version"] == 1 for row in rows)


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="Linux shared-disk workers")
def test_processes_preserve_author_and_workspace_profile_catalogs(tmp_path):
    context = multiprocessing.get_context("fork")
    start = context.Barrier(2)
    workers = [context.Process(target=_create_profiles_worker, args=(str(tmp_path), number, start, 8)) for number in range(2)]
    try:
        for process in workers:
            process.start()
        for process in workers:
            process.join(15)
        assert all(not process.is_alive() and process.exitcode == 0 for process in workers)
    finally:
        for process in workers:
            if process.is_alive():
                process.terminate()
                process.join(5)
    backend = storage.LocalStorageBackend(str(tmp_path))
    expected = {f"worker-{worker}-{number}" for worker in range(2) for number in range(8)}
    for module in (authors, workspace):
        rows = backend.get_json(module.INDEX_PATH, [])
        assert len(rows) == len(expected)
        assert {row["display_name"] for row in rows} == expected
        assert all(backend.get_json(module._profile_path(row["id"]), {})["display_name"] == row["display_name"] for row in rows)


@pytest.mark.parametrize("kind", ["author", "workspace"])
def test_concurrent_disjoint_profile_fields_use_latest_version(backend, kind):
    module, create, update, get = _api(kind)
    profile = create("Pessoa")
    start = Barrier(2)
    fields = ("bio", "website") if kind == "author" else ("default_locale", "default_visual_style")

    def worker(field):
        start.wait(timeout=5)
        for number in range(15):
            update(profile["id"], **{field: f"{field}-{number}"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker, fields))
    saved = get(profile["id"])
    values = saved if kind == "author" else saved["preferences"]
    assert {field: values[field] for field in fields} == {field: f"{field}-14" for field in fields}
    assert saved["version"] == 31
    assert backend.get_json(module.INDEX_PATH, [])[0]["profile_version"] == 31


@pytest.mark.parametrize("kind", ["author", "workspace"])
def test_delayed_summary_cannot_regress_newer_profile_or_duplicate_it(backend, kind):
    module, create, update, _get = _api(kind)
    earlier = create("Antes")
    backend.update_json(module.INDEX_PATH, lambda rows: [{**row, "unknown_field": "preserved"} for row in rows], [])
    newer = update(earlier["id"], display_name="Depois", active=False)
    module._sync_index(earlier)
    rows = backend.get_json(module.INDEX_PATH, [])
    assert len(rows) == 1
    assert rows[0]["display_name"] == "Depois"
    assert rows[0]["active"] is False
    assert rows[0]["profile_version"] == newer["version"] == 2
    assert rows[0]["unknown_field"] == "preserved"


def test_touch_sharing_and_thumbnail_updates_preserve_each_other(backend):
    owner = workspace.create_workspace_profile("Owner")["id"]
    shared = workspace.create_workspace_profile("Shared")["id"]
    added = workspace.create_workspace_profile("Added")["id"]
    path = "livros/c/book.json"
    backend.put_json(path, {"titulo": "Original", "cenas_texto": [{"texto": "Preservar"}]})
    original = backend.get_bytes(path)
    workspace.assign_project(owner, "story", path, shared_profile_ids=[shared])
    start = Barrier(4)

    def worker(action):
        start.wait(timeout=5)
        for number in range(15):
            if action == "sharing":
                workspace.update_project_sharing("story", path, [shared, added])
            elif action == "thumbnail":
                workspace.set_project_thumbnail("story", path, f"thumb-{number}")
            else:
                workspace.touch_project(action, "story", path)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(worker, [owner, shared, "sharing", "thumbnail"]))
    saved = workspace.project_link("story", path)
    assert saved["shared_profile_ids"] == [shared, added]
    assert saved["thumbnail_asset_id"] == "thumb-14"
    assert set(saved["last_opened_by"]) == {owner, shared}
    assert backend.get_bytes(path) == original


def test_concurrent_assignment_keeps_one_link_per_project(backend):
    owner = workspace.create_workspace_profile("Owner")["id"]
    start = Barrier(3)

    def assign(number):
        start.wait(timeout=5)
        return workspace.assign_project(owner, "story", "livros/book.json", title=f"Title-{number}")

    with ThreadPoolExecutor(max_workers=3) as pool:
        links = list(pool.map(assign, range(3)))
    saved = backend.get_json(workspace.PROJECT_LINKS_PATH, [])
    assert len(saved) == 1
    assert {link["id"] for link in links} == {saved[0]["id"]}


class InterleavingBackend(storage.LocalStorageBackend):
    """Execute the real CAS retry loop with one intervening committed edit."""
    def __init__(self, root):
        super().__init__(root)
        self.intervening = None
        self.first_attempt = None

    def update_json(self, path, mutator, default=None, *, max_attempts=5):
        return storage.StorageBackend.update_json(self, path, mutator, default, max_attempts=max_attempts)

    def compare_and_swap_json(self, path, expected_revision, value):
        if self.intervening is not None and path == workspace.PROJECT_LINKS_PATH:
            intervening, self.intervening = self.intervening, None
            self.first_attempt = deepcopy(value)
            storage.LocalStorageBackend.update_json(self, path, intervening, [])
        return super().compare_and_swap_json(path, expected_revision, value)


def test_touch_rechecks_membership_after_concurrent_revocation(tmp_path, monkeypatch):
    backend = InterleavingBackend(str(tmp_path))
    monkeypatch.setattr(workspace, "BACKEND", backend)
    owner = workspace.create_workspace_profile("Owner")["id"]
    guest = workspace.create_workspace_profile("Guest")["id"]
    path = "livros/book.json"
    workspace.assign_project(owner, "story", path, shared_profile_ids=[guest], title="Original")

    def revoke(rows):
        rows[0]["shared_profile_ids"] = []
        return rows

    backend.intervening = revoke
    assert workspace.touch_project(guest, "story", path, title="Unauthorized change") is None
    saved = workspace.project_link("story", path)
    assert saved["shared_profile_ids"] == []
    assert saved["last_opened_by"] == {}
    assert saved["title"] == "Original"


def test_sharing_filters_current_owner_after_retry(tmp_path, monkeypatch):
    backend = InterleavingBackend(str(tmp_path))
    monkeypatch.setattr(workspace, "BACKEND", backend)
    first = workspace.create_workspace_profile("First")["id"]
    second = workspace.create_workspace_profile("Second")["id"]
    workspace.assign_project(first, "story", "livros/book.json")

    def transfer(rows):
        rows[0]["owner_profile_id"] = second
        return rows

    backend.intervening = transfer
    saved = workspace.update_project_sharing("story", "livros/book.json", [first, second])
    assert saved["owner_profile_id"] == second
    assert saved["shared_profile_ids"] == [first]


def test_assignment_reuses_operation_identity_and_timestamp_after_retry(tmp_path, monkeypatch):
    backend = InterleavingBackend(str(tmp_path))
    monkeypatch.setattr(workspace, "BACKEND", backend)
    owner = workspace.create_workspace_profile("Owner")["id"]
    timestamps = iter(["first-operation-time", "unexpected-callback-time"])
    monkeypatch.setattr(workspace, "_now", lambda: next(timestamps))
    backend.intervening = lambda rows: rows + [{"id": "other", "kind": "story", "storage_path": "livros/other.json"}]
    saved = workspace.assign_project(owner, "story", "livros/book.json")
    attempted = next(row for row in backend.first_attempt if row.get("storage_path") == "livros/book.json")
    assert saved["id"] == attempted["id"]
    assert saved["created_at"] == attempted["created_at"] == "first-operation-time"
    assert saved["updated_at"] == "first-operation-time"
    assert len(backend.get_json(workspace.PROJECT_LINKS_PATH, [])) == 2


def test_missing_or_unauthorized_touch_performs_no_write(backend):
    assert workspace.touch_project("unknown", "story", "livros/missing.json") is None
    assert not backend.exists(workspace.PROJECT_LINKS_PATH)
    owner = workspace.create_workspace_profile("Owner")["id"]
    workspace.assign_project(owner, "story", "livros/book.json")
    before = backend.get_bytes(workspace.PROJECT_LINKS_PATH)
    assert workspace.touch_project("unknown", "story", "livros/book.json") is None
    assert backend.get_bytes(workspace.PROJECT_LINKS_PATH) == before


@pytest.mark.parametrize("kind", ["author", "workspace"])
def test_legacy_supabase_profile_pilot_remains_compatible(monkeypatch, kind):
    objects = {}
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake")
    module, create, update, get = _api(kind)
    monkeypatch.setattr(module, "BACKEND", backend)

    def path_for(url):
        assert "/storage/v1/object/faithbloom/" in url
        return url.split("/storage/v1/object/faithbloom/", 1)[1]

    def read(url, **kwargs):
        path = path_for(url)
        return SimpleNamespace(status_code=200, content=objects[path]) if path in objects else SimpleNamespace(status_code=404, content=b"")

    def write(url, **kwargs):
        objects[path_for(url)] = kwargs["data"]
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(storage.requests, "get", read)
    monkeypatch.setattr(storage.requests, "post", write)
    profile = create("Antes")
    update(profile["id"], display_name="Depois")
    assert get(profile["id"])["display_name"] == "Depois"
    assert backend.get_json(module.INDEX_PATH, [])[0]["profile_version"] == 2
    assert backend.json_concurrency == "read_modify_write_without_cross_worker_CAS"


@pytest.mark.parametrize("kind", ["author", "workspace"])
def test_profile_rpc_failure_never_uploads_legacy_document(monkeypatch, kind):
    calls = []

    def unavailable(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(status_code=404, text="private-response")

    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    monkeypatch.setattr(storage.requests, "post", unavailable)
    monkeypatch.setattr(storage.requests, "get", lambda *args, **kwargs: pytest.fail("RPC failure cannot try legacy reads"))
    backend = storage.SupabaseStorageBackend("https://example.supabase.co", "sb_secret_fake", json_mode="rpc_cas")
    module, _create, update, _get = _api(kind)
    monkeypatch.setattr(module, "BACKEND", backend)
    with pytest.raises(storage.StorageUnavailable):
        update("existing-id", display_name="Depois")
    assert len(calls) == 1
    assert "/rest/v1/rpc/" in calls[0]

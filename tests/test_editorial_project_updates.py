from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, Event
from unittest.mock import Mock

import pytest

import editorial_products as products
import editorial_generation_runtime as runtime
import editorial_project_updates as edits
import storage_backend as storage
from test_editorial_generation_atomic import durable, product, provider


def completed():
    value = product()
    products.generate_product(value, provider, confirmed=True)
    return value


def test_product_metadata_merges_independent_observed_fields_without_rebuying(durable):
    source = completed()
    first = edits.load_metadata_snapshot(source["storage_path"])
    second = edits.load_metadata_snapshot(source["storage_path"])
    before = deepcopy(first["baseline"]["editorial_product"])
    edits.update_metadata_fields(first, {"authorship": {"authors": [{"name": "Erica"}]}, "autora": "Erica"})
    result = edits.update_metadata_fields(second, {"agent_skill_audit": {"ok": True}})
    saved = result["baseline"]
    assert saved["authorship"]["authors"][0]["name"] == "Erica"
    assert saved["agent_skill_audit"] == {"ok": True}
    assert saved["editorial_product"]["units"] == before["units"]
    assert saved["editorial_product"]["execution"]["attempts"] == before["execution"]["attempts"]
    assert saved["editorial_product"]["execution"]["revision"] == before["execution"]["revision"] + 2
    paid = Mock(side_effect=AssertionError("metadata cannot require another generation"))
    products.generate_product(products.load_product(source["storage_path"]), paid, confirmed=True)
    paid.assert_not_called()


def test_two_editors_of_the_same_field_have_one_winner_and_no_silent_overwrite(durable):
    source = completed()
    snapshots = [edits.load_metadata_snapshot(source["storage_path"]) for _ in range(2)]
    start = Barrier(2)
    def save(index):
        start.wait(5)
        try:
            edits.update_metadata_fields(snapshots[index], {"market_evidence": [{"source": str(index)}]})
            return index
        except edits.ProjectMetadataConflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, range(2)))
    winners = [value for value in results if value is not None]
    assert len(winners) == 1
    assert edits.load_metadata_snapshot(source["storage_path"])["baseline"]["market_evidence"] == [{"source": str(winners[0])}]


def test_claim_acquired_during_asset_preparation_is_not_erased(durable, monkeypatch):
    source = product()
    snapshot = edits.load_metadata_snapshot(source["storage_path"])
    entered, release = Event(), Event()
    paid = Mock(side_effect=lambda **kw: (entered.set(), release.wait(10), provider(**kw))[-1])
    prepare = storage.persistir_assets_em_objeto
    future = None
    with ThreadPoolExecutor(max_workers=1) as pool:
        def assets(value, prefix):
            nonlocal future
            if not prefix.startswith("assets/project_metadata/") or future is not None:
                return prepare(value, prefix)
            # This boundary represents another session starting a paid job after
            # metadata preflight and before the transactional field merge.
            future = pool.submit(products.generate_product, source, paid, confirmed=True)
            assert entered.wait(5)
            return deepcopy(value)
        monkeypatch.setattr(storage, "persistir_assets_em_objeto", assets)
        try:
            with pytest.raises(PermissionError, match="geração"):
                edits.update_metadata_fields(snapshot, {"authorship": {"authors": []}})
            current = durable.get_json(runtime._path(source["storage_path"]))
            assert current["editorial_product"]["execution"]["claim"]
            assert current.get("authorship") == snapshot["baseline"].get("authorship")
        finally:
            monkeypatch.setattr(storage, "persistir_assets_em_objeto", prepare)
            release.set()
        future.result(10)
    assert paid.call_count == 1


@pytest.mark.parametrize("state,status", [("running", "running"), ("uncertain", "needs_reconciliation"), ("raw", "save_failed")])
def test_unresolved_attempts_veto_metadata_before_upload(durable, monkeypatch, state, status):
    source = completed()
    path = runtime._path(source["storage_path"])
    current = durable.get_json(path)
    execution = current["editorial_product"]["execution"]
    execution["attempts"][0]["state"] = state
    if state == "raw":
        execution["attempts"][0]["response"] = {"received": True}
    execution["status"] = status
    execution["claim"] = ({"token": "active", "host": "host", "pid": 123, "owner_active": True} if state == "running" else None)
    durable.put_json(path, current)
    snapshot = edits.load_metadata_snapshot(source["storage_path"])
    upload = Mock(side_effect=AssertionError("veto must precede asset work"))
    monkeypatch.setattr(storage, "persistir_assets_em_objeto", upload)
    assert edits.metadata_edit_status(snapshot)["allowed"] is False
    with pytest.raises(PermissionError):
        edits.update_metadata_fields(snapshot, {"agent_skill_audit": {"ok": True}})
    upload.assert_not_called()
    assert durable.get_json(path) == current


def test_missing_and_null_fields_differ_and_source_watch_prevents_stale_report(durable):
    source = completed()
    snapshot = edits.load_metadata_snapshot(source["storage_path"])
    path = runtime._path(source["storage_path"])
    current = durable.get_json(path)
    current["market_evidence"] = None
    current["cenas_texto"][0]["texto"] += " Texto revisado."
    durable.put_json(path, current)
    with pytest.raises(edits.ProjectMetadataConflict):
        edits.update_metadata_fields(snapshot, {"market_evidence": []})
    with pytest.raises(edits.ProjectMetadataConflict):
        edits.update_metadata_fields(snapshot, {"bestseller_readiness_report": {"ok": True}}, watched_fields=("cenas_texto",))
    assert durable.get_json(path) == current


def test_callbacks_replay_without_repeating_asset_work(durable, monkeypatch, tmp_path):
    source = completed()
    snapshot = edits.load_metadata_snapshot(source["storage_path"])
    original = durable.update_json
    report_image = tmp_path / "report.png"
    report_image.write_bytes(b"report-image")
    uploads = Mock(wraps=storage.persistir_arquivo)
    monkeypatch.setattr(storage, "persistir_arquivo", uploads)
    def replay(path, callback, default=None, **kw):
        before = durable.get_json(path, default)
        callback(deepcopy(before))
        callback(deepcopy(before))
        return original(path, callback, default, **kw)
    monkeypatch.setattr(durable, "update_json", replay)
    saved = edits.update_metadata_fields(snapshot, {"agent_skill_audit": {"ok": True, "report_image": str(report_image)}})
    assert saved["baseline"]["agent_skill_audit"]["ok"]
    assert uploads.call_count == 1
    image_ref = saved["baseline"]["agent_skill_audit"]["report_image"]
    assert durable.get_bytes(storage.uri_to_path(image_ref)) == b"report-image"


def test_metadata_cannot_replace_paid_ledger_or_book_identity(durable):
    source = completed()
    snapshot = edits.load_metadata_snapshot(source["storage_path"])
    before = durable.get_bytes(runtime._path(source["storage_path"]))
    with pytest.raises(ValueError):
        edits.update_metadata_fields(snapshot, {"editorial_product": {}})
    with pytest.raises(PermissionError):
        edits.update_metadata_fields(snapshot, {"book_id": "another-book"})
    assert durable.get_bytes(runtime._path(source["storage_path"])) == before

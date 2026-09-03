from pathlib import Path

import pytest
from PIL import Image

import armazenamento
import asset_library
import storage_backend
from storage_backend import LocalStorageBackend, storage_uri


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    backend = LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage_backend, "BACKEND", backend)
    monkeypatch.setattr(armazenamento, "BACKEND", backend)
    monkeypatch.setattr(asset_library, "BACKEND", backend)
    cache = tmp_path / "cache"; cache.mkdir()
    monkeypatch.setattr(storage_backend, "CACHE_DIR", cache)
    # asset_library imported materializar by reference; it still reads storage_backend.BACKEND at runtime.
    return backend, tmp_path


def png(path: Path, size=(120, 80), color=(240, 220, 200)):
    Image.new("RGB", size, color).save(path)
    return path


def test_legacy_gallery_migrates_without_losing_fields(isolated):
    backend, _ = isolated
    backend.put_json("galeria/index.json", [{"id":"a1","nome":"Mel","tipo":"personagem","tags":["Mel"],"storage_uri":"fb://assets/galeria/x.png"}])
    out = asset_library.migrate_gallery_index()
    assert out["assets"] == 1
    item = asset_library.get_asset("a1", materialize_file=False)
    assert item["asset_schema_version"] == 2
    assert item["status"] == "active"
    assert item["version_group"] == "a1"
    assert item["nome"] == "Mel"


def test_search_combines_metadata_and_tokens(isolated):
    backend, _ = isolated
    backend.put_json("galeria/index.json", [
        {"id":"a","nome":"Mel na neve","tipo":"cena","tags":["Natal"],"metadata":{"personagem":"Mel","colecao":"Pequenas Histórias","estacao":"inverno"},"storage_uri":"fb://assets/galeria/a.png"},
        {"id":"b","nome":"Girafa","tipo":"line_art","tags":["animal"],"metadata":{"colecao":"Bolufinhas"},"storage_uri":"fb://assets/galeria/b.png"},
    ])
    r = asset_library.list_assets({"q":"Mel Natal inverno", "status":None}, page_size=20)
    assert r["total"] == 1 and r["items"][0]["id"] == "a"
    r2 = asset_library.list_assets({"colecao":"Bolufinhas","status":None}, page_size=20)
    assert [x["id"] for x in r2["items"]] == ["b"]


def test_virtual_collections_do_not_duplicate_asset(isolated):
    backend, _ = isolated
    backend.put_json("galeria/index.json", [{"id":"a","nome":"Mel","storage_uri":"fb://assets/galeria/a.png"}])
    col = asset_library.create_virtual_collection("Mel — Natal")
    assert asset_library.add_to_collection(["a"], col["id"]) == 1
    assert asset_library.add_to_collection(["a"], col["id"]) == 0
    item = asset_library.get_asset("a", materialize_file=False)
    assert item["virtual_collections"] == [col["id"]]
    assert len(backend.get_json("galeria/index.json", [])) == 1


def test_versions_share_group_and_preserve_original(isolated):
    backend, _ = isolated
    backend.put_json("galeria/index.json", [{"id":"a","nome":"Cena 12","storage_uri":"fb://assets/galeria/a.png","version_group":"a"}])
    v = asset_library.create_version("a", storage_uri_value="fb://assets/galeria/b.png", version_label="Versão B")
    versions = asset_library.versions_for(v["id"])
    assert len(versions) == 2
    assert versions[0]["id"] == "a"
    assert versions[1]["parent_asset_id"] == "a"


def test_usage_scan_finds_asset_reference_in_project(isolated):
    backend, _ = isolated
    backend.put_json("galeria/index.json", [{"id":"a","nome":"Mel","storage_uri":"fb://assets/galeria/hash.png"}])
    backend.put_json("livros/colecao/livro.json", {"titulo":"Livro da Mel","cenas":[{"imagem":"fb://assets/galeria/hash.png"}]})
    result = asset_library.scan_usage("a")
    assert any(x["project_title"] == "Livro da Mel" for x in result["records"])
    assert any("cenas" in x["location"] for x in result["records"])


def test_duplicate_groups_detect_content_addressed_uri(isolated):
    backend, _ = isolated
    digest="0123456789abcdefabcd"
    backend.put_json("galeria/index.json", [
        {"id":"a","nome":"A","storage_uri":f"fb://assets/galeria/{digest}.png"},
        {"id":"b","nome":"B","storage_uri":f"fb://assets/other/{digest}.png"},
    ])
    groups = asset_library.duplicate_groups()
    assert len(groups) == 1
    assert groups[0]["count"] == 2


def test_archive_hides_from_default_listing_but_does_not_delete(isolated):
    backend, _ = isolated
    backend.put_json("galeria/index.json", [{"id":"a","nome":"A","storage_uri":"fb://assets/galeria/a.png"}])
    asset_library.set_archived("a", True)
    assert asset_library.list_assets({})["total"] == 0
    assert asset_library.list_assets({"status":"archived"})["total"] == 1
    assert asset_library.get_asset("a", materialize_file=False) is not None


def test_master_and_usage_block_permanent_delete(isolated):
    backend, _ = isolated
    backend.put_json("galeria/index.json", [{"id":"a","nome":"Mel","storage_uri":"fb://assets/galeria/a.png","master_roles":["character_master"]}])
    allowed, reason = asset_library.permanent_delete_allowed("a", {"records":[]})
    assert not allowed and "Master" in reason
    asset_library.update_asset("a", master_roles=[])
    backend.put_json("livros/teste.json", {"titulo":"Uso","ref":"fb://assets/galeria/a.png"})
    allowed2, _ = asset_library.permanent_delete_allowed("a")
    assert not allowed2


def test_thumbnail_and_technical_metadata(isolated):
    backend, tmp = isolated
    p = png(tmp / "img.png", (800, 600))
    data=p.read_bytes(); backend.put_bytes("assets/galeria/0123456789abcdefabcd.png",data,"image/png")
    backend.put_json("galeria/index.json", [{"id":"a","nome":"Imagem","storage_uri":"fb://assets/galeria/0123456789abcdefabcd.png","media_kind":"image"}])
    out=asset_library.backfill_technical_metadata(["a"], limit=1)
    assert out["processed"] == 1
    item=asset_library.get_asset("a", materialize_file=False)
    assert item["metadata"]["width_px"] == 800
    assert item["metadata"]["height_px"] == 600
    thumb=asset_library.get_thumbnail("a", 240)
    assert thumb and Path(thumb).exists()
    with Image.open(thumb) as im:
        assert max(im.size) <= 240


def test_batch_update_and_stats(isolated):
    backend, _ = isolated
    backend.put_json("galeria/index.json", [
        {"id":"a","nome":"A","storage_uri":"fb://assets/galeria/a.png","metadata":{"file_size_bytes":100}},
        {"id":"b","nome":"B","storage_uri":"fb://assets/galeria/b.png","metadata":{"file_size_bytes":200}},
    ])
    assert asset_library.batch_update(["a","b"], favorite=True, add_tags=["Natal"]) == 2
    stats=asset_library.library_stats()
    assert stats["favorites"] == 2
    assert stats["known_bytes"] == 300
    assert all("Natal" in asset_library.get_asset(x,False)["tags"] for x in ["a","b"])


def test_permanent_delete_blocks_shared_physical_file(isolated):
    backend, _ = isolated
    backend.put_json("galeria/index.json", [
        {"id":"a","nome":"A","storage_uri":"fb://assets/galeria/shared.png"},
        {"id":"b","nome":"B","storage_uri":"fb://assets/galeria/shared.png"},
    ])
    allowed, reason = asset_library.permanent_delete_allowed("a", {"records":[]})
    assert not allowed
    assert "outro registro" in reason

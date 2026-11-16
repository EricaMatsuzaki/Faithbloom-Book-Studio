"""Shared exporters authorize destinations and source media across two accounts."""
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import shutil
import zipfile

from PIL import Image
from pypdf import PdfReader
import pytest

import epub_exporter as epub
import publishing_distribution as distribution
import renderizador_editorial as renderer
import saas_access as access
import storage_backend as storage


@pytest.fixture
def tenants(tmp_path, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "multi_tenant")
    monkeypatch.setenv("FAITHBLOOM_OIDC_ISSUERS", "https://identity.example")
    monkeypatch.delenv("FAITHBLOOM_ACCESS_ROLES", raising=False)
    actors = [access.actor_from_trusted_claims({
        "authenticated": True, "iss": "https://identity.example", "sub": account,
    }) for account in ("account-a", "account-b")]
    cache = tmp_path / "cache"
    roots = [cache / "tenants" / actor.tenant_id / "outputs" for actor in actors]
    for root in roots:
        root.mkdir(parents=True)
    raw = storage.LocalStorageBackend(str(tmp_path / "durable"))
    backend = storage.TenantStorageBackend(raw)
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    monkeypatch.setattr(storage, "BACKEND", backend)
    monkeypatch.setattr(distribution, "BACKEND", backend)
    monkeypatch.chdir(tmp_path)
    return actors, roots, raw


def book(media=None):
    state = {
        "book_id": "master-book", "titulo": "Mel no jardim", "autora": "Autora",
        "idioma_original": "pt-BR", "faixa_etaria": "6-8",
        "trim_largura_in": 6, "trim_altura_in": 9,
        "cenas_texto": [{"numero": 1, "texto": "Mel cuidou da semente com alegria."}],
        "layout_paginas": [
            {"pagina": 1, "tipo": "rosto"}, {"pagina": 2, "tipo": "creditos"},
            {"pagina": 3, "tipo": "texto", "cena_numero": 1},
            {"pagina": 4, "tipo": "imagem", "cena_numero": 1},
            *[{"pagina": n, "tipo": "pagina_em_branco"} for n in range(5, 25)],
        ],
    }
    if media:
        # The print renderer and EPUB engine support their respective existing
        # image contracts; both references must remain unchanged in the Master.
        state["cenas_imagem"] = [{"numero": 1, "caminho_arquivo": media, "arquivo": media}]
        state["capa_ebook"] = media
    return state


def plan(epub_path=None, cover=None):
    return {
        "quality_gate": {"passed": True, "certificate_id": "reviewed-version"},
        "ai_disclosure": {"recorded": True},
        "editions": [{
            "edition_id": "edition-pt", "readiness": "ready", "platform_id": "amazon_kdp",
            "platform_name": "Amazon KDP", "product": "ebook", "locale": "pt-BR",
            "master": {"language": "pt-BR"}, "metadata": {"titulo": "Mel no jardim"},
            "preflight": {"ready": True}, "specification": {"version": "reviewed"},
            "assets": {"epub": epub_path, "cover_ebook": cover},
        }],
    }


def export(kind, state, destination, package_plan=None):
    if kind == "pdf":
        return renderer.renderizar_miolo_pdf(state, destino=destination, bleed=False, forcar=True)
    if kind == "epub":
        return epub.export_epub(state, destination)
    return distribution.build_channel_package(state, package_plan or plan(), "edition-pt", destination)


def forbid_content_and_creation(monkeypatch, raw, *, forbid_epub_builder=False):
    def forbidden(*args, **kwargs):
        pytest.fail("Denied operation reached content reads, preflight, or output creation")
    monkeypatch.setattr(raw, "get_bytes", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(renderer, "_registrar_fontes", forbidden)
    monkeypatch.setattr(renderer, "preflight_livro", forbidden)
    monkeypatch.setattr(renderer.canvas, "Canvas", forbidden)
    monkeypatch.setattr(Image, "open", forbidden)
    monkeypatch.setattr(shutil, "copy2", forbidden)
    monkeypatch.setattr(zipfile, "ZipFile", forbidden)
    if forbid_epub_builder:
        monkeypatch.setattr(epub, "_image_items", forbidden)


@pytest.mark.parametrize("kind", ["pdf", "epub", "distribution"])
@pytest.mark.parametrize("failure", ["foreign", "traversal", "symlink", "viewer", "missing"])
def test_destination_denied_before_preflight_media_canvas_or_mkdir(
    tenants, monkeypatch, kind, failure,
):
    (a, _), (own, foreign), raw = tenants
    link = own / "foreign-link"
    link.symlink_to(foreign, target_is_directory=True)
    destinations = {
        "foreign": foreign / "private-export",
        "traversal": own / ".." / "outputs" / "escape",
        "symlink": link / "private-export",
        "viewer": own / "blocked-export",
        "missing": own / "blocked-export",
    }
    with monkeypatch.context() as guard:
        forbid_content_and_creation(guard, raw, forbid_epub_builder=True)
        if failure == "missing":
            with pytest.raises(access.AccessDenied):
                export(kind, book(), str(destinations[failure]))
        else:
            actor = replace(a, role="viewer") if failure == "viewer" else a
            with access.access_context(actor), pytest.raises(access.AccessDenied):
                export(kind, book(), str(destinations[failure]))
    assert not list(foreign.iterdir())
    assert not (own / "blocked-export").exists()


@pytest.mark.parametrize("kind", ["pdf", "epub", "distribution"])
@pytest.mark.parametrize("reference", ["local", "uri"])
def test_foreign_source_denied_before_reads_or_partial_export(
    tenants, monkeypatch, kind, reference,
):
    (a, b), (own, foreign), raw = tenants
    secret = foreign / "private.png"
    secret.write_bytes(b"tenant-b-private-master")
    with access.access_context(b):
        storage.BACKEND.put_bytes("assets/private.png", secret.read_bytes())
        secret_uri = storage.storage_uri("assets/private.png")
    source = str(secret) if reference == "local" else secret_uri
    # Distribution resolves a harmless first selection, then a foreign cover.
    # It must not copy even the first selection before rejecting the cover.
    own_book = own / "book.epub"
    own_book.write_bytes(b"existing-own-export")
    package_plan = plan(str(own_book), source)
    state = book(source)
    before = deepcopy(state)
    destination = own / "new-export" / ("book.pdf" if kind == "pdf" else "book.epub")
    with monkeypatch.context() as guard:
        forbid_content_and_creation(guard, raw)
        with access.access_context(a), pytest.raises(access.AccessDenied):
            export(kind, state, str(destination), package_plan)
    assert state == before
    assert not destination.parent.exists()
    assert secret.read_bytes() == b"tenant-b-private-master"
    assert own_book.read_bytes() == b"existing-own-export"


@pytest.mark.parametrize("reference", ["local", "uri"])
def test_epub_inspection_denies_foreign_input_before_opening_archive(tenants, monkeypatch, reference):
    (a, b), (_, foreign), raw = tenants
    secret = foreign / "private.epub"
    secret.write_bytes(b"private-book")
    with access.access_context(b):
        storage.BACKEND.put_bytes("assets/private.epub", b"private-book")
        secret_uri = storage.storage_uri("assets/private.epub")
    with monkeypatch.context() as guard:
        forbid_content_and_creation(guard, raw)
        with access.access_context(a), pytest.raises(access.AccessDenied):
            epub.inspect_epub(str(secret) if reference == "local" else secret_uri)


def test_output_resolver_scopes_defaults_without_mkdir_and_reauthorizes_existing_paths(tenants, monkeypatch):
    (a, b), (own, foreign), _ = tenants
    with monkeypatch.context() as guard:
        guard.setattr(Path, "mkdir", lambda *a, **k: pytest.fail("Resolving a path created directories"))
        with access.access_context(a):
            path = storage.resolve_local_output(default_path="reports/new/book.pdf")
            assert Path(path) == own / "reports/new/book.pdf"
            assert storage.resolve_local_output(path, default_path="unused") == path
        with access.access_context(b), pytest.raises(access.AccessDenied):
            storage.resolve_local_output(path, default_path="unused")
        with access.access_context(replace(a, role="viewer")), pytest.raises(access.AccessDenied):
            storage.resolve_local_output(path, default_path="unused")
        with pytest.raises(access.AccessDenied):
            storage.resolve_local_output(path, default_path="unused")
    assert not (own / "reports").exists()
    assert not list(foreign.iterdir())


@pytest.mark.parametrize("account", [0, 1], ids=["account-a", "account-b"])
def test_real_own_exports_and_rebuilt_packages_preserve_masters_and_unrelated_files(tenants, account):
    actors, roots, _ = tenants
    own, foreign = roots[account], roots[1 - account]
    with access.access_context(actors[account]):
        png = BytesIO()
        Image.new("RGB", (1800, 2700), "green").save(png, format="PNG")
        master = own / "master.png"
        master.write_bytes(png.getvalue())
        master_uri = storage.persistir_arquivo(str(master), "assets/masters")
        state = book(master_uri)
        original = deepcopy(state)
        pdf = renderer.renderizar_miolo_pdf(state, bleed=False, forcar=True)
        assert pdf["ok"] and not pdf["avisos"] and pdf["paginas"] == 24
        assert own in Path(pdf["caminho"]).parents
        reader = PdfReader(pdf["caminho"])
        assert "Mel cuidou da semente" in reader.pages[2].extract_text()
        assert len(reader.pages[3].images) == 1
        exported = epub.export_epub(state, None)
        assert own in Path(exported["path"]).parents
        assert exported["images"] == 1 and exported["cover_included"]
        epub_uri = storage.persistir_arquivo(exported["path"], "assets/exports")
        assert epub.inspect_epub(epub_uri)["ok"]
        package_plan = plan(epub_uri, master_uri)
        package = distribution.build_channel_package(state, package_plan, "edition-pt")
        folder, archive = Path(package["folder"]), Path(package["zip"])
        assert own in folder.parents and own in archive.parents
        assert (folder / "FILES/book.epub").read_bytes() == Path(exported["path"]).read_bytes()
        assert (folder / "FILES/cover.png").read_bytes() == master.read_bytes()
        stale = folder / "FILES/stale.epub"
        stale.write_bytes(b"old-unselected-edition")
        unrelated = folder / "author-notes.txt"
        unrelated.write_text("Preserve these private notes")
        sibling = folder.parent / "another-channel.txt"
        sibling.write_bytes(b"unrelated-channel")
        package_plan["editions"][0]["assets"]["cover_ebook"] = None
        distribution.build_channel_package(state, package_plan, "edition-pt")
        with zipfile.ZipFile(archive) as zipped:
            names = zipped.namelist()
            assert len(names) == len(set(names)) == 7
            assert any(name.endswith("/FILES/book.epub") for name in names)
            assert not any(name.endswith(("stale.epub", "cover.png", "author-notes.txt", "another-channel.txt")) for name in names)
        assert stale.read_bytes() == b"old-unselected-edition"
        assert unrelated.read_text() == "Preserve these private notes"
        assert sibling.read_bytes() == b"unrelated-channel"
        assert (folder / "FILES/cover.png").read_bytes() == png.getvalue()
        assert master.read_bytes() == png.getvalue()
        assert state == original
    assert not list(foreign.iterdir())


def test_pilot_default_export_paths_and_explicit_strings_are_preserved(tenants, monkeypatch):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    assert storage.resolve_local_output("custom/../book.pdf", default_path="unused") == "custom/../book.pdf"
    state = book()
    pdf = renderer.renderizar_miolo_pdf(state, bleed=False, forcar=True)
    assert pdf["caminho"] == "exportacoes_kdp/mel-no-jardim-miolo-print-ready.pdf"
    assert Path(pdf["caminho"]).read_bytes().startswith(b"%PDF")
    exported = epub.export_epub(state, None)
    assert exported["path"] == "exportacoes_epub/book.epub"
    assert epub.inspect_epub(exported["path"])["ok"]
    package = distribution.build_channel_package(state, plan(exported["path"]), "edition-pt")
    assert package["folder"] == "saida_distribuicao/mel-no-jardim/amazon_kdp__ebook__pt-br"
    assert package["zip"] == package["folder"] + ".zip"
    assert Path(package["zip"]).exists()


@pytest.mark.parametrize("kind", ["pdf", "epub", "distribution"])
def test_export_destination_cannot_overwrite_its_master_source(tenants, monkeypatch, kind):
    (a, _), (own, _), raw = tenants
    if kind == "distribution":
        destination = own / "packages"
        master = destination / "mel-no-jardim/amazon_kdp__ebook__pt-br/FILES/cover.png"
        master.parent.mkdir(parents=True)
    else:
        master = own / "master.png"
        destination = master
    master.write_bytes(b"master-must-remain-unchanged")
    state = book(str(master))
    original = deepcopy(state)
    with monkeypatch.context() as guard:
        forbid_content_and_creation(guard, raw)
        with access.access_context(a), pytest.raises(ValueError, match="preservar"):
            export(kind, state, str(destination), plan(None, str(master)))
    assert master.read_bytes() == b"master-must-remain-unchanged"
    assert state == original

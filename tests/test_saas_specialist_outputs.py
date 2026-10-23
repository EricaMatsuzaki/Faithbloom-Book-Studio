"""Specialist exports authorize destinations before building or reading content."""
from dataclasses import replace
from pathlib import Path
import zipfile

import pytest

import comic_studio
import editorial_products
import saas_access as access
import storage_backend as storage


STUDIOS = [
    pytest.param(comic_studio, "export_comic", "_typeset_layout", id="comic"),
    pytest.param(editorial_products, "export_product", "build_export_state", id="editorial"),
]


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
    monkeypatch.setattr(storage, "BACKEND", storage.TenantStorageBackend(raw))
    monkeypatch.setattr(storage, "CACHE_DIR", cache)
    monkeypatch.chdir(tmp_path)
    return actors, roots, raw


def forbid_export_io(monkeypatch, module, builder):
    def forbidden(*args, **kwargs):
        pytest.fail("Denied export reached content building or filesystem I/O")
    monkeypatch.setattr(module, builder, forbidden)
    monkeypatch.setattr(storage, "persistir_arquivo", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)


@pytest.mark.parametrize("module,exporter,builder", STUDIOS)
@pytest.mark.parametrize("format", ["pdf", "epub"])
@pytest.mark.parametrize("destination", ["foreign", "outside", "traversal", "symlink"])
def test_foreign_or_escaping_destinations_deny_before_build_and_io(
    tenants, tmp_path, monkeypatch, module, exporter, builder, format, destination,
):
    (a, b), (own, foreign), _ = tenants
    existing = foreign / f"private.{format}"
    existing.write_bytes(b"tenant-b-private-export")
    link = own / "foreign-link"
    link.symlink_to(foreign, target_is_directory=True)
    paths = {
        "foreign": existing,
        "outside": tmp_path / f"outside.{format}",
        "traversal": own / ".." / "outputs" / f"escape.{format}",
        "symlink": link / f"private.{format}",
    }
    with monkeypatch.context() as guard:
        forbid_export_io(guard, module, builder)
        with access.access_context(a), pytest.raises(access.AccessDenied):
            getattr(module, exporter)({"book_id": "book-a"}, format,
                                      output_path=str(paths[destination]), draft=True)
    assert existing.read_bytes() == b"tenant-b-private-export"
    assert not (tmp_path / f"outside.{format}").exists()


@pytest.mark.parametrize("module,exporter,builder", STUDIOS)
@pytest.mark.parametrize("format", ["pdf", "epub"])
@pytest.mark.parametrize("identity", ["missing", "viewer"])
@pytest.mark.parametrize("explicit", [False, True])
def test_missing_actor_and_viewer_cannot_export_before_build_and_io(
    tenants, monkeypatch, module, exporter, builder, format, identity, explicit,
):
    (a, _), (own, _), _ = tenants
    forbid_export_io(monkeypatch, module, builder)
    kwargs = {"output_path": str(own / f"blocked.{format}")} if explicit else {}

    def export():
        with pytest.raises(access.AccessDenied):
            getattr(module, exporter)({"book_id": "book-a"}, format, draft=True, **kwargs)

    if identity == "viewer":
        with access.access_context(replace(a, role="viewer")):
            export()
    else:
        export()


def comic_project():
    source = {
        "book_id": "source-book", "titulo": "Aprender a esperar", "faixa_etaria": "6-8",
        "idioma_original": "pt-BR", "personagens": {},
        "cenas_texto": [{"numero": 1, "texto": "Mel cuida da semente com calma."}],
    }
    script = {"titulo": "A semente", "paginas": [{"numero": 1, "paineis": [{
        "numero": 1, "acao_visual": "Mel observa uma semente no jardim.",
        "dialogos": [{"personagem": "Mel", "fala": "Vou cuidar de você!"}],
        "narracao": "Esperar também é cuidado.", "sfx": "Plim!",
        "emocao": "curiosidade", "personagem_foco": "Mel",
    }]}]}
    return comic_studio.create_comic(source, script=script)


@pytest.mark.parametrize("format", ["pdf", "epub"])
@pytest.mark.parametrize("alias", [False, True], ids=["same-path", "hard-link"])
def test_comic_export_preserves_original_panel_bytes(tenants, format, alias):
    from PIL import Image
    (actor, _), (own, _), _ = tenants
    panel = own / "original-panel.png"
    Image.new("RGB", (600, 450), "orange").save(panel)
    original = panel.read_bytes()
    output = panel
    if alias:
        output = own / f"output.{format}"
        output.hardlink_to(panel)
    with access.access_context(actor):
        project = comic_project()
        comic_studio._attach_results(project, "1:1", [{
            "asset_id": "legacy-local-panel", "storage_uri": str(panel), "approved": False}])
        with pytest.raises(ValueError, match="preservar"):
            comic_studio.export_comic(project, format, output_path=str(output), draft=True,
                                      checkpoint=lambda _: pytest.fail("No checkpoint after a rejected destination"))
    assert panel.read_bytes() == original
    assert output.read_bytes() == original


def editorial_project():
    project = editorial_products.create_product(
        "children_advice", "A vez de falar", "Aprender a ouvir com atenção", unit_count=1,
    )
    meta = project["editorial_product"]
    meta["units"] = [editorial_products.validate_unit({
        "title": "Ouvir com atenção", "objectives": ["Respeitar a vez de falar"],
        "source_refs": [], "situation": "Uma amiga está contando uma história.",
        "advice": "Espere a amiga terminar antes de falar.",
        "reflection": "Como você se sente quando alguém escuta?",
        "activity": "Pratique uma conversa com alguém de confiança.",
    }, meta["unit_plan"][0], meta["spec"])]
    meta["active_version"] = "review-draft"
    return project


def make_project(module):
    return comic_project() if module is comic_studio else editorial_project()


@pytest.mark.parametrize("module,exporter,builder", STUDIOS)
@pytest.mark.parametrize("format", ["pdf", "epub"])
@pytest.mark.parametrize("explicit", [False, True])
def test_real_own_tenant_exports_remain_durable_and_isolated(
    tenants, module, exporter, builder, format, explicit,
):
    (a, b), (own, foreign), raw = tenants
    with access.access_context(a):
        project = make_project(module)
        kwargs = {"output_path": str(own / "custom" / f"review.{format}")} if explicit else {}
        result = getattr(module, exporter)(project, format, draft=True,
                                           checkpoint=lambda _: None, **kwargs)
        path = Path(result["path"])
        assert own in path.parents
        if explicit:
            assert path == own / "custom" / f"review.{format}"
        content = path.read_bytes()
        assert content.startswith(b"%PDF" if format == "pdf" else b"PK")
        assert storage.BACKEND.get_bytes(storage.uri_to_path(result["storage_ref"])) == content
        if format == "epub":
            with zipfile.ZipFile(path) as archive:
                body = archive.read("EPUB/page_001.xhtml" if module is comic_studio else "EPUB/book.xhtml").decode()
                assert "RASCUNHO" in body
                assert ("Vou cuidar de você!" if module is comic_studio else "Ouvir com atenção") in body
    assert not list(foreign.iterdir())
    with access.access_context(b), pytest.raises(access.AccessDenied):
        storage.materializar(result["storage_ref"])
    assert raw.get_bytes(result["storage_ref"].removeprefix("fb://")) == content


@pytest.mark.parametrize("module,exporter,builder", STUDIOS)
@pytest.mark.parametrize("explicit", [False, True])
def test_pilot_preserves_default_layout_and_explicit_path(
    tenants, tmp_path, monkeypatch, module, exporter, builder, explicit,
):
    monkeypatch.setenv("FAITHBLOOM_ACCESS_MODE", "pilot")
    project = make_project(module)
    requested = "custom/pilot.epub"
    kwargs = {"output_path": requested} if explicit else {}
    result = getattr(module, exporter)(project, "epub", draft=True,
                                       checkpoint=lambda _: None, **kwargs)
    if explicit:
        assert result["path"] == requested
    else:
        kind = "comics" if module is comic_studio else "editorial-products"
        path = Path(result["path"])
        assert path.parent.parent == storage.CACHE_DIR / kind / project["book_id"]
        assert len(path.parent.name) == 32
        assert path.name == ("comic.epub" if module is comic_studio else f"product-{project['book_id']}.epub")
    assert Path(result["path"]).read_bytes().startswith(b"PK")


def test_comic_readiness_propagates_access_denial(monkeypatch):
    project = comic_project()
    denied = access.AccessDenied("Account access denied")

    def deny(*args, **kwargs):
        raise denied

    monkeypatch.setattr(comic_studio, "_require_script_review", deny)
    with pytest.raises(access.AccessDenied) as raised:
        comic_studio.comic_readiness(project)
    assert raised.value is denied

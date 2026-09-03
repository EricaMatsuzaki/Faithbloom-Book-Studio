import family_profiles as fp
import integration_ux as ux
import storage_backend
from storage_backend import LocalStorageBackend


def isolated(tmp_path, monkeypatch):
    backend = LocalStorageBackend(str(tmp_path / "data"))
    monkeypatch.setattr(storage_backend, "BACKEND", backend)
    monkeypatch.setattr(fp, "BACKEND", backend)
    return backend


def test_family_profiles_are_not_authentication_or_authorship(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    p = fp.create_workspace_profile("Larissa", relationship="filha", linked_author_profile_id="author-123")
    s = fp.profile_summary(p)
    assert s["name"] == "Larissa"
    assert s["linked_author_profile_id"] == "author-123"
    assert s["security_boundary"] is False
    assert "role" not in p and "authorship" not in p


def test_profile_preferences_persist(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    p = fp.create_workspace_profile("Erica", default_locale="pt-BR", default_age_profile="3-8", dashboard_mode="simple")
    p2 = fp.update_workspace_profile(p["id"], default_locale="ja-JP", default_age_profile="adult", dashboard_mode="advanced", publication_markets=["Kobo", "Amazon KDP"])
    assert p2["preferences"]["default_locale"] == "ja-JP"
    assert p2["preferences"]["default_age_profile"] == "adult"
    assert p2["preferences"]["dashboard_mode"] == "advanced"
    assert p2["preferences"]["publication_markets"] == ["Amazon KDP", "Kobo"]


def test_project_assignment_is_external_to_book_master(tmp_path, monkeypatch):
    backend = isolated(tmp_path, monkeypatch)
    original = {"titulo": "Livro", "autora": "Pessoa A", "cenas_texto": [{"numero": 1, "texto": "Oi"}]}
    backend.put_json("livros/c/livro.json", original)
    p = fp.create_workspace_profile("Kleber")
    fp.assign_project(p["id"], "story", "livros/c/livro.json", title="Livro", collection="C")
    assert backend.get_json("livros/c/livro.json", {}) == original
    assert fp.project_link("story", "livros/c/livro.json")["owner_profile_id"] == p["id"]


def test_projects_do_not_mix_between_profiles_by_default(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    a = fp.create_workspace_profile("Erica")
    b = fp.create_workspace_profile("Larissa")
    fp.assign_project(a["id"], "story", "livros/c/a.json", title="A")
    fp.assign_project(b["id"], "story", "livros/c/b.json", title="B")
    cards = [
        {"kind": "story", "storage_path": "livros/c/a.json", "titulo": "A"},
        {"kind": "story", "storage_path": "livros/c/b.json", "titulo": "B"},
    ]
    assert [x["titulo"] for x in fp.visible_project_cards(cards, a["id"])] == ["A"]
    assert [x["titulo"] for x in fp.visible_project_cards(cards, b["id"])] == ["B"]


def test_project_can_be_shared_without_changing_owner(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    a = fp.create_workspace_profile("Erica")
    b = fp.create_workspace_profile("Larissa")
    link = fp.assign_project(a["id"], "story", "livros/c/a.json", shared_profile_ids=[b["id"]])
    assert link["owner_profile_id"] == a["id"]
    assert b["id"] in link["shared_profile_ids"]
    shared = fp.project_links_for_profile(b["id"])
    assert shared[0]["access"] == "shared"


def test_touch_project_tracks_recent_per_profile(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    a = fp.create_workspace_profile("Erica")
    fp.assign_project(a["id"], "coloring", "livros_colorir/x.json", title="X")
    touched = fp.touch_project(a["id"], "coloring", "livros_colorir/x.json")
    assert touched["last_opened_by"][a["id"]]
    rows = fp.project_links_for_profile(a["id"])
    assert rows[0]["last_opened_at"]


def test_unrelated_profile_cannot_touch_project(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    a = fp.create_workspace_profile("Erica")
    b = fp.create_workspace_profile("Kleber")
    fp.assign_project(a["id"], "story", "livros/c/a.json")
    assert fp.touch_project(b["id"], "story", "livros/c/a.json") is None


def test_thumbnail_is_metadata_only(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    a = fp.create_workspace_profile("Erica")
    fp.assign_project(a["id"], "story", "livros/c/a.json")
    link = fp.set_project_thumbnail("story", "livros/c/a.json", "asset-cover-1")
    assert link["thumbnail_asset_id"] == "asset-cover-1"


def test_archive_profile_hides_it_from_active_list(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    p = fp.create_workspace_profile("Pessoa")
    fp.archive_workspace_profile(p["id"], True)
    assert fp.list_workspace_profiles() == []
    assert len(fp.list_workspace_profiles(include_archived=True)) == 1


def test_refinement18_route_is_in_integration_registry():
    registry = {x["id"]: x for x in ux.studio_registry()}
    assert "workspace_profiles" in registry
    assert registry["workspace_profiles"]["page"].endswith("Perfis_e_Dashboard.py")


def test_new_saved_project_can_be_auto_assigned_to_active_profile(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    p = fp.create_workspace_profile("Larissa")
    link = fp.assign_saved_project_to_profile(p["id"], "story", "fb://livros/c/novo.json", {"titulo": "Novo", "colecao": "C"})
    assert link["owner_profile_id"] == p["id"]
    assert link["storage_path"] == "livros/c/novo.json"
    assert link["title"] == "Novo"


def test_auto_assign_without_profile_is_noop(tmp_path, monkeypatch):
    isolated(tmp_path, monkeypatch)
    assert fp.assign_saved_project_to_profile("", "story", "fb://livros/c/novo.json", {"titulo": "Novo"}) is None

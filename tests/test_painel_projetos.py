"""Contratos de seleção e abertura com dependências de storage/UI substituídas."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import painel_projetos as projects
from integration_ux import PROJECT_CONTEXT_KEY
from painel_dados import filter_projects


class ProjectNavigationTests(unittest.TestCase):
    def test_available_projects_preserves_profile_scope_and_recent_order(self):
        stories = [{"storage_path": "livros/first.json", "titulo": "Mesmo título"},
                   {"storage_path": "livros/second.json", "titulo": "Mesmo título"}]
        coloring = [{"storage_path": "livros_colorir/flowers.json", "titulo": "Flores"}]
        links = [{"kind": "story", "storage_path": "livros/second.json", "owner_profile_id": "erica", "updated_at": "2026-10-05"},
                 {"kind": "coloring", "storage_path": "livros_colorir/flowers.json", "owner_profile_id": "erica", "updated_at": "2026-10-04"},
                 {"kind": "story", "storage_path": "livros/first.json", "owner_profile_id": "outro", "updated_at": "2026-10-06"}]
        with patch.object(projects, "listar_livros", return_value=stories), \
             patch.object(projects, "listar_livros_colorir", return_value=coloring), \
             patch("family_profiles._links", return_value=links):
            cards = projects.available_projects("erica")
        self.assertEqual([projects.project_path(card) for card in cards], ["livros/second.json", "livros_colorir/flowers.json"])
        self.assertNotIn("kind", stories[0])

    def test_active_project_matches_path_without_choosing_default(self):
        cards = [{"kind": "story", "storage_path": "livros/first.json", "titulo": "Mesmo"},
                 {"kind": "story", "storage_path": "livros/second.json", "titulo": "Mesmo"}]
        session = {}
        with patch.object(projects.st, "session_state", session):
            self.assertIsNone(projects.get_active_project(cards))
            session[PROJECT_CONTEXT_KEY] = {"storage_path": "fb://livros/second.json", "kind": "story"}
            self.assertEqual(projects.get_active_project(cards), cards[1])
            session[PROJECT_CONTEXT_KEY]["storage_path"] = "livros/outside-profile.json"
            self.assertIsNone(projects.get_active_project(cards))

    def test_open_story_loads_selected_project_into_jarvis_and_resume(self):
        card = {"kind": "story", "storage_path": "fb://livros/second.json", "titulo": "Segundo", "colecao": "Jardim"}
        state = {"titulo": "Segundo", "cenas_texto": [{"numero": 1, "texto": "Mel sorriu."}]}
        before = deepcopy(state)
        session = {PROJECT_CONTEXT_KEY: {"storage_path": "livros/first.json"}, "r_dna_Mel": "valor antigo"}
        with patch.object(projects.st, "session_state", session), \
             patch.object(projects, "carregar_livro", return_value=state) as loader, \
             patch.object(projects.st, "switch_page") as navigate:
            projects.open_project(card)
        loader.assert_called_once_with("Jardim", "livros/second.json")
        navigate.assert_called_once_with(projects.STORY_PAGE)
        self.assertEqual(session[PROJECT_CONTEXT_KEY]["storage_path"], "livros/second.json")
        self.assertEqual(session[PROJECT_CONTEXT_KEY]["kind"], "story")
        self.assertIs(session["state"], session["state_r"])
        self.assertEqual(session["etapa_r"], "personagens")
        self.assertNotIn("r_dna_Mel", session)
        self.assertEqual(state, before)

    def test_coloring_after_story_has_own_state_and_no_previous_cover(self):
        card = {"kind": "coloring", "storage_path": "livros_colorir/flowers.json"}
        state = {"titulo": "Flores", "paginas": [{"nome": "Rosa"}]}
        session = {PROJECT_CONTEXT_KEY: {"storage_path": "livros/first.json"}, "state": {"titulo": "Anterior"}, "capa_colorir_phase8": {"path": "old.png"}}
        with patch.object(projects.st, "session_state", session), \
             patch.object(projects, "carregar_livro_colorir", return_value=state), \
             patch.object(projects.st, "switch_page") as navigate:
            projects.open_project(card)
        navigate.assert_called_once_with(projects.COLORING_PAGE)
        self.assertEqual(session["state"]["titulo"], "Flores")
        self.assertIs(session["state"], session["state_c"])
        self.assertEqual(session["etapa_c"], "paginas")
        self.assertNotIn("capa_colorir_phase8", session)

    def test_reopening_active_book_preserves_unsaved_edits(self):
        card = {"kind": "story", "storage_path": "livros/current.json"}
        state = {"titulo": "Título editado nesta sessão", "cenas_texto": [{"numero": 1, "texto": "Nova versão."}]}
        session = {PROJECT_CONTEXT_KEY: {"storage_path": "livros/current.json", "kind": "story"},
                   "state_r": state, "state": state, "caminho_salvo_r": "livros/current.json", "etapa_r": "finalizar"}
        with patch.object(projects.st, "session_state", session), patch.object(projects, "load_project") as loader:
            projects.activate_project(card)
        loader.assert_not_called()
        self.assertEqual(session["state"]["titulo"], "Título editado nesta sessão")
        self.assertEqual(session["state_r"]["cenas_texto"][0]["texto"], "Nova versão.")
        self.assertNotEqual(session["etapa_r"], "finalizar")

    def test_coloring_names_are_searchable_and_pdf_is_not_a_cover(self):
        card = {"kind": "coloring", "storage_path": "livros_colorir/flowers.json", "titulo": "Flores"}
        state = {"paginas": [{"nome": "Rosa", "personagem_nome": "Téo"}]}
        with patch.object(projects, "project_snapshot", return_value=state):
            enriched = projects.searchable_projects([card])
        self.assertEqual(filter_projects(enriched, "teo"), enriched)
        self.assertNotIn("character_names", card)
        cover_state = {"capa_ebook": "https://example.org/wrap.pdf", "capa_fisica_preview": "https://example.org/preview.png"}
        with patch.object(projects, "materializar", side_effect=lambda value: value) as materialize:
            self.assertEqual(projects.project_cover_path(cover_state), "https://example.org/preview.png")
        materialize.assert_called_once_with("https://example.org/preview.png")

    def test_configured_profile_thumbnail_precedes_saved_cover(self):
        card = {"kind": "story", "storage_path": "fb://livros/current.json"}
        links = [{"kind": "story", "storage_path": "livros/other.json", "thumbnail_asset_id": "other-cover"},
                 {"kind": "story", "storage_path": "livros/current.json", "thumbnail_asset_id": "chosen-cover"}]
        with tempfile.TemporaryDirectory() as directory:
            thumb = Path(directory) / "chosen.png"
            # Cabeçalho PNG: a fixture representa o arquivo retornado pela Asset Library.
            thumb.write_bytes(b"\x89PNG\r\n\x1a\n")
            with patch.object(projects, "project_links_for_profile", return_value=links) as profile_links, \
                 patch.object(projects, "get_thumbnail", return_value=str(thumb)) as thumbnail, \
                 patch.object(projects, "materializar", side_effect=lambda value: value):
                cover = projects.project_cover_path({"capa_ebook": "https://example.org/saved.png"}, card, "erica")
            self.assertEqual(cover, str(thumb))
            profile_links.assert_called_once_with("erica")
            thumbnail.assert_called_once_with("chosen-cover", max_px=360)

    def test_broken_profile_thumbnail_falls_back_without_inventing_cover(self):
        card = {"kind": "coloring", "storage_path": "livros_colorir/flowers.json"}
        link = {**card, "thumbnail_asset_id": "missing-cover"}
        saved_cover = "https://example.org/saved.png"
        with patch.object(projects, "project_links_for_profile", return_value=[link]), \
             patch.object(projects, "materializar", side_effect=lambda value: value):
            for thumbnail in (None, "/tmp/faithbloom-thumbnail-that-does-not-exist.png"):
                with self.subTest(thumbnail=thumbnail), patch.object(projects, "get_thumbnail", return_value=thumbnail):
                    self.assertEqual(projects.project_cover_path({"capa_ebook": saved_cover}, card, "erica"), saved_cover)
                    self.assertEqual(projects.project_cover_path({}, card, "erica"), "")
            with patch.object(projects, "get_thumbnail", side_effect=OSError("Asset indisponível")):
                self.assertEqual(projects.project_cover_path({"capa_ebook": saved_cover}, card, "erica"), saved_cover)


if __name__ == "__main__":
    unittest.main()

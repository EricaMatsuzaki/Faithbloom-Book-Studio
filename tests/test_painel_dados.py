"""Testes dos dados do painel; não importam Streamlit nem acessam APIs."""
from copy import deepcopy
from pathlib import Path
import unittest

from painel_dados import ACTIONS, NAV_GROUPS, filter_actions, filter_projects, production_stages, suggest_actions


class DashboardDataTests(unittest.TestCase):
    def statuses(self, state, kind="story"):
        return {stage["label"]: stage["status"] for stage in production_stages(state, kind)}

    def test_empty_state_has_no_completed_stages(self):
        for kind in ("story", "coloring"):
            stages = production_stages({}, kind)
            self.assertEqual(len(stages), 6)
            self.assertEqual({stage["status"] for stage in stages}, {"pendente"})

    def test_partial_story_does_not_infer_approval(self):
        state = {
            "titulo": "Mel e a esperança", "cenas_texto": [{"numero": 1, "texto": "Mel sorriu."}],
            "personagens": {"Mel": {"imagem_referencia": "fb://mel.png", "aparencia_aprovada": False}},
            "cenas_imagem": [{"numero": 1, "caminho_arquivo": "fb://cena.png", "aprovado": False}],
        }
        statuses = self.statuses(state)
        self.assertEqual(statuses["História"], "concluido")
        self.assertEqual(statuses["Personagens"], "em_andamento")
        self.assertEqual(statuses["Ilustrações"], "em_andamento")
        self.assertEqual(statuses["Revisão"], "em_andamento")
        self.assertEqual(statuses["Diagramação"], "pendente")

    def test_approved_image_without_file_or_missing_scene_is_incomplete(self):
        state = {"cenas_texto": [{"numero": 1, "texto": "Um."}, {"numero": 2, "texto": "Dois."}],
                 "cenas_imagem": [{"numero": 1, "aprovado": True}]}
        self.assertEqual(self.statuses(state)["Ilustrações"], "em_andamento")
        state["cenas_imagem"][0]["caminho_arquivo"] = "fb://um.png"
        self.assertEqual(self.statuses(state)["Ilustrações"], "em_andamento")
        state["cenas_imagem"].append({"numero": 2, "caminho_arquivo": "fb://dois.png", "aprovado": True})
        self.assertEqual(self.statuses(state)["Ilustrações"], "concluido")

    def test_saved_approval_numbers_accept_json_string_numbers(self):
        state = {"cenas_texto": [{"numero": 1, "texto": "Mel sorriu."}],
                 "cenas_imagem": [{"numero": 1, "caminho_arquivo": "fb://um.png"}],
                 "cenas_imagem_aprovadas": ["1"]}
        self.assertEqual(self.statuses(state)["Ilustrações"], "concluido")

    def test_explicit_rejection_overrides_stale_approval(self):
        state = {"cenas_texto": [{"numero": 1, "texto": "Mel sorriu."}],
                 "cenas_imagem": [{"numero": 1, "caminho_arquivo": "fb://um.png", "aprovado": False, "status": "approved"}],
                 "cenas_imagem_aprovadas": [1]}
        self.assertEqual(self.statuses(state)["Ilustrações"], "em_andamento")
        coloring = {"paginas": [{"nome": "Mel", "caminho_arquivo": "fb://mel.png", "aprovada": False, "status": "aprovada"}]}
        self.assertEqual(self.statuses(coloring, "coloring")["Revisão"], "em_andamento")

    def test_layout_requires_export_not_only_available_layout(self):
        state = {"layout_paginas": [{"pagina": 1, "tipo": "texto"}]}
        self.assertEqual(self.statuses(state)["Diagramação"], "em_andamento")
        state["pdf_miolo"] = "fb://miolo.pdf"
        self.assertEqual(self.statuses(state)["Diagramação"], "concluido")

    def test_package_ready_never_means_published(self):
        state = {"pacote_pronto": True, "pdf_miolo": "fb://miolo.pdf"}
        self.assertEqual(self.statuses(state)["Publicação"], "em_andamento")
        state["distribution_summary"] = {"total": 1, "ready": 1, "live": 0}
        state["distribution_plan_id"] = "plan-1"
        self.assertEqual(self.statuses(state)["Publicação"], "em_andamento")
        state["distribution_summary"]["live"] = 1
        self.assertEqual(self.statuses(state)["Publicação"], "concluido")
        state["distribution_summary"]["blocked"] = 1
        self.assertEqual(self.statuses(state)["Publicação"], "em_andamento")
        state["distribution_summary"]["blocked"] = 0
        state["distribution_summary"]["total"] = 2
        self.assertEqual(self.statuses(state)["Publicação"], "em_andamento")

    def test_coloring_uses_page_approval_and_no_story_steps(self):
        state = {"titulo": "Jardim", "tema_geral": "Flores", "paginas": [
            {"nome": "Rosa", "caminho_arquivo": "fb://rosa.png", "aprovada": False}]}
        statuses = self.statuses(state, "coloring")
        self.assertEqual(statuses["Tema"], "concluido")
        self.assertNotIn("História", statuses)
        self.assertEqual(statuses["Line art"], "em_andamento")
        self.assertEqual(statuses["Revisão"], "em_andamento")
        state["paginas"][0]["aprovada"] = True
        self.assertEqual(self.statuses(state, "coloring")["Revisão"], "concluido")

    def test_search_ignores_accents_and_finds_character_names(self):
        projects = [{"titulo": "O jardim da Fé", "colecao": "Coração", "personagens": {"Érica": {"nome": "Érica"}}},
                    {"titulo": "Pequenos heróis", "colecao": "Amigos"}]
        self.assertEqual(filter_projects(projects, "jardim fe"), projects[:1])
        self.assertEqual(filter_projects(projects, "CORACAO"), projects[:1])
        self.assertEqual(filter_projects(projects, "erica"), projects[:1])
        cards = [{"titulo": "Um novo projeto", "personagens_nomes": ["Érica", "Mel"]}]
        self.assertEqual(filter_projects(cards, "erica"), cards)
        self.assertEqual(filter_projects(projects, "inexistente"), [])
        self.assertEqual(filter_projects(projects, ""), projects)
        self.assertEqual([action["key"] for action in filter_actions("ilustracoes")], ["images"])

    def test_local_suggestions_prioritize_concrete_intent_and_are_isolated(self):
        self.assertEqual(suggest_actions("Quero publicar meu livro na KDP")[0]["key"], "publish")
        self.assertEqual(suggest_actions("Revisão do texto da história")[0]["key"], "text")
        self.assertEqual(suggest_actions("Quero restaurar uma ilustração")[0]["key"], "images")
        self.assertEqual(suggest_actions("Gerenciar personagens da Mel")[0]["key"], "characters")
        suggestions = suggest_actions("")
        suggestions[0]["title"] = "Alterado"
        self.assertEqual(ACTIONS[0]["title"], "Criar um livro")

    def test_helpers_preserve_state_and_all_routes_exist(self):
        state = {"cenas_texto": [{"numero": 1, "texto": "Olá!"}], "distribution_summary": {"live": "1"}}
        before = deepcopy(state)
        production_stages(state)
        self.assertEqual(state, before)
        root = Path(__file__).resolve().parents[1]
        for action in ACTIONS + [item for group in NAV_GROUPS for item in group["items"]]:
            self.assertTrue((root / action["route"]).is_file(), action["route"])


if __name__ == "__main__":
    unittest.main()

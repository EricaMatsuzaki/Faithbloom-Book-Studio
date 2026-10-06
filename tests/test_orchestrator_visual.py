import unittest
from unittest.mock import patch

import orchestrator_visual as ov


class TestOrchestratorVisual(unittest.TestCase):
    def _storage(self):
        store = {}

        def fake_json(path, default):
            value = store.get(path, default)
            if isinstance(value, dict):
                return dict(value)
            if isinstance(value, list):
                return [dict(x) for x in value]
            return value

        def fake_save(path, value):
            store[path] = value

        return store, patch.multiple(ov, _json=fake_json, _save_json=fake_save)

    def test_scenes_blocked_until_story_characters_locations_and_style_approved(self):
        _, patches = self._storage()
        with patches:
            plan = ov.create_visual_plan(
                "p1", "Livro",
                characters=[{"id": "mel", "principal": True}],
                locations=[{"id": "jardim", "required": True}],
            )
            with self.assertRaises(PermissionError):
                ov.require_scene_generation_ready(plan)

            plan = ov.approve_story(plan)
            plan = ov.approve_character_candidate(plan, "mel", "cand-a", "fb://mel-a.png")
            world = ov.create_world_master("Coleção", "Jardim", "Jardim primavera")
            world = ov.approve_world_master(world["id"])
            plan = ov.link_location_approval(plan, "jardim", world["id"])
            plan = ov.approve_style(plan, {"name": "Aquarela suave"})

            self.assertTrue(ov.visual_preflight_status(plan)["ready_for_scene_generation"])
            ov.require_scene_generation_ready(plan)

    def test_character_candidate_never_becomes_official_master_automatically(self):
        _, patches = self._storage()
        with patches:
            plan = ov.create_visual_plan("p1", "Livro")
            plan = ov.approve_character_candidate(plan, "mel", "cand-a")
            self.assertFalse(plan["approvals"]["characters"]["mel"]["official_master_promoted"])
            plan = ov.mark_character_master_promoted(plan, "mel")
            self.assertTrue(plan["approvals"]["characters"]["mel"]["official_master_promoted"])

    def test_world_master_requires_explicit_approval_before_link(self):
        _, patches = self._storage()
        with patches:
            plan = ov.create_visual_plan("p1", "Livro", locations=[{"id": "casa"}])
            world = ov.create_world_master("C", "Casa", "Casa aconchegante")
            with self.assertRaises(PermissionError):
                ov.link_location_approval(plan, "casa", world["id"])

    def test_scenario_only_lock_preserves_everything_else(self):
        out = ov.scenario_only_instruction("Trocar o jardim por neve")
        self.assertFalse(out["locks"]["scenario"])
        self.assertTrue(out["locks"]["characters"])
        self.assertTrue(out["locks"]["pose_composition"])
        self.assertEqual(["scenario"], out["unlocked"])
        self.assertIn("Trocar o jardim por neve", out["instruction"])

    def test_paid_operation_requires_author_confirmation(self):
        _, patches = self._storage()
        with patches:
            plan = ov.create_visual_plan("p1", "Livro", budget_limit_usd=5.0)
            gate = ov.cost_gate(plan, 1.25, paid=True)
            self.assertTrue(gate["requires_author_confirmation"])
            self.assertFalse(gate["over_budget"])

    def test_budget_limit_blocks_silent_overrun(self):
        _, patches = self._storage()
        with patches:
            plan = ov.create_visual_plan("p1", "Livro", budget_limit_usd=2.0)
            plan["budget_spent_usd"] = 1.75
            gate = ov.cost_gate(plan, 0.50, paid=False)
            self.assertTrue(gate["over_budget"])
            self.assertTrue(gate["requires_author_confirmation"])


if __name__ == "__main__":
    unittest.main()

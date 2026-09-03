import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from unittest.mock import patch

import stable_candidate as sc
from storage_backend import LocalStorageBackend


class Refinamento15Tests(unittest.TestCase):
    def full_evidence(self):
        items = {}
        for spec in sc.cloud_launch_checklist():
            items[spec["id"]] = {
                "done": True,
                "note": "validado no ambiente de teste" if spec["required"] else "",
                "reference": "run-123" if spec["required"] else "",
                "actor": "tester",
            }
        return {"schema": sc.EVIDENCE_SCHEMA, "items": items}

    def test_source_manifest_has_fingerprint(self):
        m = sc.source_release_manifest()
        self.assertGreater(m["file_count"], 0)
        self.assertEqual(len(m["source_fingerprint"]), 64)

    def test_required_checkbox_without_detail_is_not_enough(self):
        evidence = {x["id"]: True for x in sc.cloud_launch_checklist()}
        ev = sc.evaluate_cloud_launch_evidence(evidence)
        self.assertFalse(ev["cloud_launch_evidence_passed"])
        self.assertTrue(ev["required_without_detail"])

    def test_full_evidence_passes(self):
        ev = sc.evaluate_cloud_launch_evidence(self.full_evidence())
        self.assertTrue(ev["cloud_launch_evidence_passed"])
        self.assertFalse(ev["missing_required"])

    def test_candidate_gate_blocks_without_qa(self):
        gate = sc.release_candidate_gate(self.full_evidence(), deployment_ready=True, qa_ok=False)
        self.assertFalse(gate["candidate_ready"])
        self.assertIn("offline_qa", {x["id"] for x in gate["blockers"]})

    def test_candidate_gate_passes_with_injected_readiness(self):
        gate = sc.release_candidate_gate(self.full_evidence(), deployment_ready=True, qa_ok=True)
        self.assertTrue(gate["candidate_ready"])

    def test_rollback_is_non_destructive(self):
        p = sc.build_rollback_plan(candidate_version="2.0.0-rc2")
        self.assertFalse(p["destructive_actions_automatic"])
        self.assertTrue(any("Não apagar" in x for x in p["principles"]))

    def test_candidate_persistence_and_signoff(self):
        with tempfile.TemporaryDirectory() as td, patch.object(sc, "BACKEND", LocalStorageBackend(td)):
            c = sc.create_release_candidate(
                version="2.0.0-rc2",
                evidence=self.full_evidence(),
                qa_report={"ok": True},
                deployment_ready=True,
                deployment_detail={"ready_for_cloud_validation": True},
                actor="tester",
            )
            self.assertEqual(c["status"], "candidate")
            rows = sc.list_release_candidates()
            self.assertEqual(len(rows), 1)
            signed = sc.record_manual_signoff(c["candidate_id"], approved=True, actor="tester", note="approved")
            self.assertTrue(signed["manual_signoff"]["approved"])

    def test_promotion_requires_current_source_and_signoff(self):
        manifest = sc.source_release_manifest()
        candidate = {
            "schema": sc.SCHEMA,
            "source_manifest": manifest,
            "gate": {"status": "PASS"},
            "manual_signoff": {"approved": False},
        }
        gate = sc.stable_promotion_gate(candidate, current_manifest=manifest)
        self.assertFalse(gate["ready_to_tag_stable_manually"])
        candidate["manual_signoff"] = {"approved": True, "actor": "tester"}
        gate2 = sc.stable_promotion_gate(candidate, current_manifest=manifest)
        self.assertTrue(gate2["ready_to_tag_stable_manually"])

    def test_changed_source_invalidates_candidate(self):
        manifest = sc.source_release_manifest()
        changed = dict(manifest)
        changed["source_fingerprint"] = "0" * 64
        r = sc.candidate_is_current({"source_manifest": manifest}, current_manifest=changed)
        self.assertFalse(r["current"])

    def test_evidence_bundle_contains_expected_files(self):
        manifest = sc.source_release_manifest()
        candidate = {
            "schema": sc.SCHEMA,
            "candidate_id": "x",
            "source_manifest": manifest,
            "evidence": self.full_evidence(),
            "gate": {"status": "PASS"},
            "deployment_snapshot": {},
            "qa_report": {"ok": True},
            "rollback_plan": sc.build_rollback_plan(candidate_version="2.0.0-rc2", source_manifest=manifest),
            "manual_signoff": {"approved": True, "actor": "tester"},
        }
        data = sc.build_evidence_bundle_bytes(candidate)
        with zipfile.ZipFile(BytesIO(data)) as z:
            names = set(z.namelist())
        self.assertIn("candidate.json", names)
        self.assertIn("rollback-plan.json", names)
        self.assertIn("promotion-gate.json", names)

    def test_evidence_draft_roundtrip(self):
        with tempfile.TemporaryDirectory() as td, patch.object(sc, "BACKEND", LocalStorageBackend(td)):
            saved = sc.save_evidence_draft(self.full_evidence(), actor="tester")
            loaded = sc.load_evidence_draft()
            self.assertEqual(saved["schema"], sc.EVIDENCE_SCHEMA)
            self.assertEqual(loaded["items"]["boot"]["done"], True)


if __name__ == "__main__":
    unittest.main()

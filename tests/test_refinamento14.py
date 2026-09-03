import tempfile
import unittest

from production_deployment import (
    evaluate_real_e2e,
    local_storage_inventory,
    plan_storage_migration,
    execute_storage_migration,
    deployment_config_snapshot,
)
from storage_backend import LocalStorageBackend


class TestRefinamento14(unittest.TestCase):
    def test_snapshot_nao_expoe_secret(self):
        r = deployment_config_snapshot({
            "OPENROUTER_API_KEY": "sk-super-secret",
            "SUPABASE_SERVICE_ROLE_KEY": "also-secret",
            "FAITHBLOOM_DEPLOYMENT_MODE": "production",
        })
        blob = str(r)
        self.assertNotIn("sk-super-secret", blob)
        self.assertNotIn("also-secret", blob)
        self.assertTrue(r["env_present"]["OPENROUTER_API_KEY"])

    def test_inventory_local(self):
        with tempfile.TemporaryDirectory() as d:
            b = LocalStorageBackend(d)
            b.put_bytes("books/a.json", b"{}")
            inv = local_storage_inventory(d)
            self.assertEqual(inv["count"], 1)
            self.assertEqual(inv["bytes"], 2)
            self.assertEqual(inv["items"][0]["path"], "books/a.json")

    def test_migration_copy_and_verify(self):
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as t:
            src = LocalStorageBackend(s); dst = LocalStorageBackend(t)
            src.put_bytes("a/x.txt", b"hello")
            p = plan_storage_migration(src, dst)
            self.assertEqual(len(p["copy"]), 1)
            r = execute_storage_migration(src, dst)
            self.assertTrue(r["ok"])
            self.assertEqual(dst.get_bytes("a/x.txt"), b"hello")
            self.assertEqual(src.get_bytes("a/x.txt"), b"hello")

    def test_migration_conflict_no_overwrite(self):
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as t:
            src = LocalStorageBackend(s); dst = LocalStorageBackend(t)
            src.put_bytes("x.txt", b"source")
            dst.put_bytes("x.txt", b"target")
            r = execute_storage_migration(src, dst)
            self.assertFalse(r["ok"])
            self.assertEqual(dst.get_bytes("x.txt"), b"target")

    def test_real_e2e_required(self):
        r = evaluate_real_e2e({})
        self.assertFalse(r["cloud_e2e_passed"])
        evidence = {x["id"]: True for x in r["items"] if x["required"]}
        r2 = evaluate_real_e2e(evidence)
        self.assertTrue(r2["cloud_e2e_passed"])


if __name__ == "__main__":
    unittest.main()

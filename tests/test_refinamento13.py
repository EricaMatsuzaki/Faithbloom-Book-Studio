import os
import tempfile
import unittest
from unittest.mock import patch

import stable_hardening as sh
from storage_backend import LocalStorageBackend
from stable_hardening import (
    CURRENT_DATA_SCHEMA, can, environment_diagnostics, migrate_project_state,
    permission_matrix, prepare_restore_working_copy, sanitize_for_log,
    stable_release_gate, state_fingerprint,
)


class Refinamento13Tests(unittest.TestCase):
    def base(self):
        return {"titulo":"Livro Teste", "colecao":"Colecao A", "idioma_original":"pt-BR", "cenas_texto":[{"numero":1,"texto":"Oi"}]}

    def test_migration_reaches_current_schema(self):
        r=migrate_project_state(self.base())
        self.assertEqual(r["to_version"], CURRENT_DATA_SCHEMA)
        self.assertEqual(r["state"]["_faithbloom_schema_version"], CURRENT_DATA_SCHEMA)

    def test_migration_is_idempotent(self):
        a=migrate_project_state(self.base())["state"]
        b=migrate_project_state(a)
        self.assertFalse(b["changed"])

    def test_migration_preserves_content(self):
        s=self.base(); r=migrate_project_state(s)["state"]
        self.assertEqual(r["cenas_texto"], s["cenas_texto"])
        self.assertEqual(r["titulo"], s["titulo"])

    def test_bible_guard_locked_on_by_migration(self):
        r=migrate_project_state(self.base())["state"]
        self.assertTrue(r["content_protection"]["bible_guard_required"])

    def test_permissions_owner_and_viewer(self):
        self.assertTrue(can("owner", "publish"))
        self.assertFalse(can("viewer", "publish"))
        self.assertTrue(can("viewer", "view"))

    def test_permission_matrix_has_roles(self):
        m=permission_matrix()
        self.assertTrue(m)
        self.assertIn("owner", m[0])
        self.assertIn("reviewer", m[0])

    def test_sanitize_secret_keys(self):
        r=sanitize_for_log({"api_key":"secret-value", "nested":{"password":"x"}, "safe":"ok"})
        self.assertEqual(r["api_key"], "[REDACTED]")
        self.assertEqual(r["nested"]["password"], "[REDACTED]")
        self.assertEqual(r["safe"], "ok")

    def test_restore_is_working_copy(self):
        current=self.base(); old={**self.base(), "titulo":"Livro Teste", "cenas_texto":[{"numero":1,"texto":"Anterior"}]}
        rp={"state":old}
        r=prepare_restore_working_copy(current, rp)
        self.assertIn("working_copy", r)
        self.assertEqual(r["working_copy"]["cenas_texto"][0]["texto"], "Anterior")
        self.assertEqual(current["cenas_texto"][0]["texto"], "Oi")

    def test_fingerprint_changes_with_content(self):
        a=self.base(); b=self.base(); b["cenas_texto"][0]["texto"]="Mudou"
        self.assertNotEqual(state_fingerprint(a), state_fingerprint(b))

    def test_development_without_auth_is_warning_not_blocker(self):
        env={"FAITHBLOOM_DEPLOYMENT_MODE":"development"}
        d=environment_diagnostics(env)
        self.assertTrue(d["ok_for_production"])
        self.assertTrue(any(x["id"]=="auth" and not x["ok"] for x in d["warnings"]))

    def test_production_requires_auth_storage_and_key(self):
        env={"FAITHBLOOM_DEPLOYMENT_MODE":"production", "FAITHBLOOM_AUTH_MODE":"none"}
        d=environment_diagnostics(env)
        self.assertFalse(d["ok_for_production"])
        ids={x["id"] for x in d["blockers"]}
        self.assertIn("auth", ids)
        self.assertIn("openrouter", ids)

    def test_stable_gate_keeps_bible_guard(self):
        gate=stable_release_gate(settings={"bible_guard_required":True, "author_name":"Erica", "default_locale":"pt-BR"}, environ={"FAITHBLOOM_DEPLOYMENT_MODE":"development"})
        bible=next(x for x in gate["checks"] if x["id"]=="bible_guard")
        self.assertTrue(bible["ok"])

    def test_recovery_roundtrip_isolated_backend(self):
        with tempfile.TemporaryDirectory() as td, patch.object(sh, "BACKEND", LocalStorageBackend(td)):
            rp=sh.create_recovery_point(self.base(), label="before-edit", actor="Tester")
            self.assertTrue(rp["recovery_id"])
            points=sh.list_recovery_points("Livro Teste", "Colecao A")
            self.assertEqual(len(points), 1)
            loaded=sh.load_recovery_point(points[0]["storage_path"])
            self.assertEqual(loaded["state"]["titulo"], "Livro Teste")

    def test_audit_redacts_secret_isolated_backend(self):
        with tempfile.TemporaryDirectory() as td, patch.object(sh, "BACKEND", LocalStorageBackend(td)):
            sh.record_audit_event("test", actor="Tester", details={"api_key":"supersecret", "safe":"ok"})
            events=sh.list_audit_events()
            self.assertEqual(events[0]["details"]["api_key"], "[REDACTED]")
            self.assertEqual(events[0]["details"]["safe"], "ok")

    def test_settings_never_disable_bible_guard(self):
        with tempfile.TemporaryDirectory() as td, patch.object(sh, "BACKEND", LocalStorageBackend(td)):
            saved=sh.save_settings({"author_name":"Erica", "bible_guard_required":False, "api_key":"do-not-store"})
            self.assertTrue(saved["bible_guard_required"])
            self.assertNotIn("api_key", saved)

    def test_storage_roundtrip_probe_cleans_up(self):
        with tempfile.TemporaryDirectory() as td, patch.object(sh, "BACKEND", LocalStorageBackend(td)):
            r=sh.storage_roundtrip_probe()
            self.assertTrue(r["ok"])
            self.assertFalse((LocalStorageBackend(td).root / r["path"]).exists())


if __name__ == "__main__":
    unittest.main()

import json
import unittest

from project_hub import same_project, build_project_overview, build_edition_matrix, build_project_snapshot


class ProjectHubTests(unittest.TestCase):
    def base(self):
        return {
            "titulo":"Livro Teste","colecao":"Coleção A","idioma_original":"pt-BR",
            "cenas_texto":[{"numero":1,"texto":"Oi"}],"revisao_aprovada":True,
            "personagens":{"Mel":{"nome":"Mel"}},
        }

    def test_same_project_casefold(self):
        self.assertTrue(same_project(" Livro Teste ","Coleção A","livro teste","coleção a"))
        self.assertFalse(same_project("Livro A","","Livro B",""))

    def test_no_fake_quality_score_policy(self):
        o=build_project_overview(self.base())
        self.assertTrue(o["policy"]["no_fake_quality_score"])
        self.assertNotIn("score", o)

    def test_editorial_approved(self):
        o=build_project_overview(self.base())
        stage=next(x for x in o["stages"] if x["id"]=="editorial")
        self.assertEqual(stage["status"],"complete")

    def test_guardian_stale_blocks(self):
        state=self.base()
        report={"project_fingerprint":"old","certificate":{"status":"passed"},"summary":{"open_blockers":0}}
        o=build_project_overview(state,guardian_reports=[report])
        stage=next(x for x in o["stages"] if x["id"]=="quality")
        self.assertEqual(stage["status"],"blocked")

    def test_guardian_current_certificate_completes(self):
        from quality_guardian import project_fingerprint
        state=self.base()
        report={"project_fingerprint":project_fingerprint(state),"certificate":{"status":"INTERNAL_QUALITY_GATE_PASSED"},"author_final_approval":{"approved":True},"summary":{"open_blockers":0}}
        o=build_project_overview(state,guardian_reports=[report])
        stage=next(x for x in o["stages"] if x["id"]=="quality")
        self.assertEqual(stage["status"],"complete")

    def test_translation_approved_locale(self):
        tr={"edicoes":{"en-US":{"versoes":[{"versao_id":"v1"}],"aprovada_id":"v1"}}}
        o=build_project_overview(self.base(),translations=[tr])
        self.assertEqual(o["translations"]["approved_locales"],1)

    def test_activity_optional_when_absent(self):
        o=build_project_overview(self.base())
        stage=next(x for x in o["stages"] if x["id"]=="activities")
        self.assertEqual(stage["status"],"optional")

    def test_audio_requires_author_final_approval(self):
        a={"locale":"pt-BR","status":"approved","final_author_approval":{"approved":False}}
        o=build_project_overview(self.base(),audiobooks=[a])
        self.assertEqual(o["audiobooks"]["approved_projects"],0)

    def test_edition_matrix_separates_translation_and_live(self):
        tr={"edicoes":{"en-US":{"versoes":[{"versao_id":"v1"}],"aprovada_id":"v1"}}}
        plan={"editions":[{"locale":"en-US","readiness":"ready","submission":{"status":"live"}}]}
        rows=build_edition_matrix(self.base(),translations=[tr],distribution_plans=[plan])
        en=next(x for x in rows if x["locale"]=="en-US")
        self.assertEqual(en["text_status"],"Aprovada")
        self.assertEqual(en["live"],1)

    def test_distribution_stale_is_blocked(self):
        plan={"project_fingerprint":"old","summary":{"total":1,"ready":1,"blocked":0,"live":0},"editions":[]}
        o=build_project_overview(self.base(),distribution_plans=[plan])
        stage=next(x for x in o["stages"] if x["id"]=="distribution")
        self.assertEqual(stage["status"],"blocked")

    def test_release_not_ready_without_quality_and_distribution(self):
        o=build_project_overview(self.base())
        self.assertFalse(o["release"]["ready_for_channel_packages"])

    def test_snapshot_json(self):
        o=build_project_overview(self.base())
        m=build_edition_matrix(self.base())
        snap=json.loads(build_project_snapshot(self.base(),o,m))
        self.assertEqual(snap["schema"],"faithbloom.project-hub.snapshot.v1")
        self.assertEqual(snap["project"]["title"],"Livro Teste")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

import publishing_distribution as pd
from quality_guardian import run_quality_guardian, record_issue_decision, register_author_final_approval, issue_internal_certificate


class Refinamento11Tests(unittest.TestCase):
    def minimal_state(self):
        return {
            "titulo":"Teste Distribuição", "autora":"Erica Matsuzaki", "idioma_original":"pt-BR",
            "revisao_aprovada":True, "cenas_texto":[{"numero":1,"texto":"Mel sorriu."}], "licao_final":"Uma lição.",
            "mapa_emocional":[{"numero":1}], "personagens":{}, "paginas_fisicas":32,
            "trim_largura_in":8.5,"trim_altura_in":8.5,"usar_bleed":True,
        }

    def certified_report(self, s):
        r=run_quality_guardian(s)
        for x in list(r["issues"]):
            if x.get("requires_decision") and x["severity"] != "bloqueante":
                r=record_issue_decision(r,x["id"],"nao_se_aplica","qa")
        r=register_author_final_approval(r,True)
        return issue_internal_certificate(r)

    def test_guardian_gate_rejeita_relatorio_ausente(self):
        self.assertFalse(pd.guardian_gate(self.minimal_state(),None)["passed"])

    def test_guardian_gate_detecta_conteudo_alterado(self):
        s=self.minimal_state(); r=self.certified_report(s); s["licao_final"]="Mudou"
        self.assertEqual(pd.guardian_gate(s,r)["status"],"stale")

    def test_kdp_select_detecta_conflito_digital(self):
        master={"kdp_select_active":True}
        c=pd.exclusivity_conflicts(master,[{"platform_id":"kobo_writing_life","product":"ebook"},{"platform_id":"amazon_kdp","product":"ebook"}])
        self.assertEqual(len(c),1); self.assertEqual(c[0]["platform_id"],"kobo_writing_life")

    def test_plano_sem_assets_fica_bloqueado_sem_fingir_prontidao(self):
        s=self.minimal_state(); r=self.certified_report(s)
        p=pd.create_distribution_plan(s,[{"platform_id":"amazon_kdp","product":"paperback"}],r)
        self.assertEqual(p["summary"]["ready"],0)
        self.assertEqual(p["editions"][0]["readiness"],"blocked")

    def test_status_live_nao_pode_ser_marcardo_se_bloqueado(self):
        s=self.minimal_state(); r=self.certified_report(s)
        p=pd.create_distribution_plan(s,[{"platform_id":"amazon_kdp","product":"paperback"}],r)
        with self.assertRaises(ValueError):
            pd.update_submission(p,p["editions"][0]["edition_id"],"live")

    def test_update_submission_exige_confirmacao_explicita(self):
        p={"editions":[{"edition_id":"x","readiness":"ready","submission":{"status":"draft"}}],"quality_gate":{"passed":True}}
        p2=pd.update_submission(p,"x","submitted",external_id="ABC")
        self.assertEqual(p2["editions"][0]["submission"]["status"],"submitted")
        self.assertEqual(p2["summary"]["submitted"],1)

    def test_platform_custom_continua_compativel_com_center(self):
        # O Center usa list/get do Registry, portanto não mantém uma lista fechada.
        import platform_registry as registry
        with tempfile.TemporaryDirectory() as td:
            old=(registry.DATA_DIR,registry.CUSTOM_PATH,registry.OVERRIDE_PATH,registry.HISTORY_PATH)
            registry.DATA_DIR=Path(td); registry.CUSTOM_PATH=Path(td)/"custom.json"; registry.OVERRIDE_PATH=Path(td)/"overrides.json"; registry.HISTORY_PATH=Path(td)/"history.json"
            try:
                rec=registry.register_custom_platform(name="Nova Loja",products=["ebook"],accepted_formats={"ebook":["epub"]})
                self.assertEqual(registry.get_platform(rec["id"])["name"],"Nova Loja")
            finally:
                registry.DATA_DIR,registry.CUSTOM_PATH,registry.OVERRIDE_PATH,registry.HISTORY_PATH=old


if __name__ == "__main__": unittest.main()

import unittest

from quality_guardian import (
    run_quality_guardian, record_issue_decision, register_author_final_approval,
    issue_internal_certificate, build_specialist_review_prompt,
    normalize_specialist_review, check_bible, check_readability,
)
from activity_studio import create_activity_page, attach_qa, approve_activity_page


class Refinamento10Tests(unittest.TestCase):
    def story(self):
        return {
            "titulo": "Quando Mel Aprendeu a Esperar",
            "colecao": "Pequenas Histórias, Grandes Lições",
            "faixa_etaria": "3-8",
            "aprendizado_cristao": "Paciência e confiança em Deus",
            "versiculo_referencia": "Eclesiastes 3:1",
            "revisao_aprovada": True,
            "licao_final": "Esperar também é confiar.",
            "cenas_texto": [
                {"numero": 1, "texto": "Mel queria tudo depressa.", "emocao": "ansiedade"},
                {"numero": 2, "texto": "Téo explicou que algumas coisas precisam de tempo.", "emocao": "esperança"},
            ],
            "mapa_emocional": [{"numero": 1}, {"numero": 2}],
            "personagens": {},
            "bible_records": {},
            "traducoes": {},
        }

    def test_guardian_nao_inventa_score(self):
        r = run_quality_guardian(self.story())
        self.assertFalse(any("score" in i for i in r.get("issues", [])))
        self.assertFalse(any("quality_score" in (i.get("evidence") or {}) for i in r.get("issues", [])))
        self.assertTrue(r["policy"]["no_invented_quality_scores"])

    def test_repeticao_consecutiva_e_detectada_sem_correcao(self):
        s = self.story(); s["cenas_texto"][1]["texto"] = s["cenas_texto"][0]["texto"]
        r = run_quality_guardian(s)
        dup = [x for x in r["issues"] if x["code"] == "adjacent_duplicate_text"]
        self.assertEqual(len(dup), 1)
        self.assertEqual(s["cenas_texto"][1]["texto"], "Mel queria tudo depressa.")
        self.assertTrue(r["policy"]["no_silent_corrections"])

    def test_bloqueio_nao_pode_ser_ignorado_com_justificativa(self):
        s = self.story(); s["revisao_aprovada"] = False
        r = run_quality_guardian(s)
        x = next(i for i in r["issues"] if i["code"] == "author_editorial_approval")
        r2 = record_issue_decision(r, x["id"], "manter_com_justificativa", "quero manter")
        x2 = next(i for i in r2["issues"] if i["id"] == x["id"])
        self.assertEqual(x2["resolution_status"], "open")
        with self.assertRaises(ValueError): register_author_final_approval(r2, True)

    def test_resolvido_exige_rerun(self):
        s = self.story(); s["licao_final"] = ""
        r = run_quality_guardian(s)
        x = next(i for i in r["issues"] if i["code"] == "missing_lesson")
        r2 = record_issue_decision(r, x["id"], "resolvido")
        self.assertEqual(next(i for i in r2["issues"] if i["id"] == x["id"])["resolution_status"], "pending_recheck")
        self.assertFalse(r2["summary"]["ready_for_author_signoff"])
        s["licao_final"] = "Esperar também é confiar."
        r3 = run_quality_guardian(s, previous_report=r2)
        self.assertFalse(any(i["code"] == "missing_lesson" for i in r3["issues"]))

    def test_activity_invalida_vira_bloqueio(self):
        p = create_activity_page("maze", "5-6", instruction="Saia do labirinto.", content={"grid":[[0,1],[1,0]],"start":[0,0],"end":[1,1]})
        p = attach_qa(p)
        r = run_quality_guardian(self.story(), activity_project={"pages":[p]})
        self.assertTrue(any(i["domain"] == "activities" and i["severity"] == "bloqueante" for i in r["issues"]))

    def test_activity_aprovada_nao_cria_bloqueio_de_activity(self):
        p = create_activity_page("count", "3-4", instruction="Conte.", content={"items":["f","f"],"answer":2})
        p = approve_activity_page(attach_qa(p))
        r = run_quality_guardian(self.story(), activity_project={"pages":[p]})
        self.assertFalse(any(i["domain"] == "activities" and i["severity"] == "bloqueante" for i in r["issues"]))

    def test_bible_guard_detecta_traducao_nao_protegida(self):
        s = self.story(); s["traducoes"] = {"en-US":{"bible_ai_translation_allowed":True,"cenas_texto":s["cenas_texto"]}}
        issues = check_bible(s)
        self.assertTrue(any(i["code"] == "bible_ai_guard" and i["severity"] == "bloqueante" for i in issues))

    def test_prompt_revisor_biblico_nao_envia_texto_biblico(self):
        s = self.story(); s["versiculo_texto_original"] = "TEXTO QUE NAO DEVE IR"; s["bible_records"]={"pt-BR":{"referencia":"Eclesiastes 3:1","texto_aprovado":"OUTRO TEXTO PROTEGIDO","versao":"X"}}
        system, payload = build_specialist_review_prompt(s, "biblical_context")
        self.assertIn("Eclesiastes 3:1", payload)
        self.assertNotIn("TEXTO QUE NAO DEVE IR", payload)
        self.assertNotIn("OUTRO TEXTO PROTEGIDO", payload)
        self.assertIn("NÃO deve citar", system)

    def test_revisor_especialista_remove_campo_biblico(self):
        r = normalize_specialist_review({"issues":[{"severity":"atencao","location":"Final","finding":"Revisar clareza","why":"Motivo","suggestion":"Ajustar","scripture_text":"inventado"}]}, "biblical_context")
        self.assertNotIn("inventado", str(r))

    def test_readability_declara_metodo_heuristico(self):
        issues = check_readability(self.story())
        info = next(x for x in issues if x["code"] == "readability_method")
        self.assertEqual(info["evidence"].get("profile"), "3-8")
        self.assertIn("não apresenta", info["why"].lower())

    def test_certificado_interno_exige_decisoes_e_aprovacao(self):
        # projeto não cristão/minimal para evitar alertas de contexto; resolve avisos deliberadamente
        s = {"titulo":"Teste","revisao_aprovada":True,"cenas_texto":[{"numero":1,"texto":"Olá."}],"licao_final":"Fim.","mapa_emocional":[{"numero":1}],"personagens":{}}
        r = run_quality_guardian(s)
        for x in list(r["issues"]):
            if x.get("requires_decision") and x["severity"] != "bloqueante":
                r = record_issue_decision(r, x["id"], "nao_se_aplica", "validado para este teste")
        self.assertEqual(r["summary"]["open_blockers"], 0)
        r = register_author_final_approval(r, True)
        r = issue_internal_certificate(r)
        self.assertEqual(r["certificate"]["status"], "INTERNAL_QUALITY_GATE_PASSED")
        self.assertIn("não é certificação", r["certificate"]["disclaimer"].lower())


if __name__ == "__main__":
    unittest.main()

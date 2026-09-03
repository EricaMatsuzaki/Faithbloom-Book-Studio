import unittest
from activity_studio import (
    AUDIENCE_PRESETS, available_activity_types, create_activity_page,
    attach_qa, approve_activity_page, revise_activity_page, project_readiness,
    create_activity_project, add_page_to_project, story_to_activity_suggestions,
    normalize_llm_activity_result, render_activity_svg, generation_prompt,
)

class Refinamento08Tests(unittest.TestCase):
    def test_publicos_incluem_adulto_e_60mais(self):
        for key in ("3-4","5-6","7-8","9-12","teen","adult","senior","custom"):
            self.assertIn(key,AUDIENCE_PRESETS)
        self.assertIn("crossword",available_activity_types("adult"))
        self.assertIn("word_search",available_activity_types("senior"))

    def test_labirinto_solucionavel_passa_e_gabarito_tem_caminho(self):
        p=create_activity_page("maze","5-6",instruction="Ajude Mel a chegar até Téo.",content={"grid":[[0,1,0],[0,0,0],[1,1,0]],"start":[0,0],"end":[2,2]})
        p=attach_qa(p)
        self.assertTrue(p["qa"]["valid"])
        self.assertGreater(p["qa"]["answer_key"]["steps"],0)
        self.assertEqual(p["status"],"ready_for_author_review")

    def test_labirinto_sem_saida_bloqueia_aprovacao(self):
        p=create_activity_page("maze","5-6",instruction="Encontre a saída.",content={"grid":[[0,1,0],[1,1,1],[0,1,0]],"start":[0,0],"end":[2,2]})
        p=attach_qa(p)
        self.assertFalse(p["qa"]["valid"])
        with self.assertRaises(ValueError): approve_activity_page(p)

    def test_caca_palavras_detecta_palavra_ausente(self):
        p=create_activity_page("word_search","7-8",instruction="Encontre as palavras.",content={"grid":[list("MELX"),list("XXXX"),list("XXXX"),list("XXXX")],"words":["MEL","TEO"]})
        p=attach_qa(p)
        self.assertFalse(p["qa"]["valid"])
        self.assertTrue(any(a["code"]=="word_search_missing_words" for a in p["qa"]["alerts"]))

    def test_diferencas_quantidade_precisa_bater(self):
        p=create_activity_page("spot_difference","7-8",instruction="Ache 5 diferenças.",content={"declared_count":5,"differences":["a","b","c"]})
        self.assertFalse(attach_qa(p)["qa"]["valid"])

    def test_matematica_confere_gabarito(self):
        good=create_activity_page("math","9-12",instruction="Resolva.",content={"items":[{"expression":"12/3+2","answer":6.0}]})
        self.assertTrue(attach_qa(good)["qa"]["valid"])
        bad=create_activity_page("math","9-12",instruction="Resolva.",content={"items":[{"expression":"2+2","answer":5}]})
        self.assertFalse(attach_qa(bad)["qa"]["valid"])

    def test_sudoku_exige_solucao_unica(self):
        p=create_activity_page("sudoku","adult",instruction="Complete o Sudoku.",content={"board":[[1,0,3,0],[0,4,0,2],[2,0,4,0],[0,3,0,1]]})
        q=attach_qa(p)["qa"]
        self.assertTrue(q["valid"])
        self.assertEqual(len(q["answer_key"]),4)

    def test_cruzadinha_detecta_conflito(self):
        p=create_activity_page("crossword","adult",instruction="Complete a cruzadinha.",content={"entries":[
            {"answer":"MEL","clue":"Gatinha","row":0,"col":0,"direction":"across"},
            {"answer":"SOL","clue":"Brilha","row":0,"col":0,"direction":"down"},
        ]})
        self.assertFalse(attach_qa(p)["qa"]["valid"])

    def test_aprovacao_autora_e_prontidao(self):
        p=create_activity_page("count","3-4",instruction="Conte as flores.",content={"items":["f","f","f"],"answer":3})
        p=approve_activity_page(attach_qa(p))
        project={"pages":[p]}
        self.assertTrue(project_readiness(project)["ready"])
        self.assertTrue(p["author_approval"]["approved"])

    def test_modificar_somente_isto_preserva_campos(self):
        p=create_activity_page("maze","5-6",instruction="Versão antiga",theme="Natal",character_ids=["mel"],content={"grid":[[0,0],[1,0]],"start":[0,0],"end":[1,1]})
        p2=revise_activity_page(p,change_request="mudar só a instrução",patch={"instruction":"Nova instrução","theme":"Verão","character_ids":["outro"]},preserve_fields=["theme","character_ids"])
        self.assertEqual(p2["version_label"],"B")
        self.assertEqual(p2["theme"],"Natal")
        self.assertEqual(p2["character_ids"],["mel"])
        self.assertEqual(len(p2["revisions"]),1)

    def test_story_suggestions_nao_inventam_texto_biblico(self):
        s=story_to_activity_suggestions({"titulo":"Mel","versiculo_referencia":"Lucas 2:11","versiculo_texto_original":"NÃO COPIAR"},"7-8",20)
        blob=str(s)
        self.assertNotIn("NÃO COPIAR",blob)
        bib=[x for x in s if "bible" in x["activity_type"]]
        if bib: self.assertEqual(bib[0].get("bible_reference_only"),"Lucas 2:11")

    def test_bible_guard_sanitiza_resultado_do_activity_designer(self):
        r=normalize_llm_activity_result({"instruction":"Faça a atividade","content":{},"scripture_text":"texto inventado","answer_key":None})
        self.assertNotIn("scripture_text",r)
        sys,user=generation_prompt("bible_activity","7-8","moderate","Fé","compreensão",{"versiculo_referencia":"Lucas 2:11","versiculo_texto_original":"NÃO ENVIAR"})
        self.assertIn("Lucas 2:11",user)
        self.assertNotIn("NÃO ENVIAR",user)

    def test_preview_svg_nao_expoe_gabarito(self):
        p=create_activity_page("math","9-12",instruction="Resolva.",content={"items":[{"expression":"2+3","answer":5}]})
        svg=render_activity_svg(p)
        self.assertIn("2+3",svg)
        self.assertNotIn(">5<",svg)
        self.assertIn("gabarito não impresso",svg)

if __name__=='__main__': unittest.main()

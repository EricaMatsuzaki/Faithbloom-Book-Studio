import unittest

from translation_localization import (
    LOCALIZACOES,
    normalize_locale,
    sugerir_onomatopeias,
    criar_registro_biblico,
    validar_registro_biblico,
    texto_biblico_para_exportacao,
    construir_prompt_localizacao,
    normalizar_resultado_localizacao,
    revisar_localizacao_estrutural,
)
from agents.tradutor import tradutor_node


class Refinamento06Tests(unittest.TestCase):
    def setUp(self):
        self.master={
            "titulo":"Quando Mel Aprendeu a Esperar",
            "colecao":"Pequenas Histórias, Grandes Lições",
            "idioma_original":"pt-BR",
            "versiculo_referencia":"Eclesiastes 3:1",
            "versiculo_texto_original":"Tudo tem o seu tempo determinado.",
            "personagens":{"Mel":{"nome":"Mel"},"Téo":{"nome":"Téo"}},
            "cenas_texto":[
                {"numero":1,"texto":"Mel queria tudo depressa.","emocao":"ansiedade"},
                {"numero":2,"texto":"Tudo tem o seu tempo determinado.","emocao":"fé"},
            ],
            "licao_final":"Esperar também é confiar em Deus.",
            "dedicatoria_texto":"Para Erica e sua família.",
            "lista_dedicatoria":[{"pessoa":"Erica","relacao":"autora"}],
        }

    def test_variantes_ingles_estao_disponiveis(self):
        for loc in ("en-US","en-CA","en-GB","en-AU","en-INT"):
            self.assertIn(loc,LOCALIZACOES)
        self.assertEqual(normalize_locale("en"),"en-US")

    def test_sons_sao_localizados_por_mercado(self):
        self.assertIn("PLOP!",sugerir_onomatopeias("queda_engracada","en-US"))
        self.assertIn("どてん！",sugerir_onomatopeias("queda_engracada","ja-JP"))
        self.assertNotEqual(sugerir_onomatopeias("espirro","pt-BR"),sugerir_onomatopeias("espirro","en-US"))

    def test_biblia_sem_texto_fica_reference_only(self):
        rec=criar_registro_biblico("Lucas 2:11","en-US")
        self.assertEqual(rec["status"],"reference_only")
        exp=texto_biblico_para_exportacao(rec)
        self.assertFalse(exp["pode_exportar_texto"])
        self.assertEqual(exp["texto"],"")

    def test_biblia_texto_exige_versao_e_aprovacao(self):
        rec=criar_registro_biblico("Lucas 2:11","en-US",texto_aprovado="Approved verse text")
        erros=validar_registro_biblico(rec)
        self.assertTrue(any("versão" in x.lower() for x in erros))
        self.assertTrue(any("aprovado" in x.lower() for x in erros))

    def test_texto_biblico_master_nao_vai_para_payload(self):
        prompt,payload=construir_prompt_localizacao(self.master,"en-US")
        blob=repr(payload)
        self.assertNotIn("Tudo tem o seu tempo determinado.",blob)
        self.assertIn("BIBLE_VERSE_PROTECTED",blob)
        self.assertIn("NÃO traduza",prompt)

    def test_modelo_nao_pode_injetar_scripture_text(self):
        out=normalizar_resultado_localizacao({"titulo":"X","scripture_text":"inventado","cenas_texto":[]},"en-US")
        self.assertNotIn("scripture_text",out)
        self.assertFalse(out["bible_ai_translation_allowed"])

    def test_revisor_detecta_contagem_de_cenas(self):
        trad={"locale":"en-US","bible_ai_translation_allowed":False,"cenas_texto":[{"numero":1,"texto":"Mel was impatient."}]}
        r=revisar_localizacao_estrutural(self.master,trad)
        self.assertFalse(r["ok"])
        self.assertTrue(any(a["codigo"]=="scene_count" for a in r["alertas"]))

    def test_tradutor_legado_usa_locale_e_bible_guard(self):
        state=dict(self.master)
        state.update({"idiomas_alvo":["en"],"faixa_etaria":"3–8","glossario_colecao":{},"bible_records":{}})
        calls=[]
        def fake_llm(sistema,instrucao):
            calls.append((sistema,instrucao))
            return {"titulo":"When Mel Learned to Wait","cenas_texto":[{"numero":1,"texto":"Mel wanted everything fast."},{"numero":2,"texto":"[BIBLE_VERSE_PROTECTED:Eclesiastes 3:1]"}]}
        result=tradutor_node(state,fake_llm)
        self.assertIn("en-US",result["traducoes"])
        self.assertFalse(result["traducoes"]["en-US"]["bible_ai_translation_allowed"])
        self.assertNotIn("Tudo tem o seu tempo determinado.",calls[0][1])


if __name__ == "__main__":
    unittest.main()

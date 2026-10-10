import unittest

from originality_guard import creation_originality_contract, evaluate_originality
from agents.diagramador import diagramador_node


class OriginalityGuardTests(unittest.TestCase):
    def _state(self):
        return {
            "titulo": "Luna e a Caixa das Pequenas Coragens",
            "subtitulo": "",
            "faixa_etaria": "6–8",
            "paginas_minimas": 24,
            "cenas_texto": [
                {"numero": i, "texto": f"Luna tentou uma ideia nova na cena {i} e descobriu algo sobre coragem."}
                for i in range(1, 13)
            ],
            "licao_final": "Coragem também é pedir ajuda e continuar com fé.",
            "versiculo_referencia": "Salmos 56:3",
            "personagens": {"Luna": {"nome": "Luna"}},
            "dedicatoria_texto": "Para crianças curiosas.",
            "sinopse_vendas_curta": "Uma aventura sobre coragem, amizade e fé.",
            "boas_vindas": "Bem-vindos.",
            "pais_educadores": {"mensagem": "Conversem sobre coragem."},
            "ficha_pedagogica": {"tema_central": "coragem"},
            "estilo_narrativo": "misto",
            "paginas_colorir": [{"numero": 1}, {"numero": 6}, {"numero": 12}],
        }

    def test_contract_separa_mecanismo_de_expressao(self):
        state = {
            "inspiration_references": [
                {"title": "Obra de referência", "allowed_use": "principles_only"}
            ]
        }
        text = creation_originality_contract(state)
        self.assertIn("SOMENTE princípios gerais", text)
        self.assertIn("não imite", text.lower())
        self.assertIn("Obra de referência", text)

    def test_sem_evidencia_de_overlap_pass_internal(self):
        report = evaluate_originality(self._state())
        self.assertEqual(report["status"], "PASS_INTERNAL")
        self.assertFalse(report["policy"]["worldwide_novelty_certified"])

    def test_overlap_longo_com_texto_de_clearance_bloqueia(self):
        state = self._state()
        state["cenas_texto"][0]["texto"] = "A lua pequena guardava sete segredos dentro da velha caixa azul brilhante."
        refs = [{
            "title": "Referência X",
            "text_excerpt": "Naquela noite, a lua pequena guardava sete segredos dentro da velha caixa azul brilhante e ninguém sabia.",
        }]
        report = evaluate_originality(state, references=refs)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(any(x["code"] == "DISTINCTIVE_PHRASE_OVERLAP" for x in report["blockers"]))

    def test_resumo_conceitual_nao_e_tratado_como_texto_copiado(self):
        state = self._state()
        refs = [{
            "title": "Livro cumulativo",
            "summary": "História com repetição, humor e animais que aparecem aos poucos.",
            "allowed_use": "principles_only",
        }]
        report = evaluate_originality(state, references=refs)
        self.assertEqual(report["status"], "PASS_INTERNAL")

    def test_pedido_explicito_de_imitacao_bloqueia(self):
        state = self._state()
        state["creative_brief"] = "Faça no estilo de uma autora famosa e copie a mesma voz."
        report = evaluate_originality(state)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(any(x["code"] == "IMITATION_REQUEST" for x in report["blockers"]))

    def test_titulo_muito_proximo_pede_revisao_sem_falso_certificado(self):
        state = self._state()
        state["titulo"] = "A Caixa das Pequenas Coragens"
        refs = [{"title": "A Caixa das Pequenas Coragens!"}]
        report = evaluate_originality(state, references=refs)
        self.assertEqual(report["status"], "NEEDS_REVIEW")
        self.assertTrue(any(x["code"] == "TITLE_TOO_CLOSE" for x in report["review_items"]))

    def test_diagramador_bloqueia_pacote_quando_guard_bloqueia(self):
        state = self._state()
        state["creative_brief"] = "Copie a mesma voz de uma obra conhecida."
        out = diagramador_node(state)
        self.assertFalse(out["pacote_pronto"])
        self.assertFalse(out["checklist_kdp"]["originalidade_interna_ok"])
        self.assertEqual(out["originality_guard_report"]["status"], "BLOCKED")
        self.assertTrue(any("ORIGINALITY GUARD" in n for n in out.get("notas_revisor", [])))


if __name__ == "__main__":
    unittest.main()

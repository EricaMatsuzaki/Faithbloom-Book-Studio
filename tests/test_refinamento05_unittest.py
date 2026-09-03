import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from coloring_book_doctor import analisar_line_art_avancada, auditar_lote_colorir, gerar_plano_recuperacao, plano_acabamento_colorir
import cover_master


class Refinamento05Tests(unittest.TestCase):
    def _img(self, path: Path, gray=False):
        im = Image.new("L", (300, 300), 255)
        d = ImageDraw.Draw(im)
        d.ellipse((60, 50, 240, 230), outline=128 if gray else 0, width=8)
        im.save(path)

    def test_line_art_qa(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.png"; self._img(p)
            r = analisar_line_art_avancada(str(p), "5-6", 1, 1)
            self.assertEqual(r["print_qa"]["ppi_efetivo"], 300.0)
            self.assertIn(r["status"], {"adequada", "ajustes", "atencao", "bloqueante"})

    def test_batch_plan(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.png"; self._img(p, gray=True)
            rel = auditar_lote_colorir([{"id":"x", "pagina":1, "arquivo":str(p)}], "3-4")
            plan = gerar_plano_recuperacao(rel)
            self.assertEqual(len(plan["itens"]), 1)

    def test_finish_plan(self):
        p = plano_acabamento_colorir(["Copyright"], True)
        self.assertIn("Capa frontal", p["essenciais"])
        self.assertIn("Copyright", p["opcionais_selecionados"])

    def test_cover_plan_versioning(self):
        with tempfile.TemporaryDirectory() as td:
            projeto={"id":"x","pasta":td,"titulo":"Cute"}
            p=Path(td)/"f.png"; Image.new("RGB",(100,100),"white").save(p)
            cover_master.criar_cover_master(projeto)
            rec=cover_master.registrar_variacao_cover(projeto,"frente",str(p),"teste")
            cover_master.aprovar_variacao_cover(projeto,rec["id"])
            plan=cover_master.carregar_cover_master(projeto)
            self.assertEqual(cover_master.variacao_selecionada(plan,"frente")["id"],rec["id"])

    def test_cover_prompt_has_no_ai_text(self):
        prompt=cover_master.montar_prompt_cover_master("Cute",[],"","jardim","")
        self.assertIn("SEM título",prompt)
        self.assertIn("SEM texto",prompt)


if __name__ == "__main__":
    unittest.main()

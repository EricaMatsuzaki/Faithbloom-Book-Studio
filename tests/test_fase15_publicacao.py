import os, tempfile, unittest
from pathlib import Path
from pacote_publicacao import normalizar_metadata, checklist_publicacao, disclosure_ia, gerar_pacote_publicacao

class Fase15Tests(unittest.TestCase):
    def base(self):
        return {"titulo":"Teste","autora":"Erica Matsuzaki","sinopse_vendas_curta":"Descrição","palavras_chave_kdp":["a"],"categorias_sugeridas":["Cat"],"revisao_aprovada":True,"preflight_impressao":{"bloqueios":[]}}
    def test_metadata_limita(self):
        s=self.base(); s["palavras_chave_kdp"]=list(map(str,range(10))); s["categorias_sugeridas"]=list(map(str,range(5)))
        m=normalizar_metadata(s); self.assertEqual(len(m["palavras_chave"]),7); self.assertEqual(len(m["categorias"]),3)
    def test_disclosure(self):
        s=self.base(); s["disclosure_ia"]={"texto_gerado_ia":True,"revisado_pela_autora":True}
        self.assertTrue(disclosure_ia(s)["texto_gerado_ia"])
    def test_pacote(self):
        with tempfile.TemporaryDirectory() as td:
            miolo=os.path.join(td,"m.pdf"); capa=os.path.join(td,"c.pdf")
            Path(miolo).write_bytes(b"pdf"); Path(capa).write_bytes(b"pdf")
            s=self.base(); s.update({"pdf_miolo":miolo,"capa_fisica_pdf":capa})
            r=gerar_pacote_publicacao(s, os.path.join(td,"out")); self.assertTrue(os.path.exists(r["zip"]))

if __name__=='__main__': unittest.main()

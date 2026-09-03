import tempfile, unittest
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
from book_doctor import criar_projeto,auditar_pdf,auditar_imagem,gerar_relatorio
class TestBookDoctor(unittest.TestCase):
    def test_image_ppi(self):
        d=Path(tempfile.mkdtemp()); p=d/'x.png'; Image.new('RGB',(3000,3000),'white').save(p)
        r=auditar_imagem(str(p),10,10); self.assertEqual(r['ppi_efetivo'],300.0); self.assertEqual(r['status'],'excelente')
    def test_pdf_preserves(self):
        d=Path(tempfile.mkdtemp()); p=d/'x.pdf'; c=canvas.Canvas(str(p),pagesize=(612,612)); c.drawString(20,20,'test'); c.showPage(); c.save()
        r=auditar_pdf(str(p)); self.assertEqual(r['paginas_total'],1); self.assertFalse(r['original_alterado'])
    def test_report_has_pending_human_review(self):
        pr=criar_projeto('Teste Doctor'); r=gerar_relatorio(pr); self.assertTrue(r['revisoes_pendentes'])
if __name__=='__main__': unittest.main()

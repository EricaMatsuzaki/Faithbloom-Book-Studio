import unittest
from copy import deepcopy
from historia_natal import ESTADO_INICIAL_NATAL
from integracao_e2e import preparar_state_retomada
from piloto_visual import cenas_recomendadas_piloto, detectar_personagens_cena, readiness_producao

class TestPilotoVisual(unittest.TestCase):
    def test_recomenda_lote(self):
        s=preparar_state_retomada(ESTADO_INICIAL_NATAL)
        r=cenas_recomendadas_piloto(s)
        self.assertEqual(len(r),3)
        self.assertIn(8,r)
    def test_detecta_trio_na_cena8(self):
        s=preparar_state_retomada(ESTADO_INICIAL_NATAL)
        c=next(c for c in s['cenas_texto'] if c['numero']==8)
        nomes=detectar_personagens_cena(s,c)
        self.assertTrue({'Mel','Manu','Max'}.issubset(set(nomes)))
    def test_nao_libera_sem_aprovacao(self):
        s=preparar_state_retomada(ESTADO_INICIAL_NATAL)
        self.assertFalse(readiness_producao(s)['liberado_producao_completa'])
if __name__=='__main__': unittest.main()

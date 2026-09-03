import os
import tempfile
import unittest
from unittest.mock import patch

import controle_geracao as cg


class ControleGeracaoTests(unittest.TestCase):
    def setUp(self):
        cg._IN_FLIGHT.clear(); cg._RECENT.clear()

    def test_estimativa_imagem(self):
        self.assertGreater(cg.estimar_custo("imagem",3),0)

    def test_bloqueia_lote_grande(self):
        with self.assertRaises(cg.GeracaoBloqueada):
            cg.validar_lote_imagens(cg.POLITICA.max_imagens_lote+1)

    def test_bloqueia_mesma_requisicao_em_andamento(self):
        a=cg.iniciar_requisicao("texto","modelo","mesmo conteudo",0)
        try:
            with self.assertRaises(cg.GeracaoBloqueada):
                cg.iniciar_requisicao("texto","modelo","mesmo conteudo",0)
        finally:
            cg.finalizar_requisicao(a[0],a[1],"texto","modelo",a[2],a[3],"sucesso")

    def test_sanitiza_chave(self):
        s=cg.sanitizar_texto("Authorization Bearer abc.def e sk-or-v1-SEGREDO123")
        self.assertNotIn("SEGREDO123",s)
        self.assertNotIn("abc.def",s)


if __name__ == '__main__':
    unittest.main()

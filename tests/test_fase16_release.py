import unittest

import qa_release as qa


class Fase16ReleaseTests(unittest.TestCase):
    def test_requirements_essenciais(self):
        checks = qa.verificar_requirements()
        self.assertTrue(all(x["ok"] for x in checks), checks)

    def test_rotas_apontam_para_paginas_existentes(self):
        checks = qa.verificar_page_links()
        self.assertTrue(all(x["ok"] for x in checks), checks)

    def test_sem_chave_real_no_codigo(self):
        checks = qa.verificar_segredos()
        self.assertTrue(all(x["ok"] for x in checks), checks)

    def test_sintaxe_projeto(self):
        checks = qa.verificar_sintaxe()
        self.assertTrue(all(x["ok"] for x in checks), checks)


if __name__ == "__main__":
    unittest.main()

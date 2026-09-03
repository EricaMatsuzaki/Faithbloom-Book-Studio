import unittest

from integracao_e2e import diagnostico_natal, preparar_state_retomada, validar_state_story
from historia_natal import ESTADO_INICIAL_NATAL


class TestIntegracaoE2E(unittest.TestCase):
    def test_state_natal_pode_ser_preparado_sem_mutar_original(self):
        original_tem = "historico_imagens_cenas" in ESTADO_INICIAL_NATAL
        s = preparar_state_retomada(ESTADO_INICIAL_NATAL)
        self.assertIn("historico_imagens_cenas", s)
        self.assertIn("instrucoes_imagens_cenas", s)
        self.assertEqual(original_tem, "historico_imagens_cenas" in ESTADO_INICIAL_NATAL)

    def test_natal_tem_cenas_e_personagens(self):
        d = diagnostico_natal()
        self.assertTrue(d["state"].get("cenas_texto"))
        self.assertGreaterEqual(len(d["state"].get("personagens", {})), 1)

    def test_validator_reprova_state_vazio(self):
        checks = validar_state_story({})
        self.assertTrue(any(not c["ok"] for c in checks))


if __name__ == "__main__":
    unittest.main()

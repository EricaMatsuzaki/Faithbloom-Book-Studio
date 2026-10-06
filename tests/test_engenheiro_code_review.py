import base64
import unittest
from unittest.mock import MagicMock, patch

import engenheiro_code_review as eng


def _resp(status=200, json_body=None, text=""):
    resp = MagicMock()
    resp.status_code = status
    resp.content = b"x" if json_body is not None else b""
    resp.json.return_value = json_body or {}
    resp.text = text
    return resp


class EngenheiroTests(unittest.TestCase):
    def setUp(self):
        self._token_original = eng.GITHUB_TOKEN

    def tearDown(self):
        eng.GITHUB_TOKEN = self._token_original

    def test_sem_token_da_erro_claro_ao_ler_arquivo(self):
        eng.GITHUB_TOKEN = ""
        resultado = eng.investigar_e_corrigir("bug qualquer", "arquivo.py")
        self.assertFalse(resultado.sucesso)
        self.assertIn("GITHUB_TOKEN", resultado.diagnostico)

    @patch("engenheiro_code_review.chamar_llm")
    @patch("engenheiro_code_review.requests.request")
    def test_confianca_baixa_nao_abre_pr(self, mock_request, mock_llm):
        eng.GITHUB_TOKEN = "token-teste"
        conteudo_b64 = base64.b64encode(b"codigo original").decode()
        mock_request.return_value = _resp(200, {"content": conteudo_b64, "sha": "sha-original"})
        mock_llm.return_value = {
            "diagnostico": "não tenho certeza da causa raiz",
            "confianca": "baixa",
            "conteudo_novo_do_arquivo": None,
            "resumo_da_mudanca": "",
            "risco": "",
        }
        resultado = eng.investigar_e_corrigir("bug qualquer", "arquivo.py")
        self.assertFalse(resultado.sucesso)
        self.assertIn("Confiança", resultado.motivo_bloqueio)
        # só a leitura do arquivo, nenhuma chamada de escrita (branch/commit/PR)
        self.assertEqual(mock_request.call_count, 1)

    @patch("engenheiro_code_review.chamar_llm")
    @patch("engenheiro_code_review.requests.request")
    def test_confianca_alta_cria_branch_commita_e_abre_pr(self, mock_request, mock_llm):
        eng.GITHUB_TOKEN = "token-teste"
        conteudo_b64 = base64.b64encode(b"codigo original com bug").decode()

        respostas = [
            _resp(200, {"content": conteudo_b64, "sha": "sha-original"}),  # obter conteúdo
            _resp(200, {"object": {"sha": "sha-da-base"}}),  # ref da branch base
            _resp(201, {"ref": "refs/heads/auto-fix/x"}),  # criar branch
            _resp(200, {"content": "..."}),  # commit do arquivo
            _resp(201, {"html_url": "https://github.com/x/y/pull/99"}),  # abrir PR
        ]
        mock_request.side_effect = respostas

        mock_llm.return_value = {
            "diagnostico": "o retry engolia a exceção de interrupção",
            "confianca": "alta",
            "conteudo_novo_do_arquivo": "codigo corrigido sem o bug",
            "resumo_da_mudanca": "trocou except Exception por except BaseException",
            "risco": "nenhum conhecido",
        }
        resultado = eng.investigar_e_corrigir("bug qualquer", "arquivo.py")
        self.assertTrue(resultado.sucesso)
        self.assertEqual(resultado.pr_url, "https://github.com/x/y/pull/99")
        self.assertTrue(resultado.branch.startswith("auto-fix/arquivo-py-"))
        self.assertEqual(mock_request.call_count, 5)

        # o PR deve ser aberto como Draft
        chamada_pr = mock_request.call_args_list[-1]
        self.assertTrue(chamada_pr.kwargs["json"]["draft"])
        self.assertNotEqual(chamada_pr.kwargs["json"]["base"], "release/2.0.0-rc5-skills")

    @patch("engenheiro_code_review.chamar_llm")
    @patch("engenheiro_code_review.requests.request")
    def test_correcao_identica_ao_original_nao_abre_pr(self, mock_request, mock_llm):
        eng.GITHUB_TOKEN = "token-teste"
        conteudo_b64 = base64.b64encode(b"codigo identico").decode()
        mock_request.return_value = _resp(200, {"content": conteudo_b64, "sha": "sha-original"})
        mock_llm.return_value = {
            "diagnostico": "não achei nada de errado",
            "confianca": "alta",
            "conteudo_novo_do_arquivo": "codigo identico",
            "resumo_da_mudanca": "",
            "risco": "",
        }
        resultado = eng.investigar_e_corrigir("bug qualquer", "arquivo.py")
        self.assertFalse(resultado.sucesso)
        self.assertIn("idêntica", resultado.motivo_bloqueio)
        self.assertEqual(mock_request.call_count, 1)

    @patch("engenheiro_code_review.requests.request")
    def test_erro_http_ao_ler_arquivo_e_tratado(self, mock_request):
        eng.GITHUB_TOKEN = "token-teste"
        mock_request.return_value = _resp(404, text="Not Found")
        resultado = eng.investigar_e_corrigir("bug qualquer", "arquivo-inexistente.py")
        self.assertFalse(resultado.sucesso)
        self.assertIn("Não consegui ler", resultado.diagnostico)


if __name__ == "__main__":
    unittest.main()

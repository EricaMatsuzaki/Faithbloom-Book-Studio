import json
import unittest
from unittest.mock import MagicMock, patch

import controle_geracao as cg
import gemini_client as gc
import openrouter_client as orc


def _resposta_gemini(payload: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]
    }
    resp.raise_for_status = MagicMock()
    return resp


def _resposta_openrouter(payload: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(payload)}}]
    }
    resp.raise_for_status = MagicMock()
    return resp


class GeminiClientTests(unittest.TestCase):
    def setUp(self):
        cg._IN_FLIGHT.clear()
        cg._RECENT.clear()
        self._chave_original = gc.GEMINI_API_KEY

    def tearDown(self):
        gc.GEMINI_API_KEY = self._chave_original

    def test_indisponivel_sem_chave(self):
        gc.GEMINI_API_KEY = ""
        self.assertFalse(gc.gemini_disponivel())
        with self.assertRaises(gc.GeminiFaithBloomError):
            gc.chamar_llm_gemini("sistema", "instrucao")

    def test_disponivel_com_chave(self):
        gc.GEMINI_API_KEY = "chave-teste"
        self.assertTrue(gc.gemini_disponivel())

    @patch("gemini_client.requests.post")
    def test_chamar_llm_gemini_sucesso_no_primeiro_modelo(self, mock_post):
        gc.GEMINI_API_KEY = "chave-teste"
        mock_post.return_value = _resposta_gemini({"ok": True, "campo": "valor"})
        resultado = gc.chamar_llm_gemini("sistema", "instrucao")
        self.assertEqual(resultado, {"ok": True, "campo": "valor"})
        self.assertEqual(mock_post.call_count, 1)

    @patch("gemini_client.time.sleep")
    @patch("gemini_client.requests.post")
    def test_chamar_llm_gemini_cai_para_proximo_modelo_da_lista(self, mock_post, mock_sleep):
        gc.GEMINI_API_KEY = "chave-teste"

        def efeito(url, params=None, json=None, timeout=None):
            if gc.MODELO_TEXTO_PADRAO in url:
                raise gc.requests.exceptions.RequestException("modelo indisponível")
            return _resposta_gemini({"ok": True})

        mock_post.side_effect = efeito
        resultado = gc.chamar_llm_gemini("sistema", "instrucao")
        self.assertEqual(resultado, {"ok": True})
        self.assertGreaterEqual(mock_post.call_count, 2)

    @patch("gemini_client.time.sleep")
    @patch("gemini_client.requests.get")
    @patch("gemini_client.requests.post")
    def test_chamar_llm_gemini_usa_descoberta_dinamica_como_ultimo_recurso(self, mock_post, mock_get, mock_sleep):
        gc.GEMINI_API_KEY = "chave-teste"

        resp_get = MagicMock()
        resp_get.raise_for_status = MagicMock()
        resp_get.json.return_value = {
            "models": [
                {"name": "models/gemini-modelo-novo", "supportedGenerationMethods": ["generateContent"]},
            ]
        }
        mock_get.return_value = resp_get

        # todos os modelos da lista fixa falham (não importa quantas vezes o
        # retry interno chame); só o modelo descoberto dinamicamente responde
        def efeito(url, params=None, json=None, timeout=None):
            if "gemini-modelo-novo" in url:
                return _resposta_gemini({"ok": "via-descoberta"})
            raise gc.requests.exceptions.RequestException("modelo fixo indisponível")

        mock_post.side_effect = efeito
        resultado = gc.chamar_llm_gemini("sistema", "instrucao")
        self.assertEqual(resultado, {"ok": "via-descoberta"})
        mock_get.assert_called_once()


class OpenRouterDispatcherTests(unittest.TestCase):
    """Cobre o roteamento multi-provedor em openrouter_client.chamar_llm."""

    def setUp(self):
        cg._IN_FLIGHT.clear()
        cg._RECENT.clear()
        self._provedor_original = orc.PROVEDOR_TEXTO
        self._chave_or_original = orc.OPENROUTER_API_KEY
        self._chave_gemini_original = gc.GEMINI_API_KEY

    def tearDown(self):
        orc.PROVEDOR_TEXTO = self._provedor_original
        orc.OPENROUTER_API_KEY = self._chave_or_original
        gc.GEMINI_API_KEY = self._chave_gemini_original

    def test_prefere_gemini_quando_disponivel(self):
        orc.PROVEDOR_TEXTO = "auto"
        gc.GEMINI_API_KEY = "chave-teste"
        with patch("gemini_client.chamar_llm_gemini", return_value={"via": "gemini"}) as mock_gemini, \
             patch.object(orc, "_chamar_llm_openrouter") as mock_openrouter:
            resultado = orc.chamar_llm("sistema", "instrucao")
        self.assertEqual(resultado, {"via": "gemini"})
        mock_gemini.assert_called_once()
        mock_openrouter.assert_not_called()

    def test_cai_para_openrouter_se_gemini_falhar(self):
        orc.PROVEDOR_TEXTO = "auto"
        gc.GEMINI_API_KEY = "chave-teste"
        orc.OPENROUTER_API_KEY = "chave-or-teste"
        with patch("gemini_client.chamar_llm_gemini", side_effect=gc.GeminiFaithBloomError("falhou")), \
             patch.object(orc, "_chamar_llm_openrouter", return_value={"via": "openrouter"}) as mock_openrouter:
            resultado = orc.chamar_llm("sistema", "instrucao")
        self.assertEqual(resultado, {"via": "openrouter"})
        mock_openrouter.assert_called_once()

    def test_erro_quando_nenhum_provedor_configurado(self):
        orc.PROVEDOR_TEXTO = "auto"
        gc.GEMINI_API_KEY = ""
        orc.OPENROUTER_API_KEY = ""
        # Sem Gemini disponível, o dispatcher chama _chamar_llm_openrouter
        # incondicionalmente (como o código original sempre fez); sem chave
        # da OpenRouter, o erro real vem de dentro dela (_headers()).
        with self.assertRaises(RuntimeError):
            orc.chamar_llm("sistema", "instrucao")

    def test_provedor_gemini_forcado_sem_chave_da_erro_claro(self):
        orc.PROVEDOR_TEXTO = "gemini"
        gc.GEMINI_API_KEY = ""
        orc.OPENROUTER_API_KEY = "chave-or-teste"
        with patch.object(orc, "_chamar_llm_openrouter") as mock_openrouter:
            with self.assertRaises(orc.OpenRouterFaithBloomError):
                orc.chamar_llm("sistema", "instrucao")
        mock_openrouter.assert_not_called()

    def test_forcar_provedor_openrouter_ignora_gemini(self):
        orc.PROVEDOR_TEXTO = "openrouter"
        gc.GEMINI_API_KEY = "chave-teste"
        orc.OPENROUTER_API_KEY = "chave-or-teste"
        with patch("gemini_client.chamar_llm_gemini") as mock_gemini, \
             patch.object(orc, "_chamar_llm_openrouter", return_value={"via": "openrouter"}) as mock_openrouter:
            resultado = orc.chamar_llm("sistema", "instrucao")
        self.assertEqual(resultado, {"via": "openrouter"})
        mock_gemini.assert_not_called()
        mock_openrouter.assert_called_once()

    def test_texto_provedor_ativo_reflete_ambiente(self):
        orc.PROVEDOR_TEXTO = "auto"
        gc.GEMINI_API_KEY = "chave-teste"
        self.assertEqual(orc.texto_provedor_ativo(), "gemini")
        gc.GEMINI_API_KEY = ""
        orc.OPENROUTER_API_KEY = "chave-or-teste"
        self.assertEqual(orc.texto_provedor_ativo(), "openrouter")
        orc.OPENROUTER_API_KEY = ""
        self.assertEqual(orc.texto_provedor_ativo(), "indisponível")


if __name__ == "__main__":
    unittest.main()

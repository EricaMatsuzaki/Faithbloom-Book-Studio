"""Cliente Google AI Studio (Gemini) do FaithBloom — camada de texto gratuita/econômica.

Contexto: os créditos pagos da OpenRouter se esgotaram. Este módulo cobre a
modalidade de TEXTO (Jarvis, classificação, Roteirista, Revisor, DNA visual
textual, etc.) usando a API gratuita/econômica do Google AI Studio como
primeira tentativa. Imagem e áudio continuam na OpenRouter (ver
openrouter_client.py) até que a rota Gemini para essas modalidades seja
validada com o mesmo nível de segurança e QA.

Reaproveita integralmente o mesmo módulo de custo/segurança/dedup usado pela
OpenRouter (controle_geracao.py) — nenhuma lógica de orçamento, cooldown ou
sanitização de log é duplicada aqui.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import requests

from controle_geracao import (
    POLITICA,
    extrair_custo_reportado,
    finalizar_requisicao,
    iniciar_requisicao,
    sanitizar_texto,
)

# Aceita GEMINI_API_KEY (nome preferido) ou GOOGLE_API_KEY (nome usado pelo
# próprio Google AI Studio em vários exemplos oficiais), para reduzir atrito
# de configuração.
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Modelo preferido, configurável por ambiente. Os demais nomes funcionam como
# rede de segurança: se o modelo preferido não existir mais/estiver
# indisponível para a chave, o cliente tenta os seguintes antes de desistir.
MODELO_TEXTO_PADRAO = os.environ.get("GEMINI_MODELO_TEXTO", "gemini-flash-latest")
_MODELOS_TEXTO_RESERVA = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


class GeminiFaithBloomError(RuntimeError):
    pass


def gemini_disponivel() -> bool:
    """Usado pelo openrouter_client (e por telas de diagnóstico) para decidir
    se vale tentar o Gemini antes da OpenRouter."""
    return bool(GEMINI_API_KEY)


def _ordem_modelos_texto() -> list[str]:
    ordem = [MODELO_TEXTO_PADRAO] + _MODELOS_TEXTO_RESERVA
    vistos: set[str] = set()
    saida = []
    for m in ordem:
        if m and m not in vistos:
            vistos.add(m)
            saida.append(m)
    return saida


def _descobrir_modelos_disponiveis() -> list[str]:
    """Descoberta dinâmica: pergunta à própria API do Google quais modelos a
    chave atual pode usar. Só é chamada quando a lista fixa acima falha
    inteira, para não gastar uma chamada extra no caminho feliz."""
    if not GEMINI_API_KEY:
        return []
    try:
        resp = requests.get(
            f"{GEMINI_BASE_URL}/models",
            params={"key": GEMINI_API_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        dados = resp.json()
        nomes = []
        for modelo in dados.get("models", []):
            metodos = modelo.get("supportedGenerationMethods", [])
            nome = str(modelo.get("name", "")).removeprefix("models/")
            if "generateContent" in metodos and nome:
                nomes.append(nome)
        return nomes
    except requests.RequestException:
        return []


def _post_com_retry(url: str, payload: dict, timeout: int) -> requests.Response:
    ultimo: Exception | None = None
    for tentativa in range(1, POLITICA.tentativas_http + 1):
        try:
            resp = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=timeout)
            if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                if tentativa < POLITICA.tentativas_http:
                    time.sleep(POLITICA.backoff_inicial_seg * (2 ** (tentativa - 1)))
                    continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            ultimo = exc
            if tentativa < POLITICA.tentativas_http:
                time.sleep(POLITICA.backoff_inicial_seg * (2 ** (tentativa - 1)))
    codigo = getattr(getattr(ultimo, "response", None), "status_code", None)
    sufixo = f" (HTTP {codigo})" if codigo else ""
    raise GeminiFaithBloomError(
        "O Gemini (Google AI Studio) não respondeu corretamente após novas tentativas" + sufixo + ". "
        "Nenhuma chave ou payload foi gravado no log."
    ) from ultimo


def _json_resposta(resp: requests.Response) -> dict[str, Any]:
    try:
        dados = resp.json()
    except ValueError as exc:
        raise GeminiFaithBloomError("O Gemini retornou uma resposta que não é JSON válido.") from exc
    if not isinstance(dados, dict):
        raise GeminiFaithBloomError("Formato inesperado de resposta do Gemini.")
    return dados


def _extrair_texto(dados: dict) -> str:
    try:
        return dados["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        motivo = ""
        try:
            motivo = dados["candidates"][0].get("finishReason", "")
        except Exception:
            pass
        sufixo = f" (finishReason={motivo})" if motivo else ""
        raise GeminiFaithBloomError(f"O Gemini não retornou texto utilizável{sufixo}.") from exc


def _tentar_modelo(modelo: str, sistema: str, instrucao: str, conteudo_assinatura: str) -> dict | list:
    modelo_marcado = f"gemini/{modelo}"
    req_id, assinatura, estimativa, inicio = iniciar_requisicao("texto", modelo_marcado, conteudo_assinatura)
    try:
        payload = {
            "system_instruction": {
                "parts": [{"text": sistema + "\n\nResponda APENAS em JSON válido, sem markdown e sem comentários."}]
            },
            "contents": [{"role": "user", "parts": [{"text": instrucao}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        resp = _post_com_retry(f"{GEMINI_BASE_URL}/models/{modelo}:generateContent", payload, 120)
        dados = _json_resposta(resp)
        texto = _extrair_texto(dados)
        texto_limpo = texto.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        resultado = json.loads(texto_limpo)
        finalizar_requisicao(
            req_id, assinatura, "texto", modelo_marcado, estimativa, inicio, "sucesso",
            extrair_custo_reportado(dados),
        )
        return resultado
    except BaseException as exc:
        finalizar_requisicao(
            req_id, assinatura, "texto", modelo_marcado, estimativa, inicio, "erro",
            detalhe=sanitizar_texto(str(exc)),
        )
        raise


def chamar_llm_gemini(sistema: str, instrucao: str) -> dict | list:
    """Mesmo contrato de openrouter_client.chamar_llm: recebe system + instrução,
    devolve JSON já decodificado (dict ou list). É a primeira tentativa
    (gratuita/econômica) antes de cair para a OpenRouter.
    """
    if not GEMINI_API_KEY:
        raise GeminiFaithBloomError(
            "GEMINI_API_KEY (ou GOOGLE_API_KEY) não configurada. "
            "Defina nos Secrets do ambiente para usar a camada gratuita/econômica."
        )

    conteudo_assinatura = sistema + "\n" + instrucao
    ultimo_erro: Exception | None = None

    for modelo in _ordem_modelos_texto():
        try:
            return _tentar_modelo(modelo, sistema, instrucao, conteudo_assinatura)
        except Exception as exc:
            ultimo_erro = exc
            continue

    # A lista fixa inteira falhou (ex.: nomes de modelo desatualizados para
    # esta chave). Antes de desistir, pergunta à API quais modelos existem
    # de fato e tenta os que ainda não foram tentados.
    ja_tentados = set(_ordem_modelos_texto())
    for modelo in _descobrir_modelos_disponiveis():
        if modelo in ja_tentados:
            continue
        try:
            return _tentar_modelo(modelo, sistema, instrucao, conteudo_assinatura)
        except Exception as exc:
            ultimo_erro = exc
            continue

    raise GeminiFaithBloomError(
        "Nenhum modelo Gemini disponível respondeu corretamente para esta chave."
    ) from ultimo_erro

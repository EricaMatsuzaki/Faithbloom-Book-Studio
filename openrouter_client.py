"""
Cliente OpenRouter para o pipeline - texto E imagem pela mesma chave de
API (OPENROUTER_API_KEY), já que a Erica tem assinatura ativa lá.

Modelos sugeridos (configuráveis por variável de ambiente):
- Texto: qualquer modelo de raciocínio forte (ex: anthropic/claude-sonnet-4-6)
- Imagem: google/gemini-3.1-flash-image (Nano Banana 2) - recomendado
  pela melhor consistência de personagem multi-referência hoje.
  Alternativa: openai/gpt-image-1 (até 16 imagens de referência por edição).

Documentação: https://openrouter.ai/docs (Image API - modalidades
["image", "text"] no endpoint de chat completions, ou o endpoint
dedicado /v1/images).
"""

import base64
import json
import os
import uuid

import requests

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODELO_TEXTO = os.environ.get("OPENROUTER_MODELO_TEXTO", "anthropic/claude-sonnet-4-6")
MODELO_IMAGEM = os.environ.get("OPENROUTER_MODELO_IMAGEM", "google/gemini-3.1-flash-image")
MODELO_VOZ = os.environ.get("OPENROUTER_MODELO_VOZ", "google/gemini-3.1-flash-tts-preview")
VOZ_PADRAO = os.environ.get("OPENROUTER_VOZ_PADRAO", "")  # deixar em branco usa a voz padrão do provedor

PASTA_AUDIO = "saida_audio"
os.makedirs(PASTA_AUDIO, exist_ok=True)

PASTA_IMAGENS = "saida_imagens"
os.makedirs(PASTA_IMAGENS, exist_ok=True)


def _headers() -> dict:
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "Defina a variável de ambiente OPENROUTER_API_KEY antes de rodar."
        )
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


def chamar_llm(sistema: str, instrucao: str) -> dict:
    """
    Chama o modelo de texto via OpenRouter e espera um JSON de volta.
    Pede explicitamente output em JSON para simplificar o parsing.
    """
    payload = {
        "model": MODELO_TEXTO,
        "messages": [
            {"role": "system", "content": sistema + "\n\nResponda APENAS em JSON válido, sem markdown."},
            {"role": "user", "content": instrucao},
        ],
    }
    resp = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers=_headers(),
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    texto = resp.json()["choices"][0]["message"]["content"]
    texto_limpo = texto.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(texto_limpo)


def gerar_imagem(prompt: str, imagem_base: str | None = None) -> str:
    """
    Gera uma imagem via OpenRouter (Nano Banana 2 por padrão).
    Se imagem_base for passado (caminho de arquivo local), envia como
    referência visual junto ao prompt - é isso que trava a consistência
    do personagem entre cenas.
    Retorna o caminho do arquivo PNG salvo localmente.
    """
    content = [{"type": "text", "text": prompt}]

    if imagem_base and os.path.exists(imagem_base):
        with open(imagem_base, "rb") as f:
            b64_ref = base64.b64encode(f.read()).decode()
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64_ref}"},
            }
        )

    payload = {
        "model": MODELO_IMAGEM,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["image", "text"],
    }
    resp = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers=_headers(),
        json=payload,
        timeout=180,
    )
    resp.raise_for_status()
    dados = resp.json()

    # A imagem volta em base64 dentro da resposta - formato pode variar
    # ligeiramente por modelo, ajuste conforme a resposta real da API.
    imagens = dados["choices"][0]["message"].get("images", [])
    if not imagens:
        raise RuntimeError(f"Nenhuma imagem retornada pela API: {dados}")

    b64_imagem = imagens[0]["image_url"]["url"].split(",", 1)[1]
    caminho = os.path.join(PASTA_IMAGENS, f"{uuid.uuid4().hex}.png")
    with open(caminho, "wb") as f:
        f.write(base64.b64decode(b64_imagem))
    return caminho


def gerar_audio(texto_com_marcacoes: str, nome_arquivo: str) -> str:
    """
    Converte um trecho do roteiro de audiobook (já com as marcações
    [pausa curta], [voz suave], etc.) em áudio de verdade via OpenRouter
    TTS (endpoint dedicado /api/v1/audio/speech, compatível com a API
    de audio da OpenAI).

    O Gemini 3.1 Flash TTS aceita tags inline parecidas nativamente -
    se estiver usando outro modelo TTS sem suporte a tags, considere
    passar o texto por converter_marcacoes_para_texto_natural() antes.
    """
    payload = {
        "model": MODELO_VOZ,
        "input": texto_com_marcacoes,
        "response_format": "mp3",
    }
    if VOZ_PADRAO:
        payload["voice"] = VOZ_PADRAO

    resp = requests.post(
        f"{OPENROUTER_BASE_URL}/audio/speech",
        headers=_headers(),
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()

    caminho = os.path.join(PASTA_AUDIO, f"{nome_arquivo}.mp3")
    with open(caminho, "wb") as f:
        f.write(resp.content)  # a resposta é o áudio bruto, não JSON
    return caminho


def converter_marcacoes_para_texto_natural(texto_com_marcacoes: str) -> str:
    """
    Fallback para modelos TTS sem suporte a tags inline: troca nossas
    marcações por pontuação que a maioria dos motores de voz já
    interpreta naturalmente como pausa (reticências, quebra de linha).
    Use isso só se o modelo escolhido em MODELO_VOZ não suportar tags.
    """
    substituicoes = {
        "[pausa curta]": "...",
        "[pausa longa]": "...\n\n",
        "[voz suave]": "",
        "[voz animada]": "",
        "[voz sussurrada]": "",
    }
    texto = texto_com_marcacoes
    for marcado, natural in substituicoes.items():
        texto = texto.replace(marcado, natural)
    # remove marcações de ênfase, mantendo só a palavra
    import re
    texto = re.sub(r"\[ênfase:\s*(.*?)\]", r"\1", texto)
    return texto

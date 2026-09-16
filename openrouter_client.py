"""Cliente OpenRouter do FaithBloom com guardrails de custo/duplicidade (Fase 13).

Refinamento (16/09/2026): a modalidade de TEXTO agora tenta primeiro o Gemini
(Google AI Studio, gratuito/econômico — ver gemini_client.py) e só cai para a
OpenRouter se o Gemini não estiver configurado ou falhar. Isso mantém o SaaS
funcional mesmo sem crédito pago na OpenRouter. Imagem e áudio permanecem
exclusivamente na OpenRouter por enquanto: a rota Gemini para essas
modalidades ainda não foi validada com o mesmo nível de QA visual.

A interface pública deste módulo (chamar_llm, gerar_imagem, gerar_audio) não
muda para quem já importa daqui — nenhum agente precisa alterar seu import.
"""
from __future__ import annotations

import base64
import json
import os
import time
import uuid
from typing import Any

import requests

import gemini_client
from controle_geracao import (
    POLITICA,
    extrair_custo_reportado,
    finalizar_requisicao,
    iniciar_requisicao,
    sanitizar_texto,
)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODELO_TEXTO = os.environ.get("OPENROUTER_MODELO_TEXTO", "anthropic/claude-sonnet-4-6")
MODELO_IMAGEM = os.environ.get("OPENROUTER_MODELO_IMAGEM", "google/gemini-3.1-flash-image")
MODELO_VOZ = os.environ.get("OPENROUTER_MODELO_VOZ", "google/gemini-3.1-flash-tts-preview")
VOZ_PADRAO = os.environ.get("OPENROUTER_VOZ_PADRAO", "")

# "auto" (padrão): usa Gemini primeiro se GEMINI_API_KEY/GOOGLE_API_KEY estiver
# configurada, com fallback para a OpenRouter. "gemini" ou "openrouter" forçam
# um único provedor de texto (útil para diagnóstico/comparação).
PROVEDOR_TEXTO = os.environ.get("FAITHBLOOM_PROVEDOR_TEXTO", "auto").strip().lower()

PASTA_AUDIO = "saida_audio"
os.makedirs(PASTA_AUDIO, exist_ok=True)
PASTA_IMAGENS = "saida_imagens"
os.makedirs(PASTA_IMAGENS, exist_ok=True)


class OpenRouterFaithBloomError(RuntimeError):
    pass


def _headers() -> dict:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("Defina a variável de ambiente OPENROUTER_API_KEY antes de rodar.")
    return {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}


def _post_com_retry(url: str, payload: dict, timeout: int) -> requests.Response:
    ultimo: Exception | None = None
    for tentativa in range(1, POLITICA.tentativas_http + 1):
        try:
            resp=requests.post(url, headers=_headers(), json=payload, timeout=timeout)
            if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                if tentativa < POLITICA.tentativas_http:
                    time.sleep(POLITICA.backoff_inicial_seg * (2 ** (tentativa-1)))
                    continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            ultimo=exc
            if tentativa < POLITICA.tentativas_http:
                time.sleep(POLITICA.backoff_inicial_seg * (2 ** (tentativa-1)))
    codigo=getattr(getattr(ultimo,"response",None),"status_code",None)
    sufixo=f" (HTTP {codigo})" if codigo else ""
    raise OpenRouterFaithBloomError(
        "A OpenRouter não respondeu corretamente após novas tentativas" + sufixo + ". "
        "Nenhuma chave ou payload foi gravado no log."
    ) from ultimo


def _json_resposta(resp: requests.Response) -> dict[str,Any]:
    try:
        dados=resp.json()
    except ValueError as exc:
        raise OpenRouterFaithBloomError("A OpenRouter retornou uma resposta que não é JSON válido.") from exc
    if not isinstance(dados,dict):
        raise OpenRouterFaithBloomError("Formato inesperado de resposta da OpenRouter.")
    return dados


def texto_provedor_ativo() -> str:
    """Diagnóstico: qual provedor de texto o próximo chamar_llm() vai tentar
    primeiro, dado o ambiente atual. Usado por telas de status/onboarding."""
    if PROVEDOR_TEXTO == "openrouter":
        return "openrouter"
    if PROVEDOR_TEXTO == "gemini":
        return "gemini" if gemini_client.gemini_disponivel() else "indisponível"
    # modo "auto"
    if gemini_client.gemini_disponivel():
        return "gemini"
    if OPENROUTER_API_KEY:
        return "openrouter"
    return "indisponível"


def chamar_llm(sistema: str, instrucao: str) -> dict | list:
    """Ponto único chamado por todos os agentes. Decide o provedor de texto
    (Gemini gratuito/econômico primeiro, OpenRouter como fallback pago) sem
    exigir nenhuma mudança nos agentes que já importam esta função.
    """
    tentar_gemini = PROVEDOR_TEXTO != "openrouter" and gemini_client.gemini_disponivel()
    tentar_openrouter = PROVEDOR_TEXTO != "gemini" and bool(OPENROUTER_API_KEY)

    if tentar_gemini:
        try:
            return gemini_client.chamar_llm_gemini(sistema, instrucao)
        except Exception as exc_gemini:
            if not tentar_openrouter:
                raise
            # Cai silenciosamente para a OpenRouter; o erro do Gemini fica
            # registrado no log de gerações (via gemini_client), não é
            # descartado, só não interrompe o pedido do usuário.
            try:
                return _chamar_llm_openrouter(sistema, instrucao)
            except Exception as exc_openrouter:
                raise OpenRouterFaithBloomError(
                    "Nem o Gemini nem a OpenRouter responderam. "
                    f"Gemini: {exc_gemini}. OpenRouter: {exc_openrouter}."
                ) from exc_openrouter

    if tentar_openrouter:
        return _chamar_llm_openrouter(sistema, instrucao)

    raise OpenRouterFaithBloomError(
        "Nenhum provedor de texto está configurado. Defina GEMINI_API_KEY "
        "(gratuito/econômico) ou OPENROUTER_API_KEY (pago) nos Secrets do ambiente."
    )


def _chamar_llm_openrouter(sistema: str, instrucao: str) -> dict | list:
    conteudo_assinatura = sistema + "\n" + instrucao
    req_id,assinatura,estimativa,inicio=iniciar_requisicao("texto", MODELO_TEXTO, conteudo_assinatura)
    try:
        payload={
            "model":MODELO_TEXTO,
            "messages":[
                {"role":"system","content":sistema+"\n\nResponda APENAS em JSON válido, sem markdown."},
                {"role":"user","content":instrucao},
            ],
        }
        resp=_post_com_retry(f"{OPENROUTER_BASE_URL}/chat/completions",payload,120)
        dados=_json_resposta(resp)
        texto=dados["choices"][0]["message"]["content"]
        texto_limpo=texto.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        resultado=json.loads(texto_limpo)
        finalizar_requisicao(req_id,assinatura,"texto",MODELO_TEXTO,estimativa,inicio,"sucesso",extrair_custo_reportado(dados))
        return resultado
    except Exception as exc:
        finalizar_requisicao(req_id,assinatura,"texto",MODELO_TEXTO,estimativa,inicio,"erro",detalhe=sanitizar_texto(str(exc)))
        raise


def gerar_imagem(prompt: str, imagem_base: str | None = None, imagens_referencia: list[str] | None = None) -> str:
    """Gera imagem aceitando cena-base + múltiplas referências visuais oficiais.

    `imagem_base` continua compatível com chamadas antigas. `imagens_referencia` é
    usado pelo Restoration Studio para anexar Character Masters sem substituir a
    cena original como referência principal.

    Nota: continua exclusivamente na OpenRouter (ver cabeçalho do módulo).
    """
    refs=[]
    if imagem_base:
        refs.append(imagem_base)
    for r in imagens_referencia or []:
        if r and r not in refs:
            refs.append(r)
    ref_sig=""
    for ref in refs:
        if os.path.exists(ref):
            st=os.stat(ref)
            ref_sig+=f"|ref:{os.path.basename(ref)}:{st.st_size}:{int(st.st_mtime)}"
    req_id,assinatura,estimativa,inicio=iniciar_requisicao("imagem",MODELO_IMAGEM,prompt+ref_sig)
    try:
        content=[{"type":"text","text":prompt}]
        import mimetypes
        for ref in refs:
            if not ref or not os.path.exists(ref):
                continue
            with open(ref,"rb") as f:
                b64_ref=base64.b64encode(f.read()).decode()
            mime=mimetypes.guess_type(ref)[0] or "image/png"
            content.append({"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64_ref}"}})
        payload={"model":MODELO_IMAGEM,"messages":[{"role":"user","content":content}],"modalities":["image","text"]}
        resp=_post_com_retry(f"{OPENROUTER_BASE_URL}/chat/completions",payload,180)
        dados=_json_resposta(resp)
        imagens=dados.get("choices",[{}])[0].get("message",{}).get("images",[])
        if not imagens:
            raise OpenRouterFaithBloomError("O modelo não retornou imagem nesta chamada. Tente novamente ou revise o modelo selecionado.")
        url=imagens[0].get("image_url",{}).get("url","")
        if "," not in url:
            raise OpenRouterFaithBloomError("Formato de imagem inesperado na resposta do provedor.")
        b64_imagem=url.split(",",1)[1]
        caminho=os.path.join(PASTA_IMAGENS,f"{uuid.uuid4().hex}.png")
        with open(caminho,"wb") as f:
            f.write(base64.b64decode(b64_imagem))
        finalizar_requisicao(req_id,assinatura,"imagem",MODELO_IMAGEM,estimativa,inicio,"sucesso",extrair_custo_reportado(dados))
        return caminho
    except Exception as exc:
        finalizar_requisicao(req_id,assinatura,"imagem",MODELO_IMAGEM,estimativa,inicio,"erro",detalhe=sanitizar_texto(str(exc)))
        raise


def gerar_audio(texto_com_marcacoes: str, nome_arquivo: str, voice: str | None = None) -> str:
    """Gera MP3 via TTS mantendo compatibilidade com o pipeline legado.

    Marcadores editoriais do FaithBloom são convertidos para pontuação natural
    antes de enviar ao TTS, evitando que o sintetizador leia ``[pausa curta]``
    em voz alta. O Voice Profile pode fornecer um ``provider_voice_id``; quando
    vazio, usa-se a voz padrão configurada no ambiente.

    Nota: continua exclusivamente na OpenRouter (ver cabeçalho do módulo).
    """
    texto_tts=converter_marcacoes_para_texto_natural(texto_com_marcacoes)
    palavras=max(1,len(texto_tts.split()))
    mins=max(0.1,palavras/145.0)
    estimativa=POLITICA.estimativa_audio_min_usd*mins
    voice_id=(voice or VOZ_PADRAO or "").strip()
    assinatura_conteudo=texto_tts+(f"|voice:{voice_id}" if voice_id else "")
    req_id,assinatura,estimativa,inicio=iniciar_requisicao("audio",MODELO_VOZ,assinatura_conteudo,estimativa)
    try:
        payload={"model":MODELO_VOZ,"input":texto_tts,"response_format":"mp3"}
        if voice_id:
            payload["voice"]=voice_id
        resp=_post_com_retry(f"{OPENROUTER_BASE_URL}/audio/speech",payload,120)
        caminho=os.path.join(PASTA_AUDIO,f"{nome_arquivo}.mp3")
        with open(caminho,"wb") as f:
            f.write(resp.content)
        finalizar_requisicao(req_id,assinatura,"audio",MODELO_VOZ,estimativa,inicio,"sucesso")
        return caminho
    except Exception as exc:
        finalizar_requisicao(req_id,assinatura,"audio",MODELO_VOZ,estimativa,inicio,"erro",detalhe=sanitizar_texto(str(exc)))
        raise


def converter_marcacoes_para_texto_natural(texto_com_marcacoes: str) -> str:
    substituicoes={"[pausa curta]":"...","[pausa longa]":"...\n\n","[voz suave]":"","[voz animada]":"","[voz sussurrada]":""}
    texto=texto_com_marcacoes or ""
    for marcado,natural in substituicoes.items():
        texto=texto.replace(marcado,natural)
    import re
    texto=re.sub(r"\[ênfase:\s*(.*?)\]",r"\1",texto,flags=re.I)
    texto=re.sub(r"\[(?:emoção|emocao|ritmo|speaker|voz):[^\]]+\]","",texto,flags=re.I)
    texto=re.sub(r"\[pausa:\s*(\d+)\s*ms\]",lambda m:", " if int(m.group(1))<500 else "... ",texto,flags=re.I)
    return re.sub(r"[ \t]+"," ",texto).strip()


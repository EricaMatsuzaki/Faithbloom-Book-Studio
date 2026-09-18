"""Cliente OpenRouter do FaithBloom com guardrails de custo/duplicidade (Fase 13).

Refinamento (17/09/2026): as modalidades de TEXTO e VOZ agora tentam primeiro
o Gemini (Google AI Studio, gratuito/econômico — ver gemini_client.py) e só
caem para a OpenRouter se o Gemini não estiver configurado ou falhar. Isso
mantém o SaaS funcional mesmo sem crédito pago na OpenRouter. Imagem
permanece exclusivamente na OpenRouter por enquanto: a rota Gemini para essa
modalidade ainda não foi validada com o mesmo nível de QA visual.

A interface pública deste módulo (chamar_llm, gerar_imagem, gerar_audio) não
muda para quem já importa daqui — nenhum agente precisa alterar seu import.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
import uuid
import wave
from typing import Any

import requests

import gemini_client
from controle_geracao import (
    POLITICA,
    extrair_custo_reportado,
    finalizar_requisicao,
    liberar_requisicao,
    atualizar_etapa,
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
# um único provedor de texto/voz (útil para diagnóstico/comparação).
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
    tentativas = 1 if url.rstrip("/").endswith("/images") else max(1, POLITICA.tentativas_http)
    for tentativa in range(1, tentativas + 1):
        try:
            resp=requests.post(url, headers=_headers(), json=payload, timeout=timeout)
            if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                if tentativa < tentativas:
                    time.sleep(POLITICA.backoff_inicial_seg * (2 ** (tentativa-1)))
                    continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            ultimo=exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                break
            if tentativa < tentativas:
                time.sleep(POLITICA.backoff_inicial_seg * (2 ** (tentativa-1)))
    codigo=getattr(getattr(ultimo,"response",None),"status_code",None)
    sufixo=f" (HTTP {codigo})" if codigo else ""
    orientacao = {
        400: "A OpenRouter rejeitou os parâmetros da geração. Revise modelo, referências e resolução.",
        401: "A OpenRouter não aceitou a autenticação. Verifique a chave nas configurações do aplicativo.",
        402: "A OpenRouter informou saldo ou limite de créditos insuficiente.",
        403: "A OpenRouter não autorizou esta solicitação. Verifique as permissões do modelo.",
        404: "O modelo ou serviço solicitado não está disponível na OpenRouter.",
        422: "A OpenRouter não aceitou o formato ou as opções da imagem.",
        502: "O provedor de imagem falhou ou excedeu seu prazo. Esta tentativa terminou com erro; nenhuma nova tentativa de imagem foi enviada automaticamente.",
        429: "A OpenRouter atingiu um limite temporário. Aguarde antes de tentar novamente.",
    }.get(codigo, "Não foi possível concluir a geração na OpenRouter. Tente novamente mais tarde.")
    raise OpenRouterFaithBloomError(orientacao + sufixo) from None


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
    if gemini_client.gemini_disponivel():
        return "gemini"
    if OPENROUTER_API_KEY:
        return "openrouter"
    return "indisponível"


def chamar_llm(sistema: str, instrucao: str) -> dict | list:
    """Ponto único chamado por todos os agentes. Decide o provedor de texto
    (Gemini gratuito/econômico primeiro, OpenRouter como fallback pago) sem
    exigir nenhuma mudança nos agentes que já importam esta função.

    Quando o Gemini não está disponível, chama _chamar_llm_openrouter()
    incondicionalmente — exatamente como o código original sempre fez — em vez
    de checar OPENROUTER_API_KEY antes. Isso preserva o comportamento e as
    mensagens de erro de sempre, inclusive para testes que simulam falhas de
    rede ou interrupção do Streamlit.
    """
    if PROVEDOR_TEXTO != "openrouter" and gemini_client.gemini_disponivel():
        try:
            return gemini_client.chamar_llm_gemini(sistema, instrucao)
        except Exception as exc_gemini:
            if PROVEDOR_TEXTO == "gemini":
                raise
            try:
                return _chamar_llm_openrouter(sistema, instrucao)
            except Exception as exc_openrouter:
                raise OpenRouterFaithBloomError(
                    "Nem o Gemini nem a OpenRouter responderam. "
                    f"Gemini: {exc_gemini}. OpenRouter: {exc_openrouter}."
                ) from exc_openrouter

    if PROVEDOR_TEXTO == "gemini":
        raise OpenRouterFaithBloomError(
            "FAITHBLOOM_PROVEDOR_TEXTO=gemini foi definido, mas o Gemini não está "
            "configurado ou disponível. Defina GEMINI_API_KEY (ou GOOGLE_API_KEY)."
        )

    return _chamar_llm_openrouter(sistema, instrucao)


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
    except BaseException:
        liberar_requisicao(assinatura)
        raise


def gerar_imagem(prompt: str, imagem_base: str | None = None, imagens_referencia: list[str] | None = None, *, resolution: str | None = None, provider: str | None = None, aspect_ratio: str | None = None, output_format: str | None = "png") -> str:
    if resolution not in {None, "1K", "2K", "4K"}:
        raise ValueError("Resolução inválida. Escolha 1K, 2K ou 4K.")
    if provider not in {None, "google-vertex", "google-ai-studio"}:
        raise ValueError("Fornecedor de imagem inválido.")
    if aspect_ratio not in {None, "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"}:
        raise ValueError("Proporção de imagem inválida.")
    if output_format not in {None, "png"}:
        raise ValueError("Formato de saída inválido.")
    if not prompt.strip():
        raise ValueError("Escreva o pedido de edição antes de gerar.")
    refs=[]
    if imagem_base:
        refs.append(imagem_base)
    for r in imagens_referencia or []:
        if r and r not in refs:
            refs.append(r)
    ref_sig=f"|resolution:{resolution or 'default'}|provider:{provider}|aspect_ratio:{aspect_ratio}|output_format:{output_format}"
    for ref in refs:
        if not os.path.isfile(ref):
            raise OpenRouterFaithBloomError("Uma imagem de referência não está disponível. Selecione-a novamente antes de gerar.")
        if os.path.exists(ref):
            st=os.stat(ref)
            ref_sig+=f"|ref:{os.path.basename(ref)}:{st.st_size}:{int(st.st_mtime)}"
    req_id,assinatura,estimativa,inicio=iniciar_requisicao("imagem",MODELO_IMAGEM,prompt+ref_sig)
    try:
        imagens_entrada=[]
        for ref in refs:
            if not ref or not os.path.exists(ref):
                continue
            with open(ref,"rb") as f:
                b64_ref=base64.b64encode(f.read()).decode()
            mime=mimetypes.guess_type(ref)[0] or "image/png"
            imagens_entrada.append(f"data:{mime};base64,{b64_ref}")
        payload={"model":MODELO_IMAGEM,"prompt":prompt}
        if output_format:
            payload["output_format"] = output_format
        if provider:
            payload["provider"] = {"only": [provider]}
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if resolution:
            payload["resolution"] = resolution
        if imagens_entrada:
            payload["input_references"] = [{"type": "image_url", "image_url": {"url": url}} for url in imagens_entrada]
        atualizar_etapa(assinatura, "aguardando OpenRouter")
        resp=_post_com_retry(f"{OPENROUTER_BASE_URL}/images",payload,180)
        atualizar_etapa(assinatura, "salvando resultado")
        dados=_json_resposta(resp)
        imagens=dados.get("data") or []
        b64_imagem=imagens[0].get("b64_json","") if imagens and isinstance(imagens[0],dict) else ""
        if not b64_imagem:
            raise OpenRouterFaithBloomError("O provedor não retornou uma imagem nesta chamada. Tente novamente ou revise o modelo selecionado.")
        media_type = imagens[0].get("media_type", "image/png")
        extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(media_type)
        if not extension:
            raise OpenRouterFaithBloomError("O provedor retornou um formato de imagem não suportado.")
        caminho=os.path.join(PASTA_IMAGENS,f"{uuid.uuid4().hex}.{extension}")
        with open(caminho,"wb") as f:
            f.write(base64.b64decode(b64_imagem,validate=True))
        finalizar_requisicao(req_id,assinatura,"imagem",MODELO_IMAGEM,estimativa,inicio,"sucesso",extrair_custo_reportado(dados))
        return caminho
    except Exception as exc:
        finalizar_requisicao(req_id,assinatura,"imagem",MODELO_IMAGEM,estimativa,inicio,"erro",detalhe=sanitizar_texto(str(exc)))
        raise
    except BaseException:
        liberar_requisicao(assinatura)
        raise


def _salvar_pcm_como_wav(nome_arquivo: str, pcm_bytes: bytes, sample_rate: int = 24000) -> str:
    caminho=os.path.join(PASTA_AUDIO,f"{nome_arquivo}.wav")
    with wave.open(caminho, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return caminho


def gerar_audio(
    texto_com_marcacoes: str,
    nome_arquivo: str,
    voice: str | None = None,
    *,
    model: str | None = None,
    instructions: str | None = None,
    response_format: str = "mp3",
) -> str:
    """Gera voz para o Jarvis/Audiobook. Decide o provedor de voz da mesma
    forma que chamar_llm() decide o provedor de texto: Gemini gratuito/
    econômico primeiro, OpenRouter como fallback pago — sem exigir nenhuma
    mudança em quem já chama esta função.

    Só tenta o Gemini quando ``model`` não foi passado explicitamente: um
    ``model`` específico (ex.: um modelo OpenRouter escolhido a dedo pelo
    Audiobook Studio) significa que quem chamou já decidiu o provedor, e essa
    escolha é respeitada sem substituição silenciosa.
    """
    texto_tts=converter_marcacoes_para_texto_natural(texto_com_marcacoes)

    if model is None and PROVEDOR_TEXTO != "openrouter" and gemini_client.gemini_disponivel():
        try:
            pcm_bytes, taxa = gemini_client.gerar_audio_gemini(texto_tts, voice)
            return _salvar_pcm_como_wav(nome_arquivo, pcm_bytes, taxa)
        except Exception as exc_gemini:
            if PROVEDOR_TEXTO == "gemini":
                raise
            try:
                return _gerar_audio_openrouter(texto_tts, nome_arquivo, voice, model=model, instructions=instructions, response_format=response_format)
            except Exception as exc_openrouter:
                raise OpenRouterFaithBloomError(
                    "Nem o Gemini nem a OpenRouter geraram a voz. "
                    f"Gemini: {exc_gemini}. OpenRouter: {exc_openrouter}."
                ) from exc_openrouter

    if PROVEDOR_TEXTO == "gemini" and model is None:
        raise OpenRouterFaithBloomError(
            "FAITHBLOOM_PROVEDOR_TEXTO=gemini foi definido, mas o Gemini não está "
            "configurado ou disponível. Defina GEMINI_API_KEY (ou GOOGLE_API_KEY)."
        )

    return _gerar_audio_openrouter(texto_tts, nome_arquivo, voice, model=model, instructions=instructions, response_format=response_format)


def _gerar_audio_openrouter(
    texto_tts: str,
    nome_arquivo: str,
    voice: str | None = None,
    *,
    model: str | None = None,
    instructions: str | None = None,
    response_format: str = "mp3",
) -> str:
    """Gera voz usando o endpoint TTS já compartilhado pelo FaithBloom.

    ``model`` e ``instructions`` permitem especializar a identidade sonora do
    Jarvis sem criar um segundo cliente de áudio nem alterar o Audiobook Studio.

    Para Gemini TTS em PCM, convertemos o fluxo cru 24 kHz/16-bit/mono para WAV.
    Isso evita que Safari/Streamlit tentem reproduzir bytes PCM como se fossem MP3.
    """
    palavras=max(1,len(texto_tts.split()))
    mins=max(0.1,palavras/145.0)
    estimativa=POLITICA.estimativa_audio_min_usd*mins
    selected_model=(model or MODELO_VOZ).strip()
    voice_id=(voice or VOZ_PADRAO or "").strip()
    fmt=(response_format or "mp3").strip().lower()
    if fmt not in {"mp3", "pcm"}:
        raise ValueError("Formato de voz inválido. Use mp3 ou pcm.")
    assinatura_conteudo=texto_tts+f"|model:{selected_model}|format:{fmt}"+(f"|voice:{voice_id}" if voice_id else "")
    req_id,assinatura,estimativa,inicio=iniciar_requisicao("audio",selected_model,assinatura_conteudo,estimativa)
    try:
        payload={"model":selected_model,"input":texto_tts,"response_format":fmt}
        if voice_id:
            payload["voice"]=voice_id
        if instructions and instructions.strip():
            payload["instructions"]=instructions.strip()
        resp=_post_com_retry(f"{OPENROUTER_BASE_URL}/audio/speech",payload,120)
        if not resp.content:
            raise OpenRouterFaithBloomError("A OpenRouter retornou áudio vazio.")

        if fmt == "pcm" and selected_model.startswith("google/gemini-"):
            caminho=_salvar_pcm_como_wav(nome_arquivo, resp.content, 24000)
        else:
            extension="mp3" if fmt == "mp3" else "pcm"
            caminho=os.path.join(PASTA_AUDIO,f"{nome_arquivo}.{extension}")
            with open(caminho,"wb") as f:
                f.write(resp.content)

        finalizar_requisicao(req_id,assinatura,"audio",selected_model,estimativa,inicio,"sucesso")
        return caminho
    except Exception as exc:
        finalizar_requisicao(req_id,assinatura,"audio",selected_model,estimativa,inicio,"erro",detalhe=sanitizar_texto(str(exc)))
        raise
    except BaseException:
        liberar_requisicao(assinatura)
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

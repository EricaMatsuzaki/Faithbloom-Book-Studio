"""Natural conversational replies for the FaithBloom Jarvis.

This is a thin dialogue layer over the existing OpenRouter transport. It does not
replace the editorial orchestrator, tools, approvals, STT or TTS, and it never
claims an action was completed unless the caller provides an explicit result.

The canonical Jarvis is latency-sensitive. It therefore uses a dedicated fast
chat model instead of the heavier editorial model, with a short context window and
small output budget. The editorial agents continue using their stronger models.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from controle_geracao import (
    extrair_custo_reportado,
    finalizar_requisicao,
    iniciar_requisicao,
    liberar_requisicao,
    sanitizar_texto,
)
from openrouter_client import OPENROUTER_BASE_URL, _json_resposta, _post_com_retry

DEFAULT_JARVIS_DIALOGUE_MODEL = "google/gemini-2.5-flash-lite:nitro"
JARVIS_DIALOGUE_MODEL = (
    os.environ.get("OPENROUTER_MODELO_JARVIS", DEFAULT_JARVIS_DIALOGUE_MODEL).strip()
    or DEFAULT_JARVIS_DIALOGUE_MODEL
)

SYSTEM_PROMPT = """Você é o Jarvis do FaithBloom Book Studio, um assistente central de voz.
Converse de forma natural, curta, clara e útil em português do Brasil.
Entenda a intenção real da pessoa em vez de repetir uma resposta padrão.
Use o contexto recente somente quando ele realmente ajudar.
Nunca diga que executou, publicou, apagou, alterou Master, gastou créditos ou concluiu uma tarefa se isso não estiver explicitamente confirmado no contexto de execução.
Quando houver uma rota editorial preparada, explique em linguagem humana o que você entendeu e qual é o próximo passo, sem recitar nomes internos de módulos desnecessariamente.
Ações críticas continuam exigindo aprovação humana.
Se algo estiver fora das ferramentas disponíveis, seja transparente e diga o que consegue fazer a seguir.
Responda preferencialmente em 1 ou 2 frases, salvo se a pessoa pedir detalhes.
Sua personalidade é adulta, elegante, calma, eficiente e acolhedora; nunca infantilizada nem caricata."""


def _history_messages(history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Keep only the minimum recent context needed for a voice turn."""
    messages: list[dict[str, str]] = []
    for item in (history or [])[-4:]:
        role = item.get("role")
        text = str(item.get("text") or "").strip()
        if role not in {"user", "assistant"} or not text:
            continue
        messages.append({"role": role, "content": text[:900]})
    return messages


def build_natural_reply(
    user_text: str,
    *,
    history: list[dict[str, Any]] | None = None,
    route_result: dict[str, Any] | None = None,
    project_progress: dict[str, Any] | None = None,
) -> str:
    """Generate one concise low-latency reply while preserving guardrails."""
    text = (user_text or "").strip()
    if not text:
        raise ValueError("A mensagem para o Jarvis está vazia.")

    context: dict[str, Any] = {}
    if route_result:
        plan = route_result.get("route_plan") or {}
        context["rota_editorial"] = {
            "tipo": route_result.get("project_type"),
            "origem": route_result.get("origin"),
            "publico": route_result.get("audience"),
            "linha": route_result.get("editorial_line"),
            "proximo_passo": route_result.get("next_action"),
            "pagina_sugerida": route_result.get("next_page"),
            "aprovacao_autora": bool(route_result.get("requires_author_approval", True)),
            "rotulo_projeto": plan.get("project_label"),
            "rotulo_publico": plan.get("audience_label"),
        }
    if project_progress:
        context["progresso_projeto"] = {
            "titulo": project_progress.get("title"),
            "proximo_passo": project_progress.get("next_step"),
            "mensagem": project_progress.get("message"),
        }

    signature = json.dumps({"text": text, "context": context}, ensure_ascii=False, sort_keys=True)
    req_id, request_sig, estimate, started = iniciar_requisicao(
        "texto", JARVIS_DIALOGUE_MODEL, "jarvis-dialogue|" + signature
    )
    t0 = time.perf_counter()
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(_history_messages(history))
        if context:
            messages.append(
                {
                    "role": "system",
                    "content": "Contexto operacional confirmado pelo FaithBloom: "
                    + json.dumps(context, ensure_ascii=False),
                }
            )
        messages.append({"role": "user", "content": text})
        payload = {
            "model": JARVIS_DIALOGUE_MODEL,
            "messages": messages,
            "temperature": 0.25,
            "max_tokens": 120,
        }
        response = _post_com_retry(f"{OPENROUTER_BASE_URL}/chat/completions", payload, 30)
        data = _json_resposta(response)
        answer = str(data["choices"][0]["message"]["content"] or "").strip()
        if not answer:
            raise RuntimeError("O modelo não retornou uma resposta para o Jarvis.")
        finalizar_requisicao(
            req_id,
            request_sig,
            "texto",
            JARVIS_DIALOGUE_MODEL,
            estimate,
            started,
            "sucesso",
            extrair_custo_reportado(data),
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(
            f"[FaithBloom Jarvis Latency] dialogue_ms={elapsed_ms} model={JARVIS_DIALOGUE_MODEL}",
            flush=True,
        )
        return answer
    except Exception as exc:
        finalizar_requisicao(
            req_id,
            request_sig,
            "texto",
            JARVIS_DIALOGUE_MODEL,
            estimate,
            started,
            "erro",
            detalhe=sanitizar_texto(str(exc)),
        )
        raise
    except BaseException:
        liberar_requisicao(request_sig)
        raise

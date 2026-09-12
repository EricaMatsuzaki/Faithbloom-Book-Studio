"""Jarvis Character Auto-Setup.

Orquestra recursos existentes do Character Universe, Asset Library e Visual Master.
Nao cria um segundo sistema de personagens: apenas automatiza o fluxo
Character Master -> Reference Pack -> Color Master -> DNA visual, com uma unica
confirmacao humana antes de persistir/promover Master.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
from copy import deepcopy
from typing import Any

from character_universe import (
    USOS_PADRAO,
    buscar_personagens_por_nome,
    carregar_personagem_oficial,
    criar_personagem_oficial,
    listar_personagens_oficiais,
    mover_personagem_para_colecao,
    normalizar_dna,
    atualizar_personagem_oficial,
)
from controle_geracao import (
    atualizar_etapa,
    extrair_custo_reportado,
    finalizar_requisicao,
    iniciar_requisicao,
    liberar_requisicao,
    sanitizar_texto,
)
from faithbloom_cost_mode import model_for
from openrouter_client import (
    OPENROUTER_BASE_URL,
    _headers,
    _json_resposta,
    _post_com_retry,
)
from visual_master_manager import promote_reference_color_master, register_upload

MAX_ANALYSIS_IMAGES = max(1, int(os.environ.get("JARVIS_CHARACTER_MAX_ANALYSIS_IMAGES", "8")))

VISUAL_FIELDS = (
    "especie",
    "olhos",
    "paleta_base",
    "rosto",
    "proporcoes",
    "marcas_permanentes",
    "cabelo_pelagem_penas",
    "expressao_base",
    "estilo_visual",
    "tracos_nao_mudar",
)


def current_vision_model() -> str:
    """Modelo multimodal definido pelo modo Econômico/Balanceado/Premium."""
    return model_for("character_vision")


def infer_character_context(request: str, known_collections: list[str] | None = None) -> dict[str, str]:
    """Extrai nome/colecao sem IA quando a frase ja os informa explicitamente."""
    text = " ".join(str(request or "").strip().split())
    collections = sorted(
        {str(c).strip() for c in (known_collections or []) if str(c).strip()},
        key=len,
        reverse=True,
    )
    collection = ""
    folded = text.casefold()
    for candidate in collections:
        if candidate.casefold() in folded:
            collection = candidate
            break

    name = ""
    patterns = (
        r"(?:esse|esta|este|essa)\s+(?:e|é)\s+(?:o|a)?\s*personagem\s+[\"“']?([^\"”']+?)[\"”']?\s+(?:da|do)\s+cole[cç][aã]o\b",
        r"personagem\s+[\"“']?([^\"”']+?)[\"”']?\s+(?:da|do)\s+cole[cç][aã]o\b",
        r"(?:nome|personagem)\s*[:=-]\s*[\"“']?([^,;\n\"”']+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            name = match.group(1).strip(" .,:;-\"“”'")
            break
    if not name:
        quoted = re.search(r"personagem\s+[\"“']([^\"”']+)[\"”']", text, flags=re.I)
        if quoted:
            name = quoted.group(1).strip()

    if not collection:
        match = re.search(r"cole[cç][aã]o\s*[:=-]?\s*([^.;\n]+)", text, flags=re.I)
        if match:
            candidate = match.group(1).strip(" .,:;-\"“”'")
            candidate = re.split(r"\s+(?:e\s+)?(?:crie|criar|use|salve|melhore|preencha|escolha)\b", candidate, maxsplit=1, flags=re.I)[0].strip()
            collection = candidate

    return {"character_name": name, "target_collection": collection}


def _clean_analysis(raw: dict[str, Any], image_count: int) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    fields = raw.get("campos_bloqueados") if isinstance(raw.get("campos_bloqueados"), dict) else {}
    clean_fields = {
        key: str(fields.get(key) or "").strip()
        for key in VISUAL_FIELDS
        if str(fields.get(key) or "").strip()
    }
    try:
        index = int(raw.get("melhor_referencia_indice", 0))
    except (TypeError, ValueError):
        index = 0
    if image_count:
        index = max(0, min(index, image_count - 1))
    else:
        index = 0
    allowed = [
        str(v).strip() for v in (raw.get("variaveis_permitidas") or [])
        if str(v).strip()
    ]
    return {
        "descricao_master": str(raw.get("descricao_master") or "").strip(),
        "campos_bloqueados": clean_fields,
        "caracteristicas_bloqueadas": str(raw.get("caracteristicas_bloqueadas") or raw.get("descricao_master") or "").strip(),
        "visual_prompt_master": str(raw.get("visual_prompt_master") or "").strip(),
        "variaveis_permitidas": allowed,
        "melhor_referencia_indice": index,
        "melhor_referencia_motivo": str(raw.get("melhor_referencia_motivo") or "").strip(),
        "resumo_visual": str(raw.get("resumo_visual") or raw.get("descricao_master") or "").strip(),
    }


def analyze_character_images(
    character_name: str,
    collection: str,
    files: list[dict[str, Any]],
    request: str = "",
) -> dict[str, Any]:
    """Analisa apenas atributos visiveis e retorna DNA estruturado + melhor referencia."""
    images = [f for f in files if str(f.get("kind") or "") == "image" and f.get("data")][:MAX_ANALYSIS_IMAGES]
    if not images:
        raise ValueError("Envie ao menos uma imagem do personagem para preencher o DNA visual automaticamente.")

    vision_model = current_vision_model()
    system = (
        "Voce e o analista visual do Character Universe do FaithBloom. "
        "Analise SOMENTE caracteristicas visiveis das imagens. Nao invente idade exata, etnia, diagnosticos, historia pessoal ou atributos nao observaveis. "
        "Seu objetivo e produzir um DNA visual reutilizavel e conservador para manter consistencia entre ilustracoes infantis. "
        "Quando imagens divergirem por roupa, pose, expressao ou acessorio temporario, trate isso como variacao e preserve como permanente apenas o que for consistente. "
        "Escolha a melhor referencia pela clareza do rosto/corpo, nitidez, iluminacao neutra e representatividade da identidade. "
        "Responda APENAS JSON valido, sem markdown."
    )
    instruction = {
        "personagem": character_name,
        "colecao": collection,
        "pedido_da_autora": request,
        "saida_obrigatoria": {
            "descricao_master": "descricao curta da identidade visual",
            "campos_bloqueados": {key: "texto somente se claramente observavel" for key in VISUAL_FIELDS},
            "caracteristicas_bloqueadas": "sintese dos tracos que devem permanecer",
            "visual_prompt_master": "prompt visual neutro, sem cenario, baseado apenas nas referencias",
            "variaveis_permitidas": ["pose", "acao", "expressao", "emocao", "figurino", "acessorios_temporarios", "cenario", "estacao", "festividade"],
            "melhor_referencia_indice": 0,
            "melhor_referencia_motivo": "motivo objetivo",
            "resumo_visual": "resumo em linguagem simples para revisao humana",
        },
        "regras": [
            "indices das imagens comecam em 0",
            "nao transformar roupa temporaria em marca permanente",
            "nao copiar tracos de outro personagem citado apenas como referencia de qualidade",
            "se algo nao for visivel, deixe vazio",
        ],
    }

    content: list[dict[str, Any]] = [{"type": "text", "text": json.dumps(instruction, ensure_ascii=False)}]
    signature_parts = []
    for file in images:
        raw = bytes(file.get("data") or b"")
        mime = str(file.get("mime_type") or mimetypes.guess_type(str(file.get("name") or "imagem.png"))[0] or "image/png")
        b64 = base64.b64encode(raw).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        signature_parts.append(str(file.get("sha256") or f"{file.get('name')}:{len(raw)}"))

    signature = f"{character_name}|{collection}|" + "|".join(signature_parts)
    req_id, req_signature, estimate, started = iniciar_requisicao("texto", vision_model, signature)
    try:
        payload = {
            "model": vision_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
        }
        atualizar_etapa(req_signature, "analisando referencias do personagem")
        response = _post_com_retry(f"{OPENROUTER_BASE_URL}/chat/completions", payload, 120)
        data = _json_resposta(response)
        message_content = data["choices"][0]["message"]["content"]
        if isinstance(message_content, list):
            message_content = "".join(
                str(part.get("text") or "") if isinstance(part, dict) else str(part)
                for part in message_content
            )
        text = str(message_content or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text)
        result = _clean_analysis(parsed, len(images))
        finalizar_requisicao(req_id, req_signature, "texto", vision_model, estimate, started, "sucesso", extrair_custo_reportado(data))
        return result
    except Exception as exc:
        finalizar_requisicao(req_id, req_signature, "texto", vision_model, estimate, started, "erro", detalhe=sanitizar_texto(str(exc)))
        raise
    except BaseException:
        liberar_requisicao(req_signature)
        raise


def merge_visual_dna(existing: dict | str | None, analysis: dict[str, Any]) -> dict:
    """Preenche lacunas sem destruir DNA ja bloqueado/aprovado."""
    current = normalizar_dna(existing)
    fields = dict(current.get("campos_bloqueados") or {})
    for key, value in (analysis.get("campos_bloqueados") or {}).items():
        if value and not str(fields.get(key) or "").strip():
            fields[key] = value
    current["campos_bloqueados"] = fields
    if not str(current.get("descricao_master") or "").strip():
        current["descricao_master"] = analysis.get("descricao_master", "")
    if not str(current.get("caracteristicas_bloqueadas") or "").strip():
        current["caracteristicas_bloqueadas"] = analysis.get("caracteristicas_bloqueadas", "")
    if not str(current.get("visual_prompt_master") or "").strip():
        current["visual_prompt_master"] = analysis.get("visual_prompt_master", "")
    if analysis.get("variaveis_permitidas") and not current.get("variaveis_permitidas"):
        current["variaveis_permitidas"] = list(analysis["variaveis_permitidas"])
    current["auto_visual_analysis"] = {
        "source": "jarvis_character_auto_setup",
        "analyzed_at": int(time.time()),
        "model": current_vision_model(),
    }
    return normalizar_dna(current)


def prepare_auto_setup(
    package: dict[str, Any],
    *,
    character_name: str,
    target_collection: str,
) -> dict[str, Any]:
    name = str(character_name or "").strip()
    collection = str(target_collection or "").strip()
    files = [f for f in package.get("files") or [] if str(f.get("kind") or "") == "image" and f.get("data")]
    if not name:
        raise ValueError("Nao consegui identificar o nome do personagem.")
    if not collection:
        raise ValueError("Nao consegui identificar a colecao do personagem.")
    if not files:
        raise ValueError("Envie ao menos uma imagem do personagem.")

    matches_target = [
        item for item in listar_personagens_oficiais(collection, incluir_arquivados=False)
        if str(item.get("nome") or "").strip().casefold() == name.casefold()
    ]
    same_name = buscar_personagens_por_nome(name, incluir_arquivados=False)
    elsewhere = [item for item in same_name if str(item.get("colecao") or "") != collection]
    if len(matches_target) > 1:
        raise ValueError(f"Ha mais de um Character Master ativo chamado {name} em {collection}. Resolva a duplicidade antes de continuar.")
    if not matches_target and len(elsewhere) > 1:
        locations = ", ".join(sorted({str(x.get("colecao") or "") for x in elsewhere}))
        raise ValueError(f"Ha mais de um personagem chamado {name} em outras colecoes ({locations}). Resolva a duplicidade antes de continuar.")

    existing = carregar_personagem_oficial(str(matches_target[0].get("id"))) if matches_target else None
    move_from = ""
    character_id = str((existing or {}).get("id") or "")
    if not existing and len(elsewhere) == 1:
        character_id = str(elsewhere[0].get("id") or "")
        existing = carregar_personagem_oficial(character_id)
        move_from = str((existing or {}).get("colecao") or "")

    analysis = analyze_character_images(name, collection, files, str(package.get("request") or ""))
    merged_dna = merge_visual_dna((existing or {}).get("dna"), analysis)
    master_exists = bool((existing or {}).get("color_master"))
    best_index = int(analysis.get("melhor_referencia_indice", 0))

    return {
        "handoff_id": str(package.get("id") or ""),
        "character_name": name,
        "target_collection": collection,
        "character_id": character_id,
        "operation": "update" if existing else "create",
        "move_from_collection": move_from,
        "files": files,
        "analysis": analysis,
        "dna": merged_dna,
        "best_reference_index": best_index,
        "existing_color_master": master_exists,
        "will_promote_color_master": not master_exists,
        "reference_count": len(files),
        "ready": True,
    }


def execute_auto_setup(plan: dict[str, Any], *, confirmed: bool = False) -> dict[str, Any]:
    """Persiste tudo somente apos a confirmacao humana unica do resumo."""
    if not confirmed:
        raise PermissionError("Aprovacao humana explicita e obrigatoria antes de salvar o Auto-Setup.")
    if not plan.get("ready"):
        raise ValueError("O plano de Auto-Setup ainda nao esta pronto.")

    name = str(plan.get("character_name") or "").strip()
    collection = str(plan.get("target_collection") or "").strip()
    files = list(plan.get("files") or [])
    pid = str(plan.get("character_id") or "")
    moved = False

    if pid:
        character = carregar_personagem_oficial(pid)
        if not character:
            raise KeyError(pid)
        if str(character.get("colecao") or "") != collection:
            character = mover_personagem_para_colecao(
                pid,
                collection,
                confirmacao_explicita=True,
                motivo=f"jarvis_auto_setup:{plan.get('handoff_id') or ''}",
            )
            moved = True
    else:
        character = criar_personagem_oficial(
            collection,
            name,
            plan.get("dna") or {},
            metadata={
                "usos_permitidos": list(USOS_PADRAO),
                "origem": "jarvis_character_auto_setup",
                "handoff_id": str(plan.get("handoff_id") or ""),
                "auto_setup": True,
            },
        )
        pid = str(character.get("id") or "")

    current = carregar_personagem_oficial(pid)
    merged_dna = merge_visual_dna(current.get("dna"), plan.get("analysis") or {})
    metadata = deepcopy(current.get("metadata") or {})
    completed = list(metadata.get("jarvis_auto_setup_handoffs") or [])
    handoff_id = str(plan.get("handoff_id") or "")
    if handoff_id and handoff_id not in completed:
        completed.append(handoff_id)
    metadata["jarvis_auto_setup_handoffs"] = completed
    metadata["jarvis_auto_setup_last"] = {
        "handoff_id": handoff_id,
        "completed_at": int(time.time()),
        "reference_count": len(files),
        "model": current_vision_model(),
    }
    atualizar_personagem_oficial(pid, {"dna": merged_dna, "metadata": metadata})

    uploaded_assets: list[dict[str, Any]] = []
    for file in files:
        asset = register_upload(
            pid,
            str(file.get("name") or "referencia.png"),
            bytes(file.get("data") or b""),
            "outra",
        )
        uploaded_assets.append(asset)

    promoted_asset_id = ""
    current = carregar_personagem_oficial(pid)
    if uploaded_assets and not current.get("color_master"):
        index = max(0, min(int(plan.get("best_reference_index") or 0), len(uploaded_assets) - 1))
        chosen = uploaded_assets[index]
        promoted_asset_id = str(chosen.get("id") or "")
        if promoted_asset_id:
            promote_reference_color_master(pid, promoted_asset_id, confirmed=True)

    final_character = carregar_personagem_oficial(pid)
    return {
        "character_id": pid,
        "character_name": name,
        "target_collection": collection,
        "operation": plan.get("operation"),
        "moved": moved,
        "references_added": len(uploaded_assets),
        "color_master_asset_id": promoted_asset_id,
        "color_master_preserved": bool(final_character.get("color_master")) and not bool(promoted_asset_id),
        "dna_filled": bool((final_character.get("dna") or {}).get("campos_bloqueados")),
        "character": final_character,
    }

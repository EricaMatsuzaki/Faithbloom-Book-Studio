"""FaithBloom — External AI Authoring Bridge (zero créditos OpenRouter).

Este módulo NÃO chama modelo/API. Ele prepara um prompt editorial completo para
uso manual em ChatGPT ou outra IA externa já disponível à autora e importa de
volta uma resposta JSON estruturada para a Biblioteca de Versões Narrativas.

Objetivos:
- oferecer uma opção autoral livre baseada apenas em 💡 ideia ou 🪄 prompt;
- reutilizar a mesma skill `storyteller`, Heart Arc e Originality Guard;
- permitir texto-base da PRÓPRIA autora (ex.: edição atualizada de livro anterior);
- não consumir créditos OpenRouter;
- preservar rastreabilidade: conteúdo volta marcado como `external_ai_manual`.

Importante: isto é uma ponte manual. Não usa a assinatura ChatGPT da autora como
API e não automatiza login, envio ou leitura de conversas externas.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from agent_skills import skill_contract
from age_profiles import instrucao_faixa_etaria, normalizar_faixa_etaria
from agents.estilos_narrativos import ESTILOS_NARRATIVOS, aplicar_estilo_ao_state, normalizar_licao_final
from generation_autosave import persist_generation_snapshot
from originality_guard import creation_originality_contract, evaluate_originality

EXTERNAL_AI_LABEL = "🤖 IA externa — Prompt/Ideia"
EXTERNAL_AI_ORIGIN = "external_ai_manual"
SOURCE_IDEA = "ideia"
SOURCE_PROMPT = "prompt"
VALID_SOURCES = {SOURCE_IDEA, SOURCE_PROMPT}

DERIVADOS_NARRATIVOS = (
    "revisao_aprovada",
    "notas_revisor",
    "mapa_emocional",
    "cenas_imagem",
    "imagens_cenas_enviadas",
    "cenas_imagem_aprovadas",
    "paginas_colorir",
    "traducoes",
    "roteiro_audiobook",
    "audio_gerado",
    "layout_paginas",
    "pacote_pronto",
    "checklist_kdp",
    "preflight_impressao",
    "pdf_miolo_print_ready",
    "sinopse_vendas_curta",
    "sinopse_contracapa",
    "material_lancamento",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _character_brief(state: dict) -> str:
    parts: list[str] = []
    for name, data in (state.get("personagens") or {}).items():
        if isinstance(data, dict):
            role = _text(data.get("papel"))
            fixed = _text(data.get("descricao_fixa"))
            parts.append(f"{name}{f' ({role})' if role else ''}: {fixed}".strip())
        else:
            parts.append(_text(name))
    narrative = _text(state.get("personagens_historia_brief"))
    if narrative:
        parts.append("Briefing narrativo da autora:\n" + narrative)
    return "\n".join(x for x in parts if x) or "Preserve apenas os personagens definidos pela autora na ideia/prompt."


def prompt_originality_preflight(state: dict, author_prompt: str = "") -> dict:
    """Audita somente instruções livres; texto-base autoral não é referência externa."""
    probe = deepcopy(state or {})
    probe["prompt_livre"] = _text(author_prompt)
    return evaluate_originality(probe, references=[])


def build_external_authoring_prompt(
    state: dict,
    *,
    source_mode: str,
    author_prompt: str = "",
    author_owned_reference: str = "",
) -> str:
    """Monta prompt completo sem fazer qualquer chamada de IA."""
    source_mode = source_mode if source_mode in VALID_SOURCES else SOURCE_IDEA
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    idea = _text(state.get("_entrada_tema_livre") or state.get("titulo"))
    custom = _text(author_prompt)
    own_text = _text(author_owned_reference)

    if source_mode == SOURCE_IDEA and not idea:
        raise ValueError("Escreva uma ideia antes de preparar o prompt externo.")
    if source_mode == SOURCE_PROMPT and not custom:
        raise ValueError("Escreva seu prompt/instrução antes de preparar o prompt externo.")

    source_block = (
        f"IDEIA-SEMENTE DA AUTORA:\n{idea}"
        if source_mode == SOURCE_IDEA
        else f"PROMPT / DIREÇÃO LIVRE DA AUTORA:\n{custom}"
    )

    own_block = ""
    if own_text:
        own_block = f"""
\n=== TEXTO-BASE DA PRÓPRIA AUTORA ===
O texto abaixo foi fornecido pela própria autora como obra/rascunho dela. Pode ser
usado para preservar cânone, personagens, fatos e intenção editorial, inclusive
para criar uma versão atualizada. Não trate este material como autorização para
copiar obras de terceiros e não importe elementos externos não fornecidos.

{own_text}
=== FIM DO TEXTO-BASE AUTORAL ===
""".rstrip()

    prompt = f"""
Você é o Roteirista Autoral do FaithBloom Book Studio.
Escreva uma obra infantil ORIGINAL, inédita na execução e editorialmente forte.
Você recebe a mesma skill profissional do Roteirista FaithBloom, mas tem liberdade
para escolher a melhor estratégia narrativa em vez de ficar preso a um dos quatro
estilos formais.

{source_block}

DADOS EDITORIAIS DO PROJETO:
- Coleção: {_text(state.get('colecao')) or '(não informada)'}
- Título atual/provisório: {_text(state.get('titulo')) or '(pode propor um título original)'}
- Faixa etária: {faixa}
- Emoção central: {_text(state.get('emocao_central')) or '(inferir com cuidado a partir da ideia)'}
- Lição cristã: {_text(state.get('aprendizado_cristao')) or '(integrar de modo natural, sem sermão)'}
- Referência bíblica: {_text(state.get('versiculo_referencia')) or '(não inventar texto de versículo)'}

PERSONAGENS:
{_character_brief(state)}

FAIXA ETÁRIA OBRIGATÓRIA:
{instrucao_faixa_etaria(faixa)}
{own_block}

REGRAS DE CRIAÇÃO:
- A história precisa funcionar primeiro como história: divertida, emocionante, visual e memorável.
- FaithBloom Heart Arc™: encantamento → emoção → experiência → descoberta → transformação → fé.
- A criança vive a experiência antes de receber a moral.
- Use gancho, progressão causal, page-turn, ação visual, ritmo de leitura em voz alta, humor/surpresa quando couber e recompensa emocional.
- Fé integrada de modo natural, amoroso e não coercitivo; sem medo religioso, culpa, ameaça ou sermão longo.
- Preserve a idade e não infantilize leitores maiores.
- Se houver texto-base da própria autora, faça uma evolução editorial verdadeira: melhore ritmo, cenas, emoção, humor, clareza, musicalidade e transformação quando necessário, preservando o coração da obra e o cânone indicado.
- Não copie nem imite obra, franquia, autor, ilustrador, bordão, refrão, piada, personagem, cena distintiva, estrutura textual distintiva ou identidade visual de terceiros.
- Referências culturais/literárias só podem informar mecanismos gerais, nunca expressão copiável.
- Não invente o texto completo do versículo; preserve somente a referência fornecida.

RETORNE SOMENTE JSON VÁLIDO, sem markdown e sem comentários fora do JSON:
{{
  "titulo": "título original",
  "sinopse_poetica": "sinopse curta da história",
  "estilo_recomendado": "estilo_1|estilo_2|estilo_3|misto",
  "justificativa_criativa": "por que esta forma de contar funciona para esta história",
  "cenas_texto": [
    {{
      "numero": 1,
      "texto": "texto narrativo da cena",
      "emocao": "emoção principal",
      "emocao_secundaria": "subemoção opcional",
      "intensidade_emocional": 1,
      "transicao_emocional": "como a emoção muda",
      "figurino": "somente se relevante",
      "contexto_visual": "cenário/tempo/clima concretos",
      "personagem_principal": "nome",
      "expressao": "expressão e linguagem corporal"
    }}
  ],
  "licao_final": "moral curta, clara e natural"
}}

Crie cenas suficientes para uma história completa compatível com o projeto e a faixa etária.
""".strip()

    return prompt + "\n\n" + skill_contract("storyteller") + "\n" + creation_originality_contract(state)


def _json_candidate(raw: str) -> dict:
    text = _text(raw)
    if not text:
        raise ValueError("Cole a resposta JSON da IA externa.")

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    first, last = text.find("{"), text.rfind("}")
    if first >= 0 and last > first:
        candidates.append(text[first:last + 1])
    candidates.append(text)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    raise ValueError("A resposta não contém JSON válido. Peça à IA para retornar somente o JSON solicitado.")


def parse_external_story_response(raw: str, state: dict | None = None) -> dict:
    """Valida/normaliza resposta externa sem usar LLM."""
    state = state or {}
    data = _json_candidate(raw)
    scenes_raw = data.get("cenas_texto") or data.get("cenas") or []
    if not isinstance(scenes_raw, list) or not scenes_raw:
        raise ValueError("O JSON precisa conter `cenas_texto` com pelo menos uma cena.")

    scenes: list[dict] = []
    for idx, scene in enumerate(scenes_raw, start=1):
        if not isinstance(scene, dict):
            continue
        text = _text(scene.get("texto"))
        if not text:
            continue
        try:
            intensity = int(scene.get("intensidade_emocional") or 1)
        except Exception:
            intensity = 1
        intensity = min(5, max(1, intensity))
        scenes.append({
            "numero": int(scene.get("numero") or idx),
            "texto": text,
            "emocao": _text(scene.get("emocao") or state.get("emocao_central")),
            "emocao_secundaria": _text(scene.get("emocao_secundaria")),
            "intensidade_emocional": intensity,
            "transicao_emocional": _text(scene.get("transicao_emocional")),
            "figurino": _text(scene.get("figurino")),
            "contexto_visual": _text(scene.get("contexto_visual")),
            "personagem_principal": _text(scene.get("personagem_principal")),
            "expressao": _text(scene.get("expressao")),
        })
    if not scenes:
        raise ValueError("Nenhuma cena com texto válido foi encontrada no JSON.")

    style = _text(data.get("estilo_recomendado"))
    if style not in ESTILOS_NARRATIVOS:
        style = "misto"

    return {
        "estilo": "ia_externa",
        "label": EXTERNAL_AI_LABEL,
        "modo": "completa",
        "origem": EXTERNAL_AI_ORIGIN,
        "titulo": _text(data.get("titulo") or state.get("titulo")),
        "sinopse_poetica": _text(data.get("sinopse_poetica") or data.get("sinopse")),
        "cenas_texto": scenes,
        "licao_final": normalizar_licao_final(data.get("licao_final")),
        "estilo_recomendado": style,
        "justificativa_criativa": _text(data.get("justificativa_criativa")),
    }


def register_external_version(state: dict, version: dict, *, source_mode: str) -> tuple[str, str]:
    """Guarda uma versão externa na biblioteca e persiste o Book Master."""
    if not _text(state.get("colecao")):
        raise ValueError("Defina a coleção antes de importar a versão externa.")
    if not _text(version.get("titulo") or state.get("titulo")):
        raise ValueError("A versão externa precisa ter título.")

    if not _text(state.get("titulo")):
        state["titulo"] = _text(version.get("titulo"))

    payload = json.dumps(version, ensure_ascii=False, sort_keys=True).encode("utf-8")
    key = "ia_externa_" + hashlib.sha256(payload).hexdigest()[:10]
    item = deepcopy(version)
    item.update({
        "origem": EXTERNAL_AI_ORIGIN,
        "source_mode": source_mode if source_mode in VALID_SOURCES else SOURCE_IDEA,
        "faixa_etaria": normalizar_faixa_etaria(state.get("faixa_etaria")),
        "colecao": state.get("colecao"),
        "status": "atual",
    })
    library = deepcopy(state.get("versoes_narrativas_salvas") or {})
    library[key] = item
    state["versoes_narrativas_salvas"] = library
    state["versao_ia_externa_ultima"] = key
    path = persist_generation_snapshot(
        state,
        reason=f"ia_externa_{item['source_mode']}",
        updates={
            "versoes_narrativas_salvas": library,
            "versao_ia_externa_ultima": key,
        },
    )
    return key, path


def activate_external_version(state: dict, key: str, version: dict) -> dict:
    """Ativa versão externa preservando biblioteca e arquivando derivados atuais."""
    current = _text(state.get("versao_narrativa_ativa"))
    snapshot = {}
    for field in DERIVADOS_NARRATIVOS:
        if field in state and state.get(field) not in (None, "", [], {}, False):
            snapshot[field] = deepcopy(state.get(field))
    if current and snapshot:
        history = deepcopy(state.get("historico_derivados_por_versao") or {})
        history.setdefault(current, []).append(snapshot)
        state["historico_derivados_por_versao"] = history

    style = _text(version.get("estilo_recomendado"))
    if style not in ESTILOS_NARRATIVOS:
        style = "misto"
    new_state = aplicar_estilo_ao_state(dict(state), style, version)
    for field in DERIVADOS_NARRATIVOS:
        new_state.pop(field, None)
    new_state["revisao_aprovada"] = False
    new_state["pacote_pronto"] = False
    new_state["versao_narrativa_ativa"] = key
    new_state["versao_narrativa_origem"] = EXTERNAL_AI_ORIGIN
    new_state["estilo_narrativo_label"] = EXTERNAL_AI_LABEL
    new_state["estilo_escolhido_no_comparador"] = True
    new_state["modo_comparacao_escolhido"] = "completa"
    new_state["idade_historia_precisa_regenerar"] = False
    state.clear()
    state.update(new_state)
    persist_generation_snapshot(state, reason="ativar_ia_externa")
    return state

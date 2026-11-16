"""FaithBloom Full Editorial Remaster — mesa de revisão textual controlada.

Reutiliza Editor de História, Revisor, Prompt-Mestre, Emotional & Color Director
sem duplicar suas regras. No modo manual, alterações continuam como propostas.
No Autopilot, o clique inicial autoriza correções editoriais seguras apenas na
versão DERIVADA, incluindo inferência de metadados faltantes e ciclos curtos de
auto-reparo antes de devolver um bloqueio à autora.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from book_doctor import sha256


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _verify_original(state: dict) -> None:
    original = state.get("original") or {}
    path = Path(str(original.get("arquivo") or ""))
    expected = str(original.get("sha256") or "")
    if not path.exists():
        raise ValueError("Original preservado não encontrado. Revisão bloqueada.")
    if expected and sha256(str(path)) != expected:
        raise ValueError("SHA-256 do original divergiu. Revisão bloqueada.")


def _state_path(state: dict) -> Path:
    raw = str(state.get("arquivo_estado") or "").strip()
    if not raw:
        raise ValueError("Estado do remaster não possui arquivo_estado para persistência segura.")
    return Path(raw)


def salvar_estado_remaster(state: dict) -> dict:
    """Persiste apenas a versão derivada; o PDF original nunca é tocado."""
    _verify_original(state)
    path = _state_path(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(state)
    payload["atualizado_em"] = _now_iso()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def carregar_dossie(state: dict) -> dict:
    path = _state_path(state).parent / "editorial_dossier.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def aprovar_dossie_para_edicao(state: dict, dossie: dict, *, aprovado: bool) -> dict:
    """Libera o Editor somente após decisão humana explícita ou autorização do Autopilot."""
    _verify_original(state)
    if not dossie or dossie.get("remaster_id") != state.get("remaster_id"):
        raise ValueError("Dossiê ausente ou não pertence a este remaster.")
    novo = deepcopy(state)
    novo["dossie_editorial_aprovado_para_edicao"] = bool(aprovado)
    novo["dossie_editorial_decidido_em"] = _now_iso()
    novo["status"] = "edicao_textual_liberada" if aprovado else "dossie_rejeitado_ou_pendente"
    return salvar_estado_remaster(novo)


def _scene_index(state: dict, numero_cena: int) -> int:
    for idx, cena in enumerate(state.get("cenas_texto") or []):
        if int(cena.get("numero") or idx + 1) == int(numero_cena):
            return idx
    raise ValueError(f"Cena {numero_cena} não encontrada.")


def gerar_proposta_edicao_cena(
    state: dict,
    numero_cena: int,
    instrucao: str,
    chamar_llm: Callable,
) -> dict:
    """Gera BEFORE/AFTER sem aplicar a mudança ao livro."""
    _verify_original(state)
    if not state.get("dossie_editorial_aprovado_para_edicao"):
        raise ValueError("Aprove o Dossiê Editorial antes de gerar propostas de edição.")
    pedido = str(instrucao or "").strip()
    if not pedido:
        raise ValueError("Informe o que deve ser melhorado nesta cena.")

    idx = _scene_index(state, numero_cena)
    antes = deepcopy((state.get("cenas_texto") or [])[idx])

    from agents.editor_historia import editar_cena

    depois = editar_cena(antes, pedido, deepcopy(state), chamar_llm)
    if not isinstance(depois, dict):
        raise RuntimeError("Editor de História não retornou uma cena estruturada.")
    if int(depois.get("numero") or numero_cena) != int(numero_cena):
        raise RuntimeError("Editor tentou alterar a identidade/numeração da cena. Proposta bloqueada.")

    proposal = {
        "schema": "faithbloom.editorial-remaster-scene-proposal.v1",
        "remaster_id": state.get("remaster_id", ""),
        "numero_cena": int(numero_cena),
        "pagina_origem": antes.get("pagina_origem"),
        "instrucao": pedido,
        "antes": antes,
        "depois": depois,
        "status": "aguardando_aprovacao",
        "gerado_em": _now_iso(),
        "aplicado": False,
    }
    proposals = _state_path(state).parent / "propostas"
    proposals.mkdir(parents=True, exist_ok=True)
    path = proposals / f"cena_{int(numero_cena):03d}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    proposal["arquivo_proposta"] = str(path)
    return proposal


def aplicar_proposta_edicao(state: dict, proposta: dict, *, aprovado: bool) -> dict:
    """Aplica somente proposta aprovada; rejeição não altera cenas."""
    _verify_original(state)
    if not proposta or proposta.get("remaster_id") != state.get("remaster_id"):
        raise ValueError("Proposta ausente ou pertence a outro remaster.")
    novo = deepcopy(state)
    historico = list(novo.get("historico_revisao_textual") or [])
    registro = {
        "numero_cena": int(proposta.get("numero_cena") or 0),
        "decidido_em": _now_iso(),
        "aprovado": bool(aprovado),
        "antes": deepcopy(proposta.get("antes") or {}),
        "depois": deepcopy(proposta.get("depois") or {}),
        "instrucao": proposta.get("instrucao", ""),
    }
    if aprovado:
        idx = _scene_index(novo, registro["numero_cena"])
        atual = deepcopy((novo.get("cenas_texto") or [])[idx])
        esperado = proposta.get("antes") or {}
        if atual != esperado:
            raise ValueError("A cena mudou desde que a proposta foi gerada. Gere uma nova proposta antes de aplicar.")
        nova_cena = deepcopy(proposta.get("depois") or {})
        nova_cena["numero"] = atual.get("numero", registro["numero_cena"])
        nova_cena["pagina_origem"] = atual.get("pagina_origem")
        nova_cena["origem"] = "editorial_remaster_aprovado"
        novo["cenas_texto"][idx] = nova_cena
        novo["revisao_aprovada"] = False
        novo["status"] = "texto_em_revisao"
    historico.append(registro)
    novo["historico_revisao_textual"] = historico
    return salvar_estado_remaster(novo)


def _autopilot_ativo(state: dict) -> bool:
    auth = state.get("autopilot_authorization") or {}
    return bool(auth and auth.get("final_human_approval_required"))


def _inferir_metadados_editoriais_faltantes(state: dict, chamar_llm: Callable) -> tuple[dict, dict]:
    """Infere metadados que antes eram pedidos em ficha, usando somente a obra derivada.

    Não sobrescreve campos já existentes. Referência bíblica inferida continua
    submetida ao Bible Guard antes da etapa visual/final.
    """
    campos = {
        "licao_final": str(state.get("licao_final") or "").strip(),
        "aprendizado_cristao": str(state.get("aprendizado_cristao") or "").strip(),
        "emocao_central": str(state.get("emocao_central") or "").strip(),
        "versiculo_referencia": str(state.get("versiculo_referencia") or "").strip(),
    }
    faltantes = [k for k, v in campos.items() if not v]
    if not faltantes:
        return deepcopy(state), {"inferred": False, "fields": []}

    cenas = [
        {"numero": c.get("numero"), "texto": c.get("texto", "")}
        for c in (state.get("cenas_texto") or []) if isinstance(c, dict)
    ]
    resposta = chamar_llm(
        sistema=(
            "Você é o Analista Editorial Cristão do FaithBloom. Leia a obra já publicada e infira apenas metadados "
            "editoriais que estiverem faltando. Não reescreva a história. Preserve o sentido vivido na narrativa; "
            "não transforme a história em sermão. Para referência bíblica, priorize uma referência explicitamente "
            "presente na obra. Se não houver uma explícita, escolha somente uma referência curta e coerente com a "
            "verdade central; ela ainda passará pelo Bible Guard. Responda apenas JSON."
        ),
        instrucao=(
            "Título: " + str(state.get("titulo") or "") + "\n"
            "Faixa etária: " + str(state.get("faixa_etaria") or "3-8") + "\n"
            "Campos faltantes: " + json.dumps(faltantes, ensure_ascii=False) + "\n"
            "Campos já protegidos: " + json.dumps({k: v for k, v in campos.items() if v}, ensure_ascii=False) + "\n"
            "Cenas: " + json.dumps(cenas, ensure_ascii=False) + "\n"
            "Retorne JSON com licao_final, aprendizado_cristao, emocao_central, versiculo_referencia, "
            "confianca (0-1 por campo) e justificativas (objeto por campo)."
        ),
    )
    if not isinstance(resposta, dict):
        raise RuntimeError("Especialista de metadados não retornou JSON estruturado.")

    novo = deepcopy(state)
    aplicados = []
    for campo in faltantes:
        valor = str(resposta.get(campo) or "").strip()
        if valor:
            novo[campo] = valor
            aplicados.append(campo)
    if "licao_final" in faltantes and not str(novo.get("licao_final") or "").strip():
        raise RuntimeError("Não foi possível inferir automaticamente a Lição de Moral obrigatória.")

    registro = {
        "em": _now_iso(),
        "campos_inferidos": aplicados,
        "confianca": deepcopy(resposta.get("confianca") or {}),
        "justificativas": deepcopy(resposta.get("justificativas") or {}),
        "fonte": "obra_remasterizada",
        "revisao_final_humana": True,
    }
    novo.setdefault("historico_inferencia_editorial", []).append(registro)
    novo["metadata_editorial_inferida_pelo_autopilot"] = True
    return salvar_estado_remaster(novo), {"inferred": bool(aplicados), "fields": aplicados, **registro}


def _normalize_ws(value: object) -> str:
    return " ".join(str(value or "").split())


def _recover_bible_text_from_published_original(state: dict, chamar_llm: Callable) -> tuple[dict, dict]:
    """Recupera apenas texto bíblico que já esteja literalmente no original publicado.

    O modelo atua como localizador, não como fonte bíblica. A resposta só é aceita
    quando o trecho retornado pode ser comprovado no texto extraído de uma página
    do PDF original. Assim o Remaster preserva a Palavra de Deus já publicada sem
    inventar, completar ou traduzir versículos.
    """
    if any(str(state.get(k) or "").strip() for k in ("versiculo_texto_original", "versiculo_texto", "bible_verse_text")):
        return deepcopy(state), {"recovered": False, "reason": "texto_biblico_ja_presente"}

    reference = str(state.get("versiculo_referencia") or "").strip()
    pages = [
        {"pagina": int(p.get("pagina") or 0), "texto": str(p.get("texto_extraido") or "").strip()}
        for p in (state.get("paginas_texto_extraido") or [])
        if isinstance(p, dict) and str(p.get("texto_extraido") or "").strip()
    ]
    if not reference or not pages:
        return deepcopy(state), {"recovered": False, "reason": "referencia_ou_paginas_ausentes"}

    ref_key = _normalize_ws(reference).casefold()
    candidates = [p for p in pages if ref_key in _normalize_ws(p["texto"]).casefold()]
    if not candidates:
        candidates = pages[-5:]

    raw = chamar_llm(
        sistema=(
            "Você é um LOCALIZADOR de texto em um livro já publicado. NÃO forneça conhecimento bíblico externo, "
            "não complete, não corrija e não traduza versículos. Encontre somente um trecho que esteja literalmente "
            "nas páginas fornecidas e que corresponda à referência informada. Se não puder provar, retorne found=false."
        ),
        instrucao=(
            "Referência: " + reference + "\n"
            "Páginas: " + json.dumps(candidates, ensure_ascii=False) + "\n"
            "Retorne JSON {found:boolean,pagina:inteiro,texto_exato:string}. "
            "texto_exato deve ser copiado do material fornecido, sem alteração."
        ),
    )
    if not isinstance(raw, dict) or raw.get("found") is not True:
        return deepcopy(state), {"recovered": False, "reason": "nao_localizado"}

    try:
        page_no = int(raw.get("pagina"))
    except (TypeError, ValueError):
        return deepcopy(state), {"recovered": False, "reason": "pagina_invalida"}
    quote = str(raw.get("texto_exato") or "").strip()
    page = next((p for p in candidates if p["pagina"] == page_no), None)
    if not page or not quote:
        return deepcopy(state), {"recovered": False, "reason": "evidencia_incompleta"}

    normalized_quote = _normalize_ws(quote)
    normalized_page = _normalize_ws(page["texto"])
    if normalized_quote not in normalized_page:
        return deepcopy(state), {
            "recovered": False,
            "reason": "trecho_nao_comprovado_no_original",
            "pagina": page_no,
        }

    novo = deepcopy(state)
    novo["versiculo_texto_original"] = normalized_quote
    novo["versiculo_texto_source_page"] = page_no
    novo["versiculo_texto_source"] = "original_published_book"
    novo.setdefault("historico_bible_guard", []).append({
        "em": _now_iso(),
        "acao": "recover_exact_scripture_from_published_original",
        "referencia": reference,
        "pagina": page_no,
        "verified_literal_source": True,
        "ai_generated_scripture": False,
    })
    return salvar_estado_remaster(novo), {
        "recovered": True,
        "reference": reference,
        "pagina": page_no,
        "source": "original_published_book",
    }


def _normalizar_cenas_reparo(raw: object, atuais: list[dict]) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("Especialista editorial não retornou cenas revisadas válidas.")
    by_num = {int(c.get("numero") or i + 1): c for i, c in enumerate(atuais) if isinstance(c, dict)}
    saida = []
    for i, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise RuntimeError("Cena reparada inválida.")
        numero = item.get("numero") or i
        try:
            numero = int(numero)
        except (TypeError, ValueError):
            numero = i
        original = by_num.get(numero) or (atuais[i - 1] if i - 1 < len(atuais) else {})
        texto = str(item.get("texto") or "").strip()
        if not texto:
            raise RuntimeError(f"Cena {numero} ficou sem texto durante o auto-reparo editorial.")
        cena = deepcopy(original)
        cena.update(deepcopy(item))
        cena["numero"] = int(original.get("numero") or numero)
        cena["pagina_origem"] = original.get("pagina_origem")
        cena["texto"] = texto
        cena["origem"] = "autopilot_editorial_repair"
        saida.append(cena)
    if len(saida) != len(atuais):
        raise RuntimeError("Auto-reparo alteraria a quantidade de cenas. Encaminhar ao Storyteller em vez de aplicar silenciosamente.")
    return saida


def _reparar_pendencias_editoriais(state: dict, result: dict, chamar_llm: Callable, ciclo: int) -> tuple[dict, dict]:
    """Corrige somente pendências apontadas pelo Revisor/Prompt-Mestre na derivada."""
    notas = deepcopy(result.get("notas") or [])
    prompt = deepcopy(result.get("prompt_mestre") or {})
    bloqueios = deepcopy(prompt.get("bloqueios") or [])
    harmony = deepcopy(result.get("story_experience_biblical_harmony") or {})
    harmony_blockers = deepcopy(harmony.get("blockers") or [])
    harmony_recommendations = deepcopy(harmony.get("recommendations") or [])
    if not notas and not bloqueios and not harmony_blockers:
        return deepcopy(state), {"changed": False, "cycle": ciclo}

    atuais = deepcopy(state.get("cenas_texto") or [])
    resposta = chamar_llm(
        sistema=(
            "Você é o Editor de História de recuperação do FaithBloom. Corrija SOMENTE as pendências apontadas pelo "
            "Revisor e pelo Prompt-Mestre na versão derivada. Preserve alma, propósito, personagens, moral, aprendizado "
            "cristão, referência bíblica, faixa etária, páginas de origem e tudo que já funciona. Não crie cenas novas "
            "neste reparo; mudanças estruturais maiores pertencem ao Storyteller. A história deve continuar natural, "
            "emocional e não sermonizante. Responda apenas JSON."
        ),
        instrucao=(
            "Ciclo de auto-reparo: " + str(ciclo) + "\n"
            "Lição de moral: " + str(state.get("licao_final") or "") + "\n"
            "Aprendizado cristão: " + str(state.get("aprendizado_cristao") or "") + "\n"
            "Referência bíblica: " + str(state.get("versiculo_referencia") or "") + "\n"
            "Notas do Revisor: " + json.dumps(notas, ensure_ascii=False) + "\n"
            "Bloqueios Prompt-Mestre: " + json.dumps(bloqueios, ensure_ascii=False) + "\n"
            "Bloqueios Story Experience/Biblical Harmony: " + json.dumps(harmony_blockers, ensure_ascii=False) + "\n"
            "Recomendações Story Experience/Biblical Harmony: " + json.dumps(harmony_recommendations, ensure_ascii=False) + "\n"
            "Cenas atuais: " + json.dumps(atuais, ensure_ascii=False) + "\n"
            "Retorne JSON com cenas_texto_revisadas (mesma quantidade e mesmos números), ajustes_realizados (lista) "
            "e invariantes_preservados=true."
        ),
    )
    if not isinstance(resposta, dict) or resposta.get("invariantes_preservados") is not True:
        raise RuntimeError("Auto-reparo editorial não confirmou preservação dos invariantes da obra.")

    novo = deepcopy(state)
    novo["cenas_texto"] = _normalizar_cenas_reparo(resposta.get("cenas_texto_revisadas"), atuais)
    novo["revisao_aprovada"] = False
    novo["metadata_emocional_confirmada"] = False
    novo["mapa_emocional"] = []
    novo["status"] = "autopilot_editorial_repair_aplicado"
    registro = {
        "em": _now_iso(),
        "ciclo": ciclo,
        "notas_revisor": notas,
        "bloqueios_prompt_mestre": bloqueios,
        "bloqueios_story_experience": harmony_blockers,
        "recomendacoes_story_experience": harmony_recommendations,
        "ajustes_realizados": deepcopy(resposta.get("ajustes_realizados") or []),
        "invariantes_preservados": True,
    }
    novo.setdefault("historico_auto_reparo_editorial", []).append(registro)
    return salvar_estado_remaster(novo), {"changed": True, **registro}


def rodar_revisao_final_textual(state: dict, chamar_llm: Callable) -> dict:
    """Revisor + auto-reparo controlado + emoções + cores + Prompt-Mestre + Bible Guard.

    No Autopilot, metadados editoriais ausentes são inferidos da própria obra e
    pendências revisáveis passam por até 3 ciclos internos antes de virar um
    bloqueio visível. Em modo manual, mantém o comportamento conservador de uma
    única revisão.
    """
    _verify_original(state)
    if not state.get("dossie_editorial_aprovado_para_edicao"):
        raise ValueError("Dossiê Editorial ainda não foi aprovado para edição.")

    from agents.revisor import revisor_node
    from editorial_remaster_emotional import analisar_emocoes_automaticamente, metadata_emocional_completa
    from emotional_color_director import construir_mapa_emocional
    from prompt_master_compliance import avaliar_prompt_mestre
    from biblical_reference_validator import reference_gate
    from story_experience_biblical_harmony import (
        bible_final_text_gate,
        review_story_experience_harmony,
    )

    work = deepcopy(state)
    metadata_info = {"inferred": False, "fields": []}
    bible_text_recovery = {"recovered": False, "reason": "not_attempted"}
    if _autopilot_ativo(work):
        work, metadata_info = _inferir_metadados_editoriais_faltantes(work, chamar_llm)
        work, bible_text_recovery = _recover_bible_text_from_published_original(work, chamar_llm)

    max_ciclos = 3 if _autopilot_ativo(work) else 1
    repairs = []
    ultimo = None

    for ciclo in range(1, max_ciclos + 1):
        revisado = revisor_node(deepcopy(work), chamar_llm)
        aprovado = bool(revisado.get("revisao_aprovada"))

        if aprovado:
            emocional = metadata_emocional_completa(revisado)
            if emocional.get("ok"):
                revisado = deepcopy(revisado)
                revisado["mapa_emocional"] = construir_mapa_emocional(revisado.get("cenas_texto") or [])
                revisado["metadata_emocional_confirmada"] = True
                revisado.setdefault("metadata_emocional_modo", "reutilizado_do_revisor")
            else:
                revisado = analisar_emocoes_automaticamente(revisado, chamar_llm)

        compliance = avaliar_prompt_mestre(dict(revisado))
        bible = reference_gate(dict(revisado))
        harmony = review_story_experience_harmony(dict(revisado), chamar_llm) if aprovado else {
            "schema": "faithbloom.story-experience-biblical-harmony.v1",
            "ok": False,
            "checks": {},
            "blockers": ["revisao_editorial_nao_aprovada"],
            "strengths": [],
            "recommendations": [],
            "summary": "A auditoria de experiência/harmonia aguarda revisão editorial aprovada.",
            "rewrote_story": False,
        }
        bible_text = bible_final_text_gate(dict(revisado))
        # A etapa textual pode liberar o handoff visual com referência bíblica
        # presente e harmonia narrativa aprovada. A validação de fonte/contexto e
        # o TEXTO bíblico aprovado continuam gates obrigatórios de fechamento,
        # não devem impedir trabalho visual já autorizado.
        pronto = bool(
            aprovado
            and compliance.get("ok_para_finalizar")
            and bool(str(revisado.get("versiculo_referencia") or "").strip())
            and harmony.get("ok")
        )

        novo = deepcopy(work)
        novo["revisao_aprovada"] = aprovado
        novo["notas_revisor"] = deepcopy(revisado.get("notas_revisor") or [])
        if aprovado:
            novo["cenas_texto"] = deepcopy(revisado.get("cenas_texto") or [])
            novo["mapa_emocional"] = deepcopy(revisado.get("mapa_emocional") or [])
            novo["metadata_emocional_confirmada"] = True
            novo["metadata_emocional_modo"] = revisado.get("metadata_emocional_modo", "automatico_com_override_humano")
            novo["analise_emocional_automatica"] = deepcopy(revisado.get("analise_emocional_automatica") or {})
        novo["prompt_master_compliance_remaster"] = compliance
        novo["bible_reference_gate_remaster"] = bible
        novo["bible_final_text_gate_remaster"] = bible_text
        novo["story_experience_biblical_harmony"] = harmony
        novo["necessita_intervencao_estrutural_roteirista"] = not aprovado
        novo["status"] = "texto_aprovado_pronto_para_visual" if pronto else "texto_ainda_em_revisao"
        novo = salvar_estado_remaster(novo)

        ultimo = {
            "aprovado": aprovado,
            "notas": deepcopy(novo.get("notas_revisor") or []),
            "mapa_emocional": deepcopy(novo.get("mapa_emocional") or []),
            "analise_emocional_automatica": deepcopy(novo.get("analise_emocional_automatica") or {}),
            "prompt_mestre": compliance,
            "bible_reference": bible,
            "bible_final_text": bible_text,
            "story_experience_biblical_harmony": harmony,
            "necessita_roteirista": not aprovado,
            "pronto_para_visual": pronto,
            "metadata_inference": deepcopy(metadata_info),
            "bible_text_recovery": deepcopy(bible_text_recovery),
            "auto_repair_cycles": deepcopy(repairs),
            "estado": novo,
        }
        if pronto:
            return ultimo
        if not _autopilot_ativo(novo) or ciclo >= max_ciclos:
            return ultimo

        work, repair_info = _reparar_pendencias_editoriais(novo, ultimo, chamar_llm, ciclo)
        repairs.append(repair_info)

    return ultimo or {
        "aprovado": False,
        "notas": ["Revisão final não produziu resultado."],
        "mapa_emocional": [],
        "prompt_mestre": {},
        "bible_reference": {},
        "bible_final_text": {},
        "story_experience_biblical_harmony": {},
        "necessita_roteirista": True,
        "pronto_para_visual": False,
        "metadata_inference": metadata_info,
        "bible_text_recovery": bible_text_recovery,
        "auto_repair_cycles": repairs,
        "estado": salvar_estado_remaster(work),
    }

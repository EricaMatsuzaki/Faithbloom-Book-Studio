"""Storyteller layer for FaithBloom Full Editorial Remaster.

Keeps the legacy structural-review path for compatibility and adds a safe
"enrich without deviating" flow for already-published books. The Storyteller may
propose richer experience, Heart Arc, discovery, emotion, humor, interaction and
new scenes when there is real editorial gain, but proposals are always derived,
versioned and require explicit human approval before replacing the active
Remastered text. The preserved original is never mutated.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from age_profiles import normalizar_faixa_etaria, instrucao_faixa_etaria
from agent_skills import skill_contract
from book_doctor import sha256


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _verify_original(state: dict) -> tuple[str, str]:
    original = state.get("original") or {}
    path = str(original.get("arquivo") or "")
    expected = str(original.get("sha256") or "")
    if not path or not expected or sha256(path) != expected:
        raise ValueError("Integridade do original não confirmada.")
    return path, expected


def _state_path(state: dict) -> Path:
    raw = str(state.get("arquivo_estado") or "").strip()
    if not raw:
        raise ValueError("Estado do remaster não possui arquivo_estado para persistência segura.")
    return Path(raw)


def _write_state(state: dict) -> dict:
    _verify_original(state)
    path = _state_path(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(state)
    payload["atualizado_em"] = _now_iso()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _normalize_proposed_scenes(raw_scenes: object, original_scenes: list[dict]) -> list[dict]:
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise RuntimeError("Roteirista não retornou uma lista válida de cenas propostas.")
    normalized: list[dict] = []
    by_original_number = {
        int(scene.get("numero") or idx + 1): scene
        for idx, scene in enumerate(original_scenes)
        if isinstance(scene, dict)
    }
    for idx, item in enumerate(raw_scenes, 1):
        if not isinstance(item, dict):
            raise RuntimeError("Cada cena proposta pelo Roteirista deve ser um objeto estruturado.")
        scene = deepcopy(item)
        text = str(scene.get("texto") or "").strip()
        if not text:
            raise RuntimeError(f"Cena proposta {idx} ficou sem texto.")
        original_number = scene.get("numero_origem") or scene.get("numero")
        try:
            original_number_int = int(original_number) if original_number is not None else None
        except (TypeError, ValueError):
            original_number_int = None
        original = by_original_number.get(original_number_int) if original_number_int else None
        scene["numero"] = idx
        scene["numero_origem"] = original_number_int if original else None
        scene["pagina_origem"] = original.get("pagina_origem") if original else None
        scene["origem"] = "storyteller_enrichment_candidate"
        normalized.append(scene)
    return normalized


def gerar_parecer_estrutural_roteirista(state: dict, chamar_llm: Callable, *, autorizado: bool) -> dict:
    """Legacy structural opinion, kept for compatibility and manual diagnostics."""
    if not autorizado:
        raise ValueError("Autorização explícita é obrigatória para chamar o Roteirista no remaster.")
    if not state.get("necessita_intervencao_estrutural_roteirista"):
        raise ValueError("O Revisor não marcou necessidade de intervenção estrutural do Roteirista.")
    path, expected = _verify_original(state)

    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    scenes = deepcopy(state.get("cenas_texto") or [])
    system = f"""
Você é o Roteirista principal do FaithBloom atuando em uma OBRA JÁ PUBLICADA.
Seu papel aqui é produzir um PARECER ESTRUTURAL, não reescrever a história.

{instrucao_faixa_etaria(faixa)}

REGRAS OBRIGATÓRIAS:
- preserve a alma, premissa, personagens, lição cristã e referência bíblica;
- não proponha trocar o tema central apenas para deixar a obra diferente;
- analise Heart Arc, experiência emocional, ritmo, page-turn, clareza, ação visual e integração natural da fé;
- se uma cena já funciona, marque MANTER;
- prefira correção pontual pelo Editor de História quando possível;
- recomende intervenção estrutural somente onde houver ganho real;
- não forneça texto bíblico completo;
- não aplique nenhuma alteração.

Título: {state.get('titulo','')}
Coleção: {state.get('colecao','')}
Emoção central: {state.get('emocao_central','')}
Aprendizado cristão: {state.get('aprendizado_cristao','')}
Lição final: {state.get('licao_final','')}
Referência bíblica: {state.get('versiculo_referencia','')}
""" + "\n\n" + skill_contract("storyteller")

    result = chamar_llm(
        sistema=system,
        instrucao=(
            "Analise estas cenas sem reescrevê-las: " + json.dumps(scenes, ensure_ascii=False) +
            "\nResponda em JSON com: diagnostico_geral, heart_arc, manter, ajustes_pontuais, "
            "ajustes_estruturais, cenas_prioritarias, risco_de_perder_alma, ordem_recomendada. "
            "Cada item de cena deve referenciar o numero da cena e explicar o motivo."
        ),
    )
    if not isinstance(result, dict):
        raise RuntimeError("Roteirista não retornou parecer estruturado em JSON.")

    parecer = {
        "schema": "faithbloom.editorial-remaster-storyteller-review.v1",
        "remaster_id": state.get("remaster_id", ""),
        "gerado_em": _now_iso(),
        "original_sha256": expected,
        "alteracoes_aplicadas": False,
        "parecer": result,
        "politica": "Parecer somente. Aplicação continua controlada na versão derivada.",
    }
    raw = str(state.get("arquivo_estado") or "")
    if raw:
        out = Path(raw).parent / "storyteller_structural_review.json"
        out.write_text(json.dumps(parecer, ensure_ascii=False, indent=2), encoding="utf-8")
        parecer["arquivo_parecer"] = str(out)
    if sha256(path) != expected:
        raise RuntimeError("O original mudou durante o parecer do Roteirista. Operação bloqueada.")
    return parecer


def gerar_proposta_enriquecimento_roteirista(state: dict, chamar_llm: Callable) -> dict:
    """Create a full-book Storyteller enrichment candidate without mutating active text.

    The Storyteller is allowed to revise, expand, reorder and add scenes only when
    that creates concrete editorial gain. Core purpose, Christian learning,
    moral, Bible reference, protected characters, age profile and story soul are
    explicit invariants. The candidate remains pending until human approval.
    """
    path, expected = _verify_original(state)
    if not state.get("dossie_editorial_aprovado_para_edicao"):
        raise ValueError("Dossiê Editorial ainda não foi aprovado para edição.")

    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    scenes = deepcopy(state.get("cenas_texto") or [])
    if not scenes:
        raise ValueError("Remaster sem cenas para análise do Storyteller.")

    system = f"""
Você é o Storyteller/Roteirista principal do FaithBloom revisando uma OBRA JÁ PUBLICADA.
A regra editorial central é: ENRIQUECER SEM DESVIAR.

{instrucao_faixa_etaria(faixa)}

OBJETIVO:
- avaliar a obra inteira, não apenas falhas locais;
- fortalecer História → Experiência → Emoção → Descoberta → Transformação → Lição → Verdade bíblica;
- fortalecer o Heart Arc: encantamento → emoção → experiência → descoberta → transformação → fé;
- quando houver ganho real, você PODE revisar, expandir, reorganizar e acrescentar cenas;
- novas cenas podem trazer aventura, interação, humor, descoberta, tentativa, consequência, vínculo, emoção ou transformação;
- se a obra já estiver forte, não invente mudanças só para parecer diferente.

INVARIANTES — NUNCA ALTERAR:
- propósito central e alma da história;
- identidade e personalidade protegida dos personagens;
- aprendizado cristão central;
- lição de moral;
- referência bíblica/base de verdade;
- adequação à faixa etária;
- tom da coleção e continuidade canônica.

REGRAS:
- fé deve nascer da experiência da personagem, não de sermão artificial;
- preserve cenas boas e falas memoráveis quando funcionarem;
- não banalize emoção nem resolva toda dificuldade de forma mágica;
- não adicione sofrimento, trauma ou conflito apenas para aumentar drama;
- não forneça texto bíblico longo: preserve a referência e o sentido já definidos;
- qualquer mudança proposta deve ter motivo editorial claro;
- a saída é apenas uma CANDIDATA derivada; nunca afirme que foi aprovada/publicada.

DADOS PROTEGIDOS:
Título: {state.get('titulo','')}
Coleção: {state.get('colecao','')}
Emoção central: {state.get('emocao_central','')}
Aprendizado cristão: {state.get('aprendizado_cristao','')}
Lição de moral: {state.get('licao_final','')}
Referência bíblica: {state.get('versiculo_referencia','')}
""" + "\n\n" + skill_contract("storyteller")

    instruction = (
        "Analise e, somente se houver ganho editorial real, proponha uma versão enriquecida destas cenas: "
        + json.dumps(scenes, ensure_ascii=False)
        + "\nRetorne JSON com exatamente estes campos: "
        "ganho_editorial (boolean), diagnostico_geral, motivos (lista), heart_arc, experiencia, "
        "descoberta_transformacao, licao_moral_preservada (boolean), mensagem_biblica_preservada (boolean), "
        "risco_de_desvio (baixo|medio|alto), novas_cenas_adicionadas (lista), cenas_texto_propostas (lista). "
        "Em cenas_texto_propostas, cada cena deve ter texto e, quando derivar de cena antiga, numero_origem. "
        "Se ganho_editorial=false, devolva as mesmas cenas sem alterações substanciais."
    )
    result = chamar_llm(sistema=system, instrucao=instruction)
    if not isinstance(result, dict):
        raise RuntimeError("Storyteller não retornou proposta estruturada em JSON.")
    if result.get("licao_moral_preservada") is not True:
        raise RuntimeError("Proposta bloqueada: Storyteller não confirmou preservação da lição de moral.")
    if result.get("mensagem_biblica_preservada") is not True:
        raise RuntimeError("Proposta bloqueada: Storyteller não confirmou preservação da mensagem bíblica.")
    if str(result.get("risco_de_desvio") or "").casefold() == "alto":
        raise RuntimeError("Proposta bloqueada: risco alto de desvio da essência da obra.")

    ganho = bool(result.get("ganho_editorial"))
    proposed = _normalize_proposed_scenes(result.get("cenas_texto_propostas"), scenes)
    if not ganho:
        proposed = deepcopy(scenes)

    proposal = {
        "schema": "faithbloom.editorial-remaster-storyteller-enrichment.v1",
        "remaster_id": state.get("remaster_id", ""),
        "gerado_em": _now_iso(),
        "original_sha256": expected,
        "status": "aguardando_aprovacao" if ganho else "sem_mudancas_recomendadas",
        "ganho_editorial": ganho,
        "antes": scenes,
        "depois": proposed,
        "analise": {
            "diagnostico_geral": result.get("diagnostico_geral", ""),
            "motivos": deepcopy(result.get("motivos") or []),
            "heart_arc": deepcopy(result.get("heart_arc")),
            "experiencia": deepcopy(result.get("experiencia")),
            "descoberta_transformacao": deepcopy(result.get("descoberta_transformacao")),
            "novas_cenas_adicionadas": deepcopy(result.get("novas_cenas_adicionadas") or []),
            "risco_de_desvio": result.get("risco_de_desvio", "baixo"),
            "licao_moral_preservada": True,
            "mensagem_biblica_preservada": True,
        },
        "politica": "Enriquecer sem desviar; original imutável; candidata derivada exige aprovação humana.",
        "aplicado": False,
    }
    folder = _state_path(state).parent / "propostas_storyteller"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"storyteller_enrichment_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    out.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    proposal["arquivo_proposta"] = str(out)

    if sha256(path) != expected:
        raise RuntimeError("O original mudou durante o enriquecimento do Storyteller. Operação bloqueada.")
    return proposal


def aplicar_proposta_enriquecimento_roteirista(state: dict, proposta: dict, *, aprovado: bool) -> dict:
    """Approve/reject a Storyteller candidate on the derived Remaster only."""
    _verify_original(state)
    if not proposta or proposta.get("remaster_id") != state.get("remaster_id"):
        raise ValueError("Proposta do Storyteller ausente ou pertence a outro remaster.")
    if proposta.get("original_sha256") != (state.get("original") or {}).get("sha256"):
        raise ValueError("Proposta foi gerada a partir de outro original. Aplicação bloqueada.")
    if deepcopy(state.get("cenas_texto") or []) != deepcopy(proposta.get("antes") or []):
        raise ValueError("O texto mudou desde a geração da proposta. Gere nova proposta do Storyteller.")

    novo = deepcopy(state)
    history = list(novo.get("historico_storyteller") or [])
    record = {
        "decidido_em": _now_iso(),
        "aprovado": bool(aprovado),
        "ganho_editorial": bool(proposta.get("ganho_editorial")),
        "analise": deepcopy(proposta.get("analise") or {}),
        "antes": deepcopy(proposta.get("antes") or []),
        "depois": deepcopy(proposta.get("depois") or []),
    }
    if aprovado and proposta.get("ganho_editorial"):
        novo["cenas_texto"] = deepcopy(proposta.get("depois") or [])
        novo["storyteller_enrichment_aprovado"] = True
        novo["revisao_aprovada"] = False
        novo["metadata_emocional_confirmada"] = False
        novo["mapa_emocional"] = []
        novo["status"] = "texto_enriquecido_aguardando_revisao_final"
    elif aprovado:
        novo["storyteller_enrichment_aprovado"] = True
        novo["status"] = "storyteller_sem_mudancas_aguardando_revisao_final"
    else:
        novo["storyteller_enrichment_aprovado"] = False
        novo["status"] = "storyteller_rejeitado_texto_derivado_preservado"
    history.append(record)
    novo["historico_storyteller"] = history
    return _write_state(novo)

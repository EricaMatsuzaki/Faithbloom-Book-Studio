"""Parecer estrutural do Roteirista para Full Editorial Remaster.

Reutiliza a skill oficial `storyteller` para diagnosticar estrutura quando o
Revisor continua reprovando após edições pontuais. Não reescreve cenas e não
aplica mudanças automaticamente.
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


def gerar_parecer_estrutural_roteirista(state: dict, chamar_llm: Callable, *, autorizado: bool) -> dict:
    """Produz recomendações estruturais somente após autorização explícita."""
    if not autorizado:
        raise ValueError("Autorização explícita é obrigatória para chamar o Roteirista no remaster.")
    if not state.get("necessita_intervencao_estrutural_roteirista"):
        raise ValueError("O Revisor não marcou necessidade de intervenção estrutural do Roteirista.")
    original = state.get("original") or {}
    path = str(original.get("arquivo") or "")
    expected = str(original.get("sha256") or "")
    if not path or not expected or sha256(path) != expected:
        raise ValueError("Integridade do original não confirmada.")

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
        "politica": "Parecer somente. Aplicação continua cena a cena pelo Editor de História com aprovação humana.",
    }
    raw = str(state.get("arquivo_estado") or "")
    if raw:
        out = Path(raw).parent / "storyteller_structural_review.json"
        out.write_text(json.dumps(parecer, ensure_ascii=False, indent=2), encoding="utf-8")
        parecer["arquivo_parecer"] = str(out)
    if sha256(path) != expected:
        raise RuntimeError("O original mudou durante o parecer do Roteirista. Operação bloqueada.")
    return parecer

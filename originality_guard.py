"""FaithBloom Originality & Ineditism Guard.

Camada de prevenção e auditoria editorial para reduzir risco de imitação/cópia.
O Guard distingue princípios/mecanismos literários gerais de elementos
expressivos específicos. Ele NÃO declara originalidade jurídica mundial e NÃO
substitui pesquisa externa, clearance editorial ou parecer jurídico.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata
from typing import Any

SCHEMA = "faithbloom.originality-guard.v1"

# Mecanismos gerais podem inspirar a arquitetura de leitura. Eles nunca autorizam
# copiar expressão específica de uma obra.
GENERAL_MECHANISMS_ALLOWED = {
    "aventura", "conto cumulativo", "lengalenga", "repeticao", "musicalidade",
    "humor cotidiano", "terceira pessoa proxima", "quadrinhos", "hq",
    "profundidade emocional", "page-turn", "onomatopeias", "dialogo rapido",
    "fábula", "fabula", "rima", "mistério leve", "misterio leve",
}

IMITATION_PATTERNS = [
    r"\bno estilo de\b",
    r"\bimite?\b",
    r"\bcopie?\b",
    r"\bigual (?:a|ao|à)\b",
    r"\bmesma voz (?:de|do|da)\b",
    r"\bmesmo tra[cç]o (?:de|do|da)\b",
    r"\bfa[cç]a como\b",
    r"\breproduza\b",
]


def _plain(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_plain(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_plain(v) for v in value)
    return str(value or "")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^\w\s'-]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _words(text: str) -> list[str]:
    return re.findall(r"[\w'-]+", _normalize(text), flags=re.UNICODE)


def _ngrams(text: str, n: int = 6) -> set[tuple[str, ...]]:
    words = _words(text)
    if len(words) < n:
        return set()
    return {tuple(words[i:i+n]) for i in range(len(words)-n+1)}


def _story_text(state: dict) -> str:
    scenes = state.get("cenas_texto") or []
    parts = [str(state.get("titulo") or ""), str(state.get("subtitulo") or "")]
    for scene in scenes:
        parts.append(str(scene.get("texto") or "") if isinstance(scene, dict) else str(scene))
    parts.append(_plain(state.get("licao_final")))
    return "\n".join(x for x in parts if x)


def _protected_reference_text(ref: dict) -> str:
    """Só compara texto expressivo realmente fornecido para clearance.

    Resumos conceituais e notas de inspiração NÃO entram na comparação textual,
    porque ideias, temas e mecanismos gerais não são tratados como frases copiadas.
    """
    return str(
        ref.get("protected_text")
        or ref.get("text_excerpt")
        or ref.get("quoted_excerpt")
        or ""
    )


def _title_similarity(a: str, b: str) -> float:
    aa, bb = _normalize(a), _normalize(b)
    if not aa or not bb:
        return 0.0
    return SequenceMatcher(None, aa, bb).ratio()


def _shared_long_phrases(a: str, b: str, n: int = 6) -> list[str]:
    shared = _ngrams(a, n) & _ngrams(b, n)
    return [" ".join(x) for x in sorted(shared)[:12]]


def _character_names(state: dict) -> set[str]:
    names = set()
    chars = state.get("personagens") or {}
    if isinstance(chars, dict):
        names.update(_normalize(x) for x in chars if _normalize(x))
    briefing = str(state.get("personagens_narrativa_briefing") or state.get("character_narrative_briefing") or "")
    for line in briefing.splitlines():
        candidate = _normalize(line.split("-")[0].strip())
        if candidate and len(candidate.split()) <= 3:
            names.add(candidate)
    return names


def creation_originality_contract(state: dict | None = None) -> str:
    """Contrato preventivo para agentes geradores/editoriais."""
    state = state or {}
    refs = state.get("inspiration_references") or state.get("referencias_inspiracao") or []
    labels = []
    for ref in refs:
        if isinstance(ref, dict):
            label = ref.get("title") or ref.get("titulo") or ref.get("label")
        else:
            label = str(ref)
        if label:
            labels.append(str(label))
    suffix = f" Referências declaradas apenas como inspiração de mecanismos: {', '.join(labels)}." if labels else ""
    return (
        "\n=== ORIGINALITY & INEDITISM CONTRACT ===\n"
        "Crie expressão inteiramente nova: personagens, nomes distintivos, voz, diálogos, "
        "bordões, refrões, cenas, piadas, solução narrativa, composição visual e wording próprios. "
        "Referências externas podem informar SOMENTE princípios gerais (ex.: cumulatividade, humor, "
        "page-turn, profundidade emocional, HQ, musicalidade), nunca conteúdo copiável. "
        "Não imite autor, ilustrador, franquia, personagem, obra, editora ou identidade visual específica. "
        "Se uma referência estiver muito presente, aumente a distância criativa mudando premissa concreta, "
        "personagens, causalidade, sequência de acontecimentos, dispositivo cômico, refrão e resolução."
        + suffix + "\n"
    )


def evaluate_originality(state: dict, *, references: list[dict] | None = None) -> dict:
    """Executa gate determinístico sobre evidências disponíveis no projeto.

    `references` pode conter obras externas ou Masters internos. Para comparação
    textual, use `protected_text`/`text_excerpt`. Resumos de mecanismos não são
    comparados como texto protegido.
    """
    state = state or {}
    refs = references if references is not None else list(state.get("originality_references") or [])
    refs += list(state.get("originality_internal_references") or [])
    target = _story_text(state)
    title = str(state.get("titulo") or "")
    target_names = _character_names(state)
    findings: list[dict] = []

    # 1) Pedido explícito de imitação registrado no projeto/prompt livre.
    prompt_fields = " ".join(str(state.get(k) or "") for k in (
        "prompt_livre", "creative_brief", "briefing", "instrucoes_autora", "story_instructions"
    ))
    imitation_hits = [p for p in IMITATION_PATTERNS if re.search(p, _normalize(prompt_fields))]
    if imitation_hits:
        findings.append({
            "severity": "BLOCKER", "code": "IMITATION_REQUEST",
            "detail": "O briefing contém linguagem de imitação direta. Converta a referência em princípios gerais antes de gerar/publicar.",
            "evidence": {"pattern_count": len(imitation_hits)},
        })

    # 2) Comparação somente com evidência expressiva disponibilizada.
    for idx, ref in enumerate(refs, 1):
        if not isinstance(ref, dict):
            continue
        label = str(ref.get("title") or ref.get("titulo") or ref.get("label") or f"Referência {idx}")
        ref_title = str(ref.get("title") or ref.get("titulo") or "")
        excerpt = _protected_reference_text(ref)
        title_sim = _title_similarity(title, ref_title)
        shared = _shared_long_phrases(target, excerpt, 6) if excerpt else []

        if shared:
            findings.append({
                "severity": "BLOCKER", "code": "DISTINCTIVE_PHRASE_OVERLAP",
                "detail": f"Há sequência(s) textual(is) longa(s) coincidente(s) com {label}; exige reescrita/revisão antes de finalizar.",
                "evidence": {"reference": label, "shared_ngrams": shared[:6], "ngram_words": 6},
            })
        elif title_sim >= 0.88 and len(_words(title)) >= 3:
            findings.append({
                "severity": "REVIEW", "code": "TITLE_TOO_CLOSE",
                "detail": f"O título está muito próximo de {label}; revisar distintividade.",
                "evidence": {"reference": label, "similarity": round(title_sim, 3)},
            })

        ref_names = {_normalize(x) for x in (ref.get("character_names") or []) if _normalize(x)}
        shared_names = sorted(target_names & ref_names)
        if len(shared_names) >= 2:
            findings.append({
                "severity": "REVIEW", "code": "CHARACTER_CLUSTER_OVERLAP",
                "detail": f"Múltiplos nomes de personagens coincidem com {label}; confirmar que não há derivação indevida.",
                "evidence": {"reference": label, "names": shared_names},
            })

    # 3) Proveniência: referências de inspiração devem ser princípios-only.
    inspirations = state.get("inspiration_references") or state.get("referencias_inspiracao") or []
    for ref in inspirations:
        if isinstance(ref, dict) and ref.get("allowed_use") not in {None, "principles_only", "mechanisms_only"}:
            findings.append({
                "severity": "REVIEW", "code": "INSPIRATION_SCOPE_UNCLEAR",
                "detail": "Uma referência de inspiração não está marcada como principles_only/mechanisms_only.",
                "evidence": {"reference": ref.get("title") or ref.get("titulo") or "referência"},
            })

    blockers = [x for x in findings if x["severity"] == "BLOCKER"]
    reviews = [x for x in findings if x["severity"] == "REVIEW"]
    if blockers:
        status = "BLOCKED"
    elif reviews:
        status = "NEEDS_REVIEW"
    else:
        status = "PASS_INTERNAL"

    return {
        "schema": SCHEMA,
        "status": status,
        "findings": findings,
        "blockers": blockers,
        "review_items": reviews,
        "references_checked": len(refs),
        "policy": {
            "principles_not_expression": True,
            "direct_imitation_forbidden": True,
            "worldwide_novelty_certified": False,
            "legal_clearance_replaced": False,
            "human_review_recommended": True,
        },
        "notice": (
            "PASS_INTERNAL significa que os checks locais disponíveis não encontraram bloqueio. "
            "Não prova ineditismo mundial nem substitui busca externa/clearance jurídico quando necessário."
        ),
    }

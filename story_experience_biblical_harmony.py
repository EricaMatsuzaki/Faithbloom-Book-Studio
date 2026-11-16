"""FaithBloom Story Experience & Biblical Harmony Gate™.

Valida a experiência narrativa antes de liberar uma história/remasterização.
O gate não substitui o Heart Arc™ nem o Emotional Experience Engine™:
- Heart Arc = macrojornada;
- Emotional Experience Engine = vida emocional dentro da jornada;
- este gate = prova editorial de que história, moral e verdade bíblica estão em harmonia.

Princípios:
- encantar antes de ensinar;
- a criança vive a experiência antes de receber a conclusão;
- a lição de moral final é explícita e obrigatória;
- a Palavra de Deus no final é obrigatória, mas texto bíblico completo só pode
  sair de Bible Record aprovado/fornecido pela autora;
- fé acompanha a realidade e não promete que esforço, oração ou coragem
  garantem o resultado desejado;
- nem toda dor precisa desaparecer para existir transformação;
- humor e leveza podem coexistir com emoções difíceis quando apropriado;
- cada história deve possuir uma assinatura emocional própria, não uma sequência
  mecânica repetida em todos os livros.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Callable, Any

SCHEMA = "faithbloom.story-experience-biblical-harmony.v1"

REQUIRED_SEMANTIC_CHECKS = (
    "story_first_not_sermon",
    "experience_before_explanation",
    "emotional_journey_coherent",
    "transformation_earned",
    "moral_emerges_from_journey",
    "moral_explicit_at_end",
    "faith_natural_and_age_appropriate",
    "biblical_truth_harmonizes_with_journey",
    "no_false_guarantee_of_outcome",
    "no_artificial_erasure_of_difficult_emotion",
    "opening_does_not_spoil_core_discovery",
)

OPTIONAL_CONTEXT_CHECKS = (
    "humor_or_lightness_when_appropriate",
    "emotional_contrast_when_appropriate",
    "memorable_delight_or_wonder",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _scene_payload(state: dict) -> list[dict]:
    out = []
    for i, scene in enumerate(state.get("cenas_texto") or [], 1):
        if not isinstance(scene, dict):
            continue
        out.append({
            "numero": int(scene.get("numero") or i),
            "texto": _text(scene.get("texto")),
            "emocao": _text(scene.get("emocao")),
            "emocao_secundaria": _text(scene.get("emocao_secundaria")),
            "intensidade_emocional": scene.get("intensidade_emocional"),
            "transicao_emocional": _text(scene.get("transicao_emocional")),
        })
    return out


def bible_final_text_gate(state: dict) -> dict:
    """Exige Palavra de Deus no fechamento sem deixar IA inventar/traduzir Bíblia.

    PASS ocorre somente quando:
    - existe referência bíblica; e
    - existe Bible Record com texto bíblico aprovado pela autora; e
    - o Bible Record identifica claramente a versão e a fonte bíblica.

    O texto precisa vir de uma Bíblia/edição real (por exemplo, King James Version
    para inglês quando escolhida), nunca de paráfrase livre, memória do modelo ou
    tradução gerada pela IA. Texto legado extraído de livro publicado é apenas
    evidência para conferência e precisa ser reconciliado com um Bible Record
    aprovado antes do fechamento.
    """
    reference = _text(state.get("versiculo_referencia"))
    if not reference:
        return {
            "ok": False, "status": "MISSING_REFERENCE", "reference": "",
            "reason": "A história precisa terminar com referência bíblica."
        }

    records = state.get("bible_records") or {}
    for locale, record in records.items():
        if not isinstance(record, dict):
            continue
        text = _text(record.get("texto_aprovado"))
        if (
            record.get("status") == "approved_text"
            and text
            and bool(record.get("aprovado_pela_autora"))
            and _text(record.get("referencia") or reference) == reference
            and _text(record.get("versao"))
            and _text(record.get("fonte"))
        ):
            return {
                "ok": True,
                "status": "APPROVED_BIBLE_TEXT",
                "reference": reference,
                "locale": locale,
                "version": _text(record.get("versao")),
                "text_source": "bible_record",
            }

    return {
        "ok": False,
        "status": "TEXT_APPROVAL_REQUIRED",
        "reference": reference,
        "reason": (
            "A referência existe, mas o fechamento ainda não possui um Bible Record "
            "com texto bíblico, versão, fonte e aprovação. O FaithBloom não deve inventar, "
            "parafrasear nem traduzir livremente o versículo."
        ),
    }



def bible_closing_payload(state: dict) -> dict:
    """Retorna o fechamento bíblico publicável sem gerar texto novo."""
    gate = bible_final_text_gate(state)
    reference = _text(state.get("versiculo_referencia"))
    if not gate.get("ok"):
        return {
            "ok": False,
            "reference": reference,
            "text": "",
            "version": "",
            "source": gate.get("text_source", ""),
            "status": gate.get("status", ""),
            "reason": gate.get("reason", ""),
        }

    records = state.get("bible_records") or {}
    if gate.get("text_source") == "bible_record":
        locale = gate.get("locale")
        record = records.get(locale) if isinstance(records, dict) else {}
        record = record if isinstance(record, dict) else {}
        return {
            "ok": True,
            "reference": reference,
            "text": _text(record.get("texto_aprovado")),
            "version": _text(record.get("versao")),
            "source": "bible_record",
            "locale": locale,
            "status": gate.get("status"),
        }

    return {
        "ok": False,
        "reference": reference,
        "text": "",
        "version": "",
        "source": "",
        "status": "BIBLE_RECORD_REQUIRED",
        "reason": "O fechamento exige Bible Record aprovado com texto, versão e fonte bíblica.",
    }


def deterministic_story_experience_gate(state: dict) -> dict:
    scenes = _scene_payload(state)
    moral = _text(state.get("licao_final"))
    reference = _text(state.get("versiculo_referencia"))
    emotional_map = [x for x in (state.get("mapa_emocional") or []) if isinstance(x, dict)]
    heart_map = state.get("heart_arc_scene_map") or {}
    semantic = state.get("story_experience_biblical_harmony") or {}

    heart_stages = ("encantamento", "emoção", "experiência", "descoberta", "transformação", "fé")
    heart_complete = all(bool((heart_map or {}).get(stage)) for stage in heart_stages)
    emotions = {
        _text(scene.get("emocao")).casefold()
        for scene in scenes
        if _text(scene.get("emocao"))
    }
    # Diversidade emocional é evidência de ritmo, não quota. Histórias muito curtas
    # podem ter menos emoções; por isso o requisito mínimo é conservador.
    emotional_rhythm = len(emotions) >= 2 if len(scenes) >= 4 else bool(emotions)

    semantic_checks = semantic.get("checks") if isinstance(semantic, dict) else {}
    semantic_required_ok = bool(semantic.get("ok")) if semantic_checks else False

    bible_text = bible_final_text_gate(state)
    checks = {
        "story_present": {"ok": bool(scenes), "scene_count": len(scenes)},
        "heart_arc_mapped": {"ok": heart_complete, "heart_arc_scene_map": deepcopy(heart_map)},
        "emotional_map_ready": {
            "ok": bool(scenes) and len(emotional_map) == len(scenes),
            "scene_count": len(scenes), "map_count": len(emotional_map),
        },
        "emotional_rhythm_evidence": {
            "ok": emotional_rhythm,
            "distinct_primary_emotions": sorted(x for x in emotions if x),
        },
        "moral_explicit": {"ok": bool(moral), "value": moral},
        "bible_reference": {"ok": bool(reference), "value": reference},
        "bible_text_final": bible_text,
        "semantic_harmony_review": {
            "ok": semantic_required_ok,
            "schema": semantic.get("schema") if isinstance(semantic, dict) else "",
            "blockers": deepcopy(semantic.get("blockers") or []) if isinstance(semantic, dict) else [],
        },
    }
    failures = [name for name, result in checks.items() if not result.get("ok")]
    return {
        "schema": SCHEMA,
        "ok": not failures,
        "checks": checks,
        "failures": failures,
        "policy": (
            "História primeiro → experiência emocional → descoberta → transformação → "
            "lição de moral explícita → fé → Palavra de Deus aprovada."
        ),
    }


def review_story_experience_harmony(state: dict, chamar_llm: Callable) -> dict:
    """Auditoria semântica estruturada. Não reescreve a história."""
    scenes = _scene_payload(state)
    if not scenes:
        raise ValueError("Não há cenas narrativas para auditar.")

    system = """Você é o FaithBloom Story Experience & Biblical Harmony Guardian.
Faça AUDITORIA, não reescreva a história.

CORAÇÃO DO FAITHBLOOM:
- história infantil envolvente, leve, expressiva, emocionante, divertida e encantadora;
- variedade emocional nasce dos acontecimentos, não de rótulos aleatórios;
- a criança vive o conflito/experiência antes de receber explicações;
- Heart Arc: Encantamento → Emoção → Experiência → Descoberta → Transformação → Fé;
- a macrojornada não precisa ser solene nem linear: pode haver humor, ternura,
  surpresa, alegria, medo, ansiedade, frustração, perda, saudade, alívio e esperança;
- nem toda situação pode ser resolvida. Luto, saudade e outras perdas irreversíveis
  podem permanecer, com consolo, memória, amor, apoio e esperança em Deus;
- esforço, treino, persistência e oração NÃO garantem vitória externa. A história
  pode terminar com crescimento interior, contentamento por ter feito o melhor,
  resiliência e esperança;
- fé não apaga emoções difíceis e não deve ser usada como culpa ou promessa mágica;
- a Lição de Moral é obrigatória e explícita no final, mas deve ter sido construída
  organicamente pela experiência;
- a Palavra de Deus no final é obrigatória e deve estar em harmonia com toda a
  jornada moral/emocional; não invente nem traduza o texto bíblico;
- evite sermão durante a narrativa e evite revelar a descoberta central na abertura;
- humor/alívio é desejável quando combina com a experiência, sem ridicularizar dor;
- cada história deve ter sua própria assinatura emocional, sem fórmula mecânica.

Avalie somente o material fornecido. Se algo não puder ser provado, marque false.
Para humor/leveza, marque true quando estiver presente OU quando a ausência for
editorialmente apropriada ao tema delicado; explique no evidence.
"""

    payload = {
        "titulo": _text(state.get("titulo")),
        "faixa_etaria": _text(state.get("faixa_etaria") or "3-8"),
        "aprendizado_cristao": _text(state.get("aprendizado_cristao")),
        "licao_final": _text(state.get("licao_final")),
        "versiculo_referencia": _text(state.get("versiculo_referencia")),
        "heart_arc_scene_map": deepcopy(state.get("heart_arc_scene_map") or {}),
        "cenas": scenes,
    }
    instruction = (
        "Retorne JSON com: checks (objeto), blockers (lista), strengths (lista), "
        "recommendations (lista) e summary. checks deve conter exatamente estas chaves "
        "obrigatórias: " + ", ".join(REQUIRED_SEMANTIC_CHECKS) +
        "; e estas contextuais: " + ", ".join(OPTIONAL_CONTEXT_CHECKS) +
        ". Cada check deve ser objeto {ok:boolean,evidence:string,scenes:[inteiros]}. "
        "Não dê nota numérica. Não reescreva cenas. Dados: " + repr(payload)
    )
    raw = chamar_llm(sistema=system, instrucao=instruction)
    if not isinstance(raw, dict) or not isinstance(raw.get("checks"), dict):
        raise RuntimeError("Story Experience Guardian não retornou auditoria estruturada.")

    normalized = {}
    blockers = [str(x).strip() for x in (raw.get("blockers") or []) if str(x).strip()]
    for key in REQUIRED_SEMANTIC_CHECKS + OPTIONAL_CONTEXT_CHECKS:
        item = raw["checks"].get(key) if isinstance(raw["checks"], dict) else None
        item = item if isinstance(item, dict) else {}
        ok = item.get("ok") is True
        normalized[key] = {
            "ok": ok,
            "evidence": _text(item.get("evidence")),
            "scenes": [int(x) for x in (item.get("scenes") or []) if str(x).isdigit()],
        }
        if key in REQUIRED_SEMANTIC_CHECKS and not ok and key not in blockers:
            blockers.append(key)

    result = {
        "schema": SCHEMA,
        "ok": not blockers and all(normalized[k]["ok"] for k in REQUIRED_SEMANTIC_CHECKS),
        "checks": normalized,
        "blockers": blockers,
        "strengths": deepcopy(raw.get("strengths") or []),
        "recommendations": deepcopy(raw.get("recommendations") or []),
        "summary": _text(raw.get("summary")),
        "rewrote_story": False,
    }
    return result

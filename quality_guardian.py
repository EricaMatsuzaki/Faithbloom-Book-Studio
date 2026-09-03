"""FaithBloom Refinamento 10 — Quality Guardian.

Revisor final independente e orientado a evidências. O Guardian NÃO corrige
silenciosamente e NÃO inventa notas percentuais. Ele agrega checks objetivos
já existentes no FaithBloom, cria alertas rastreáveis e exige decisão da autora
para bloqueios antes de emitir um certificado INTERNO de quality gate.

O certificado interno não substitui KDP Previewer, prova física, EPUBCheck,
validação de plataforma, revisão jurídica/licenças ou revisão teológica humana.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re
import time
import uuid
from typing import Any

from armazenamento import _json, _save_json

SEVERITIES = {
    "bloqueante": {"rank": 4, "icon": "🔴", "label": "Bloqueante"},
    "recomendado": {"rank": 3, "icon": "🟠", "label": "Correção recomendada"},
    "atencao": {"rank": 2, "icon": "🟡", "label": "Atenção"},
    "sugestao": {"rank": 1, "icon": "🔵", "label": "Sugestão"},
    "info": {"rank": 0, "icon": "⚪", "label": "Informativo"},
}

DOMAIN_LABELS = {
    "editorial": "Editorial & continuidade",
    "readability": "Legibilidade por faixa etária",
    "bible": "Bible Guard & contexto cristão",
    "characters": "Character Guardian",
    "emotional": "Emoção & psicologia das cores",
    "translation": "Tradução & localização",
    "activities": "Activity QA",
    "audiobook": "Audiobook QA",
    "cover": "Capa & acabamento",
    "print": "Impressão & layout",
    "publishing": "Plataformas & distribuição",
    "cross_modal": "Consistência multimodal",
    "agent_skills": "Agent Skills & Handoffs",
    "market": "Market & Bestseller Readiness",
}

REPORT_INDEX = "quality_guardian/index.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _issue_id(domain: str, code: str, location: str, finding: str) -> str:
    raw = "|".join([domain, code, location, _norm_text(finding)]).encode("utf-8")
    return sha256(raw).hexdigest()[:16]


def issue(domain: str, severity: str, code: str, location: str, finding: str, why: str,
          suggestion: str = "", *, evidence: dict | None = None,
          before: str = "", after: str = "", requires_decision: bool = True) -> dict:
    sev = severity if severity in SEVERITIES else "atencao"
    return {
        "id": _issue_id(domain, code, location, finding),
        "domain": domain,
        "severity": sev,
        "code": code,
        "location": location or "Projeto",
        "finding": _norm_text(finding),
        "why": _norm_text(why),
        "suggestion": _norm_text(suggestion),
        "evidence": deepcopy(evidence or {}),
        "before": before or "",
        "after": after or "",
        "requires_decision": bool(requires_decision),
        "decision": None,
        "resolution_status": "open",
    }



def project_fingerprint(state: dict) -> str:
    auth = state.get("authorship") if isinstance(state.get("authorship"), dict) else {}
    def _credits(rows):
        return [
            {
                "profile_id": x.get("profile_id", ""),
                "role": x.get("role", ""),
                "order": int(x.get("order") or 0),
                "credit_as": x.get("credit_as") or x.get("display_name_snapshot") or "",
            }
            for x in (rows or []) if isinstance(x, dict)
        ]
    semantic_auth = {
        "authors": _credits(auth.get("authors")),
        "contributors": _credits(auth.get("contributors")),
        "cover_credit_override": auth.get("cover_credit_override") or "",
    }
    payload = {
        "titulo": state.get("titulo") or state.get("title"),
        "cenas_texto": state.get("cenas_texto") or [],
        "licao_final": state.get("licao_final"),
        "versiculo_referencia": state.get("versiculo_referencia"),
        "personagens": state.get("personagens") or {},
        "traducoes": state.get("traducoes") or {},
        "authorship": semantic_auth,
        "autora_legacy": "" if semantic_auth["authors"] else (state.get("autora") or ""),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return sha256(raw).hexdigest()


def _scene_rows(state: dict) -> list[dict]:
    rows = state.get("cenas_texto") or []
    out = []
    for i, row in enumerate(rows, 1):
        if isinstance(row, dict):
            out.append({**row, "numero": row.get("numero", i), "texto": str(row.get("texto") or "")})
        else:
            out.append({"numero": i, "texto": str(row)})
    return out


def _age_profile(state: dict) -> tuple[str, dict]:
    raw = str(state.get("faixa_etaria") or state.get("audience") or "3-8").lower().replace("–", "-")
    profiles = {
        "3-5": {"max_words_sentence": 14, "max_words_scene": 75, "label": "3–5"},
        "3-8": {"max_words_sentence": 18, "max_words_scene": 105, "label": "3–8"},
        "5-6": {"max_words_sentence": 17, "max_words_scene": 95, "label": "5–6"},
        "6-8": {"max_words_sentence": 20, "max_words_scene": 120, "label": "6–8"},
        "7-8": {"max_words_sentence": 22, "max_words_scene": 135, "label": "7–8"},
        "9-10": {"max_words_sentence": 26, "max_words_scene": 180, "label": "9–10"},
        "9-12": {"max_words_sentence": 30, "max_words_scene": 220, "label": "9–12"},
        "teen": {"max_words_sentence": 36, "max_words_scene": 320, "label": "Teen"},
        "adult": {"max_words_sentence": 45, "max_words_scene": 500, "label": "Adulto"},
    }
    key = next((k for k in profiles if k in raw), "3-8")
    return key, profiles[key]


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?…])\s+|\n+", text or "") if x.strip()]


def check_editorial(state: dict) -> list[dict]:
    items: list[dict] = []
    title = _norm_text(state.get("titulo"))
    scenes = _scene_rows(state)
    if not title:
        items.append(issue("editorial", "bloqueante", "missing_title", "Metadados", "Título do livro não está definido.", "Uma edição final precisa de título identificável.", "Defina e aprove o título antes da liberação."))
    if not scenes:
        items.append(issue("editorial", "bloqueante", "missing_story", "Miolo", "Não há cenas/texto narrativo para revisar.", "O Guardian não consegue validar continuidade sem conteúdo.", "Associe o Story/Book Master correto."))
        return items

    nums = [int(s.get("numero") or 0) for s in scenes]
    dup_nums = sorted({n for n in nums if n and nums.count(n) > 1})
    if dup_nums:
        items.append(issue("editorial", "recomendado", "duplicate_scene_numbers", "Estrutura", f"Números de cena repetidos: {dup_nums}.", "Numeração duplicada pode causar ordem incorreta na diagramação, tradução e áudio.", "Renumerar preservando a ordem narrativa.", evidence={"scene_numbers": dup_nums}))

    normalized = [_norm_text(s.get("texto")).casefold() for s in scenes]
    for i in range(1, len(normalized)):
        if normalized[i] and normalized[i] == normalized[i-1]:
            n1, n2 = scenes[i-1]["numero"], scenes[i]["numero"]
            items.append(issue("editorial", "recomendado", "adjacent_duplicate_text", f"Cenas {n1}–{n2}", "Duas cenas consecutivas possuem texto idêntico.", "Pode ser repetição editorial acidental; o Guardian sinaliza sem apagar nada.", "Comparar visualmente e decidir se a repetição é intencional ou deve ser revisada.", before=scenes[i]["texto"], evidence={"scene_a": n1, "scene_b": n2}))

    empty = [s["numero"] for s in scenes if not _norm_text(s.get("texto"))]
    if empty:
        items.append(issue("editorial", "bloqueante", "empty_scenes", "Miolo", f"Cenas sem texto: {empty}.", "Cenas vazias podem virar páginas incompletas ou quebrar traduções/áudio.", "Preencher ou remover conscientemente as cenas vazias.", evidence={"scenes": empty}))

    if state.get("revisao_aprovada") is not True:
        items.append(issue("editorial", "bloqueante", "author_editorial_approval", "Aprovação editorial", "A revisão editorial da obra ainda não está marcada como aprovada pela autora.", "O Quality Guardian é um gate posterior à aprovação editorial, não um substituto dela.", "Concluir a revisão da história e registrar aprovação explícita."))

    if not _norm_text(state.get("licao_final")):
        items.append(issue("editorial", "atencao", "missing_lesson", "Final", "Lição/moral final não está registrada.", "Para coleções com lição explícita isso pode deixar o fechamento inconsistente.", "Confirmar se a obra exige uma moral final e, se sim, aprová-la."))
    return items


def check_readability(state: dict) -> list[dict]:
    items: list[dict] = []
    scenes = _scene_rows(state)
    if not scenes:
        return items
    age_key, p = _age_profile(state)
    long_sentence_examples = []
    dense_scenes = []
    total_words = 0
    total_sentences = 0
    for s in scenes:
        words = re.findall(r"\b[\wÀ-ÿ'-]+\b", s["texto"], flags=re.UNICODE)
        total_words += len(words)
        sents = _sentences(s["texto"]) or ([s["texto"]] if s["texto"].strip() else [])
        total_sentences += len(sents)
        for sentence in sents:
            wc = len(re.findall(r"\b[\wÀ-ÿ'-]+\b", sentence, flags=re.UNICODE))
            if wc > p["max_words_sentence"]:
                long_sentence_examples.append({"scene": s["numero"], "words": wc, "text": sentence[:180]})
        if len(words) > p["max_words_scene"]:
            dense_scenes.append({"scene": s["numero"], "words": len(words)})

    if long_sentence_examples:
        items.append(issue("readability", "recomendado", "long_sentences", "Texto", f"Foram encontradas {len(long_sentence_examples)} frases acima do limiar heurístico para {p['label']}.", "Frases longas podem dificultar leitura em voz alta e compreensão; isto é um indicador editorial, não um teste com crianças reais.", "Revisar as frases sinalizadas e simplificar somente quando a musicalidade/clareza melhorar.", evidence={"profile": age_key, "examples": long_sentence_examples[:12], "method": "heuristic_not_child_test"}))
    if dense_scenes:
        items.append(issue("readability", "atencao", "dense_scenes", "Texto por cena", f"{len(dense_scenes)} cenas têm densidade de palavras acima do preset {p['label']}.", "Muito texto por página/cena pode competir com a ilustração e o ritmo infantil.", "Conferir diagramação e considerar divisão ou edição pontual.", evidence={"scenes": dense_scenes, "method": "heuristic_not_child_test"}))

    avg = round(total_words / max(1, total_sentences), 1)
    items.append(issue("readability", "info", "readability_method", "Metodologia", f"Proxy de legibilidade: {total_words} palavras, {total_sentences} frases, média {avg} palavras/frase; preset {p['label']}.", "O FaithBloom não apresenta isto como teste com crianças reais.", "Para lançamento importante, complementar com leitura humana/educacional apropriada.", evidence={"words": total_words, "sentences": total_sentences, "avg_words_sentence": avg, "profile": age_key}, requires_decision=False))
    return items


def check_bible(state: dict) -> list[dict]:
    items: list[dict] = []
    ref = _norm_text(state.get("versiculo_referencia"))
    records = state.get("bible_records") or {}
    translations = state.get("traducoes") or {}
    if any(isinstance(t, dict) and t.get("bible_ai_translation_allowed") is not False for t in translations.values()):
        items.append(issue("bible", "bloqueante", "bible_ai_guard", "Traduções", "Uma ou mais traduções não registram explicitamente o Bible Guard como ativo.", "Versículos bíblicos não podem ser traduzidos, completados ou inventados livremente pela IA.", "Reprocessar a edição pelo Translation Studio com Bible Guard ativo."))

    try:
        from translation_localization import validar_registro_biblico
        for locale, rec in records.items():
            errs = validar_registro_biblico(rec)
            if errs:
                items.append(issue("bible", "bloqueante", "invalid_bible_record", f"Bible record {locale}", "; ".join(errs), "Texto bíblico completo só pode seguir quando versão/fonte/aprovação exigidas estão registradas.", "Corrigir o registro bíblico; não pedir à IA que traduza o versículo.", evidence={"locale": locale}))
    except Exception:
        pass

    legacy = _norm_text(state.get("versiculo_texto_original") or state.get("versiculo_texto") or state.get("bible_verse_text"))
    if legacy:
        approved_texts = {_norm_text((r or {}).get("texto_aprovado")) for r in records.values() if isinstance(r, dict) and (r or {}).get("aprovado_pela_autora")}
        in_story = any(legacy and legacy in _norm_text(s.get("texto")) for s in _scene_rows(state))
        if in_story and legacy not in approved_texts:
            items.append(issue("bible", "bloqueante", "unapproved_scripture_in_story", "Texto da história", "Um texto bíblico legado aparece dentro das cenas sem registro aprovado correspondente.", "Esse conteúdo poderia ser traduzido/localizado indevidamente ou publicado sem controle de versão/fonte.", "Separar o versículo do texto narrativo e criar Bible Record aprovado; enquanto isso, usar apenas a referência."))

    if state.get("aprendizado_cristao") and not ref:
        items.append(issue("bible", "atencao", "missing_bible_reference", "Conteúdo cristão", "A obra tem aprendizado cristão, mas não há referência bíblica registrada.", "A coleção pode exigir uma âncora bíblica explícita.", "Confirmar se esta obra deve ter versículo/referência e registrar somente a referência adequada."))

    # Refinamento 21: sugestão de IA não equivale a referência/contexto validados.
    if state.get("aprendizado_cristao") and ref:
        try:
            from biblical_reference_validator import reference_gate
            rg = reference_gate(state)
            if not rg.get("ok"):
                items.append(issue(
                    "bible", "bloqueante", "biblical_reference_validation", "Referência bíblica",
                    rg.get("reason") or "Referência bíblica ainda não validada.",
                    "O Curador pode sugerir referências, mas a edição final precisa de fonte aprovada, contexto conferido e aprovação humana.",
                    "Validar a referência no Agent Skills & Bestseller Readiness. O FaithBloom não traduz nem fornece o texto do versículo nesta etapa.",
                    evidence={"reference": ref, "status": rg.get("status")},
                ))
        except Exception as exc:
            items.append(issue("bible", "atencao", "biblical_reference_validator_unavailable", "Referência bíblica", f"Validator indisponível: {type(exc).__name__}.", "Sem o validator, o Guardian não deve afirmar validação de contexto.", "Executar revisão humana/fonte aprovada antes do release."))

    specialist = (state.get("guardian_specialist_reviews") or {}).get("biblical") or {}
    if state.get("aprendizado_cristao") and not specialist.get("approved"):
        items.append(issue("bible", "atencao", "theological_context_review", "Contexto cristão", "A revisão de contexto bíblico/teológico independente ainda não foi registrada.", "Bible Guard protege o texto do versículo, mas não prova sozinho que a aplicação narrativa da referência está teologicamente adequada.", "Solicitar/revisar a análise de contexto e registrar a decisão da autora. O revisor não deve traduzir o versículo.", evidence={"reference": ref, "scope": "context_not_verse_translation"}))
    return items


def check_characters(state: dict) -> list[dict]:
    items: list[dict] = []
    chars = state.get("personagens") or {}
    images = state.get("cenas_imagem") or []
    if not chars:
        if images:
            items.append(issue("characters", "atencao", "no_character_registry", "Personagens", "Há ilustrações, mas nenhum personagem está vinculado ao Character Universe/DNA no estado atual.", "Sem referência oficial o Guardian não consegue sustentar uma análise de consistência de identidade.", "Vincular personagens recorrentes aos Masters oficiais antes do fechamento."))
        return items

    unlocked, unapproved, no_universe = [], [], []
    for name, c in chars.items():
        if not isinstance(c, dict):
            continue
        if c.get("dna_visual_travado") is False:
            unlocked.append(name)
        if c.get("aparencia_aprovada") is False:
            unapproved.append(name)
        if images and not c.get("character_universe_id"):
            no_universe.append(name)
    if unlocked:
        items.append(issue("characters", "recomendado", "character_dna_unlocked", "Character DNA", f"DNA visual não travado: {', '.join(unlocked)}.", "Mudanças posteriores podem alterar identidade entre páginas/edições.", "Revisar o Master e travar o DNA dos personagens oficiais.", evidence={"characters": unlocked}))
    if unapproved:
        items.append(issue("characters", "bloqueante", "character_not_approved", "Aprovação de personagens", f"Aparência ainda não aprovada: {', '.join(unapproved)}.", "O fluxo final exige aprovação explícita antes de tratar o personagem como oficial.", "Aprovar ou substituir a referência Master antes do release.", evidence={"characters": unapproved}))
    if no_universe:
        items.append(issue("characters", "atencao", "character_master_link", "Character Universe", f"Personagens sem vínculo oficial detectável: {', '.join(no_universe)}.", "A comparação de consistência fica limitada sem Character Master vinculado.", "Vincular ao Character Universe quando forem personagens recorrentes.", evidence={"characters": no_universe}))

    reports = state.get("character_consistency_reports") or []
    for r in reports if isinstance(reports, list) else []:
        if r.get("status") == "divergente":
            items.append(issue("characters", "recomendado", "character_divergence", str(r.get("location") or r.get("scene") or "Cena"), "Divergência de características estruturadas detectada em relação ao Character Master.", "A identidade oficial deve permanecer estável; roupa, pose e emoção são variáveis separadas.", "Comparar Antes × Depois no Restoration Studio e corrigir somente as características divergentes.", evidence=r))
    if images and not reports:
        items.append(issue("characters", "atencao", "visual_consistency_evidence_missing", "Ilustrações", "Não há relatório estruturado de comparação visual dos personagens anexado a este projeto.", "O Guardian não inventa percentuais de consistência sem evidência observável.", "Executar Character Consistency Auditor ou fazer comparação humana com os Masters oficiais.", requires_decision=False))
    return items


def check_emotional(state: dict) -> list[dict]:
    scenes = _scene_rows(state)
    if not scenes:
        return []
    items: list[dict] = []
    m = state.get("mapa_emocional") or []
    if not m:
        items.append(issue("emotional", "atencao", "emotional_map_missing", "Direção visual", "Mapa emocional/cromático não está registrado para esta obra.", "Sem o mapa, a progressão de emoção, luz e atmosfera fica mais difícil de revisar de forma consistente.", "Criar ou aprovar o mapa no Emotional & Color Director."))
    elif len(m) != len(scenes):
        items.append(issue("emotional", "recomendado", "emotional_scene_count", "Mapa emocional", f"Mapa emocional tem {len(m)} itens para {len(scenes)} cenas.", "Diferenças podem deslocar paletas/emoções para a cena errada.", "Alinhar o mapa emocional com a estrutura atual da história.", evidence={"map_items": len(m), "scenes": len(scenes)}))
    violations = state.get("emotion_color_violations") or []
    if violations:
        items.append(issue("emotional", "bloqueante", "identity_recolored", "Character × Color", f"Há {len(violations)} violações registradas em que direção emocional interfere em característica bloqueada do personagem.", "Emoção deve mudar luz/atmosfera/expressão, não olhos, pele, cabelo, pelagem ou marcas oficiais.", "Corrigir somente a direção visual da(s) cena(s), preservando Character DNA.", evidence={"violations": violations}))
    return items


def _map_translation_severity(level: str) -> str:
    x = str(level or "").casefold()
    if x in {"bloqueante", "blocker", "blocking", "erro"}: return "bloqueante"
    if x in {"recomendado", "warning", "review", "atencao", "atenção"}: return "recomendado" if x in {"warning", "review", "recomendado"} else "atencao"
    return "sugestao"


def check_translations(state: dict) -> list[dict]:
    translations = state.get("traducoes") or {}
    if not translations:
        return []
    items: list[dict] = []
    glossary = state.get("glossario_colecao") or {}
    bible_records = state.get("bible_records") or {}
    reviews = state.get("linguistic_reviews") or {}
    try:
        from translation_localization import revisar_localizacao_estrutural
        for locale, trans in translations.items():
            r = revisar_localizacao_estrutural(state, trans, bible_record=bible_records.get(locale), glossario=glossary)
            for a in r.get("alertas", []):
                items.append(issue("translation", _map_translation_severity(a.get("nivel")), str(a.get("codigo") or "translation_review"), f"Edição {locale}", str(a.get("mensagem") or "Revisar localização."), "A edição localizada deve preservar cenas, nomes protegidos, sentido e Bible Guard.", "Abrir Translation & Localization Studio e revisar somente o trecho afetado.", evidence={"locale": locale, "source": "structural_localization_review"}))
            lr = reviews.get(locale) or {}
            if not lr or not (lr.get("approved") or lr.get("ok")):
                items.append(issue("translation", "recomendado", "independent_linguistic_review", f"Edição {locale}", "Revisão linguística independente ainda não está registrada como aprovada.", "A tradução deve ser comparada com o Master para omissões, invenções, voz, idade e naturalidade de mercado.", "Executar o Revisor Linguístico Independente e registrar a decisão.", evidence={"locale": locale}))
    except Exception as exc:
        items.append(issue("translation", "atencao", "translation_check_unavailable", "Traduções", f"Não foi possível executar a revisão estrutural: {type(exc).__name__}.", "O Guardian não deve declarar uma tradução pronta sem conseguir executar o check.", "Abrir Translation Studio e revisar a edição manualmente."))
    return items


def check_activities(activity_project: dict | None) -> list[dict]:
    if not activity_project:
        return []
    items: list[dict] = []
    try:
        from activity_studio import project_readiness, qa_activity
        pages = activity_project.get("pages") or []
        for i, p in enumerate(pages, 1):
            qa = p.get("qa") or qa_activity(p)
            if qa.get("blockers", 0) > 0 or not qa.get("valid", True):
                items.append(issue("activities", "bloqueante", "activity_invalid", f"Atividade {i}", "A atividade possui erro estrutural/solução bloqueante.", "Labirintos, gabaritos, cruzadinhas, Sudoku e outras atividades verificáveis não podem ser publicados com solução inválida.", "Corrigir a estrutura e executar Activity QA novamente.", evidence={"page_id": p.get("id"), "alerts": qa.get("alerts", [])}))
            if p.get("status") != "approved":
                items.append(issue("activities", "bloqueante", "activity_author_approval", f"Atividade {i}", "Folha ainda não foi aprovada pela autora.", "Cada folha exige revisão visual/editorial mesmo quando o gabarito está tecnicamente correto.", "Visualizar, solicitar alteração se necessário e aprovar explicitamente."))
        r = project_readiness(activity_project)
        if not pages:
            items.append(issue("activities", "atencao", "activity_project_empty", "Activity Book", "Projeto de atividades não possui folhas.", "Não há conteúdo para validar.", "Adicionar atividades ou remover este módulo do escopo desta edição."))
        elif not r.get("ready"):
            # detalhes já aparecem por página; item informativo agregado
            items.append(issue("activities", "info", "activity_readiness_summary", "Activity Book", f"Prontidão: {r.get('approved_pages',0)}/{r.get('total_pages',0)} aprovadas; {r.get('qa_blocked_pages',0)} com bloqueio de QA.", "Resumo agregado do Activity Studio.", "Resolver os itens por página.", evidence=r, requires_decision=False))
    except Exception as exc:
        items.append(issue("activities", "bloqueante", "activity_qa_unavailable", "Activity Book", f"Activity QA indisponível: {type(exc).__name__}.", "A liberação final não deve ignorar validação de gabaritos/soluções.", "Reabrir o Activity Studio e executar o QA."))
    return items


def check_audiobook(audiobook_project: dict | None) -> list[dict]:
    if not audiobook_project:
        return []
    items: list[dict] = []
    try:
        from audiobook_studio import distribution_readiness
        r = distribution_readiness(audiobook_project)
        for a in r.get("alerts", []):
            sev = "bloqueante" if a.get("severity") in {"blocking", "blocker"} else "recomendado"
            items.append(issue("audiobook", sev, str(a.get("code") or "audio_review"), "Audiobook", str(a.get("message") or "Revisar audiobook."), "O Master de áudio precisa de integridade técnica e aprovação por escuta.", "Abrir Audiobook Studio, corrigir/regenerar somente o segmento necessário e reexecutar QA.", evidence=a))
        if not (audiobook_project.get("final_author_approval") or {}).get("approved"):
            items.append(issue("audiobook", "bloqueante", "final_listening_approval", "Mix final", "Aprovação humana por escuta do mix final não está registrada.", "Metadados técnicos não avaliam emoção, pronúncia e interpretação.", "Escutar o Master completo e registrar aprovação explícita."))
        if r.get("ready"):
            items.append(issue("audiobook", "info", "audio_ready", "Audiobook", "Audiobook passou pelos checks técnicos do Studio e possui aprovação final registrada.", "Isto não certifica requisitos de uma distribuidora externa específica.", "Validar também o perfil da plataforma de audiobook escolhida.", evidence=r, requires_decision=False))
    except Exception as exc:
        items.append(issue("audiobook", "bloqueante", "audio_qa_unavailable", "Audiobook", f"QA de audiobook indisponível: {type(exc).__name__}.", "Não é seguro liberar áudio sem conseguir verificar o pipeline.", "Reabrir Audiobook Studio e executar QA."))
    return items


def check_cover(state: dict) -> list[dict]:
    items: list[dict] = []
    physical = bool(state.get("capa_fisica_pdf") or state.get("capa_fisica_wrap") or state.get("capa_fisica_dimensoes") or state.get("pacote_pronto"))
    ebook = bool(state.get("capa_ebook"))
    if not physical and not ebook:
        return items
    if physical:
        if not state.get("capa_fisica_pdf") and not state.get("capa_fisica_wrap"):
            items.append(issue("cover", "bloqueante", "missing_physical_cover", "Capa física", "Arquivo final de capa/wrap físico não está associado.", "A edição impressa exige frente, lombada quando aplicável e contracapa no envelope técnico correto.", "Gerar/associar o wrap final pelo Cover Master."))
        pf = state.get("capa_fisica_preflight") or {}
        if pf and pf.get("ok") is False:
            items.append(issue("cover", "bloqueante", "cover_preflight_failed", "Capa física", "Preflight técnico da capa está reprovado.", "Dimensões ou estrutura incorretas podem causar rejeição/corte na plataforma.", "Corrigir a capa e executar o preflight novamente.", evidence=pf))
        elif not pf:
            items.append(issue("cover", "recomendado", "cover_preflight_missing", "Capa física", "Não há preflight técnico da capa anexado ao estado atual.", "O Guardian não deve assumir dimensões corretas apenas pela aparência.", "Executar Cover/Platform preflight."))
    return items


def check_print(state: dict) -> list[dict]:
    items: list[dict] = []
    pf = state.get("preflight_impressao") or {}
    pdf = state.get("pdf_miolo_print_ready") or ""
    if not pf and not pdf and not state.get("pacote_pronto"):
        return items
    if pf:
        ready = pf.get("pronto_para_publicar")
        blockers = pf.get("bloqueios") or pf.get("blockers") or []
        if blockers:
            items.append(issue("print", "bloqueante", "print_blockers", "Miolo", f"Preflight de impressão possui {len(blockers)} bloqueio(s).", "Problemas de PPI, bleed, margens ou geometria podem comprometer impressão.", "Resolver os bloqueios no módulo de Qualidade de Impressão.", evidence={"blockers": blockers}))
        if ready is False:
            items.append(issue("print", "atencao", "external_print_proof_required", "Prova final", "O próprio preflight não marca o livro como definitivamente pronto para publicar.", "O FaithBloom separa validação interna de Previewer/prova humana da plataforma.", "Abrir o arquivo final no previewer oficial e, para impressão, considerar prova física.", evidence={"preflight_ready_flag": ready}))
    else:
        items.append(issue("print", "recomendado", "print_preflight_missing", "Miolo", "PDF/edição de publicação existe, mas o preflight de impressão não está anexado.", "Sem medidas/PPI/bleed validados, o Guardian não pode sustentar readiness técnico.", "Executar preflight do miolo."))
    if not pdf and state.get("pacote_pronto"):
        items.append(issue("print", "bloqueante", "missing_print_ready_pdf", "Miolo", "Pacote está marcado como pronto, mas não há PDF Print Ready associado.", "Status e artefatos estão inconsistentes.", "Gerar/associar o PDF final antes da liberação."))
    return items


def check_publishing(state: dict, publishing_preflights: list[dict] | None = None) -> list[dict]:
    rows = publishing_preflights if publishing_preflights is not None else (state.get("publishing_preflights") or [])
    if not rows:
        return []
    items: list[dict] = []
    for r in rows:
        name = r.get("platform_name") or r.get("platform_id") or "Plataforma"
        for a in r.get("alerts", []):
            s = a.get("severity")
            sev = "bloqueante" if s in {"blocker", "blocking"} else ("recomendado" if s in {"warning", "review"} else "sugestao")
            items.append(issue("publishing", sev, str(a.get("code") or "platform_alert"), name, str(a.get("message") or "Revisar regra da plataforma."), "Cada destino tem requisitos próprios; o FaithBloom não deve reutilizar arquivos incompatíveis silenciosamente.", "Corrigir a edição derivada ou atualizar a especificação oficial da plataforma.", evidence={"spec_version": r.get("spec_version"), "last_verified": r.get("last_verified")}))
        if r.get("ready") is False and not r.get("alerts"):
            items.append(issue("publishing", "bloqueante", "platform_not_ready", name, "Preflight de plataforma não está pronto.", "A edição não deve ser exportada para este destino até que o gate passe.", "Executar novamente o Platform Engine com os assets finais."))
    return items


def check_cross_modal(state: dict, audiobook_project: dict | None = None) -> list[dict]:
    items: list[dict] = []
    scenes = _scene_rows(state)
    imgs = state.get("cenas_imagem") or []
    if scenes and imgs:
        scene_nums = {int(s.get("numero") or 0) for s in scenes}
        image_nums = {int(i.get("numero") or i.get("cena_numero") or 0) for i in imgs if isinstance(i, dict)}
        missing = sorted(n for n in scene_nums if n and n not in image_nums)
        extra = sorted(n for n in image_nums if n and n not in scene_nums)
        if missing:
            items.append(issue("cross_modal", "recomendado", "missing_scene_images", "Texto × imagem", f"Cenas sem ilustração correspondente detectável: {missing}.", "A relação texto-imagem pode ficar incompleta ou deslocada.", "Confirmar se são páginas propositalmente sem arte; caso contrário, gerar/associar a ilustração correta.", evidence={"missing": missing}))
        if extra:
            items.append(issue("cross_modal", "atencao", "extra_scene_images", "Texto × imagem", f"Ilustrações sem cena textual correspondente: {extra}.", "Pode ser material extra, capa ou versão antiga; precisa de decisão para não entrar por engano no miolo.", "Classificar/retirar da sequência final ou vincular à cena correta.", evidence={"extra": extra}))
        approved = set(int(x) for x in (state.get("cenas_imagem_aprovadas") or []) if str(x).isdigit())
        pending = sorted(n for n in scene_nums if n and n in image_nums and n not in approved)
        if pending:
            items.append(issue("cross_modal", "bloqueante", "scene_images_not_approved", "Aprovação visual", f"Ilustrações ainda não aprovadas explicitamente: {pending}.", "O Quality Guardian não pode substituir a aprovação visual da autora.", "Revisar e aprovar as imagens finais no editor/galeria.", evidence={"scenes": pending}))
    elif scenes and not imgs and state.get("tipo_projeto", "story") == "story":
        items.append(issue("cross_modal", "atencao", "no_scene_images", "Texto × imagem", "A obra possui história, mas nenhuma lista de ilustrações está associada ao estado atual.", "Para um livro ilustrado, o Guardian não consegue verificar completude visual.", "Associe a edição/estado que contém as ilustrações finais."))

    if audiobook_project and scenes:
        source_scenes = [x for x in (audiobook_project.get("source") or {}).get("scenes", []) if x.get("scene_type") == "story"]
        if source_scenes and len(source_scenes) != len(scenes):
            items.append(issue("cross_modal", "bloqueante", "audio_story_count", "Texto × audiobook", f"Audiobook possui {len(source_scenes)} cenas narrativas para {len(scenes)} cenas no Master.", "O audiobook pode estar baseado em uma versão anterior da história.", "Reconstruir a fonte do Audiobook Studio a partir da versão aprovada atual."))
    items.append(issue("cross_modal", "info", "semantic_visual_review_limit", "Texto × imagem", "Correspondência semântica fina (objeto, roupa, expressão e ação exatos) requer evidência visual ou revisão especializada; ela não é inferida por contagem de arquivos.", "O Guardian evita declarar consistência visual sem análise sustentada.", "Usar Character/Restoration review e inspeção humana para as cenas críticas.", requires_decision=False))
    return items


def _domain_status(domain: str, issues: list[dict], applicable: bool = True) -> str:
    if not applicable:
        return "not_applicable"
    own = [x for x in issues if x.get("domain") == domain]
    unresolved = [x for x in own if x.get("resolution_status") != "resolved"]
    if any(x["severity"] == "bloqueante" for x in unresolved): return "blocked"
    if any(x["severity"] in {"recomendado", "atencao"} for x in unresolved): return "review"
    return "pass"


def check_agent_skills(state: dict) -> list[dict]:
    items: list[dict] = []
    try:
        from agent_skills import validate_registry
        audit = validate_registry()
        if not audit.get("ok"):
            items.append(issue("agent_skills", "bloqueante", "skill_registry_invalid", "Agent Skills Registry", "O registry formal de skills possui inconsistências.", "Agentes sem skill contract completo podem produzir resultados sem critérios/handoffs auditáveis.", "Corrigir o registry antes do release.", evidence=audit))
        else:
            items.append(issue("agent_skills", "info", "skill_registry_ok", "Agent Skills Registry", f"{audit.get('role_count',0)} papéis especializados possuem skill profiles formais.", "O registry documenta skills, critérios, limites e handoffs; ele não garante desempenho comercial por si só.", "Revalidar o registry sempre que um agente novo for adicionado.", evidence=audit, requires_decision=False))
    except Exception as exc:
        items.append(issue("agent_skills", "bloqueante", "skill_registry_unavailable", "Agent Skills Registry", f"Registry indisponível: {type(exc).__name__}.", "A camada de competências não pode ser auditada.", "Restaurar agent_skills.py e executar os testes do Refinamento 21."))
    return items


def check_market_readiness(state: dict) -> list[dict]:
    items: list[dict] = []
    try:
        from market_intelligence import classify_market_mode
        mode = classify_market_mode(state.get("market_evidence") or [])
        if not mode.get("can_make_observed_market_claims"):
            items.append(issue(
                "market", "atencao", "market_evidence_missing", "Posicionamento comercial",
                "Não há evidência observada válida de mercado anexada; sugestões de keywords/categorias são inferência de IA.",
                "Inferência pode ajudar a criar hipóteses, mas não sustenta afirmações de demanda, competição ou tendência atual.",
                "Adicionar pesquisa observada com fonte, data e mercado quando quiser validar posicionamento comercial.",
                evidence=mode,
            ))
        provenance = state.get("market_suggestions_provenance") or {}
        if provenance and provenance.get("mode") == "model_inference_only":
            items.append(issue("market", "info", "market_provenance_inference", "Keywords/Categorias", "Sugestões comerciais estão corretamente rotuladas como model_inference_only.", "Isso impede que hipóteses sejam apresentadas como dados observados.", "Validar com evidência externa antes de fazer alegações quantitativas.", evidence=provenance, requires_decision=False))
    except Exception as exc:
        items.append(issue("market", "atencao", "market_intelligence_unavailable", "Mercado", f"Market Intelligence indisponível: {type(exc).__name__}.", "O Guardian não deve inventar dados comerciais para preencher a lacuna.", "Revisar o módulo Market Intelligence."))
    return items


def _preserve_decisions(new_issues: list[dict], previous_report: dict | None) -> None:
    old = {x.get("id"): x for x in (previous_report or {}).get("issues", [])}
    for x in new_issues:
        prev = old.get(x["id"])
        if prev and prev.get("decision"):
            x["decision"] = deepcopy(prev.get("decision"))
            # Uma decisão "resolvido" precisa ser revalidada: se o problema ainda
            # existe no rerun, ele volta a open; manter/aceitar continua registrado.
            if prev.get("decision", {}).get("action") in {"manter_com_justificativa", "nao_se_aplica"} and x["severity"] != "bloqueante":
                x["resolution_status"] = "resolved"


def run_quality_guardian(state: dict, *, activity_project: dict | None = None,
                         audiobook_project: dict | None = None,
                         publishing_preflights: list[dict] | None = None,
                         previous_report: dict | None = None,
                         project_type: str = "story") -> dict:
    """Executa o Guardian sem chamadas externas e sem aplicar correções.

    Cada issue inclui onde/o quê/por quê/sugestão e espaço para decisão da autora.
    Reruns preservam decisões não bloqueantes quando o mesmo issue persiste, mas
    um bloqueio persistente nunca é considerado resolvido apenas por override.
    """
    state = deepcopy(state or {})
    fingerprint = project_fingerprint(state)
    previous_specialists = deepcopy((previous_report or {}).get("specialist_reviews") or {})
    if (previous_report or {}).get("project_fingerprint") == fingerprint:
        biblical = previous_specialists.get("biblical_context") or {}
        if biblical.get("approved"):
            state.setdefault("guardian_specialist_reviews", {})["biblical"] = {"approved": True, "reviewed_at": biblical.get("reviewed_at"), "source": "independent_reviewer_same_fingerprint"}
    issues: list[dict] = []
    issues += check_editorial(state) if project_type == "story" else []
    issues += check_readability(state) if project_type == "story" else []
    issues += check_bible(state)
    issues += check_characters(state)
    issues += check_emotional(state) if project_type == "story" else []
    issues += check_translations(state)
    issues += check_activities(activity_project)
    issues += check_audiobook(audiobook_project)
    issues += check_cover(state)
    issues += check_print(state)
    issues += check_publishing(state, publishing_preflights)
    issues += check_cross_modal(state, audiobook_project) if project_type == "story" else []
    issues += check_agent_skills(state)
    issues += check_market_readiness(state)
    _preserve_decisions(issues, previous_report)

    applicability = {
        "editorial": project_type == "story",
        "readability": project_type == "story",
        "bible": bool(state.get("aprendizado_cristao") or state.get("versiculo_referencia") or state.get("bible_records")),
        "characters": bool(state.get("personagens") or state.get("cenas_imagem")),
        "emotional": project_type == "story",
        "translation": bool(state.get("traducoes")),
        "activities": bool(activity_project),
        "audiobook": bool(audiobook_project),
        "cover": bool(state.get("capa_ebook") or state.get("capa_fisica_pdf") or state.get("capa_fisica_wrap") or state.get("pacote_pronto")),
        "print": bool(state.get("preflight_impressao") or state.get("pdf_miolo_print_ready") or state.get("pacote_pronto")),
        "publishing": bool(publishing_preflights if publishing_preflights is not None else state.get("publishing_preflights")),
        "cross_modal": project_type == "story",
        "agent_skills": True,
        "market": bool(state.get("palavras_chave_kdp") or state.get("categorias_sugeridas") or state.get("market_evidence")),
    }
    domains = {d: {"label": DOMAIN_LABELS[d], "applicable": applicability[d], "status": _domain_status(d, issues, applicability[d])} for d in DOMAIN_LABELS}
    counts = {s: sum(1 for x in issues if x["severity"] == s and x.get("resolution_status") != "resolved") for s in SEVERITIES}
    open_blockers = [x for x in issues if x["severity"] == "bloqueante" and x.get("resolution_status") != "resolved"]
    rid = (previous_report or {}).get("id") or uuid.uuid4().hex
    report = {
        "id": rid,
        "project_title": state.get("titulo") or state.get("title") or "Projeto sem título",
        "project_type": project_type,
        "project_fingerprint": fingerprint,
        "created_at": (previous_report or {}).get("created_at") or _now_iso(),
        "updated_at": _now_iso(),
        "run_number": int((previous_report or {}).get("run_number") or 0) + 1,
        "policy": {
            "no_silent_corrections": True,
            "no_invented_quality_scores": True,
            "bible_ai_translation_allowed": False,
            "author_final_decision_required": True,
            "internal_certificate_only": True,
        },
        "domains": domains,
        "issues": issues,
        "summary": {
            "counts": counts,
            "open_blockers": len(open_blockers),
            "open_decisions": sum(1 for x in issues if x.get("requires_decision") and x.get("resolution_status") != "resolved"),
            "ready_for_author_signoff": len(open_blockers) == 0 and not any(x.get("requires_decision") and x.get("resolution_status") != "resolved" for x in issues),
            "applicable_domains": sum(1 for x in applicability.values() if x),
        },
        "author_final_approval": deepcopy((previous_report or {}).get("author_final_approval")) if (previous_report or {}).get("project_fingerprint") == fingerprint else None,
        "specialist_reviews": previous_specialists if (previous_report or {}).get("project_fingerprint") == fingerprint else {},
        "certificate": None,
    }
    # Certificado antigo é invalidado por qualquer rerun, pois o conteúdo/checks podem ter mudado.
    return report


def record_issue_decision(report: dict, issue_id: str, action: str, note: str = "", decided_by: str = "autora") -> dict:
    allowed = {"corrigir", "resolvido", "manter_com_justificativa", "nao_se_aplica"}
    if action not in allowed:
        raise ValueError("Decisão inválida.")
    out = deepcopy(report)
    target = next((x for x in out.get("issues", []) if x.get("id") == issue_id), None)
    if not target:
        raise KeyError(issue_id)
    if target.get("severity") == "bloqueante" and action in {"manter_com_justificativa", "nao_se_aplica"}:
        # A autora pode registrar a decisão, mas o bloqueio permanece até um rerun
        # provar que o problema deixou de existir.
        resolution = "open"
    elif action in {"manter_com_justificativa", "nao_se_aplica"}:
        resolution = "resolved"
    elif action == "resolvido":
        resolution = "pending_recheck"
    else:
        resolution = "open"
    target["decision"] = {"action": action, "note": note.strip(), "decided_by": decided_by, "decided_at": _now_iso()}
    target["resolution_status"] = resolution
    blockers = [x for x in out.get("issues", []) if x.get("severity") == "bloqueante" and x.get("resolution_status") != "resolved"]
    out.setdefault("summary", {})["open_blockers"] = len(blockers)
    out["summary"]["open_decisions"] = sum(1 for x in out.get("issues", []) if x.get("requires_decision") and x.get("resolution_status") != "resolved")
    out["summary"]["ready_for_author_signoff"] = len(blockers) == 0 and out["summary"]["open_decisions"] == 0
    out["updated_at"] = _now_iso()
    return out


def register_author_final_approval(report: dict, approved: bool, note: str = "", approved_by: str = "autora") -> dict:
    out = deepcopy(report)
    blockers = [x for x in out.get("issues", []) if x.get("severity") == "bloqueante" and x.get("resolution_status") != "resolved"]
    open_decisions = [x for x in out.get("issues", []) if x.get("requires_decision") and x.get("resolution_status") != "resolved"]
    if approved and blockers:
        raise ValueError("Existem bloqueios abertos. Corrija e rode o Quality Guardian novamente antes da aprovação final.")
    if approved and open_decisions:
        raise ValueError("Ainda existem alertas que exigem decisão da autora. Resolva, justifique ou marque como não aplicável antes da aprovação final.")
    out["author_final_approval"] = {"approved": bool(approved), "note": note.strip(), "approved_by": approved_by, "approved_at": _now_iso()}
    out["updated_at"] = _now_iso()
    return out


def issue_internal_certificate(report: dict) -> dict:
    out = deepcopy(report)
    blockers = [x for x in out.get("issues", []) if x.get("severity") == "bloqueante" and x.get("resolution_status") != "resolved"]
    open_decisions = [x for x in out.get("issues", []) if x.get("requires_decision") and x.get("resolution_status") != "resolved"]
    if blockers:
        raise ValueError("Há bloqueios abertos; certificado interno não pode ser emitido.")
    if open_decisions:
        raise ValueError("Ainda existem alertas sem decisão final da autora.")
    if not (out.get("author_final_approval") or {}).get("approved"):
        raise ValueError("A aprovação final da autora é obrigatória.")
    cert = {
        "certificate_id": "FB-QG-" + uuid.uuid4().hex[:12].upper(),
        "report_id": out.get("id"),
        "project_title": out.get("project_title"),
        "issued_at": _now_iso(),
        "run_number": out.get("run_number"),
        "status": "INTERNAL_QUALITY_GATE_PASSED",
        "remaining_non_blocking": sum(1 for x in out.get("issues", []) if x.get("severity") != "bloqueante" and x.get("resolution_status") != "resolved" and x.get("requires_decision")),
        "disclaimer": "Certificado interno FaithBloom. Não é certificação da Amazon KDP nem de outra plataforma e não substitui previewer oficial, EPUBCheck quando aplicável, prova física, validação jurídica/licenças ou revisão humana especializada.",
    }
    out["certificate"] = cert
    out["updated_at"] = _now_iso()
    return out


def build_specialist_review_prompt(state: dict, focus: str = "editorial", locale: str = "") -> tuple[str, str]:
    """Prompt de segunda opinião independente. Não aplica mudanças automaticamente."""
    allowed = {"editorial", "child_readability", "biblical_context", "cross_modal"}
    if focus not in allowed:
        raise ValueError("Foco de revisão não suportado.")
    safe = deepcopy(state or {})
    for key in ("versiculo_texto", "versiculo_texto_original", "bible_verse_text"):
        safe.pop(key, None)
    # Bible records seguem sem o texto, preservando referência/versão/metadados.
    safe_records = {}
    for loc, rec in (safe.get("bible_records") or {}).items():
        if isinstance(rec, dict):
            safe_records[loc] = {k: v for k, v in rec.items() if k not in {"texto_aprovado", "text", "scripture_text"}}
    safe["bible_records"] = safe_records
    payload = {
        "titulo": safe.get("titulo"), "colecao": safe.get("colecao"), "faixa_etaria": safe.get("faixa_etaria", "3–8"),
        "aprendizado_cristao": safe.get("aprendizado_cristao"), "versiculo_referencia": safe.get("versiculo_referencia"),
        "cenas_texto": safe.get("cenas_texto", []), "licao_final": safe.get("licao_final"), "locale": locale,
        "personagens": list((safe.get("personagens") or {}).keys()),
    }
    system = f"""Você é um REVISOR INDEPENDENTE do FaithBloom, separado do agente que criou o conteúdo.
Foco: {focus}. Avalie criticamente, sem elogios genéricos e sem modificar o projeto.
Retorne somente JSON: {{"issues":[{{"severity":"bloqueante|recomendado|atencao|sugestao","location":"...","finding":"...","why":"...","suggestion":"..."}}],"review_notes":"..."}}.
Nunca invente percentuais de qualidade. Não diga que realizou teste com crianças reais.
BIBLE GUARD: você pode avaliar a COERÊNCIA DO CONTEXTO entre a história e a referência bíblica fornecida, mas NÃO deve citar, completar, traduzir ou parafrasear o texto do versículo. Se precisar do texto exato, peça revisão humana/fonte aprovada.
Nenhuma sugestão será aplicada automaticamente; a autora decide.
"""
    return system, json.dumps(payload, ensure_ascii=False)


def normalize_specialist_review(result: Any, focus: str) -> dict:
    if isinstance(result, list):
        result = {"issues": result}
    if not isinstance(result, dict):
        return {"focus": focus, "issues": [], "review_notes": "Resposta do revisor em formato inválido.", "approved": False}
    out = []
    for raw in result.get("issues", []) if isinstance(result.get("issues"), list) else []:
        if not isinstance(raw, dict):
            continue
        sev = raw.get("severity") if raw.get("severity") in SEVERITIES else "atencao"
        # remove campos que poderiam tentar inserir texto bíblico gerado
        safe = {k: v for k, v in raw.items() if str(k).lower() not in {"scripture_text", "versiculo_texto", "bible_text", "texto_biblico"}}
        out.append(issue("bible" if focus == "biblical_context" else ("readability" if focus == "child_readability" else ("cross_modal" if focus == "cross_modal" else "editorial")), sev, f"specialist_{focus}", str(safe.get("location") or "Revisão especializada"), str(safe.get("finding") or "Revisão necessária."), str(safe.get("why") or "Segunda opinião independente."), str(safe.get("suggestion") or "Revisar com a autora."), evidence={"source": "independent_ai_reviewer", "focus": focus}))
    return {"focus": focus, "issues": out, "review_notes": _norm_text(result.get("review_notes")), "approved": True, "reviewed_at": _now_iso()}


def merge_specialist_review(report: dict, specialist_review: dict) -> dict:
    out = deepcopy(report)
    specialist_review = deepcopy(specialist_review)
    specialist_review["project_fingerprint"] = out.get("project_fingerprint")
    existing = {x.get("id") for x in out.get("issues", [])}
    for x in specialist_review.get("issues", []):
        if x.get("id") not in existing:
            out.setdefault("issues", []).append(deepcopy(x)); existing.add(x.get("id"))
    out.setdefault("specialist_reviews", {})[specialist_review.get("focus", "review")] = deepcopy(specialist_review)
    blockers = [x for x in out.get("issues", []) if x.get("severity") == "bloqueante" and x.get("resolution_status") != "resolved"]
    out.setdefault("summary", {})["open_blockers"] = len(blockers)
    out["summary"]["open_decisions"] = sum(1 for x in out.get("issues", []) if x.get("requires_decision") and x.get("resolution_status") != "resolved")
    out["summary"]["ready_for_author_signoff"] = len(blockers) == 0 and out["summary"]["open_decisions"] == 0
    out["updated_at"] = _now_iso()
    return out


def save_guardian_report(report: dict) -> dict:
    out = deepcopy(report)
    rid = out.get("id") or uuid.uuid4().hex
    out["id"] = rid; out["updated_at"] = _now_iso()
    _save_json(f"quality_guardian/reports/{rid}.json", out)
    idx = _json(REPORT_INDEX, []) or []
    item = {"id": rid, "project_title": out.get("project_title", ""), "project_type": out.get("project_type", ""), "run_number": out.get("run_number", 0), "open_blockers": (out.get("summary") or {}).get("open_blockers", 0), "updated_at": out.get("updated_at")}
    idx = [x for x in idx if x.get("id") != rid] + [item]
    _save_json(REPORT_INDEX, idx[-200:])
    return out


def load_guardian_report(report_id: str) -> dict:
    return _json(f"quality_guardian/reports/{report_id}.json", {}) or {}


def list_guardian_reports() -> list[dict]:
    rows = _json(REPORT_INDEX, []) or []
    return sorted(rows, key=lambda x: x.get("updated_at", ""), reverse=True)


def export_guardian_report_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)

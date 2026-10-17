"""Author-reviewed, exact-source emotional direction for the visual pipeline.

The canonical FaithBloom palette is editorial guidance, not a universal clinical
claim. Bindings contain scene digests and direction, never another raw account.
Legacy plans remain readable; no final provider call inherits an old approval.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re
import time

from emotional_color_director import construir_mapa_emocional, prompt_direcao_visual

SCHEMA = "faithbloom.emotional-visual-binding.v1"
IDENTITY_RULE = (
    "Preservar Character/World/Style Masters e referências originais. Manter cor, forma, "
    "brilho, reflexos, estrelas e detalhes canônicos dos olhos, pele, pelagem e cabelo. "
    "A emoção altera atmosfera, luz e expressão permitida, nunca a identidade nem "
    "a geometria/geografia do World Master; não recolorir o Master canônico. "
    "A fidelidade da imagem exige revisão visual humana; este contrato não é validação de pixels."
)


def fingerprint(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def source_for_plan(plan):
    reference = str(plan.get("source_ref") or "")
    if reference:
        import storage_backend as storage
        canonical = reference if storage.is_storage_uri(reference) else storage.storage_uri(reference)
        source = storage.BACKEND.get_json(storage.uri_to_path(canonical), None)
        if not isinstance(source, dict):
            raise PermissionError("Recupere a origem salva antes de revisar a direção emocional.")
        expected_id = plan.get("source_book_id")
        actual_id = source.get("book_id") or source.get("project_id") or source.get("id")
        if expected_id and actual_id != expected_id:
            raise PermissionError("A identidade da obra da direção emocional não corresponde à origem salva.")
        if plan.get("source_fingerprint"):
            from editorial_dispatch import content_fingerprint
            if content_fingerprint(source) != plan["source_fingerprint"]:
                raise PermissionError("A origem mudou. Atualize o pré-voo antes de revisar o mapa emocional.")
        rows = _scene_rows(source)
        texts = [row["texto"].strip() for row in rows]
        if str(plan.get("story_text") or "").strip() not in {separator.join(texts) for separator in ("\n", "\n\n")} :
            raise PermissionError("O texto do pré-voo não corresponde à versão canônica da obra. Atualize o plano antes da direção emocional.")
        return source
    texts = [text.strip() for text in str(plan.get("story_text") or "").split("\n\n") if text.strip()]
    return {"book_id": plan.get("project_id"), "cenas_texto": [{"numero": i, "texto": text} for i, text in enumerate(texts, 1)]}


def _scene_rows(source):
    rows = source.get("cenas_texto") or []
    if not rows:
        rows = [{"numero": i, "texto": row.get("instruction") or row.get("cena") or row.get("prompt_livre") or row.get("title") or row.get("nome") or ""}
                for i, row in enumerate(source.get("pages") or source.get("paginas") or [], 1)]
    clean, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or not str(row.get("texto") or "").strip():
            raise ValueError("Cada cena do mapa emocional precisa de texto salvo.")
        number = row.get("numero")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1 or number in seen:
            raise ValueError("O mapa emocional precisa de números de cena únicos e positivos.")
        seen.add(number)
        clean.append(deepcopy(row))
    if not clean:
        raise ValueError("Salve as cenas antes de preparar a direção emocional.")
    return clean


def _source_signature(plan, source):
    return fingerprint({"source_ref": plan.get("source_ref", ""),
                        "book_id": source.get("book_id") or source.get("project_id") or source.get("id") or plan.get("project_id"),
                        "scenes": _scene_rows(source), "characters": source.get("personagens"),
                        "map": source.get("mapa_emocional"), "preset": source.get("paleta_emocional_preset"),
                        "style": source.get("style_dna") or source.get("style_dna_id")})


def _approval_signature(plan, binding):
    approvals = plan.get("approvals") or {}
    return fingerprint({"source": binding.get("source_signature"), "scenes": binding.get("scenes"),
                        "style": plan.get("style_master"), "characters": plan.get("characters"),
                        "locations": plan.get("locations"),
                        "character_references": approvals.get("characters"), "world_references": approvals.get("locations")})


def prepare_emotional_binding(plan, source=None):
    """Prepare suggestions without approving them or sending content to AI."""
    out = deepcopy(plan)
    source = source_for_plan(out) if source is None else deepcopy(source)
    rows = _scene_rows(source)
    generated = construir_mapa_emocional(rows, source.get("paleta_emocional_preset") or "Erica Matsuzaki · Pastel Faith")
    existing = {row.get("numero"): row for row in source.get("mapa_emocional") or [] if isinstance(row, dict)}
    mapped = []
    for row, item in zip(rows, generated):
        prior = existing.get(row["numero"]) or {}
        if isinstance(prior.get("direcao"), dict):
            item["direcao"] = deepcopy(prior["direcao"])
        item["instrucao_autora"] = str(prior.get("instrucao_autora", item.get("instrucao_autora", "")))
        item.pop("texto", None)
        item["aprovado"] = False
        item["source_text_digest"] = fingerprint(row["texto"].strip())
        mapped.append(item)
    out["emotional_binding"] = {"schema": SCHEMA, "source_ref": out.get("source_ref", ""),
                                "source_signature": _source_signature(out, source), "scenes": mapped, "approval": None}
    out.setdefault("approvals", {})["scene_options"] = {}
    return out


def _normalize_reviewed_scenes(scenes, expected):
    if not isinstance(scenes, list) or len(scenes) != len(expected):
        raise ValueError("Revise a direção emocional de todas as cenas da obra.")
    normalized = []
    from emotional_color_director import direcao_emocional
    from emotion_colors import EMOCOES, EMOCOES_COMPLEMENTARES
    from emotional_color_director import PLUTCHIK_POR_EMOCAO, EMOCAO_BASE, _slug_emocao
    allowed = set(EMOCOES) | set(EMOCOES_COMPLEMENTARES) | set(PLUTCHIK_POR_EMOCAO) | set(EMOCAO_BASE)
    for actual, canonical in zip(scenes, expected):
        if not isinstance(actual, dict) or actual.get("numero") != canonical["numero"]:
            raise ValueError("O mapa precisa corresponder aos números exatos das cenas de origem.")
        d = actual.get("direcao") or {}
        emotion = str(d.get("emocao_narrativa") or "").strip()
        intensity = d.get("intensidade")
        if _slug_emocao(emotion) not in allowed or isinstance(intensity, bool) or not isinstance(intensity, int) or not 1 <= intensity <= 5:
            raise ValueError("Informe emoção reconhecida e intensidade inteira de 1 a 5 em cada cena.")
        item = deepcopy(canonical)
        # Deterministic canonical palette wins over arbitrary LLM/free-form colors.
        item["direcao"] = direcao_emocional(emotion, d.get("preset", ""), intensity,
                                            str(d.get("subemocao") or ""), str(d.get("transicao_emocional") or ""))
        item["instrucao_autora"] = str(actual.get("instrucao_autora") or "").strip()
        item["expressao"] = str(actual.get("expressao") or canonical.get("expressao") or emotion)
        item["aprovado"] = True
        normalized.append(item)
    return normalized


def approve_emotional_binding(plan, scenes, *, reviewed=False, reviewer=""):
    if not reviewed or not str(reviewer).strip():
        raise PermissionError("Revise o mapa cena por cena e identifique quem aprova a direção emocional.")
    prepared = prepare_emotional_binding(plan)
    expected = prepared["emotional_binding"]["scenes"]
    normalized = _normalize_reviewed_scenes(scenes, expected)
    binding = prepared["emotional_binding"]
    binding["scenes"] = normalized
    binding["approval"] = {"reviewer": str(reviewer).strip(), "approved_at": int(time.time()),
                           "fingerprint": _approval_signature(prepared, binding)}
    return prepared


def require_emotional_binding(plan):
    binding = plan.get("emotional_binding") or {}
    approval = binding.get("approval") or {}
    if binding.get("schema") != SCHEMA or not approval.get("reviewer") or not binding.get("scenes"):
        raise PermissionError("Prepare, revise e aprove o mapa emocional de todas as cenas antes de gerar com IA.")
    if binding.get("source_signature") != _source_signature(plan, source_for_plan(plan)):
        raise PermissionError("A narrativa, o mapa ou a identidade de origem mudou. Revise e aprove novamente a direção emocional.")
    if approval.get("fingerprint") != _approval_signature(plan, binding) or not all(x.get("aprovado") is True for x in binding["scenes"]):
        raise PermissionError("O mapa, as referências ou o estilo mudou. Revise e aprove novamente a direção emocional.")
    return deepcopy(binding)


def scene_direction(plan, scene_key, *, source_scene_number=None, excerpt=""):
    binding = require_emotional_binding(plan)
    number = source_scene_number or (plan.get("scene_emotional_links") or {}).get(str(scene_key))
    if number is None:
        match = re.fullmatch(r"(?:cena_)?([1-9][0-9]*)", str(scene_key))
        number = int(match.group(1)) if match else None
    if number is None and excerpt:
        matches = [item["numero"] for item in binding["scenes"] if item["source_text_digest"] == fingerprint(str(excerpt).strip())]
        number = matches[0] if len(matches) == 1 else None
    item = next((item for item in binding["scenes"] if item["numero"] == number), None)
    if item is None:
        raise PermissionError("Vincule explicitamente a proposta/painel a uma cena exata do mapa emocional aprovado.")
    return item


def source_scene_text(plan, number):
    return next(row["texto"].strip() for row in _scene_rows(source_for_plan(plan)) if row["numero"] == number)


def direction_prompt(item):
    return prompt_direcao_visual(item) + "\n" + IDENTITY_RULE


BOOK_SCHEMA = "faithbloom.book-emotional-approval.v1"
EMOTIONAL_SCENE_FIELDS = ("emocao", "emocao_secundaria", "intensidade_emocional", "transicao_emocional",
                          "instrucao_emocional", "paleta_preset", "emocao_travada", "mapa_emocional_aprovado")


def _stable_reference(value):
    """Local/cache/storage paths of the same original bytes share one identity."""
    from pathlib import Path
    value = str(value or "")
    if not value:
        return ""
    from storage_backend import materializar
    # The storage layer also enforces local tenant boundaries. Do not read a
    # raw local reference directly before that access check has happened.
    path = materializar(value)
    if Path(path).is_file():
        return {"media_sha256": sha256(Path(path).read_bytes()).hexdigest()}
    return {"reference": value}


def _book_characters(state):
    rows = {}
    for name, character in (state.get("personagens") or {}).items():
        rows[name] = {key: character.get(key) for key in ("nome", "descricao_fixa", "papel", "dna", "aparencia_aprovada", "character_universe_id", "official_id")}
        rows[name]["reference"] = _stable_reference(character.get("imagem_referencia") or character.get("color_master"))
    return rows


def book_visual_style(state):
    """Resolve the exact declared style without inventing a replacement style."""
    inline = state.get("style_dna") or state.get("style_master")
    style_id = state.get("style_dna_id") or (inline.get("style_dna_id") if isinstance(inline, dict) else None)
    if style_id:
        from style_dna import carregar_style
        style = carregar_style(str(style_id))
        if not isinstance(style, dict) or not style or style.get("status") != "oficial":
            raise PermissionError("Recupere e aprove o Style DNA declarado antes de gerar imagens.")
    elif inline:
        if not isinstance(inline, dict):
            raise PermissionError("O estilo declarado precisa de uma direção visual estruturada.")
        style = deepcopy(inline)
        if style.get("status", "oficial") != "oficial":
            raise PermissionError("Aprove o Style DNA candidato antes de gerar imagens.")
    else:
        return {}
    if style.get("usos_permitidos") and "story" not in style["usos_permitidos"]:
        raise PermissionError("O Style DNA declarado não está autorizado para histórias.")
    if not (style.get("regras") or style.get("description") or style.get("descricao")):
        raise PermissionError("O Style DNA declarado precisa conter suas regras visuais aprovadas.")
    return {key: deepcopy(style.get(key)) for key in ("id", "nome", "name", "status", "modo", "regras", "description", "descricao", "usos_permitidos") if key in style}


def _book_content(state, *, include_emotions=True):
    fields = ("numero", "texto", "personagem_principal", "contexto_visual", "figurino", "expressao")
    if include_emotions:
        fields += EMOTIONAL_SCENE_FIELDS
    return {"scenes": [{key: row.get(key) for key in fields} for row in _scene_rows(state)],
            "characters": _book_characters(state), "style_dna_id": state.get("style_dna_id"),
            "style_dna": state.get("style_dna"), "style_master": state.get("style_master"),
            "active_narrative": state.get("versao_narrativa_ativa"), "resolved_style": book_visual_style(state)}


def book_emotional_review_key(state):
    """Changes of work/content reset UI approval; titles never identify a book."""
    return fingerprint({"book_id": state.get("book_id"), "source_ref": state.get("storage_path"),
                        "content": _book_content(state), "map": state.get("mapa_emocional"),
                        "preset": state.get("paleta_emocional_preset")})


def prepare_book_emotional_map(state):
    """Return a local draft, with no approval, image or paid provider action."""
    if not isinstance(state, dict):
        raise ValueError("Abra um livro antes de preparar o mapa emocional.")
    out = deepcopy(state)
    pseudo = {"project_id": out.get("book_id") or out.get("storage_path") or "unsaved-book"}
    prepared = prepare_emotional_binding(pseudo, out)
    out["mapa_emocional"] = deepcopy(prepared["emotional_binding"]["scenes"])
    out["emotional_book_binding"] = {"schema": BOOK_SCHEMA, "approval": None}
    return out


def _sync_book_map(state, items):
    by_number = {row["numero"]: row for row in items}
    for scene in state["cenas_texto"]:
        item = by_number[scene["numero"]]
        d = item["direcao"]
        scene.update(emocao=d["emocao_narrativa"], emocao_secundaria=d.get("subemocao", ""),
                     intensidade_emocional=d["intensidade"], transicao_emocional=d.get("transicao_emocional", ""),
                     instrucao_emocional=item.get("instrucao_autora", ""), paleta_preset=d["preset"],
                     mapa_emocional_aprovado=True)
    state["mapa_emocional"] = deepcopy(items)


def _book_approval_fingerprint(state):
    return fingerprint({"book_id": state.get("book_id"), "content": _book_content(state),
                        "map": state.get("mapa_emocional"), "preset": state.get("paleta_emocional_preset")})


def approve_book_emotional_map(state, scenes=None, *, reviewed=False, reviewer=""):
    """Explicit author approval; legacy flags alone never authorize generation."""
    if not reviewed or not str(reviewer).strip():
        raise PermissionError("Revise todas as cenas e identifique quem aprova o mapa emocional do livro.")
    draft = prepare_book_emotional_map(state)
    expected = draft["mapa_emocional"]
    actual = deepcopy(scenes if scenes is not None else state.get("mapa_emocional") or expected)
    items = _normalize_reviewed_scenes(actual, expected)
    _sync_book_map(draft, items)
    if not draft.get("book_id"):
        import uuid
        draft["book_id"] = uuid.uuid4().hex
    draft["emotional_book_binding"] = {"schema": BOOK_SCHEMA, "source_ref": str(draft.get("storage_path") or ""),
                                      "book_id": draft["book_id"],
                                      "approval": {"reviewer": str(reviewer).strip(), "approved_at": int(time.time()),
                                                   "fingerprint": _book_approval_fingerprint(draft)}}
    return draft


def require_book_emotional_map(state):
    binding = state.get("emotional_book_binding") or {}
    approval = binding.get("approval") or {}
    if (binding.get("schema") != BOOK_SCHEMA or not approval.get("reviewer")
            or not binding.get("book_id") or binding.get("book_id") != state.get("book_id")):
        raise PermissionError("Prepare, revise e aprove o mapa emocional do livro antes de gerar novas imagens.")
    expected_ref = str(binding.get("source_ref") or "").removeprefix("fb://")
    if expected_ref and expected_ref != str(state.get("storage_path") or "").removeprefix("fb://"):
        raise PermissionError("A aprovação emocional pertence a outra referência de livro salvo.")
    if approval.get("fingerprint") != _book_approval_fingerprint(state):
        raise PermissionError("A narrativa, o mapa, os personagens ou o estilo mudou. Revise e aprove novamente o mapa emocional.")
    rows = state.get("mapa_emocional") or []
    if len(rows) != len(_scene_rows(state)) or not all(row.get("aprovado") is True for row in rows):
        raise PermissionError("Revise e aprove o mapa emocional de todas as cenas do livro.")
    return deepcopy(binding)


def require_book_source_current(state, *, require_saved=False, require_approval=True):
    """Fail before spending/writing if this exact durable Book Master changed.

    Image candidates, history and checkpoints intentionally do not identify the
    manuscript. Explicit unsaved inputs remain usable outside production queues.
    This is a freshness check, not a distributed transaction or a merge policy.
    """
    if require_approval:
        require_book_emotional_map(state)
    reference = str(state.get("storage_path") or "")
    if not reference:
        if require_saved:
            raise PermissionError("Revise e salve o mapa no Book Master antes de gerar imagens.")
        return deepcopy(state)
    import storage_backend as storage
    canonical = reference if storage.is_storage_uri(reference) else storage.storage_uri(reference)
    saved = storage.BACKEND.get_json(storage.uri_to_path(canonical), None)
    if not isinstance(saved, dict) or not saved:
        raise PermissionError("O Book Master exato não está disponível. Reabra a fonte antes de gerar imagens.")
    saved = deepcopy(saved)
    saved["storage_path"] = canonical
    current = deepcopy(state)
    current["storage_path"] = canonical
    if require_approval:
        require_book_emotional_map(saved)
    if book_emotional_review_key(saved) != book_emotional_review_key(current):
        raise PermissionError("A narrativa, os personagens, o estilo ou o mapa do Book Master mudou. Reabra a versão atual antes de gerar imagens.")
    return saved


def book_scene_direction(state, number):
    require_book_emotional_map(state)
    matches = [row for row in state["mapa_emocional"] if row.get("numero") == number]
    if len(matches) != 1:
        raise PermissionError("O número da cena não corresponde ao mapa emocional aprovado.")
    return deepcopy(matches[0])


def persist_book_emotional_map(state):
    """Persist to the exact saved identity, preserving newer unrelated metadata."""
    require_book_emotional_map(state)
    from armazenamento import salvar_livro, atualizar_livro_salvo
    import storage_backend as storage
    out = deepcopy(state)
    reference = str(out.get("storage_path") or "")
    if reference:
        canonical = reference if storage.is_storage_uri(reference) else storage.storage_uri(reference)
        path = storage.uri_to_path(canonical)
        saved = storage.BACKEND.get_json(path, None)
        if not isinstance(saved, dict) or (saved.get("book_id") and saved["book_id"] != out["book_id"]):
            raise PermissionError("A referência salva não pertence a este livro. Nenhuma outra obra foi alterada.")
        if _book_content(saved, include_emotions=False) != _book_content(out, include_emotions=False):
            raise PermissionError("A história salva mudou em outra tela. Reabra a versão atual antes de salvar o mapa emocional.")
        _sync_book_map(saved, out["mapa_emocional"])
        reviewed_scenes = {row["numero"]: row for row in out["cenas_texto"]}
        for scene in saved["cenas_texto"]:
            reviewed = reviewed_scenes[scene["numero"]]
            for field in EMOTIONAL_SCENE_FIELDS:
                if field in reviewed:
                    scene[field] = deepcopy(reviewed[field])
                else:
                    scene.pop(field, None)
        for key in ("book_id", "paleta_emocional_preset", "emotional_book_binding"):
            if key in out:
                saved[key] = deepcopy(out[key])
        saved["storage_path"] = canonical
        atualizar_livro_salvo(canonical, saved)
        out = saved
    else:
        # This is an explicit save by the author, never a same-title lookup.
        out["storage_path"] = salvar_livro(out)
    return out

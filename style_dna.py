"""Style DNA persistente por coleção/projeto (Story, Coloring e Activity)."""
from __future__ import annotations
import time, uuid
from armazenamento import _json, _save_json, _slug
import storage_backend as storage
from storage_updates import update_json_document

INDEX = "style_dna/index.json"

DEFAULT_USE_CONTEXTS = ["story", "coloring", "activity", "cover"]


def _index() -> list[dict]:
    d = _json(INDEX, [])
    return d if isinstance(d, list) else []


def _style_card(style: dict) -> dict:
    return {
        "id": style.get("id", ""),
        "nome": style.get("nome", ""),
        "colecao": style.get("colecao", ""),
        "modo": style.get("modo", "geral"),
        "status": style.get("status", "oficial"),
    }


def _sync_index_record(style: dict) -> list[dict]:
    """Upsert one Style DNA card without replacing concurrent index changes."""
    card = _style_card(style)
    sid = str(card.get("id") or "")
    if not sid:
        raise ValueError("Style DNA sem id não pode ser indexado.")

    def mutate(rows):
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise storage.StorageCorrupt("Índice de Style DNA inválido; nenhuma gravação foi realizada.")
        out = [dict(item) for item in rows if isinstance(item, dict) and str(item.get("id") or "") != sid]
        out.append(card)
        return out

    return update_json_document(
        storage.BACKEND, INDEX, mutate, [], allow_legacy_pilot=True
    )


def criar_style_dna(nome: str, colecao: str, regras: dict, modo: str = "geral", usos: list[str] | None = None, metadata: dict | None = None) -> dict:
    sid = uuid.uuid4().hex
    obj = {
        "id": sid,
        "nome": nome,
        "colecao": colecao,
        "modo": modo,
        "status": "oficial",
        "regras": regras or {},
        "usos_permitidos": usos or DEFAULT_USE_CONTEXTS,
        "metadata": metadata or {},
        "versoes": [],
        "criado_em": int(time.time()),
        "atualizado_em": int(time.time()),
    }
    _save_json(f"style_dna/{sid}.json", obj)
    _sync_index_record(obj)
    return obj


def criar_style_candidate_autopilot(colecao: str) -> dict:
    """Cria uma identidade visual provisória quando a coleção ainda não possui Style DNA.

    O candidato é deliberadamente NÃO-oficial e nunca vira Master automaticamente.
    Ele existe para o Autopilot não bloquear no meio do livro por falta de uma ficha
    manual. A autora continua responsável pela aprovação/promocão posterior.
    """
    collection = str(colecao or "").strip()
    if not collection:
        return {}

    existentes = [x for x in _index() if x.get("colecao") == collection]
    for card in existentes:
        if str(card.get("status") or "").lower() == "candidate":
            style = carregar_style(str(card.get("id") or ""))
            if style:
                return style
    if existentes:
        return {}

    sid = uuid.uuid4().hex
    now = int(time.time())
    nome = f"Autopilot Candidate — {collection}"
    obj = {
        "id": sid,
        "nome": nome,
        "colecao": collection,
        "modo": "autopilot_provisional",
        "status": "candidate",
        "regras": {
            "source_of_truth": "preserve_original_book_and_approved_character_masters",
            "character_consistency": "preservar Character DNA, Color Master e referências oficiais; nunca redesenhar identidade canônica",
            "collection_consistency": "manter linguagem visual coerente entre cenas usando o próprio livro publicado como referência primária",
            "palette": "derivar a paleta do material existente e da direção emocional aprovada; não inventar paleta canônica nova",
            "composition": "composição infantil clara, legível e apropriada à faixa etária; ação visual compreensível",
            "text_in_image": "não inserir texto editorial dentro da ilustração salvo quando explicitamente aprovado",
            "safety": "nenhuma regra deste candidato promove, substitui ou altera Style DNA/Character Master oficial",
        },
        "usos_permitidos": ["story"],
        "metadata": {
            "source": "autopilot_empty_collection_fallback",
            "provisional": True,
            "requires_final_human_approval": True,
            "master_promotion_allowed": False,
            "collection": collection,
            "created_at": now,
        },
        "versoes": [],
        "criado_em": now,
        "atualizado_em": now,
    }
    _save_json(f"style_dna/{sid}.json", obj)
    _sync_index_record(obj)
    return obj


def _auto_ativar_story_se_unico(itens: list[dict], colecao: str | None) -> None:
    """Migra com segurança o Style DNA oficial único de uma coleção para Story.

    O Autopilot deve seguir sem formulário quando a escolha é inequívoca. Esta
    migração só acontece quando uma coleção explícita possui exatamente UM Style
    DNA oficial. Regras visuais não são alteradas; apenas o contexto ``story`` é
    acrescentado, com snapshot/versionamento e trilha em metadata. Com zero ou
    múltiplos estilos nada é promovido silenciosamente.
    """
    if not colecao or len(itens) != 1:
        return
    card = itens[0]
    if str(card.get("status") or "oficial") != "oficial":
        return
    sid = str(card.get("id") or "")
    if not sid:
        return
    style = carregar_style(sid)
    if not style or str(style.get("status") or "oficial") != "oficial":
        return
    usos = list(style.get("usos_permitidos") or [])
    if not usos or "story" in usos:
        return
    metadata = dict(style.get("metadata") or {})
    metadata["story_auto_activation"] = {
        "source": "autopilot_unambiguous_collection_style",
        "collection": colecao,
        "activated_at": int(time.time()),
        "rules_changed": False,
    }
    atualizar_style(sid, {
        "usos_permitidos": [*usos, "story"],
        "metadata": metadata,
    })


def listar_styles(colecao: str | None = None) -> list[dict]:
    itens = _index()
    if colecao:
        itens = [x for x in itens if x.get("colecao") == colecao]
        if not itens:
            candidate = criar_style_candidate_autopilot(colecao)
            if candidate:
                itens = [{
                    "id": candidate.get("id"),
                    "nome": candidate.get("nome"),
                    "colecao": candidate.get("colecao"),
                    "modo": candidate.get("modo"),
                    "status": candidate.get("status"),
                }]
        _auto_ativar_story_se_unico(itens, colecao)
    return sorted(itens, key=lambda x: (x.get("colecao", ""), x.get("nome", "")))


def carregar_style(sid: str) -> dict:
    return _json(f"style_dna/{sid}.json", {}) or {}


def atualizar_style(sid: str, novos: dict) -> dict:
    """Merge top-level Style DNA fields atomically and retain a pre-edit snapshot."""
    if not isinstance(novos, dict):
        raise TypeError("A atualização do Style DNA precisa ser um objeto.")
    path = f"style_dna/{sid}.json"
    prepared = dict(novos)

    def mutate(atual):
        if not isinstance(atual, dict) or not atual:
            raise KeyError(sid)
        if str(atual.get("id") or sid) != str(sid):
            raise storage.StorageCorrupt("O Style DNA salvo possui identidade divergente.")
        snap = {k: v for k, v in atual.items() if k != "versoes"}
        result = dict(atual)
        result["versoes"] = list(atual.get("versoes") or [])
        result["versoes"].append({"salvo_em": int(time.time()), "snapshot": snap})
        result.update(prepared)
        result["id"] = sid
        result["atualizado_em"] = int(time.time())
        return result

    committed = update_json_document(
        storage.BACKEND, path, mutate, None, allow_legacy_pilot=True
    )
    _sync_index_record(committed)
    return committed


def style_para_prompt(style: dict, contexto: str = "story") -> str:
    if not style:
        return ""
    usos = style.get("usos_permitidos", [])
    if usos and contexto not in usos:
        return ""
    regras = style.get("regras", {})
    status = str(style.get("status") or "oficial").lower()
    rotulo = "STYLE DNA OFICIAL" if status == "oficial" else "STYLE DNA PROVISÓRIO / CANDIDATO"
    approval_note = (
        "Este candidato não é Master e exige aprovação humana final. "
        if status != "oficial" else ""
    )
    return (
        f"{rotulo} '{style.get('nome','')}' ({style.get('modo','geral')}). "
        f"{approval_note}Aplicar estas regras visuais sem alterar Character DNA: {regras}. "
        "Consistência de coleção é obrigatória; pose, ação, cenário e figurino podem variar quando autorizados."
    )

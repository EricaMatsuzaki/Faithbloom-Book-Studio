"""Style DNA persistente por coleção/projeto (Story, Coloring e Activity)."""
from __future__ import annotations
import time, uuid
from armazenamento import _json, _save_json, _slug

INDEX = "style_dna/index.json"

DEFAULT_USE_CONTEXTS = ["story", "coloring", "activity", "cover"]


def _index() -> list[dict]:
    d = _json(INDEX, [])
    return d if isinstance(d, list) else []


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
    idx = [x for x in _index() if x.get("id") != sid]
    idx.append({"id": sid, "nome": nome, "colecao": colecao, "modo": modo, "status": "oficial"})
    _save_json(INDEX, idx)
    return obj


def listar_styles(colecao: str | None = None) -> list[dict]:
    itens = _index()
    if colecao:
        itens = [x for x in itens if x.get("colecao") == colecao]
    return sorted(itens, key=lambda x: (x.get("colecao", ""), x.get("nome", "")))


def carregar_style(sid: str) -> dict:
    return _json(f"style_dna/{sid}.json", {}) or {}


def atualizar_style(sid: str, novos: dict) -> dict:
    atual = carregar_style(sid)
    if not atual:
        raise KeyError(sid)
    snap = {k: v for k, v in atual.items() if k != "versoes"}
    atual.setdefault("versoes", []).append({"salvo_em": int(time.time()), "snapshot": snap})
    atual.update(novos)
    atual["atualizado_em"] = int(time.time())
    _save_json(f"style_dna/{sid}.json", atual)
    return atual


def style_para_prompt(style: dict, contexto: str = "story") -> str:
    if not style:
        return ""
    usos = style.get("usos_permitidos", [])
    if usos and contexto not in usos:
        return ""
    regras = style.get("regras", {})
    return (
        f"STYLE DNA OFICIAL '{style.get('nome','')}' ({style.get('modo','geral')}). "
        f"Aplicar estas regras visuais sem alterar Character DNA: {regras}. "
        "Consistência de coleção é obrigatória; pose, ação, cenário e figurino podem variar quando autorizados."
    )

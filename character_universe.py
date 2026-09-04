"""FaithBloom Character Universe — personagens oficiais reutilizáveis por coleção.

Refinamento 03: separa identidade bloqueada de variáveis narrativas e mantém
histórico/variações sem destruir versões anteriores.
"""
from __future__ import annotations
import time, uuid
from copy import deepcopy
from armazenamento import _json, _save_json, _slug
from storage_backend import materializar_assets_em_objeto, persistir_assets_em_objeto

INDEX = "character_universe/index.json"
USOS_PADRAO = ["story", "coloring", "activity", "cover"]
VARIAVEIS_PADRAO = ["pose", "acao", "expressao", "emocao", "figurino", "acessorios_temporarios", "cenario", "estacao", "festividade"]


def _index():
    x = _json(INDEX, [])
    return x if isinstance(x, list) else []


def normalizar_dna(dna: dict | str | None) -> dict:
    """Aceita o DNA antigo em texto e o novo DNA estruturado."""
    if isinstance(dna, str):
        return {
            "descricao_master": dna,
            "campos_bloqueados": {},
            "caracteristicas_bloqueadas": dna,
            "variaveis_permitidas": list(VARIAVEIS_PADRAO),
        }
    d = deepcopy(dna or {})
    d.setdefault("descricao_master", d.get("caracteristicas_bloqueadas", ""))
    d.setdefault("campos_bloqueados", {})
    d.setdefault("variaveis_permitidas", list(VARIAVEIS_PADRAO))
    return d


def _reference_asset_id(ref: dict) -> str:
    return str((ref.get("metadata") or {}).get("asset_library_id") or ref.get("asset_library_id") or "").strip()


def _reference_path(ref: dict) -> str:
    return str(ref.get("asset") or ref.get("storage_uri") or ref.get("caminho_arquivo") or "").strip()


def _merge_reference_data(first: dict, duplicate: dict) -> dict:
    """Mantém a primeira ocorrência e preenche apenas informação que faltava."""
    merged = deepcopy(first)
    for key, value in duplicate.items():
        if key == "metadata":
            metadata = dict(merged.get("metadata") or {})
            for meta_key, meta_value in (value or {}).items():
                if meta_key not in metadata or metadata[meta_key] in (None, "", [], {}):
                    metadata[meta_key] = deepcopy(meta_value)
            merged["metadata"] = metadata
        elif key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = deepcopy(value)
    return merged


def deduplicar_reference_pack(reference_pack: list | None) -> list[dict]:
    """Deduplica vínculos, nunca assets físicos, preservando a primeira ordem.

    ``asset_library_id`` é a identidade principal. O caminho/URI só é usado
    quando pelo menos uma ocorrência é legada e não possui esse identificador.
    """
    unique: list[dict] = []
    for raw in reference_pack or []:
        if isinstance(raw, str):
            ref = {"asset": raw}
        elif isinstance(raw, dict):
            ref = deepcopy(raw)
        else:
            continue
        asset_id = _reference_asset_id(ref)
        path = _reference_path(ref)
        duplicate_index = None
        for index, existing in enumerate(unique):
            existing_id = _reference_asset_id(existing)
            existing_path = _reference_path(existing)
            same_id = bool(asset_id and existing_id and asset_id == existing_id)
            legacy_same_path = bool(path and existing_path and path == existing_path and not (asset_id and existing_id))
            if same_id or legacy_same_path:
                duplicate_index = index
                break
        if duplicate_index is None:
            unique.append(ref)
        else:
            unique[duplicate_index] = _merge_reference_data(unique[duplicate_index], ref)
    return unique


def criar_personagem_oficial(colecao: str, nome: str, dna: dict, color_master: str = "", line_art_master: str = "", reference_pack: list | None = None, metadata: dict | None = None) -> dict:
    pid = uuid.uuid4().hex
    meta = deepcopy(metadata or {})
    meta.setdefault("usos_permitidos", list(USOS_PADRAO))
    meta.setdefault("presets", {"figurinos": [], "cenarios": [], "estacoes": [], "festividades": [], "emocoes": []})
    obj = {
        "id": pid,
        "colecao": colecao,
        "nome": nome,
        "status": "oficial",
        "dna": normalizar_dna(dna),
        "color_master": color_master,
        "line_art_master": line_art_master,
        "reference_pack": reference_pack or [],
        "metadata": meta,
        "variacoes": [],
        "versoes": [],
        "criado_em": int(time.time()),
        "atualizado_em": int(time.time()),
    }
    obj = persistir_assets_em_objeto(obj, f"assets/character_universe/{_slug(colecao)}/{_slug(nome)}")
    _save_json(f"character_universe/{pid}.json", obj)
    idx = [i for i in _index() if i.get("id") != pid]
    idx.append({"id": pid, "colecao": colecao, "nome": nome, "status": "oficial"})
    _save_json(INDEX, idx)
    return materializar_assets_em_objeto(obj)


def listar_personagens_oficiais(colecao: str | None = None) -> list[dict]:
    itens = _index()
    if colecao:
        itens = [i for i in itens if i.get("colecao") == colecao]
    return sorted(itens, key=lambda x: (x.get("colecao", ""), x.get("nome", "")))


def carregar_personagem_oficial(pid: str) -> dict:
    path = f"character_universe/{pid}.json"
    raw = _json(path, {}) or {}
    if raw:
        original_refs = raw.get("reference_pack", [])
        unique_refs = deduplicar_reference_pack(original_refs)
        if unique_refs != original_refs:
            # Repara somente os vínculos duplicados; Masters, histórico e bytes
            # da Asset Library/storage não são tocados.
            raw = deepcopy(raw)
            raw["reference_pack"] = unique_refs
            _save_json(path, raw)
    obj = materializar_assets_em_objeto(raw)
    if obj:
        obj["dna"] = normalizar_dna(obj.get("dna"))
        obj.setdefault("variacoes", [])
        obj.setdefault("metadata", {})
        obj["metadata"].setdefault("usos_permitidos", list(USOS_PADRAO))
        obj["metadata"].setdefault("presets", {"figurinos": [], "cenarios": [], "estacoes": [], "festividades": [], "emocoes": []})
        # Refinamento 22: defaults aditivos mantêm documentos legados válidos.
        obj["metadata"].setdefault("master_history", [])
        obj["metadata"].setdefault("current_master_asset_ids", {})
        obj.setdefault("reference_pack", [])
        obj.setdefault("color_master", "")
        obj.setdefault("line_art_master", "")
    return obj


def atualizar_personagem_oficial(pid: str, novos: dict) -> dict:
    atual = _json(f"character_universe/{pid}.json", {}) or {}
    if not atual:
        raise KeyError(pid)
    snapshot = {k: v for k, v in atual.items() if k != "versoes"}
    atual.setdefault("versoes", []).append({"salvo_em": int(time.time()), "snapshot": snapshot})
    novos = deepcopy(novos)
    if "dna" in novos:
        novos["dna"] = normalizar_dna(novos["dna"])
    atual.update(novos)
    atual["atualizado_em"] = int(time.time())
    atual = persistir_assets_em_objeto(atual, f"assets/character_universe/{_slug(atual.get('colecao',''))}/{_slug(atual.get('nome',''))}")
    _save_json(f"character_universe/{pid}.json", atual)
    return materializar_assets_em_objeto(atual)


def adicionar_variacao(pid: str, tipo: str, instrucao: str, asset: str = "", metadata: dict | None = None, aprovada: bool = False) -> dict:
    p = carregar_personagem_oficial(pid)
    if not p:
        raise KeyError(pid)
    v = {
        "id": uuid.uuid4().hex,
        "tipo": tipo,
        "instrucao": instrucao,
        "asset": asset,
        "metadata": metadata or {},
        "aprovada": bool(aprovada),
        "criada_em": int(time.time()),
    }
    p.setdefault("variacoes", []).append(v)
    atualizar_personagem_oficial(pid, {"variacoes": p["variacoes"]})
    return v


def aprovar_variacao(pid: str, variacao_id: str) -> dict:
    p = carregar_personagem_oficial(pid)
    vars_ = p.get("variacoes", [])
    for v in vars_:
        if v.get("id") == variacao_id:
            v["aprovada"] = True
    return atualizar_personagem_oficial(pid, {"variacoes": vars_})


def salvar_preset(pid: str, categoria: str, nome: str, instrucao: str) -> dict:
    p = carregar_personagem_oficial(pid)
    meta = p.setdefault("metadata", {})
    presets = meta.setdefault("presets", {"figurinos": [], "cenarios": [], "estacoes": [], "festividades": [], "emocoes": []})
    presets.setdefault(categoria, [])
    item = {"id": uuid.uuid4().hex, "nome": nome, "instrucao": instrucao}
    presets[categoria].append(item)
    atualizar_personagem_oficial(pid, {"metadata": meta})
    return item


def personagem_para_prompt(p: dict, modo: str = "color", variaveis: dict | None = None, contexto: str = "story") -> str:
    dna = normalizar_dna(p.get("dna", {}))
    usos = p.get("metadata", {}).get("usos_permitidos", USOS_PADRAO)
    if usos and contexto not in usos:
        raise ValueError(f"Personagem não está autorizado para o contexto '{contexto}'.")
    campos = dna.get("campos_bloqueados") or dna.get("caracteristicas_bloqueadas") or dna.get("descricao_master")
    permitidas = set(dna.get("variaveis_permitidas", VARIAVEIS_PADRAO))
    solicitadas = variaveis or {}
    filtradas = {k: v for k, v in solicitadas.items() if k in permitidas and v not in (None, "")}
    proibidas = [k for k in solicitadas if k not in permitidas]
    texto = (
        f"PERSONAGEM OFICIAL {p.get('nome')}. CHARACTER DNA BLOQUEADO: {campos}. "
        f"Preserve rigorosamente rosto, espécie, proporções fundamentais, olhos, marcas, paleta-base e identidade visual. "
        f"Modo visual: {modo}; uso: {contexto}. Variáveis autorizadas nesta cena: {filtradas}. "
        "Roupas, pose, ação, cenário, estação, festividade e expressão podem mudar SOMENTE quando autorizados; a identidade não muda."
    )
    if proibidas:
        texto += f" Ignorar alterações não autorizadas nos campos: {proibidas}."
    return texto


def adicionar_referencia(pid: str, asset: str, tipo: str = "cena", origem: str = "book_doctor", metadata: dict | None = None) -> dict:
    """Adiciona referência ao pack sem substituir Color/Line Art Master."""
    path = f"character_universe/{pid}.json"
    p = _json(path, {}) or {}
    if not p:
        raise KeyError(pid)
    refs = deduplicar_reference_pack(p.get("reference_pack", []))
    item = {
        "id": uuid.uuid4().hex,
        "asset": asset,
        "tipo": tipo,
        "origem": origem,
        "metadata": metadata or {},
        "criada_em": int(time.time()),
    }
    combined = deduplicar_reference_pack([*refs, item])
    if combined != p.get("reference_pack", []):
        # Usa o versionamento normal do Character Universe; nenhum arquivo da
        # Asset Library é removido ou regravado.
        return atualizar_personagem_oficial(pid, {"reference_pack": combined})
    return carregar_personagem_oficial(pid)


def definir_master_visual(pid: str, asset: str, modo: str = "color") -> dict:
    """Define um asset já aprovado como Color Master ou Line Art Master com histórico."""
    if modo not in {"color", "line_art"}:
        raise ValueError("modo deve ser 'color' ou 'line_art'")
    campo = "color_master" if modo == "color" else "line_art_master"
    return atualizar_personagem_oficial(pid, {campo: asset})

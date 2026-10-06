"""FaithBloom Character Universe — personagens oficiais reutilizáveis por coleção.

Refinamento 03: separa identidade bloqueada de variáveis narrativas e mantém
histórico/variações sem destruir versões anteriores.
Refinamento 26: Duplicate & Archive Safety — duplicidades entre coleções,
arquivamento não destrutivo e proteção de Character Masters com histórico.
Refinamento 27: Collection Safety — mudança de coleção explícita, sem duplicar
Character Masters e preservando DNA, Masters, referências, assets e histórico.
"""
from __future__ import annotations
import time, uuid
from copy import deepcopy
from armazenamento import _json, _save_json, _slug
from storage_backend import materializar_assets_em_objeto, persistir_assets_em_objeto

INDEX = "character_universe/index.json"
USOS_PADRAO = ["story", "coloring", "activity", "cover"]
VARIAVEIS_PADRAO = [
    "pose", "acao", "expressao", "emocao", "figurino", "acessorios_temporarios",
    "cor_acessorio_identitario", "cenario", "estacao", "festividade",
]
MEL_CANONICAL_COLLECTION = "Pequenas Histórias, Grandes Lições"


def _identidade_referencia(ref: dict) -> tuple[str, str] | None:
    if not isinstance(ref, dict):
        return None
    metadata = ref.get("metadata") if isinstance(ref.get("metadata"), dict) else {}
    asset_library_id = metadata.get("asset_library_id") or ref.get("asset_library_id")
    asset_library_id = str(asset_library_id).strip() if asset_library_id is not None else ""
    if asset_library_id:
        return "asset_library_id", asset_library_id
    for campo in ("asset", "storage_uri", "uri", "caminho_arquivo", "path"):
        valor = ref.get(campo)
        if isinstance(valor, str) and valor.strip():
            return "asset", valor.strip()
    return None


def normalizar_reference_pack(reference_pack: list | None) -> list:
    unicas = []
    identidades = set()
    for ref in reference_pack or []:
        identidade = _identidade_referencia(ref)
        if identidade is not None and identidade in identidades:
            continue
        unicas.append(ref)
        if identidade is not None:
            identidades.add(identidade)
    return unicas


def _index():
    x = _json(INDEX, [])
    return x if isinstance(x, list) else []


def _sync_index_record(personagem: dict) -> None:
    """Mantém o índice alinhado quando nome, coleção ou status mudam."""
    pid = str(personagem.get("id") or "")
    if not pid:
        return
    idx = [dict(item) for item in _index()]
    registro = {
        "id": pid,
        "colecao": personagem.get("colecao", ""),
        "nome": personagem.get("nome", ""),
        "status": personagem.get("status", "oficial"),
    }
    for pos, item in enumerate(idx):
        if str(item.get("id") or "") == pid:
            idx[pos] = registro
            break
    else:
        idx.append(registro)
    _save_json(INDEX, idx)


def normalizar_dna(dna: dict | str | None) -> dict:
    if isinstance(dna, str):
        return {
            "descricao_master": dna,
            "campos_bloqueados": {},
            "caracteristicas_bloqueadas": dna,
            "visual_prompt_master": "",
            "assinaturas_visuais": {},
            "regras_variaveis": {},
            "variaveis_permitidas": list(VARIAVEIS_PADRAO),
        }
    d = deepcopy(dna or {})
    d.setdefault("descricao_master", d.get("caracteristicas_bloqueadas", ""))
    d.setdefault("campos_bloqueados", {})
    d.setdefault("visual_prompt_master", "")
    d.setdefault("assinaturas_visuais", {})
    d.setdefault("regras_variaveis", {})
    d.setdefault("variaveis_permitidas", list(VARIAVEIS_PADRAO))
    return d


def criar_personagem_oficial(colecao: str, nome: str, dna: dict, color_master: str = "", line_art_master: str = "", reference_pack: list | None = None, metadata: dict | None = None) -> dict:
    pid = uuid.uuid4().hex
    meta = deepcopy(metadata or {})
    meta.setdefault("usos_permitidos", list(USOS_PADRAO))
    meta.setdefault("presets", {"figurinos": [], "cenarios": [], "estacoes": [], "festividades": [], "emocoes": []})
    obj = {
        "id": pid, "colecao": colecao, "nome": nome, "status": "oficial",
        "dna": normalizar_dna(dna), "color_master": color_master,
        "line_art_master": line_art_master, "reference_pack": normalizar_reference_pack(reference_pack),
        "metadata": meta, "variacoes": [], "versoes": [],
        "criado_em": int(time.time()), "atualizado_em": int(time.time()),
    }
    obj = persistir_assets_em_objeto(obj, f"assets/character_universe/{_slug(colecao)}/{_slug(nome)}")
    _save_json(f"character_universe/{pid}.json", obj)
    _sync_index_record(obj)
    return materializar_assets_em_objeto(obj)


def listar_personagens_oficiais(colecao: str | None = None, incluir_arquivados: bool = False) -> list[dict]:
    itens = _index()
    if colecao:
        itens = [i for i in itens if i.get("colecao") == colecao]
    if not incluir_arquivados:
        itens = [i for i in itens if i.get("status", "oficial") != "arquivado"]
    return sorted(itens, key=lambda x: (x.get("colecao", ""), x.get("nome", ""), x.get("status", "")))


def buscar_personagens_por_nome(nome: str, incluir_arquivados: bool = False) -> list[dict]:
    """Localiza o mesmo personagem em qualquer coleção sem criar duplicatas."""
    wanted = str(nome or "").strip().casefold()
    if not wanted:
        return []
    return [
        item for item in listar_personagens_oficiais(incluir_arquivados=incluir_arquivados)
        if str(item.get("nome") or "").strip().casefold() == wanted
    ]


def detectar_personagens_mesmo_nome(nome: str | None = None, incluir_arquivados: bool = True) -> dict[str, list[dict]]:
    """Agrupa nomes que aparecem em mais de uma coleção, sem misturar os registros."""
    grupos: dict[str, list[dict]] = {}
    for item in listar_personagens_oficiais(incluir_arquivados=incluir_arquivados):
        item_nome = str(item.get("nome") or "").strip()
        if not item_nome:
            continue
        if nome and item_nome.casefold() != nome.strip().casefold():
            continue
        grupos.setdefault(item_nome.casefold(), []).append(item)
    return {
        chave: valores for chave, valores in grupos.items()
        if len({str(v.get("colecao") or "").strip().casefold() for v in valores}) > 1
    }


def carregar_personagem_oficial(pid: str) -> dict:
    path = f"character_universe/{pid}.json"
    persistido = _json(path, {}) or {}
    if persistido:
        referencias = normalizar_reference_pack(persistido.get("reference_pack", []))
        if referencias != persistido.get("reference_pack", []):
            persistido = deepcopy(persistido)
            persistido["reference_pack"] = referencias
            _save_json(path, persistido)
    obj = materializar_assets_em_objeto(persistido)
    if obj:
        obj["dna"] = normalizar_dna(obj.get("dna"))
        obj.setdefault("status", "oficial")
        obj.setdefault("variacoes", [])
        obj.setdefault("metadata", {})
        obj["metadata"].setdefault("usos_permitidos", list(USOS_PADRAO))
        obj["metadata"].setdefault("presets", {"figurinos": [], "cenarios": [], "estacoes": [], "festividades": [], "emocoes": []})
        obj["metadata"].setdefault("master_history", [])
        obj["metadata"].setdefault("current_master_asset_ids", {})
        obj.setdefault("reference_pack", [])
        obj.setdefault("color_master", "")
        obj.setdefault("line_art_master", "")
    return obj


def _tem_historico_character_master(p: dict) -> bool:
    metadata = p.get("metadata") or {}
    return bool(
        p.get("color_master") or p.get("line_art_master") or p.get("reference_pack")
        or p.get("variacoes") or p.get("versoes") or metadata.get("master_history")
        or metadata.get("current_master_asset_ids")
    )


def mel_canonica_protegida(p: dict) -> bool:
    return (
        str(p.get("nome") or "").strip().casefold() == "mel"
        and str(p.get("colecao") or "").strip() == MEL_CANONICAL_COLLECTION
        and bool(p.get("color_master"))
        and bool(p.get("reference_pack"))
        and p.get("status", "oficial") != "arquivado"
    )


def validar_exclusao_permanente(pid: str, confirmacao_explicita: bool = False) -> bool:
    """Safety gate para qualquer futura exclusão física de Character Master."""
    p = carregar_personagem_oficial(pid)
    if not p:
        raise KeyError(pid)
    if _tem_historico_character_master(p) and not confirmacao_explicita:
        raise PermissionError("Character Master com histórico exige confirmação explícita para exclusão permanente.")
    return True


def arquivar_personagem(pid: str) -> dict:
    """Arquiva sem apagar DNA, Masters, referências, assets, versões ou histórico."""
    p = carregar_personagem_oficial(pid)
    if not p:
        raise KeyError(pid)
    if mel_canonica_protegida(p):
        raise PermissionError("A Mel canônica de Pequenas Histórias, Grandes Lições possui Color Master e Reference Pack oficiais e deve permanecer ativa.")
    if p.get("status") == "arquivado":
        return p
    metadata = deepcopy(p.get("metadata") or {})
    metadata["arquivado_em"] = int(time.time())
    return atualizar_personagem_oficial(pid, {"status": "arquivado", "metadata": metadata})


def restaurar_personagem(pid: str) -> dict:
    p = carregar_personagem_oficial(pid)
    if not p:
        raise KeyError(pid)
    metadata = deepcopy(p.get("metadata") or {})
    metadata.pop("arquivado_em", None)
    return atualizar_personagem_oficial(pid, {"status": "oficial", "metadata": metadata})


def atualizar_personagem_oficial(pid: str, novos: dict) -> dict:
    atual = _json(f"character_universe/{pid}.json", {}) or {}
    if not atual:
        raise KeyError(pid)
    snapshot = {k: v for k, v in atual.items() if k != "versoes"}
    atual.setdefault("versoes", []).append({"salvo_em": int(time.time()), "snapshot": snapshot})
    novos = deepcopy(novos)
    if "dna" in novos:
        novos["dna"] = normalizar_dna(novos["dna"])
    if "reference_pack" in novos:
        novos["reference_pack"] = normalizar_reference_pack(novos["reference_pack"])
    atual.update(novos)
    atual["atualizado_em"] = int(time.time())
    atual = persistir_assets_em_objeto(atual, f"assets/character_universe/{_slug(atual.get('colecao',''))}/{_slug(atual.get('nome',''))}")
    _save_json(f"character_universe/{pid}.json", atual)
    _sync_index_record(atual)
    return materializar_assets_em_objeto(atual)


def mover_personagem_para_colecao(pid: str, nova_colecao: str, *, confirmacao_explicita: bool = False, motivo: str = "correcao_manual") -> dict:
    """Move o MESMO Character Master para outra coleção, preservando identidade e histórico.

    Não duplica personagem. Exige confirmação explícita e bloqueia colisão de nome
    na coleção de destino. A Mel canônica protegida não pode ser movida.
    """
    destino = str(nova_colecao or "").strip()
    if not destino:
        raise ValueError("Selecione uma coleção de destino.")
    personagem = carregar_personagem_oficial(pid)
    if not personagem:
        raise KeyError(pid)
    origem = str(personagem.get("colecao") or "").strip()
    if origem == destino:
        return personagem
    if mel_canonica_protegida(personagem):
        raise PermissionError("A Mel canônica protegida não pode ser movida para outra coleção.")
    if not confirmacao_explicita:
        raise PermissionError("Mover um Character Master entre coleções exige confirmação explícita.")
    nome = str(personagem.get("nome") or "").strip()
    colisao = [
        item for item in buscar_personagens_por_nome(nome, incluir_arquivados=False)
        if str(item.get("id") or "") != str(pid)
        and str(item.get("colecao") or "").strip() == destino
    ]
    if colisao:
        raise ValueError(f"Já existe um Character Master ativo chamado {nome} na coleção {destino}. Resolva a duplicidade antes de mover.")
    metadata = deepcopy(personagem.get("metadata") or {})
    history = list(metadata.get("collection_history") or [])
    history.append({
        "de": origem,
        "para": destino,
        "movido_em": int(time.time()),
        "motivo": str(motivo or "correcao_manual"),
    })
    metadata["collection_history"] = history
    metadata["colecao_corrigida_manualmente"] = True
    return atualizar_personagem_oficial(pid, {"colecao": destino, "metadata": metadata})


def adicionar_variacao(pid: str, tipo: str, instrucao: str, asset: str = "", metadata: dict | None = None, aprovada: bool = False) -> dict:
    p = carregar_personagem_oficial(pid)
    if not p: raise KeyError(pid)
    v = {"id": uuid.uuid4().hex, "tipo": tipo, "instrucao": instrucao, "asset": asset,
         "metadata": metadata or {}, "aprovada": bool(aprovada), "criada_em": int(time.time())}
    p.setdefault("variacoes", []).append(v)
    atualizar_personagem_oficial(pid, {"variacoes": p["variacoes"]})
    return v


def aprovar_variacao(pid: str, variacao_id: str) -> dict:
    p = carregar_personagem_oficial(pid)
    vars_ = p.get("variacoes", [])
    for v in vars_:
        if v.get("id") == variacao_id: v["aprovada"] = True
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
    visual_prompt = str(dna.get("visual_prompt_master") or "").strip()
    regras_variaveis = dna.get("regras_variaveis") or {}
    regras_ativas = {k: regras_variaveis[k] for k in filtradas if k in regras_variaveis}
    texto = (f"PERSONAGEM OFICIAL {p.get('nome')}. CHARACTER DNA BLOQUEADO: {campos}. "
        f"Preserve rigorosamente rosto, espécie, proporções fundamentais, olhos, marcas, paleta-base e identidade visual. "
        f"Modo visual: {modo}; uso: {contexto}. Variáveis autorizadas nesta cena: {filtradas}. "
        "Roupas, pose, ação, cenário, estação, festividade, expressão e acessórios temporários podem mudar SOMENTE quando autorizados; "
        "a identidade não muda. A cor de um acessório identitário só pode mudar quando `cor_acessorio_identitario` estiver autorizada; "
        "sua presença, forma e posição canônicas permanecem bloqueadas.")
    if visual_prompt: texto += f" PROMPT MESTRE VISUAL OFICIAL: {visual_prompt}"
    if regras_ativas: texto += f" Regras específicas das variáveis ativas: {regras_ativas}."
    if proibidas: texto += f" Ignorar alterações não autorizadas nos campos: {proibidas}."
    return texto


def adicionar_referencia(pid: str, asset: str, tipo: str = "cena", origem: str = "book_doctor", metadata: dict | None = None) -> dict:
    p = carregar_personagem_oficial(pid)
    if not p: raise KeyError(pid)
    refs = list(p.get("reference_pack", []) or [])
    item = {"id": uuid.uuid4().hex, "asset": asset, "tipo": tipo, "origem": origem,
            "metadata": metadata or {}, "criada_em": int(time.time())}
    if _identidade_referencia(item) in {_identidade_referencia(ref) for ref in refs}:
        return p
    refs.append(item)
    return atualizar_personagem_oficial(pid, {"reference_pack": refs})


def definir_master_visual(pid: str, asset: str, modo: str = "color") -> dict:
    if modo not in {"color", "line_art"}: raise ValueError("modo deve ser 'color' ou 'line_art'")
    campo = "color_master" if modo == "color" else "line_art_master"
    return atualizar_personagem_oficial(pid, {campo: asset})

"""FaithBloom 2.0 — persistência de projetos, personagens, galeria e marca.

A API pública deste módulo foi mantida para não quebrar as telas existentes.
Por baixo, os dados usam storage_backend.py:
- local no desenvolvimento;
- Supabase Storage no Streamlit Cloud, quando configurado.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from storage_backend import (
    BACKEND, backend_status, is_storage_uri, materializar,
    materializar_assets_em_objeto, persistir_arquivo, persistir_assets_em_objeto,
    storage_uri,
)
from stable_hardening import ensure_project_schema


def _slug(titulo: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (titulo or "").lower()).strip("-")
    return slug or "sem-titulo"


def _json(path: str, default):
    return BACKEND.get_json(path, default)


def _save_json(path: str, data) -> str:
    BACKEND.put_json(path, data)
    return path


def salvar_livro(state: dict) -> str:
    state = ensure_project_schema(dict(state))
    colecao_slug = _slug(state.get("colecao", "sem-colecao"))
    slug = _slug(state.get("titulo", ""))
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = f"livros/{colecao_slug}/{slug}-{timestamp}.json"
    serializavel = persistir_assets_em_objeto(dict(state), f"assets/livros/{colecao_slug}/{slug}")
    _save_json(path, serializavel)
    if state.get("personagens"):
        atualizar_biblioteca_personagens(state.get("colecao", "sem-colecao"), state["personagens"])
    return storage_uri(path)


def atualizar_livro_salvo(storage_path: str, state: dict) -> str:
    """Atualiza explicitamente um projeto salvo no MESMO caminho.

    Usado por telas editoriais que precisam persistir metadados estruturados
    (ex.: autoria). Não cria uma nova versão e nunca é chamado silenciosamente.
    """
    if not storage_path:
        raise ValueError("storage_path do projeto não foi informado.")
    path = storage_path.replace("fb://", "", 1).strip("/")
    if not path.startswith("livros/") or not path.endswith(".json"):
        raise ValueError("Somente projetos Story Book existentes podem ser atualizados por esta função.")
    state = ensure_project_schema(dict(state))
    serializavel = persistir_assets_em_objeto(dict(state), f"assets/livros/{_slug(state.get('colecao','sem-colecao'))}/{_slug(state.get('titulo',''))}")
    _save_json(path, serializavel)
    return storage_uri(path)


def listar_livros(colecao: str | None = None) -> list[dict]:
    prefix = f"livros/{_slug(colecao)}" if colecao else "livros"
    itens = []
    for path in reversed(BACKEND.list(prefix)):
        if not path.endswith(".json"):
            continue
        dados = _json(path, {}) or {}
        itens.append({
            "arquivo": path.split("/")[-1],
            "storage_path": path,
            "colecao": dados.get("colecao", ""),
            "titulo": dados.get("titulo", "(sem título)"),
            "pacote_pronto": dados.get("pacote_pronto", False),
        })
    return itens


def carregar_livro(colecao: str, nome_arquivo: str) -> dict:
    path = nome_arquivo if "/" in nome_arquivo else f"livros/{_slug(colecao)}/{nome_arquivo}"
    dados = _json(path, {}) or {}
    # Compatibilidade: projetos antigos são migrados apenas na cópia carregada.
    # A versão persistida só muda quando a autora salvar explicitamente uma nova versão.
    dados = ensure_project_schema(dados)
    return materializar_assets_em_objeto(dados)


def listar_colecoes() -> list[str]:
    nomes = set()
    for livro in listar_livros():
        if livro.get("colecao"):
            nomes.add(livro["colecao"])
    # bibliotecas podem existir antes de um livro finalizado
    for path in BACKEND.list("bibliotecas_personagens"):
        if path.endswith(".json"):
            dados = _json(path, {}) or {}
            nome = dados.get("_colecao_nome") if isinstance(dados, dict) else None
            if nome:
                nomes.add(nome)
    return sorted(nomes)


def atualizar_biblioteca_personagens(colecao: str, personagens: dict) -> None:
    path = f"bibliotecas_personagens/{_slug(colecao)}.json"
    biblioteca = _json(path, {}) or {}
    biblioteca.pop("_colecao_nome", None)
    incoming = persistir_assets_em_objeto(personagens, f"assets/personagens/{_slug(colecao)}")
    biblioteca.update(incoming)
    biblioteca["_colecao_nome"] = colecao
    _save_json(path, biblioteca)


def carregar_biblioteca_personagens(colecao: str) -> dict:
    path = f"bibliotecas_personagens/{_slug(colecao)}.json"
    biblioteca = _json(path, {}) or {}
    if isinstance(biblioteca, dict):
        biblioteca.pop("_colecao_nome", None)
    return materializar_assets_em_objeto(biblioteca)


def salvar_asset_marca(colecao: str, tipo: str, conteudo_bytes: bytes) -> str:
    path = f"marca_colecoes/{_slug(colecao)}/{tipo}.png"
    BACKEND.put_bytes(path, conteudo_bytes, "image/png")
    return materializar(storage_uri(path))


def carregar_asset_marca(colecao: str, tipo: str) -> str | None:
    path = f"marca_colecoes/{_slug(colecao)}/{tipo}.png"
    if not BACKEND.exists(path):
        return None
    return materializar(storage_uri(path))


def salvar_livro_colorir(state: dict) -> str:
    state = ensure_project_schema(dict(state))
    slug = _slug(state.get("titulo", ""))
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    path = f"livros_colorir/{slug}-{timestamp}.json"
    serializavel = persistir_assets_em_objeto(dict(state), f"assets/colorir/{slug}")
    _save_json(path, serializavel)
    return storage_uri(path)


def atualizar_livro_colorir_salvo(storage_path: str, state: dict) -> str:
    """Atualiza explicitamente um Coloring Book já salvo, preservando o caminho."""
    if not storage_path:
        raise ValueError("storage_path do Coloring Book não foi informado.")
    path = storage_path.replace("fb://", "", 1).strip("/")
    if not path.startswith("livros_colorir/") or not path.endswith(".json"):
        raise ValueError("Caminho não corresponde a um Coloring Book salvo.")
    state = ensure_project_schema(dict(state))
    serializavel = persistir_assets_em_objeto(dict(state), f"assets/colorir/{_slug(state.get('titulo',''))}")
    _save_json(path, serializavel)
    return storage_uri(path)


def listar_livros_colorir() -> list[dict]:
    livros = []
    for path in reversed(BACKEND.list("livros_colorir")):
        if not path.endswith(".json"):
            continue
        dados = _json(path, {}) or {}
        livros.append({"arquivo": path.split("/")[-1], "storage_path": path, "titulo": dados.get("titulo", "(sem título)"), "tema_geral": dados.get("tema_geral", "")})
    return livros


def carregar_livro_colorir(nome_arquivo: str) -> dict:
    path = nome_arquivo if "/" in nome_arquivo else f"livros_colorir/{nome_arquivo}"
    dados = ensure_project_schema(_json(path, {}) or {})
    return materializar_assets_em_objeto(dados)


def temas_colorir_usados() -> list[str]:
    return [l["titulo"] for l in listar_livros_colorir()]


# ------------------------- Galeria permanente -------------------------
GALERIA_INDEX = "galeria/index.json"


def _ler_indice_galeria() -> list[dict]:
    dados = _json(GALERIA_INDEX, [])
    return dados if isinstance(dados, list) else []


def _salvar_indice_galeria(itens: list[dict]) -> None:
    _save_json(GALERIA_INDEX, itens)


def salvar_na_galeria(caminho_origem: str, nome: str, tipo: str = "personagem", tags: list[str] | None = None, metadata: dict | None = None) -> dict:
    """Salva um asset no catálogo visual sem duplicar bytes idênticos.

    O índice continua compatível com as telas antigas, mas já nasce com os
    campos do Asset Library & Media Manager (Refinamento 16). Se a mesma URI
    já existir, apenas une tags/metadados e reutiliza o registro.
    """
    if not caminho_origem:
        raise FileNotFoundError("Nenhuma imagem foi informada.")
    if is_storage_uri(caminho_origem):
        uri = caminho_origem
    else:
        if not os.path.exists(caminho_origem):
            raise FileNotFoundError("A imagem escolhida não existe nesta sessão.")
        uri = persistir_arquivo(caminho_origem, "assets/galeria")
    agora = int(time.time())
    itens = _ler_indice_galeria()
    existente = next((x for x in itens if x.get("storage_uri") == uri), None)
    if existente:
        existente["tags"] = sorted(set([*existente.get("tags", []), *[t for t in (tags or []) if t]]))
        merged = dict(existente.get("metadata") or {}); merged.update(metadata or {})
        existente["metadata"] = merged
        existente["atualizada_em"] = agora
        existente["status"] = "active"
        existente.setdefault("asset_schema_version", 2)
        existente.setdefault("status", "active")
        existente.setdefault("master_roles", [])
        existente.setdefault("virtual_collections", [])
        existente.setdefault("version_group", existente.get("id"))
        existente.setdefault("version_label", "Original")
        existente.setdefault("approved", bool(merged.get("aprovada", False)))
        _salvar_indice_galeria(itens)
        return {**existente, "caminho_arquivo": materializar(uri)}
    ext = Path(uri[5:] if is_storage_uri(uri) else uri).suffix.lower()
    media_kind = "image" if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"} else ("svg" if ext == ".svg" else ("pdf" if ext == ".pdf" else ("audio" if ext in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"} else "other")))
    item_id = uuid.uuid4().hex
    item = {
        "id": item_id,
        "nome": nome or "Imagem sem nome",
        "tipo": tipo,
        "tags": sorted(set(t for t in (tags or []) if t)),
        "storage_uri": uri,
        "metadata": metadata or {},
        "favorita": False,
        "criada_em": agora,
        "atualizada_em": agora,
        "status": "active",
        "asset_schema_version": 2,
        "master_roles": [],
        "virtual_collections": [],
        "version_group": item_id,
        "version_label": "Original",
        "parent_asset_id": "",
        "approved": bool((metadata or {}).get("aprovada", False)),
        "locked_original": bool((metadata or {}).get("original_publicado", False)),
        "media_kind": media_kind,
    }
    itens.append(item); _salvar_indice_galeria(itens)
    return {**item, "caminho_arquivo": materializar(uri)}


def listar_galeria(tipo: str | None = None, somente_favoritas: bool = False, busca: str = "") -> list[dict]:
    """Lista assets ativos para compatibilidade com todos os Studios antigos."""
    itens = [i for i in _ler_indice_galeria() if i.get("status", "active") != "archived"]
    if tipo:
        itens = [i for i in itens if i.get("tipo") == tipo]
    if somente_favoritas:
        itens = [i for i in itens if i.get("favorita")]
    q = busca.strip().lower()
    if q:
        def blob(i):
            m = i.get("metadata") or {}
            vals = [i.get("nome", ""), *i.get("tags", []), i.get("tipo", ""), m.get("personagem", ""), m.get("colecao", ""), m.get("livro", ""), m.get("emocao", ""), m.get("estacao", ""), m.get("festividade", "")]
            return " ".join(str(x) for x in vals).lower()
        tokens = [x for x in q.split() if x]
        itens = [i for i in itens if all(t in blob(i) for t in tokens)]
    out = []
    for item in sorted(itens, key=lambda i: i.get("criada_em", 0), reverse=True):
        uri = item.get("storage_uri") or item.get("caminho_arquivo", "")
        caminho = ""
        if uri:
            try: caminho = materializar(uri)
            except Exception: caminho = uri
        out.append({**item, "caminho_arquivo": caminho})
    return out


def favoritar_item_galeria(item_id: str, favorita: bool = True) -> None:
    itens = _ler_indice_galeria()
    for item in itens:
        if item.get("id") == item_id:
            item["favorita"] = bool(favorita); break
    _salvar_indice_galeria(itens)


def excluir_item_galeria(item_id: str, excluir_arquivo: bool = True) -> bool:
    itens = _ler_indice_galeria(); alvo = next((i for i in itens if i.get("id") == item_id), None)
    if not alvo: return False
    if excluir_arquivo and is_storage_uri(alvo.get("storage_uri", "")):
        try: BACKEND.delete(alvo["storage_uri"][5:])
        except Exception: pass
    _salvar_indice_galeria([i for i in itens if i.get("id") != item_id])
    return True


def estatisticas_armazenamento() -> dict:
    return {
        **backend_status(),
        "livros": len(listar_livros()),
        "livros_colorir": len(listar_livros_colorir()),
        "colecoes": len(listar_colecoes()),
        "galeria": len(_ler_indice_galeria()),
    }


def migrar_dados_locais_legados() -> dict:
    """Importa pastas da V1/V2 local para o backend atual. Seguro para rodar mais de uma vez."""
    resumo = {"json": 0, "assets": 0, "erros": []}
    mappings = [
        ("livros_salvos", "livros"), ("livros_colorir_salvos", "livros_colorir"),
        ("bibliotecas_personagens", "bibliotecas_personagens"), ("marca_colecoes", "marca_colecoes"),
    ]
    for src_root, dest_root in mappings:
        base = Path(src_root)
        if not base.exists(): continue
        for p in base.rglob("*"):
            if not p.is_file(): continue
            rel = p.relative_to(base).as_posix(); dest = f"{dest_root}/{rel}"
            try:
                BACKEND.put_bytes(dest, p.read_bytes())
                resumo["json" if p.suffix.lower()==".json" else "assets"] += 1
            except Exception as e: resumo["erros"].append(f"{p}: {e}")
    # galeria antiga: converte index + arquivos para o novo formato
    old_index = Path("galeria_imagens/index.json")
    if old_index.exists():
        try:
            old = json.loads(old_index.read_text(encoding="utf-8"))
            existentes = {i.get("id") for i in _ler_indice_galeria()}
            novos = _ler_indice_galeria()
            for item in old if isinstance(old, list) else []:
                if item.get("id") in existentes: continue
                path = item.get("caminho_arquivo", "")
                if path and Path(path).exists():
                    uri = persistir_arquivo(path, "assets/galeria")
                    item = {k:v for k,v in item.items() if k != "caminho_arquivo"}; item["storage_uri"] = uri
                    novos.append(item); resumo["assets"] += 1
            _salvar_indice_galeria(novos)
        except Exception as e: resumo["erros"].append(f"galeria: {e}")
    return resumo

"""
Persistência simples e local dos livros gerados - um passo intermediário
antes de um banco de dados de verdade (Postgres + storage, ver roadmap
no README). Salva o estado final de cada livro como um arquivo JSON,
para não perder o trabalho quando a sessão do Streamlit fechar.

Limitação importante: isso NÃO substitui um banco de dados multiusuário
- é só um "salvar em disco" local, útil pra uso individual enquanto o
motor é validado. Quando o projeto virar SaaS de verdade (ver roadmap),
isso deve ser trocado por uma tabela real.
"""

import json
import os
import re
import time

PASTA_LIVROS = "livros_salvos"
os.makedirs(PASTA_LIVROS, exist_ok=True)

PASTA_BIBLIOTECAS = "bibliotecas_personagens"
os.makedirs(PASTA_BIBLIOTECAS, exist_ok=True)


def _slug(titulo: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", titulo.lower()).strip("-")
    return slug or "sem-titulo"


def salvar_livro(state: dict) -> str:
    """Salva o estado final do livro como JSON, dentro da pasta da coleção."""
    colecao_slug = _slug(state.get("colecao", "sem-colecao"))
    pasta_colecao = os.path.join(PASTA_LIVROS, colecao_slug)
    os.makedirs(pasta_colecao, exist_ok=True)

    slug = _slug(state.get("titulo", ""))
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    caminho = os.path.join(pasta_colecao, f"{slug}-{timestamp}.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    # Toda vez que um livro é salvo, a biblioteca de personagens da
    # coleção é atualizada - assim os personagens ficam disponíveis
    # pros próximos livros da MESMA coleção, sem vazar pra outras.
    if state.get("personagens"):
        atualizar_biblioteca_personagens(state.get("colecao", "sem-colecao"), state["personagens"])

    return caminho


def listar_livros(colecao: str | None = None) -> list[dict]:
    """Lista os livros salvos, do mais recente para o mais antigo. Filtra por coleção se informado."""
    livros = []
    pastas = [colecao] if colecao else os.listdir(PASTA_LIVROS)
    for nome_pasta in pastas:
        pasta_colecao = os.path.join(PASTA_LIVROS, _slug(nome_pasta))
        if not os.path.isdir(pasta_colecao):
            continue
        for nome_arquivo in sorted(os.listdir(pasta_colecao), reverse=True):
            if nome_arquivo.endswith(".json"):
                with open(os.path.join(pasta_colecao, nome_arquivo), encoding="utf-8") as f:
                    dados = json.load(f)
                livros.append({
                    "arquivo": nome_arquivo,
                    "colecao": dados.get("colecao", ""),
                    "titulo": dados.get("titulo", "(sem título)"),
                    "pacote_pronto": dados.get("pacote_pronto", False),
                })
    return livros


def carregar_livro(colecao: str, nome_arquivo: str) -> dict:
    caminho = os.path.join(PASTA_LIVROS, _slug(colecao), nome_arquivo)
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def listar_colecoes() -> list[str]:
    """Nomes das coleções que já têm pelo menos um livro salvo."""
    if not os.path.isdir(PASTA_LIVROS):
        return []
    return sorted(os.listdir(PASTA_LIVROS))


def atualizar_biblioteca_personagens(colecao: str, personagens: dict) -> None:
    """Funde os personagens deste livro na biblioteca permanente da coleção."""
    caminho = os.path.join(PASTA_BIBLIOTECAS, f"{_slug(colecao)}.json")
    biblioteca = {}
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            biblioteca = json.load(f)
    biblioteca.update(personagens)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(biblioteca, f, ensure_ascii=False, indent=2)


def carregar_biblioteca_personagens(colecao: str) -> dict:
    """Retorna os personagens já cadastrados nesta coleção (ex: Mel, Téo, Manu)."""
    caminho = os.path.join(PASTA_BIBLIOTECAS, f"{_slug(colecao)}.json")
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)

"""
Estado de um projeto de LIVRO DE COLORIR - mais simples que o
LivroState (não tem roteiro, dedicatória, tradução, audiobook: é só
tema visual + páginas + capa).
"""

from typing import TypedDict


class PaginaColorir(TypedDict, total=False):
    nome: str           # ex: "Leãozinho no campo", "Avião de resgate", "Princesa da Lua"
    categoria: str       # ex: "leão", "avião", "princesa" - o tipo de sujeito
    sexo: str            # "macho", "femea", ou "" se o tema não usa distinção
    cena: str            # descrição da cena/pose
    caminho_arquivo: str # preenchido depois de gerada


class LivroColorirState(TypedDict, total=False):
    titulo: str
    colecao: str                       # nome da marca/selo, se ela quiser reaproveitar entre livros de colorir
    tema_geral: str
    precisa_codigo_sexo: bool
    trim_largura_in: float             # padrão 8.5
    trim_altura_in: float              # padrão 8.5
    paginas: list[PaginaColorir]

    # Capa e contracapa - arquivos SEPARADOS do miolo, igual nos livros
    # de história (ver agents/capa.py) - eBook e físico são diferentes.
    capa_ebook: str
    capa_fisica_wrap: str
    capa_fisica_dimensoes: dict

    # Diagramador (ver agents/diagramador_colorir.py)
    layout_paginas: list[dict]
    paginas_fisicas_total: int
    checklist_kdp: dict

    pacote_pronto: bool

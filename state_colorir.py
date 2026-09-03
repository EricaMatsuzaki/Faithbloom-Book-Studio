"""Estado do Coloring Book Studio do FaithBloom 2.0."""
from typing import TypedDict


class VariacaoLineArt(TypedDict, total=False):
    id: str
    caminho_arquivo: str
    origem: str
    prompt: str
    base: str
    favorita: bool


class PaginaColorir(TypedDict, total=False):
    nome: str
    categoria: str
    sexo: str
    cena: str
    origem: str  # gerar_ia | imagem_enviada | foto_real | prompt_livre | galeria | biblioteca_personagem
    caminho_foto_original: str
    caminho_imagem_enviada: str
    prompt_livre: str
    prompt_adicional: str
    personagem_nome: str
    imagem_referencia: str
    galeria_item_id: str
    preset_id: str
    caminho_arquivo: str
    variacoes: list[VariacaoLineArt]
    variacao_selecionada_id: str
    aprovada: bool
    status: str


class LivroColorirState(TypedDict, total=False):
    titulo: str
    autora: str                    # compatibilidade; derivada da autoria estruturada quando houver
    authorship: dict               # autores/coautores/contribuidores deste Coloring Book
    colecao: str
    tema_geral: str
    publico: str
    faixa_etaria: str
    preset_padrao_id: str
    precisa_codigo_sexo: bool
    trim_largura_in: float
    trim_altura_in: float
    paginas: list[PaginaColorir]
    capa_ebook: str
    capa_fisica_wrap: str
    capa_fisica_dimensoes: dict
    layout_paginas: list[dict]
    paginas_fisicas_total: int
    checklist_kdp: dict
    pacote_pronto: bool

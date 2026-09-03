"""FaithBloom Coloring Book Studio — geração e conversão de Line Art.

Suporta geração do zero, prompt livre, imagem/foto enviada, Galeria e
Biblioteca de Personagens. O estilo é controlado por presets reutilizáveis.
Nunca apaga a imagem-base: novas tentativas viram variações.
"""
from __future__ import annotations

import time
import uuid

from coloring_presets import preset_para_prompt
from agent_skills import skill_contract

CODIGO_VISUAL_SEXO = {
    "macho": (
        "Olhos redondos grandes com 2 pontos de brilho, sem cílios. "
        "Bochechas com círculo tracejado. Sem laço por padrão."
    ),
    "femea": (
        "Olhos redondos grandes com 2 pontos de brilho, cílios finos. "
        "Bochechas em formato de coração e um laço característico."
    ),
}

BASE_TECNICA_LINE_ART = (
    "Página de livro de colorir em preto e branco puro. Apenas linhas pretas limpas; "
    "sem preenchimento de cor, sem cinza, sem sombreado, sem hachura e sem textura pintada. "
    "Contornos e áreas devem ser fechados e utilizáveis para colorir. Composição original, "
    "sem copiar a identidade visual de artistas, marcas ou livros específicos."
)


def prompt_pagina_colorir(
    nome_sujeito: str,
    categoria: str,
    cena: str,
    sexo: str | None = None,
    preset: dict | None = None,
    prompt_livre: str = "",
    instrucao_extra: str = "",
    transformar_referencia: bool = False,
) -> str:
    partes = [BASE_TECNICA_LINE_ART]
    if preset:
        partes.append(preset_para_prompt(preset, instrucao_extra))
    elif instrucao_extra:
        partes.append(instrucao_extra)

    if prompt_livre.strip():
        partes.append("Pedido livre da autora: " + prompt_livre.strip())
    else:
        partes.append(f"Assunto: {nome_sujeito} ({categoria}).")
        if sexo in CODIGO_VISUAL_SEXO:
            partes.append(f"Código visual ({sexo}): {CODIGO_VISUAL_SEXO[sexo]}")
        partes.append(f"Cena: {cena}")

    if transformar_referencia:
        partes.append(
            "Use a imagem de referência como base visual. Preserve o sujeito, pose e elementos "
            "importantes reconhecíveis, mas REINTERPRETE a cena como line art própria para colorir; "
            "não aplique apenas filtro de bordas e não destrua o arquivo original."
        )
    return "\n".join(p for p in partes if p) + skill_contract("line_art_specialist", compact=True)


def gerar_pagina_colorir(
    nome_sujeito: str,
    categoria: str,
    cena: str,
    gerar_imagem,
    sexo: str | None = None,
    imagem_referencia: str | None = None,
    preset: dict | None = None,
    prompt_livre: str = "",
    instrucao_extra: str = "",
    transformar_referencia: bool = False,
) -> str:
    prompt = prompt_pagina_colorir(
        nome_sujeito, categoria, cena, sexo, preset, prompt_livre,
        instrucao_extra, transformar_referencia,
    )
    return gerar_imagem(prompt=prompt, imagem_base=imagem_referencia)


def criar_registro_variacao(caminho: str, origem: str, prompt: str = "", base: str = "") -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "caminho_arquivo": caminho,
        "origem": origem,
        "prompt": prompt,
        "base": base,
        "favorita": False,
        "criada_em": int(time.time()),
    }


def gerar_variacao_line_art(
    pagina: dict,
    gerar_imagem,
    preset: dict | None = None,
    instrucao: str = "",
    base_escolhida: str | None = None,
) -> dict:
    base = base_escolhida or pagina.get("caminho_arquivo") or pagina.get("imagem_referencia")
    prompt = prompt_pagina_colorir(
        pagina.get("nome", ""), pagina.get("categoria", ""), pagina.get("cena", ""),
        pagina.get("sexo") or None, preset, pagina.get("prompt_livre", ""), instrucao,
        transformar_referencia=bool(base),
    )
    caminho = gerar_imagem(prompt=prompt, imagem_base=base)
    return criar_registro_variacao(caminho, "variacao", prompt=prompt, base=base or "")


def prompt_capa_colorida(sujeitos_destaque: list[dict], titulo: str) -> str:
    descricoes = []
    for s in sujeitos_destaque:
        linha = f"{s['nome']} ({s['categoria']})"
        if s.get("sexo") in CODIGO_VISUAL_SEXO:
            linha += f": {CODIGO_VISUAL_SEXO[s['sexo']]}"
        descricoes.append(linha)
    return (
        "Capa colorida original para livro de colorir, coerente com a line art do miolo: "
        "formas limpas, cores planas, proporção consistente, sem imitar artista ou marca específica.\n"
        + "\n".join(descricoes) + f'\nTítulo: "{titulo}".'
    )


def gerar_capa_colorida(sujeitos_destaque: list[dict], titulo: str, gerar_imagem, imagem_referencia: str | None = None) -> str:
    return gerar_imagem(prompt=prompt_capa_colorida(sujeitos_destaque, titulo), imagem_base=imagem_referencia)

# ---------------------------------------------------------------------
# Capa e contracapa SEPARADAS (eBook vs. livro físico), reaproveitando
# a mesma infraestrutura de cálculo da KDP e composição de marca via
# PIL que já existe pra livros de história (ver agents/capa.py e
# marca.py) - só troca o estilo visual de fundo pra vetor/colorir.
# ---------------------------------------------------------------------

from kdp_rules import calcular_dimensoes_capa_fisica, dimensoes_capa_ebook_px
from marca import aplicar_faixa_colecao, aplicar_selo_colecao
from armazenamento import carregar_asset_marca

TRIM_LARGURA_IN_PADRAO = 8.5
TRIM_ALTURA_IN_PADRAO = 8.5


def prompt_arte_capa_frontal_colorir(sujeitos_destaque: list[dict]) -> str:
    """Só a cena (sem título/faixa - isso entra depois via PIL)."""
    descricoes = []
    for s in sujeitos_destaque:
        linha = f"{s['nome']} ({s['categoria']})"
        if s.get("sexo"):
            linha += f": {CODIGO_VISUAL_SEXO[s['sexo']]}"
        descricoes.append(linha)
    return (
        "Capa de livro de colorir infantil, VERSÃO COLORIDA no MESMO "
        "estilo vetor simples e fofo do miolo (contorno grosso, cores "
        "lisas/planas) - NUNCA aquarela/pintura/textura rica. SEM "
        "nenhum texto, título ou logotipo na imagem (será adicionado "
        "depois separadamente). Sujeitos em destaque, centralizados, "
        "espaço livre na parte superior para posterior título:\n"
        + "\n".join(descricoes)
    )


def gerar_capa_ebook_colorir(state: dict, gerar_imagem) -> str:
    trim_l = state.get("trim_largura_in") or TRIM_LARGURA_IN_PADRAO
    trim_a = state.get("trim_altura_in") or TRIM_ALTURA_IN_PADRAO
    dimensoes = dimensoes_capa_ebook_px(trim_l, trim_a)

    sujeitos_destaque = [
        {"nome": p["nome"], "categoria": p.get("categoria", ""), "sexo": p.get("sexo") or None}
        for p in state.get("paginas", [])[:3]
    ]
    imagem_referencia = state["paginas"][0]["caminho_arquivo"] if state.get("paginas") else None

    prompt = prompt_arte_capa_frontal_colorir(sujeitos_destaque) + (
        f" Gerar em {dimensoes['largura_px']}x{dimensoes['altura_px']} pixels."
    )
    caminho_arte = gerar_imagem(prompt=prompt, imagem_base=imagem_referencia)

    faixa_png = carregar_asset_marca(state.get("colecao", state.get("titulo", "")), "faixa")
    return aplicar_faixa_colecao(caminho_arte, state.get("colecao", ""), faixa_png)


def gerar_capa_fisica_wrap_colorir(state: dict, gerar_imagem) -> dict:
    trim_l = state.get("trim_largura_in") or TRIM_LARGURA_IN_PADRAO
    trim_a = state.get("trim_altura_in") or TRIM_ALTURA_IN_PADRAO
    # Usa a contagem real calculada pelo Diagramador (ver
    # agents/diagramador_colorir.py) - roda esse nó ANTES de gerar a
    # capa física, senão cai no valor aproximado como fallback.
    paginas_fisicas = state.get("paginas_fisicas_total") or (len(state.get("paginas", [])) + 4)
    dimensoes = calcular_dimensoes_capa_fisica(trim_l, trim_a, paginas_fisicas)

    sujeitos_destaque = [
        {"nome": p["nome"], "categoria": p.get("categoria", ""), "sexo": p.get("sexo") or None}
        for p in state.get("paginas", [])[:3]
    ]
    imagem_referencia = state["paginas"][0]["caminho_arquivo"] if state.get("paginas") else None

    prompt = (
        f"{prompt_arte_capa_frontal_colorir(sujeitos_destaque)}\n"
        f"Canvas do wraparound completo (contracapa + lombada + capa): "
        f"{dimensoes['largura_total_px']}x{dimensoes['altura_total_px']} px, "
        f"{dimensoes['dpi']} DPI, sangria de 0.125\" nas bordas externas. "
        f"Lombada de {dimensoes['largura_lombada_in']}\" entre contracapa e capa. "
        "Contracapa (lado esquerdo) mais simples/discreta, com espaço "
        "reservado para texto de sinopse e para o código de barras."
    )
    caminho_arte = gerar_imagem(prompt=prompt, imagem_base=imagem_referencia)

    faixa_png = carregar_asset_marca(state.get("colecao", state.get("titulo", "")), "faixa")
    caminho_com_faixa = aplicar_faixa_colecao(caminho_arte, state.get("colecao", ""), faixa_png)

    selo_png = carregar_asset_marca(state.get("colecao", state.get("titulo", "")), "selo")
    caminho_final = caminho_com_faixa
    if selo_png:
        caminho_final = aplicar_selo_colecao(caminho_com_faixa, selo_png, posicao="inferior_esquerda")

    return {"caminho_arquivo": caminho_final, **dimensoes}


def gerar_capas_colorir(state: dict, gerar_imagem) -> dict:
    """Gera os dois arquivos de capa (eBook + físico) para o livro de colorir."""
    capa_ebook = gerar_capa_ebook_colorir(state, gerar_imagem)
    resultado_fisica = gerar_capa_fisica_wrap_colorir(state, gerar_imagem)
    return {
        "capa_ebook": capa_ebook,
        "capa_fisica_wrap": resultado_fisica["caminho_arquivo"],
        "capa_fisica_dimensoes": resultado_fisica,
    }


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('line_art_specialist',)

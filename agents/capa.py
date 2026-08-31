"""
Agente de Capa e Contracapa.

Capa e contracapa são arquivos SEPARADOS do miolo, com medidas
próprias, e o eBook e o livro físico usam formatos diferentes:

    EBOOK: um arquivo só, a arte de capa frontal (sem lombada/contracapa).
    LIVRO FÍSICO: um arquivo ÚNICO "wraparound" (contracapa+lombada+capa),
    cuja largura de lombada só pode ser calculada depois que o miolo
    fecha (ver kdp_rules.calcular_dimensoes_capa_fisica).

O tamanho do livro (trim size) NÃO é adivinhado - vem de
state["trim_largura_in"]/["trim_altura_in"], com 8.5x8.5" como padrão
se a autora não escolher outro.

A arte de fundo (personagens, cenário) é gerada pela IA. Os elementos
de marca fixos (faixa "COLEÇÃO X" e o selo/emblema) são SOBREPOSTOS
depois via PIL (ver marca.py) - não são redesenhados pela IA a cada
capa, pra ficarem sempre idênticos.
"""

from state import LivroState
from agents.ilustrador import ESTILO_VISUAL_FIXO
from kdp_rules import calcular_dimensoes_capa_fisica, dimensoes_capa_ebook_px
from marca import aplicar_faixa_colecao, aplicar_selo_colecao
from armazenamento import carregar_asset_marca

TRIM_LARGURA_IN_PADRAO = 8.5
TRIM_ALTURA_IN_PADRAO = 8.5


def _trim(state: LivroState) -> tuple[float, float]:
    return (
        state.get("trim_largura_in") or TRIM_LARGURA_IN_PADRAO,
        state.get("trim_altura_in") or TRIM_ALTURA_IN_PADRAO,
    )


def prompt_arte_capa_frontal(personagens: dict) -> str:
    """
    Só a CENA (personagens + cenário) - sem título, sem faixa, sem nome
    de autora. Esses elementos de texto/marca entram depois via PIL.
    """
    protagonistas = ", ".join(
        f"{p['nome']} ({p['descricao_fixa']})" for p in personagens.values()
    )
    return (
        f"{ESTILO_VISUAL_FIXO}\n"
        "Arte de capa de livro infantil, SOMENTE a cena ilustrada "
        "(sem nenhum texto, título, letras ou logotipo na imagem - "
        "isso será adicionado depois separadamente). Personagens em "
        f"destaque, centralizados, espaço livre na parte superior da "
        f"composição para posterior sobreposição de título: {protagonistas}."
    )


def prompt_arte_contracapa() -> str:
    """
    Cenário decorativo mais discreto (sem os personagens principais em
    destaque), com espaço reservado pro texto da sinopse e pro
    código de barras - tudo sem texto/logo embutido pela IA.
    """
    return (
        f"{ESTILO_VISUAL_FIXO}\n"
        "Arte de contracapa de livro infantil: cenário decorativo mais "
        "simples e discreto que a capa frontal (sem personagens em "
        "destaque, sem nenhum texto, título ou logotipo - isso será "
        "adicionado depois separadamente). Deixar a metade inferior da "
        "composição mais neutra/vazia, para acomodar texto de sinopse "
        "e a área reservada para código de barras."
    )


def gerar_capa_ebook(state: LivroState, gerar_imagem) -> str:
    trim_l, trim_a = _trim(state)
    dimensoes = dimensoes_capa_ebook_px(trim_l, trim_a)

    protagonista = next(
        (p for p in state.get("personagens", {}).values() if p.get("papel") == "protagonista"),
        None,
    )
    imagem_base = protagonista["imagem_referencia"] if protagonista else None

    prompt = prompt_arte_capa_frontal(state.get("personagens", {})) + (
        f" Gerar em {dimensoes['largura_px']}x{dimensoes['altura_px']} pixels."
    )
    caminho_arte = gerar_imagem(prompt=prompt, imagem_base=imagem_base)

    faixa_png = carregar_asset_marca(state.get("colecao", ""), "faixa")
    return aplicar_faixa_colecao(caminho_arte, state.get("colecao", ""), faixa_png)


def gerar_capa_fisica_wrap(state: LivroState, gerar_imagem, paginas_fisicas: int) -> dict:
    trim_l, trim_a = _trim(state)
    dimensoes = calcular_dimensoes_capa_fisica(trim_l, trim_a, paginas_fisicas)

    protagonista = next(
        (p for p in state.get("personagens", {}).values() if p.get("papel") == "protagonista"),
        None,
    )
    imagem_base = protagonista["imagem_referencia"] if protagonista else None

    prompt = (
        f"{prompt_arte_capa_frontal(state.get('personagens', {}))}\n"
        f"Canvas do wraparound completo: {dimensoes['largura_total_px']}x"
        f"{dimensoes['altura_total_px']} px, {dimensoes['dpi']} DPI, "
        f"sangria de 0.125\" nas bordas externas. Lombada de "
        f"{dimensoes['largura_lombada_in']}\" entre contracapa e capa."
    )
    caminho_arte = gerar_imagem(prompt=prompt, imagem_base=imagem_base)

    faixa_png = carregar_asset_marca(state.get("colecao", ""), "faixa")
    caminho_com_faixa = aplicar_faixa_colecao(caminho_arte, state.get("colecao", ""), faixa_png)

    selo_png = carregar_asset_marca(state.get("colecao", ""), "selo")
    caminho_final = caminho_com_faixa
    if selo_png:
        caminho_final = aplicar_selo_colecao(caminho_com_faixa, selo_png, posicao="inferior_esquerda")

    return {"caminho_arquivo": caminho_final, **dimensoes}


def capa_node(state: LivroState, gerar_imagem) -> LivroState:
    paginas_fisicas = state["layout_paginas"][-1]["pagina"] if state.get("layout_paginas") else 24

    state["capa_ebook"] = gerar_capa_ebook(state, gerar_imagem)
    resultado_fisica = gerar_capa_fisica_wrap(state, gerar_imagem, paginas_fisicas)
    state["capa_fisica_wrap"] = resultado_fisica["caminho_arquivo"]
    state["capa_fisica_dimensoes"] = resultado_fisica

    if "checklist_kdp" in state:
        state["checklist_kdp"]["capa_ebook_gerada"] = bool(state["capa_ebook"])
        state["checklist_kdp"]["capa_fisica_wrap_gerada"] = bool(state["capa_fisica_wrap"])
    return state

# TODO (próxima iteração): montar capa e contracapa como duas artes
# geradas separadamente, compostas lado a lado no canvas final com PIL
# (em vez de pedir pra IA gerar o wraparound inteiro numa imagem só,
# que é menos confiável pra manter a lombada no lugar certo).

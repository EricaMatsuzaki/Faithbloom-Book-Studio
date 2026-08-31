"""
Agente de Line Art / Livro de Colorir.

Projeto SEPARADO dos livros com história - um livro de colorir é só um
tema visual coeso com várias páginas dentro (bichinhos, princesas,
carros, aviões, navios, objetos fofos, etc.), sem narrativa entre elas.

REGRA DE ESTILO MAIS IMPORTANTE: quando o tema tem personagens com
gênero (bichinhos, princesas, heróis), macho e fêmea têm códigos
visuais DIFERENTES e FIXOS:

    MACHO:  olhos redondos com 2 brilhos, SEM cílios, blush em círculo
            TRACEJADO, sem acessório por padrão.
    FÊMEA:  olhos redondos com 2 brilhos, COM cílios, blush em formato
            de CORAÇÃO, acessório característico (laço).

Para temas SEM gênero (carros, aviões, navios, objetos), esse código
não se aplica - usa só o estilo base fofo, sem distinção.

DIAGNÓSTICO DA CAPA (problema que a Erica teve no "Cute Friends"): a
capa tinha um estilo AQUARELA/PINTURA rico, enquanto o miolo é um
estilo VETOR simples e plano - duas técnicas diferentes, não só duas
variações de cor. A correção: gerar a capa na MESMA técnica vetor do
miolo (só colorida), usando uma página de line art já aprovada como
imagem-base/referência - nunca descrever a capa do zero.
"""

ESTILO_LINE_ART_COLORIR = (
    "Line art para livro de colorir infantil: contorno preto grosso e "
    "limpo, SEM preenchimento de cor, SEM sombreado, traços simples e "
    "bem fechados (sem lacunas) - fáceis de colorir por uma criança. "
    "Estilo VETOR simples e fofo (proporção arredondada, elementos "
    "grandes e simples) - nunca estilo aquarela/pintura/textura rica, "
    "mesmo na versão colorida da capa. Moldura com cantos arredondados "
    "ao redor da cena, fundo simples (nuvens, grama, sol, ou elementos "
    "do tema) sem detalhes complexos."
)

CODIGO_VISUAL_SEXO = {
    "macho": (
        "Olhos redondos grandes com 2 pontos de brilho (highlight), "
        "SEM cílios. Marca nas bochechas em formato de CÍRCULO "
        "TRACEJADO (contorno pontilhado, nunca preenchido ou em "
        "coração). Sem laço ou acessório."
    ),
    "femea": (
        "Olhos redondos grandes com 2 pontos de brilho (highlight), "
        "COM cílios finos irradiando do topo do olho. Marca nas "
        "bochechas em formato de CORAÇÃO suave (nunca círculo). "
        "Acessório característico: um laço."
    ),
}


def prompt_pagina_colorir(nome_sujeito: str, categoria: str, cena: str, sexo: str | None = None) -> str:
    """
    sexo: "macho", "femea", ou None se o tema não usa distinção de
    gênero (veículos, objetos, formas).
    """
    partes = [ESTILO_LINE_ART_COLORIR, f"Assunto: {nome_sujeito} ({categoria})."]
    if sexo:
        partes.append(f"Código visual ({sexo}): {CODIGO_VISUAL_SEXO[sexo]}")
    partes.append(f"Cena: {cena}")
    return "\n".join(partes)


def gerar_pagina_colorir(
    nome_sujeito: str, categoria: str, cena: str, gerar_imagem,
    sexo: str | None = None, imagem_referencia: str | None = None,
) -> str:
    prompt = prompt_pagina_colorir(nome_sujeito, categoria, cena, sexo)
    return gerar_imagem(prompt=prompt, imagem_base=imagem_referencia)


def prompt_capa_colorida(sujeitos_destaque: list[dict], titulo: str) -> str:
    """sujeitos_destaque: [{"nome": str, "categoria": str, "sexo": str|None}, ...]"""
    descricoes = []
    for s in sujeitos_destaque:
        linha = f"{s['nome']} ({s['categoria']})"
        if s.get("sexo"):
            linha += f": {CODIGO_VISUAL_SEXO[s['sexo']]}"
        descricoes.append(linha)
    return (
        "Capa de livro de colorir infantil, VERSÃO COLORIDA no MESMO "
        "estilo vetor simples e fofo do miolo (contorno grosso, cores "
        "lisas/planas, proporção arredondada) - NUNCA estilo aquarela, "
        "pintura digital rica, texturizada ou com sombreado complexo. "
        "Mesma proporção e código visual dos personagens do miolo, só "
        "que coloridos:\n" + "\n".join(descricoes)
        + f"\nTítulo do livro em destaque: \"{titulo}\"."
    )


def gerar_capa_colorida(
    sujeitos_destaque: list[dict], titulo: str, gerar_imagem, imagem_referencia: str | None = None
) -> str:
    """
    imagem_referencia: passe o caminho de uma página de line art já
    aprovada como imagem-base - ancora a proporção/estilo da capa no
    que já foi validado no miolo, em vez de reinterpretar do zero.
    """
    prompt = prompt_capa_colorida(sujeitos_destaque, titulo)
    return gerar_imagem(prompt=prompt, imagem_base=imagem_referencia)


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

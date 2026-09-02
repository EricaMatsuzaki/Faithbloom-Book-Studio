"""
Regras fixas da Amazon KDP, verificadas em agosto/2026.
Fonte: kdp.amazon.com/help (paperback submission guidelines, book supported
languages). Revalidar periodicamente - a KDP atualiza essas regras.
"""

PAGINAS_MINIMAS_PAPERBACK_PREMIUM_COLOR = 24   # nunca publicar abaixo disso
PAGINAS_MINIMAS_PAPERBACK_STANDARD_COLOR = 72
PAGINAS_MINIMAS_PAPERBACK_PRETO_BRANCO = 24     # miolo preto/branco (line art de colorir usa esse)
PAGINAS_MINIMAS_HARDCOVER = 75


def validar_paginas_par(paginas_fisicas: int) -> tuple[bool, int]:
    """
    A KDP exige contagem de páginas par (o processo de impressão dobra
    folhas em cadernos). Retorna (já_estava_par, contagem_corrigida).
    Se for ímpar, soma 1 (página em branco no final).
    """
    if paginas_fisicas % 2 == 0:
        return True, paginas_fisicas
    return False, paginas_fisicas + 1

# --- Cálculo de capa (verificado em ago/2026, fonte: kdp.amazon.com
# cover calculator + submission guidelines - revalidar periodicamente) ---
#
# EBOOK: uma imagem só (capa frontal), sem lombada, sem contracapa.
# LIVRO FÍSICO: um único arquivo "wraparound" (capa + lombada + contracapa),
# com sangria de 0.125" em todas as bordas externas, 300 DPI. A largura
# da lombada depende da contagem de páginas E do tipo de papel - por
# isso não pode ser calculada até o miolo estar fechado.

BLEED_IN = 0.125
DPI_CAPA = 300

MULTIPLICADOR_ESPESSURA_PAPEL = {
    "branco": 0.002252,
    "creme": 0.0025,
    "cor_premium": 0.002347,
    "cor_padrao": 0.002252,
}

PAGINAS_MINIMAS_PARA_TEXTO_NA_LOMBADA = 79  # abaixo disso, lombada sem texto


def calcular_largura_lombada_in(paginas_fisicas: int, papel: str = "cor_premium") -> float:
    multiplicador = MULTIPLICADOR_ESPESSURA_PAPEL[papel]
    return round(paginas_fisicas * multiplicador, 4)


def calcular_dimensoes_capa_fisica(
    trim_largura_in: float, trim_altura_in: float, paginas_fisicas: int, papel: str = "cor_premium"
) -> dict:
    """
    Retorna as dimensões do arquivo ÚNICO de capa física (wraparound):
    contracapa + lombada + capa, já com sangria - pronto pra virar o
    canvas onde o Diagramador posiciona cada parte.
    """
    largura_lombada = calcular_largura_lombada_in(paginas_fisicas, papel)
    largura_total = BLEED_IN + trim_largura_in + largura_lombada + trim_largura_in + BLEED_IN
    altura_total = BLEED_IN + trim_altura_in + BLEED_IN
    return {
        "largura_lombada_in": largura_lombada,
        "largura_total_in": round(largura_total, 4),
        "altura_total_in": round(altura_total, 4),
        "largura_total_px": round(largura_total * DPI_CAPA),
        "altura_total_px": round(altura_total * DPI_CAPA),
        "texto_na_lombada_permitido": paginas_fisicas >= PAGINAS_MINIMAS_PARA_TEXTO_NA_LOMBADA,
        "dpi": DPI_CAPA,
    }


def dimensoes_capa_ebook_px(trim_largura_in: float, trim_altura_in: float) -> dict:
    """
    A capa de eBook é só a arte frontal (sem lombada/contracapa).
    KDP recomenda o lado maior com pelo menos 2560px, mantendo a
    proporção do trim size do livro físico (mesma arte de capa,
    recortada só na parte frontal).
    """
    proporcao = trim_altura_in / trim_largura_in
    lado_maior_px = 2560
    if proporcao >= 1:
        altura_px = lado_maior_px
        largura_px = round(lado_maior_px / proporcao)
    else:
        largura_px = lado_maior_px
        altura_px = round(lado_maior_px * proporcao)
    return {"largura_px": largura_px, "altura_px": altura_px}


# ---------------------------------------------------------------------
# Custo de impressão e royalty (verificado ago/2026 - fontes de
# calculadoras terceiras divergem um pouco entre si; os valores abaixo
# são os mais consistentes entre elas, mas SEMPRE confira na
# calculadora oficial da KDP - kdp.amazon.com/en_US/help/topic/G201834340
# - antes de fixar um preço de venda de verdade).
# ---------------------------------------------------------------------

CUSTO_FIXO_PRETO_BRANCO = 1.00
CUSTO_POR_PAGINA_PRETO_BRANCO = 0.012

CUSTO_FIXO_COR_PADRAO = 1.00
CUSTO_POR_PAGINA_COR_PADRAO = 0.07

# Cor premium tem uma faixa curta (24-40 páginas) que cobra só o custo
# fixo, sem custo por página - regra confirmada em múltiplas fontes,
# mas o valor exato do fixo curto varia (~$3.60 pra trim regular nos
# EUA) - CONFIRME na calculadora oficial antes de usar pra precificar.
CUSTO_FIXO_COR_PREMIUM_CURTO = 3.60   # livros de 24-40 páginas
CUSTO_FIXO_COR_PREMIUM_LONGO = 1.00   # livros com mais de 40 páginas
CUSTO_POR_PAGINA_COR_PREMIUM_LONGO = 0.065

ROYALTY_PAPERBACK = 0.60   # taxa de royalty do paperback (canal direto Amazon)
ROYALTY_EBOOK_BAIXO = 0.35
ROYALTY_EBOOK_ALTO = 0.70  # só disponível pra preço entre $2.99 e $9.99


def calcular_custo_impressao(paginas: int, tipo_papel: str = "cor_premium") -> float:
    """
    tipo_papel: "preto_branco", "cor_padrao" ou "cor_premium".
    Retorna o custo de impressão estimado em USD (mercado EUA).
    """
    if tipo_papel == "preto_branco":
        return round(CUSTO_FIXO_PRETO_BRANCO + paginas * CUSTO_POR_PAGINA_PRETO_BRANCO, 2)
    if tipo_papel == "cor_padrao":
        return round(CUSTO_FIXO_COR_PADRAO + paginas * CUSTO_POR_PAGINA_COR_PADRAO, 2)
    if tipo_papel == "cor_premium":
        if 24 <= paginas <= 40:
            return CUSTO_FIXO_COR_PREMIUM_CURTO
        return round(CUSTO_FIXO_COR_PREMIUM_LONGO + paginas * CUSTO_POR_PAGINA_COR_PREMIUM_LONGO, 2)
    raise ValueError(f"tipo_papel inválido: {tipo_papel}")


def calcular_preco_minimo_viavel(custo_impressao: float) -> float:
    """Preço abaixo do qual você perde dinheiro em cada venda (royalty negativo)."""
    return round(custo_impressao / ROYALTY_PAPERBACK, 2)


def calcular_royalty_paperback(preco_capa: float, custo_impressao: float) -> float:
    return round(preco_capa * ROYALTY_PAPERBACK - custo_impressao, 2)


def calcular_royalty_ebook(preco_capa: float, taxa: str = "alta") -> float:
    """taxa: "alta" (70%, só entre $2.99-$9.99) ou "baixa" (35%, qualquer preço)."""
    if taxa == "alta" and not (2.99 <= preco_capa <= 9.99):
        raise ValueError("A taxa de 70% só é válida para preços entre $2.99 e $9.99.")
    percentual = ROYALTY_EBOOK_ALTO if taxa == "alta" else ROYALTY_EBOOK_BAIXO
    return round(preco_capa * percentual, 2)


def sugerir_faixa_de_preco(custo_impressao: float) -> dict:
    """
    Sugestão de 3 pontos de preço (mínimo viável, competitivo, premium)
    - referência pra começar a decidir, não uma recomendação definitiva.
    """
    minimo = calcular_preco_minimo_viavel(custo_impressao)
    return {
        "minimo_viavel": minimo,
        "competitivo_sugerido": round(max(minimo + 3, 9.99), 2),
        "premium_sugerido": round(max(minimo + 6, 14.99), 2),
    }

# Idiomas com upload direto em PDF nativo (os demais precisam de outro formato)
IDIOMAS_PDF_NATIVO = {
    "pt", "en", "fr", "de", "it", "es", "ca", "gl", "eu",
}

# Idiomas hoje SEM suporte a paperback (só eBook) - checar antes de traduzir
# pensando em impressão física
IDIOMAS_SOMENTE_EBOOK = {
    "hi", "ta", "mr", "gu", "ml",  # idiomas indianos - paperback não suportado
}

MARKETPLACE_PARA_IDIOMA_PADRAO = {
    "US": "en", "UK": "en", "CA": "en", "IE": "en", "AU": "en",
    "DE": "de",
    "FR": "fr", "BE": "fr",
    "IT": "it",
    "ES": "es", "MX": "es",
    "JP": "ja",
    "NL": "nl",
    "PL": "pl",
    "SE": "sv",
    "BR": "pt",
    "IN": "en",   # paperback em idioma indiano não suportado hoje -> inglês
}


def validar_contagem_paginas(paginas_fisicas: int, cor: str = "premium") -> tuple[bool, str]:
    """
    paginas_fisicas = total de páginas do miolo (já contando texto+imagem
    separados, se for esse o layout escolhido).
    """
    minimo = {
        "premium": PAGINAS_MINIMAS_PAPERBACK_PREMIUM_COLOR,
        "standard": PAGINAS_MINIMAS_PAPERBACK_STANDARD_COLOR,
        "preto_branco": PAGINAS_MINIMAS_PAPERBACK_PRETO_BRANCO,
        "hardcover": PAGINAS_MINIMAS_HARDCOVER,
    }[cor]
    if paginas_fisicas < minimo:
        return False, f"Abaixo do mínimo KDP para {cor} ({minimo} páginas)."
    return True, "OK"


def idioma_elegivel_paperback(codigo_idioma: str) -> bool:
    return codigo_idioma not in IDIOMAS_SOMENTE_EBOOK

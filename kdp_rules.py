"""
Regras fixas da Amazon KDP, verificadas em agosto/2026.
Fonte: kdp.amazon.com/help (paperback submission guidelines, book supported
languages). Revalidar periodicamente - a KDP atualiza essas regras.
"""

PAGINAS_MINIMAS_PAPERBACK_PREMIUM_COLOR = 24   # nunca publicar abaixo disso
PAGINAS_MINIMAS_PAPERBACK_STANDARD_COLOR = 72
PAGINAS_MINIMAS_HARDCOVER = 75

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
        "hardcover": PAGINAS_MINIMAS_HARDCOVER,
    }[cor]
    if paginas_fisicas < minimo:
        return False, f"Abaixo do mínimo KDP para {cor} ({minimo} páginas)."
    return True, "OK"


def idioma_elegivel_paperback(codigo_idioma: str) -> bool:
    return codigo_idioma not in IDIOMAS_SOMENTE_EBOOK

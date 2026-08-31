"""
Agente Diagramador - Livro de Colorir.

Monta o layout final do miolo (capa interna/rosto + "este livro
pertence a" + páginas de colorir + página em branco final se
necessário) e valida contra as regras da KDP para miolo preto e
branco: mínimo de 24 páginas, contagem par obrigatória.

REGRA IMPORTANTE (padrão da indústria pra livro de colorir): cada
página de colorir vai IMPRESSA SÓ NA FRENTE, com o VERSO EM BRANCO -
isso evita que giz de cera, lápis de cor ou principalmente marcador
atravessem o papel fino e estraguem o desenho seguinte. Isso
literalmente DOBRA a contagem de páginas do miolo (20 desenhos viram
40 páginas), e afeta diretamente a largura da lombada calculada pra
capa física - por isso esse Diagramador precisa rodar antes da capa.
"""

from kdp_rules import validar_contagem_paginas, validar_paginas_par

# Páginas fixas de abertura, no padrão que a Erica já usa (ver PDF
# "Cute Friends"): folha de rosto/título + "este livro pertence a".
PAGINAS_ABERTURA_FIXAS = 2


def montar_layout_colorir(total_paginas_colorir: int) -> list[dict]:
    layout = []
    pagina_atual = 1
    for tipo in ("rosto_titulo", "este_livro_pertence_a"):
        layout.append({"pagina": pagina_atual, "tipo": tipo})
        pagina_atual += 1
    for i in range(total_paginas_colorir):
        layout.append({"pagina": pagina_atual, "tipo": "colorir", "indice_pagina_colorir": i})
        pagina_atual += 1
        # Verso em branco - protege a ilustração seguinte de giz de
        # cera/marcador que atravessa o papel. Nunca pular isso.
        layout.append({"pagina": pagina_atual, "tipo": "verso_em_branco", "indice_pagina_colorir": i})
        pagina_atual += 1
    return layout


def diagramador_colorir_node(state: dict) -> dict:
    total_colorir = len(state.get("paginas", []))
    layout = montar_layout_colorir(total_colorir)
    paginas_fisicas = layout[-1]["pagina"] if layout else 0

    par_ok, paginas_corrigidas = validar_paginas_par(paginas_fisicas)
    if not par_ok:
        layout.append({"pagina": paginas_corrigidas, "tipo": "pagina_em_branco"})
        paginas_fisicas = paginas_corrigidas

    minimo_ok, msg = validar_contagem_paginas(paginas_fisicas, cor="preto_branco")

    state["layout_paginas"] = layout
    state["paginas_fisicas_total"] = paginas_fisicas
    state["checklist_kdp"] = {
        "paginas_minimas_ok": minimo_ok,
        "paginas_par_ok": True,  # já corrigido acima se precisasse
        "impressao_single_sided_ok": True,  # verso em branco em toda página de colorir
        "dpi_300_confirmado": False,
        "divulgacao_ia_preenchida": False,
    }
    if not minimo_ok:
        state["checklist_kdp"]["nota"] = msg
    return state

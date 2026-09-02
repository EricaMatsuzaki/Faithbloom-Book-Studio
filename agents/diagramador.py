"""
Agente Diagramador / Formatter.

Monta o layout final, página a página, alternando o lado do
texto/imagem a cada spread (padrão de mercado - evita transparência de
texto na impressão), valida contra as regras da KDP, e monta o
checklist final (incluindo a divulgação obrigatória de conteúdo gerado
por IA). Não publica sozinho - o clique final de "Publicar" é sempre
manual, feito conscientemente pela Erica na plataforma oficial.
"""

from state import LivroState
from kdp_rules import validar_contagem_paginas


def montar_layout(state: LivroState) -> list[dict]:
    """
    Cada cena vira 2 páginas físicas: uma de texto, uma de imagem,
    alternando qual fica à esquerda/direita a cada spread.
    """
    layout = []
    pagina_atual = 3  # páginas 1-2 reservadas para capa/rosto/copyright/dedicatória
    for i, cena in enumerate(state["cenas_texto"]):
        lado_texto = "esquerda" if i % 2 == 0 else "direita"
        lado_imagem = "direita" if lado_texto == "esquerda" else "esquerda"
        layout.append(
            {
                "pagina": pagina_atual,
                "tipo": "texto",
                "lado": lado_texto,
                "cena_numero": cena["numero"],
            }
        )
        layout.append(
            {
                "pagina": pagina_atual + 1,
                "tipo": "imagem",
                "lado": lado_imagem,
                "cena_numero": cena["numero"],
            }
        )
        pagina_atual += 2
    # + 3 páginas de fechamento (resolução, celebração, lição+versículo/FIM)
    for tipo in ("resolucao", "celebracao", "licao_e_versiculo_fim"):
        layout.append({"pagina": pagina_atual, "tipo": tipo, "lado": "spread"})
        pagina_atual += 1

    # + seção de atividades: 3 páginas de line-art para colorir
    for pagina_colorir in state.get("paginas_colorir", []):
        layout.append(
            {
                "pagina": pagina_atual,
                "tipo": "atividade_colorir",
                "lado": "spread",
                "cena_numero": pagina_colorir["numero"],
            }
        )
        pagina_atual += 1

    return layout


def diagramador_node(state: LivroState) -> LivroState:
    layout = montar_layout(state)
    total_paginas = layout[-1]["pagina"]

    ok, msg = validar_contagem_paginas(
        total_paginas, cor="premium"
    )

    checklist = {
        "paginas_minimas_ok": ok,
        "dpi_300_confirmado": False,       # confirmar após render final das imagens
        "cmyk_confirmado": False,
        "bleed_configurado": False,
        "divulgacao_ia_preenchida": False,  # exigência KDP 2026 - conteúdo gerado por IA
        "dedicatoria_incluida": bool(state.get("dedicatoria_texto")),
        "sinopse_vendas_pronta": bool(state.get("sinopse_vendas_curta")),
        "capa_ebook_gerada": False,          # arquivo separado - ver agents/capa.py
        "capa_fisica_wrap_gerada": False,    # arquivo separado - ver agents/capa.py
    }

    state["layout_paginas"] = layout
    state["checklist_kdp"] = checklist
    state["pacote_pronto"] = ok and all(
        checklist[k] for k in ("dedicatoria_incluida", "sinopse_vendas_pronta")
    )
    if not ok:
        state.setdefault("notas_revisor", []).append(msg)
    return state

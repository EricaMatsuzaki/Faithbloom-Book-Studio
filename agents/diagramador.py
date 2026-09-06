"""
Agente Diagramador / Formatter.

Monta o layout final, página a página, alternando o lado do
texto/imagem a cada spread (padrão de mercado - evita transparência de
texto na impressão), valida contra as regras da KDP, e monta o
checklist final (incluindo a divulgação obrigatória de conteúdo gerado
por IA). Não publica sozinho - o clique final de "Publicar" é sempre
manual, feito conscientemente pela Erica na plataforma oficial.
"""

SKILL_PROFILE_ID = "diagrammer"

from state import LivroState
from kdp_rules import validar_contagem_paginas
from qualidade_impressao import preflight_livro
from prompt_master_compliance import avaliar_prompt_mestre


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

    prompt_mestre = avaliar_prompt_mestre(dict(state))
    state["prompt_mestre_compliance"] = prompt_mestre
    moral_ok = not any(
        item.get("codigo") == "MORAL_OBRIGATORIA"
        for item in prompt_mestre.get("bloqueios", [])
    )

    checklist = {
        "paginas_minimas_ok": ok,
        "dpi_300_confirmado": False,       # calculado abaixo por pixels reais / tamanho impresso
        "perfil_cor_revisado": False,       # não força CMYK genericamente; depende do produto/arquivo
        "bleed_configurado": True,
        "divulgacao_ia_preenchida": False,  # exigência KDP 2026 - conteúdo gerado por IA
        "dedicatoria_incluida": bool(state.get("dedicatoria_texto")),
        "sinopse_vendas_pronta": bool(state.get("sinopse_vendas_curta")),
        "moral_obrigatoria_ok": moral_ok,
        "boas_vindas_pronta": bool(str(state.get("boas_vindas") or "").strip()),
        "pais_educadores_pronto": bool(state.get("pais_educadores")),
        "ficha_pedagogica_pronta": bool(state.get("ficha_pedagogica")),
        "estilo_narrativo_definido": bool(state.get("estilo_narrativo")),
        "tres_paginas_colorir_prontas": len(state.get("paginas_colorir") or []) >= 3,
        "capa_ebook_gerada": False,          # arquivo separado - ver agents/capa.py
        "capa_fisica_wrap_gerada": False,    # arquivo separado - ver agents/capa.py
        "pdf_miolo_gerado": bool(state.get("pdf_miolo")),
    }

    state["layout_paginas"] = layout
    state["checklist_kdp"] = checklist
    preflight = preflight_livro(state, bleed=True)
    state["preflight_impressao"] = preflight
    state["checklist_kdp"]["dpi_300_confirmado"] = preflight["checks"]["imagens_300ppi"]
    state["checklist_kdp"]["bleed_configurado"] = preflight["checks"]["bleed_configurado"]

    # Prompt-Mestre: a ausência de Lição de Moral é bloqueio real de finalização.
    state["pacote_pronto"] = (
        ok
        and moral_ok
        and all(checklist[k] for k in ("dedicatoria_incluida", "sinopse_vendas_pronta"))
    )

    if not ok:
        state.setdefault("notas_revisor", []).append(msg)
    if not moral_ok:
        state.setdefault("notas_revisor", []).append(
            "BLOQUEIO PROMPT-MESTRE: a Lição de Moral é obrigatória antes da finalização."
        )
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('diagrammer',)

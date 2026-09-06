"""Refinamento 24 — conformidade do Prompt-Mestre FaithBloom."""
from __future__ import annotations


def avaliar_prompt_mestre(state: dict) -> dict:
    bloqueios: list[dict] = []
    recomendacoes: list[dict] = []
    aprovados: list[str] = []

    if str(state.get("licao_final") or "").strip():
        aprovados.append("Lição de Moral")
    else:
        bloqueios.append({
            "codigo": "MORAL_OBRIGATORIA",
            "campo": "licao_final",
            "mensagem": "A Lição de Moral é obrigatória e bloqueia a finalização do livro.",
        })

    if state.get("estilo_narrativo"):
        aprovados.append("Estilo narrativo formal")
    else:
        recomendacoes.append({
            "codigo": "ESTILO_NARRATIVO_AUSENTE",
            "campo": "estilo_narrativo",
            "mensagem": "Escolha formalmente Estilo 1, Estilo 2, Estilo 3 ou Estilo misto.",
        })

    if str(state.get("boas_vindas") or "").strip():
        aprovados.append("Boas-vindas")
    else:
        recomendacoes.append({
            "codigo": "BOAS_VINDAS_AUSENTE",
            "campo": "boas_vindas",
            "mensagem": "Gerar e revisar a mensagem de boas-vindas do livro.",
        })

    if state.get("pais_educadores"):
        aprovados.append("Pais/Educadores")
    else:
        recomendacoes.append({
            "codigo": "PAIS_EDUCADORES_AUSENTE",
            "campo": "pais_educadores",
            "mensagem": "Gerar a mensagem e o guia de conversa para pais e educadores.",
        })

    if state.get("ficha_pedagogica"):
        aprovados.append("Ficha Pedagógica")
    else:
        recomendacoes.append({
            "codigo": "FICHA_PEDAGOGICA_AUSENTE",
            "campo": "ficha_pedagogica",
            "mensagem": "Gerar a ficha pedagógica da obra.",
        })

    # Psicologia das cores é regra editorial obrigatória de criação, mas não
    # vira um segundo bloqueio de exportação neste refinamento: a decisão
    # explícita da autora foi manter a Moral como bloqueio Prompt-Mestre.
    cenas = [x for x in (state.get("cenas_texto") or []) if isinstance(x, dict)]
    mapa = [x for x in (state.get("mapa_emocional") or []) if isinstance(x, dict)]
    if cenas:
        faltando_meta = [
            int(c.get("numero", i + 1))
            for i, c in enumerate(cenas)
            if not str(c.get("emocao") or "").strip()
            or not (1 <= int(c.get("intensidade_emocional") or 0) <= 5)
        ]
        if faltando_meta:
            recomendacoes.append({
                "codigo": "EMOCAO_POR_CENA_INCOMPLETA",
                "campo": "cenas_texto",
                "mensagem": f"Completar emoção e intensidade 1–5 nas cenas: {faltando_meta}.",
            })
        elif not mapa:
            recomendacoes.append({
                "codigo": "MAPA_EMOCIONAL_AUSENTE",
                "campo": "mapa_emocional",
                "mensagem": "A psicologia das cores é obrigatória página por página; gere/revise o mapa no Emotional & Color Director antes das ilustrações finais.",
            })
        elif len(mapa) != len(cenas):
            recomendacoes.append({
                "codigo": "MAPA_EMOCIONAL_INCOMPLETO",
                "campo": "mapa_emocional",
                "mensagem": f"O mapa emocional possui {len(mapa)} itens para {len(cenas)} cenas. Alinhe o mapa com a história atual.",
            })
        else:
            aprovados.append("Psicologia das cores página por página")

    paginas_colorir = state.get("paginas_colorir") or []
    if len(paginas_colorir) >= 3:
        aprovados.append("3 páginas para colorir")
    else:
        recomendacoes.append({
            "codigo": "COLORIR_INCOMPLETO",
            "campo": "paginas_colorir",
            "mensagem": f"O padrão atual do SaaS é 3 páginas para colorir; existem {len(paginas_colorir)}.",
        })

    return {
        "ok_para_finalizar": not bloqueios,
        "bloqueios": bloqueios,
        "recomendacoes": recomendacoes,
        "aprovados": aprovados,
        "regra_colorir": 3,
        "regra_psicologia_cores": "pagina_por_pagina",
    }


def pode_finalizar_prompt_mestre(state: dict) -> bool:
    return bool(avaliar_prompt_mestre(state)["ok_para_finalizar"])

"""Refinamento 24 — conformidade do Prompt-Mestre FaithBloom."""
from __future__ import annotations

from age_profiles import normalizar_faixa_etaria, perfil_etario


def _intensidade_valida(valor) -> bool:
    """Aceita projetos novos/antigos sem lançar exceção por valor legado."""
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return False
    return 1 <= numero <= 5


def avaliar_prompt_mestre(state: dict) -> dict:
    bloqueios: list[dict] = []
    recomendacoes: list[dict] = []
    aprovados: list[str] = []

    # Faixa etária é central para novos livros. Projetos legados sem esse campo
    # continuam compatíveis com 3–8, mas recebem recomendação para confirmação.
    raw_faixa = str(state.get("faixa_etaria") or "").strip()
    faixa = normalizar_faixa_etaria(raw_faixa or None)
    perfil = perfil_etario(faixa)
    if raw_faixa:
        aprovados.append(f"Faixa etária: {perfil['short_label']}")
    else:
        recomendacoes.append({
            "codigo": "FAIXA_ETARIA_NAO_CONFIRMADA",
            "campo": "faixa_etaria",
            "mensagem": "Confirme a faixa etária oficial do livro. Enquanto isso, o projeto usa 3–8 anos por compatibilidade.",
        })

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

    ficha = state.get("ficha_pedagogica")
    if ficha:
        aprovados.append("Ficha Pedagógica")
        if isinstance(ficha, dict):
            faixa_ficha = str(ficha.get("faixa_etaria") or "").strip()
            if faixa_ficha and normalizar_faixa_etaria(faixa_ficha) != faixa:
                recomendacoes.append({
                    "codigo": "FICHA_FAIXA_ETARIA_DIVERGENTE",
                    "campo": "ficha_pedagogica.faixa_etaria",
                    "mensagem": (
                        f"A Ficha Pedagógica indica '{faixa_ficha}', mas o livro está configurado para "
                        f"{perfil['short_label']}. Regenere ou ajuste a ficha antes da exportação final."
                    ),
                })
    else:
        recomendacoes.append({
            "codigo": "FICHA_PEDAGOGICA_AUSENTE",
            "campo": "ficha_pedagogica",
            "mensagem": "Gerar a ficha pedagógica da obra.",
        })

    # Psicologia das cores é regra editorial obrigatória de criação, mas não
    # vira um segundo bloqueio de exportação neste refinamento: a Moral continua
    # sendo o bloqueio Prompt-Mestre definido para compatibilidade do produto.
    cenas = [x for x in (state.get("cenas_texto") or []) if isinstance(x, dict)]
    mapa = [x for x in (state.get("mapa_emocional") or []) if isinstance(x, dict)]
    if cenas:
        faltando_meta = [
            int(c.get("numero", i + 1))
            for i, c in enumerate(cenas)
            if not str(c.get("emocao") or "").strip()
            or not _intensidade_valida(c.get("intensidade_emocional"))
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
        "faixa_etaria": faixa,
        "faixa_etaria_label": perfil["short_label"],
    }


def pode_finalizar_prompt_mestre(state: dict) -> bool:
    return bool(avaliar_prompt_mestre(state)["ok_para_finalizar"])

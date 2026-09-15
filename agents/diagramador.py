"""
Agente Diagramador / Formatter.

Monta o layout final página a página, respeitando paridade física do livro,
regras KDP e seções editoriais do Prompt-Mestre. Não publica sozinho: o clique
final de publicação continua sendo uma decisão humana na plataforma oficial.
"""

SKILL_PROFILE_ID = "diagrammer"

from state import LivroState
from kdp_rules import validar_contagem_paginas
from qualidade_impressao import preflight_livro
from prompt_master_compliance import avaliar_prompt_mestre
from age_profiles import normalizar_faixa_etaria
from originality_guard import evaluate_originality


def _lado_da_pagina(numero: int) -> str:
    # Em livro encadernado: página par fica à esquerda; ímpar, à direita.
    return "esquerda" if int(numero) % 2 == 0 else "direita"


def _numero_colorir(item: dict, fallback: int) -> int:
    try:
        return int(item.get("numero", item.get("cena_numero", fallback)))
    except (TypeError, ValueError):
        return fallback


def montar_layout(state: LivroState) -> list[dict]:
    """Monta a ordem física do miolo.

    Páginas 1 e 2 são desenhadas diretamente pelo renderizador como rosto e
    créditos/dedicatória. A página 3 é reservada para Boas-vindas, e a história
    começa na página 4 para que o primeiro spread seja fisicamente coerente:
    página par = esquerda; página ímpar = direita.

    A cada nova cena, alternamos qual lado recebe texto e imagem. Isso mantém o
    padrão editorial sem apenas rotular o lado: a ORDEM das páginas passa a
    corresponder à encadernação real.
    """
    layout: list[dict] = [
        {"pagina": 3, "tipo": "boas_vindas", "lado": "direita"},
    ]
    pagina_atual = 4

    for i, cena in enumerate(state.get("cenas_texto") or []):
        numero_cena = int(cena.get("numero", i + 1))
        if i % 2 == 0:
            layout.append(
                {"pagina": pagina_atual, "tipo": "texto", "lado": "esquerda", "cena_numero": numero_cena}
            )
            layout.append(
                {"pagina": pagina_atual + 1, "tipo": "imagem", "lado": "direita", "cena_numero": numero_cena}
            )
        else:
            layout.append(
                {"pagina": pagina_atual, "tipo": "imagem", "lado": "esquerda", "cena_numero": numero_cena}
            )
            layout.append(
                {"pagina": pagina_atual + 1, "tipo": "texto", "lado": "direita", "cena_numero": numero_cena}
            )
        pagina_atual += 2

    for tipo in ("resolucao", "celebracao", "licao_e_versiculo_fim"):
        layout.append({"pagina": pagina_atual, "tipo": tipo, "lado": _lado_da_pagina(pagina_atual)})
        pagina_atual += 1

    if str(state.get("pais_educadores") or "").strip() and state.get("pais_educadores"):
        layout.append({"pagina": pagina_atual, "tipo": "pais_educadores", "lado": _lado_da_pagina(pagina_atual)})
        pagina_atual += 1

    if str(state.get("ficha_pedagogica") or "").strip() and state.get("ficha_pedagogica"):
        layout.append({"pagina": pagina_atual, "tipo": "ficha_pedagogica", "lado": _lado_da_pagina(pagina_atual)})
        pagina_atual += 1

    for idx, pagina_colorir in enumerate(state.get("paginas_colorir", []) or [], 1):
        num = _numero_colorir(pagina_colorir, idx)
        layout.append(
            {"pagina": pagina_atual, "tipo": "atividade_colorir", "lado": _lado_da_pagina(pagina_atual), "cena_numero": num}
        )
        pagina_atual += 1

    ultimo = layout[-1]["pagina"] if layout else 2
    if ultimo % 2:
        layout.append({"pagina": ultimo + 1, "tipo": "pagina_em_branco", "lado": "esquerda"})

    return layout


def diagramador_node(state: LivroState) -> LivroState:
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    state["faixa_etaria"] = faixa
    state["age_profile_id"] = faixa

    layout = montar_layout(state)
    total_paginas = layout[-1]["pagina"]

    ok, msg = validar_contagem_paginas(total_paginas, cor="premium")

    prompt_mestre = avaliar_prompt_mestre(dict(state))
    state["prompt_mestre_compliance"] = prompt_mestre
    moral_ok = not any(
        item.get("codigo") == "MORAL_OBRIGATORIA"
        for item in prompt_mestre.get("bloqueios", [])
    )

    # Originality & Ineditism Guard: bloqueia somente quando existe evidência
    # concreta local (ex.: overlap textual longo ou briefing de imitação direta).
    # PASS_INTERNAL não é certificado jurídico de ineditismo mundial.
    originality = evaluate_originality(dict(state))
    state["originality_guard_report"] = originality
    originality_ok = originality.get("status") != "BLOCKED"

    checklist = {
        "paginas_minimas_ok": ok,
        "dpi_300_confirmado": False,
        "perfil_cor_revisado": False,
        "bleed_configurado": True,
        "divulgacao_ia_preenchida": False,
        "dedicatoria_incluida": bool(state.get("dedicatoria_texto")),
        "sinopse_vendas_pronta": bool(state.get("sinopse_vendas_curta")),
        "moral_obrigatoria_ok": moral_ok,
        "originalidade_interna_ok": originality_ok,
        "faixa_etaria_definida": bool(state.get("faixa_etaria")),
        "boas_vindas_pronta": bool(str(state.get("boas_vindas") or "").strip()),
        "pais_educadores_pronto": bool(state.get("pais_educadores")),
        "ficha_pedagogica_pronta": bool(state.get("ficha_pedagogica")),
        "estilo_narrativo_definido": bool(state.get("estilo_narrativo")),
        "tres_paginas_colorir_prontas": len(state.get("paginas_colorir") or []) >= 3,
        "capa_ebook_gerada": False,
        "capa_fisica_wrap_gerada": False,
        "pdf_miolo_gerado": bool(state.get("pdf_miolo") or state.get("pdf_miolo_print_ready")),
    }

    state["layout_paginas"] = layout
    state["checklist_kdp"] = checklist
    preflight = preflight_livro(state, bleed=True)
    state["preflight_impressao"] = preflight
    state["checklist_kdp"]["dpi_300_confirmado"] = preflight["checks"]["imagens_300ppi"]
    state["checklist_kdp"]["bleed_configurado"] = preflight["checks"]["bleed_configurado"]

    state["pacote_pronto"] = (
        ok
        and moral_ok
        and originality_ok
        and all(checklist[k] for k in ("dedicatoria_incluida", "sinopse_vendas_pronta"))
    )

    if not ok:
        state.setdefault("notas_revisor", []).append(msg)
    if not moral_ok:
        state.setdefault("notas_revisor", []).append(
            "BLOQUEIO PROMPT-MESTRE: a Lição de Moral é obrigatória antes da finalização."
        )
    if not originality_ok:
        state.setdefault("notas_revisor", []).append(
            "BLOQUEIO ORIGINALITY GUARD: há evidência local de proximidade indevida/imitação. Revisar antes da finalização."
        )
    elif originality.get("status") == "NEEDS_REVIEW":
        state.setdefault("notas_revisor", []).append(
            "ATENÇÃO ORIGINALITY GUARD: há itens de distintividade que pedem revisão humana antes da publicação."
        )
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('diagrammer',)
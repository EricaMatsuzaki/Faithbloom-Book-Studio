"""Mapa emocional automation-first do Full Editorial Remaster.

O agente especialista lê a história/cenas em lote, identifica a emoção narrativa
mais adequada e o Emotional & Color Director aplica a Psicologia das Cores
canônica do FaithBloom. A autora não precisa preencher ficha cena por cena:
ajustes manuais continuam possíveis e prevalecem quando uma emoção é travada.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable

from emotion_colors import EMOCOES, EMOCOES_COMPLEMENTARES
from emotional_color_director import construir_mapa_emocional
from editorial_remaster_revision import salvar_estado_remaster


def opcoes_emocao() -> list[str]:
    return list(EMOCOES.keys()) + [x for x in EMOCOES_COMPLEMENTARES.keys() if x not in EMOCOES]


def metadata_emocional_completa(state: dict) -> dict:
    faltando = []
    for i, cena in enumerate(state.get("cenas_texto") or [], 1):
        numero = int(cena.get("numero") or i)
        emocao = str(cena.get("emocao") or "").strip()
        try:
            intensidade = int(cena.get("intensidade_emocional"))
        except (TypeError, ValueError):
            intensidade = 0
        if not emocao or emocao not in opcoes_emocao() or not 1 <= intensidade <= 5:
            faltando.append(numero)
    return {"ok": not faltando, "cenas_pendentes": faltando}


def _payload_cenas(state: dict) -> list[dict]:
    payload = []
    for i, cena in enumerate(state.get("cenas_texto") or [], 1):
        if not isinstance(cena, dict):
            continue
        payload.append({
            "numero": int(cena.get("numero") or i),
            "texto": str(cena.get("texto") or ""),
            "contexto_visual": str(cena.get("contexto_visual") or ""),
            "personagem_principal": str(cena.get("personagem_principal") or ""),
            "expressao_atual": str(cena.get("expressao") or ""),
            "emocao_travada": bool(cena.get("emocao_travada")),
            "emocao_atual": str(cena.get("emocao") or "") if cena.get("emocao_travada") else "",
        })
    return payload


def analisar_emocoes_automaticamente(state: dict, chamar_llm: Callable) -> dict:
    """Analisa todas as cenas em uma única chamada e gera o mapa cromático.

    O modelo escolhe somente EMOÇÃO/SUBEMOÇÃO/INTENSIDADE/TRANSIÇÃO/EXPRESSÃO.
    Cores não são inventadas pelo modelo: depois da análise, o motor determinístico
    ``construir_mapa_emocional`` converte a emoção para a tabela canônica da
    Psicologia das Cores do FaithBloom.
    """
    cenas = _payload_cenas(state)
    if not cenas:
        raise ValueError("Não há cenas para análise emocional automática.")

    allowed = opcoes_emocao()
    system = f"""Você é o Especialista de Emoção Narrativa Infantil do FaithBloom.
Leia a história como um arco completo e depois analise cada cena no contexto das cenas anteriores e seguintes.
Objetivo: identificar a emoção vivida NAQUELE MOMENTO da narrativa para orientar ambiente, luz e atmosfera sem perder a emoção, qualidade, propósito cristão e faixa etária.

REGRAS:
- Escolha emocao e emocao_secundaria SOMENTE desta taxonomia: {allowed}.
- intensidade deve ser inteiro de 1 a 5.
- transicao_emocional deve ser curta e natural quando houver mudança; pode ser vazia.
- expressao deve descrever a expressão/linguagem corporal compatível com a cena, sem reescrever a história.
- NÃO escolha cores e NÃO recolora personagem. A Psicologia das Cores será aplicada depois por um motor canônico determinístico.
- Preserve emoções travadas pela autora exatamente como recebidas.
- Evite classificar todas as cenas com a mesma emoção; respeite o arco real do texto.
- Não invente eventos, conflitos ou sentimentos que o texto/contexto não sustentem.

Retorne JSON no formato:
{{"cenas":[{{"numero":1,"emocao":"...","emocao_secundaria":"","intensidade":3,"transicao_emocional":"","expressao":"...","justificativa_curta":"..."}}],"resumo_arco":"..."}}
"""
    instruction = json.dumps({
        "titulo": state.get("titulo", ""),
        "faixa_etaria": state.get("faixa_etaria", "3–8"),
        "aprendizado_cristao": state.get("aprendizado_cristao", ""),
        "licao_final": state.get("licao_final", ""),
        "cenas": cenas,
    }, ensure_ascii=False)

    raw = chamar_llm(system, instruction)
    if not isinstance(raw, dict) or not isinstance(raw.get("cenas"), list):
        raise RuntimeError("Especialista emocional retornou formato inválido; nenhuma cor foi aplicada automaticamente.")

    por_numero = {}
    for item in raw.get("cenas") or []:
        if not isinstance(item, dict):
            continue
        try:
            numero = int(item.get("numero"))
            intensidade = int(item.get("intensidade"))
        except (TypeError, ValueError):
            continue
        emocao = str(item.get("emocao") or "").strip()
        secundaria = str(item.get("emocao_secundaria") or "").strip()
        if emocao not in allowed or (secundaria and secundaria not in allowed) or not 1 <= intensidade <= 5:
            continue
        por_numero[numero] = {
            "emocao": emocao,
            "emocao_secundaria": secundaria,
            "intensidade_emocional": intensidade,
            "transicao_emocional": str(item.get("transicao_emocional") or "").strip(),
            "expressao": str(item.get("expressao") or "").strip(),
            "justificativa_curta": str(item.get("justificativa_curta") or "").strip(),
        }

    novo = deepcopy(state)
    faltando = []
    for i, cena in enumerate(novo.get("cenas_texto") or [], 1):
        numero = int(cena.get("numero") or i)
        if cena.get("emocao_travada"):
            continue
        analise = por_numero.get(numero)
        if not analise:
            faltando.append(numero)
            continue
        cena.update({k: v for k, v in analise.items() if k != "justificativa_curta"})
        cena["emocao_origem"] = "especialista_automatico"
        cena["emocao_justificativa"] = analise.get("justificativa_curta", "")

    status = metadata_emocional_completa(novo)
    pendentes = sorted(set(faltando + status.get("cenas_pendentes", [])))
    if pendentes:
        raise RuntimeError(
            "Análise emocional automática ficou incompleta nas cenas "
            + ", ".join(str(x) for x in pendentes)
            + "; nenhuma liberação visual automática foi feita."
        )

    novo["metadata_emocional_confirmada"] = True
    novo["metadata_emocional_modo"] = "automatico_com_override_humano"
    novo["analise_emocional_automatica"] = {
        "resumo_arco": str(raw.get("resumo_arco") or "").strip(),
        "taxonomia": allowed,
        "cores_por_motor_canonico": True,
        "personagem_recolorido": False,
    }
    novo["mapa_emocional"] = construir_mapa_emocional(novo.get("cenas_texto") or [])
    novo["status"] = "mapa_emocional_automatico_pronto"
    return novo


def atualizar_metadata_emocional_cena(
    state: dict,
    numero_cena: int,
    *,
    emocao: str,
    intensidade: int,
    emocao_secundaria: str = "",
    transicao_emocional: str = "",
    expressao: str = "",
) -> dict:
    """Override opcional da autora; não é etapa obrigatória do fluxo rápido."""
    if emocao not in opcoes_emocao():
        raise ValueError("Emoção não reconhecida pelo FaithBloom.")
    if emocao_secundaria and emocao_secundaria not in opcoes_emocao():
        raise ValueError("Subemoção não reconhecida pelo FaithBloom.")
    intensidade = int(intensidade)
    if not 1 <= intensidade <= 5:
        raise ValueError("Intensidade emocional deve ficar entre 1 e 5.")

    novo = deepcopy(state)
    cenas = novo.get("cenas_texto") or []
    alvo = None
    for i, cena in enumerate(cenas, 1):
        if int(cena.get("numero") or i) == int(numero_cena):
            alvo = cena
            break
    if alvo is None:
        raise ValueError(f"Cena {numero_cena} não encontrada.")

    alvo["emocao"] = emocao
    alvo["intensidade_emocional"] = intensidade
    alvo["emocao_secundaria"] = emocao_secundaria
    alvo["transicao_emocional"] = str(transicao_emocional or "").strip()
    alvo["emocao_travada"] = True
    alvo["emocao_origem"] = "override_autora"
    if str(expressao or "").strip():
        alvo["expressao"] = str(expressao).strip()

    status = metadata_emocional_completa(novo)
    novo["metadata_emocional_confirmada"] = status["ok"]
    novo["mapa_emocional"] = construir_mapa_emocional(cenas) if status["ok"] else []
    novo["status"] = "mapa_emocional_confirmado" if status["ok"] else "aguardando_mapa_emocional"
    return salvar_estado_remaster(novo)


def reconstruir_mapa_confirmado(state: dict) -> dict:
    status = metadata_emocional_completa(state)
    if not status["ok"]:
        raise ValueError(f"Metadados emocionais incompletos nas cenas: {status['cenas_pendentes']}")
    novo = deepcopy(state)
    novo["metadata_emocional_confirmada"] = True
    novo["mapa_emocional"] = construir_mapa_emocional(novo.get("cenas_texto") or [])
    novo["status"] = "mapa_emocional_confirmado"
    return salvar_estado_remaster(novo)

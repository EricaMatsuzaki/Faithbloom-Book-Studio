"""Mapa emocional controlado do Full Editorial Remaster.

Não inventa emoção automaticamente. A autora confirma emoção, subemoção,
intensidade e transição por cena; depois o Emotional & Color Director existente
transforma esses dados em direção visual canônica.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

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

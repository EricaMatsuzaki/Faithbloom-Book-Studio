"""Auditoria estruturada de consistência de personagem.

Não inventa percentuais a partir de imagem. O score só existe quando o chamador
fornece explicitamente características observadas/evidenciadas para comparar.
"""
from __future__ import annotations


def auditar_caracteristicas(character: dict, observadas: dict) -> dict:
    dna = character.get("dna", {}) or {}
    bloqueadas = dna.get("campos_bloqueados") or dna.get("caracteristicas_bloqueadas") or {}
    if isinstance(bloqueadas, str):
        return {
            "status": "revisao_humana",
            "avaliadas": 0,
            "coincidentes": 0,
            "divergencias": [],
            "nao_avaliadas": [bloqueadas],
            "score_evidenciado": None,
            "nota": "DNA está em texto livre; normalize em campos estruturados para obter comparação objetiva.",
        }
    divergencias, coincidentes, nao_avaliadas = [], [], []
    for campo, esperado in bloqueadas.items():
        if campo not in observadas:
            nao_avaliadas.append(campo)
            continue
        atual = observadas[campo]
        if str(atual).strip().lower() == str(esperado).strip().lower():
            coincidentes.append(campo)
        else:
            divergencias.append({"campo": campo, "esperado": esperado, "observado": atual})
    avaliadas = len(coincidentes) + len(divergencias)
    score = round(100 * len(coincidentes) / avaliadas, 1) if avaliadas else None
    return {
        "status": "consistente" if avaliadas and not divergencias else ("divergente" if divergencias else "sem_evidencia"),
        "avaliadas": avaliadas,
        "coincidentes": coincidentes,
        "divergencias": divergencias,
        "nao_avaliadas": nao_avaliadas,
        "score_evidenciado": score,
        "nota": "Percentual calculado somente sobre campos explicitamente observados; não é similaridade visual inferida.",
    }

"""Extensão de estado do Refinamento 24 sem quebrar o LivroState legado."""
from __future__ import annotations

from state import LivroState


class LivroStatePromptMestre(LivroState, total=False):
    # Origem criativa / briefing narrativo
    origem_ideia: str                 # ideia_da_autora | ideia_da_ia | projeto_existente
    personagens_historia_brief: str  # briefing livre antes do Character DNA formal
    historia_escolhida_preservar: bool

    # Estilo narrativo formal
    estilo_narrativo: str
    estilo_narrativo_label: str
    comparativo_estilos: dict[str, dict]

    # Complementos editoriais do Prompt-Mestre
    boas_vindas: str
    pais_educadores: dict
    ficha_pedagogica: dict

    # Auditoria do Prompt-Mestre
    prompt_mestre_compliance: dict

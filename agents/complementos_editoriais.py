"""Refinamento 24 — complementos editoriais do Prompt-Mestre.

Gera Boas-vindas, Mensagem para Pais/Educadores e Ficha Pedagógica sem
reescrever a história aprovada e sem inventar texto bíblico.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(str(x) for x in value if str(x).strip())
    if isinstance(value, dict):
        return "\n".join(f"{k}: {v}" for k, v in value.items())
    return str(value or "").strip()


def gerar_complementos_editoriais(state: dict, chamar_llm) -> dict:
    sistema = """
Você é o Editor Pedagógico-Cristão do FaithBloom Book Studio.
Crie SOMENTE três complementos para uma história já definida:
1) mensagem de boas-vindas;
2) mensagem para pais e educadores;
3) ficha pedagógica.

Regras:
- público padrão 3–8 anos;
- linguagem acolhedora, simples e profissional;
- não reescreva a história;
- não invente dados sobre desenvolvimento infantil;
- não invente nem traduza livremente o texto de versículos;
- use somente a REFERÊNCIA bíblica recebida;
- mantenha o princípio cristão amoroso e adequado à infância.

Retorne JSON com:
{
  "boas_vindas": "...",
  "pais_educadores": {
    "mensagem": "...",
    "tema": "...",
    "emocao_trabalhada": "...",
    "principio_biblico": "...",
    "habilidade_socioemocional": "...",
    "perguntas": ["...", "...", "..."],
    "aplicacoes": ["...", "..."]
  },
  "ficha_pedagogica": {
    "faixa_etaria": "3–8 anos",
    "tema_central": "...",
    "emocao_principal": "...",
    "habilidade_socioemocional": "...",
    "valor_cristao": "...",
    "versiculo_referencia": "...",
    "objetivo_pedagogico": "...",
    "psicologia_das_cores": "...",
    "perguntas_reflexao": ["...", "...", "..."]
  }
}
""".strip()
    instrucao = f"""
Título: {state.get('titulo','')}
Estilo narrativo: {state.get('estilo_narrativo_label') or state.get('estilo_narrativo') or 'Estilo 1 — Aventura'}
Tema/ideia: {state.get('_entrada_tema_livre') or state.get('titulo','')}
Emoção central: {state.get('emocao_central','')}
Lição cristã: {state.get('licao_final') or state.get('aprendizado_cristao','')}
Referência bíblica: {state.get('versiculo_referencia','')}
Resumo/sinopse: {state.get('sinopse_poetica','')}
""".strip()
    resposta = chamar_llm(sistema=sistema, instrucao=instrucao)
    if not isinstance(resposta, dict):
        resposta = {}

    pais = resposta.get("pais_educadores") if isinstance(resposta.get("pais_educadores"), dict) else {}
    ficha = resposta.get("ficha_pedagogica") if isinstance(resposta.get("ficha_pedagogica"), dict) else {}

    return {
        "boas_vindas": _as_text(resposta.get("boas_vindas")),
        "pais_educadores": pais,
        "ficha_pedagogica": ficha,
    }


def aplicar_complementos(state: dict, complementos: dict) -> dict:
    novo = deepcopy(state)
    novo["boas_vindas"] = _as_text(complementos.get("boas_vindas"))
    novo["pais_educadores"] = complementos.get("pais_educadores") or {}
    novo["ficha_pedagogica"] = complementos.get("ficha_pedagogica") or {}
    return novo

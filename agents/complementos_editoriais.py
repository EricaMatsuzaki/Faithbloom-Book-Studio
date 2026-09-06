"""Refinamento 24 — complementos editoriais do Prompt-Mestre.

Gera Boas-vindas, Mensagem para Pais/Educadores e Ficha Pedagógica sem
reescrever a história aprovada e sem inventar texto bíblico. A faixa etária
oficial do livro orienta linguagem, perguntas e nível de reflexão.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from age_profiles import normalizar_faixa_etaria, perfil_etario, instrucao_faixa_etaria


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(str(x) for x in value if str(x).strip())
    if isinstance(value, dict):
        return "\n".join(f"{k}: {v}" for k, v in value.items())
    return str(value or "").strip()


def gerar_complementos_editoriais(state: dict, chamar_llm) -> dict:
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    perfil = perfil_etario(faixa)
    qtd_perguntas = int(perfil.get("perguntas_pedagogicas") or 3)

    sistema = f"""
Você é o Editor Pedagógico-Cristão do FaithBloom Book Studio.
Crie SOMENTE três complementos para uma história já definida:
1) mensagem de boas-vindas;
2) mensagem para pais e educadores;
3) ficha pedagógica.

FAIXA ETÁRIA OBRIGATÓRIA:
{instrucao_faixa_etaria(faixa)}

Regras:
- linguagem acolhedora, simples e profissional, adequada à faixa escolhida;
- não reescreva a história;
- não invente dados sobre desenvolvimento infantil;
- não invente nem traduza livremente o texto de versículos;
- use somente a REFERÊNCIA bíblica recebida;
- mantenha o princípio cristão amoroso e adequado à infância;
- perguntas devem combinar com a capacidade de compreensão da faixa, sem infantilizar leitores maiores;
- produza exatamente {qtd_perguntas} perguntas em pais_educadores.perguntas e exatamente {qtd_perguntas} em ficha_pedagogica.perguntas_reflexao.

Retorne JSON com:
{{
  "boas_vindas": "...",
  "pais_educadores": {{
    "mensagem": "...",
    "tema": "...",
    "emocao_trabalhada": "...",
    "principio_biblico": "...",
    "habilidade_socioemocional": "...",
    "perguntas": ["..."],
    "aplicacoes": ["...", "..."]
  }},
  "ficha_pedagogica": {{
    "faixa_etaria": "{perfil['short_label']}",
    "tema_central": "...",
    "emocao_principal": "...",
    "habilidade_socioemocional": "...",
    "valor_cristao": "...",
    "versiculo_referencia": "...",
    "objetivo_pedagogico": "...",
    "psicologia_das_cores": "...",
    "perguntas_reflexao": ["..."]
  }}
}}
""".strip()
    instrucao = f"""
Título: {state.get('titulo','')}
Faixa etária: {perfil['short_label']}
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
    # A faixa oficial vem do projeto, não da geração livre do modelo.
    ficha["faixa_etaria"] = perfil["short_label"]

    return {
        "boas_vindas": _as_text(resposta.get("boas_vindas")),
        "pais_educadores": pais,
        "ficha_pedagogica": ficha,
    }


def aplicar_complementos(state: dict, complementos: dict) -> dict:
    novo = deepcopy(state)
    faixa = normalizar_faixa_etaria(novo.get("faixa_etaria"))
    novo["faixa_etaria"] = faixa
    novo["age_profile_id"] = faixa
    novo["boas_vindas"] = _as_text(complementos.get("boas_vindas"))
    novo["pais_educadores"] = complementos.get("pais_educadores") or {}
    ficha = complementos.get("ficha_pedagogica") or {}
    if isinstance(ficha, dict):
        ficha = deepcopy(ficha)
        ficha["faixa_etaria"] = perfil_etario(faixa)["short_label"]
    novo["ficha_pedagogica"] = ficha
    return novo

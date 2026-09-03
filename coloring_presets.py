"""FaithBloom 2.0 — presets reutilizáveis do Coloring Book Studio.

Os presets ficam separados dos livros. Um preset descreve COMO a line art
será produzida (público, faixa etária, traço, complexidade, fundo e prompt-base).
Ele pode ser usado, duplicado e alterado sem modificar imagens já geradas.
"""
from __future__ import annotations

import time
import uuid

from storage_backend import BACKEND

ARQUIVO_PRESETS = "presets_line_art/presets.json"

PUBLICOS = ["Infantil", "Juvenil", "Adulto", "Personalizado"]
FAIXAS_ETARIAS = [
    "2–4 anos", "3–5 anos", "4–6 anos", "4–8 anos", "6–8 anos",
    "7–10 anos", "8–12 anos", "13+", "Adulto", "Personalizado",
]
ESPESSURAS = ["Muito grosso", "Grosso", "Médio", "Fino", "Muito fino", "Personalizado"]
COMPLEXIDADES = ["Muito simples", "Simples", "Equilibrada", "Detalhada", "Muito detalhada", "Personalizada"]
FUNDOS = ["Sem fundo", "Muito simples", "Simplificado", "Moderado", "Detalhado", "Personalizado"]

PRESETS_PADRAO = [
    {
        "id": "faithbloom-baby-cute",
        "nome": "FaithBloom — Baby Cute",
        "publico": "Infantil",
        "faixa_etaria": "2–4 anos",
        "espessura": "Muito grosso",
        "complexidade": "Muito simples",
        "fundo": "Muito simples",
        "areas": "muito grandes e bem fechadas",
        "nivel_realismo": "muito estilizado e arredondado",
        "prompt_base": "Personagens muito fofos, cabeça grande, formas simples, poucos elementos e amplas áreas para colorir.",
        "favorito": False,
        "sistema": True,
    },
    {
        "id": "faithbloom-cute-cozy",
        "nome": "FaithBloom — Cute & Cozy",
        "publico": "Infantil",
        "faixa_etaria": "4–8 anos",
        "espessura": "Grosso",
        "complexidade": "Equilibrada",
        "fundo": "Simplificado",
        "areas": "grandes e médias",
        "nivel_realismo": "fofo, acolhedor e original",
        "prompt_base": "Cena aconchegante, personagens arredondados e expressivos, objetos simples e composição agradável para colorir.",
        "favorito": True,
        "sistema": True,
    },
    {
        "id": "faithbloom-junior-detail",
        "nome": "FaithBloom — Junior Detail",
        "publico": "Juvenil",
        "faixa_etaria": "8–12 anos",
        "espessura": "Médio",
        "complexidade": "Detalhada",
        "fundo": "Moderado",
        "areas": "médias, com alguns detalhes menores",
        "nivel_realismo": "estilizado com mais detalhes",
        "prompt_base": "Mais detalhes internos e de cenário, mantendo linhas limpas, legíveis e áreas fechadas para colorir.",
        "favorito": False,
        "sistema": True,
    },
    {
        "id": "faithbloom-botanical-relax",
        "nome": "FaithBloom — Botanical Relax",
        "publico": "Adulto",
        "faixa_etaria": "Adulto",
        "espessura": "Fino",
        "complexidade": "Muito detalhada",
        "fundo": "Detalhado",
        "areas": "médias e pequenas, sem microdetalhes inutilizáveis",
        "nivel_realismo": "ornamental/botânico elegante",
        "prompt_base": "Composição relaxante para adultos, flora detalhada, linhas nítidas, sem sombreado preenchido e com equilíbrio visual.",
        "favorito": False,
        "sistema": True,
    },
]


def _ler() -> list[dict]:
    dados = BACKEND.get_json(ARQUIVO_PRESETS, [])
    return dados if isinstance(dados, list) else []


def _salvar(itens: list[dict]) -> None:
    BACKEND.put_json(ARQUIVO_PRESETS, itens)

def garantir_presets_padrao() -> None:
    itens = _ler()
    ids = {p.get("id") for p in itens}
    mudou = False
    for preset in PRESETS_PADRAO:
        if preset["id"] not in ids:
            itens.append(dict(preset))
            mudou = True
    if mudou:
        _salvar(itens)


def listar_presets(publico: str | None = None) -> list[dict]:
    garantir_presets_padrao()
    itens = _ler()
    if publico and publico != "Todos":
        itens = [p for p in itens if p.get("publico") == publico]
    return sorted(itens, key=lambda p: (not p.get("favorito", False), p.get("nome", "").lower()))


def obter_preset(preset_id: str) -> dict | None:
    return next((p for p in listar_presets() if p.get("id") == preset_id), None)


def salvar_preset(dados: dict, preset_id: str | None = None) -> dict:
    itens = _ler()
    agora = int(time.time())
    if preset_id:
        for i, item in enumerate(itens):
            if item.get("id") == preset_id:
                novo = {**item, **dados, "id": preset_id, "atualizado_em": agora, "sistema": False}
                itens[i] = novo
                _salvar(itens)
                return novo
    novo = {
        "id": uuid.uuid4().hex[:12],
        "nome": dados.get("nome") or "Meu estilo",
        "publico": dados.get("publico", "Personalizado"),
        "faixa_etaria": dados.get("faixa_etaria", "Personalizado"),
        "espessura": dados.get("espessura", "Personalizado"),
        "complexidade": dados.get("complexidade", "Personalizada"),
        "fundo": dados.get("fundo", "Personalizado"),
        "areas": dados.get("areas", ""),
        "nivel_realismo": dados.get("nivel_realismo", ""),
        "prompt_base": dados.get("prompt_base", ""),
        "favorito": bool(dados.get("favorito", False)),
        "sistema": False,
        "criado_em": agora,
    }
    itens.append(novo)
    _salvar(itens)
    return novo


def duplicar_preset(preset_id: str, novo_nome: str | None = None) -> dict:
    original = obter_preset(preset_id)
    if not original:
        raise KeyError("Preset não encontrado")
    copia = {k: v for k, v in original.items() if k not in {"id", "criado_em", "atualizado_em", "sistema"}}
    copia["nome"] = novo_nome or f"{original.get('nome', 'Estilo')} — cópia"
    copia["favorito"] = False
    return salvar_preset(copia)


def excluir_preset(preset_id: str) -> bool:
    itens = _ler()
    alvo = next((p for p in itens if p.get("id") == preset_id), None)
    if not alvo or alvo.get("sistema"):
        return False
    novos = [p for p in itens if p.get("id") != preset_id]
    _salvar(novos)
    return len(novos) != len(itens)


def favoritar_preset(preset_id: str, favorito: bool = True) -> None:
    itens = _ler()
    for p in itens:
        if p.get("id") == preset_id:
            p["favorito"] = bool(favorito)
            break
    _salvar(itens)


def preset_para_prompt(preset: dict, instrucao_extra: str = "") -> str:
    partes = [
        f"Público: {preset.get('publico', 'Personalizado')}.",
        f"Faixa etária/nível de uso: {preset.get('faixa_etaria', 'Personalizado')}.",
        f"Espessura do contorno: {preset.get('espessura', 'Personalizado')}.",
        f"Complexidade: {preset.get('complexidade', 'Personalizada')}.",
        f"Fundo: {preset.get('fundo', 'Personalizado')}.",
        f"Áreas para colorir: {preset.get('areas', '')}.",
        f"Nível visual: {preset.get('nivel_realismo', '')}.",
        preset.get("prompt_base", ""),
    ]
    if instrucao_extra.strip():
        partes.append("Instrução específica desta página, sem alterar o preset salvo: " + instrucao_extra.strip())
    return "\n".join(p for p in partes if p and p != ".")

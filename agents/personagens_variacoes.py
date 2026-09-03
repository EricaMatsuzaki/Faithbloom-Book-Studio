"""
FaithBloom 2.0 — variações visuais e aprovação de personagens.

Responsabilidade deste módulo:
- preservar a primeira referência visual;
- gerar novas opções sem apagar as anteriores;
- criar uma variação a partir de uma opção específica;
- aplicar um pedido livre da autora ("mais fofuxa", "mais rosinha"...);
- marcar uma opção como oficial/aprovada antes de gerar as cenas.

A geração usa a função gerar_imagem injetada (OpenRouter hoje), portanto
este módulo continua desacoplado do provedor de imagem.
"""

from __future__ import annotations

import time
import uuid

from agents.ilustrador import ESTILO_VISUAL_FIXO, prompt_referencia_personagem
from agent_skills import skill_contract


def _nova_variacao(caminho: str, origem: str, prompt: str, base: str = "") -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "caminho_arquivo": caminho,
        "origem": origem,
        "prompt": prompt,
        "base": base,
        "favorita": False,
        "criada_em": int(time.time()),
    }


def garantir_variacao_inicial(personagem: dict) -> dict:
    """Registra a referência atual na galeria do personagem sem duplicar."""
    personagem.setdefault("variacoes_visuais", [])
    caminho = personagem.get("imagem_referencia", "")
    if caminho and not any(v.get("caminho_arquivo") == caminho for v in personagem["variacoes_visuais"]):
        personagem["variacoes_visuais"].append(
            _nova_variacao(
                caminho,
                personagem.get("origem_referencia", "referencia_existente") or "referencia_existente",
                "Referência visual inicial do personagem.",
            )
        )
    return personagem


def gerar_primeira_referencia(personagem: dict, gerar_imagem) -> dict:
    """Gera somente a primeira referência e a preserva como Opção 1."""
    personagem = garantir_variacao_inicial(personagem)
    if personagem.get("imagem_referencia"):
        return personagem

    prompt = prompt_referencia_personagem(
        personagem.get("nome", "Personagem"),
        personagem.get("descricao_fixa", ""),
        personagem.get("papel", "personagem"),
    )
    prompt += skill_contract("character_variations", compact=True)
    caminho = gerar_imagem(prompt=prompt, imagem_base=None)
    personagem["imagem_referencia"] = caminho
    personagem["origem_referencia"] = "gerada_pelo_agente"
    personagem["variacoes_visuais"].append(
        _nova_variacao(caminho, "gerada_pelo_agente", prompt)
    )
    personagem.setdefault("variacao_selecionada_id", personagem["variacoes_visuais"][-1]["id"])
    personagem.setdefault("aparencia_aprovada", False)
    return personagem


def gerar_variacao(personagem: dict, gerar_imagem, instrucao: str = "", variacao_base_id: str | None = None) -> dict:
    """Cria uma nova opção sem apagar nenhuma existente.

    Se variacao_base_id for informado, usa aquela imagem como base. Se não,
    usa a referência atualmente selecionada/oficial.
    """
    personagem = garantir_variacao_inicial(personagem)
    variacoes = personagem.get("variacoes_visuais", [])

    base = ""
    if variacao_base_id:
        for v in variacoes:
            if v.get("id") == variacao_base_id:
                base = v.get("caminho_arquivo", "")
                break
    if not base:
        base = personagem.get("imagem_referencia", "")

    regra_preservacao = (
        "Use a imagem de referência como identidade visual principal. Preserve rosto, espécie, "
        "formato dos olhos, proporções reconhecíveis e traços que não foram explicitamente pedidos para mudar. "
        "Crie UMA NOVA VARIAÇÃO; não copie arte/texto de terceiros e não inclua texto na imagem."
    )
    pedido = instrucao.strip() or (
        "Crie uma alternativa visual claramente distinta, mas ainda coerente com o mesmo DNA do personagem. "
        "Varie suavemente expressão, proporção fofa, acabamento e pequenos detalhes autorais, sem mudar a identidade."
    )
    prompt = (
        f"{ESTILO_VISUAL_FIXO}\n"
        f"Personagem: {personagem.get('nome', '')} ({personagem.get('papel', '')}).\n"
        f"DNA visual: {personagem.get('descricao_fixa', '')}\n"
        f"{regra_preservacao}\n"
        f"Pedido da autora: {pedido}\n"
        "Gerar character reference limpa, corpo inteiro bem enquadrado, fundo simples, alta legibilidade visual."
    )
    prompt += skill_contract("character_variations", compact=True)
    caminho = gerar_imagem(prompt=prompt, imagem_base=base or None)
    nova = _nova_variacao(caminho, "variacao_ia", prompt, base=base)
    variacoes.append(nova)
    personagem["variacoes_visuais"] = variacoes
    personagem["variacao_selecionada_id"] = nova["id"]
    personagem["aparencia_aprovada"] = False
    return personagem


def gerar_multiplas_variacoes(personagem: dict, gerar_imagem, quantidade: int = 2, variacao_base_id: str | None = None) -> dict:
    """Gera N alternativas sequencialmente, preservando todas."""
    quantidade = max(1, min(int(quantidade), 4))
    for i in range(quantidade):
        personagem = gerar_variacao(
            personagem,
            gerar_imagem,
            instrucao=(
                f"Crie a alternativa visual número {i + 1} desta rodada. "
                "Ela deve ter personalidade própria, continuar muito fofa e respeitar integralmente o DNA visual."
            ),
            variacao_base_id=variacao_base_id,
        )
    return personagem


def selecionar_variacao(personagem: dict, variacao_id: str) -> dict:
    personagem = garantir_variacao_inicial(personagem)
    for v in personagem.get("variacoes_visuais", []):
        if v.get("id") == variacao_id:
            personagem["variacao_selecionada_id"] = variacao_id
            return personagem
    return personagem


def aprovar_variacao(personagem: dict, variacao_id: str) -> dict:
    """Promove a opção escolhida a referência oficial/travada do personagem."""
    personagem = garantir_variacao_inicial(personagem)
    for v in personagem.get("variacoes_visuais", []):
        if v.get("id") == variacao_id:
            personagem["imagem_referencia"] = v.get("caminho_arquivo", "")
            personagem["origem_referencia"] = v.get("origem", "variacao_aprovada")
            personagem["variacao_selecionada_id"] = variacao_id
            personagem["aparencia_aprovada"] = True
            personagem["dna_visual_travado"] = True
            return personagem
    raise ValueError("Variação visual não encontrada para aprovação.")


def favoritar_variacao(personagem: dict, variacao_id: str, favorita: bool = True) -> dict:
    personagem = garantir_variacao_inicial(personagem)
    for v in personagem.get("variacoes_visuais", []):
        if v.get("id") == variacao_id:
            v["favorita"] = bool(favorita)
            break
    return personagem


def registrar_variacao_externa(personagem: dict, caminho: str, origem: str = "enviada_pela_autora", descricao: str = "Imagem enviada pela autora") -> dict:
    """Adiciona uma imagem externa às opções sem apagar nenhuma anterior."""
    personagem = garantir_variacao_inicial(personagem)
    nova = _nova_variacao(caminho, origem, descricao)
    personagem.setdefault("variacoes_visuais", []).append(nova)
    personagem["variacao_selecionada_id"] = nova["id"]
    personagem["aparencia_aprovada"] = False
    return personagem


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('character_variations',)

"""
Editor Editorial do FaithBloom.

Permite revisar uma história cena a cena sem reescrever o livro inteiro.
Também sugere alternativas de versículo e lição de moral, sempre com
aprovação humana antes de substituir o conteúdo atual.
"""

from copy import deepcopy
from agent_skills import skill_contract


def _como_lista(resposta, chave: str) -> list:
    """Aceita tanto lista JSON direta quanto objeto {chave: [...]} do LLM."""
    if isinstance(resposta, list):
        return resposta
    if isinstance(resposta, dict):
        valor = resposta.get(chave, [])
        return valor if isinstance(valor, list) else []
    return []


def editar_cena(cena: dict, instrucao: str, state: dict, chamar_llm) -> dict:
    """Reescreve SOMENTE uma cena e preserva o restante do livro."""
    sistema = f"""\
Você é o Editor Editorial do FaithBloom Book Studio.
Edite SOMENTE a cena informada. NÃO reescreva outras cenas e NÃO altere
versículo, título, lição final ou personagens do livro.

Público: crianças de 3 a 8 anos.
Regras:
- frases curtas, simples, naturais e musicais para leitura em voz alta;
- emoções concretas e fáceis de compreender;
- sem metáforas complexas;
- preserve continuidade de personagens, cenário e figurino;
- mantenha o princípio cristão natural e adequado à história;
- se a instrução pedir menos diálogo, reduza falas sem perder emoção;
- se pedir mais emoção, aumente ação/expressão concreta, não abstrações.

Contexto do livro:
Título: {state.get('titulo', '')}
Lição: {state.get('aprendizado_cristao', '')}
Versículo: {state.get('versiculo_referencia', '')}

Cena atual:
{cena}

Pedido da autora:
{instrucao}
"""
    sistema += skill_contract("story_editor")
    resposta = chamar_llm(
        sistema=sistema,
        instrucao=(
            "Responda em JSON com as chaves texto, emocao, figurino e "
            "contexto_visual. Preserve o numero e personagem_principal."
        ),
    )
    if not isinstance(resposta, dict):
        return deepcopy(cena)

    nova = deepcopy(cena)
    for campo in ("texto", "emocao", "figurino", "contexto_visual"):
        if resposta.get(campo):
            nova[campo] = resposta[campo]
    return nova


def sugerir_versiculos(state: dict, chamar_llm, quantidade: int = 3) -> list[dict]:
    sistema = f"""\
Você é o Curador Bíblico do FaithBloom Book Studio.
Sugira {quantidade} referências bíblicas que combinem naturalmente com esta história infantil.
NÃO invente referências. Não escreva sermão. Dê alternativas para a autora escolher.
IMPORTANTE: todas as referências são CANDIDATAS, não validadas. Não forneça nem traduza o texto do versículo.

Título: {state.get('titulo', '')}
Tema/emoção: {state.get('emocao_central', '')}
Aprendizado cristão: {state.get('aprendizado_cristao', '')}
Versículo atual: {state.get('versiculo_referencia', '')}
Resumo/cenas: {state.get('cenas_texto', [])}
"""
    sistema += skill_contract("story_editor")
    resposta = chamar_llm(
        sistema=sistema,
        instrucao=(
            "Responda em JSON no formato {\"opcoes\":[{\"referencia\":\"...\","
            "\"motivo\":\"explicação curta\"}]}."
        ),
    )
    return _como_lista(resposta, "opcoes")


def sugerir_licoes(state: dict, chamar_llm, quantidade: int = 3) -> list[dict]:
    sistema = f"""\
Você é o Editor de Valores Cristãos do FaithBloom Book Studio.
Sugira {quantidade} alternativas CURTAS de lição de moral para crianças de 3 a 8 anos.
A mensagem deve ser feliz, concreta, simples e coerente com a história.
Não mude o enredo.

Título: {state.get('titulo', '')}
Aprendizado atual: {state.get('aprendizado_cristao', '')}
Lição final atual: {state.get('licao_final', '')}
Cenas: {state.get('cenas_texto', [])}
"""
    sistema += skill_contract("story_editor")
    resposta = chamar_llm(
        sistema=sistema,
        instrucao=(
            "Responda em JSON no formato {\"opcoes\":[{\"licao\":\"...\","
            "\"motivo\":\"explicação curta\"}]}."
        ),
    )
    return _como_lista(resposta, "opcoes")


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('story_editor',)

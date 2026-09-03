"""
Agente Sinopse de Vendas.

Gera DUAS versões separadas, com objetivo comercial (não confundir com
a sinopse poética do Roteirista, que é pro clima interno do livro):

- sinopse_vendas_curta: pra descrição de produto na KDP (limite de
  caracteres, primeira coisa que o comprador vê).
- sinopse_contracapa: texto impresso na contracapa física, pode ser
  um pouco mais longo/poético.

Estrutura: gancho -> personagem/conflito (sem spoiler do final) ->
lição/valor que a criança aprende -> chamada emocional final.
"""

from state import LivroState
from agent_skills import skill_contract

PROMPT_SINOPSE = """\
Você é o agente de Copywriting de Vendas da coleção. Escreva DUAS
versões da sinopse, com objetivo de converter (fazer o comprador parar
de rolar a tela), não só resumir a história:

1. sinopse_vendas_curta: para a descrição de produto na Amazon KDP.
   Objetiva, com gancho forte na primeira frase. Pode incluir palavras-
   chave de SEO relevantes (ex: "livro infantil cristão", tema da lição).
2. sinopse_contracapa: para impressão física na contracapa. Pode ser
   um pouco mais longa e poética.

Estrutura obrigatória em ambas:
- Gancho inicial (pergunta ou situação que a criança/pai reconhece)
- Apresentação do personagem e conflito, SEM entregar o final
- A lição/valor que a criança vai aprender (isso é o que convence o pai)
- Chamada emocional final (conexão com o momento de leitura em família)

Dados do livro:
Título: {titulo}
Sinopse poética (interna, não copiar literalmente): {sinopse_poetica}
Lição: {aprendizado_cristao}
"""


def sinopse_node(state: LivroState, chamar_llm) -> LivroState:
    prompt = PROMPT_SINOPSE.format(
        titulo=state["titulo"],
        sinopse_poetica=state.get("sinopse_poetica", state.get("titulo", "")),
        aprendizado_cristao=state["aprendizado_cristao"],
    )
    prompt += skill_contract("sales_synopsis")
    resposta = chamar_llm(sistema=prompt, instrucao="Gere as duas versões.")
    state["sinopse_vendas_curta"] = resposta.get("sinopse_vendas_curta", "")
    state["sinopse_contracapa"] = resposta.get("sinopse_contracapa", "")
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('sales_synopsis',)

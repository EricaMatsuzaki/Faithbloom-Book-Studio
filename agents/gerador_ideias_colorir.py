"""
Agente Gerador de Ideias - Livro de Colorir.

Diferente do gerador_ideias.py (que sugere TEMAS DE HISTÓRIA, com
emoção/versículo/lição), este sugere CONCEITOS DE LIVRO DE COLORIR -
que não precisam de narrativa nenhuma, só um tema visual coeso e uma
lista de páginas/personagens/objetos dentro dele.

Cobre qualquer tipo de tema, não só bichinhos: princesas, carros,
aviões, navios, objetos fofos, etc. - por isso cada ideia sugerida já
vem marcando se aquele tema precisa do código visual macho/fêmea (faz
sentido pra bichinhos/personagens com gênero) ou não (carros, aviões,
navios, objetos não têm gênero - usam só o estilo base).
"""

from agent_skills import skill_contract

TEMAS_EXEMPLO = [
    "bichinhos fofos", "princesas encantadas", "carrinhos da cidade",
    "aviões e foguetes", "navios e piratas", "dinossauros fofos",
    "objetos fofos do dia a dia (xícara, guarda-chuva, sorvete)",
    "fadas e unicórnios", "super-heróis fofos", "insetos e jardim",
]

PROMPT_IDEIAS_COLORIR = """\
Você é o Gerador de Ideias para livros de colorir (line art) infantis.
A autora já lançou um livro de bichinhos fofos ("Cute Friends") e quer
variar os temas dos próximos - não precisam ser animais.

Gere {quantidade} ideias de livro de colorir NOVAS e diferentes entre
si, cobrindo tipos de tema variados (pode incluir personagens com
gênero como princesas/bichinhos, e também temas sem gênero como
carros/aviões/navios/objetos). Para cada ideia:

- Um título curto e atrativo (ex: "Aviões Fofos ao Redor do Mundo",
  "Princesas do Reino Encantado")
- O tema geral em 1 frase
- Se esse tema precisa do código visual macho/fêmea (personagens com
  gênero: bichinhos, princesas, heróis) ou não (veículos, objetos,
  formas - esses usam só o estilo base fofo, sem distinção de gênero)
- Uma lista de 8 a 12 sugestões de página/personagem dentro do tema
  (ex: pra "Aviões Fofos": "avião de caça sorridente", "helicóptero
  resgate", "balão de ar quente", ...)

Temas já lançados ou em andamento (não repetir): {temas_usados}

Responda em JSON: lista de objetos com titulo_sugerido, tema_geral,
precisa_codigo_sexo (true/false), sugestoes_paginas (lista de strings).
"""


def gerador_ideias_colorir_node(quantidade: int, temas_usados: list[str], chamar_llm) -> list[dict]:
    prompt = PROMPT_IDEIAS_COLORIR.format(
        quantidade=quantidade,
        temas_usados=", ".join(temas_usados) if temas_usados else "(nenhum ainda)",
    )
    prompt += skill_contract("coloring_idea_generator")
    resposta = chamar_llm(sistema=prompt, instrucao="Gere as ideias em JSON.")
    if isinstance(resposta, list):
        return resposta
    if isinstance(resposta, dict):
        return resposta.get("ideias", [])
    return []


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('coloring_idea_generator',)

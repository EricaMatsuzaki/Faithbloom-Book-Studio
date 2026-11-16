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
    ideias = resposta if isinstance(resposta, list) else resposta.get("ideias", []) if isinstance(resposta, dict) else []
    campos = ('titulo_sugerido', 'tema_geral')
    if not isinstance(ideias, list) or not ideias or any(
        not isinstance(ideia, dict) or any(not isinstance(ideia.get(campo), str) or not ideia[campo].strip() for campo in campos)
        for ideia in ideias
    ):
        raise ValueError("O gerador não retornou ideias completas; nenhuma sugestão vazia foi aceita.")
    if any(type(ideia.get("precisa_codigo_sexo")) is not bool or not isinstance(ideia.get("sugestoes_paginas"), list)
           or not ideia["sugestoes_paginas"] or any(not isinstance(x, str) or not x.strip() for x in ideia["sugestoes_paginas"])
           for ideia in ideias):
        raise ValueError("As ideias de colorir precisam indicar os sujeitos e páginas do conceito.")
    return ideias


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('coloring_idea_generator',)

"""
Criador de Personagem Novo.

Quando a história pede um personagem que ainda não existe na "biblioteca"
da autora (ex: precisa de um coelhinho pra essa história específica),
esse helper expande uma ideia curta ("um coelhinho tímido") numa
descrição fixa (DNA) completa e pronta pro Ilustrador usar - já seguindo
as regras de estilo visual da coleção (proporções fofas, sem citar
nenhum estúdio de animação).

Diferente dos outros agentes, este é usado sob demanda (não faz parte
do fluxo automático do grafo) - a autora aciona quando precisa de um
personagem novo, na tela de cadastro de personagens.
"""

from state import PersonagemDNA
from agent_skills import skill_contract
from agents.ilustrador import ESTILO_VISUAL_FIXO

PROMPT_CRIADOR_PERSONAGEM = """\
Você expande uma ideia curta de personagem numa descrição fixa (DNA
visual) completa, para um livro infantil cristão de 3-8 anos.

Regras de estilo obrigatórias:
{estilo_visual}

A descrição fixa deve incluir: espécie/tipo, cor principal da
pelagem/pele, cor e formato dos olhos, um acessório ou marca
característica (laço, cachecol, mancha, etc.), e a proporção do corpo
(sempre fofo: cabeça grande, corpo pequeno e rechonchudo). Não inclua
roupa/figurino de cena específica aqui - isso é definido depois, cena a
cena, pelo Roteirista.

Ideia curta da autora: "{ideia_curta}"
Papel do personagem na história: {papel}

Responda em JSON: {{"nome_sugerido": "...", "descricao_fixa": "..."}}
"""


def criar_personagem_a_partir_de_ideia(
    ideia_curta: str, papel: str, chamar_llm
) -> PersonagemDNA:
    prompt = PROMPT_CRIADOR_PERSONAGEM.format(
        estilo_visual=ESTILO_VISUAL_FIXO,
        ideia_curta=ideia_curta,
        papel=papel,
    )
    prompt += skill_contract("character_creator")
    resposta = chamar_llm(sistema=prompt, instrucao="Gere o personagem em JSON.")
    return PersonagemDNA(
        nome=resposta.get("nome_sugerido", ""),
        descricao_fixa=resposta.get("descricao_fixa", ""),
        imagem_referencia="",
        origem_referencia="",
        papel=papel,
    )


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('character_creator',)

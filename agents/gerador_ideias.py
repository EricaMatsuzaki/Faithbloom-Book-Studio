"""
Agente Gerador de Ideias.

Sugere temas/conceitos de livros novos para quando a autora não tiver
uma ideia pronta. Diferente do Curador de Tema (que pega UM tema/resumo
e o transforma em emoção+versículo+lição), este agente parte do zero e
sugere VÁRIAS ideias de tema, pra autora escolher uma.

Cada ideia sugerida já vem com: um conflito/situação simples do
cotidiano infantil, a emoção provável envolvida, e uma pista de
possível lição cristã - o suficiente pra autora decidir se quer seguir
com aquela ideia (que então passa pelo Curador de Tema ou direto pro
Roteirista).
"""

from state import LivroState
from agent_skills import skill_contract
from emotion_colors import EMOCOES

PROMPT_IDEIAS = """\
Você é o Gerador de Ideias de uma coleção de livros infantis cristãos para 3-8 anos.
Coleção atual: {colecao}. Crédito/autoria atual: {author_credit}.
Não presuma personagens fixos de outra coleção; proponha situações que possam
ser adaptadas aos personagens oficiais do projeto.

Gere {quantidade} ideias de tema NOVAS e diferentes entre si. Cada
ideia deve ter:
- Uma situação simples do cotidiano de uma criança pequena (brincar,
  esperar, dividir, ter medo do escuro, mudar de casa, fazer um novo
  amigo, perder algo, etc.)
- A emoção central envolvida, escolhida entre: {emocoes_validas}
- Uma pista da possível lição cristã (sem repetir literalmente lições
  já usadas, se a lista de temas já usados for informada)
- Um título curto e poético no estilo "Quando [personagem] aprendeu a/o [lição]"

Temas já usados nesta coleção (não repetir a mesma lição/situação):
{temas_usados}

Responda em JSON: lista de objetos com titulo_sugerido, situacao,
emocao_central, pista_licao.
"""


def gerador_ideias_node(quantidade: int, temas_usados: list[str], chamar_llm, colecao: str = "", author_credit: str = "") -> list[dict]:
    prompt = PROMPT_IDEIAS.format(
        quantidade=quantidade,
        emocoes_validas=", ".join(EMOCOES.keys()),
        temas_usados=", ".join(temas_usados) if temas_usados else "(nenhum ainda)",
        colecao=colecao or "coleção atual",
        author_credit=author_credit or "não definido",
    )
    prompt += skill_contract("idea_generator")
    resposta = chamar_llm(sistema=prompt, instrucao="Gere as ideias em JSON.")
    if isinstance(resposta, list):
        return resposta
    if isinstance(resposta, dict):
        return resposta.get("ideias", [])
    return []


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('idea_generator',)

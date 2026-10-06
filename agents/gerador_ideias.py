"""
Agente Gerador de Ideias.

Sugere temas/conceitos de livros novos para quando a autora não tiver
uma ideia pronta. Diferente do Curador de Tema (que pega UM tema/resumo
e o transforma em emoção+versículo+lição), este agente parte do zero e
sugere VÁRIAS ideias de tema, pra autora escolher uma.

Cada ideia sugerida já vem com: um conflito/situação adequada à faixa
etária, a emoção provável envolvida, e uma pista de possível lição cristã.
"""

from agent_skills import skill_contract
from emotion_colors import EMOCOES
from age_profiles import normalizar_faixa_etaria, perfil_etario, instrucao_faixa_etaria

PROMPT_IDEIAS = """\
Você é o Gerador de Ideias de uma coleção de livros infantis cristãos.
Coleção atual: {colecao}. Crédito/autoria atual: {author_credit}.

{instrucao_idade}

Não presuma personagens fixos de outra coleção; proponha situações que possam
ser adaptadas aos personagens oficiais do projeto.

Gere {quantidade} ideias de tema NOVAS e diferentes entre si. Cada ideia deve ter:
- Uma situação adequada à idade escolhida e reconhecível pelo público;
- Um pequeno desejo, problema ou conflito compatível com a maturidade da faixa;
- A emoção central envolvida, escolhida entre: {emocoes_validas};
- Uma pista da possível lição cristã, adequada à faixa etária e sem doutrina complexa;
- Um título curto e memorável. Para faixas menores, títulos no estilo
  "Quando [personagem] aprendeu..." são bem-vindos; para leitores maiores,
  não force esse molde se um título mais natural funcionar melhor.

Temas já usados nesta coleção (não repetir a mesma lição/situação):
{temas_usados}

Responda em JSON: lista de objetos com titulo_sugerido, situacao,
emocao_central, pista_licao.
"""


def gerador_ideias_node(
    quantidade: int,
    temas_usados: list[str],
    chamar_llm,
    colecao: str = "",
    author_credit: str = "",
    faixa_etaria: str = "3-8",
) -> list[dict]:
    faixa = normalizar_faixa_etaria(faixa_etaria)
    perfil = perfil_etario(faixa)
    prompt = PROMPT_IDEIAS.format(
        quantidade=quantidade,
        emocoes_validas=", ".join(EMOCOES.keys()),
        temas_usados=", ".join(temas_usados) if temas_usados else "(nenhum ainda)",
        colecao=colecao or "coleção atual",
        author_credit=author_credit or "não definido",
        instrucao_idade=instrucao_faixa_etaria(faixa),
    )
    prompt += (
        f"\nLimites editoriais de legibilidade para esta faixa: até aproximadamente "
        f"{perfil['max_words_sentence']} palavras por frase e {perfil['max_words_scene']} "
        "palavras por cena como teto heurístico de revisão, não como meta de enchimento."
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

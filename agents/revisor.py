"""
Agente Revisor.

Checa continuidade (figurino, cenário, objetos que não podem sumir sem
explicação), gramática, adequação etária e se a cadência narrativa fixa
foi seguida. Pode devolver a história pro Roteirista com notas (loop).
"""

from state import LivroState
from agent_skills import skill_contract

PROMPT_REVISOR = """\
Você é o Revisor/Editor da coleção. Analise a lista de cenas a seguir e
verifique:

1. Continuidade de figurino: um item de roupa/acessório só pode mudar se
   a narrativa indicar mudança de contexto (novo dia, nova situação).
2. Continuidade de objetos/cenário: nada que apareceu como importante
   pode sumir sem explicação.
3. Gramática e fluidez.
4. Adequação etária ESTRITA para 3-8 anos: frases curtas (5-15
   palavras), vocabulário simples, emoções descritas de forma CONCRETA
   (ex: "coração quentinho", "Mel ficou triste") - nunca metáfora
   complexa ou abstração. Reprove qualquer frase longa demais, palavra
   difícil, ou sentimento explicado de forma abstrata.
5. Repetição suave presente (frase-chave, som ou estrutura repetida ao
   longo da história).
6. Ação visual em cada cena (algo acontecendo, não só descrição parada).
7. A cadência curiosidade -> desafio -> emoção -> aprendizado -> fé ->
   gratidão está presente na ordem certa?
8. O texto soa bem em leitura EM VOZ ALTA (ritmo natural, sem
   trava-línguas)?

Se tudo estiver certo, responda APROVADO. Se houver problema, responda
REVISAR e liste as notas especificamente por número de cena.
"""


def revisor_node(state: LivroState, chamar_llm) -> LivroState:
    resposta = chamar_llm(
        sistema=PROMPT_REVISOR + skill_contract("story_reviewer"),
        instrucao=f"Cenas: {state['cenas_texto']}",
    )
    aprovado = resposta.get("status") == "APROVADO"
    state["revisao_aprovada"] = aprovado
    state["notas_revisor"] = resposta.get("notas", [])
    return state


def precisa_retrabalho(state: LivroState) -> str:
    """Função de roteamento condicional do LangGraph."""
    return "roteirista" if not state.get("revisao_aprovada") else "ilustrador"


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('story_reviewer',)

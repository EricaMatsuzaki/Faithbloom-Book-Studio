"""
Agente de Marketing de Lançamento.

Gera o material de divulgação do lançamento - não gera vendas
sozinho, mas tira o "branco na hora de escrever o post" que costuma
atrasar o lançamento de verdade. Cobre: post de Instagram/redes
sociais, descrição pra Pinterest, e-mail de anúncio pra lista de
contatos, e o pedido de avaliação (review) pros primeiros leitores -
que é um dos fatores que mais pesa pra um livro ganhar tração na KDP
logo nos primeiros dias.
"""

from state import LivroState
from agent_skills import skill_contract

PROMPT_MARKETING = """\
Você escreve o material de lançamento de um livro infantil cristão da
coleção "{colecao}", no tom caloroso e pessoal definido para este projeto.
Crédito/autoria do livro: {author_credit}. Não presuma que o usuário logado
é a pessoa que assina a obra e não invente biografia do autor.

Gere:
1. legenda_instagram: um post de Instagram/redes sociais (com 3-5
   hashtags relevantes no fim, sem exagerar)
2. descricao_pinterest: uma descrição curta otimizada pra Pinterest
   (bom pra tráfego de busca, menciona a lição do livro)
3. email_lancamento: um e-mail curto de anúncio pra lista de contatos/
   amigos, convidando pra conhecer o livro
4. pedido_avaliacao: uma mensagem carinhosa e neutra para convidar leitores
   elegíveis a deixar uma avaliação honesta, sem pedir avaliação positiva,
   sem recompensa e sem afirmar que reviews garantem ranking/visibilidade

Dados do livro:
Título: {titulo}
Sinopse de vendas: {sinopse_vendas_curta}
Lição: {aprendizado_cristao}

Responda em JSON com essas 4 chaves.
"""


def marketing_lancamento_node(state: LivroState, chamar_llm) -> LivroState:
    prompt = PROMPT_MARKETING.format(
        colecao=state.get("colecao", ""),
        author_credit=__import__("author_profiles").author_display_from_state(state) or "não definida",
        titulo=state.get("titulo", ""),
        sinopse_vendas_curta=state.get("sinopse_vendas_curta", ""),
        aprendizado_cristao=state.get("aprendizado_cristao", ""),
    )
    prompt += skill_contract("marketing_launch")
    resposta = chamar_llm(sistema=prompt, instrucao="Gere o material de lançamento em JSON.")
    state["material_lancamento"] = resposta
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('marketing_launch',)

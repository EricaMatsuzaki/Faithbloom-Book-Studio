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

PROMPT_MARKETING = """\
Você escreve o material de lançamento de um livro infantil cristão da
coleção "{colecao}", no tom caloroso e pessoal da autora Erica
Matsuzaki (não corporativo, não robótico - como se ela estivesse
contando pra amigos e família sobre o livro novo).

Gere:
1. legenda_instagram: um post de Instagram/redes sociais (com 3-5
   hashtags relevantes no fim, sem exagerar)
2. descricao_pinterest: uma descrição curta otimizada pra Pinterest
   (bom pra tráfego de busca, menciona a lição do livro)
3. email_lancamento: um e-mail curto de anúncio pra lista de contatos/
   amigos, convidando pra conhecer o livro
4. pedido_avaliacao: uma mensagem carinhosa pra pedir avaliação
   (review) na Amazon pros primeiros leitores/família - isso é
   importante porque reviews rápidas logo no lançamento ajudam muito
   na visibilidade do livro na plataforma

Dados do livro:
Título: {titulo}
Sinopse de vendas: {sinopse_vendas_curta}
Lição: {aprendizado_cristao}

Responda em JSON com essas 4 chaves.
"""


def marketing_lancamento_node(state: LivroState, chamar_llm) -> LivroState:
    prompt = PROMPT_MARKETING.format(
        colecao=state.get("colecao", ""),
        titulo=state.get("titulo", ""),
        sinopse_vendas_curta=state.get("sinopse_vendas_curta", ""),
        aprendizado_cristao=state.get("aprendizado_cristao", ""),
    )
    resposta = chamar_llm(sistema=prompt, instrucao="Gere o material de lançamento em JSON.")
    state["material_lancamento"] = resposta
    return state

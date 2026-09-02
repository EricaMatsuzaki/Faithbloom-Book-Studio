"""
Agente de Pesquisa de Mercado - palavras-chave e categorias.

IMPORTANTE, pra calibrar expectativa: este agente NÃO tem acesso a
dados reais de venda/busca da Amazon (não existe API pública de
volume de busca da KDP). Ele gera sugestões com base em conhecimento
geral de SEO/categoria de livro infantil cristão, seguindo as boas
práticas documentadas da própria KDP - é um bom ponto de partida, não
uma pesquisa de mercado real com dados. Validação de verdade só
acontece observando o desempenho depois de publicado (Author Central,
KDP Reports) ou usando ferramentas de terceiros com dados reais
(Publisher Rocket, etc.), que estão fora deste pipeline.

O que a KDP permite hoje (verificado ago/2026):
- 7 campos de palavras-chave (frases, não palavras soltas) na tela de
  cadastro do livro
- 2 categorias escolhidas na tela + até mais via e-mail de suporte da
  KDP pedindo categorias adicionais (prática documentada, não é bug)
"""

from state import LivroState

PROMPT_PALAVRAS_CHAVE = """\
Você é especialista em SEO de listagem da Amazon KDP para livros
infantis cristãos. Sugira exatamente 7 frases-chave (não palavras
soltas) para os campos de keyword do KDP, seguindo essas regras da
própria Amazon:
- Frases de long-tail (3-5 palavras), não termos genéricos de uma
  palavra só
- Nunca usar nome de marca de terceiros, nem palavras como "bestseller"
  ou "grátis" (violam a política da KDP)
- Cobrir ângulos diferentes: tema/lição (ex: "livro sobre paciência
  para crianças"), ocasião (ex: "presente batismo menina"), formato
  ("livro ilustrado cristão 3 anos"), personagem/gênero

Dados do livro:
Título: {titulo}
Tema/lição: {aprendizado_cristao}
Emoção central: {emocao_central}
Sinopse: {sinopse_vendas_curta}

Responda em JSON: lista de 7 strings.
"""

PROMPT_CATEGORIAS = """\
Você é especialista em categorização de livros na Amazon KDP. Sugira
caminhos de categoria (Browse Category) da árvore da KDP pra esse
livro - priorize categorias ESPECÍFICAS e menos disputadas em vez de
categorias amplas (é mais fácil um livro virar "Nº1 Mais Vendido" numa
subcategoria de nicho do que numa categoria ampla). Sugira 5
categorias, sabendo que a autora pode escolher 2 na tela do KDP e
pedir as outras 3 por e-mail de suporte (prática permitida pela KDP).

Dados do livro:
Título: {titulo}
Tema/lição: {aprendizado_cristao}

Responda em JSON: lista de 5 strings, cada uma um caminho de categoria
plausível (ex: "Books > Children's Books > Religions > Christian >
Values & Virtues").
"""


def pesquisa_palavras_chave_node(state: LivroState, chamar_llm) -> LivroState:
    prompt = PROMPT_PALAVRAS_CHAVE.format(
        titulo=state.get("titulo", ""),
        aprendizado_cristao=state.get("aprendizado_cristao", ""),
        emocao_central=state.get("emocao_central", ""),
        sinopse_vendas_curta=state.get("sinopse_vendas_curta", ""),
    )
    resposta = chamar_llm(sistema=prompt, instrucao="Gere as 7 frases-chave em JSON.")
    state["palavras_chave_kdp"] = resposta.get("palavras_chave", resposta if isinstance(resposta, list) else [])
    return state


def pesquisa_categorias_node(state: LivroState, chamar_llm) -> LivroState:
    prompt = PROMPT_CATEGORIAS.format(
        titulo=state.get("titulo", ""),
        aprendizado_cristao=state.get("aprendizado_cristao", ""),
    )
    resposta = chamar_llm(sistema=prompt, instrucao="Gere as 5 categorias sugeridas em JSON.")
    state["categorias_sugeridas"] = resposta.get("categorias", resposta if isinstance(resposta, list) else [])
    return state

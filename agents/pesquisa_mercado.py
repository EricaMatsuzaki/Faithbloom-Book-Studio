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
- até 3 categorias selecionadas na configuração do título; a disponibilidade
  varia conforme marketplace, público e formato
"""

from state import LivroState
from agent_skills import skill_contract
from market_intelligence import evidence_prompt, classify_market_mode

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
caminhos de categoria (Browse Category) da árvore da KDP para esse
livro. Priorize categorias ESPECÍFICAS e genuinamente relevantes ao conteúdo;
nunca escolha categoria irrelevante apenas para tentar manipular ranking.
Sugira exatamente 3 categorias altamente relevantes. A árvore disponível pode
variar por marketplace; não invente uma estratégia baseada em categorias irrelevantes.

Dados do livro:
Título: {titulo}
Tema/lição: {aprendizado_cristao}

Responda em JSON: lista de 3 strings, cada uma um caminho de categoria
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
    prompt += "\n" + evidence_prompt(state.get("market_evidence") or []) + skill_contract("market_keywords")
    resposta = chamar_llm(sistema=prompt, instrucao="Gere as 7 frases-chave em JSON.")
    state["palavras_chave_kdp"] = resposta if isinstance(resposta, list) else resposta.get("palavras_chave", []) if isinstance(resposta, dict) else []
    state["market_suggestions_provenance"] = classify_market_mode(state.get("market_evidence") or [])
    return state


def pesquisa_categorias_node(state: LivroState, chamar_llm) -> LivroState:
    prompt = PROMPT_CATEGORIAS.format(
        titulo=state.get("titulo", ""),
        aprendizado_cristao=state.get("aprendizado_cristao", ""),
    )
    prompt += "\n" + evidence_prompt(state.get("market_evidence") or []) + skill_contract("market_categories")
    resposta = chamar_llm(sistema=prompt, instrucao="Gere as 3 categorias sugeridas em JSON.")
    state["categorias_sugeridas"] = resposta if isinstance(resposta, list) else resposta.get("categorias", []) if isinstance(resposta, dict) else []
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('market_keywords', 'market_categories')

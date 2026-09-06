"""
Agente Sinopse de Vendas.

Gera DUAS versões separadas, com objetivo comercial (não confundir com
a sinopse poética do Roteirista, que é para o clima interno do livro):

- sinopse_vendas_curta: descrição de produto;
- sinopse_contracapa: texto impresso na contracapa física.

A voz comercial respeita a faixa etária oficial do livro sem fazer promessa
de ranking, desempenho ou benefício pedagógico não comprovado.
"""

from state import LivroState
from agent_skills import skill_contract
from age_profiles import normalizar_faixa_etaria, perfil_etario

PROMPT_SINOPSE = """\
Você é o agente de Copywriting Editorial do FaithBloom Book Studio.
Escreva DUAS versões da sinopse para apresentar este livro com clareza,
calor e apelo comercial, sem exageros nem promessas não verificáveis.

PÚBLICO DO LIVRO: {faixa_label} — {publico}.
A voz da sinopse deve combinar com essa faixa: não infantilize leitores
9–12 e não use linguagem adulta para livros de 3–5.

1. sinopse_vendas_curta: descrição objetiva de produto, com um gancho forte
   na primeira frase. Pode usar expressões descritivas relevantes ao conteúdo,
   como "livro infantil cristão" ou o tema real da história, mas não force SEO,
   não faça keyword stuffing e não afirme ranking/best-seller.
2. sinopse_contracapa: texto físico um pouco mais literário e emocional,
   ainda claro para quem compra o livro.

Estrutura sugerida em ambas:
- gancho inicial relacionado ao desejo/conflito da história;
- personagem e desafio, sem revelar toda a resolução;
- valor/lição realmente presente no enredo;
- convite emocional à experiência de leitura adequado à faixa.

Regras:
- não invente prêmios, avaliações, dados pedagógicos, vendas ou benefícios comprovados;
- não prometa que a criança vai mudar comportamento, aprender mais rápido ou melhorar desempenho;
- não transforme a sinopse em sermão;
- preserve a mensagem cristã amorosa da obra;
- não cite o texto completo do versículo; use a referência somente se editorialmente necessário.

Dados do livro:
Título: {titulo}
Faixa: {faixa_label}
Sinopse poética (interna, não copiar literalmente): {sinopse_poetica}
Lição: {aprendizado_cristao}
Referência bíblica: {versiculo_referencia}
"""


def sinopse_node(state: LivroState, chamar_llm) -> LivroState:
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    perfil = perfil_etario(faixa)
    state["faixa_etaria"] = faixa
    state["age_profile_id"] = faixa

    prompt = PROMPT_SINOPSE.format(
        faixa_label=perfil["short_label"],
        publico=perfil["publico"],
        titulo=state.get("titulo", ""),
        sinopse_poetica=state.get("sinopse_poetica", state.get("titulo", "")),
        aprendizado_cristao=state.get("aprendizado_cristao", ""),
        versiculo_referencia=state.get("versiculo_referencia", ""),
    )
    prompt += skill_contract("sales_synopsis")
    resposta = chamar_llm(sistema=prompt, instrucao="Gere as duas versões em JSON.")
    if not isinstance(resposta, dict):
        resposta = {}
    state["sinopse_vendas_curta"] = resposta.get("sinopse_vendas_curta", "")
    state["sinopse_contracapa"] = resposta.get("sinopse_contracapa", "")
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('sales_synopsis',)

"""
Agente de Marketing de Lançamento.

Gera materiais de divulgação sem prometer vendas, ranking, resultado
pedagógico ou avaliações positivas. A comunicação respeita a faixa etária
do livro e diferencia o leitor da pessoa adulta que normalmente compra,
presenteia, ensina ou acompanha a leitura.
"""

from state import LivroState
from agent_skills import skill_contract
from age_profiles import normalizar_faixa_etaria, perfil_etario

PROMPT_MARKETING = """\
Você escreve o material de lançamento de um livro cristão da coleção
"{colecao}", no tom caloroso e pessoal definido para este projeto.
Crédito/autoria do livro: {author_credit}. Não presuma que o usuário logado
é a pessoa que assina a obra e não invente biografia do autor.

FAIXA ETÁRIA DO LIVRO: {faixa_label} — {publico}.
A comunicação deve apresentar o livro de forma adequada ao leitor dessa faixa
e à pessoa que pode comprá-lo/presenteá-lo, sem infantilizar leitores maiores.

Gere:
1. legenda_instagram: post de redes sociais com 3–5 hashtags realmente relacionadas ao conteúdo;
2. descricao_pinterest: descrição curta e pesquisável, mencionando somente temas presentes no livro;
3. email_lancamento: e-mail curto de anúncio convidando a conhecer a obra;
4. pedido_avaliacao: mensagem neutra para leitores elegíveis deixarem avaliação honesta, sem pedir avaliação positiva, sem recompensa e sem pressão.

Regras obrigatórias:
- não afirmar nem insinuar que o livro é best-seller, viral, premiado ou recomendado por especialistas sem evidência fornecida;
- não prometer vendas, ranking, transformação comportamental ou benefício pedagógico garantido;
- não inventar depoimentos, números, avaliações ou escassez;
- manter a mensagem cristã fiel à história, sem culpa religiosa ou medo;
- não citar texto bíblico completo gerado livremente; preserve somente a referência se ela for mencionada;
- diferenciar "para crianças/leitores" de "para pais/educadores" conforme a faixa, evitando chamar leitores 9–12 de "crianças pequenas".

Dados do livro:
Título: {titulo}
Faixa: {faixa_label}
Sinopse de vendas: {sinopse_vendas_curta}
Lição: {aprendizado_cristao}
Referência bíblica: {versiculo_referencia}

Responda em JSON com essas 4 chaves.
"""


def marketing_lancamento_node(state: LivroState, chamar_llm) -> LivroState:
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    perfil = perfil_etario(faixa)
    state["faixa_etaria"] = faixa
    state["age_profile_id"] = faixa

    prompt = PROMPT_MARKETING.format(
        colecao=state.get("colecao", ""),
        author_credit=__import__("author_profiles").author_display_from_state(state) or "não definida",
        faixa_label=perfil["short_label"],
        publico=perfil["publico"],
        titulo=state.get("titulo", ""),
        sinopse_vendas_curta=state.get("sinopse_vendas_curta", ""),
        aprendizado_cristao=state.get("aprendizado_cristao", ""),
        versiculo_referencia=state.get("versiculo_referencia", ""),
    )
    prompt += skill_contract("marketing_launch")
    resposta = chamar_llm(sistema=prompt, instrucao="Gere o material de lançamento em JSON.")
    state["material_lancamento"] = resposta if isinstance(resposta, dict) else {}
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('marketing_launch',)

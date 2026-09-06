"""
Editor Editorial do FaithBloom.

Permite revisar uma história cena a cena sem reescrever o livro inteiro.
Também sugere alternativas de versículo e lição de moral, sempre com
aprovação humana antes de substituir o conteúdo atual. Todas as sugestões
respeitam a faixa etária oficial do projeto.
"""

from copy import deepcopy
from agent_skills import skill_contract
from age_profiles import normalizar_faixa_etaria, perfil_etario, instrucao_faixa_etaria


def _como_lista(resposta, chave: str) -> list:
    """Aceita tanto lista JSON direta quanto objeto {chave: [...]} do LLM."""
    if isinstance(resposta, list):
        return resposta
    if isinstance(resposta, dict):
        valor = resposta.get(chave, [])
        return valor if isinstance(valor, list) else []
    return []


def _idade(state: dict) -> tuple[str, dict]:
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    return faixa, perfil_etario(faixa)


def editar_cena(cena: dict, instrucao: str, state: dict, chamar_llm) -> dict:
    """Reescreve SOMENTE uma cena e preserva o restante do livro."""
    faixa, perfil = _idade(state)
    sistema = f"""\
Você é o Editor Editorial do FaithBloom Book Studio.
Edite SOMENTE a cena informada. NÃO reescreva outras cenas e NÃO altere
versículo, título, lição final ou personagens do livro.

FAIXA ETÁRIA OBRIGATÓRIA:
{instrucao_faixa_etaria(faixa)}

Regras:
- preserve a mesma ação, intenção e continuidade salvo quando a autora pedir mudança explícita;
- ajuste vocabulário, ritmo e densidade para {perfil['short_label']};
- preserve musicalidade natural e onomatopeias apenas quando fizerem sentido para a idade e a ação;
- emoções devem ser compreensíveis para a faixa, com mais concretude nas menores e nuance controlada nas maiores;
- preserve continuidade de personagens, cenário e figurino;
- mantenha o princípio cristão natural, amoroso e coerente com a história;
- não use culpa religiosa, ameaça, medo excessivo ou doutrina complexa;
- se a instrução pedir menos diálogo, reduza falas sem perder emoção;
- se pedir mais emoção, aumente ação/expressão coerente, não abstrações vazias;
- teto heurístico de revisão: cerca de {perfil['max_words_sentence']} palavras por frase e {perfil['max_words_scene']} palavras por cena, sem usar o teto como meta.

Contexto do livro:
Título: {state.get('titulo', '')}
Faixa etária: {perfil['short_label']}
Lição: {state.get('aprendizado_cristao', '')}
Versículo: {state.get('versiculo_referencia', '')}

Cena atual:
{cena}

Pedido da autora:
{instrucao}
"""
    sistema += skill_contract("story_editor")
    resposta = chamar_llm(
        sistema=sistema,
        instrucao=(
            "Responda em JSON com as chaves texto, emocao, emocao_secundaria, "
            "intensidade_emocional, transicao_emocional, figurino, contexto_visual e expressao. "
            "Preserve numero e personagem_principal."
        ),
    )
    if not isinstance(resposta, dict):
        return deepcopy(cena)

    nova = deepcopy(cena)
    for campo in (
        "texto", "emocao", "emocao_secundaria", "intensidade_emocional",
        "transicao_emocional", "figurino", "contexto_visual", "expressao",
    ):
        if resposta.get(campo) not in (None, ""):
            nova[campo] = resposta[campo]
    return nova


def sugerir_versiculos(state: dict, chamar_llm, quantidade: int = 3) -> list[dict]:
    faixa, perfil = _idade(state)
    sistema = f"""\
Você é o Curador Bíblico do FaithBloom Book Studio.
Sugira {quantidade} referências bíblicas que combinem naturalmente com esta história.
As opções devem fazer sentido para a maturidade de {perfil['short_label']} e para a lição vivida no enredo.
NÃO invente referências. Não escreva sermão. Dê alternativas para a autora escolher.
IMPORTANTE: todas as referências são CANDIDATAS, não validadas. Não forneça nem traduza o texto do versículo.

{instrucao_faixa_etaria(faixa)}

Título: {state.get('titulo', '')}
Tema/emoção: {state.get('emocao_central', '')}
Aprendizado cristão: {state.get('aprendizado_cristao', '')}
Versículo atual: {state.get('versiculo_referencia', '')}
Resumo/cenas: {state.get('cenas_texto', [])}
"""
    sistema += skill_contract("story_editor")
    resposta = chamar_llm(
        sistema=sistema,
        instrucao=(
            "Responda em JSON no formato {\"opcoes\":[{\"referencia\":\"...\","
            "\"motivo\":\"explicação curta\"}]}."
        ),
    )
    return _como_lista(resposta, "opcoes")


def sugerir_licoes(state: dict, chamar_llm, quantidade: int = 3) -> list[dict]:
    faixa, perfil = _idade(state)
    sistema = f"""\
Você é o Editor de Valores Cristãos do FaithBloom Book Studio.
Sugira {quantidade} alternativas de lição de moral adequadas a {perfil['short_label']}.
A mensagem deve ser amorosa, clara e coerente com a história.
Para faixas menores, seja mais curta e concreta. Para 9–12, permita uma reflexão um pouco mais nuançada sem virar sermão ou linguagem adulta.
Não mude o enredo. Não use culpa religiosa, ameaça ou medo como ferramenta de ensino.

{instrucao_faixa_etaria(faixa)}

Título: {state.get('titulo', '')}
Aprendizado atual: {state.get('aprendizado_cristao', '')}
Lição final atual: {state.get('licao_final', '')}
Cenas: {state.get('cenas_texto', [])}
"""
    sistema += skill_contract("story_editor")
    resposta = chamar_llm(
        sistema=sistema,
        instrucao=(
            "Responda em JSON no formato {\"opcoes\":[{\"licao\":\"...\","
            "\"motivo\":\"explicação curta\"}]}."
        ),
    )
    return _como_lista(resposta, "opcoes")


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('story_editor',)

"""
Agente Curador de Tema.

Roda ANTES do Roteirista. Permite que a autora forneça só o tema (ex:
"medo do escuro") ou um resumo livre (2-3 frases) da ideia da história,
e o agente deduz:

    1. A emoção central (dentro do dicionário fixo de emotion_colors)
    2. Um versículo bíblico que combine com o tema
    3. A lição cristã (aprendizado_cristao) adequada à faixa etária
    4. Um título coerente com a voz e maturidade do público

Se a autora já informou algum desses campos manualmente, o agente NÃO
sobrescreve - só preenche o que estiver faltando.
"""

from state import LivroState
from emotion_colors import EMOCOES
from agent_skills import skill_contract
from biblical_reference_validator import create_reference_candidate
from age_profiles import normalizar_faixa_etaria, instrucao_faixa_etaria, perfil_etario

PROMPT_CURADOR = """\
Você é o Curador de Tema do FaithBloom Book Studio. A autora forneceu um
tema ou resumo livre da ideia de uma história infantil cristã.

FAIXA ETÁRIA OBRIGATÓRIA:
{instrucao_idade}

Sua tarefa:
1. Identifique a emoção central da história, escolhendo APENAS entre:
   {emocoes_validas}
2. Sugira uma referência bíblica (livro, capítulo e versículo - ex:
   "Filipenses 4:6") que se conecte de forma natural e não-forçada ao
   tema e à emoção identificados.
3. Escreva a lição cristã em uma frase adequada à maturidade da faixa.
   A mensagem deve ser amorosa, sem medo, culpa religiosa ou doutrina
   complexa como recurso de ensino.
4. Sugira um título curto e memorável. Para faixas menores, títulos como
   "Quando [personagem] aprendeu..." são bem-vindos; para 9–12, não force
   esse molde se um título mais natural e menos infantil funcionar melhor.
5. Preserve a premissa da autora. Não acrescente conflito pesado apenas
   para tornar a história mais dramática.

Entrada da autora (tema ou resumo livre):
{entrada_usuario}

Responda em JSON com as chaves: emocao_central, versiculo_referencia,
aprendizado_cristao, titulo_sugerido, justificativa (breve, explicando
por que essa referência combina com o tema - para a autora poder trocar
se preferir outra).
"""


def curador_tema_node(state: LivroState, chamar_llm) -> LivroState:
    entrada = state.get("_entrada_tema_livre", "")
    if not entrada:
        return state

    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    perfil = perfil_etario(faixa)
    state["faixa_etaria"] = faixa
    state["age_profile_id"] = faixa
    versiculo_preexistente = bool(str(state.get("versiculo_referencia") or "").strip())

    prompt = PROMPT_CURADOR.format(
        emocoes_validas=", ".join(EMOCOES.keys()),
        entrada_usuario=entrada,
        instrucao_idade=instrucao_faixa_etaria(faixa),
    )
    prompt += (
        f"\nA lição e o título devem soar naturais para {perfil['short_label']}; "
        "clareza e adequação etária têm prioridade sobre fórmulas fixas."
    )
    prompt += skill_contract("theme_curator")
    resposta = chamar_llm(sistema=prompt, instrucao="Gere a sugestão em JSON.")
    if not isinstance(resposta, dict):
        resposta = {}

    # Só preenche o que não foi informado manualmente - nunca sobrescreve valor real.
    if not state.get("emocao_central"):
        state["emocao_central"] = resposta.get("emocao_central", "")
    if not state.get("versiculo_referencia"):
        state["versiculo_referencia"] = resposta.get("versiculo_referencia", "")
    if not state.get("aprendizado_cristao"):
        state["aprendizado_cristao"] = resposta.get("aprendizado_cristao", "")
    if not state.get("titulo"):
        state["titulo"] = resposta.get("titulo_sugerido", "")

    state["_justificativa_curadoria"] = resposta.get("justificativa", "")
    suggested_ref = str(resposta.get("versiculo_referencia") or "").strip()
    adopted_ref = str(state.get("versiculo_referencia") or "").strip()

    # Referência sugerida por IA só vira CANDIDATA se foi realmente adotada.
    # Se a autora já tinha informado outra referência, não contaminamos a
    # validação existente com uma sugestão que não está no livro.
    if (not versiculo_preexistente) and suggested_ref and adopted_ref == suggested_ref:
        state["bible_reference_candidate"] = create_reference_candidate(
            suggested_ref, reason=resposta.get("justificativa", ""), suggested_by="theme_curator"
        )
        state.setdefault("bible_reference_validation", dict(state["bible_reference_candidate"]))
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('theme_curator',)

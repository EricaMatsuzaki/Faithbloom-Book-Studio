"""
Agente Curador de Tema.

Roda ANTES do Roteirista. Permite que a Erica forneça só o tema (ex:
"medo do escuro") ou um resumo livre (2-3 frases) da ideia da história,
e o agente deduz:

    1. A emoção central (dentro do dicionário fixo de emotion_colors)
    2. Um versículo bíblico que combine com o tema/emoção
    3. A lição cristã (aprendizado_cristao) que a história vai ensinar

Se a Erica já informou algum desses campos manualmente, o agente NÃO
sobrescreve - só preenche o que estiver faltando. Isso permite tanto o
fluxo "só me dê o tema" quanto o fluxo "quero controlar tudo".
"""

from state import LivroState
from emotion_colors import EMOCOES

PROMPT_CURADOR = """\
Você é o Curador de Tema da coleção "Pequenas Histórias, Grandes
Lições". A autora forneceu apenas um tema ou resumo livre da ideia de
uma história infantil cristã. Sua tarefa:

1. Identifique a emoção central da história, escolhendo APENAS entre:
   {emocoes_validas}
2. Sugira um versículo bíblico (livro, capítulo e versículo - ex:
   "Filipenses 4:6") que se conecte de forma natural e não-forçada ao
   tema e à emoção identificados.
3. Escreva a lição cristã em uma frase (ex: "confiar em Deus mesmo com
   medo", "esperar o tempo certo de Deus", "perdoar como fomos
   perdoados").
4. Sugira um título poético e curto pro livro, no estilo "Quando Mel
   Aprendeu a Esperar" (nome do personagem + verbo de aprendizado).

Entrada da autora (tema ou resumo livre):
{entrada_usuario}

Responda em JSON com as chaves: emocao_central, versiculo_referencia,
aprendizado_cristao, titulo_sugerido, justificativa (breve, explicando
por que esse versículo combina com o tema - para a autora poder trocar
se preferir outro).
"""


def curador_tema_node(state: LivroState, chamar_llm) -> LivroState:
    entrada = state.get("_entrada_tema_livre", "")
    if not entrada:
        # Nada a curar - a Erica já informou tudo manualmente.
        return state

    prompt = PROMPT_CURADOR.format(
        emocoes_validas=", ".join(EMOCOES.keys()),
        entrada_usuario=entrada,
    )
    resposta = chamar_llm(sistema=prompt, instrucao="Gere a sugestão em JSON.")

    # Só preenche o que a Erica não informou manualmente - nunca sobrescreve.
    state.setdefault("emocao_central", resposta.get("emocao_central", ""))
    state.setdefault("versiculo_referencia", resposta.get("versiculo_referencia", ""))
    state.setdefault("aprendizado_cristao", resposta.get("aprendizado_cristao", ""))
    state.setdefault("titulo", resposta.get("titulo_sugerido", ""))

    # Guardamos a justificativa para mostrar na tela de aprovação do
    # frontend - a Erica pode trocar o versículo antes de seguir.
    state["_justificativa_curadoria"] = resposta.get("justificativa", "")
    return state

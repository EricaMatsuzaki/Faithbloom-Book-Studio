"""
Agente Dedicatória Dinâmica.

Conecta a metáfora central da história (tema/lição) à lista fixa de
pessoas da família da Erica, seguindo o tom e a estrutura do exemplo de
referência ("Quando Mel Aprendeu a Esperar") como few-shot - nunca como
texto fixo copiado.

A lista de pessoas fica em config local (não versionar publicamente
com dados pessoais reais - ver README).
"""

from state import LivroState

PROMPT_DEDICATORIA = """\
Você escreve a Dedicatória de um livro da coleção "Pequenas Histórias,
Grandes Lições" de Erica Matsuzaki.

Regras:
- Use a metáfora central da história (emoção: {emocao_central},
  aprendizado: {aprendizado_cristao}) para conectar cada pessoa da
  lista abaixo ao tema do livro - a dedicatória deve parecer escrita
  especificamente para ESTA história, não um texto genérico.
- Siga o tom e a estrutura do exemplo de referência (fornecido como
  few-shot), mas NUNCA copie frases literalmente - crie uma dedicatória
  nova a cada livro.
- Nomes próprios de pessoas reais nunca são traduzidos ou adaptados em
  nenhum idioma.

Pessoas a incluir: {lista_pessoas}

Exemplo de referência (tom/estrutura, não copiar texto):
{exemplo_referencia}
"""

EXEMPLO_REFERENCIA = """\
A Deus, Nosso Criador, que planta os sonhos no nosso coração...
Aos que Plantaram a Semente em Mim: [família próxima]...
À Minha Fonte de Carinho e Legado: [família extensa]...
E para você, pequeno leitor, [mensagem final ligada ao tema]...
"""


def dedicatoria_node(state: LivroState, chamar_llm) -> LivroState:
    prompt = PROMPT_DEDICATORIA.format(
        emocao_central=state["emocao_central"],
        aprendizado_cristao=state["aprendizado_cristao"],
        lista_pessoas=state.get("lista_dedicatoria", []),
        exemplo_referencia=EXEMPLO_REFERENCIA,
    )
    resposta = chamar_llm(sistema=prompt, instrucao="Escreva a dedicatória.")
    state["dedicatoria_texto"] = resposta.get("texto", "")
    return state

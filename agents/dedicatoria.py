"""
Agente Dedicatória Dinâmica.

Conecta a metáfora central da história (tema/lição) à lista de pessoas
da autora, seguindo o tom e a estrutura de exemplos de referência como
few-shot - nunca como texto fixo copiado.

IMPORTANTE - PRIVACIDADE: a lista de pessoas (state["lista_dedicatoria"])
NUNCA deve ser hardcoded neste arquivo nem em nenhum arquivo versionado
no repositório público. Ela deve vir de uma fonte local não commitada
(ver config_local.py.example e README - variável de ambiente, arquivo
.env, ou input na tela do Streamlit). Este arquivo só contém a LÓGICA
de como usar essa lista, nunca os nomes reais.
"""

from state import LivroState

PROMPT_DEDICATORIA = """\
Você escreve a Dedicatória de um livro da coleção "{colecao}" de
Erica Matsuzaki.

Regras:
- Use a metáfora central da história (emoção: {emocao_central},
  aprendizado: {aprendizado_cristao}) para conectar cada pessoa da
  lista abaixo ao tema do livro - a dedicatória deve parecer escrita
  especificamente para ESTA história, não um texto genérico.
- Siga o tom e a estrutura dos exemplos de referência (fornecidos como
  few-shot), mas NUNCA copie frases literalmente - crie uma dedicatória
  nova a cada livro.
- Nomes próprios de pessoas reais nunca são traduzidos ou adaptados em
  nenhum idioma.
- Pessoas marcadas como "in memoriam" recebem uma menção com carinho,
  no tom de lembrança (ex: "em memória eterna de...", "em doce
  lembrança de..."), nunca tratadas como se estivessem presentes.

Pessoas a incluir (nome - relação - status):
{lista_pessoas_formatada}

Exemplos de referência (tom/estrutura - NÃO copiar texto literalmente):
{exemplos_referencia}
"""

# Exemplos de ESTILO apenas (não têm dados pessoais - são só a
# estrutura genérica que o prompt acima já usa como referência).
EXEMPLOS_REFERENCIA = """\
Exemplo 1 (estrutura curta):
A Deus, Nosso Criador, que planta os sonhos no nosso coração...
Aos que Plantaram a Semente em Mim: [família próxima]...
À Minha Fonte de Carinho e Legado: [família extensa]...
E para você, pequeno leitor, [mensagem final ligada ao tema]...

Exemplo 2 (estrutura completa, com blocos temáticos e emojis):
🌸 Dedicatória
✨ A Deus, [conexão entre a fé e o tema da história]...
✨ Aos que Plantaram a Semente em Mim: [pais/cônjuge/filhos, ligados
   à metáfora central]...
✨ À Minha Fonte de Carinho e Legado: [tios/avós, incluindo os que já
   faleceram, em tom de lembrança carinhosa]...
[irmãos, familiares e amigos, agradecimento breve]...
✨ E para você, pequeno leitor, [mensagem final ligada à lição
   específica desta história]...
"""


def _formatar_lista_pessoas(lista_dedicatoria: list[dict]) -> str:
    linhas = []
    for pessoa in lista_dedicatoria:
        status = " (in memoriam)" if pessoa.get("in_memoriam") else ""
        linhas.append(f"- {pessoa.get('pessoa', '')} - {pessoa.get('relacao', '')}{status}")
    return "\n".join(linhas) if linhas else "(nenhuma pessoa informada)"


def dedicatoria_node(state: LivroState, chamar_llm) -> LivroState:
    prompt = PROMPT_DEDICATORIA.format(
        colecao=state.get("colecao", ""),
        emocao_central=state["emocao_central"],
        aprendizado_cristao=state["aprendizado_cristao"],
        lista_pessoas_formatada=_formatar_lista_pessoas(state.get("lista_dedicatoria", [])),
        exemplos_referencia=EXEMPLOS_REFERENCIA,
    )
    resposta = chamar_llm(sistema=prompt, instrucao="Escreva a dedicatória.")
    state["dedicatoria_texto"] = resposta.get("texto", "")
    return state

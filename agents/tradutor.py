"""
Agente Tradutor/Localizador.

Checklist fixo (nunca pular nenhum item):
1. Cultural - adapta referências/objetos/comida que não fazem sentido
   localmente. Nomes próprios de pessoas reais NUNCA são traduzidos.
2. Idiomático - troca expressões sem tradução literal por equivalente
   que uma criança daquele país reconheceria.
3. Faixa etária no idioma alvo - vocabulário/complexidade ajustados
   para 3-10 anos NAQUELE idioma especificamente.
4. Versículo bíblico - busca a referência oficial já existente na
   versão consagrada do idioma alvo (ex: KJV/NIV em inglês, Reina-Valera
   em espanhol). NUNCA traduz o versículo literalmente.
5. Elegibilidade de formato - verifica se o idioma é elegível para
   paperback na KDP antes de traduzir (ver kdp_rules.py).
"""

from state import LivroState
from kdp_rules import idioma_elegivel_paperback

PROMPT_TRADUTOR = """\
Você é o Tradutor/Localizador da coleção. Traduza o conteúdo abaixo do
português para o idioma alvo: {idioma_alvo}.

Checklist obrigatório:
1. Cultural: adapte referências, comidas e objetos que não existem ou
   não fazem sentido na cultura local. NUNCA traduza nomes próprios de
   pessoas reais (aparecem na dedicatória).
2. Idiomático: troque expressões sem equivalente literal por uma
   expressão que uma criança local reconheceria.
3. Ajuste o vocabulário e a complexidade de frase para leitura de
   3-10 anos NO IDIOMA ALVO (não apenas espelhar a complexidade do
   português).
4. Para o versículo bíblico ({versiculo_referencia}), busque a
   referência oficial já existente na versão consagrada da Bíblia
   nesse idioma - NUNCA traduza o texto do versículo literalmente.
5. Não simplifique nem altere a lição/mensagem central - apenas a
   forma de contar pode se adaptar, o conteúdo da lição não.

Conteúdo a traduzir:
{conteudo}
"""


def tradutor_node(state: LivroState, chamar_llm) -> LivroState:
    traducoes: dict[str, dict] = {}
    for idioma in state.get("idiomas_alvo", []):
        if not idioma_elegivel_paperback(idioma):
            traducoes[idioma] = {
                "status": "eBook apenas - paperback não suportado pela KDP "
                "para este idioma no momento"
            }
            continue

        conteudo = {
            "cenas_texto": state["cenas_texto"],
            "dedicatoria": state["dedicatoria_texto"],
            "licao_final": state["licao_final"],
        }
        prompt = PROMPT_TRADUTOR.format(
            idioma_alvo=idioma,
            versiculo_referencia=state["versiculo_referencia"],
            conteudo=conteudo,
        )
        resposta = chamar_llm(sistema=prompt, instrucao="Traduza seguindo o checklist.")
        traducoes[idioma] = resposta

    state["traducoes"] = traducoes
    return state

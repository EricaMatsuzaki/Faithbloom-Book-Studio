"""
Agente Roteirista.

Escreve a história completa: sinopse poética, cenas (texto curto por
cena, com emoção e figurino marcados) e a lição final + versículo.

Cadência narrativa fixa: curiosidade -> desafio -> emoção -> aprendizado
-> fé -> gratidão -> lição final + versículo.
"""

from state import LivroState, CenaTexto
from agent_skills import skill_contract

PROMPT_BASE = """\
Você é o Roteirista de um projeto de livro infantil cristão, fiel ao
Prompt-Mestre editorial do projeto. Preserve a voz da coleção e não presuma
que o usuário logado é a pessoa creditada como autora.
Autoria/crédito deste projeto: {author_credit}.

Estilo de escrita OBRIGATÓRIO (best-seller infantil cristão, 3-8 anos):
- Frases muito curtas e diretas (idealmente 5-15 palavras). Uma ideia
  por frase.
- Palavras simples, do vocabulário cotidiano de uma criança pequena.
- Emoções SEMPRE descritas de forma CONCRETA, nunca metafórica ou
  abstrata. Exemplos do padrão certo: "coração quentinho", "Mel ficou
  triste", "Mel sorriu", "ficaram muito felizes". Nunca use metáforas
  complexas ou linguagem adulta para descrever sentimento.
- Repetição suave e proposital: repita uma frase-chave, um som ou uma
  estrutura ao longo da história (crianças de 3-8 anos gostam, e isso
  ajuda a fixar e acalmar).
- Ação visual rápida: cada cena tem algo ACONTECENDO (um gesto, um
  movimento, uma reação), nunca só descrição parada - crianças pequenas
  entendem a história pelas imagens e ações, não por explicação.
- Sem simbolismo complexo, sem duplo sentido: o tema e a lição devem
  ficar transparentes e claros para uma criança pequena entender sem
  ajuda de um adulto.
- Escreva pensando em leitura EM VOZ ALTA: frases com ritmo natural e
  musical, fáceis de ler por pais, professores ou contadores de
  histórias, sem trava-línguas nem orações longas.

Cadência narrativa fixa: curiosidade -> desafio -> emoção ->
aprendizado -> fé -> gratidão.
- Cada cena tem UMA emoção central, escolhida entre: {emocoes_validas}.
- Cada cena registra o figurino do personagem principal nessa cena
  (roupa/acessório). Se a cena é continuação direta da anterior (mesmo
  dia, mesma situação), repita o mesmo figurino. Se a narrativa muda de
  contexto (novo dia, nova situação: dormir, chuva, festa...), marque a
  troca explicitamente - nunca troque roupa sem motivo narrativo.
- Personagens fixos disponíveis: {personagens}.
- Gere no mínimo {min_cenas} cenas (o suficiente para {paginas_minimas}
  páginas físicas, considerando texto e imagem em páginas separadas).
- Feche a história em 3 camadas: (1) diálogo de resolução, (2) cena de
  celebração, (3) página final só com Lição + Versículo bíblico
  ({versiculo_referencia}), marcada como FIM.

Dados da história:
Título: {titulo}
Emoção central: {emocao_central}
Aprendizado cristão: {aprendizado_cristao}
Versículo: {versiculo_referencia}
"""


def montar_prompt(state: LivroState) -> str:
    from emotion_colors import EMOCOES

    personagens_str = ", ".join(
        f"{p['nome']} ({p['papel']})" for p in state["personagens"].values()
    )
    min_cenas = max(12, state.get("paginas_minimas", 24) // 2)
    return PROMPT_BASE.format(
        emocoes_validas=", ".join(EMOCOES.keys()),
        personagens=personagens_str,
        min_cenas=min_cenas,
        paginas_minimas=state.get("paginas_minimas", 24),
        titulo=state["titulo"],
        emocao_central=state["emocao_central"],
        aprendizado_cristao=state["aprendizado_cristao"],
        versiculo_referencia=state["versiculo_referencia"],
        author_credit=__import__("author_profiles").author_display_from_state(state) or "não definida",
    ) + skill_contract("storyteller")


def roteirista_node(state: LivroState, chamar_llm) -> LivroState:
    """
    chamar_llm: função injetada que recebe um prompt de sistema + instrução
    e devolve texto (abstrai a chamada real à API - ver main.py).
    Espera-se que o LLM devolva um JSON estruturado; aqui simplificamos
    a validação para manter o esqueleto legível.
    """
    prompt = montar_prompt(state)
    resposta = chamar_llm(
        sistema=prompt,
        instrucao=(
            "Gere a sinopse poética, a lista de cenas (numero, texto, "
            "emocao, figurino, contexto_visual) e a licao_final em JSON."
        ),
    )
    # Em produção: json.loads(resposta) + validação com pydantic.
    # Aqui deixamos o retorno bruto para o próximo agente revisar.
    state["sinopse_poetica"] = resposta.get("sinopse_poetica", "")
    state["cenas_texto"] = resposta.get("cenas_texto", [])
    state["licao_final"] = resposta.get("licao_final", "")
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('storyteller',)

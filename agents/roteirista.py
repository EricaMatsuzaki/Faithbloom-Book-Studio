"""
Agente Roteirista.

Escreve a história completa: sinopse poética, cenas (com emoção, subemoção,
intensidade e figurino marcados) e a lição final + versículo.

A faixa etária oficial do livro vem do Age Profile Engine e altera linguagem,
ritmo, densidade, musicalidade, humor, tensão e profundidade reflexiva.
"""

from state import LivroState, CenaTexto
from agent_skills import skill_contract
from agents.estilos_narrativos import normalizar_estilo, instrucao_estilo, normalizar_licao_final
from age_profiles import normalizar_faixa_etaria, instrucao_faixa_etaria, perfil_etario
from originality_guard import creation_originality_contract

PROMPT_BASE = """\
Você é o Roteirista de um projeto de livro infantil cristão, fiel ao
Prompt-Mestre editorial do projeto. Preserve a voz da coleção e não presuma
que o usuário logado é a pessoa creditada como autora.
Autoria/crédito deste projeto: {author_credit}.

FAIXA ETÁRIA — REGRA OBRIGATÓRIA:
{instrucao_idade}

ESTILO NARRATIVO FORMAL ESCOLHIDO:
{estilo_narrativo}

Siga o estilo narrativo e a faixa etária simultaneamente, sem alterar os fatos
centrais, personagens, lição cristã ou referência bíblica do projeto.

REGRAS NARRATIVAS UNIVERSAIS FAITHBLOOM:
- Clareza acima de enfeite. O vocabulário, tamanho das frases e densidade de
  texto devem obedecer ao perfil etário escolhido.
- Emoções devem ser compreensíveis para a idade. Para os menores, descreva-as
  de forma concreta; para leitores maiores, permita mais nuance sem linguagem
  adulta desnecessária.
- Use musicalidade natural em todos os estilos. A intensidade de repetição,
  pausas e sons deve seguir o perfil etário.
- Onomatopeias são bem-vindas quando ligadas a ação real, humor, movimento ou
  surpresa; use a intensidade recomendada pelo perfil etário e nunca em excesso.
- Cada cena deve ter algo acontecendo: gesto, movimento, decisão, reação,
  descoberta ou consequência. Evite exposição parada.
- A jornada deve ter movimento, humor adequado à idade, tensão segura,
  descoberta, transformação emocional, descoberta espiritual e
  recompensa/celebração ao final.
- Nunca use medo excessivo, sofrimento pesado, culpa religiosa ou ameaça como
  recurso de ensino cristão.
- A mensagem cristã deve ser amorosa e adequada à idade; não use doutrina
  complexa nem sermão longo.
- Escreva pensando em leitura em voz alta quando isso combinar com a faixa,
  preservando ritmo natural e frases agradáveis de ouvir.

Cadência narrativa-base: curiosidade -> desejo -> desafio -> tentativas ->
humor/movimento -> tensão segura -> emoção -> descoberta -> fé ->
transformação -> recompensa emocional -> gratidão/celebração.
A cadência pode ganhar mais nuance e duração nas faixas maiores, sem perder
clareza nem a transformação central.

MAPA EMOCIONAL OBRIGATÓRIO POR CENA:
- Cada cena tem UMA emoção principal CANÔNICA, escolhida entre: {emocoes_validas}.
- Pode ter UMA subemoção complementar, escolhida quando fizer sentido entre:
  {subemocoes_validas}.
- Registre intensidade_emocional de 1 a 5.
- Registre transicao_emocional em linguagem curta quando a cena estiver mudando
  de estado emocional, por exemplo: "tristeza → começando a surgir esperança".
- Não escolha a cor diretamente. O Emotional & Color Director aplicará a tabela
  canônica de psicologia das cores do Prompt-Mestre e a taxonomia de Plutchik.
- Emoção, subemoção e intensidade devem ser coerentes com o que realmente
  acontece na cena; não use emoções aleatórias só para variar paleta.

CONTINUIDADE VISUAL:
- Cada cena registra o figurino do personagem principal nessa cena.
- Se a cena continua no mesmo dia/situação, mantenha o figurino.
- Se houver mudança de contexto, marque a troca explicitamente.
- Personagens fixos disponíveis: {personagens}.
- Briefing adicional de personagens da autora: {personagens_brief}.

ESTRUTURA DO LIVRO:
- Gere no mínimo {min_cenas} cenas para {paginas_minimas} páginas físicas,
  considerando a proposta ilustrada e a densidade indicada pelo perfil etário.
- Teto heurístico de revisão: cerca de {max_words_sentence} palavras por frase e
  {max_words_scene} palavras por cena. Não use o teto como meta de enchimento.
- Feche a história em 3 camadas: (1) resolução, (2) recompensa/celebração,
  (3) Lição de Moral + referência bíblica ({versiculo_referencia}), marcada como FIM.
- A Lição de Moral é obrigatória. Nunca devolva licao_final vazia.

Dados da história:
Título: {titulo}
Faixa etária: {faixa_etaria_label}
Emoção central: {emocao_central}
Aprendizado cristão: {aprendizado_cristao}
Versículo: {versiculo_referencia}
"""


def montar_prompt(state: LivroState) -> str:
    from emotion_colors import EMOCOES, EMOCOES_COMPLEMENTARES

    personagens = state.get("personagens") or {}
    personagens_str = ", ".join(
        f"{p.get('nome', nome)} ({p.get('papel', '')})"
        for nome, p in personagens.items()
        if isinstance(p, dict)
    ) or "ainda não formalizados"
    min_cenas = max(12, state.get("paginas_minimas", 24) // 2)
    estilo = normalizar_estilo(state.get("estilo_narrativo"))
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    perfil = perfil_etario(faixa)
    return PROMPT_BASE.format(
        emocoes_validas=", ".join(EMOCOES.keys()),
        subemocoes_validas=", ".join(EMOCOES_COMPLEMENTARES.keys()),
        personagens=personagens_str,
        personagens_brief=state.get("personagens_historia_brief", "") or "nenhum briefing adicional",
        min_cenas=min_cenas,
        paginas_minimas=state.get("paginas_minimas", 24),
        max_words_sentence=perfil["max_words_sentence"],
        max_words_scene=perfil["max_words_scene"],
        faixa_etaria_label=perfil["short_label"],
        instrucao_idade=instrucao_faixa_etaria(faixa),
        titulo=state.get("titulo", ""),
        emocao_central=state.get("emocao_central", ""),
        aprendizado_cristao=state.get("aprendizado_cristao", ""),
        versiculo_referencia=state.get("versiculo_referencia", ""),
        author_credit=__import__("author_profiles").author_display_from_state(state) or "não definida",
        estilo_narrativo=instrucao_estilo(estilo),
    ) + skill_contract("storyteller") + creation_originality_contract(dict(state))


def roteirista_node(state: LivroState, chamar_llm) -> LivroState:
    """Gera a história, exceto quando a autora já escolheu uma versão completa."""
    estilo = normalizar_estilo(state.get("estilo_narrativo"))
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    state["faixa_etaria"] = faixa
    state["age_profile_id"] = faixa
    state["estilo_narrativo"] = estilo
    state["estilo_narrativo_label"] = __import__(
        "agents.estilos_narrativos", fromlist=["ESTILOS_NARRATIVOS"]
    ).ESTILOS_NARRATIVOS[estilo]["label"]

    if (
        state.get("historia_escolhida_preservar")
        and state.get("cenas_texto")
        and str(state.get("licao_final") or "").strip()
    ):
        state["historia_escolhida_preservar"] = False
        state["revisao_aprovada"] = False
        return state

    prompt = montar_prompt(state)
    resposta = chamar_llm(
        sistema=prompt,
        instrucao=(
            "Gere a sinopse poética, a lista de cenas e a licao_final em JSON. "
            "Cada cena deve conter: numero, texto, emocao, emocao_secundaria, "
            "intensidade_emocional (1-5), transicao_emocional, figurino, "
            "contexto_visual, personagem_principal e expressao."
        ),
    )
    state["sinopse_poetica"] = resposta.get("sinopse_poetica", "")
    state["cenas_texto"] = resposta.get("cenas_texto", [])
    state["licao_final"] = normalizar_licao_final(resposta.get("licao_final", ""))
    state["historia_escolhida_preservar"] = False
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('storyteller',)
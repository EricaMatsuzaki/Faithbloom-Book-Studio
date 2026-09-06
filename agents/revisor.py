"""
Agente Revisor.

Checa continuidade, gramática, adequação etária, musicalidade, ação visual,
segurança emocional e a jornada narrativa FaithBloom. O perfil etário do livro
vem do Age Profile Engine; o Revisor nunca deve infantilizar uma faixa maior nem
aprovar densidade inadequada para uma faixa menor.
"""

from state import LivroState
from agent_skills import skill_contract
from age_profiles import normalizar_faixa_etaria, perfil_etario, instrucao_faixa_etaria

PROMPT_REVISOR = """\
Você é o Revisor/Editor independente do FaithBloom Book Studio.

FAIXA ETÁRIA OBRIGATÓRIA:
{instrucao_idade}

Analise a lista de cenas e verifique:
1. Continuidade de figurino: roupa/acessório só muda quando a narrativa indica mudança de contexto.
2. Continuidade de objetos/cenário: elementos importantes não desaparecem sem motivo.
3. Gramática, clareza e fluidez.
4. Adequação etária ao perfil escolhido: vocabulário, tamanho das frases, densidade por cena, humor, tensão e profundidade espiritual devem combinar com {faixa_label}.
5. Musicalidade natural e leitura em voz alta quando apropriado para a faixa; repetição e onomatopeias devem aparecer na intensidade adequada, nunca como obrigação artificial.
6. Ação narrativa em cada cena: gesto, movimento, decisão, reação, descoberta ou consequência; evite cenas puramente expositivas.
7. Jornada narrativa coerente: curiosidade/desejo -> desafio -> tentativas -> movimento/humor quando couber -> tensão segura -> emoção -> descoberta -> fé -> transformação -> recompensa emocional -> gratidão/celebração.
8. Segurança infantil/cristã: nada de medo excessivo, sofrimento pesado, culpa religiosa, ameaça espiritual ou sermão longo como recurso pedagógico.
9. Transformação emocional e descoberta espiritual devem ser VIVIDAS pelo personagem, não apenas explicadas por um adulto/mentor.
10. Lição final coerente com o enredo e adequada à idade.
11. Referência bíblica: preserve a referência informada; não invente, traduza ou complete o texto do versículo.
12. Mapa emocional narrativo: emoção, subemoção, intensidade e transição devem combinar com o que realmente acontece na cena quando esses campos estiverem presentes.

Limites heurísticos do perfil, usados como alerta editorial e não como meta de enchimento:
- até aproximadamente {max_words_sentence} palavras por frase;
- até aproximadamente {max_words_scene} palavras por cena.

Se tudo estiver consistente, responda JSON com status="APROVADO" e notas=[].
Se houver problema, responda status="REVISAR" e liste notas específicas por número de cena,
explicando o que ajustar SEM reescrever silenciosamente o livro inteiro.
"""


def montar_prompt_revisor(state: LivroState) -> str:
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    perfil = perfil_etario(faixa)
    return PROMPT_REVISOR.format(
        instrucao_idade=instrucao_faixa_etaria(faixa),
        faixa_label=perfil["short_label"],
        max_words_sentence=perfil["max_words_sentence"],
        max_words_scene=perfil["max_words_scene"],
    )


def revisor_node(state: LivroState, chamar_llm) -> LivroState:
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    state["faixa_etaria"] = faixa
    state["age_profile_id"] = faixa
    resposta = chamar_llm(
        sistema=montar_prompt_revisor(state) + skill_contract("story_reviewer"),
        instrucao=(
            f"Título: {state.get('titulo','')}\n"
            f"Lição cristã: {state.get('licao_final') or state.get('aprendizado_cristao','')}\n"
            f"Referência bíblica: {state.get('versiculo_referencia','')}\n"
            f"Cenas: {state.get('cenas_texto', [])}"
        ),
    )
    if not isinstance(resposta, dict):
        resposta = {"status": "REVISAR", "notas": ["Resposta do Revisor não veio em JSON estruturado; revisar manualmente."]}
    aprovado = resposta.get("status") == "APROVADO"
    state["revisao_aprovada"] = aprovado
    state["notas_revisor"] = resposta.get("notas", [])
    return state


def precisa_retrabalho(state: LivroState) -> str:
    """Função de roteamento condicional do LangGraph."""
    return "roteirista" if not state.get("revisao_aprovada") else "ilustrador"


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('story_reviewer',)

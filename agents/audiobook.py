"""
Agente Audiobook.

Pega o texto já aprovado pelo Revisor e gera uma versão com marcações
de pausa e entonação, pensada para leitura em voz alta / evangelização
infantil (pais, professores, contadores de história ou síntese de voz TTS).

A faixa etária oficial altera somente a DIREÇÃO DE PERFORMANCE: o texto
aprovado não é reescrito.
"""

from state import LivroState
from agent_skills import skill_contract
from age_profiles import normalizar_faixa_etaria, perfil_etario

PROMPT_AUDIOBOOK = """\
Você adapta o texto já aprovado da história para uma versão de AUDIOBOOK,
pensada para leitura em voz alta e também compatível com síntese de voz TTS.

FAIXA ETÁRIA OFICIAL: {faixa_label}.
Direção de performance por idade: {direcao_performance}

Regras:
- NÃO reescreva, resuma, expanda ou simplifique a história; use o texto aprovado e adicione apenas marcações de performance.
- Insira [pausa curta] entre frases quando a respiração/emoção pedir.
- Insira [pausa longa] em transições de cena ou depois de uma virada emocional importante.
- Use [voz suave], [voz animada] ou [voz sussurrada] conforme a emoção real da cena.
- Use [ênfase: palavra] somente em palavras-chave que realmente mereçam destaque.
- Preserve onomatopeias do texto e dê a elas interpretação natural, sem acrescentar novas por conta própria.
- Mantenha o ritmo compatível com a idade: não torne 9–12 excessivamente pausado/infantil e não acelere 3–5 a ponto de dificultar acompanhamento.
- BÍBLIA É CONTEÚDO PROTEGIDO: não traduza, complete, parafraseie nem invente texto de versículo. Se uma referência aparecer, preserve apenas a referência; texto bíblico completo é inserido por outra camada somente quando a autora aprovou uma versão específica.

Cenas da história (com a emoção de cada uma):
{cenas}

Lição final e referência bíblica:
{licao_final}
"""


def _direcao_performance(faixa: str) -> str:
    if faixa == "3-5":
        return "ritmo acolhedor e um pouco mais pausado, com tempo para processar ações, sons e mudanças emocionais; sem exagerar vozes caricatas"
    if faixa == "6-8":
        return "ritmo ágil e claro, com pausas expressivas em humor, surpresa, descoberta e emoção"
    if faixa == "9-12":
        return "ritmo mais contínuo e natural, menos pausas artificiais, interpretação emocional com nuance e sem infantilizar"
    return "ritmo de leitura em voz alta equilibrado, acolhedor e musical, compatível com a faixa ampla 3–8"


def audiobook_node(state: LivroState, chamar_llm) -> LivroState:
    faixa = normalizar_faixa_etaria(state.get("faixa_etaria"))
    perfil = perfil_etario(faixa)
    state["faixa_etaria"] = faixa
    state["age_profile_id"] = faixa

    prompt = PROMPT_AUDIOBOOK.format(
        faixa_label=perfil["short_label"],
        direcao_performance=_direcao_performance(faixa),
        cenas=state.get("cenas_texto", []),
        licao_final=(
            f"{state.get('licao_final','')} | referência: {state.get('versiculo_referencia','')}"
        ),
    )
    prompt += skill_contract("audiobook_director")
    resposta = chamar_llm(
        sistema=prompt,
        instrucao=(
            "Gere o roteiro de audiobook em JSON: lista de objetos com "
            "numero, texto_narrado (com as marcações) e nota_producao. "
            "Não altere as palavras do texto aprovado além das marcações."
        ),
    )
    if isinstance(resposta, list):
        roteiro = resposta
    elif isinstance(resposta, dict):
        roteiro = resposta.get("roteiro", [])
    else:
        roteiro = []
    state["roteiro_audiobook"] = roteiro
    return state


def narracao_node(state: LivroState, gerar_audio) -> LivroState:
    """Converte cada trecho aprovado do roteiro em áudio via TTS."""
    audios = []
    for trecho in state.get("roteiro_audiobook", []):
        caminho = gerar_audio(
            texto_com_marcacoes=trecho["texto_narrado"],
            nome_arquivo=f"cena_{trecho['numero']}",
        )
        audios.append({"numero": trecho["numero"], "caminho_arquivo": caminho})
    state["audio_gerado"] = audios
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('audiobook_director', 'narrator')

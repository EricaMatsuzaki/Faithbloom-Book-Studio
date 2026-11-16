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
from generation_autosave import persist_generation_snapshot
import hashlib
import re


def _texto_sem_marcacoes(texto: str) -> str:
    # Only production directions may differ from the approved manuscript.
    return " ".join(re.sub(r"\[[^\[\]]*\]", " ", texto).split())


def _validar_roteiro(roteiro: object, cenas: list[dict] | None = None) -> list[dict]:
    if not isinstance(roteiro, list) or not roteiro:
        raise ValueError("O roteiro de audiobook está vazio ou inválido. A versão anterior foi preservada.")
    numeros = []
    for trecho in roteiro:
        if (not isinstance(trecho, dict) or type(trecho.get("numero")) is not int
                or trecho["numero"] < 1 or not isinstance(trecho.get("texto_narrado"), str)
                or not _texto_sem_marcacoes(trecho["texto_narrado"])):
            raise ValueError("O roteiro de audiobook contém trecho incompleto. A versão anterior foi preservada.")
        numeros.append(trecho["numero"])
    if len(set(numeros)) != len(numeros):
        raise ValueError("O roteiro de audiobook repete números de cenas. A versão anterior foi preservada.")
    if cenas is not None:
        if (not isinstance(cenas, list) or not cenas
                or any(not isinstance(cena, dict) or type(cena.get("numero")) is not int
                       or not isinstance(cena.get("texto"), str) or not cena["texto"].strip()
                       for cena in cenas)):
            raise ValueError("Selecione um manuscrito com texto e cenas numeradas antes de dirigir o audiobook.")
        if numeros != [cena["numero"] for cena in cenas]:
            raise ValueError("O roteiro omitiu, acrescentou ou reordenou cenas. A versão anterior foi preservada.")
        if any(_texto_sem_marcacoes(trecho["texto_narrado"]) != _texto_sem_marcacoes(cena["texto"])
               for trecho, cena in zip(roteiro, cenas)):
            raise ValueError("O roteiro alterou palavras do texto aprovado. A versão anterior foi preservada.")
    return roteiro

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
    cenas = state.get("cenas_texto") or []
    # Validate before any provider call, using the original words as a script.
    _validar_roteiro([{"numero": c.get("numero"), "texto_narrado": c.get("texto")}
                      for c in cenas if isinstance(c, dict)], cenas)

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
    _validar_roteiro(roteiro, cenas)
    state["faixa_etaria"] = faixa
    state["age_profile_id"] = faixa
    state["roteiro_audiobook"] = roteiro
    return state


def narracao_node(state: LivroState, gerar_audio) -> LivroState:
    """Converte cada trecho aprovado do roteiro em áudio via TTS."""
    from agent_skills import require_role_ready
    require_role_ready("narrator")
    roteiro = _validar_roteiro(state.get("roteiro_audiobook"), state.get("cenas_texto") or None)
    audios = list(state.get("audio_gerado") or [])
    if any(not isinstance(item, dict) for item in audios):
        raise ValueError("O histórico de áudio está inválido; revise-o antes de gerar novamente.")
    por_numero = {item.get("numero"): item for item in audios}
    if len(por_numero) != len(audios):
        raise ValueError("O histórico de áudio repete cenas; revise-o antes de gerar novamente.")
    for trecho in roteiro:
        existente = por_numero.get(trecho["numero"])
        fingerprint = hashlib.sha256(trecho["texto_narrado"].encode("utf-8")).hexdigest()
        if existente and existente.get("caminho_arquivo") and existente.get("texto_fingerprint") != fingerprint:
            raise ValueError("Há áudio de outra versão ou sem rastreabilidade. Crie uma nova versão no Audiobook Studio; o áudio anterior foi preservado.")
    for trecho in roteiro:
        fingerprint = hashlib.sha256(trecho["texto_narrado"].encode("utf-8")).hexdigest()
        existente = por_numero.get(trecho["numero"])
        if existente and existente.get("caminho_arquivo"):
            continue
        caminho = gerar_audio(
            texto_com_marcacoes=trecho["texto_narrado"],
            nome_arquivo=f"cena_{trecho['numero']}_{fingerprint[:12]}",
        )
        if not isinstance(caminho, str) or not caminho.strip():
            raise ValueError("O narrador não retornou um arquivo de áudio utilizável. Os trechos concluídos foram preservados.")
        item = {"numero": trecho["numero"], "caminho_arquivo": caminho, "texto_fingerprint": fingerprint}
        if existente:
            audios[audios.index(existente)] = item
        else:
            audios.append(item)
        por_numero[trecho["numero"]] = item
        state["audio_gerado"] = list(audios)
        # A failed save stops the batch before another paid request.
        persist_generation_snapshot(state, reason=f"audio_narrated:{trecho['numero']}")
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('audiobook_director', 'narrator')

"""
Agente Audiobook.

Pega o texto já aprovado pelo Revisor e gera uma versão com marcações
de pausa e entonação, pensada para leitura em voz alta / evangelização
infantil (pais, professores, contadores de história, ou síntese de voz
via TTS).

Formato de marcação: usamos notação simples entre colchetes, fácil de
ler por um humano E fácil de mapear depois para SSML se você quiser
gerar áudio via TTS (Amazon Polly, ElevenLabs, etc. - todos aceitam
SSML, então essa camada intermediária facilita a portabilidade entre
provedores de voz).

Marcações usadas:
    [pausa curta]   -> ~0.5s, entre frases dentro da mesma ideia
    [pausa longa]    -> ~1.5s, entre cenas ou depois de um momento de virada
    [voz suave]       -> trecho de emoção calma/triste/reflexiva
    [voz animada]      -> trecho de alegria/celebração
    [voz sussurrada]    -> segredo, mistério, momento intimista
    [ênfase: palavra]    -> palavra que deve ser lida com destaque
"""

from state import LivroState

PROMPT_AUDIOBOOK = """\
Você adapta o texto já aprovado da história para uma versão de
AUDIOBOOK, pensada para leitura em voz alta por pais, professores ou
contadores de histórias (e também compatível com síntese de voz TTS).

Regras:
- NÃO reescreva a história - use o texto já aprovado, só adicione
  marcações de pausa e entonação.
- Insira [pausa curta] entre frases dentro da mesma ideia/sentimento.
- Insira [pausa longa] na transição entre cenas, e especialmente depois
  de um momento de virada emocional (isso dá tempo pra criança
  processar antes de seguir).
- Marque o tom de cada trecho com [voz suave], [voz animada] ou
  [voz sussurrada], conforme a emoção da cena.
- Use [ênfase: palavra] nas palavras-chave da lição (ex: a palavra que
  carrega o aprendizado cristão da história).
- Mantenha o ritmo natural de leitura em voz alta - nada de pausas
  exageradas que quebrem o fluxo da história.

Cenas da história (com a emoção de cada uma):
{cenas}

Lição final e versículo:
{licao_final}
"""


def audiobook_node(state: LivroState, chamar_llm) -> LivroState:
    prompt = PROMPT_AUDIOBOOK.format(
        cenas=state["cenas_texto"],
        licao_final=state["licao_final"],
    )
    resposta = chamar_llm(
        sistema=prompt,
        instrucao=(
            "Gere o roteiro de audiobook em JSON: lista de objetos com "
            "numero, texto_narrado (com as marcações) e nota_producao "
            "(dica extra pro narrador, se precisar)."
        ),
    )
    state["roteiro_audiobook"] = resposta.get("roteiro", [])
    return state


def narracao_node(state: LivroState, gerar_audio) -> LivroState:
    """
    Roda depois de audiobook_node. Converte cada trecho do roteiro (já
    com as marcações de pausa/entonação) em um arquivo MP3 real via TTS.
    Separado do audiobook_node porque um usa LLM de texto e o outro usa
    o modelo de voz - mantém os dois desacoplados.
    """
    audios = []
    for trecho in state.get("roteiro_audiobook", []):
        caminho = gerar_audio(
            texto_com_marcacoes=trecho["texto_narrado"],
            nome_arquivo=f"cena_{trecho['numero']}",
        )
        audios.append({"numero": trecho["numero"], "caminho_arquivo": caminho})
    state["audio_gerado"] = audios
    return state

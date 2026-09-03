"""
Agente Ilustrador.

Este é o agente que resolve o problema que a Erica teve na prática:
pedir várias vezes até a imagem ficar "parecida". A regra de ouro:

    NUNCA gerar uma cena só a partir de texto.
    SEMPRE incluir a imagem de referência do personagem (DNA fixo)
    + a descrição da cena específica (figurino variável + paleta de
    emoção + lado do spread).

Fluxo:
1. gerar_referencia_personagem() - roda UMA vez por personagem, gera a
   "character sheet" e pede aprovação humana antes de seguir.
2. gerar_cena() - roda para cada cena, sempre injetando a referência
   aprovada como imagem-base (image-to-image / character reference),
   nunca gerando do zero.

Estilo visual fixo (sem citar nenhum estúdio, só descrição técnica):
    - Ilustração digital 2D, traços arredondados, texturas macias
    - Proporções: cabeça grande, olhos grandes e expressivos, corpo
      pequeno e rechonchudo (isso é o que dá o efeito "fofo" -
      é proporção, não é estilo de um estúdio específico)
    - Sombras suaves, sem contornos duros, atmosfera de conto de fadas
    - Luz dourada, acolhedora
"""

from state import LivroState, PersonagemDNA, CenaImagem
from emotion_colors import paleta_para_prompt
from emotional_color_director import direcao_emocional, prompt_direcao_visual
from agent_skills import skill_contract

ESTILO_VISUAL_FIXO = (
    "Ilustração digital 2D, traços arredondados, texturas macias. "
    "Proporções fofas: cabeça grande, olhos grandes e expressivos, "
    "corpo pequeno e rechonchudo. Sombras suaves, sem contornos duros, "
    "atmosfera de conto de fadas. Luz dourada e acolhedora. "
    "Personagens e cenários 100% originais - não referenciar nenhum "
    "estúdio de animação específico."
)


def prompt_referencia_personagem(nome: str, descricao_fixa: str, papel: str) -> str:
    return (
        f"Character sheet de referência para '{nome}' ({papel}). "
        f"{ESTILO_VISUAL_FIXO}\n"
        f"Descrição fixa e imutável do personagem: {descricao_fixa}\n"
        "Gerar em 3-4 poses/ângulos diferentes (frente, perfil, 3/4, "
        "expressão feliz) na mesma folha, para servir de referência "
        "visual em todas as cenas seguintes."
    ) + skill_contract("illustrator", compact=True)


def gerar_referencia_personagem(
    personagem: PersonagemDNA, gerar_imagem
) -> PersonagemDNA:
    if personagem.get("origem_referencia") == "enviada_pela_autora" and personagem.get(
        "imagem_referencia"
    ):
        # A autora já enviou a imagem de referência - não gera nada,
        # só usa a imagem enviada como base pra todas as cenas seguintes.
        return personagem

    prompt = prompt_referencia_personagem(
        personagem["nome"], personagem["descricao_fixa"], personagem["papel"]
    )
    caminho = gerar_imagem(prompt=prompt, imagem_base=None)
    personagem["imagem_referencia"] = caminho
    personagem["origem_referencia"] = "gerada_pelo_agente"
    return personagem


def prompt_cena(
    cena: dict, personagens: dict[str, PersonagemDNA], lado_spread: str
) -> str:
    protagonista = personagens.get(cena.get("personagem_principal", ""), None)
    dna = protagonista["descricao_fixa"] if protagonista else ""
    return (
        f"{ESTILO_VISUAL_FIXO}\n"
        f"DNA fixo do personagem (nunca alterar): {dna}\n"
        f"Figurino desta cena (pode variar conforme a narrativa): "
        f"{cena.get('figurino', 'padrão')}\n"
        f"Cena: {cena.get('texto', '')}\n"
        f"Contexto visual: {cena.get('contexto_visual', '')}\n"
        f"{paleta_para_prompt(cena.get('emocao', 'esperanca'))}\n"
        f"{prompt_direcao_visual({'direcao': direcao_emocional(cena.get('emocao', 'esperanca'), cena.get('paleta_preset', 'Erica Matsuzaki · Pastel Faith'), cena.get('intensidade_emocional', 3)), 'expressao': cena.get('expressao', cena.get('emocao','')), 'instrucao_autora': cena.get('instrucao_emocional','')})}\n"
        "REGRA DE CONSISTÊNCIA: emoção muda expressão, pose, luz e atmosfera; não muda a identidade, cores canônicas ou proporções fundamentais do personagem.\n"
        f"Layout: página {lado_spread} do spread, sem texto embutido na "
        "imagem (texto vai em página separada) - deixar composição "
        "plena, respeitando margem de segurança para a dobra central."
    ) + skill_contract("illustrator", compact=True)


def ilustrador_node(state: LivroState, gerar_imagem) -> LivroState:
    # Passo 1: gerar/confirmar referência de cada personagem, uma vez só
    for nome, personagem in state["personagens"].items():
        if not personagem.get("imagem_referencia"):
            state["personagens"][nome] = gerar_referencia_personagem(
                personagem, gerar_imagem
            )
            # Em produção: pausar aqui e pedir aprovação humana da
            # referência antes de seguir para as cenas.

    # Passo 2: gerar cada cena usando a referência aprovada como imagem-base
    # - EXCETO cenas cuja imagem já foi enviada pela autora (ver
    # state["imagens_cenas_enviadas"]) - essas são usadas direto, sem
    # gastar créditos gerando de novo.
    imagens_enviadas = state.get("imagens_cenas_enviadas", {})
    # Se o estado veio de um arquivo JSON salvo, as chaves viram string -
    # normaliza pra sempre comparar como string.
    imagens_enviadas = {str(k): v for k, v in imagens_enviadas.items()}
    cenas_imagem: list[CenaImagem] = []
    for i, cena in enumerate(state["cenas_texto"]):
        numero = cena["numero"]
        if str(numero) in imagens_enviadas:
            cenas_imagem.append(
                CenaImagem(
                    numero=numero,
                    prompt_final="(imagem enviada pela autora - não gerada por IA)",
                    caminho_arquivo=imagens_enviadas[str(numero)],
                    aprovado=True,
                    origem="enviada_pela_autora",
                )
            )
            continue

        lado = "esquerda" if i % 2 == 0 else "direita"  # alterna por spread
        protagonista = state["personagens"].get(
            cena.get("personagem_principal", "")
        )
        imagem_base = protagonista["imagem_referencia"] if protagonista else None
        prompt = prompt_cena(cena, state["personagens"], lado)
        caminho = gerar_imagem(prompt=prompt, imagem_base=imagem_base)
        cenas_imagem.append(
            CenaImagem(
                numero=numero,
                prompt_final=prompt,
                caminho_arquivo=caminho,
                aprovado=False,
                origem="gerada_pelo_agente",
            )
        )
    state["cenas_imagem"] = cenas_imagem
    return state


# ---------------------------------------------------------------------------
# FaithBloom 2.0 - Fase 4: ilustração cena por cena, com histórico preservado

def _cena_por_numero(state: dict, numero: int) -> dict:
    for cena in state.get("cenas_texto", []):
        if int(cena.get("numero", -1)) == int(numero):
            return cena
    raise ValueError(f"Cena {numero} não encontrada.")


def obter_imagem_cena(state: dict, numero: int) -> dict | None:
    for item in state.get("cenas_imagem", []):
        if int(item.get("numero", -1)) == int(numero):
            return item
    return None


def _registrar_historico_imagem(state: dict, numero: int, item: dict | None) -> None:
    if not item or not item.get("caminho_arquivo"):
        return
    hist = state.setdefault("historico_imagens_cenas", {})
    chave = str(numero)
    hist.setdefault(chave, [])
    if not hist[chave] or hist[chave][-1].get("caminho_arquivo") != item.get("caminho_arquivo"):
        hist[chave].append(dict(item))


def definir_imagem_cena(state: dict, numero: int, caminho: str, prompt: str, origem: str, aprovado: bool = False) -> dict:
    """Troca a imagem ATIVA sem apagar a anterior: a versão atual vai para o histórico."""
    atual = obter_imagem_cena(state, numero)
    _registrar_historico_imagem(state, numero, atual)
    novo = CenaImagem(
        numero=int(numero),
        prompt_final=prompt,
        caminho_arquivo=caminho,
        aprovado=bool(aprovado),
        origem=origem,
    )
    itens = [dict(i) for i in state.get("cenas_imagem", []) if int(i.get("numero", -1)) != int(numero)]
    itens.append(novo)
    itens.sort(key=lambda i: int(i.get("numero", 0)))
    state["cenas_imagem"] = itens
    aprovadas = {int(n) for n in state.get("cenas_imagem_aprovadas", [])}
    if aprovado:
        aprovadas.add(int(numero))
    else:
        aprovadas.discard(int(numero))
    state["cenas_imagem_aprovadas"] = sorted(aprovadas)
    return state


def _referencia_para_cena(state: dict, cena: dict) -> str | None:
    nome = cena.get("personagem_principal", "")
    personagem = state.get("personagens", {}).get(nome)
    if personagem and personagem.get("imagem_referencia"):
        return personagem["imagem_referencia"]
    for p in state.get("personagens", {}).values():
        if p.get("papel") == "protagonista" and p.get("imagem_referencia"):
            return p["imagem_referencia"]
    for p in state.get("personagens", {}).values():
        if p.get("imagem_referencia"):
            return p["imagem_referencia"]
    return None


def gerar_cena_unica(state: dict, numero: int, gerar_imagem, instrucao_extra: str = "") -> dict:
    """Gera/regera somente UMA cena e preserva a versão anterior."""
    cena = _cena_por_numero(state, numero)
    idx = next((i for i, c in enumerate(state.get("cenas_texto", [])) if int(c.get("numero", -1)) == int(numero)), 0)
    lado = "esquerda" if idx % 2 == 0 else "direita"
    prompt = prompt_cena(cena, state.get("personagens", {}), lado)
    if instrucao_extra.strip():
        prompt += (
            "\nINSTRUÇÃO ESPECÍFICA DA AUTORA PARA ESTA CENA: " + instrucao_extra.strip()
            + "\nAltere somente o que foi pedido. Preserve personagens, identidade visual e elementos já aprovados."
        )
    base = _referencia_para_cena(state, cena)
    caminho = gerar_imagem(prompt=prompt, imagem_base=base)
    return definir_imagem_cena(state, numero, caminho, prompt, "gerada_pelo_agente", aprovado=False)


def criar_variacao_cena(state: dict, numero: int, gerar_imagem, instrucao: str = "") -> dict:
    """Cria uma variação a partir da imagem atual, mantendo a atual no histórico."""
    atual = obter_imagem_cena(state, numero)
    if not atual or not atual.get("caminho_arquivo"):
        return gerar_cena_unica(state, numero, gerar_imagem, instrucao)
    cena = _cena_por_numero(state, numero)
    pedido = instrucao.strip() or "Crie uma variação sutil desta cena mantendo personagens, rosto, proporções, roupas e composição principal reconhecíveis."
    prompt = (
        f"{ESTILO_VISUAL_FIXO}\n"
        f"Cena original: {cena.get('texto', '')}\n"
        f"Contexto: {cena.get('contexto_visual', '')}\n"
        "Use a imagem-base como referência visual principal. NÃO descarte a identidade visual já aprovada.\n"
        f"Pedido da autora: {pedido}\n"
        "Gerar uma NOVA versão; não colocar texto na imagem."
    )
    caminho = gerar_imagem(prompt=prompt, imagem_base=atual.get("caminho_arquivo"))
    return definir_imagem_cena(state, numero, caminho, prompt, "variacao_ia", aprovado=False)


def aprovar_imagem_cena(state: dict, numero: int, aprovada: bool = True) -> dict:
    item = obter_imagem_cena(state, numero)
    if item is not None:
        item["aprovado"] = bool(aprovada)
    aprovadas = {int(n) for n in state.get("cenas_imagem_aprovadas", [])}
    if aprovada:
        aprovadas.add(int(numero))
    else:
        aprovadas.discard(int(numero))
    state["cenas_imagem_aprovadas"] = sorted(aprovadas)
    return state


def restaurar_ultima_imagem_cena(state: dict, numero: int) -> dict:
    hist = state.setdefault("historico_imagens_cenas", {})
    chave = str(numero)
    anteriores = hist.get(chave, [])
    if not anteriores:
        return state
    anterior = anteriores.pop()
    itens = [dict(i) for i in state.get("cenas_imagem", []) if int(i.get("numero", -1)) != int(numero)]
    itens.append(dict(anterior))
    itens.sort(key=lambda i: int(i.get("numero", 0)))
    state["cenas_imagem"] = itens
    aprovadas = {int(n) for n in state.get("cenas_imagem_aprovadas", [])}
    if anterior.get("aprovado"):
        aprovadas.add(int(numero))
    else:
        aprovadas.discard(int(numero))
    state["cenas_imagem_aprovadas"] = sorted(aprovadas)
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('illustrator',)

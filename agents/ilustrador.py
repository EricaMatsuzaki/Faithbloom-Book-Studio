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
    )


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
        f"Layout: página {lado_spread} do spread, sem texto embutido na "
        "imagem (texto vai em página separada) - deixar composição "
        "plena, respeitando margem de segurança para a dobra central."
    )


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

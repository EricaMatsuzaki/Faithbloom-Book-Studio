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


def prompt_capa(titulo: str, colecao: str, personagens: dict, autora: str = "Erica Matsuzaki") -> str:
    """
    Elemento fixo de marca da capa: uma barra branca/clara no topo com
    o nome da coleção em letras maiúsculas (ex: "COLEÇÃO PEQUENAS
    HISTÓRIAS, GRANDES LIÇÕES"), o título grande abaixo, os personagens
    principais em destaque no centro/frente da cena, e o nome da autora
    na parte inferior da imagem.
    """
    protagonistas = ", ".join(
        f"{p['nome']} ({p['descricao_fixa']})" for p in personagens.values()
    )
    return (
        f"{ESTILO_VISUAL_FIXO}\n"
        "Capa de livro infantil. Elementos de marca fixos (sempre "
        "presentes, mesma posição em toda capa da coleção):\n"
        f"1. Uma barra branca/clara fina no topo da imagem, com uma "
        f"borda decorativa simples, contendo o texto em maiúsculas: "
        f"\"COLEÇÃO {colecao.upper()}\".\n"
        f"2. Título do livro em destaque, tipografia grande e legível, "
        f"logo abaixo da barra: \"{titulo}\".\n"
        f"3. Nome da autora \"{autora}\" em itálico, na parte inferior "
        "da imagem.\n"
        f"Personagens principais em destaque, centralizados/em primeiro "
        f"plano, cena de fundo que remeta ao tema da história: "
        f"{protagonistas}."
    )


def gerar_capa(state: dict, gerar_imagem) -> str:
    """Gera a imagem de capa usando as referências já aprovadas dos personagens."""
    prompt = prompt_capa(
        titulo=state.get("titulo", ""),
        colecao=state.get("colecao", ""),
        personagens=state.get("personagens", {}),
    )
    # Usa a referência do protagonista como imagem-base, se existir,
    # para manter a mesma consistência visual da capa com o miolo.
    protagonista = next(
        (p for p in state.get("personagens", {}).values() if p.get("papel") == "protagonista"),
        None,
    )
    imagem_base = protagonista["imagem_referencia"] if protagonista else None
    return gerar_imagem(prompt=prompt, imagem_base=imagem_base)


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
    cenas_imagem: list[CenaImagem] = []
    for i, cena in enumerate(state["cenas_texto"]):
        lado = "esquerda" if i % 2 == 0 else "direita"  # alterna por spread
        protagonista = state["personagens"].get(
            cena.get("personagem_principal", "")
        )
        imagem_base = protagonista["imagem_referencia"] if protagonista else None
        prompt = prompt_cena(cena, state["personagens"], lado)
        caminho = gerar_imagem(prompt=prompt, imagem_base=imagem_base)
        cenas_imagem.append(
            CenaImagem(
                numero=cena["numero"],
                prompt_final=prompt,
                caminho_arquivo=caminho,
                aprovado=False,
            )
        )
    state["cenas_imagem"] = cenas_imagem

    # Passo 3: gerar a capa, usando o protagonista já aprovado como referência
    state["imagem_capa"] = gerar_capa(state, gerar_imagem)
    return state

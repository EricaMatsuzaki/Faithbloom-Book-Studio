"""
Agente Atividades para Colorir.

Roda depois do Ilustrador. Escolhe 3 cenas marcantes da história (por
padrão: uma do início, uma do ponto de virada emocional, uma do final -
isso cobre o arco completo da lição) e gera uma versão LINE-ART de cada
uma, do zero (não é a imagem colorida convertida - ver README sobre por
que essa opção dá resultado melhor pra colorir de verdade).

Usa a MESMA imagem de referência do personagem que o Ilustrador já usa,
então a pose/proporção do line-art continua reconhecível como o mesmo
personagem do miolo colorido.
"""

from state import LivroState, CenaImagem
from agent_skills import skill_contract

ESTILO_LINE_ART = (
    "Ilustração em LINE ART: apenas contorno em preto e branco, SEM "
    "preenchimento de cor, SEM sombreado, estilo livro de colorir "
    "infantil. Traços grossos, simples e bem fechados (sem lacunas), "
    "fáceis de colorir com lápis de cor ou giz de cera por uma criança "
    "de 3 a 10 anos. Manter a mesma pose, proporção e expressão do "
    "personagem de referência - só remover a cor e o sombreamento."
)


def escolher_cenas_chave(cenas_texto: list[dict]) -> list[dict]:
    """Uma do início, uma do ponto de virada, uma do final - cobre o arco completo."""
    if len(cenas_texto) < 3:
        return cenas_texto
    inicio = cenas_texto[0]
    meio = cenas_texto[len(cenas_texto) // 2]
    fim = cenas_texto[-1]
    return [inicio, meio, fim]


def prompt_colorir(cena: dict, dna_personagem: str) -> str:
    return (
        f"{ESTILO_LINE_ART}\n"
        f"DNA do personagem (manter pose/proporção reconhecível): {dna_personagem}\n"
        f"Cena original: {cena.get('texto', '')}\n"
        f"Contexto visual: {cena.get('contexto_visual', '')}"
    ) + skill_contract("coloring_activity_creator", compact=True)


def atividades_colorir_node(state: LivroState, gerar_imagem) -> LivroState:
    cenas_escolhidas = escolher_cenas_chave(state["cenas_texto"])
    paginas_colorir: list[CenaImagem] = []

    for cena in cenas_escolhidas:
        protagonista = state["personagens"].get(
            cena.get("personagem_principal", "")
        )
        dna = protagonista["descricao_fixa"] if protagonista else ""
        imagem_base = protagonista["imagem_referencia"] if protagonista else None

        prompt = prompt_colorir(cena, dna)
        # Opção 1: gera do zero como line-art (não converte a colorida),
        # usando a referência do personagem pra manter reconhecível.
        caminho = gerar_imagem(prompt=prompt, imagem_base=imagem_base)

        paginas_colorir.append(
            CenaImagem(
                numero=cena["numero"],
                prompt_final=prompt,
                caminho_arquivo=caminho,
                aprovado=False,
            )
        )

    state["paginas_colorir"] = paginas_colorir
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('coloring_activity_creator',)

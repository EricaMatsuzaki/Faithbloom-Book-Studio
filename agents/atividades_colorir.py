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
from agents.ilustrador import _personagem_para_cena
from generation_autosave import persist_generation_snapshot

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
    paginas_colorir: list[CenaImagem] = list(state.get("paginas_colorir") or [])
    if any(not isinstance(pagina, dict) for pagina in paginas_colorir):
        raise ValueError("O histórico de atividades de colorir está inválido; revise-o antes de gerar.")
    existentes = {str(pagina.get("numero")): pagina for pagina in paginas_colorir}
    if len(existentes) != len(paginas_colorir):
        raise ValueError("O histórico de atividades de colorir repete cenas; revise-o antes de gerar.")
    pendentes = []
    for cena in cenas_escolhidas:
        if existentes.get(str(cena["numero"]), {}).get("caminho_arquivo"):
            continue
        protagonista = _personagem_para_cena(cena, state.get("personagens") or {})
        if not protagonista or not protagonista.get("descricao_fixa") or not protagonista.get("imagem_referencia"):
            raise ValueError(f"Cena {cena['numero']}: selecione o DNA e a referência do personagem antes de gerar a atividade.")
        pendentes.append((cena, protagonista))

    for cena, protagonista in pendentes:
        dna = protagonista["descricao_fixa"]
        imagem_base = protagonista["imagem_referencia"]

        prompt = prompt_colorir(cena, dna)
        # Opção 1: gera do zero como line-art (não converte a colorida),
        # usando a referência do personagem pra manter reconhecível.
        caminho = gerar_imagem(prompt=prompt, imagem_base=imagem_base)
        if not isinstance(caminho, str) or not caminho.strip():
            raise ValueError("O gerador não retornou uma imagem de colorir utilizável. As páginas anteriores foram preservadas.")

        item = CenaImagem(
                numero=cena["numero"],
                prompt_final=prompt,
                caminho_arquivo=caminho,
                aprovado=False,
            )
        existente = existentes.get(str(cena["numero"]))
        if existente:
            paginas_colorir[paginas_colorir.index(existente)] = item
        else:
            paginas_colorir.append(item)
        state["paginas_colorir"] = list(paginas_colorir)
        persist_generation_snapshot(state, reason=f"coloring_activity_generated:{cena['numero']}")
    return state


# Refinamento 21 — papéis formais deste módulo (auditáveis pelo Skill Registry).
SKILL_PROFILE_IDS = ('coloring_activity_creator',)

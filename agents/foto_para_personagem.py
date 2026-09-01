"""
Foto para Personagem (photo-to-cartoon).

Transforma uma foto real (da própria autora, de um familiar, de um
animal de estimação) num personagem no estilo fixo da coleção -
mesmas proporções fofas, mesmo tipo de traço, mas mantendo os traços
reconhecíveis da pessoa/bicho real (cor de cabelo, tom de pele, formato
do rosto, óculos, etc.) como base pro DNA visual do personagem.

Diferente de gerar um personagem do zero: aqui a FOTO é a imagem-base
enviada pro gerador de imagem (image-to-image), não uma referência de
outro personagem já existente - o resultado é uma interpretação nova,
não uma cópia exata da foto (afinal ela vira um personagem de desenho).
"""

from state import PersonagemDNA
from agents.ilustrador import ESTILO_VISUAL_FIXO

PROMPT_FOTO_PARA_PERSONAGEM = """\
{estilo_visual}

Transforme a pessoa/animal desta foto de referência num personagem
original de desenho animado fofo, nesse estilo. Mantenha reconhecíveis
os traços marcantes da foto (cor e tipo de cabelo, tom de pele, formato
do rosto, óculos ou acessório característico, cor da pelagem se for um
animal de estimação) - o personagem deve ser uma versão estilizada e
fofa da pessoa/animal real, não uma cópia fotográfica nem uma pessoa
genérica.

Detalhe extra fornecido pela autora sobre esse personagem: {detalhe_extra}
Papel na história: {papel}
"""


def gerar_personagem_a_partir_de_foto(
    caminho_foto: str, nome: str, papel: str, gerar_imagem, detalhe_extra: str = ""
) -> PersonagemDNA:
    """
    caminho_foto: a foto real enviada pela autora (usada como
    imagem-base / image-to-image, não só como inspiração textual).
    """
    prompt = PROMPT_FOTO_PARA_PERSONAGEM.format(
        estilo_visual=ESTILO_VISUAL_FIXO,
        detalhe_extra=detalhe_extra or "(nenhum)",
        papel=papel,
    )
    caminho_gerado = gerar_imagem(prompt=prompt, imagem_base=caminho_foto)
    return PersonagemDNA(
        nome=nome,
        descricao_fixa=(
            f"Personagem baseado em foto real (photo-to-cartoon), "
            f"mantendo os traços reconhecíveis da referência original. "
            f"{detalhe_extra}"
        ),
        imagem_referencia=caminho_gerado,
        origem_referencia="gerada_a_partir_de_foto",
        papel=papel,
    )

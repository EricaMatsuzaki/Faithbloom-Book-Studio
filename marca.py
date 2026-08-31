"""
Elementos de marca fixos da coleção (faixa de texto no topo da capa,
selo/emblema na contracapa).

DECISÃO DE ARQUITETURA IMPORTANTE: esses elementos NÃO são gerados
pela IA de imagem a cada capa. Pedir pra IA "redesenhar" um logo ou um
texto todo livro reintroduz o mesmo problema de inconsistência que o
DNA fixo do personagem resolve - texto e logo gerados por IA nunca
saem pixel-idênticos duas vezes.

Em vez disso: a autora cria o selo (e opcionalmente a faixa) UMA vez
como imagem estática (PNG com fundo transparente, feito no Canva ou
onde preferir), o sistema guarda esse arquivo por coleção, e todo
livro novo só SOBREPÕE essa mesma imagem em cima da arte gerada -
usando PIL, não a IA. Isso garante que o selo fica sempre idêntico.

A faixa de texto do título ("COLEÇÃO X") tem duas opções:
    - Se a autora fornecer um PNG próprio da faixa -> usa ele.
    - Senão, o sistema desenha a faixa com PIL (fonte real, não IA)
      -  também garante consistência entre capas.
"""

from PIL import Image, ImageDraw, ImageFont

LARGURA_PADRAO_SELO_PCT = 0.16   # o selo ocupa ~16% da largura da imagem
MARGEM_PCT = 0.04


def _fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    # Usa a fonte padrão do sistema; troque o caminho se a autora tiver
    # uma fonte de marca específica (ex: a mesma serifada usada no Canva).
    try:
        return ImageFont.truetype("DejaVuSerif-Bold.ttf", tamanho)
    except OSError:
        return ImageFont.load_default()


def aplicar_faixa_colecao(caminho_imagem: str, colecao: str, caminho_faixa_png: str | None = None) -> str:
    """
    Sobrepõe a faixa "COLEÇÃO X" no topo da imagem. Se a autora tiver um
    PNG próprio da faixa (com transparência), usa ele; senão desenha
    uma faixa simples com PIL.
    """
    base = Image.open(caminho_imagem).convert("RGBA")
    largura, altura = base.size

    if caminho_faixa_png:
        faixa = Image.open(caminho_faixa_png).convert("RGBA")
        prop = largura * 0.7 / faixa.width
        faixa = faixa.resize((int(faixa.width * prop), int(faixa.height * prop)))
        pos = ((largura - faixa.width) // 2, int(altura * 0.03))
        base.alpha_composite(faixa, pos)
    else:
        draw = ImageDraw.Draw(base)
        texto = f"COLEÇÃO {colecao.upper()}"
        fonte = _fonte(int(largura * 0.028))
        bbox = draw.textbbox((0, 0), texto, font=fonte)
        largura_texto = bbox[2] - bbox[0]
        altura_texto = bbox[3] - bbox[1]
        padding_x, padding_y = 24, 12
        caixa = [
            (largura - largura_texto) // 2 - padding_x,
            int(altura * 0.03),
            (largura + largura_texto) // 2 + padding_x,
            int(altura * 0.03) + altura_texto + 2 * padding_y,
        ]
        draw.rounded_rectangle(caixa, radius=8, fill=(255, 255, 255, 235), outline=(160, 130, 60, 255), width=2)
        draw.text(
            ((largura - largura_texto) // 2, caixa[1] + padding_y),
            texto, font=fonte, fill=(60, 50, 20, 255),
        )

    caminho_saida = caminho_imagem.replace(".png", "_com_faixa.png")
    base.convert("RGB").save(caminho_saida)
    return caminho_saida


def aplicar_selo_colecao(caminho_imagem: str, caminho_selo_png: str, posicao: str = "inferior_esquerda") -> str:
    """
    Sobrepõe o selo/emblema da coleção (PNG com transparência,
    fornecido pela autora) num canto da imagem - por padrão na
    contracapa, canto inferior esquerdo, como no exemplo da Erica.
    """
    base = Image.open(caminho_imagem).convert("RGBA")
    selo = Image.open(caminho_selo_png).convert("RGBA")

    largura_alvo = int(base.width * LARGURA_PADRAO_SELO_PCT)
    prop = largura_alvo / selo.width
    selo = selo.resize((largura_alvo, int(selo.height * prop)))

    margem = int(base.width * MARGEM_PCT)
    posicoes = {
        "inferior_esquerda": (margem, base.height - selo.height - margem),
        "inferior_direita": (base.width - selo.width - margem, base.height - selo.height - margem),
        "superior_esquerda": (margem, margem),
        "superior_direita": (base.width - selo.width - margem, margem),
    }
    base.alpha_composite(selo, posicoes[posicao])

    caminho_saida = caminho_imagem.replace(".png", "_com_selo.png")
    base.convert("RGB").save(caminho_saida)
    return caminho_saida

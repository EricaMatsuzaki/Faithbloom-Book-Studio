"""FaithBloom 2.0 - Renderizador Editorial PDF (Fase 6).

Gera o MIOLO print-ready em PDF a partir do ``LivroState`` já aprovado.
A capa física continua sendo um arquivo separado, como exige o fluxo KDP.

Princípios:
- páginas individuais, nunca spreads artificiais;
- trim size e bleed calculados em polegadas -> pontos PDF;
- ilustrações full-bleed ocupam a página inteira do arquivo;
- texto permanece dentro de safe area + gutter;
- páginas de line art ficam dentro de margem segura para não cortar traços;
- original das imagens nunca é alterado;
- Boas-vindas, Pais/Educadores e Ficha Pedagógica podem virar páginas físicas;
- tipografia narrativa respeita a faixa etária oficial do livro;
- PDF só é exportado quando o preflight automático de assets não tem bloqueios,
  salvo se ``forcar=True`` for escolhido conscientemente para prova interna.

A validação automática posterior está em ``qualidade_impressao.analisar_pdf_miolo``.
"""
from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from author_profiles import author_display_from_state
from age_profiles import perfil_etario
from qualidade_impressao import (
    BLEED_IN,
    gutter_minimo_in,
    margem_externa_minima_in,
    preflight_livro,
)

PT = 72.0
PASTA_EXPORTACOES = "exportacoes_kdp"

_FONT_NORMAL = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_FONTS_REGISTRADAS = False


def _registrar_fontes() -> None:
    global _FONT_NORMAL, _FONT_BOLD, _FONTS_REGISTRADAS
    if _FONTS_REGISTRADAS:
        return
    candidatos = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/local/share/fonts/DejaVuSans.ttf", "/usr/local/share/fonts/DejaVuSans-Bold.ttf"),
    ]
    for normal, bold in candidatos:
        if os.path.exists(normal) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont("FaithBloomSans", normal))
                pdfmetrics.registerFont(TTFont("FaithBloomSansBold", bold))
                _FONT_NORMAL = "FaithBloomSans"
                _FONT_BOLD = "FaithBloomSansBold"
                break
            except Exception:
                pass
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    except Exception:
        pass
    _FONTS_REGISTRADAS = True


def _tem_cjk(texto: str) -> bool:
    return any(
        "\u3040" <= ch <= "\u30ff" or "\u3400" <= ch <= "\u9fff"
        for ch in (texto or "")
    )


def _fontes_para_texto(texto: str) -> tuple[str, str]:
    _registrar_fontes()
    if _tem_cjk(texto):
        return "HeiseiKakuGo-W5", "HeiseiKakuGo-W5"
    return _FONT_NORMAL, _FONT_BOLD


def _slug(texto: str) -> str:
    import re
    s = (texto or "livro").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "livro"


def _pagina_pts(trim_w: float, trim_h: float, bleed: bool) -> tuple[float, float, float]:
    b = BLEED_IN if bleed else 0.0
    return (trim_w + (b if bleed else 0.0)) * PT, (trim_h + 2 * b) * PT, b * PT


def _mapear_por_numero(itens: list[dict] | None) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for item in itens or []:
        try:
            out[int(item.get("numero", item.get("cena_numero")))] = item
        except (TypeError, ValueError):
            continue
    return out


def _draw_image_cover(c: canvas.Canvas, caminho: str, x: float, y: float, w: float, h: float) -> bool:
    if not caminho or not os.path.exists(caminho):
        return False
    try:
        with Image.open(caminho) as im:
            iw, ih = im.size
        if iw <= 0 or ih <= 0:
            return False
        escala = max(w / iw, h / ih)
        dw, dh = iw * escala, ih * escala
        dx, dy = x + (w - dw) / 2, y + (h - dh) / 2
        c.saveState()
        p = c.beginPath()
        p.rect(x, y, w, h)
        c.clipPath(p, stroke=0, fill=0)
        c.drawImage(ImageReader(caminho), dx, dy, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
        c.restoreState()
        return True
    except Exception:
        return False


def _draw_image_contain(c: canvas.Canvas, caminho: str, x: float, y: float, w: float, h: float) -> bool:
    if not caminho or not os.path.exists(caminho):
        return False
    try:
        with Image.open(caminho) as im:
            iw, ih = im.size
        escala = min(w / iw, h / ih)
        dw, dh = iw * escala, ih * escala
        dx, dy = x + (w - dw) / 2, y + (h - dh) / 2
        c.drawImage(ImageReader(caminho), dx, dy, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
        return True
    except Exception:
        return False


def _placeholder(c: canvas.Canvas, texto: str, page_w: float, page_h: float) -> None:
    c.saveState()
    c.setStrokeColor(HexColor("#D9DDE5"))
    c.setFillColor(HexColor("#F7F8FA"))
    c.roundRect(page_w * 0.12, page_h * 0.28, page_w * 0.76, page_h * 0.44, 12, fill=1, stroke=1)
    c.setFillColor(HexColor("#707680"))
    c.setFont(_FONT_NORMAL, 10)
    c.drawCentredString(page_w / 2, page_h / 2, texto[:110])
    c.restoreState()


def _safe_box(page_w: float, page_h: float, bleed_pt: float, pagina_num: int, total: int, bleed: bool) -> tuple[float, float, float, float]:
    margem_ext = margem_externa_minima_in(bleed) * PT
    gutter = gutter_minimo_in(total) * PT
    left = bleed_pt + (gutter if pagina_num % 2 == 1 else margem_ext)
    right = bleed_pt + (margem_ext if pagina_num % 2 == 1 else gutter)
    top = bleed_pt + margem_ext
    bottom = bleed_pt + margem_ext
    return left, bottom, max(24, page_w - left - right), max(24, page_h - top - bottom)


def _paragraph(c: canvas.Canvas, texto: str, x: float, y: float, w: float, h: float,
               font_size: float = 17, leading: float | None = None, align=TA_LEFT,
               bold: bool = False, cor: str = "#273036") -> None:
    normal, bold_font = _fontes_para_texto(texto)
    fonte = bold_font if bold else normal
    leading = leading or font_size * 1.45
    estilo = ParagraphStyle(
        "FaithBloom",
        fontName=fonte,
        fontSize=font_size,
        leading=leading,
        textColor=HexColor(cor),
        alignment=align,
        spaceAfter=0,
        allowWidows=0,
        allowOrphans=0,
    )
    seguro = html.escape(texto or "").replace("\n", "<br/>")
    p = Paragraph(seguro, estilo)
    _, ph = p.wrap(w, h)
    p.drawOn(c, x, y + h - ph)


def _lista_texto(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "\n".join(f"• {str(x).strip()}" for x in value if str(x).strip())
    if value is None:
        return ""
    return str(value).strip()


def _desenhar_rosto(c: canvas.Canvas, state: dict, page_w: float, page_h: float, bleed_pt: float) -> None:
    titulo = state.get("titulo", "Livro sem título")
    colecao = state.get("colecao", "")
    autora = author_display_from_state(state)
    x = bleed_pt + 0.65 * PT
    w = page_w - 2 * (bleed_pt + 0.65 * PT)
    _paragraph(c, colecao.upper(), x, page_h * 0.73, w, 0.4 * PT, 10, align=TA_CENTER, cor="#799588")
    _paragraph(c, titulo, x, page_h * 0.47, w, 2.0 * PT, 28, 34, TA_CENTER, bold=True, cor="#25342F")
    _paragraph(c, autora, x, page_h * 0.26, w, 0.6 * PT, 13, align=TA_CENTER, cor="#65736E")


def _desenhar_creditos_dedicatoria(c: canvas.Canvas, state: dict, page_w: float, page_h: float,
                                    bleed_pt: float, pagina_num: int, total: int, bleed: bool) -> None:
    x, y, w, h = _safe_box(page_w, page_h, bleed_pt, pagina_num, total, bleed)
    ded = state.get("dedicatoria_texto", "")
    texto = ded if ded else (
        f"{state.get('titulo','')}\n\n"
        f"Autoria: {author_display_from_state(state)}\n"
        "Edição preparada no FaithBloom Book Studio."
    )
    _paragraph(c, texto, x, y, w, h, 12.5, 19, TA_LEFT, cor="#37433F")


def _desenhar_boas_vindas(c: canvas.Canvas, state: dict, page_w: float, page_h: float,
                           bleed_pt: float, pagina_num: int, total: int, bleed: bool) -> None:
    x, y, w, h = _safe_box(page_w, page_h, bleed_pt, pagina_num, total, bleed)
    texto = str(state.get("boas_vindas") or "Bem-vindos a uma nova história FaithBloom, feita para crescer em fé, amor e aprendizado.")
    faixa = perfil_etario(state.get("faixa_etaria"))["short_label"]
    referencia = str(state.get("versiculo_referencia") or "").strip()
    _paragraph(c, "Bem-vindos!", x, y + h * 0.69, w, h * 0.14, 23, 30, TA_CENTER, bold=True, cor="#365C50")
    _paragraph(c, texto, x + w * 0.06, y + h * 0.28, w * 0.88, h * 0.36, 14.5, 22, TA_CENTER, cor="#33433D")
    rodape = f"Faixa etária: {faixa}" + (f"  •  Referência bíblica: {referencia}" if referencia else "")
    _paragraph(c, rodape, x, y + h * 0.12, w, h * 0.08, 9.5, 13, TA_CENTER, cor="#788680")


def _desenhar_texto_cena(c: canvas.Canvas, state: dict, cena: dict, page_w: float, page_h: float,
                         bleed_pt: float, pagina_num: int, total: int, bleed: bool) -> None:
    x, y, w, h = _safe_box(page_w, page_h, bleed_pt, pagina_num, total, bleed)
    inset = min(0.25 * PT, w * 0.04)
    perfil = perfil_etario(state.get("faixa_etaria"))
    font_size = float(perfil.get("pdf_font_size") or 18.0)
    leading = float(perfil.get("pdf_leading") or font_size * 1.5)
    _paragraph(
        c,
        cena.get("texto", ""),
        x + inset,
        y + h * 0.16,
        w - 2 * inset,
        h * 0.68,
        font_size=font_size,
        leading=leading,
        align=TA_LEFT,
        cor="#26332E",
    )


def _desenhar_final(c: canvas.Canvas, state: dict, tipo: str, page_w: float, page_h: float,
                    bleed_pt: float, pagina_num: int, total: int, bleed: bool) -> None:
    x, y, w, h = _safe_box(page_w, page_h, bleed_pt, pagina_num, total, bleed)
    if tipo == "resolucao":
        texto = state.get("licao_final", "") or "Uma pequena história pode guardar uma grande lição."
        titulo = "O que aprendemos"
    elif tipo == "celebracao":
        texto = "Que esta história continue florescendo no coração de quem a leu."
        titulo = "Com carinho"
    else:
        vers = state.get("versiculo_referencia", "")
        texto = f"Lição de Moral\n{state.get('licao_final','')}\n\nVersículo Bíblico\n{vers}\n\nFIM"
        titulo = "Pequenas Histórias, Grandes Lições"
    _paragraph(c, titulo, x, y + h * 0.63, w, h * 0.18, 21, 28, TA_CENTER, bold=True, cor="#365C50")
    _paragraph(c, texto, x + w * 0.06, y + h * 0.18, w * 0.88, h * 0.42, 14.5, 22, TA_CENTER, cor="#33433D")


def _desenhar_pais_educadores(c: canvas.Canvas, state: dict, page_w: float, page_h: float,
                              bleed_pt: float, pagina_num: int, total: int, bleed: bool) -> None:
    x, y, w, h = _safe_box(page_w, page_h, bleed_pt, pagina_num, total, bleed)
    dados = state.get("pais_educadores") if isinstance(state.get("pais_educadores"), dict) else {}
    blocos = []
    if dados.get("mensagem"):
        blocos.append(str(dados["mensagem"]))
    for rotulo, chave in (
        ("Tema", "tema"),
        ("Emoção trabalhada", "emocao_trabalhada"),
        ("Princípio bíblico", "principio_biblico"),
        ("Habilidade socioemocional", "habilidade_socioemocional"),
    ):
        if dados.get(chave):
            blocos.append(f"{rotulo}: {dados[chave]}")
    if dados.get("perguntas"):
        blocos.append("Perguntas para conversar:\n" + _lista_texto(dados.get("perguntas")))
    if dados.get("aplicacoes"):
        blocos.append("Aplicações práticas:\n" + _lista_texto(dados.get("aplicacoes")))
    texto = "\n\n".join(blocos) or "Conteúdo para pais e educadores ainda não preenchido."
    _paragraph(c, "Para Pais e Educadores", x, y + h * 0.78, w, h * 0.12, 20, 26, TA_CENTER, bold=True, cor="#365C50")
    _paragraph(c, texto, x + w * 0.03, y + h * 0.08, w * 0.94, h * 0.66, 11.2, 16.5, TA_LEFT, cor="#33433D")


def _desenhar_ficha_pedagogica(c: canvas.Canvas, state: dict, page_w: float, page_h: float,
                                bleed_pt: float, pagina_num: int, total: int, bleed: bool) -> None:
    x, y, w, h = _safe_box(page_w, page_h, bleed_pt, pagina_num, total, bleed)
    dados = state.get("ficha_pedagogica") if isinstance(state.get("ficha_pedagogica"), dict) else {}
    faixa = dados.get("faixa_etaria") or perfil_etario(state.get("faixa_etaria"))["short_label"]
    blocos = [f"Faixa etária: {faixa}"]
    for rotulo, chave in (
        ("Tema central", "tema_central"),
        ("Emoção principal", "emocao_principal"),
        ("Habilidade socioemocional", "habilidade_socioemocional"),
        ("Valor cristão", "valor_cristao"),
        ("Referência bíblica", "versiculo_referencia"),
        ("Objetivo pedagógico", "objetivo_pedagogico"),
        ("Psicologia das cores", "psicologia_das_cores"),
    ):
        if dados.get(chave):
            blocos.append(f"{rotulo}: {dados[chave]}")
    if dados.get("perguntas_reflexao"):
        blocos.append("Perguntas de reflexão:\n" + _lista_texto(dados.get("perguntas_reflexao")))
    texto = "\n\n".join(blocos)
    _paragraph(c, "Ficha Pedagógica", x, y + h * 0.78, w, h * 0.12, 20, 26, TA_CENTER, bold=True, cor="#365C50")
    _paragraph(c, texto, x + w * 0.03, y + h * 0.08, w * 0.94, h * 0.66, 10.8, 16, TA_LEFT, cor="#33433D")


def renderizar_miolo_pdf(state: dict, destino: str | None = None, bleed: bool = True,
                          forcar: bool = False) -> dict[str, Any]:
    """Gera o PDF físico do miolo e devolve metadados do arquivo."""
    _registrar_fontes()
    pf = preflight_livro(state, bleed=bleed)
    if pf["bloqueios"] and not forcar:
        return {"ok": False, "motivo": "Preflight automático bloqueou a exportação.", "preflight": pf}

    trim_w = float(state.get("trim_largura_in") or 8.5)
    trim_h = float(state.get("trim_altura_in") or 8.5)
    page_w, page_h, bleed_pt = _pagina_pts(trim_w, trim_h, bleed)
    layout = sorted(state.get("layout_paginas", []) or [], key=lambda p: int(p.get("pagina", 0)))
    if not layout:
        return {"ok": False, "motivo": "O livro ainda não possui layout_paginas. Rode o Diagramador primeiro.", "preflight": pf}

    total = max(int(p.get("pagina", 0)) for p in layout)
    if total % 2:
        total += 1

    Path(PASTA_EXPORTACOES).mkdir(parents=True, exist_ok=True)
    destino = destino or os.path.join(PASTA_EXPORTACOES, f"{_slug(state.get('titulo','livro'))}-miolo-print-ready.pdf")
    Path(destino).parent.mkdir(parents=True, exist_ok=True)

    cenas = _mapear_por_numero(state.get("cenas_texto"))
    imagens = _mapear_por_numero(state.get("cenas_imagem"))
    colorir = _mapear_por_numero(state.get("paginas_colorir"))
    por_pagina = {int(p["pagina"]): p for p in layout}

    c = canvas.Canvas(destino, pagesize=(page_w, page_h), pageCompression=1, initialFontName=_FONT_NORMAL, initialFontSize=10)
    c.setTitle(state.get("titulo", "FaithBloom Book"))
    c.setAuthor(author_display_from_state(state))
    c.setSubject("Miolo print-ready gerado pelo FaithBloom Book Studio")

    avisos: list[str] = []
    for pagina_num in range(1, total + 1):
        c.setFillColor(HexColor("#FFFFFF"))
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

        if pagina_num == 1:
            _desenhar_rosto(c, state, page_w, page_h, bleed_pt)
        elif pagina_num == 2:
            _desenhar_creditos_dedicatoria(c, state, page_w, page_h, bleed_pt, pagina_num, total, bleed)
        else:
            item = por_pagina.get(pagina_num)
            if item:
                tipo = item.get("tipo")
                num = item.get("cena_numero")
                if tipo == "boas_vindas":
                    _desenhar_boas_vindas(c, state, page_w, page_h, bleed_pt, pagina_num, total, bleed)
                elif tipo == "texto":
                    _desenhar_texto_cena(c, state, cenas.get(int(num), {}), page_w, page_h, bleed_pt, pagina_num, total, bleed)
                elif tipo == "imagem":
                    caminho = imagens.get(int(num), {}).get("caminho_arquivo", "")
                    if not _draw_image_cover(c, caminho, 0, 0, page_w, page_h):
                        _placeholder(c, f"Ilustração da cena {num} não encontrada", page_w, page_h)
                        avisos.append(f"Cena {num}: ilustração ausente no PDF.")
                elif tipo == "atividade_colorir":
                    caminho = colorir.get(int(num), {}).get("caminho_arquivo", "")
                    x, y, w, h = _safe_box(page_w, page_h, bleed_pt, pagina_num, total, bleed)
                    if not _draw_image_contain(c, caminho, x, y, w, h):
                        _placeholder(c, f"Line art da cena {num} não encontrada", page_w, page_h)
                        avisos.append(f"Cena {num}: line art ausente no PDF.")
                elif tipo in ("resolucao", "celebracao", "licao_e_versiculo_fim"):
                    _desenhar_final(c, state, tipo, page_w, page_h, bleed_pt, pagina_num, total, bleed)
                elif tipo == "pais_educadores":
                    _desenhar_pais_educadores(c, state, page_w, page_h, bleed_pt, pagina_num, total, bleed)
                elif tipo == "ficha_pedagogica":
                    _desenhar_ficha_pedagogica(c, state, page_w, page_h, bleed_pt, pagina_num, total, bleed)
                elif tipo not in ("pagina_em_branco", "verso_em_branco"):
                    avisos.append(f"Página {pagina_num}: tipo de layout desconhecido '{tipo}'.")
        c.showPage()

    c.save()
    return {
        "ok": True,
        "caminho": destino,
        "paginas": total,
        "page_size_in": [round(page_w / PT, 4), round(page_h / PT, 4)],
        "bleed": bleed,
        "avisos": avisos,
        "preflight_assets": pf,
    }

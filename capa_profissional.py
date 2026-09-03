"""FaithBloom 2.0 - Fase 7: capa física paperback montada matematicamente.

A IA gera apenas as ARTES (frente e contracapa). Este módulo é responsável
pela geometria de impressão: bleed, contracapa, lombada, capa frontal,
áreas seguras, reserva de barcode, textos e PDF final em dimensão exata.

Regras KDP usadas nesta fase (revalidar periodicamente):
- bleed externo: 0.125 in;
- safe area de conteúdo: mínimo 0.25 in da borda externa do arquivo;
- tolerância de dobra junto à lombada: 0.0625 in de cada lado;
- texto na lombada: somente para livros com mais de 79 páginas;
- papel colorido: espessura = páginas x 0.002347 in;
- barcode recomendado: 2 x 1.2 in, pelo menos 0.25 in da lombada e do trim.

A saída de produção é um PDF de UMA página, contendo contracapa + lombada +
capa frontal. A prévia PNG inclui guias opcionais; o PDF final NÃO inclui
crop marks, linhas-guia nem anotações.
"""

from __future__ import annotations

import os
import re
import textwrap
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pypdf import PdfReader
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader

from kdp_rules import BLEED_IN, DPI_CAPA, calcular_dimensoes_capa_fisica

PT_PER_IN = 72.0
SAFE_OUTER_IN = 0.25
SPINE_FOLD_VARIANCE_IN = 0.0625
BARCODE_W_IN = 2.0
BARCODE_H_IN = 1.2
BARCODE_CLEAR_IN = 0.25


@dataclass(frozen=True)
class GeometriaCapa:
    trim_w: float
    trim_h: float
    paginas: int
    papel: str
    spine_w: float
    total_w: float
    total_h: float
    dpi: int

    @property
    def px_total(self):
        return (round(self.total_w * self.dpi), round(self.total_h * self.dpi))

    def x_in(self):
        # coordenadas verticais do wrap, da esquerda para a direita
        x_back_start = BLEED_IN
        x_back_end = x_back_start + self.trim_w
        x_spine_end = x_back_end + self.spine_w
        x_front_end = x_spine_end + self.trim_w
        return {
            "arquivo_esquerda": 0.0,
            "back_start": x_back_start,
            "back_end": x_back_end,
            "spine_start": x_back_end,
            "spine_end": x_spine_end,
            "front_start": x_spine_end,
            "front_end": x_front_end,
            "arquivo_direita": self.total_w,
        }


def geometria_capa(trim_w: float, trim_h: float, paginas: int, papel: str = "cor_premium") -> GeometriaCapa:
    d = calcular_dimensoes_capa_fisica(trim_w, trim_h, paginas, papel)
    return GeometriaCapa(
        trim_w=float(trim_w), trim_h=float(trim_h), paginas=int(paginas), papel=papel,
        spine_w=float(d["largura_lombada_in"]), total_w=float(d["largura_total_in"]),
        total_h=float(d["altura_total_in"]), dpi=int(d["dpi"]),
    )


def _font(size: int, bold: bool = False):
    candidatos = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf",
    ]
    for c in candidatos:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _cover_resize(path: str, size: tuple[int, int]) -> Image.Image:
    img = Image.open(path).convert("RGB")
    return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _draw_centered_multiline(draw, box, text, font, fill, spacing=8):
    x0, y0, x1, y1 = box
    max_w = x1 - x0
    # wrap aproximado com medida real
    words = str(text).split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_w or not current:
            current = candidate
        else:
            lines.append(current); current = word
    if current: lines.append(current)
    heights = [draw.textbbox((0,0), l, font=font)[3] for l in lines]
    total_h = sum(heights) + max(0, len(lines)-1)*spacing
    y = y0 + max(0, (y1-y0-total_h)/2)
    for line, h in zip(lines, heights):
        bbox = draw.textbbox((0,0), line, font=font)
        w = bbox[2]-bbox[0]
        draw.text((x0+(max_w-w)/2, y), line, font=font, fill=fill)
        y += h + spacing


def _draw_wrapped_left(draw, box, text, font, fill, spacing=6):
    x0,y0,x1,y1=box; max_w=x1-x0
    words=str(text).split(); lines=[]; cur=""
    for word in words:
        cand=(cur+" "+word).strip()
        if draw.textbbox((0,0), cand, font=font)[2] <= max_w or not cur:
            cur=cand
        else:
            lines.append(cur); cur=word
    if cur: lines.append(cur)
    line_h=max(draw.textbbox((0,0), "Ag", font=font)[3],1)+spacing
    max_lines=max(1,int((y1-y0)/line_h))
    lines=lines[:max_lines]
    y=y0
    for line in lines:
        draw.text((x0,y),line,font=font,fill=fill); y+=line_h


def compor_capa_paperback(
    arte_frente: str,
    arte_verso: str,
    saida_png: str,
    trim_w: float,
    trim_h: float,
    paginas: int,
    papel: str = "cor_premium",
    titulo: str = "",
    subtitulo: str = "",
    autora: str = "",
    colecao: str = "",
    sinopse: str = "",
    spine_text: str = "",
    reservar_barcode: bool = True,
    mostrar_guias: bool = False,
) -> dict:
    """Monta o wrap final em 300 PPI. Nunca pede à IA para posicionar lombada."""
    if not os.path.exists(arte_frente) or not os.path.exists(arte_verso):
        raise FileNotFoundError("As artes de frente e contracapa precisam existir antes da montagem.")
    g = geometria_capa(trim_w, trim_h, paginas, papel)
    W,H=g.px_total
    inch=g.dpi
    bleed=round(BLEED_IN*inch)
    spine=round(g.spine_w*inch)
    trim_w_px=round(g.trim_w*inch)
    trim_h_px=round(g.trim_h*inch)

    canvas=Image.new("RGB",(W,H),(245,242,236))
    # Cada painel recebe bleed no topo/baixo e no lado externo; junto à lombada não existe bleed.
    back_box=(0,0,bleed+trim_w_px,H)
    front_x=bleed+trim_w_px+spine
    front_box=(front_x,0,W,H)
    back=_cover_resize(arte_verso,(back_box[2]-back_box[0],H))
    front=_cover_resize(arte_frente,(front_box[2]-front_box[0],H))
    canvas.paste(back,(0,0)); canvas.paste(front,(front_x,0))

    # Lombada usa média das cores de borda para não criar uma faixa branca artificial.
    left_color=front.resize((1,1)).getpixel((0,0)); right_color=back.resize((1,1)).getpixel((0,0))
    spine_color=tuple((a+b)//2 for a,b in zip(left_color,right_color))
    ImageDraw.Draw(canvas).rectangle((bleed+trim_w_px,0,front_x,H),fill=spine_color)
    draw=ImageDraw.Draw(canvas,"RGBA")

    safe=round(SAFE_OUTER_IN*inch)
    top_safe=bleed+safe
    bottom_safe=H-bleed-safe
    back_left=bleed+safe
    back_right=bleed+trim_w_px-safe
    front_left=front_x+safe
    front_right=W-bleed-safe

    # Fundo translúcido discreto para legibilidade do título; não depende da IA acertar tipografia.
    if titulo:
        title_h=round(H*0.24)
        box=(front_left,top_safe,front_right,top_safe+title_h)
        draw.rounded_rectangle(box,radius=max(8,round(W*.004)),fill=(255,255,255,205))
        _draw_centered_multiline(draw,(box[0]+20,box[1]+15,box[2]-20,box[3]-15),titulo,_font(max(24,round(trim_w_px*.055)),True),(35,35,45,255),8)
    if subtitulo:
        y=top_safe+round(H*.245)
        _draw_centered_multiline(draw,(front_left,y,front_right,y+round(H*.11)),subtitulo,_font(max(18,round(trim_w_px*.028))), (45,45,55,255),5)
    if autora:
        f=_font(max(18,round(trim_w_px*.027)),True)
        bbox=draw.textbbox((0,0),autora,font=f); tw=bbox[2]-bbox[0]
        draw.rounded_rectangle((front_left,bottom_safe-round(H*.075),front_right,bottom_safe),radius=10,fill=(255,255,255,190))
        draw.text((front_left+(front_right-front_left-tw)/2,bottom_safe-round(H*.055)),autora,font=f,fill=(35,35,45,255))

    # Contracapa: sinopse dentro da safe area, preservando região do barcode.
    barcode_box=None
    if reservar_barcode:
        bw=round(BARCODE_W_IN*inch); bh=round(BARCODE_H_IN*inch); clear=round(BARCODE_CLEAR_IN*inch)
        # lower-right da contracapa, porém dentro do trim e longe de lombada/trim.
        bx1=bleed+trim_w_px-clear
        bx0=bx1-bw
        by1=bleed+trim_h_px-clear
        by0=by1-bh
        barcode_box=(bx0,by0,bx1,by1)
        # reserva limpa; Amazon poderá sobrepor barcode sem cobrir conteúdo importante.
        draw.rounded_rectangle(barcode_box,radius=6,fill=(255,255,255,238))
        if mostrar_guias:
            draw.rectangle(barcode_box,outline=(210,80,80,255),width=3)
            draw.text((bx0+10,by0+10),"ÁREA RESERVADA BARCODE",font=_font(20,True),fill=(160,40,40,255))

    if sinopse:
        synopsis_bottom = (barcode_box[1]-round(.15*inch)) if barcode_box else bottom_safe
        syn_box=(back_left,top_safe+round(H*.08),back_right,synopsis_bottom)
        draw.rounded_rectangle(syn_box,radius=12,fill=(255,255,255,205))
        _draw_wrapped_left(draw,(syn_box[0]+25,syn_box[1]+25,syn_box[2]-25,syn_box[3]-25),sinopse,_font(max(17,round(trim_w_px*.022))), (35,35,45,255),7)

    # Texto de lombada somente quando permitido e quando fisicamente couber.
    spine_permitido=paginas > 79
    spine_text_rendered=False
    if spine_permitido and spine_text and spine >= round(.18*inch):
        temp=Image.new("RGBA",(max(round(trim_h_px*.82),1),max(spine-round(2*SPINE_FOLD_VARIANCE_IN*inch),1)),(0,0,0,0))
        td=ImageDraw.Draw(temp)
        sf=_font(max(12,min(42,round(spine*.28))),True)
        label=spine_text
        bb=td.textbbox((0,0),label,font=sf); tw=bb[2]-bb[0]; th=bb[3]-bb[1]
        if tw < temp.width:
            td.text(((temp.width-tw)/2,(temp.height-th)/2),label,font=sf,fill=(35,35,45,255))
            temp=temp.rotate(90,expand=True)
            sx=bleed+trim_w_px+(spine-temp.width)//2
            sy=(H-temp.height)//2
            canvas=Image.alpha_composite(canvas.convert("RGBA"), Image.new("RGBA",canvas.size,(0,0,0,0)))
            canvas.alpha_composite(temp,(sx,sy)); canvas=canvas.convert("RGB")
            draw=ImageDraw.Draw(canvas,"RGBA")
            spine_text_rendered=True

    if mostrar_guias:
        # Trim + dobras + safe areas apenas na prévia, nunca no PDF final.
        x_back_end=bleed+trim_w_px; x_spine_end=x_back_end+spine
        for x in (bleed,x_back_end,x_spine_end,W-bleed):
            draw.line((x,0,x,H),fill=(30,110,220,190),width=2)
        draw.rectangle((back_left,top_safe,back_right,bottom_safe),outline=(20,160,90,190),width=2)
        draw.rectangle((front_left,top_safe,front_right,bottom_safe),outline=(20,160,90,190),width=2)

    os.makedirs(os.path.dirname(saida_png) or ".",exist_ok=True)
    canvas.save(saida_png,"PNG",dpi=(g.dpi,g.dpi))
    return {
        "caminho_png":saida_png,"largura_total_in":g.total_w,"altura_total_in":g.total_h,
        "largura_lombada_in":g.spine_w,"largura_total_px":W,"altura_total_px":H,
        "dpi":g.dpi,"texto_na_lombada_permitido":spine_permitido,
        "texto_na_lombada_renderizado":spine_text_rendered,"barcode_reservado":bool(barcode_box),
        "papel":papel,"paginas":paginas,
    }


def exportar_capa_pdf(capa_png: str, saida_pdf: str, largura_in: float, altura_in: float) -> str:
    os.makedirs(os.path.dirname(saida_pdf) or ".",exist_ok=True)
    c=pdfcanvas.Canvas(saida_pdf,pagesize=(largura_in*PT_PER_IN,altura_in*PT_PER_IN),pageCompression=1)
    c.drawImage(ImageReader(capa_png),0,0,width=largura_in*PT_PER_IN,height=altura_in*PT_PER_IN,preserveAspectRatio=False,mask='auto')
    c.showPage(); c.save(); return saida_pdf


def analisar_capa_pdf(caminho_pdf: str, largura_esperada_in: float, altura_esperada_in: float) -> dict:
    r=PdfReader(caminho_pdf); erros=[]
    if len(r.pages)!=1: erros.append(f"A capa física deve ter 1 página; arquivo tem {len(r.pages)}.")
    page=r.pages[0]; box=page.mediabox
    w=float(box.width)/72; h=float(box.height)/72
    ok_size=abs(w-largura_esperada_in)<0.01 and abs(h-altura_esperada_in)<0.01
    if not ok_size: erros.append(f"Tamanho PDF {w:.4f} x {h:.4f} in; esperado {largura_esperada_in:.4f} x {altura_esperada_in:.4f} in.")
    return {"ok":not erros,"paginas":len(r.pages),"largura_in":round(w,4),"altura_in":round(h,4),"tamanho_correto":ok_size,"erros":erros}


def gerar_capa_print_ready(
    arte_frente: str, arte_verso: str, pasta_saida: str, **kwargs
) -> dict:
    os.makedirs(pasta_saida,exist_ok=True)
    preview=os.path.join(pasta_saida,"capa_preview_com_guias.png")
    final_png=os.path.join(pasta_saida,"capa_print_ready.png")
    # prévia com guias
    compor_capa_paperback(arte_frente,arte_verso,preview,mostrar_guias=True,**kwargs)
    result=compor_capa_paperback(arte_frente,arte_verso,final_png,mostrar_guias=False,**kwargs)
    pdf=os.path.join(pasta_saida,"capa_print_ready.pdf")
    exportar_capa_pdf(final_png,pdf,result["largura_total_in"],result["altura_total_in"])
    result.update({"caminho_preview":preview,"caminho_pdf":pdf,"pdf_preflight":analisar_capa_pdf(pdf,result["largura_total_in"],result["altura_total_in"])})
    return result

"""FaithBloom 2.0 — motor de qualidade de impressão / preflight KDP.

Não confia no metadado DPI gravado no PNG/JPG. Calcula PPI EFETIVO a partir
dos pixels reais e do tamanho em que a arte será impressa.

Regras-base verificadas em 02/09/2026 nas páginas oficiais da KDP:
- imagens: mínimo recomendado de 300 DPI/PPI para melhor qualidade;
- abaixo de 200 DPI é baixa resolução;
- bleed do miolo: +0.125" na largura externa e +0.25" na altura;
- margem externa mínima: 0.25" sem bleed / 0.375" com bleed;
- gutter depende da contagem de páginas;
- linhas gráficas: mínimo 0.75 pt / 0.01";
- arquivo com bleed deve ser PDF e páginas devem ser individuais.

Este módulo valida o que pode ser medido localmente. A prova física e o
Print Previewer da KDP continuam sendo etapas humanas obrigatórias/recomendadas.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable
from PIL import Image

PPI_ALVO = 300
PPI_BAIXO = 200
BLEED_IN = 0.125


def dimensoes_miolo(trim_largura_in: float, trim_altura_in: float, bleed: bool) -> dict:
    if bleed:
        return {
            "largura_in": round(trim_largura_in + BLEED_IN, 4),
            "altura_in": round(trim_altura_in + 2 * BLEED_IN, 4),
            "bleed_in": BLEED_IN,
        }
    return {"largura_in": trim_largura_in, "altura_in": trim_altura_in, "bleed_in": 0.0}


def pixels_necessarios(largura_in: float, altura_in: float, ppi: int = PPI_ALVO) -> tuple[int, int]:
    return round(largura_in * ppi), round(altura_in * ppi)


def gutter_minimo_in(paginas: int) -> float:
    if paginas <= 150: return 0.375
    if paginas <= 300: return 0.5
    if paginas <= 500: return 0.625
    if paginas <= 700: return 0.75
    return 0.875


def margem_externa_minima_in(bleed: bool) -> float:
    return 0.375 if bleed else 0.25


def analisar_imagem(caminho: str, largura_impressao_in: float, altura_impressao_in: float) -> dict:
    resultado = {
        "arquivo": caminho,
        "existe": False,
        "largura_px": 0,
        "altura_px": 0,
        "ppi_x": 0.0,
        "ppi_y": 0.0,
        "ppi_efetivo": 0.0,
        "status": "ausente",
        "mensagem": "Arquivo não encontrado.",
    }
    if not caminho or not os.path.exists(caminho):
        return resultado
    try:
        with Image.open(caminho) as img:
            w, h = img.size
            modo = img.mode
            formato = img.format
        ppi_x = w / largura_impressao_in
        ppi_y = h / altura_impressao_in
        ppi = min(ppi_x, ppi_y)
        if ppi >= PPI_ALVO:
            status, msg = "excelente", "Atinge 300 PPI efetivos ou mais no tamanho de impressão escolhido."
        elif ppi >= PPI_BAIXO:
            status, msg = "atencao", "Entre 200 e 299 PPI: pode imprimir, mas está abaixo do alvo profissional de 300 PPI."
        else:
            status, msg = "reprovada", "Abaixo de 200 PPI: baixa resolução para impressão."
        return {
            **resultado, "existe": True, "largura_px": w, "altura_px": h,
            "ppi_x": round(ppi_x, 1), "ppi_y": round(ppi_y, 1),
            "ppi_efetivo": round(ppi, 1), "status": status, "mensagem": msg,
            "modo_cor": modo, "formato": formato,
        }
    except Exception as exc:
        return {**resultado, "status": "erro", "mensagem": f"Não foi possível ler a imagem: {exc}"}


def preparar_master_print_ready(caminho: str, destino: str, largura_in: float, altura_in: float,
                                ppi: int = PPI_ALVO, permitir_upscale: bool = False) -> dict:
    """Cria cópia PRINT READY sem destruir o original/master.

    Por padrão NÃO amplia arte pequena: alterar só o metadado DPI não cria detalhe.
    Se permitir_upscale=True, faz Lanczos e registra que houve ampliação para revisão humana.
    """
    analise = analisar_imagem(caminho, largura_in, altura_in)
    if not analise["existe"]:
        return {"ok": False, "motivo": analise["mensagem"], "analise": analise}
    alvo_w, alvo_h = pixels_necessarios(largura_in, altura_in, ppi)
    if (analise["largura_px"] < alvo_w or analise["altura_px"] < alvo_h) and not permitir_upscale:
        return {
            "ok": False,
            "motivo": f"Original insuficiente para {ppi} PPI: precisa de pelo menos {alvo_w}x{alvo_h}px. Gere novamente em maior resolução ou habilite upscale conscientemente.",
            "analise": analise,
        }
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    with Image.open(caminho) as img:
        img = img.convert("RGB")
        ampliada = img.width < alvo_w or img.height < alvo_h
        # crop central proporcional, sem distorcer
        escala = max(alvo_w / img.width, alvo_h / img.height)
        novo = img.resize((round(img.width*escala), round(img.height*escala)), Image.Resampling.LANCZOS)
        x=(novo.width-alvo_w)//2; y=(novo.height-alvo_h)//2
        novo = novo.crop((x,y,x+alvo_w,y+alvo_h))
        novo.save(destino, quality=95, dpi=(ppi,ppi))
    return {"ok": True, "caminho": destino, "ampliada": ampliada,
            "analise": analisar_imagem(destino, largura_in, altura_in)}


def coletar_assets_state(state: dict) -> list[dict]:
    assets=[]
    for item in state.get("cenas_imagem", []) or []:
        assets.append({"tipo":"ilustracao", "numero":item.get("numero"), "arquivo":item.get("caminho_arquivo","")})
    for i,item in enumerate(state.get("paginas_colorir", []) or [],1):
        assets.append({"tipo":"line_art", "numero":item.get("numero", item.get("cena_numero",i)), "arquivo":item.get("caminho_arquivo","")})
    if state.get("capa_ebook"):
        assets.append({"tipo":"capa_ebook", "numero":None, "arquivo":state["capa_ebook"]})
    if state.get("capa_fisica_wrap"):
        assets.append({"tipo":"capa_fisica", "numero":None, "arquivo":state["capa_fisica_wrap"]})
    return assets


def preflight_livro(state: dict, bleed: bool = True) -> dict:
    trim_w=float(state.get("trim_largura_in") or 8.5)
    trim_h=float(state.get("trim_altura_in") or 8.5)
    total=int((state.get("layout_paginas") or [{}])[-1].get("pagina",24))
    pagina = dimensoes_miolo(trim_w, trim_h, bleed)
    alvo_px = pixels_necessarios(pagina["largura_in"], pagina["altura_in"])
    resultados=[]
    for asset in coletar_assets_state(state):
        if asset["tipo"] == "capa_fisica" and state.get("capa_fisica_dimensoes"):
            d=state["capa_fisica_dimensoes"]
            w=float(d.get("largura_total_in", pagina["largura_in"])); h=float(d.get("altura_total_in",pagina["altura_in"]))
        elif asset["tipo"] == "capa_ebook":
            # capa digital não participa do preflight do miolo impresso
            continue
        else:
            w,h=pagina["largura_in"],pagina["altura_in"]
        resultados.append({**asset, **analisar_imagem(asset["arquivo"],w,h)})
    imagens_presentes=[r for r in resultados if r["tipo"] in ("ilustracao","line_art")]
    todas_300=bool(imagens_presentes) and all(r["status"]=="excelente" for r in imagens_presentes)
    nenhuma_baixa=all(r["status"] not in ("reprovada","ausente","erro") for r in imagens_presentes)
    checks={
        "contagem_paginas_par": total % 2 == 0,
        "minimo_24_paginas": total >= 24,
        "bleed_configurado": bool(bleed),
        "margem_externa_minima_in": margem_externa_minima_in(bleed),
        "gutter_minimo_in": gutter_minimo_in(total),
        "pixels_pagina_300ppi": alvo_px,
        "imagens_300ppi": todas_300,
        "sem_imagem_baixa_resolucao": nenhuma_baixa,
        "fontes_embutidas_pdf": False,  # só pode ser confirmado após PDF existir
        "pdf_paginas_individuais": False,
        "transparencias_flatten": False,
        "sem_marcas_de_corte": False,
        "prova_fisica_revisada": False,
    }
    bloqueios=[]
    if not checks["minimo_24_paginas"]: bloqueios.append("Miolo abaixo de 24 páginas.")
    if not checks["contagem_paginas_par"]: bloqueios.append("Contagem física ímpar; inserir página em branco final.")
    if not todas_300: bloqueios.append("Há imagens sem 300 PPI efetivos no tamanho final ou ainda não há imagens para validar.")
    return {
        "trim_in": [trim_w,trim_h], "bleed":bleed, "pagina_arquivo_in":[pagina["largura_in"],pagina["altura_in"]],
        "total_paginas":total, "checks":checks, "assets":resultados, "bloqueios":bloqueios,
        "aprovado_para_exportar_pdf": len(bloqueios)==0,
        "pronto_para_publicar": False,  # somente após PDF + Previewer/prova humana
    }


def _fontes_da_pagina_pdf(page) -> list[dict]:
    """Lista fontes e se possuem stream de fonte embutido quando detectável."""
    fontes = []
    try:
        recursos = page.get("/Resources") or {}
        font_dict = recursos.get("/Font") or {}
        for nome, ref in font_dict.items():
            try:
                font = ref.get_object()
                base = str(font.get("/BaseFont", nome))
                embedded = False
                desc = font.get("/FontDescriptor")
                if desc:
                    desc = desc.get_object()
                    embedded = any(desc.get(k) is not None for k in ("/FontFile", "/FontFile2", "/FontFile3"))
                # Type0/CID: FontDescriptor costuma estar no DescendantFonts.
                if not embedded and font.get("/DescendantFonts"):
                    for dref in font.get("/DescendantFonts"):
                        dfont = dref.get_object()
                        ddesc = dfont.get("/FontDescriptor")
                        if ddesc:
                            ddesc = ddesc.get_object()
                            if any(ddesc.get(k) is not None for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                                embedded = True
                                break
                fontes.append({"nome": base, "embedded": embedded})
            except Exception:
                fontes.append({"nome": str(nome), "embedded": False})
    except Exception:
        pass
    return fontes


def analisar_pdf_miolo(caminho_pdf: str, trim_largura_in: float, trim_altura_in: float,
                        bleed: bool = True, paginas_esperadas: int | None = None) -> dict:
    """Inspeciona o PDF final com pypdf: páginas, MediaBox, fontes e metadados."""
    resultado = {
        "arquivo": caminho_pdf, "existe": False, "paginas": 0,
        "page_sizes_in": [], "page_size_correto": False,
        "fontes": [], "fontes_embutidas": False,
        "paginas_esperadas_ok": False, "erros": [],
    }
    if not caminho_pdf or not os.path.exists(caminho_pdf):
        resultado["erros"].append("PDF não encontrado.")
        return resultado
    try:
        from pypdf import PdfReader
        reader = PdfReader(caminho_pdf)
        resultado["existe"] = True
        resultado["paginas"] = len(reader.pages)
        esperado_w = trim_largura_in + (BLEED_IN if bleed else 0.0)
        esperado_h = trim_altura_in + (2 * BLEED_IN if bleed else 0.0)
        sizes = []
        fontes_todas = []
        for page in reader.pages:
            w = float(page.mediabox.width) / 72.0
            h = float(page.mediabox.height) / 72.0
            sizes.append([round(w, 4), round(h, 4)])
            fontes_todas.extend(_fontes_da_pagina_pdf(page))
        resultado["page_sizes_in"] = sizes
        resultado["page_size_correto"] = bool(sizes) and all(
            abs(w - esperado_w) <= 0.01 and abs(h - esperado_h) <= 0.01 for w, h in sizes
        )
        # deduplica fontes por nome/embedded
        unicos = {(f["nome"], bool(f["embedded"])) for f in fontes_todas}
        resultado["fontes"] = [{"nome": n, "embedded": e} for n, e in sorted(unicos)]
        resultado["fontes_embutidas"] = bool(resultado["fontes"]) and all(f["embedded"] for f in resultado["fontes"])
        resultado["paginas_esperadas_ok"] = paginas_esperadas is None or len(reader.pages) == paginas_esperadas
        if not resultado["page_size_correto"]:
            resultado["erros"].append("MediaBox do PDF não corresponde ao trim/bleed configurado.")
        if not resultado["fontes_embutidas"]:
            resultado["erros"].append("Uma ou mais fontes não foram detectadas como incorporadas.")
        if not resultado["paginas_esperadas_ok"]:
            resultado["erros"].append("Contagem de páginas do PDF difere da esperada.")
        return resultado
    except Exception as exc:
        resultado["erros"].append(f"Falha ao inspecionar PDF: {exc}")
        return resultado

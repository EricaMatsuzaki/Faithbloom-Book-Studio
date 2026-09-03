"""FaithBloom Book Doctor — auditoria conservadora de livros existentes.

Nunca altera o original. Extrai imagens incorporadas do PDF, mede páginas e
resolução e cria um relatório técnico. Avaliações sem evidência mensurável são
marcadas para revisão humana/IA posterior, em vez de inventar notas.
"""
from __future__ import annotations
import hashlib, json, shutil, time, uuid
from pathlib import Path
from PIL import Image
from pypdf import PdfReader

ROOT = Path("book_doctor_projects")

def _safe(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in (s or "livro")).strip("-") or "livro"

def criar_projeto(titulo: str, idioma: str="pt-BR", tipo_projeto: str="story", status_publicacao: str="em_desenvolvimento", colecao: str="", status_capa: str="nao_informado") -> dict:
    pid = uuid.uuid4().hex[:12]
    pasta = ROOT / f"{_safe(titulo)}-{pid}"
    for sub in ("originais", "extraidas", "relatorios", "remastered", "planos"):
        (pasta/sub).mkdir(parents=True, exist_ok=True)
    obj={
        "id":pid,"titulo":titulo,"idioma":idioma,"pasta":str(pasta),
        "tipo_projeto":tipo_projeto,"status_publicacao":status_publicacao,
        "colecao":colecao,"status_capa":status_capa,
        "criado_em":int(time.time()),"status":"importado"
    }
    (pasta/"projeto.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    return obj

def preservar_original(projeto: dict, arquivo: str, papel: str) -> str:
    src=Path(arquivo); dst=Path(projeto["pasta"])/"originais"/f"{papel}_{src.name}"
    shutil.copy2(src,dst)
    manifest_path=Path(projeto["pasta"])/"originais"/"manifest.json"
    try:
        manifest=json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    except Exception:
        manifest=[]
    manifest.append({"papel":papel,"arquivo":str(dst),"sha256":sha256(str(dst)),"preservado_em":int(time.time())})
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return str(dst)

def sha256(caminho: str) -> str:
    h=hashlib.sha256()
    with open(caminho,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def _status_ppi(ppi: float) -> tuple[str,str]:
    if ppi >= 300: return "excelente","300 PPI ou mais"
    if ppi >= 200: return "atencao","200–299 PPI"
    return "reprovada","abaixo de 200 PPI"

def auditar_pdf(caminho_pdf: str, pasta_extraidas: str|None=None) -> dict:
    reader=PdfReader(caminho_pdf)
    out=Path(pasta_extraidas) if pasta_extraidas else None
    if out: out.mkdir(parents=True,exist_ok=True)
    paginas=[]; imagens=[]
    for n,page in enumerate(reader.pages,1):
        mb=page.mediabox; w_in=float(mb.width)/72; h_in=float(mb.height)/72
        fontes=[]
        try:
            fd=(page.get("/Resources") or {}).get("/Font") or {}
            fontes=[str(k) for k in fd.keys()]
        except Exception: pass
        pimgs=[]
        try:
            for i,imgobj in enumerate(page.images,1):
                data=imgobj.data
                ext=Path(imgobj.name or "img.png").suffix or ".png"
                dest=out/f"pagina_{n:03d}_img_{i:02d}{ext}" if out else None
                if dest: dest.write_bytes(data)
                try:
                    from io import BytesIO
                    with Image.open(BytesIO(data)) as im: px=im.size
                except Exception: px=(0,0)
                # Estimativa conservadora: assume que a imagem ocupa a página toda.
                # PPI exato requer interpretar a matriz de transformação do conteúdo PDF.
                ppi=min(px[0]/w_in,px[1]/h_in) if px[0] and w_in and h_in else 0
                status,msg=_status_ppi(ppi) if ppi else ("indeterminado","não foi possível medir")
                rec={"pagina":n,"indice":i,"arquivo_extraido":str(dest) if dest else "","largura_px":px[0],"altura_px":px[1],"ppi_estimado_full_page":round(ppi,1),"status":status,"nota":msg,"estimativa":True}
                pimgs.append(rec); imagens.append(rec)
        except Exception as exc:
            pimgs.append({"pagina":n,"status":"erro","nota":str(exc)})
        paginas.append({"pagina":n,"largura_in":round(w_in,4),"altura_in":round(h_in,4),"imagens":pimgs,"fontes_recursos":fontes})
    tamanhos={(p["largura_in"],p["altura_in"]) for p in paginas}
    return {"arquivo":caminho_pdf,"sha256":sha256(caminho_pdf),"paginas_total":len(paginas),"paginas":paginas,"imagens":imagens,"tamanho_uniforme":len(tamanhos)<=1,"tamanhos_pagina_in":sorted(list(tamanhos)),"observacao_ppi":"PPI de imagens extraídas é uma estimativa conservadora assumindo uso em página inteira; o PPI efetivo depende do tamanho de colocação no PDF.","original_alterado":False}

def auditar_imagem(caminho: str, largura_final_in: float|None=None, altura_final_in: float|None=None) -> dict:
    with Image.open(caminho) as im: w,h=im.size; fmt=im.format; mode=im.mode
    ppi=None; status="indeterminado"; nota="Informe o tamanho final de impressão para calcular PPI efetivo."
    if largura_final_in and altura_final_in:
        ppi=min(w/largura_final_in,h/altura_final_in); status,nota=_status_ppi(ppi)
    return {"arquivo":caminho,"sha256":sha256(caminho),"largura_px":w,"altura_px":h,"formato":fmt,"modo_cor":mode,"ppi_efetivo":round(ppi,1) if ppi else None,"status":status,"nota":nota,"original_alterado":False}



def auditar_capa_pdf(caminho_pdf: str, largura_final_in: float|None=None, altura_final_in: float|None=None, pasta_extraidas: str|None=None) -> dict:
    """Audita capa entregue como PDF/wrap, inclusive arquivos com múltiplas versões.

    O PPI continua conservador: usa a dimensão final informada apenas quando disponível.
    """
    base=auditar_pdf(caminho_pdf,pasta_extraidas)
    avaliacoes=[]
    for im in base.get("imagens",[]):
        w=im.get("largura_px",0) or 0; h=im.get("altura_px",0) or 0
        if largura_final_in and altura_final_in and w and h:
            ppi=min(w/largura_final_in,h/altura_final_in)
            status,nota=_status_ppi(ppi)
        else:
            ppi=im.get("ppi_estimado_full_page") or 0
            status,nota=(im.get("status","indeterminado"), im.get("nota",""))
        avaliacoes.append({**im,"ppi_capa_estimado":round(ppi,1) if ppi else None,"status_capa":status,"nota_capa":nota})
    ordem={"reprovada":3,"atencao":2,"indeterminado":1,"excelente":0}
    pior=max((x.get("status_capa","indeterminado") for x in avaliacoes),key=lambda x:ordem.get(x,1),default="indeterminado")
    return {
        "arquivo":caminho_pdf,"sha256":base.get("sha256"),"tipo":"pdf",
        "paginas_total":base.get("paginas_total",0),"paginas":base.get("paginas",[]),
        "imagens":avaliacoes,"tamanhos_pagina_in":base.get("tamanhos_pagina_in",[]),
        "largura_final_in":largura_final_in,"altura_final_in":altura_final_in,
        "status":pior,"multiplas_paginas":base.get("paginas_total",0)>1,
        "nota":"PDF de capa com múltiplas páginas detectado; trate páginas como versões/idiomas separados antes de escolher o Cover Master." if base.get("paginas_total",0)>1 else "Capa PDF auditada sem alterar o original.",
        "original_alterado":False,
    }

def gerar_relatorio(projeto: dict, miolo: dict|None=None, capa: dict|None=None) -> dict:
    alertas=[]
    if miolo:
        if not miolo.get("tamanho_uniforme"): alertas.append({"gravidade":"bloqueante","area":"diagramação","mensagem":"O PDF contém páginas com dimensões diferentes."})
        for im in miolo.get("imagens",[]):
            if im.get("status")=="reprovada": alertas.append({"gravidade":"atencao","area":"imagem","pagina":im.get("pagina"),"mensagem":f"Imagem incorporada com estimativa conservadora de {im.get('ppi_estimado_full_page')} PPI se usada em página inteira. Confirmar tamanho de colocação antes de corrigir."})
    if capa and capa.get("status")=="reprovada":
        ppi_capa=capa.get("ppi_efetivo")
        if ppi_capa is None and capa.get("imagens"):
            vals=[x.get("ppi_capa_estimado") for x in capa.get("imagens",[]) if x.get("ppi_capa_estimado")]
            ppi_capa=min(vals) if vals else None
        alertas.append({"gravidade":"bloqueante","area":"capa","mensagem":f"Capa com resolução abaixo do alvo no tamanho informado" + (f" ({ppi_capa} PPI estimados)." if ppi_capa else ".")})
    if capa and capa.get("multiplas_paginas"):
        alertas.append({"gravidade":"atencao","area":"capa","mensagem":"Arquivo de capa contém múltiplas páginas/versões. Escolha um Cover Master e preserve as demais como versões antes da exportação."})
    pendentes=["consistência visual de personagens","texto × imagem","ortografia e faixa etária","tradução/localização (quando aplicável)","bleed/safe area por inspeção de layout","comparação com Character DNA oficial"]
    if projeto.get("tipo_projeto") == "coloring":
        pendentes += ["espessura/uniformidade dos traços","preto e branco puro / cinzas residuais","áreas pequenas demais para a faixa etária","consistência de Style DNA","capa coerente com a line art"]
    elif projeto.get("tipo_projeto") == "activity":
        pendentes += ["dificuldade por faixa etária","clareza das instruções","gabaritos/soluções","uso consistente dos personagens"]
    rel={"projeto_id":projeto["id"],"titulo":projeto["titulo"],"gerado_em":int(time.time()),"tipo_projeto":projeto.get("tipo_projeto","story"),"status_publicacao":projeto.get("status_publicacao","em_desenvolvimento"),"colecao":projeto.get("colecao",""),"status_capa":projeto.get("status_capa","nao_informado"),"miolo":miolo,"capa":capa,"alertas":alertas,"revisoes_pendentes":pendentes,"politica":"O Book Doctor informa e sugere. Nenhum original é substituído e nenhuma correção é aplicada sem aprovação da autora."}
    path=Path(projeto["pasta"])/"relatorios"/"book_doctor_report.json"; path.write_text(json.dumps(rel,ensure_ascii=False,indent=2),encoding="utf-8")
    return rel


def listar_projetos() -> list[dict]:
    """Lista projetos Book Doctor locais para retomada no Restoration Studio."""
    if not ROOT.exists():
        return []
    itens=[]
    for pasta in ROOT.iterdir():
        if not pasta.is_dir():
            continue
        pj=pasta/"projeto.json"
        if not pj.exists():
            continue
        try:
            d=json.loads(pj.read_text(encoding="utf-8"))
            if isinstance(d,dict):
                itens.append(d)
        except Exception:
            continue
    return sorted(itens,key=lambda x:int(x.get("criado_em",0)),reverse=True)


def carregar_projeto(projeto_id: str) -> dict:
    for p in listar_projetos():
        if p.get("id")==projeto_id:
            return p
    return {}


def carregar_relatorio(projeto: dict) -> dict:
    path=Path(projeto.get("pasta", ""))/"relatorios"/"book_doctor_report.json"
    if not path.exists():
        return {}
    try:
        d=json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d,dict) else {}
    except Exception:
        return {}


def auditar_pdf_rapido(caminho_pdf: str, expected_reference: str = "") -> dict:
    """Triagem rápida compatível com o relatório do Book Doctor.

    Lê metadados dos XObjects sem decodificar/extrair todas as imagens. Ideal para
    PDFs grandes. Não produz ``arquivo_extraido``; para restauração visual, rode a
    auditoria completa apenas quando necessário.
    """
    from real_pilot import fast_pdf_audit
    raw = fast_pdf_audit(caminho_pdf, expected_reference=expected_reference)
    status_map = {"excellent": "excelente", "attention": "atencao", "low": "reprovada", "indeterminate": "indeterminado"}
    images = []
    per_page_index = {}
    for item in raw.get("images", []):
        page = int(item.get("page") or 0)
        per_page_index[page] = per_page_index.get(page, 0) + 1
        images.append({
            "pagina": page,
            "indice": per_page_index[page],
            "arquivo_extraido": "",
            "largura_px": int(item.get("width_px") or 0),
            "altura_px": int(item.get("height_px") or 0),
            "ppi_estimado_full_page": item.get("ppi_estimated_full_page"),
            "status": status_map.get(item.get("ppi_status"), "indeterminado"),
            "nota": "Estimativa conservadora por XObject; imagem não extraída no modo rápido.",
            "estimativa": True,
        })
    pages = []
    for p in raw.get("pages", []):
        page_no = int(p.get("page") or 0)
        pages.append({
            "pagina": page_no,
            "largura_in": p.get("width_in"),
            "altura_in": p.get("height_in"),
            "imagens": [x for x in images if x.get("pagina") == page_no],
            "fontes_recursos": [],
        })
    return {
        "arquivo": str(caminho_pdf),
        "sha256": raw.get("sha256"),
        "paginas_total": raw.get("pages_total", 0),
        "paginas": pages,
        "imagens": images,
        "tamanho_uniforme": bool(raw.get("uniform_page_size")),
        "tamanhos_pagina_in": raw.get("page_sizes_in", []),
        "observacao_ppi": raw.get("ppi_note", ""),
        "original_alterado": False,
        "modo_auditoria": "rapida",
        "analise_textual_piloto": {
            "adjacent_text_overlap": raw.get("adjacent_text_overlap", []),
            "repeated_bible_reference": raw.get("repeated_bible_reference", []),
            "blank_text_pages": raw.get("blank_text_pages", []),
        },
    }

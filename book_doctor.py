"""FaithBloom Book Doctor — auditoria conservadora de livros existentes.

Nunca altera o original. Extrai imagens incorporadas do PDF, mede páginas e
resolução e cria um relatório técnico. Avaliações sem evidência mensurável são
marcadas para revisão humana/IA posterior, em vez de inventar notas.

Projetos, manifests, relatórios e originais também são espelhados no backend
persistente do FaithBloom quando disponível (Supabase no Streamlit Cloud), para
que Book Doctor, Restoration Studio e Autopilot sobrevivam a reboot/redeploy.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
import uuid
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from storage_backend import BACKEND, backend_status, materializar, tenant_local_directory
from saas_access import AccessDenied, access_mode, require_action

ROOT = Path("book_doctor_projects")
STORAGE_PREFIX = "book_doctor_projects"


def _safe(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in (s or "livro")).strip("-") or "livro"


def _storage_prefix(project_id: str) -> str:
    if access_mode() == "multi_tenant" and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", project_id):
        raise AccessDenied("Identificador do projeto não autorizado.")
    return f"{STORAGE_PREFIX}/{project_id}"


def _project_folder_name(project: dict) -> str:
    if access_mode() == "multi_tenant":
        project_id = str(project.get("id") or "")
        _storage_prefix(project_id)
        # Stored filesystem paths/folder names are never ownership evidence.
        return project_id
    return str(project.get("storage_folder") or f"{_safe(project.get('titulo', 'livro'))}-{project.get('id', '')}")


def _local_root() -> Path:
    require_action("storage.read")
    return _checked_local(tenant_local_directory("cache") / STORAGE_PREFIX) if access_mode() == "multi_tenant" else ROOT


def _checked_local(path: Path) -> Path:
    if access_mode() == "multi_tenant":
        materializar(str(path))  # Authorization precedes any cache existence/read.
        if path.resolve() != path.absolute():
            raise AccessDenied("Caminho local do projeto não autorizado.")
    return path


def _local_project_dir(project: dict) -> Path:
    return _checked_local(_local_root() / _project_folder_name(project))


def _project_child(project: dict, relative_path: str) -> Path:
    if access_mode() == "pilot":
        return Path(project.get("pasta") or _local_project_dir(project)) / relative_path
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or "\\" in relative_path:
        raise AccessDenied("Caminho local do projeto não autorizado.")
    return _checked_local(_local_project_dir(project) / relative)


def _project_payload(project: dict) -> dict:
    payload = dict(project)
    payload["storage_folder"] = _project_folder_name(project)
    payload["storage_prefix"] = _storage_prefix(str(project.get("id") or ""))
    payload["storage_backend"] = backend_status().get("modo")
    # ``pasta`` é cache/runtime local; não pode ser tratada como endereço cloud.
    payload["pasta"] = str(_local_project_dir(payload))
    return payload


def _persist_json(project: dict, relative_path: str, value) -> None:
    try:
        BACKEND.put_json(f"{_storage_prefix(str(project.get('id') or ''))}/{relative_path.lstrip('/')}", value)
    except AccessDenied:
        raise
    except Exception:
        # Persistência cloud nunca deve corromper/interromper a cópia local já segura.
        pass


def _write_project_local(project: dict) -> dict:
    local = _local_project_dir(project)
    for sub in ("originais", "extraidas", "relatorios", "remastered", "planos"):
        _project_child({**project, "pasta": str(local)}, sub).mkdir(parents=True, exist_ok=True)
    hydrated = _project_payload({**project, "pasta": str(local)})
    _project_child({**project, "pasta": str(local)}, "projeto.json").write_text(json.dumps(hydrated, ensure_ascii=False, indent=2), encoding="utf-8")
    return hydrated


def _restore_json(project: dict, relative_path: str, local_path: Path):
    require_action("storage.read")
    if access_mode() == "multi_tenant":
        expected = _project_child(project, relative_path)
        _checked_local(Path(local_path))
        if Path(local_path).absolute() != expected.absolute():
            raise AccessDenied("Cache local do projeto não autorizado.")
        local_path = expected
    if local_path.exists():
        try:
            return json.loads(local_path.read_text(encoding="utf-8"))
        except AccessDenied:
            raise
        except Exception:
            pass
    try:
        value = BACKEND.get_json(f"{_storage_prefix(str(project.get('id') or ''))}/{relative_path.lstrip('/')}", None)
    except AccessDenied:
        raise
    except Exception:
        value = None
    if value is not None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return value


def _hydrate_originals(project: dict) -> None:
    """Baixa somente os originais do projeto selecionado quando o cache local sumiu."""
    manifest_path = _project_child(project, "originais/manifest.json")
    manifest = _restore_json(project, "originais/manifest.json", manifest_path)
    if not isinstance(manifest, list):
        return
    changed = False
    for entry in manifest:
        if not isinstance(entry, dict):
            continue
        storage_path = str(entry.get("storage_path") or "")
        current = Path(str(entry.get("arquivo") or "")) if entry.get("arquivo") else None
        filename = Path(storage_path).name if storage_path else Path(str(entry.get("arquivo") or "original.bin")).name
        local = _project_child(project, f"originais/{filename}")
        if access_mode() == "multi_tenant":
            current = local
            if entry.get("arquivo") != str(local):
                entry["arquivo"] = str(local)
                changed = True
        if current and current.exists():
            continue
        if storage_path:
            try:
                data = BACKEND.get_bytes(storage_path)
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(data)
                expected = str(entry.get("sha256") or "")
                if expected and sha256(str(local)) != expected:
                    local.unlink(missing_ok=True)
                    continue
                entry["arquivo"] = str(local)
                changed = True
            except AccessDenied:
                raise
            except Exception:
                continue
    if changed:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def criar_projeto(titulo: str, idioma: str="pt-BR", tipo_projeto: str="story", status_publicacao: str="em_desenvolvimento", colecao: str="", status_capa: str="nao_informado") -> dict:
    require_action("storage.write")
    pid = uuid.uuid4().hex[:12]
    obj = {
        "id": pid,
        "titulo": titulo,
        "idioma": idioma,
        "tipo_projeto": tipo_projeto,
        "status_publicacao": status_publicacao,
        "colecao": colecao,
        "status_capa": status_capa,
        "criado_em": int(time.time()),
        "status": "importado",
        "storage_folder": f"{_safe(titulo)}-{pid}",
    }
    obj = _write_project_local(obj)
    _persist_json(obj, "projeto.json", _project_payload(obj))
    return obj


def preservar_original(projeto: dict, arquivo: str, papel: str) -> str:
    require_action("storage.write")
    src = Path(materializar(arquivo))
    dst = _project_child(projeto, f"originais/{papel}_{src.name}")
    shutil.copy2(src, dst)
    digest = sha256(str(dst))
    storage_path = f"{_storage_prefix(str(projeto.get('id') or ''))}/originais/{dst.name}"
    try:
        BACKEND.put_bytes(storage_path, dst.read_bytes(), "application/pdf" if dst.suffix.lower() == ".pdf" else None)
    except AccessDenied:
        raise
    except Exception:
        storage_path = ""

    manifest_path = _project_child(projeto, "originais/manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    except AccessDenied:
        raise
    except Exception:
        manifest = []
    manifest.append({
        "papel": papel,
        "arquivo": str(dst),
        "sha256": digest,
        "preservado_em": int(time.time()),
        "storage_path": storage_path,
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _persist_json(projeto, "originais/manifest.json", manifest)
    return str(dst)


def sha256(caminho: str) -> str:
    caminho = materializar(caminho)
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def _status_ppi(ppi: float) -> tuple[str, str]:
    if ppi >= 300:
        return "excelente", "300 PPI ou mais"
    if ppi >= 200:
        return "atencao", "200–299 PPI"
    return "reprovada", "abaixo de 200 PPI"


def auditar_pdf(caminho_pdf: str, pasta_extraidas: str | None = None) -> dict:
    caminho_pdf = materializar(caminho_pdf)
    if pasta_extraidas:
        require_action("storage.write")
    reader = PdfReader(caminho_pdf)
    out = _checked_local(Path(pasta_extraidas)) if pasta_extraidas else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    paginas = []
    imagens = []
    for n, page in enumerate(reader.pages, 1):
        mb = page.mediabox
        w_in = float(mb.width) / 72
        h_in = float(mb.height) / 72
        fontes = []
        try:
            fd = (page.get("/Resources") or {}).get("/Font") or {}
            fontes = [str(k) for k in fd.keys()]
        except AccessDenied:
            raise
        except Exception:
            pass
        pimgs = []
        try:
            for i, imgobj in enumerate(page.images, 1):
                data = imgobj.data
                ext = Path(imgobj.name or "img.png").suffix or ".png"
                dest = out / f"pagina_{n:03d}_img_{i:02d}{ext}" if out else None
                if dest:
                    _checked_local(dest).write_bytes(data)
                try:
                    from io import BytesIO
                    with Image.open(BytesIO(data)) as im:
                        px = im.size
                except AccessDenied:
                    raise
                except Exception:
                    px = (0, 0)
                ppi = min(px[0] / w_in, px[1] / h_in) if px[0] and w_in and h_in else 0
                status, msg = _status_ppi(ppi) if ppi else ("indeterminado", "não foi possível medir")
                rec = {
                    "pagina": n, "indice": i, "arquivo_extraido": str(dest) if dest else "",
                    "largura_px": px[0], "altura_px": px[1],
                    "ppi_estimado_full_page": round(ppi, 1), "status": status,
                    "nota": msg, "estimativa": True,
                }
                pimgs.append(rec)
                imagens.append(rec)
        except AccessDenied:
            raise
        except Exception as exc:
            pimgs.append({"pagina": n, "status": "erro", "nota": str(exc)})
        paginas.append({
            "pagina": n, "largura_in": round(w_in, 4), "altura_in": round(h_in, 4),
            "imagens": pimgs, "fontes_recursos": fontes,
        })
    tamanhos = {(p["largura_in"], p["altura_in"]) for p in paginas}
    return {
        "arquivo": caminho_pdf, "sha256": sha256(caminho_pdf), "paginas_total": len(paginas),
        "paginas": paginas, "imagens": imagens, "tamanho_uniforme": len(tamanhos) <= 1,
        "tamanhos_pagina_in": sorted(list(tamanhos)),
        "observacao_ppi": "PPI de imagens extraídas é uma estimativa conservadora assumindo uso em página inteira; o PPI efetivo depende do tamanho de colocação no PDF.",
        "original_alterado": False,
    }


def auditar_imagem(caminho: str, largura_final_in: float | None = None, altura_final_in: float | None = None) -> dict:
    caminho = materializar(caminho)
    with Image.open(caminho) as im:
        w, h = im.size
        fmt = im.format
        mode = im.mode
    ppi = None
    status = "indeterminado"
    nota = "Informe o tamanho final de impressão para calcular PPI efetivo."
    if largura_final_in and altura_final_in:
        ppi = min(w / largura_final_in, h / altura_final_in)
        status, nota = _status_ppi(ppi)
    return {
        "arquivo": caminho, "sha256": sha256(caminho), "largura_px": w, "altura_px": h,
        "formato": fmt, "modo_cor": mode, "ppi_efetivo": round(ppi, 1) if ppi else None,
        "status": status, "nota": nota, "original_alterado": False,
    }


def auditar_capa_pdf(caminho_pdf: str, largura_final_in: float | None = None, altura_final_in: float | None = None, pasta_extraidas: str | None = None) -> dict:
    """Audita capa entregue como PDF/wrap, inclusive arquivos com múltiplas versões."""
    base = auditar_pdf(caminho_pdf, pasta_extraidas)
    avaliacoes = []
    for im in base.get("imagens", []):
        w = im.get("largura_px", 0) or 0
        h = im.get("altura_px", 0) or 0
        if largura_final_in and altura_final_in and w and h:
            ppi = min(w / largura_final_in, h / altura_final_in)
            status, nota = _status_ppi(ppi)
        else:
            ppi = im.get("ppi_estimado_full_page") or 0
            status, nota = im.get("status", "indeterminado"), im.get("nota", "")
        avaliacoes.append({**im, "ppi_capa_estimado": round(ppi, 1) if ppi else None, "status_capa": status, "nota_capa": nota})
    ordem = {"reprovada": 3, "atencao": 2, "indeterminado": 1, "excelente": 0}
    pior = max((x.get("status_capa", "indeterminado") for x in avaliacoes), key=lambda x: ordem.get(x, 1), default="indeterminado")
    return {
        "arquivo": caminho_pdf, "sha256": base.get("sha256"), "tipo": "pdf",
        "paginas_total": base.get("paginas_total", 0), "paginas": base.get("paginas", []),
        "imagens": avaliacoes, "tamanhos_pagina_in": base.get("tamanhos_pagina_in", []),
        "largura_final_in": largura_final_in, "altura_final_in": altura_final_in,
        "status": pior, "multiplas_paginas": base.get("paginas_total", 0) > 1,
        "nota": "PDF de capa com múltiplas páginas detectado; trate páginas como versões/idiomas separados antes de escolher o Cover Master." if base.get("paginas_total", 0) > 1 else "Capa PDF auditada sem alterar o original.",
        "original_alterado": False,
    }


def gerar_relatorio(projeto: dict, miolo: dict | None = None, capa: dict | None = None) -> dict:
    require_action("storage.write")
    alertas = []
    if miolo:
        if not miolo.get("tamanho_uniforme"):
            alertas.append({"gravidade": "bloqueante", "area": "diagramação", "mensagem": "O PDF contém páginas com dimensões diferentes."})
        for im in miolo.get("imagens", []):
            if im.get("status") == "reprovada":
                alertas.append({"gravidade": "atencao", "area": "imagem", "pagina": im.get("pagina"), "mensagem": f"Imagem incorporada com estimativa conservadora de {im.get('ppi_estimado_full_page')} PPI se usada em página inteira. Confirmar tamanho de colocação antes de corrigir."})
    if capa and capa.get("status") == "reprovada":
        ppi_capa = capa.get("ppi_efetivo")
        if ppi_capa is None and capa.get("imagens"):
            vals = [x.get("ppi_capa_estimado") for x in capa.get("imagens", []) if x.get("ppi_capa_estimado")]
            ppi_capa = min(vals) if vals else None
        alertas.append({"gravidade": "bloqueante", "area": "capa", "mensagem": "Capa com resolução abaixo do alvo no tamanho informado" + (f" ({ppi_capa} PPI estimados)." if ppi_capa else ".")})
    if capa and capa.get("multiplas_paginas"):
        alertas.append({"gravidade": "atencao", "area": "capa", "mensagem": "Arquivo de capa contém múltiplas páginas/versões. Escolha um Cover Master e preserve as demais como versões antes da exportação."})
    pendentes = [
        "consistência visual de personagens", "texto × imagem", "ortografia e faixa etária",
        "tradução/localização (quando aplicável)", "bleed/safe area por inspeção de layout",
        "comparação com Character DNA oficial",
    ]
    if projeto.get("tipo_projeto") == "coloring":
        pendentes += ["espessura/uniformidade dos traços", "preto e branco puro / cinzas residuais", "áreas pequenas demais para a faixa etária", "consistência de Style DNA", "capa coerente com a line art"]
    elif projeto.get("tipo_projeto") == "activity":
        pendentes += ["dificuldade por faixa etária", "clareza das instruções", "gabaritos/soluções", "uso consistente dos personagens"]
    rel = {
        "projeto_id": projeto["id"], "titulo": projeto["titulo"], "gerado_em": int(time.time()),
        "tipo_projeto": projeto.get("tipo_projeto", "story"),
        "status_publicacao": projeto.get("status_publicacao", "em_desenvolvimento"),
        "colecao": projeto.get("colecao", ""), "status_capa": projeto.get("status_capa", "nao_informado"),
        "miolo": miolo, "capa": capa, "alertas": alertas, "revisoes_pendentes": pendentes,
        "politica": "O Book Doctor informa e sugere. Nenhum original é substituído e nenhuma correção é aplicada sem aprovação da autora.",
    }
    path = _project_child(projeto, "relatorios/book_doctor_report.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    _persist_json(projeto, "relatorios/book_doctor_report.json", rel)
    _persist_json(projeto, "projeto.json", _project_payload(projeto))
    return rel


def listar_projetos() -> list[dict]:
    """Lista cache local + projetos persistidos no backend e reidrata metadados."""
    require_action("storage.list")
    itens: dict[str, dict] = {}
    root = _local_root()
    if root.exists():
        for pasta in root.iterdir():
            _checked_local(pasta)
            if not pasta.is_dir():
                continue
            pj = _checked_local(pasta / "projeto.json")
            if not pj.exists():
                continue
            try:
                d = json.loads(pj.read_text(encoding="utf-8"))
                if isinstance(d, dict) and d.get("id"):
                    if access_mode() == "multi_tenant":
                        if _local_project_dir(d) != pasta:
                            raise AccessDenied("Cache local do projeto não autorizado.")
                        d = _project_payload(d)
                    d["pasta"] = str(pasta)
                    itens[str(d["id"])] = d
            except AccessDenied:
                raise
            except Exception:
                continue
    try:
        cloud_paths = [x for x in BACKEND.list(STORAGE_PREFIX) if x.endswith("/projeto.json")]
    except AccessDenied:
        raise
    except Exception:
        cloud_paths = []
    for storage_path in cloud_paths:
        try:
            d = BACKEND.get_json(storage_path, None)
        except AccessDenied:
            raise
        except Exception:
            d = None
        if not isinstance(d, dict) or not d.get("id"):
            continue
        hydrated = _write_project_local(d)
        itens[str(hydrated["id"])] = hydrated
    return sorted(itens.values(), key=lambda x: int(x.get("criado_em", 0)), reverse=True)


def carregar_projeto(projeto_id: str) -> dict:
    for p in listar_projetos():
        if p.get("id") == projeto_id:
            return p
    return {}


def carregar_relatorio(projeto: dict) -> dict:
    projeto = _write_project_local(projeto)
    path = _project_child(projeto, "relatorios/book_doctor_report.json")
    data = _restore_json(projeto, "relatorios/book_doctor_report.json", path)
    # O download grande acontece apenas quando o projeto é efetivamente selecionado.
    _hydrate_originals(projeto)
    return data if isinstance(data, dict) else {}


def auditar_pdf_rapido(caminho_pdf: str, expected_reference: str = "") -> dict:
    """Triagem rápida compatível com o relatório do Book Doctor.

    Lê metadados dos XObjects sem decodificar/extrair todas as imagens. Ideal para
    PDFs grandes. Não produz ``arquivo_extraido``; para restauração visual, rode a
    auditoria completa apenas quando necessário.
    """
    from real_pilot import fast_pdf_audit
    raw = fast_pdf_audit(materializar(caminho_pdf), expected_reference=expected_reference)
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

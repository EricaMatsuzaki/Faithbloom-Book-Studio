"""FaithBloom Fase 15 — pacote comercial/editorial de publicação.

Centraliza metadados, disclosure de IA, readiness e exportação de um pacote
organizado para upload manual em plataformas como Amazon KDP.
"""
from __future__ import annotations
import json, os, shutil, zipfile
from pathlib import Path
from datetime import datetime
from author_profiles import author_display_from_state, publishing_contributors, authorship_summary


def normalizar_metadata(state: dict) -> dict:
    return {
        "idioma": state.get("idioma_original", "pt-BR"),
        "titulo": state.get("titulo", ""),
        "subtitulo": state.get("subtitulo", ""),
        "serie_colecao": state.get("colecao", ""),
        "autora": author_display_from_state(state),
        "autores": [x for x in publishing_contributors(state) if x.get("role") in {"author", "coauthor"}],
        "colaboradores": [x for x in publishing_contributors(state) if x.get("role") not in {"author", "coauthor"}],
        "descricao_kdp": state.get("sinopse_vendas_curta", ""),
        "faixa_etaria": state.get("faixa_etaria", "3–8 anos"),
        "palavras_chave": list(state.get("palavras_chave_kdp") or [])[:7],
        "categorias": list(state.get("categorias_sugeridas") or [])[:3],
        "versiculo_referencia": state.get("versiculo_referencia", ""),
        "tema": state.get("aprendizado_cristao", ""),
    }


def checklist_publicacao(state: dict) -> dict:
    md = normalizar_metadata(state)
    checks = {
        "titulo": bool(md["titulo"].strip()),
        "autora": bool(md["autora"].strip()),
        "descricao": bool(md["descricao_kdp"].strip()) and len(md["descricao_kdp"]) <= 4000,
        "keywords_1a7": 1 <= len(md["palavras_chave"]) <= 7,
        "categorias_ate3": 1 <= len(md["categorias"]) <= 3,
        "pdf_miolo": bool(state.get("pdf_miolo") or state.get("pdf_miolo_print_ready")),
        "capa_fisica_pdf": bool(state.get("capa_fisica_pdf")),
        "preflight_sem_bloqueios": not bool((state.get("preflight_impressao") or {}).get("bloqueios")),
        "revisao_aprovada": bool(state.get("revisao_aprovada")),
    }
    obrigatorios = ["titulo","autora","descricao","keywords_1a7","categorias_ate3","pdf_miolo","capa_fisica_pdf","preflight_sem_bloqueios","revisao_aprovada"]
    return {"checks": checks, "pronto": all(checks[k] for k in obrigatorios), "pendencias": [k for k in obrigatorios if not checks[k]]}


def disclosure_ia(state: dict) -> dict:
    """Registro editorial; a confirmação final é sempre humana."""
    d = dict(state.get("disclosure_ia") or {})
    return {
        "texto_gerado_ia": bool(d.get("texto_gerado_ia", False)),
        "imagens_geradas_ia": bool(d.get("imagens_geradas_ia", bool(state.get("cenas_imagem")))),
        "traducoes_geradas_ia": bool(d.get("traducoes_geradas_ia", bool(state.get("traducoes")))),
        "revisado_pela_autora": bool(d.get("revisado_pela_autora", False)),
        "observacoes": d.get("observacoes", ""),
    }


def _copiar_se_existe(src: str, dst: Path) -> str | None:
    if src and os.path.exists(src):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return str(dst)
    return None


def gerar_pacote_publicacao(state: dict, pasta_base: str = "saida_publicacao") -> dict:
    slug = "-".join((state.get("titulo") or "livro").lower().replace("_"," ").split())[:70]
    root = Path(pasta_base) / slug
    if root.exists(): shutil.rmtree(root)
    (root / "01_KDP_PRINT").mkdir(parents=True)
    (root / "02_METADATA").mkdir(parents=True)
    (root / "03_MARKETING").mkdir(parents=True)
    (root / "04_REGISTROS").mkdir(parents=True)

    miolo = state.get("pdf_miolo") or state.get("pdf_miolo_print_ready") or ""
    capa = state.get("capa_fisica_pdf") or ""
    _copiar_se_existe(miolo, root / "01_KDP_PRINT" / "miolo_print_ready.pdf")
    _copiar_se_existe(capa, root / "01_KDP_PRINT" / "capa_paperback.pdf")
    if state.get("capa_ebook"):
        _copiar_se_existe(state.get("capa_ebook",""), root / "01_KDP_PRINT" / ("capa_ebook" + Path(state.get("capa_ebook","")).suffix))

    md = normalizar_metadata(state)
    disc = disclosure_ia(state)
    check = checklist_publicacao(state)
    (root / "02_METADATA" / "metadata_kdp.json").write_text(json.dumps(md, ensure_ascii=False, indent=2), encoding="utf-8")
    txt = [f"TÍTULO: {md['titulo']}", f"SUBTÍTULO: {md['subtitulo']}", f"AUTORA: {md['autora']}", f"COLEÇÃO/SÉRIE: {md['serie_colecao']}", "", "DESCRIÇÃO KDP:", md['descricao_kdp'], "", "PALAVRAS-CHAVE:"]
    txt += [f"{i}. {x}" for i,x in enumerate(md['palavras_chave'],1)]
    txt += ["", "CATEGORIAS:"] + [f"{i}. {x}" for i,x in enumerate(md['categorias'],1)]
    (root / "02_METADATA" / "copiar_e_colar_kdp.txt").write_text("\n".join(txt), encoding="utf-8")
    (root / "03_MARKETING" / "material_lancamento.json").write_text(json.dumps(state.get("material_lancamento") or {}, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "04_REGISTROS" / "disclosure_ia.json").write_text(json.dumps(disc, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "04_REGISTROS" / "checklist_publicacao.json").write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "04_REGISTROS" / "gerado_em.txt").write_text(datetime.now().isoformat(), encoding="utf-8")

    zip_path = root.with_suffix(".zip")
    if zip_path.exists(): zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if p.is_file(): z.write(p, p.relative_to(root.parent))
    return {"pasta": str(root), "zip": str(zip_path), "checklist": check, "metadata": md, "disclosure_ia": disc}

# ---------------------------------------------------------------------------
# Refinamento 07 — pacote multicanal. Mantém o gerador KDP legado intacto.
# ---------------------------------------------------------------------------

def gerar_manifesto_multiplataforma(state: dict, targets: list[dict]) -> dict:
    """Cria um manifesto de destino sem afirmar que arquivos ausentes estão prontos."""
    from platform_format_engine import normalizar_master, build_derivative_plan, preflight_target
    master = normalizar_master({
        "title": state.get("titulo", ""),
        "language": state.get("idioma_original", "pt-BR"),
        "trim_width_in": state.get("trim_largura_in", state.get("trim_width_in", 8.5)),
        "trim_height_in": state.get("trim_altura_in", state.get("trim_height_in", 8.5)),
        "page_count": state.get("paginas_fisicas", state.get("paginas_minimas", 32)),
        "interior": state.get("interior_publicacao", "premium_color"),
        "binding": state.get("binding", "paperback"),
        "bleed": state.get("usar_bleed", True),
        "target_ppi": state.get("target_ppi", 300),
        "kdp_select_active": state.get("kdp_select_active", False),
        "isbn_mode": state.get("isbn_mode", "platform"),
        "isbn": state.get("isbn", ""),
    })
    assets = {
        "interior_pdf": state.get("pdf_miolo_print_ready") or state.get("pdf_miolo"),
        "cover_pdf": state.get("capa_fisica_pdf"),
        "epub": state.get("epub") or state.get("ebook_epub"),
        "epubcheck_passed": bool(state.get("epubcheck_passed")),
        "digital_file": state.get("digital_file"),
    }
    plan = build_derivative_plan(master, targets)
    checks = [preflight_target(master, t["platform_id"], t.get("product") or master["binding"], assets) for t in targets]
    return {
        "generated_at": datetime.now().isoformat(),
        "master": master,
        "targets": targets,
        "plan": plan,
        "preflight": checks,
        "ready_count": sum(1 for x in checks if x["ready"]),
        "blocked_count": sum(1 for x in checks if not x["ready"]),
    }


def gerar_pacote_multiplataforma(state: dict, targets: list[dict], pasta_base: str = "saida_publicacao_multicanal") -> dict:
    """Empacota os assets já existentes + manifesto por plataforma.

    Não converte um PDF em eBook silenciosamente e não fabrica capas de outras
    plataformas. Quando um asset falta, o manifesto/preflight registra bloqueio.
    """
    manifesto = gerar_manifesto_multiplataforma(state, targets)
    slug = "-".join((state.get("titulo") or "livro").lower().replace("_", " ").split())[:70]
    root = Path(pasta_base) / slug
    if root.exists():
        shutil.rmtree(root)
    (root / "00_MASTER").mkdir(parents=True)
    (root / "01_TARGETS").mkdir(parents=True)
    (root / "02_METADATA").mkdir(parents=True)
    (root / "03_REGISTROS").mkdir(parents=True)

    # Assets mestres são copiados uma única vez. Derivados específicos só entram
    # quando já existem no state; a plataforma nunca recebe um arquivo incompatível
    # por simples renomeação.
    _copiar_se_existe(state.get("pdf_miolo_print_ready") or state.get("pdf_miolo") or "", root / "00_MASTER" / "interior_master.pdf")
    _copiar_se_existe(state.get("capa_fisica_pdf") or "", root / "00_MASTER" / "cover_master_print.pdf")
    epub = state.get("epub") or state.get("ebook_epub") or ""
    if epub:
        _copiar_se_existe(epub, root / "00_MASTER" / "ebook_master.epub")

    for target, check in zip(targets, manifesto["preflight"]):
        name = f"{target['platform_id']}__{target.get('product','edition')}"
        folder = root / "01_TARGETS" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "preflight.json").write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "README.txt").write_text(
            "FaithBloom Platform Package\n"
            f"Plataforma: {check['platform_name']}\nProduto: {check['product']}\n"
            f"Status: {'PRONTO PARA REVISÃO FINAL' if check['ready'] else 'BLOQUEADO/PENDENTE'}\n\n"
            "Este diretório não substitui o preview/template oficial da plataforma.\n",
            encoding="utf-8",
        )

    (root / "02_METADATA" / "metadata_master.json").write_text(json.dumps(normalizar_metadata(state), ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "03_REGISTROS" / "manifesto_multiplataforma.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "03_REGISTROS" / "disclosure_ia.json").write_text(json.dumps(disclosure_ia(state), ensure_ascii=False, indent=2), encoding="utf-8")

    zip_path = root.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(root.parent))
    return {"pasta": str(root), "zip": str(zip_path), "manifesto": manifesto}

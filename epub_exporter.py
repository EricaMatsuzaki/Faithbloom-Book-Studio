"""Exportador EPUB 3 mínimo do FaithBloom.

Gera:
- EPUB reflowable para textos corridos;
- EPUB fixed-layout para livros infantis ilustrados quando cada cena/página
  precisa manter composição visual.

O exportador não substitui EPUBCheck. Para Apple Books, o Platform Engine
mantém EPUBCheck como bloqueio externo obrigatório antes da publicação.
"""
from __future__ import annotations
from author_profiles import author_display_from_state

import html
import mimetypes
import os
import re
import uuid
import zipfile
from pathlib import Path


def _slug(value: str) -> str:
    x = re.sub(r"[^a-zA-Z0-9_-]+", "-", value or "book").strip("-").lower()
    return x or "book"


def _x(value: str) -> str:
    return html.escape(str(value or ""), quote=True)


def _image_items(images: list[dict], root: Path) -> tuple[list[dict], dict[int, str]]:
    items, by_scene = [], {}
    for i, item in enumerate(images or [], 1):
        src = str(item.get("arquivo") or item.get("caminho") or item.get("path") or "")
        if not src or not os.path.exists(src):
            continue
        ext = Path(src).suffix.lower() or ".jpg"
        name = f"images/img_{i:03d}{ext}"
        media = mimetypes.guess_type(name)[0] or "image/jpeg"
        scene = item.get("numero", item.get("cena_numero", i))
        try:
            by_scene[int(scene)] = name
        except Exception:
            pass
        items.append({"id": f"img{i}", "href": name, "media": media, "src": src})
    return items, by_scene


def _cover_item(path: str | None) -> dict | None:
    if not path or not os.path.exists(path):
        return None
    ext = Path(path).suffix.lower() or ".jpg"
    return {"id": "cover-image", "href": f"images/cover{ext}", "media": mimetypes.guess_type(path)[0] or "image/jpeg", "src": path}


def _fixed_page(scene: dict, image_href: str | None, width: int, height: int, lang: str) -> str:
    text = _x(scene.get("texto", "")).replace("\n", "<br/>")
    img = f'<img class="art" src="{_x(image_href)}" alt=""/>' if image_href else '<div class="placeholder"></div>'
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="{_x(lang)}" xml:lang="{_x(lang)}">
<head><title>{_x(scene.get('numero',''))}</title><meta name="viewport" content="width={width}, height={height}"/><link rel="stylesheet" type="text/css" href="styles.css"/></head>
<body class="fixed"><div class="page">{img}<div class="text-panel"><p>{text}</p></div></div></body></html>'''


def _reflow_body(title: str, scenes: list[dict], lesson: str, verse_reference: str) -> str:
    parts = [f"<h1>{_x(title)}</h1>"]
    for scene in scenes:
        parts.append(f"<section><p>{_x(scene.get('texto','')).replace(chr(10), '<br/>')}</p></section>")
    if lesson:
        parts.append(f"<section><h2>O que aprendemos</h2><p>{_x(lesson)}</p></section>")
    if verse_reference:
        parts.append(f"<section><h2>Referência bíblica</h2><p>{_x(verse_reference)}</p></section>")
    return "\n".join(parts)


def export_epub(
    state: dict,
    output_path: str,
    *,
    mode: str = "fixed",
    language: str | None = None,
    cover_path: str | None = None,
    page_width_px: int = 1600,
    page_height_px: int = 1600,
) -> dict:
    """Gera um EPUB 3 básico e retorna manifesto de exportação.

    ``mode``: ``fixed`` ou ``reflowable``.
    O texto bíblico completo não é injetado automaticamente; somente a
    referência já presente no state é exportada por padrão.
    """
    if mode not in {"fixed", "reflowable"}:
        raise ValueError("mode precisa ser fixed ou reflowable")
    title = state.get("titulo", "Livro sem título")
    author = author_display_from_state(state)
    lang = language or state.get("idioma_original", "pt-BR")
    scenes = list(state.get("cenas_texto") or [])
    images, by_scene = _image_items(list(state.get("cenas_imagem") or []), Path(output_path).parent)
    cover = _cover_item(cover_path or state.get("capa_ebook"))
    uid = str(state.get("isbn") or state.get("book_id") or uuid.uuid4())
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    manifest = [
        ('nav', 'nav.xhtml', 'application/xhtml+xml', ' properties="nav"'),
        ('css', 'styles.css', 'text/css', ''),
    ]
    spine = []
    xhtml_files: dict[str, str] = {}

    if mode == "fixed":
        for idx, scene in enumerate(scenes, 1):
            sid = f"p{idx:03d}"
            href = f"page_{idx:03d}.xhtml"
            try:
                scene_num = int(scene.get("numero", idx))
            except Exception:
                scene_num = idx
            xhtml_files[href] = _fixed_page(scene, by_scene.get(scene_num), page_width_px, page_height_px, lang)
            manifest.append((sid, href, 'application/xhtml+xml', ''))
            spine.append(sid)
    else:
        href = "book.xhtml"
        body = _reflow_body(title, scenes, state.get("licao_final", ""), state.get("versiculo_referencia", ""))
        xhtml_files[href] = f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="{_x(lang)}" xml:lang="{_x(lang)}"><head><title>{_x(title)}</title><link rel="stylesheet" type="text/css" href="styles.css"/></head><body class="reflow">{body}</body></html>'''
        manifest.append(("book", href, "application/xhtml+xml", ""))
        spine.append("book")

    for item in images:
        manifest.append((item["id"], item["href"], item["media"], ""))
    if cover:
        manifest.append((cover["id"], cover["href"], cover["media"], ' properties="cover-image"'))

    nav_items = "".join(f'<li><a href="{href}">Página {i}</a></li>' for i, href in enumerate(xhtml_files, 1))
    nav = f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{_x(lang)}"><head><title>Sumário</title></head><body><nav epub:type="toc"><h1>Sumário</h1><ol>{nav_items}</ol></nav></body></html>'''

    css = '''html,body{margin:0;padding:0;} body{font-family:serif;color:#26332e;} .fixed{overflow:hidden;} .page{position:relative;width:100vw;height:100vh;background:#fff;} .art{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;} .placeholder{position:absolute;inset:0;background:#f5f3ee;} .text-panel{position:absolute;left:8%;right:8%;bottom:6%;padding:2.5%;background:rgba(255,255,255,.88);border-radius:18px;font-size:4.2vw;line-height:1.35;} .text-panel p{margin:0;} .reflow{max-width:42em;margin:0 auto;padding:5%;font-size:1.05em;line-height:1.55;} .reflow section{margin:1.4em 0;}'''

    manifest_xml = "\n".join(f'<item id="{i}" href="{h}" media-type="{m}"{props}/>' for i,h,m,props in manifest)
    spine_xml = "\n".join(f'<itemref idref="{sid}"/>' for sid in spine)
    rendition = '<meta property="rendition:layout">pre-paginated</meta><meta property="rendition:orientation">auto</meta><meta property="rendition:spread">auto</meta>' if mode == "fixed" else '<meta property="rendition:layout">reflowable</meta>'
    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" prefix="rendition: http://www.idpf.org/vocab/rendition/#">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">{_x(uid)}</dc:identifier><dc:title>{_x(title)}</dc:title><dc:creator>{_x(author)}</dc:creator><dc:language>{_x(lang)}</dc:language>{rendition}<meta property="dcterms:modified">2026-09-03T00:00:00Z</meta></metadata>
<manifest>{manifest_xml}</manifest><spine>{spine_xml}</spine></package>'''

    container = '''<?xml version="1.0" encoding="UTF-8"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'''

    with zipfile.ZipFile(out, "w") as z:
        # Regra EPUB: mimetype precisa ser o primeiro item e sem compressão.
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("EPUB/package.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("EPUB/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("EPUB/styles.css", css, compress_type=zipfile.ZIP_DEFLATED)
        for href, content in xhtml_files.items():
            z.writestr(f"EPUB/{href}", content, compress_type=zipfile.ZIP_DEFLATED)
        for item in images + ([cover] if cover else []):
            z.write(item["src"], f"EPUB/{item['href']}", compress_type=zipfile.ZIP_DEFLATED)

    return {
        "path": str(out),
        "mode": mode,
        "language": lang,
        "pages": len(xhtml_files),
        "images": len(images),
        "cover_included": bool(cover),
        "bible_policy": "reference_only_unless_author_supplies_approved_text",
        "epubcheck_passed": False,
        "warning": "Arquivo gerado; executar EPUBCheck e o preview da plataforma antes da publicação final.",
    }


def inspect_epub(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {"ok": False, "errors": ["Arquivo EPUB não encontrado."]}
    errors = []
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if not names or names[0] != "mimetype":
                errors.append("mimetype não é o primeiro item do EPUB.")
            required = {"mimetype", "META-INF/container.xml", "EPUB/package.opf", "EPUB/nav.xhtml"}
            missing = sorted(required - set(names))
            if missing:
                errors.append("Arquivos obrigatórios ausentes: " + ", ".join(missing))
            try:
                mt = z.read("mimetype").decode("ascii")
                if mt != "application/epub+zip":
                    errors.append("mimetype inválido.")
            except Exception:
                errors.append("Não foi possível ler mimetype.")
    except Exception as exc:
        errors.append(f"EPUB inválido: {type(exc).__name__}: {exc}")
    return {"ok": not errors, "errors": errors, "epubcheck_passed": False}

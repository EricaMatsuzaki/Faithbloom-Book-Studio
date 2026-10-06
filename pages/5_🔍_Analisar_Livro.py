"""
Analisar Livro + entrada textual segura para Revisão Completa.

Além de visualizar livros já salvos, esta página recebe do Jarvis um manuscrito
colado em texto e o transforma em um PDF técnico derivado, somente para permitir
que o pipeline canônico Book Doctor -> Autopilot trabalhe sem exigir que a autora
salve e reenvie um arquivo manualmente. O texto original da conversa continua
preservado no histórico da sessão; nenhuma versão vira Master automaticamente.
"""

from __future__ import annotations

import re
import tempfile
import textwrap
from pathlib import Path

import streamlit as st

from estilo import aplicar_estilo, hero
from armazenamento import listar_livros, carregar_livro
from book_doctor import criar_projeto, preservar_original, auditar_pdf_rapido, gerar_relatorio

st.set_page_config(page_title="Analisar Livro", page_icon="🔍", layout="wide")
aplicar_estilo()
hero("🔍 Analisar Livro", "Veja livros salvos ou envie um texto-base do Jarvis para Revisão Completa.")

FULL_REVIEW_HINTS = (
    "revisão completa", "revisao completa", "full editorial remaster",
    "full editorial review", "revisar completamente", "edição revisada",
    "edicao revisada", "remaster editorial", "autopilot editorial remaster",
)


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold()).strip()


def _latest_jarvis_full_review_text() -> str:
    """Recupera o texto cru mais recente, preservando quebras de linha da autora."""
    history = list(st.session_state.get("jarvis_conversation_history") or [])
    for item in reversed(history):
        if item.get("role") != "user":
            continue
        raw = str(item.get("text") or "").strip()
        normalized = _norm(raw)
        if raw and any(hint in normalized for hint in FULL_REVIEW_HINTS):
            return raw
    fallback = str(st.session_state.get("jarvis_request") or "").strip()
    return fallback if any(hint in _norm(fallback) for hint in FULL_REVIEW_HINTS) else ""


def _infer_title(text: str) -> str:
    patterns = (
        r"(?im)^\s*(?:#+\s*)?(?:livro|t[ií]tulo)\s*:\s*(.+?)\s*$",
        r"(?im)^\s*##?\s*(quando\s+.+?)\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            candidate = re.sub(r"[*_#]+", "", match.group(1)).strip()
            if 3 <= len(candidate) <= 140:
                return candidate
    if "quando mel aprendeu a esperar" in _norm(text):
        return "Quando Mel Aprendeu a Esperar"
    return "Manuscrito para Revisão Completa"


def _infer_collection(text: str, title: str) -> str:
    match = re.search(r"(?im)^\s*(?:cole[cç][aã]o|universo)\s*:\s*(.+?)\s*$", text or "")
    if match:
        return re.sub(r"[*_#]+", "", match.group(1)).strip()[:140]
    if _norm(title) == "quando mel aprendeu a esperar":
        return "Pequenas Histórias, Grandes Lições"
    return ""


def _pdf_escape_line(value: str) -> bytes:
    raw = (value or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return raw.encode("cp1252", errors="replace")


def _paginate_text(text: str) -> list[list[str]]:
    """Pagina o manuscrito sem alterar suas palavras; só quebra linhas para o PDF técnico."""
    source_lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines: list[str] = []
    for source in source_lines:
        if not source.strip():
            lines.append("")
            continue
        wrapped = textwrap.wrap(
            source,
            width=92,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=False,
            break_on_hyphens=False,
        )
        lines.extend([x.rstrip() for x in wrapped] or [""])
    max_lines = 50
    pages = [lines[i:i + max_lines] for i in range(0, len(lines), max_lines)]
    return pages or [[""]]


def _build_text_pdf(text: str) -> bytes:
    """Cria PDF mínimo com texto extraível, sem dependência nova no runtime."""
    pages = _paginate_text(text)
    objects: dict[int, bytes] = {}
    page_ids = [4 + (i * 2) for i in range(len(pages))]
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = b" ".join(f"{pid} 0 R".encode("ascii") for pid in page_ids)
    objects[2] = b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_ids)).encode("ascii") + b" >>"
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"

    for index, page_lines in enumerate(pages):
        page_id = 4 + (index * 2)
        content_id = page_id + 1
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        stream = bytearray(b"BT\n/F1 9 Tf\n46 754 Td\n12 TL\n")
        for line in page_lines:
            stream += b"(" + _pdf_escape_line(line) + b") Tj\nT*\n"
        stream += b"ET\n"
        objects[content_id] = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + bytes(stream) + b"endstream"

    highest = max(objects)
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (highest + 1)
    for obj_id in range(1, highest + 1):
        offsets[obj_id] = len(output)
        output += f"{obj_id} 0 obj\n".encode("ascii")
        output += objects[obj_id] + b"\nendobj\n"
    xref = len(output)
    output += f"xref\n0 {highest + 1}\n".encode("ascii")
    output += b"0000000000 65535 f \n"
    for obj_id in range(1, highest + 1):
        output += f"{offsets[obj_id]:010d} 00000 n \n".encode("ascii")
    output += (
        f"trailer\n<< /Size {highest + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode("ascii")
    return bytes(output)


jarvis_text = _latest_jarvis_full_review_text()
if jarvis_text:
    st.success("🤖 Jarvis reconheceu um pedido de Revisão Completa em texto. Você não precisa transformar o manuscrito em arquivo manualmente.")
    st.caption(
        "O FaithBloom preservará uma representação PDF técnica desse texto como entrada imutável do projeto e seguirá pelo pipeline canônico de revisão."
    )
    default_title = _infer_title(jarvis_text)
    default_collection = _infer_collection(jarvis_text, default_title)
    with st.form("jarvis_text_full_review"):
        c1, c2 = st.columns(2)
        title = c1.text_input("Título", value=default_title)
        collection = c2.text_input("Coleção / universo", value=default_collection)
        language = st.selectbox("Idioma", ["pt-BR", "en-US", "es", "ja-JP", "fr", "it", "de", "Outro"], index=0)
        manuscript = st.text_area(
            "Texto-base recebido do Jarvis",
            value=jarvis_text,
            height=320,
            help="Você pode conferir o texto antes de iniciar. Nenhuma alteração é aplicada ao original neste campo.",
        )
        start_full_review = st.form_submit_button(
            "✨ Iniciar Revisão Completa deste texto",
            type="primary",
            use_container_width=True,
        )

    if start_full_review:
        if not manuscript.strip():
            st.error("O texto-base está vazio.")
        else:
            try:
                with st.spinner("Preservando o texto-base e preparando o Autopilot…"):
                    project = criar_projeto(
                        title.strip() or "Manuscrito para Revisão Completa",
                        language,
                        tipo_projeto="story",
                        status_publicacao="em_desenvolvimento",
                        colecao=collection.strip(),
                        status_capa="sem_capa",
                    )
                    with tempfile.TemporaryDirectory(prefix="faithbloom_jarvis_text_") as tmpdir:
                        source_pdf = Path(tmpdir) / "texto_base_jarvis.pdf"
                        source_pdf.write_bytes(_build_text_pdf(manuscript))
                        preserved = preservar_original(project, str(source_pdf), "miolo")
                        audit = auditar_pdf_rapido(preserved)
                    report = gerar_relatorio(project, audit, None)
                    st.session_state["book_doctor_report"] = report
                    st.session_state["book_doctor_project"] = project
                    st.session_state["autopilot_book_doctor_project_id"] = project.get("id")
                    st.session_state["autopilot_jarvis_request"] = manuscript
                    st.session_state.pop("jarvis_suggested_destination", None)
                    st.session_state["jarvis_text_intake_project_id"] = project.get("id")
                st.switch_page("pages/52_✨_Autopilot_Editorial_Remaster.py")
            except Exception as exc:
                st.error("Não foi possível preparar a Revisão Completa do texto enviado pelo Jarvis.")
                st.exception(exc)

    st.divider()

livros = listar_livros()
if not livros:
    if not jarvis_text:
        st.info("Nenhum livro salvo ainda.")
    st.stop()

st.subheader("📚 Livros já salvos")
opcoes = {f"{l['titulo']} ({l['colecao']})": l for l in livros}
escolha = st.selectbox("Livro", list(opcoes.keys()))
livro_info = opcoes[escolha]
s = carregar_livro(livro_info["colecao"], livro_info["arquivo"])

st.header(s.get("titulo", ""))
st.caption(f"Coleção: {s.get('colecao', '')} • Emoção central: {s.get('emocao_central', '')} • "
           f"Versículo: {s.get('versiculo_referencia', '')}")

aba_texto, aba_personagens, aba_extra, aba_lancamento, aba_kdp = st.tabs(
    ["📝 Texto", "👤 Personagens", "💐 Dedicatória / Sinopse / Traduções", "🚀 Lançamento", "✅ Checklist KDP"]
)

with aba_texto:
    st.subheader("Sinopse poética")
    st.write(s.get("sinopse_poetica", "(ainda não gerada)"))

    st.subheader("Cenas")
    for cena in s.get("cenas_texto", []):
        with st.expander(f"Cena {cena['numero']} — emoção: {cena.get('emocao', '')}"):
            st.write(cena.get("texto", ""))
            st.caption(f"Figurino: {cena.get('figurino', '')} • Contexto: {cena.get('contexto_visual', '')}")
            img = next((c for c in s.get("cenas_imagem", []) if c["numero"] == cena["numero"]), None)
            if img:
                st.image(img["caminho_arquivo"])

    st.subheader("Lição final")
    st.write(s.get("licao_final", "(ainda não gerada)"))

with aba_personagens:
    for nome, p in s.get("personagens", {}).items():
        col1, col2 = st.columns([1, 2])
        if p.get("imagem_referencia"):
            col1.image(p["imagem_referencia"], width=200)
        col2.markdown(f"**{nome}** ({p.get('papel', '')})")
        col2.write(p.get("descricao_fixa", ""))
        origem = "📤 imagem enviada pela autora" if p.get("origem_referencia") == "enviada_pela_autora" else "🤖 gerada pelo agente"
        col2.caption(origem)

with aba_extra:
    st.subheader("Dedicatória")
    st.write(s.get("dedicatoria_texto", "(não gerada)"))

    st.subheader("Sinopse de vendas (KDP)")
    st.write(s.get("sinopse_vendas_curta", "(não gerada)"))

    st.subheader("Sinopse de contracapa")
    st.write(s.get("sinopse_contracapa", "(não gerada)"))

    st.subheader("Traduções")
    for idioma, dados in s.get("traducoes", {}).items():
        with st.expander(idioma):
            st.json(dados)

with aba_lancamento:
    st.subheader("🔑 Palavras-chave (KDP)")
    for kw in s.get("palavras_chave_kdp", []):
        st.write(f"• {kw}")
    if not s.get("palavras_chave_kdp"):
        st.caption("(ainda não geradas — use a página 🚀 Lançamento)")

    st.subheader("📁 Categorias sugeridas")
    for cat in s.get("categorias_sugeridas", []):
        st.write(f"📁 {cat}")
    if not s.get("categorias_sugeridas"):
        st.caption("(ainda não geradas — use a página 🚀 Lançamento)")

    material = s.get("material_lancamento", {})
    if material:
        st.subheader("📣 Material de divulgação")
        for chave, rotulo in [
            ("legenda_instagram", "Instagram"), ("descricao_pinterest", "Pinterest"),
            ("email_lancamento", "E-mail"), ("pedido_avaliacao", "Pedido de avaliação"),
        ]:
            if material.get(chave):
                with st.expander(rotulo):
                    st.write(material[chave])
    else:
        st.caption("(ainda não gerado — use a página 🚀 Lançamento)")

with aba_kdp:
    st.json(s.get("checklist_kdp", {}))
    if s.get("capa_fisica_dimensoes"):
        st.subheader("Dimensões da capa física")
        st.json(s["capa_fisica_dimensoes"])

from __future__ import annotations

from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1]
PAGE_REF_RE = re.compile(r"pages/[^\"'\n]+\.py")


def _python_files() -> list[Path]:
    files = sorted(ROOT.glob("*.py"))
    files.extend(sorted((ROOT / "pages").glob("*.py")))
    return [p for p in files if p.exists()]


def _literal_page_refs(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    refs = set(PAGE_REF_RE.findall(text))
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return refs
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.strip()
            if value.startswith("pages/") and value.endswith(".py"):
                refs.add(value)
    return refs


def test_all_literal_page_navigation_targets_exist():
    missing: list[tuple[str, str]] = []
    for source in _python_files():
        for ref in sorted(_literal_page_refs(source)):
            if not (ROOT / ref).exists():
                missing.append((str(source.relative_to(ROOT)), ref))
    assert not missing, "Broken Streamlit page targets: " + "; ".join(
        f"{src} -> {ref}" for src, ref in missing
    )


def test_dashboard_primary_routes_exist():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    expected = {
        "pages/39_✍️_Historia_4_Estilos.py",
        "pages/16_🩺_Book_Doctor.py",
        "pages/3_🖍️_Livros_de_Colorir.py",
        "pages/23_🧩_Activity_Book_Studio.py",
        "pages/21_Translation_Localization_Studio.py",
        "pages/24_🎧_Audiobook_Studio.py",
        "pages/31_🖼️_Asset_Library_Media_Manager.py",
        "pages/25_🛡️_Quality_Guardian.py",
        "pages/26_🌐_Publishing_Distribution_Center.py",
        "pages/37_🧠_Agent_Skills_Bestseller_Readiness.py",
    }
    missing_in_app = sorted(x for x in expected if x not in app)
    missing_files = sorted(x for x in expected if not (ROOT / x).exists())
    assert not missing_in_app, f"Dashboard perdeu rotas primárias: {missing_in_app}"
    assert not missing_files, f"Dashboard aponta para páginas inexistentes: {missing_files}"


def test_no_accidental_home_href_in_pages():
    suspicious: list[str] = []
    for source in sorted((ROOT / "pages").glob("*.py")):
        text = source.read_text(encoding="utf-8")
        if re.search(r"href\s*=\s*['\"]/(?:['\"]|\?)", text):
            suspicious.append(str(source.relative_to(ROOT)))
    assert not suspicious, (
        "Found direct '/' hrefs inside pages; these can bounce users to the app home: "
        + ", ".join(suspicious)
    )

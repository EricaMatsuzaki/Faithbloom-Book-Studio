"""FaithBloom 2.0 — Fase 16: QA final e Release Candidate.

Executa verificações offline de release sem chamar modelos de IA e sem gastar
créditos. O objetivo é detectar regressões simples antes do deploy no Streamlit.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
RELEASE_VERSION = "2.0.0-rc5-skills"


@dataclass
class QAItem:
    nome: str
    ok: bool
    detalhe: str = ""
    nivel: str = "erro"  # erro | aviso | info

    def to_dict(self) -> dict:
        return asdict(self)


def _item(nome: str, ok: bool, detalhe: str = "", nivel: str = "erro") -> dict:
    return QAItem(nome, ok, detalhe, nivel).to_dict()


def arquivos_python() -> list[Path]:
    ignorar = {"__pycache__", ".git", ".venv", "venv"}
    return [p for p in ROOT.rglob("*.py") if not any(x in ignorar for x in p.parts)]


def verificar_sintaxe() -> list[dict]:
    erros = []
    total = 0
    for p in arquivos_python():
        total += 1
        try:
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except Exception as exc:
            erros.append(f"{p.relative_to(ROOT)}: {type(exc).__name__}: {exc}")
    return [_item("Sintaxe Python", not erros, f"{total} arquivos verificados" if not erros else "; ".join(erros[:8]))]


def verificar_requirements() -> list[dict]:
    req = ROOT / "requirements.txt"
    esperados = {"streamlit", "langgraph", "requests", "pillow", "reportlab", "pypdf"}
    if not req.exists():
        return [_item("requirements.txt", False, "Arquivo ausente")]
    linhas = {
        re.split(r"[<>=!~\[]", x.strip().lower(), maxsplit=1)[0]
        for x in req.read_text(encoding="utf-8").splitlines()
        if x.strip() and not x.lstrip().startswith("#")
    }
    faltam = sorted(esperados - linhas)
    return [_item("Dependências declaradas", not faltam, "OK" if not faltam else f"Faltam: {', '.join(faltam)}")]


def verificar_page_links() -> list[dict]:
    fontes = [ROOT / "app.py"] + list((ROOT / "pages").glob("*.py"))
    padrao = re.compile(r"(?:st\.page_link\(|card\([^\)]*?)(?:\n|.){0,500}?[\"'](pages/[^\"']+\.py)[\"']", re.MULTILINE)
    # captura direta de qualquer string pages/*.py; é mais robusto para cards multiline
    alvo_re = re.compile(r"[\"'](pages/[^\"']+\.py)[\"']")
    referencias = set()
    for f in fontes:
        if f.exists():
            referencias.update(alvo_re.findall(f.read_text(encoding="utf-8")))
    ausentes = sorted(x for x in referencias if not (ROOT / x).exists())
    return [_item("Navegação / page links", not ausentes, f"{len(referencias)} rotas verificadas" if not ausentes else f"Ausentes: {ausentes}")]


def verificar_segredos() -> list[dict]:
    """Procura padrões de segredo real; exemplos/nomes de variáveis não contam."""
    candidatos = []
    padroes = [
        re.compile(r"sk-or-v1-[A-Za-z0-9_-]{16,}"),
        re.compile(r"(?i)(?:api[_-]?key|service[_-]?role[_-]?key)\s*=\s*[\"'][^\"']{20,}[\"']"),
    ]
    ignorar_nomes = {"secrets.example.toml"}
    for p in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.toml")) + list(ROOT.rglob("*.md")):
        if p.name in ignorar_nomes or "__pycache__" in p.parts:
            continue
        try:
            texto = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in padroes:
            m = pat.search(texto)
            if m:
                achado = m.group(0).upper()
                # Placeholders de documentação não são segredos reais.
                if any(tok in achado for tok in ("SUA-CHAVE", "SEU_TOKEN", "YOUR_KEY", "EXAMPLE", "XXXX")):
                    continue
                candidatos.append(str(p.relative_to(ROOT)))
                break
    return [_item("Segredos no repositório", not candidatos, "Nenhum padrão de chave real detectado" if not candidatos else f"Revisar: {', '.join(candidatos[:8])}")]


def verificar_higiene_repo() -> list[dict]:
    pycache = list(ROOT.rglob("__pycache__"))
    pyc = list(ROOT.rglob("*.pyc"))
    logs_runtime = [p for p in (ROOT / ".faithbloom_data").rglob("*") if p.is_file() and p.name != ".gitkeep"] if (ROOT / ".faithbloom_data").exists() else []
    ok = not pycache and not pyc and not logs_runtime
    detalhe = "Sem caches/logs de execução empacotados" if ok else f"pycache={len(pycache)}, pyc={len(pyc)}, runtime_files={len(logs_runtime)}"
    return [_item("Higiene do pacote", ok, detalhe, "aviso" if not ok else "info")]


def verificar_natal() -> list[dict]:
    try:
        from integracao_e2e import diagnostico_natal
        d = diagnostico_natal()
        state = d.get("state") or {}
        detalhe = f"{len(state.get('cenas_texto', []))} cenas · {len(state.get('personagens', {}))} personagens"
        return [_item("Projeto piloto de Natal", bool(d.get("ok")), detalhe, "info" if d.get("ok") else "erro")]
    except Exception as exc:
        return [_item("Projeto piloto de Natal", False, f"{type(exc).__name__}: {exc}")]


def rodar_unit_tests() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    saida = (proc.stdout + "\n" + proc.stderr).strip()
    resumo = saida[-5000:]
    return {"ok": proc.returncode == 0, "returncode": proc.returncode, "saida": resumo}


def verificar_tests() -> list[dict]:
    try:
        r = rodar_unit_tests()
        linhas = [x.strip() for x in r["saida"].splitlines() if x.strip()]
        resumo = next((x for x in reversed(linhas) if "passed" in x or "failed" in x), "testes executados")
        return [_item("Testes automatizados", r["ok"], resumo if r["ok"] else r["saida"][-1200:])]
    except Exception as exc:
        return [_item("Testes automatizados", False, f"{type(exc).__name__}: {exc}")]


def verificar_stable_hardening() -> list[dict]:
    esperados = [ROOT / "stable_hardening.py", ROOT / "pages" / "28_🧱_Stable_Release_Hardening.py", ROOT / "tests" / "test_refinamento13.py"]
    faltam = [str(p.relative_to(ROOT)) for p in esperados if not p.exists()]
    return [_item("Stable Release Hardening", not faltam, "Schema/recovery/access/gate presentes" if not faltam else f"Faltam: {faltam}")]


def verificar_production_deployment() -> list[dict]:
    esperados = [ROOT / "production_deployment.py", ROOT / "pages" / "29_☁️_Production_Deployment_Real_E2E.py", ROOT / "tests" / "test_refinamento14.py"]
    faltam = [str(p.relative_to(ROOT)) for p in esperados if not p.exists()]
    return [_item("Production Deployment & Real E2E", not faltam, "Health/migration/OIDC/real-E2E presentes" if not faltam else f"Faltam: {faltam}")]


def verificar_stable_candidate() -> list[dict]:
    esperados = [ROOT / "stable_candidate.py", ROOT / "pages" / "30_🏆_Stable_Candidate_Cloud_Launch.py", ROOT / "tests" / "test_refinamento15.py"]
    faltam = [str(p.relative_to(ROOT)) for p in esperados if not p.exists()]
    return [_item("Stable Candidate & Cloud Launch", not faltam, "Fingerprint/evidências/rollback/promotion gate presentes" if not faltam else f"Faltam: {faltam}")]


def verificar_asset_library() -> list[dict]:
    esperados = [ROOT / "asset_library.py", ROOT / "pages" / "31_🖼️_Asset_Library_Media_Manager.py", ROOT / "tests" / "test_refinamento16.py"]
    faltam = [str(p.relative_to(ROOT)) for p in esperados if not p.exists()]
    return [_item("Asset Library & Media Manager", not faltam, "Galeria/filtros/Masters/versões/usage/storage manager presentes" if not faltam else f"Faltam: {faltam}")]


def verificar_refinamento17() -> list[dict]:
    esperados = [
        ROOT / "author_profiles.py",
        ROOT / "integration_ux.py",
        ROOT / "pages" / "32_✍️_Autores_e_Colaboradores.py",
        ROOT / "pages" / "33_🧭_Integration_UX_Center.py",
        ROOT / "tests" / "test_refinamento17.py",
    ]
    faltam = [str(p.relative_to(ROOT)) for p in esperados if not p.exists()]
    return [_item("Integration/UX + Author Profiles", not faltam, "Autoria estruturada + handoff entre Studios presentes" if not faltam else f"Faltam: {faltam}")]



def verificar_refinamento18() -> list[dict]:
    esperados = [
        ROOT / "family_profiles.py",
        ROOT / "pages" / "34_🏠_Perfis_e_Dashboard.py",
        ROOT / "tests" / "test_refinamento18.py",
    ]
    faltam = [str(p.relative_to(ROOT)) for p in esperados if not p.exists()]
    return [_item("Family Profiles & Simplified Dashboard", not faltam, "Perfis de workspace + organização pessoal + dashboard simplificado presentes" if not faltam else f"Faltam: {faltam}")]


def verificar_refinamento19() -> list[dict]:
    esperados = [
        ROOT / "real_pilot.py",
        ROOT / "pages" / "35_🧪_Real_Pilot_Bug_Fix.py",
        ROOT / "tests" / "test_refinamento19.py",
    ]
    faltam = [str(p.relative_to(ROOT)) for p in esperados if not p.exists()]
    return [_item("Real Pilot & Bug Fix", not faltam, "Pilotos reais + bug registry + gate pré-Stable presentes" if not faltam else f"Faltam: {faltam}")]

def verificar_refinamento20() -> list[dict]:
    esperados = [
        ROOT / "final_prelaunch.py",
        ROOT / "pages" / "36_🏆_RC4_Final_PreLaunch.py",
        ROOT / "tests" / "test_refinamento20.py",
    ]
    faltam = [str(p.relative_to(ROOT)) for p in esperados if not p.exists()]
    return [_item("RC4 Final Pre-Launch Gate", not faltam, "Cloud E2E obrigatório + pilot gate + sign-off/fingerprint presentes" if not faltam else f"Faltam: {faltam}")]


def verificar_refinamento21() -> list[dict]:
    esperados = [
        ROOT / "agent_skills.py",
        ROOT / "skills" / "agent_profiles.json",
        ROOT / "bestseller_readiness.py",
        ROOT / "market_intelligence.py",
        ROOT / "biblical_reference_validator.py",
        ROOT / "pages" / "37_🧠_Agent_Skills_Bestseller_Readiness.py",
        ROOT / "tests" / "test_refinamento21.py",
    ]
    faltam = [str(p.relative_to(ROOT)) for p in esperados if not p.exists()]
    try:
        from agent_skills import validate_registry
        audit = validate_registry()
    except Exception as exc:
        audit = {"ok": False, "errors": [f"{type(exc).__name__}: {exc}"]}
    ok = not faltam and bool(audit.get("ok")) and int(audit.get("role_count", 0)) == 23
    detalhe = f"23 papéis formalizados · {audit.get('module_count',0)} módulos agents/ · Bible/Market/Readiness presentes" if ok else f"Faltam={faltam}; audit={audit.get('errors',[])}"
    return [_item("Agent Skills & Bestseller Readiness", ok, detalhe)]


def verificar_gitignore() -> list[dict]:
    p = ROOT / ".gitignore"
    if not p.exists():
        return [_item(".gitignore", False, "Ausente", "aviso")]
    texto = p.read_text(encoding="utf-8")
    essenciais = ["__pycache__/", "*.pyc", ".streamlit/secrets.toml", ".faithbloom_cache/", "saida_imagens/", "saida_audio/"]
    faltam = [x for x in essenciais if x not in texto]
    return [_item(".gitignore", not faltam, "OK" if not faltam else f"Faltam regras: {', '.join(faltam)}", "aviso" if faltam else "info")]


def rodar_qa_release(incluir_tests: bool = True) -> dict:
    grupos = {
        "Código": verificar_sintaxe() + verificar_requirements(),
        "Navegação": verificar_page_links(),
        "Segurança": verificar_segredos(),
        "Repositório": verificar_higiene_repo() + verificar_gitignore(),
        "Stable hardening": verificar_stable_hardening(),
        "Production deployment": verificar_production_deployment(),
        "Stable candidate": verificar_stable_candidate(),
        "Asset library": verificar_asset_library(),
        "Refinamento 17": verificar_refinamento17(),
        "Refinamento 18": verificar_refinamento18(),
        "Refinamento 19": verificar_refinamento19(),
        "Refinamento 20": verificar_refinamento20(),
        "Refinamento 21": verificar_refinamento21(),
        "Projeto piloto": verificar_natal(),
    }
    if incluir_tests:
        grupos["Testes"] = verificar_tests()
    todos = [x for itens in grupos.values() for x in itens]
    erros = [x for x in todos if not x["ok"] and x["nivel"] == "erro"]
    avisos = [x for x in todos if not x["ok"] and x["nivel"] == "aviso"]
    return {
        "version": RELEASE_VERSION,
        "ok": not erros,
        "erros": erros,
        "avisos": avisos,
        "grupos": grupos,
    }


def salvar_relatorio(path: str = "release_qa_report.json") -> str:
    resultado = rodar_qa_release(incluir_tests=True)
    destino = ROOT / path
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(destino)


if __name__ == "__main__":
    r = rodar_qa_release(incluir_tests=True)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    raise SystemExit(0 if r["ok"] else 1)

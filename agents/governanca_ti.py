"""Governança de TI: integridade de fontes, dependências e evidências operacionais."""
from __future__ import annotations

import ast
import importlib.metadata
import re
from pathlib import Path
from typing import Any

from governance import build_report, finding, inspect_source, preflight_action, verify_control

ROLE_ID = "it_governance"
NAME = "Agente de Governança de TI"
MISSION = "Verificar integridade técnica, dependências, observabilidade, recuperação e prontidão operacional sem efetuar deploys."
SKILL_DOMAINS = {
    "operations": ("saúde operacional", "observabilidade", "continuidade", "gestão de incidentes"),
    "delivery": ("CI e regressão", "gestão de mudanças", "release e rollback", "integridade de configuração"),
    "supply_chain": ("inventário de dependências", "versionamento", "higiene técnica", "limites de diagnóstico estático"),
}
NON_NEGOTIABLES = (
    "não executar código inspecionado nem instalar dependências no diagnóstico",
    "não executar merge, deploy ou mudança destrutiva automaticamente",
    "teste não executado permanece UNKNOWN",
    "não alegar ausência de vulnerabilidades sem análise e evidências apropriadas",
    "não ler segredos ou configurações privadas para preencher relatórios",
)


def all_skills() -> list[str]:
    return [skill for domain in SKILL_DOMAINS.values() for skill in domain]


def check_it_action(action: str, **kwargs: Any) -> dict:
    from agent_skills import require_role_ready
    require_role_ready("it_governance")
    return preflight_action(action, **kwargs)


def run_diagnostic(root: str | Path | None = None, *, context: dict | None = None, **_: Any) -> dict:
    from agent_skills import require_role_ready
    require_role_ready("it_governance")
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    context = dict(context or {})
    findings = []
    # A lista explícita evita ler uploads, dados pessoais e diretórios fora do código.
    for name in ("app.py", "storage_backend.py", "ai_provider_router.py", "controle_geracao.py", "security_baseline.py", "agent_skills.py"):
        evidence = inspect_source(root, name)
        status = "FAIL"
        if evidence:
            try:
                ast.parse((root / name).read_text(encoding="utf-8"))
                status = "PASS"
            except (OSError, SyntaxError, UnicodeError):
                status = "FAIL"
        findings.append(finding("it_syntax_" + Path(name).stem, status, "Sintaxe Python: " + name,
            evidence, "A sintaxe aprovada não substitui testes funcionais, execução ou análise de segurança."))
    path = root / "requirements.txt"
    if path.is_file() and not path.is_symlink():
        lines = path.read_text(encoding="utf-8").splitlines()
        unbounded = []
        for line_no, raw in enumerate(lines, 1):
            spec = raw.strip()
            if not spec or spec.startswith("#"):
                continue
            match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?(.*)$", spec)
            if not match:
                findings.append(finding("dependency_spec_" + str(line_no), "UNKNOWN", "Especificação de dependência requer revisão", [f"requirements.txt:{line_no}"], "Verificar a origem e versão da dependência."))
                continue
            package, version_spec = match.groups()
            if not any(x in version_spec for x in ("==", "<", "~=")):
                unbounded.append(f"requirements.txt:{line_no}")
            try:
                importlib.metadata.version(package)
                installed = True
            except importlib.metadata.PackageNotFoundError:
                installed = False
            findings.append(finding("dependency_installed_" + package.lower(), "PASS" if installed else "WARN",
                "Dependência instalada: " + package, [f"requirements.txt:{line_no}", "runtime:package-metadata"],
                "Presença no ambiente não comprova compatibilidade nem segurança da versão."))
        findings.append(finding("it_dependency_bounds", "WARN" if unbounded else "PASS", "Limites de versões nas dependências", unbounded or ["requirements.txt:1"],
            "Fixar versões ou limites compatíveis e manter revisão de atualizações."))
    else:
        findings.append(finding("it_dependency_manifest", "FAIL", "Manifesto de dependências indisponível", [], "Restaurar requirements.txt e conferir sua integridade."))
    for name, title in (
        ("ci_green", "CI da revisão atual"), ("runtime_health", "Saúde da aplicação publicada"),
        ("regression_tests", "Regressão dos produtos e serviços"), ("vulnerability_scan", "Análise de vulnerabilidades"),
        ("monitoring_alerts", "Monitoramento e alertas"), ("rollback_tested", "Rollback testado"),
    ):
        status, evidence = verify_control(context, name)
        findings.append(finding(name, status, title, evidence, "Registrar o resultado observado na revisão implantada; não inferir produção a partir de fontes locais."))
    return build_report(ROLE_ID, NAME, findings, scope="TI: análise estática selecionada e evidências operacionais fornecidas")

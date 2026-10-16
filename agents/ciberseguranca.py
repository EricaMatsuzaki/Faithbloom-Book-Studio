"""Agente de cibersegurança: controles observados, sem scans externos ou certificação."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from governance import build_report, finding, inspect_source, preflight_action, verify_control

ROLE_ID = "cybersecurity"
NAME = "Agente de Cibersegurança"
MISSION = "Verificar controles de acesso, isolamento de clientes, segredos, uploads e riscos operacionais com evidências rastreáveis."
SKILL_DOMAINS = {
    "application_security": ("autenticação e autorização", "isolamento de tenant", "validação de uploads", "least privilege"),
    "privacy": ("proteção de segredos", "dados pessoais", "auditoria sanitizada", "armazenamento privado"),
    "resilience": ("revisão de vulnerabilidades", "resposta a incidentes", "mudanças seguras", "evidências de hardening"),
}
NON_NEGOTIABLES = (
    "não imprimir, copiar ou testar credenciais",
    "não executar ataques, scans de redes ou operações destrutivas",
    "não tratar política escrita como segurança aplicada",
    "não declarar ambiente seguro sem evidências dos controles relevantes",
    "preservar Masters, originais e histórico",
)


def all_skills() -> list[str]:
    return [skill for domain in SKILL_DOMAINS.values() for skill in domain]


def check_security_action(action: str, **kwargs: Any) -> dict:
    return preflight_action(action, **kwargs)


def run_diagnostic(root: str | Path | None = None, *, context: dict | None = None, **_: Any) -> dict:
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    context = dict(context or {})
    findings = []
    for code, symbol, title in (
        ("security_baseline", "security_by_default_gate", "Baseline de segurança presente"),
        ("security_authorization", "authorize_action", "Guarda de autorização presente"),
        ("security_upload_validation", "validate_upload", "Validação de uploads presente"),
    ):
        evidence = inspect_source(root, "security_baseline.py", symbol)
        findings.append(finding(code, "PASS" if evidence else "FAIL", title, evidence,
            "Conferir os chamadores: função definida não prova que protege cada ação."))
    calls = []
    for name in ("app.py", "saas_access.py", "storage_backend.py"):
        evidence = inspect_source(root, name)
        if not evidence:
            continue
        try:
            tree = ast.parse((root / name).read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                symbol = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if symbol in {"authorize_action", "require_action", "require_access", "require_authenticated", "require_streamlit_access", "enforce_access", "enforce_app_access"}:
                    calls.append(f"{name}:{node.lineno}")
    findings.append(finding("security_access_integration", "PASS" if calls else "WARN",
        "Chamada de controle de acesso nas fontes selecionadas", calls,
        "Verificar login, acesso direto às páginas e tentativas entre tenants em execução. Esta verificação não cobre todos os caminhos."))
    for name, title in (
        ("authentication_live", "Autenticação aplicada em execução"),
        ("authorization_live", "Permissões por ação aplicadas em execução"),
        ("cross_tenant_denied", "Acesso entre tenants negado em teste"),
        ("private_storage", "Armazenamento privado conferido"),
        ("secrets_not_logged", "Segredos protegidos nos logs"),
        ("upload_content_inspection", "Inspeção do conteúdo de uploads"),
        ("vulnerability_scan", "Vulnerabilidades revisadas"),
        ("incident_response", "Resposta e recuperação de incidentes"),
    ):
        status, evidence = verify_control(context, name)
        findings.append(finding(name, status, title, evidence,
            "Adicionar referência a teste ou execução observada; o diagnóstico não lê Secrets nem faz ataques."))
    return build_report(ROLE_ID, NAME, findings, scope="Cibersegurança: fontes locais selecionadas e evidências fornecidas")

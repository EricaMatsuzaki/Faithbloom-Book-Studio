"""Agente técnico do FaithBloom especializado em SaaS robusto e automação.

Este agente não substitui os módulos editoriais. Ele atua como engenheiro/arquiteto
transversal para evolução do produto, qualidade operacional, integrações,
automação, segurança, testes, observabilidade e release readiness.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

SCHEMA = "faithbloom.saas-automation-engineer.v1"
ROLE_ID = "saas_automation_engineer"
NAME = "Arquiteto SaaS & Automação"
MISSION = (
    "Projetar, auditar e evoluir o FaithBloom como SaaS robusto, seguro, testável, "
    "observável, automatizado e operável em produção, reutilizando a arquitetura existente."
)

SKILL_DOMAINS: dict[str, tuple[str, ...]] = {
    "architecture": (
        "software architecture", "modular monolith", "service boundaries", "API design",
        "event-driven patterns", "state machines", "idempotency", "versioning", "anti-duplication",
    ),
    "backend": (
        "Python", "FastAPI/ASGI concepts", "background jobs", "queues", "webhooks",
        "rate limiting", "retries", "timeouts", "circuit breakers", "structured errors",
    ),
    "frontend": (
        "Streamlit", "HTML/CSS/JavaScript", "responsive UI", "accessibility",
        "component architecture", "state synchronization", "browser/mobile compatibility",
    ),
    "data": (
        "PostgreSQL/Supabase", "schema design", "migrations", "transactions", "indexes",
        "row-level security", "data retention", "backup/restore", "audit trails",
    ),
    "auth_security": (
        "authentication", "authorization", "RBAC", "tenant isolation", "secrets management",
        "OWASP", "input validation", "secure uploads", "least privilege", "privacy by design",
    ),
    "saas_product": (
        "multi-tenancy", "plans/entitlements", "usage metering", "quotas", "feature flags",
        "onboarding", "account lifecycle", "billing boundaries", "admin tooling",
    ),
    "automation": (
        "workflow automation", "schedulers", "webhooks", "event triggers", "job orchestration",
        "human approval gates", "deduplication", "replay safety", "dead-letter handling",
    ),
    "ai_agents": (
        "LLM orchestration", "tool routing", "structured outputs", "prompt/version management",
        "guardrails", "cost controls", "fallback models", "evaluation", "human-in-the-loop",
    ),
    "testing": (
        "unit tests", "integration tests", "contract tests", "end-to-end tests", "regression tests",
        "browser tests", "load tests", "failure injection", "test fixtures", "CI quality gates",
    ),
    "devops": (
        "Git/GitHub", "branching", "pull requests", "GitHub Actions", "CI/CD", "Streamlit Cloud",
        "containers", "environment parity", "release strategy", "rollback", "zero-downtime thinking",
    ),
    "observability": (
        "structured logging", "metrics", "tracing", "health checks", "SLO/SLI", "alerting",
        "error budgets", "incident diagnostics", "correlation IDs", "operational dashboards",
    ),
    "reliability": (
        "graceful degradation", "fault tolerance", "backpressure", "concurrency safety",
        "recovery points", "disaster recovery", "capacity planning", "performance optimization",
    ),
    "quality": (
        "code review", "static analysis", "dependency hygiene", "documentation", "ADR",
        "release checklists", "technical debt control", "maintainability", "developer experience",
    ),
}

NON_NEGOTIABLES = (
    "verificar antes de criar para evitar duplicação",
    "reutilizar e estender componentes existentes antes de criar novos",
    "não alterar release protegida nem fazer merge sem autorização explícita",
    "não executar operação destrutiva ou irreversível sem confirmação explícita",
    "não expor segredos, tokens, credenciais ou dados privados em logs",
    "não declarar produção pronta sem evidência de testes e checks necessários",
    "preservar original, histórico, versões e recovery path antes de migrações",
    "manter ações pagas ou de alto impacto atrás de guardrails e aprovação",
)

TASK_HINTS = {
    "architecture": ("arquitetura", "refator", "módulo", "modulo", "estrutura", "duplic"),
    "automation": ("automat", "workflow", "fila", "job", "webhook", "gatilho", "scheduler"),
    "security": ("segurança", "seguranca", "auth", "login", "permiss", "token", "secret"),
    "data": ("supabase", "banco", "database", "sql", "persist", "migra", "backup"),
    "frontend": ("streamlit", "interface", "ui", "ux", "responsiv", "mobile", "css"),
    "devops": ("deploy", "github actions", "ci", "cd", "release", "rollback", "produção", "producao"),
    "testing": ("teste", "pytest", "e2e", "regress", "load test", "qa"),
    "observability": ("log", "métrica", "metrica", "monitor", "alert", "trace", "observab"),
    "ai_agents": ("agente", "llm", "openrouter", "gemini", "prompt", "tool", "jarvis"),
}

HIGH_IMPACT_HINTS = (
    "apagar", "delet", "drop", "merge", "publicar", "produção", "producao", "migrar banco",
    "alterar master", "rotacionar segredo", "cobrar", "pagamento", "billing", "enviar externo",
)


def all_skills() -> list[str]:
    """Lista única de competências, útil para UI, auditoria e testes."""
    seen: list[str] = []
    for skills in SKILL_DOMAINS.values():
        for skill in skills:
            if skill not in seen:
                seen.append(skill)
    return seen


def classify_request(text: str) -> list[str]:
    value = (text or "").casefold()
    matches = [domain for domain, hints in TASK_HINTS.items() if any(h in value for h in hints)]
    return matches or ["architecture"]


def requires_explicit_approval(text: str) -> bool:
    value = (text or "").casefold()
    return any(hint in value for hint in HIGH_IMPACT_HINTS)


def build_execution_plan(text: str, *, existing_components: list[str] | None = None) -> dict[str, Any]:
    """Cria plano técnico auditável seguindo verificar→reutilizar→estender→criar."""
    clean = (text or "").strip()
    if not clean:
        raise ValueError("Descreva a mudança técnica que o agente deve analisar.")
    domains = classify_request(clean)
    components = list(existing_components or [])
    high_impact = requires_explicit_approval(clean)
    steps = [
        {"phase": "verify", "action": "Auditar arquitetura, branch, dependências, módulos e testes relacionados antes de editar."},
        {"phase": "reuse", "action": "Mapear componentes existentes que já resolvem total ou parcialmente o pedido."},
        {"phase": "extend", "action": "Preferir extensão compatível e pequena sobre componentes canônicos existentes."},
        {"phase": "implement", "action": "Criar código novo somente para lacunas comprovadas, com interfaces explícitas e rollback."},
        {"phase": "validate", "action": "Executar testes unitários, integração/regressão aplicáveis e validar falhas reais de runtime."},
        {"phase": "release", "action": "Confirmar CI, observabilidade, segurança, migrações, rollback e aprovação humana antes de release."},
    ]
    return {
        "schema": SCHEMA,
        "role_id": ROLE_ID,
        "agent": NAME,
        "request": clean,
        "domains": domains,
        "existing_components": components,
        "anti_duplication_sequence": ["verify", "reuse", "extend", "create_if_missing"],
        "steps": steps,
        "requires_explicit_approval": high_impact,
        "status": "needs_approval" if high_impact else "planned",
    }


def automation_safety_gate(spec: dict[str, Any]) -> dict[str, Any]:
    """Valida requisitos mínimos antes de ativar automação que muda estado."""
    spec = dict(spec or {})
    mutates_state = bool(spec.get("mutates_state"))
    external_action = bool(spec.get("external_action"))
    paid_action = bool(spec.get("paid_action"))
    destructive = bool(spec.get("destructive"))
    has_idempotency = bool(spec.get("idempotency_key") or not mutates_state)
    has_audit = bool(spec.get("audit_log") or not mutates_state)
    has_rollback = bool(spec.get("rollback") or not mutates_state)
    approval_required = destructive or external_action or paid_action or bool(spec.get("high_impact"))
    blockers = []
    if not has_idempotency:
        blockers.append("idempotency_missing")
    if not has_audit:
        blockers.append("audit_log_missing")
    if not has_rollback:
        blockers.append("rollback_missing")
    if approval_required and not spec.get("approved"):
        blockers.append("explicit_approval_missing")
    return {
        "ok": not blockers,
        "blockers": blockers,
        "approval_required": approval_required,
        "safe_to_execute": not blockers,
    }


def release_readiness(checks: dict[str, Any]) -> dict[str, Any]:
    """Gate conservador: só marca ready quando todos os checks obrigatórios passam."""
    checks = dict(checks or {})
    mandatory = (
        "tests", "ci", "security", "migration_safety", "rollback", "secrets", "observability",
    )
    missing = [name for name in mandatory if checks.get(name) is not True]
    return {
        "ready": not missing,
        "missing": missing,
        "status": "ready" if not missing else "blocked",
    }


def handle_saas_request(text: str, *, existing_components: list[str] | None = None) -> dict[str, Any]:
    """Entrada operacional principal para Jarvis/Orquestrador e testes."""
    plan = build_execution_plan(text, existing_components=existing_components)
    return deepcopy({
        **plan,
        "mission": MISSION,
        "skill_domains": list(SKILL_DOMAINS),
        "skill_count": len(all_skills()),
        "non_negotiables": list(NON_NEGOTIABLES),
    })

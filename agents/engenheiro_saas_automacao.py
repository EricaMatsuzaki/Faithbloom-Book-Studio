"""Agente técnico do FaithBloom especializado em SaaS, Full-Stack e automação.

Este agente não substitui os módulos editoriais. Ele atua como engenheiro/arquiteto
transversal para evolução do produto, criação de apps e sites, qualidade operacional,
integrações, automação, segurança, testes, observabilidade e release readiness.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from security_baseline import security_by_default_gate

SCHEMA = "faithbloom.saas-fullstack-automation-engineer.v3"
ROLE_ID = "saas_automation_engineer"
NAME = "Arquiteto SaaS, Full-Stack & Automação"
MISSION = (
    "Projetar, construir, auditar e evoluir SaaS, aplicações web, painéis, sites e landing pages "
    "robustos, seguros, responsivos, testáveis, observáveis, automatizados e operáveis em produção, "
    "reutilizando a arquitetura existente antes de criar componentes novos."
)

SKILL_DOMAINS: dict[str, tuple[str, ...]] = {
    "architecture": (
        "software architecture", "modular monolith", "service boundaries", "API design",
        "event-driven patterns", "state machines", "idempotency", "versioning", "anti-duplication",
        "domain modeling", "clean architecture", "SOLID", "separation of concerns",
    ),
    "backend": (
        "Python", "FastAPI/ASGI concepts", "REST APIs", "JSON APIs", "background jobs", "queues",
        "webhooks", "rate limiting", "retries", "timeouts", "circuit breakers", "structured errors",
        "file processing", "API pagination", "caching", "service integrations",
    ),
    "fullstack": (
        "full-stack application development", "frontend-backend integration", "CRUD applications",
        "dashboard development", "admin portals", "internal tools", "forms and validation",
        "real-time UI concepts", "session management", "role-aware interfaces", "end-to-end feature delivery",
    ),
    "frontend": (
        "Streamlit", "HTML", "CSS", "JavaScript", "TypeScript concepts", "React concepts", "Next.js concepts",
        "responsive UI", "mobile-first design", "accessibility", "component architecture", "design systems",
        "state synchronization", "browser/mobile compatibility", "microinteractions", "performance", "PWA concepts",
    ),
    "websites": (
        "business websites", "marketing websites", "landing pages", "product pages", "pricing pages",
        "contact pages", "FAQ pages", "blog structure", "navigation architecture", "conversion flows",
        "lead capture", "newsletter forms", "cookie/consent UX", "responsive sections", "reusable page sections",
    ),
    "ux_ui": (
        "information architecture", "user flows", "wireframes", "visual hierarchy", "interaction design",
        "responsive layouts", "empty states", "loading states", "error states", "onboarding UX",
        "form UX", "accessibility WCAG concepts", "usability", "design consistency",
    ),
    "seo_growth": (
        "technical SEO", "semantic HTML", "metadata", "Open Graph", "structured data concepts",
        "sitemap", "robots.txt", "Core Web Vitals concepts", "analytics integration", "conversion tracking",
        "A/B testing concepts", "landing page CRO", "performance budgets",
    ),
    "data": (
        "PostgreSQL/Supabase", "schema design", "migrations", "transactions", "indexes",
        "row-level security", "data retention", "backup/restore", "audit trails", "query optimization",
        "data validation", "storage buckets", "signed URLs concepts",
    ),
    "auth_security": (
        "authentication", "authorization", "RBAC", "tenant isolation", "secrets management",
        "OWASP", "input validation", "secure uploads", "least privilege", "privacy by design",
        "CSRF/XSS/SQL injection awareness", "secure cookies", "session security", "CORS concepts",
        "security by default", "fail-closed production gates", "MFA for privileged users",
        "recent re-authentication for critical actions", "security headers", "vulnerability scanning",
        "dependency security review", "malicious upload controls", "cross-tenant access prevention",
    ),
    "saas_product": (
        "multi-tenancy", "plans/entitlements", "usage metering", "quotas", "feature flags",
        "onboarding", "account lifecycle", "billing boundaries", "admin tooling", "trial flows",
        "subscription UX", "workspace concepts", "invites", "audit history", "product analytics",
    ),
    "automation": (
        "workflow automation", "schedulers", "webhooks", "event triggers", "job orchestration",
        "human approval gates", "deduplication", "replay safety", "dead-letter handling",
        "cron concepts", "automation state machines", "reconciliation jobs", "notifications",
    ),
    "integrations": (
        "third-party APIs", "OAuth concepts", "webhook consumers", "webhook producers", "email integrations",
        "calendar integrations", "storage integrations", "payment integration boundaries", "API adapters",
        "provider abstraction", "fallback providers", "integration testing",
    ),
    "ai_agents": (
        "LLM orchestration", "tool routing", "structured outputs", "prompt/version management",
        "guardrails", "cost controls", "fallback models", "evaluation", "human-in-the-loop",
        "agent workflows", "RAG concepts", "context management", "tool permission boundaries",
    ),
    "testing": (
        "unit tests", "integration tests", "contract tests", "end-to-end tests", "regression tests",
        "browser tests", "load tests", "failure injection", "test fixtures", "CI quality gates",
        "UI smoke tests", "API tests", "migration tests", "accessibility tests concepts", "security regression tests",
    ),
    "devops": (
        "Git/GitHub", "branching", "pull requests", "GitHub Actions", "CI/CD", "Streamlit Cloud",
        "containers", "environment parity", "release strategy", "rollback", "zero-downtime thinking",
        "environment variables", "preview environments concepts", "deployment diagnostics",
    ),
    "observability": (
        "structured logging", "metrics", "tracing", "health checks", "SLO/SLI", "alerting",
        "error budgets", "incident diagnostics", "correlation IDs", "operational dashboards",
        "frontend error monitoring concepts", "audit events",
    ),
    "reliability": (
        "graceful degradation", "fault tolerance", "backpressure", "concurrency safety",
        "recovery points", "disaster recovery", "capacity planning", "performance optimization",
        "cache invalidation", "retry safety", "provider outage fallbacks",
    ),
    "quality": (
        "code review", "static analysis", "dependency hygiene", "documentation", "ADR",
        "release checklists", "technical debt control", "maintainability", "developer experience",
        "naming conventions", "modularity", "refactoring safety",
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
    "interfaces devem ser responsivas, acessíveis e funcionais antes de serem consideradas concluídas",
    "sites e landing pages devem separar conteúdo, apresentação e integrações para facilitar manutenção",
    "Security by Default é obrigatório: nenhum SaaS ou produto digital pode ser considerado pronto para produção sem Security Gate PASS",
    "isolamento de tenant, autorização e proteção de dados devem falhar de forma fechada quando a evidência estiver ausente",
)

TASK_HINTS = {
    "architecture": ("arquitetura", "refator", "módulo", "modulo", "estrutura", "duplic"),
    "automation": ("automat", "workflow", "fila", "job", "webhook", "gatilho", "scheduler"),
    "security": ("segurança", "seguranca", "auth", "login", "permiss", "token", "secret", "rls", "mfa", "vulnerab"),
    "data": ("supabase", "banco", "database", "sql", "persist", "migra", "backup"),
    "frontend": ("streamlit", "interface", "ui", "ux", "responsiv", "mobile", "css", "frontend"),
    "fullstack": ("full stack", "fullstack", "app", "aplicativo", "aplicação", "aplicacao", "dashboard", "painel", "crud"),
    "websites": ("site", "website", "landing page", "landing", "página de venda", "pagina de venda", "página institucional", "pagina institucional"),
    "seo_growth": ("seo", "google", "conversão", "conversao", "analytics", "meta tag", "sitemap"),
    "devops": ("deploy", "github actions", "ci", "cd", "release", "rollback", "produção", "producao"),
    "testing": ("teste", "pytest", "e2e", "regress", "load test", "qa"),
    "observability": ("log", "métrica", "metrica", "monitor", "alert", "trace", "observab"),
    "ai_agents": ("agente", "llm", "openrouter", "gemini", "prompt", "tool", "jarvis"),
    "integrations": ("api", "oauth", "integra", "email", "calendar", "pagamento"),
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
        {"phase": "verify", "action": "Auditar arquitetura, branch, dependências, módulos, UI e testes relacionados antes de editar."},
        {"phase": "reuse", "action": "Mapear componentes, estilos, serviços e integrações existentes que já resolvem total ou parcialmente o pedido."},
        {"phase": "design", "action": "Definir fluxo, estados, responsividade, acessibilidade, contratos de API e persistência antes da implementação."},
        {"phase": "security", "action": "Aplicar Security by Default: autenticação, autorização, tenant isolation, RLS/dados, secrets, APIs, uploads, logs, backup, privacidade, dependências e controles web."},
        {"phase": "extend", "action": "Preferir extensão compatível e pequena sobre componentes canônicos existentes."},
        {"phase": "implement", "action": "Criar código novo somente para lacunas comprovadas, com interfaces explícitas, tratamento de erros e rollback."},
        {"phase": "validate", "action": "Executar testes unitários, integração, segurança, UI/E2E/regressão aplicáveis e validar falhas reais de runtime."},
        {"phase": "release", "action": "Confirmar CI, Security Gate, observabilidade, migrações, SEO/performance quando aplicável, rollback e aprovação humana antes de release."},
    ]
    return {
        "schema": SCHEMA,
        "role_id": ROLE_ID,
        "agent": NAME,
        "request": clean,
        "domains": domains,
        "existing_components": components,
        "anti_duplication_sequence": ["verify", "reuse", "extend", "create_if_missing"],
        "security_by_default": True,
        "production_requires_security_gate": True,
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


def production_security_readiness(
    security_controls: dict[str, Any] | None,
    *,
    privileged_access: bool = True,
) -> dict[str, Any]:
    """Security Gate oficial do agente para SaaS/produtos digitais em produção."""
    return security_by_default_gate(
        security_controls,
        production=True,
        privileged_access=privileged_access,
    )


def release_readiness(checks: dict[str, Any]) -> dict[str, Any]:
    """Gate conservador: produção exige Security-by-Default além de CI/rollback."""
    checks = dict(checks or {})
    security = production_security_readiness(
        checks.get("security_controls"),
        privileged_access=bool(checks.get("privileged_access", True)),
    )
    mandatory = (
        "tests", "ci", "migration_safety", "rollback", "secrets", "observability",
    )
    missing = [name for name in mandatory if checks.get(name) is not True]
    if not security["ready"]:
        missing.append("security_gate")
    return {
        "ready": not missing,
        "missing": missing,
        "status": "ready" if not missing else "blocked",
        "security_gate": security,
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
        "security_policy": "security_by_default_fail_closed",
    })

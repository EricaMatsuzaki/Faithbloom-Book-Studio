from agents import engenheiro_saas_automacao as eng
from security_baseline import PRIVILEGED_REQUIRED, PRODUCTION_REQUIRED


def _security_controls(*, privileged=True):
    controls = {name: True for name in PRODUCTION_REQUIRED}
    if privileged:
        controls.update({name: True for name in PRIVILEGED_REQUIRED})
    return controls


def test_profile_has_broad_saas_skill_coverage():
    assert eng.ROLE_ID == "saas_automation_engineer"
    assert len(eng.SKILL_DOMAINS) >= 15
    assert len(eng.all_skills()) >= 140
    for required in (
        "architecture", "backend", "fullstack", "frontend", "websites", "ux_ui", "seo_growth",
        "data", "auth_security", "automation", "integrations", "testing", "devops",
        "observability", "reliability",
    ):
        assert required in eng.SKILL_DOMAINS


def test_fullstack_and_web_deliverables_are_covered():
    skills = set(eng.all_skills())
    for required in (
        "full-stack application development", "landing pages", "responsive UI", "REST APIs",
        "technical SEO", "design systems", "dashboard development", "third-party APIs",
    ):
        assert required in skills


def test_security_by_default_skills_are_mandatory():
    skills = set(eng.all_skills())
    for required in (
        "security by default", "fail-closed production gates", "MFA for privileged users",
        "vulnerability scanning", "cross-tenant access prevention",
    ):
        assert required in skills
    assert any("Security by Default" in item for item in eng.NON_NEGOTIABLES)


def test_request_is_classified_into_multiple_domains():
    domains = eng.classify_request("Quero automatizar o deploy no GitHub Actions e melhorar os testes e logs")
    assert "automation" in domains
    assert "devops" in domains
    assert "testing" in domains
    assert "observability" in domains


def test_app_request_is_classified_as_fullstack():
    domains = eng.classify_request("Crie um app full stack com dashboard, API e login")
    assert "fullstack" in domains
    assert "integrations" in domains


def test_landing_page_request_is_classified_for_web_and_growth():
    domains = eng.classify_request("Crie uma landing page responsiva com SEO e analytics")
    assert "websites" in domains
    assert "frontend" in domains
    assert "seo_growth" in domains


def test_security_request_is_classified_as_security():
    domains = eng.classify_request("Ative RLS, MFA e faça uma auditoria de vulnerabilidades")
    assert "security" in domains


def test_execution_plan_preserves_anti_duplication_sequence_and_security_phase():
    plan = eng.build_execution_plan("Refatore a arquitetura do SaaS", existing_components=["orchestrator", "production_queue"])
    assert plan["anti_duplication_sequence"] == ["verify", "reuse", "extend", "create_if_missing"]
    assert plan["status"] == "planned"
    assert plan["existing_components"] == ["orchestrator", "production_queue"]
    assert plan["security_by_default"] is True
    assert plan["production_requires_security_gate"] is True
    assert "security" in [step["phase"] for step in plan["steps"]]


def test_high_impact_request_requires_explicit_approval():
    plan = eng.build_execution_plan("Faça merge na release e publique em produção")
    assert plan["requires_explicit_approval"] is True
    assert plan["status"] == "needs_approval"


def test_automation_gate_blocks_mutation_without_safety_controls():
    gate = eng.automation_safety_gate({"mutates_state": True})
    assert gate["ok"] is False
    assert "idempotency_missing" in gate["blockers"]
    assert "audit_log_missing" in gate["blockers"]
    assert "rollback_missing" in gate["blockers"]


def test_automation_gate_requires_approval_for_external_action():
    gate = eng.automation_safety_gate({
        "mutates_state": True,
        "external_action": True,
        "idempotency_key": "evt-123",
        "audit_log": True,
        "rollback": True,
    })
    assert gate["approval_required"] is True
    assert "explicit_approval_missing" in gate["blockers"]


def test_release_readiness_requires_full_security_gate():
    checks = {
        "tests": True,
        "ci": True,
        "migration_safety": True,
        "rollback": True,
        "secrets": True,
        "observability": True,
        "security_controls": _security_controls(),
    }
    ready = eng.release_readiness(checks)
    assert ready["ready"] is True
    assert ready["security_gate"]["status"] == "PASS"

    blocked = eng.release_readiness({"tests": True, "ci": True})
    assert blocked["ready"] is False
    assert "security_gate" in blocked["missing"]
    assert blocked["security_gate"]["status"] == "BLOCKED"


def test_public_entrypoint_returns_operational_agent_contract():
    result = eng.handle_saas_request("Automatize uma fila segura de geração", existing_components=["Fila de Produção"])
    assert result["agent"] == "Arquiteto SaaS, Full-Stack & Automação"
    assert result["skill_count"] >= 140
    assert "automation" in result["domains"]
    assert result["non_negotiables"]
    assert result["security_policy"] == "security_by_default_fail_closed"

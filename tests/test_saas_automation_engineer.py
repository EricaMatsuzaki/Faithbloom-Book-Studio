from agents import engenheiro_saas_automacao as eng


def test_profile_has_broad_saas_skill_coverage():
    assert eng.ROLE_ID == "saas_automation_engineer"
    assert len(eng.SKILL_DOMAINS) >= 10
    assert len(eng.all_skills()) >= 80
    for required in ("architecture", "backend", "frontend", "data", "auth_security", "automation", "testing", "devops", "observability", "reliability"):
        assert required in eng.SKILL_DOMAINS


def test_request_is_classified_into_multiple_domains():
    domains = eng.classify_request("Quero automatizar o deploy no GitHub Actions e melhorar os testes e logs")
    assert "automation" in domains
    assert "devops" in domains
    assert "testing" in domains
    assert "observability" in domains


def test_execution_plan_preserves_anti_duplication_sequence():
    plan = eng.build_execution_plan("Refatore a arquitetura do SaaS", existing_components=["orchestrator", "production_queue"])
    assert plan["anti_duplication_sequence"] == ["verify", "reuse", "extend", "create_if_missing"]
    assert plan["status"] == "planned"
    assert plan["existing_components"] == ["orchestrator", "production_queue"]


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


def test_release_readiness_is_conservative():
    checks = {"tests": True, "ci": True, "security": True, "migration_safety": True, "rollback": True, "secrets": True, "observability": True}
    assert eng.release_readiness(checks)["ready"] is True
    blocked = eng.release_readiness({"tests": True, "ci": True})
    assert blocked["ready"] is False
    assert "security" in blocked["missing"]


def test_public_entrypoint_returns_operational_agent_contract():
    result = eng.handle_saas_request("Automatize uma fila segura de geração", existing_components=["Fila de Produção"])
    assert result["agent"] == "Arquiteto SaaS & Automação"
    assert result["skill_count"] >= 80
    assert "automation" in result["domains"]
    assert result["non_negotiables"]

from agents import engenheiro_code_review_profundo as deep


def test_deep_review_agent_has_broad_semantic_skills():
    skills = deep.all_skills()
    assert "line-by-line review" in skills
    assert "Streamlit rerun model" in skills
    assert "business rules" in skills
    assert "API contract review" in skills
    assert "user journey" in skills
    assert "CI failure triage" in skills
    assert len(skills) >= 70


def test_escalation_when_runtime_broken_despite_green_tests():
    assert deep.escalation_required({"tests_pass_but_feature_broken": True}) is True


def test_escalation_after_repeated_failed_fix_attempts():
    assert deep.escalation_required({"failed_fix_attempts": 2}) is True
    assert deep.escalation_required({"failed_fix_attempts": 1}) is False


def test_escalation_when_ci_fails():
    assert deep.escalation_required({"ci_failed": True}) is True


def test_deep_review_plan_requires_runtime_evidence():
    plan = deep.build_deep_review_plan(
        "Jarvis Voz",
        symptom="A interface carrega, mas voz/interação não funciona em produção.",
        related_modules=["jarvis_voice.py", "jarvis_push_to_talk.py"],
        user_journey="Abrir Jarvis -> falar -> receber resposta falada",
    )
    assert plan["status"] == "ready_for_deep_review"
    assert "identify_root_cause" in plan["review_order"]
    assert "runtime_validation_when_applicable" in plan["required_evidence"]
    assert plan["anti_duplication_sequence"] == ["verify", "reuse", "extend", "create_if_missing"]


def test_ci_remediation_plan_is_feature_only_and_non_destructive():
    plan = deep.build_ci_remediation_plan(
        workflow_run=479,
        failed_jobs=["pytest"],
        feature_branch="feature/refinamento-24-prompt-mestre-compliance",
        protected_release_branch="release/2.0.0-rc5-skills",
    )
    assert plan["status"] == "ready_for_safe_remediation"
    assert "fetch_failed_job_logs" in plan["steps"]
    assert "apply_minimal_fix_on_feature_branch_only" in plan["steps"]
    assert "rerun_ci" in plan["steps"]
    assert "merge_pull_request" in plan["forbidden"]
    assert "modify_protected_release_branch" in plan["forbidden"]


def test_ci_remediation_refuses_release_as_feature_branch():
    try:
        deep.build_ci_remediation_plan(
            workflow_run=1,
            feature_branch="release/2.0.0-rc5-skills",
            protected_release_branch="release/2.0.0-rc5-skills",
        )
    except ValueError as exc:
        assert "não pode" in str(exc)
    else:
        raise AssertionError("A autocorreção não pode escrever diretamente na release protegida")


def test_finding_severity_prioritizes_security_and_main_flow():
    assert deep.classify_finding(security_or_data=True) == "P0"
    assert deep.classify_finding(breaks_main_flow=True) == "P1"
    assert deep.classify_finding(workaround=True) == "P2"
    assert deep.classify_finding(cosmetic_or_maintenance=True) == "P3"


def test_correction_gate_does_not_allow_false_fixed_status():
    blocked = deep.correction_gate({"root_cause": "x", "fix": "y"})
    assert blocked["status"] == "BLOCKED"
    assert "regression_test" in blocked["missing"]
    assert "tests_pass" in blocked["missing"]

    passed = deep.correction_gate({
        "root_cause": "provider contract mismatch",
        "fix": "aligned transport contract",
        "regression_test": "test provider payload",
        "tests_pass": True,
        "runtime_applicable": True,
        "runtime_validated": True,
    })
    assert passed["status"] == "PASS"
    assert passed["can_mark_fixed"] is True

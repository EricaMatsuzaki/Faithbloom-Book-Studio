"""Diagnostics report observed code separately from unverified runtime claims."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest

from agents import governanca_ia, governanca_dados, governanca_ti, ciberseguranca
from governance import run_all_diagnostics

ROOT = Path(__file__).resolve().parents[1]
AGENTS = [governanca_ia, governanca_dados, governanca_ti, ciberseguranca]


def _controls(report):
    return {item["code"]: item for item in report["findings"]}


@pytest.mark.parametrize("agent", AGENTS)
def test_diagnostics_never_turn_missing_evidence_into_runtime_pass(agent, monkeypatch):
    import requests
    def no_network(*args, **kwargs):
        pytest.fail("Governance diagnostics must not call external APIs")
    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    report = agent.run_diagnostic(ROOT)
    assert report["role_id"] == agent.ROLE_ID
    assert report["status"] in {"UNKNOWN", "FAIL"}
    assert report["counts"]["UNKNOWN"] > 0
    assert all(item["evidence"] for item in report["findings"] if item["status"] == "PASS")
    assert "certificação" in " ".join(report["limitations"])


@pytest.mark.parametrize("agent", AGENTS)
def test_missing_implementation_reports_failure_instead_of_doc_success(agent, tmp_path):
    (tmp_path / "README.md").write_text("All security and governance controls PASS", encoding="utf-8")
    report = agent.run_diagnostic(tmp_path)
    assert report["counts"]["FAIL"] > 0


def test_selected_project_is_preserved_and_private_content_is_not_reported():
    state = {
        "project_id": "personal-project-id",
        "cenas_texto": [{"numero": 1, "texto": "PRIVATE-MANUSCRIPT-DO-NOT-COPY"}],
        "generation_metadata": {"provider": "example", "model": "example", "request_id": "private-id"},
        "personagens": {"Mel": {"master": "private-original.png"}},
        "origin": "real_experience", "personal_data": {"name": "Person", "email": "private@example.com"},
    }
    before = deepcopy(state)
    reports = run_all_diagnostics(ROOT, state=state)
    assert state == before
    encoded = json.dumps(reports)
    assert "PRIVATE-MANUSCRIPT" not in encoded
    assert "private@example.com" not in encoded
    assert "private-original.png" not in encoded
    assert {report["role_id"] for report in reports} == {agent.ROLE_ID for agent in AGENTS}
    assert _controls(reports[0])["project_ai_trace"]["status"] == "PASS"
    assert _controls(reports[1])["real_experience_privacy"]["status"] == "UNKNOWN"


def test_fresh_explicit_evidence_is_distinct_from_configuration_flags():
    now = datetime.now(timezone.utc).isoformat()
    context = {"controls": {
        "provider_live_test": {"status": "PASS", "verified": True, "evidence_ref": "tests/observed-live.json", "observed_at": now},
        "human_approval_coverage": True,
        "ai_output_evaluation": {"status": "PASS", "verified": True, "evidence_ref": "tests/stale.json", "observed_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()},
    }}
    controls = _controls(governanca_ia.run_diagnostic(ROOT, context=context))
    assert controls["provider_live_test"]["status"] == "PASS"
    assert controls["human_approval_coverage"]["status"] == "UNKNOWN"
    assert controls["ai_output_evaluation"]["status"] == "UNKNOWN"


def test_corrupt_source_reports_exact_file_without_echoing_secrets(tmp_path):
    (tmp_path / "app.py").write_text("password='PRIVATE-SECRET'; broken syntax !\n", encoding="utf-8")
    report = governanca_ti.run_diagnostic(tmp_path)
    assert _controls(report)["it_syntax_app"]["status"] == "FAIL"
    assert "app.py:1" in _controls(report)["it_syntax_app"]["evidence"]
    assert "PRIVATE-SECRET" not in json.dumps(report)


def test_cybersecurity_distinguishes_definition_from_callsite(tmp_path):
    (tmp_path / "security_baseline.py").write_text("def authorize_action():\n    return True\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("from security_baseline import authorize_action\n", encoding="utf-8")
    report = ciberseguranca.run_diagnostic(tmp_path)
    assert _controls(report)["security_authorization"]["status"] == "PASS"
    assert _controls(report)["security_access_integration"]["status"] == "WARN"
    (tmp_path / "app.py").write_text("from security_baseline import authorize_action\nauthorize_action()\n", encoding="utf-8")
    report = ciberseguranca.run_diagnostic(tmp_path)
    assert _controls(report)["security_access_integration"]["status"] == "PASS"
    assert _controls(report)["authentication_live"]["status"] == "UNKNOWN"


def test_agents_are_exported_with_runtime_profiles_and_technical_contracts():
    import agent_skills
    assert agent_skills.validate_registry()["ok"]
    for agent in AGENTS:
        document = agent_skills.technical_profile_document(agent.ROLE_ID)
        assert document["runtime_entrypoints"] == ["run_diagnostic"]
        assert json.loads((ROOT / "skills" / f"{agent.ROLE_ID}.json").read_text(encoding="utf-8")) == document
        assert "LITERARY EXCELLENCE CHARTER" not in agent_skills.skill_contract(agent.ROLE_ID)

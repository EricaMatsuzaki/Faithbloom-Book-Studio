"""Job-specific configuration must fail closed before invoking a provider."""
from copy import deepcopy
from pathlib import Path
import shutil

import pytest

import agent_skills as registry
from agents.gerador_ideias import gerador_ideias_node


@pytest.mark.parametrize("role_id", sorted(registry.AGENT_PROFILES))
def test_every_role_has_concrete_executor_and_distinct_operational_contract(role_id):
    profile = registry.get_agent_profile(role_id)
    report = registry.require_role_ready(role_id)
    contract = profile["runtime_contract"]
    assert report["ok"] and report["status"] == "configured_for_execution"
    assert report["quality_validated"] is False
    assert report["production_validated"] is False
    assert contract["entrypoints"] and contract["inputs"] and contract["outputs"]
    assert set(contract["essential_skills"]) <= set(profile["skills"])
    assert profile["evidence_requirements"]


def _mutate_profile(monkeypatch, role_id="idea_generator"):
    profile = deepcopy(registry.AGENT_PROFILES[role_id])
    monkeypatch.setitem(registry.AGENT_PROFILES, role_id, profile)
    return profile


@pytest.mark.parametrize("failure", ["skill", "handoff", "output_contract", "unknown_handoff"])
def test_incomplete_job_cannot_call_provider(monkeypatch, failure):
    profile = _mutate_profile(monkeypatch)
    if failure == "skill":
        profile["skills"].remove("originalidade")
        assert len(profile["skills"]) > 3  # A generic count would miss this.
    elif failure == "handoff":
        profile["required_handoffs"].remove("theme_curator")
    elif failure == "output_contract":
        profile["runtime_contract"]["outputs"] = ["qualquer texto"]
    else:
        profile["required_handoffs"].append("fictional_missing_executor")
    calls = []
    with pytest.raises(registry.SkillReadinessError):
        gerador_ideias_node(1, [], lambda **kwargs: calls.append(kwargs))
    assert calls == []


def test_dependent_role_missing_essential_skill_blocks_before_provider(monkeypatch):
    profile = _mutate_profile(monkeypatch, "theme_curator")
    profile["skills"].remove("arco emocional")
    calls = []
    with pytest.raises(registry.SkillReadinessError, match="arco emocional"):
        gerador_ideias_node(1, [], lambda **kwargs: calls.append(kwargs))
    assert calls == []


def test_prompt_receives_role_specific_io_handoffs_and_limits():
    calls = []
    def provider(**kwargs):
        calls.append(kwargs)
        return [{"titulo_sugerido": "A descoberta", "situacao": "Mel divide uma semente com Manu",
                 "emocao_central": "alegria", "pista_licao": "amizade e partilha"}]
    gerador_ideias_node(1, [], provider)
    prompt = calls[0]["sistema"]
    for expected in ("Entradas necessárias", "temas_usados", "Saídas esperadas",
                     "theme_curator", "originalidade", "NÃO FAÇA"):
        assert expected in prompt


def _source_copy(tmp_path):
    root = Path(registry.__file__).parent
    paths = {registry.profile_module_path(p).relative_to(root) for p in registry.AGENT_PROFILES.values()}
    paths.update(Path(p) for p in registry.HANDOFF_SERVICES.values())
    paths.update(Path("agents") / module for module in registry.INHERITED_MODULE_PROFILES)
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    return tmp_path


@pytest.mark.parametrize("source", [
    '# def reference_gate(state): ...\n',
    'def reference_gate(state):\n    pass\n',
    'def reference_gate(state):\n    """Implement later."""\n    raise NotImplementedError\n',
])
def test_existing_service_path_without_real_entrypoint_is_not_a_handoff(tmp_path, source):
    root = _source_copy(tmp_path)
    (root / "biblical_reference_validator.py").write_text(source)
    with pytest.raises(registry.SkillReadinessError, match="entrypoint ausente"):
        registry.require_role_ready("theme_curator", root=root)


def test_registry_rejects_discarded_prompt_contract(tmp_path):
    root = _source_copy(tmp_path)
    source = (root / "agents/gerador_ideias.py").read_text()
    source = source.replace('prompt += skill_contract("idea_generator")',
                            'skill_contract("idea_generator")')
    (root / "agents/gerador_ideias.py").write_text(source)
    errors = registry.validate_registry(root, check_export=False)["errors"]
    assert any("contrato de idea_generator não utilizado" in error for error in errors)


def test_services_have_explicit_functions_without_fictional_llm_profiles():
    assert set(registry.HANDOFF_SERVICES) == set(registry.HANDOFF_SERVICE_CONTRACTS)
    assert "emotional_color_director" not in registry.AGENT_PROFILES
    assert "biblical_reference_validator" not in registry.AGENT_PROFILES
    assert "construir_mapa_emocional" in registry.HANDOFF_SERVICE_CONTRACTS["emotional_color_director"]


def test_fullstack_is_existing_engineer_role_not_an_unwired_duplicate():
    profile = registry.get_agent_profile("saas_automation_engineer")
    assert "full-stack application development" in profile["runtime_contract"]["essential_skills"]
    assert profile["execution"] == "deterministic"
    assert "full_stack_developer" not in registry.AGENT_PROFILES


def test_unknown_role_cannot_execute():
    with pytest.raises(registry.SkillReadinessError, match="contrato operacional ausente"):
        registry.require_role_ready("unregistered_agent")


def test_inventory_separates_static_presence_from_supplied_execution_evidence():
    supplied = {"idea_generator": [{"scope": "offline fake-provider activation", "result": "passed"}]}
    inventory = registry.agent_capability_inventory(runtime_evidence=supplied)
    assert inventory["role_count"] == len(registry.AGENT_PROFILES)
    role = next(row for row in inventory["roles"] if row["role_id"] == "idea_generator")
    assert role["contract_injected_in_source"] is True
    assert role["entrypoint_static_presence"]["gerador_ideias_node"] is True
    assert role["provided_runtime_evidence"] == supplied["idea_generator"]
    assert role["imported_callable_verified_by_inventory"] is False
    assert role["output_quality_verified_by_inventory"] is False
    role["provided_runtime_evidence"][0]["result"] = "changed"
    assert supplied["idea_generator"][0]["result"] == "passed"

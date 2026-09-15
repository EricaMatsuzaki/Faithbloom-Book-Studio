"""Regression tests for real routing, prompt context and honest completion state."""
from copy import deepcopy
from pathlib import Path
import json
import shutil

import pytest
import agent_skills as registry
import character_guide as guide
from agents.complementos_editoriais import gerar_complementos_editoriais, aplicar_complementos
from agents import engenheiro_saas_automacao as eng
from agents import engenheiro_code_review_profundo as deep
from jarvis_assistant import interpret_request
from jarvis_conversation import detect_safe_navigation
from jarvis_voice import build_spoken_reply

ROOT = Path(__file__).resolve().parents[1]


def _registry_copy(tmp_path):
    paths = {registry.profile_module_path(p).relative_to(ROOT) for p in registry.all_agent_profiles()}
    paths.update(Path("agents") / name for name in registry.INHERITED_MODULE_PROFILES)
    paths.update(Path(p) for p in registry.HANDOFF_SERVICES.values())
    paths.add(Path("skills/agent_profiles.json"))
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)
    return tmp_path


def test_registry_rejects_unregistered_agent_and_unknown_handoff(tmp_path, monkeypatch):
    root = _registry_copy(tmp_path)
    (root / "agents" / "forgotten.py").write_text("def run(): return True\n")
    profile = deepcopy(registry.AGENT_PROFILES["storyteller"])
    profile["required_handoffs"].append("nonexistent_service")
    monkeypatch.setitem(registry.AGENT_PROFILES, "storyteller", profile)
    errors = registry.validate_registry(root, check_export=False)["errors"]
    assert any("forgotten.py" in e for e in errors)
    assert any("nonexistent_service" in e for e in errors)


def test_registry_rejects_comment_only_contract_and_stale_export(tmp_path):
    root = _registry_copy(tmp_path)
    (root / "agents" / "roteirista.py").write_text('# storyteller skill_contract("storyteller")\n')
    (root / "skills" / "agent_profiles.json").write_text('{}')
    errors = registry.validate_registry(root)["errors"]
    assert any("contrato de storyteller" in e for e in errors)
    assert any("desatualizado" in e for e in errors)


def test_registry_export_matches_all_profiles_and_technical_scope():
    assert registry.validate_registry()["ok"]
    assert json.loads((ROOT / "skills/agent_profiles.json").read_text()) == registry.registry_document()
    assert "scene_director" in registry.AGENT_PROFILES
    assert "pedagogical_editor" in registry.AGENT_PROFILES
    contract = registry.skill_contract("deep_code_review_engineer")
    assert "line-by-line review" in contract
    assert "LITERARY EXCELLENCE CHARTER" not in contract
    assert registry.roles_for_module("agents/roteirista_autoral.py") == ["storyteller"]


@pytest.mark.parametrize("age,count", [("3-5", 2), ("3-8", 3), ("6-8", 3), ("9-12", 4)])
def test_pedagogical_editor_receives_story_and_validates_per_age(age, count, complete_editorial_extras):
    from age_profiles import perfil_etario
    count = perfil_etario(age)["perguntas_pedagogicas"]
    original = {"faixa_etaria": age, "versiculo_referencia": "Efésios 4:32",
                "cenas_texto": [{"numero": 1, "texto": "Mel devolveu a semente a Manu."}],
                "mapa_emocional": [{"numero": 1, "emocao": "gratidão"}]}
    before = deepcopy(original)
    def llm(**kwargs):
        assert "Editor Pedagógico" in kwargs["sistema"]
        assert original["cenas_texto"][0]["texto"] in kwargs["instrucao"]
        assert "gratidão" in kwargs["instrucao"]
        return complete_editorial_extras(count)
    output = gerar_complementos_editoriais(original, llm)
    assert len(output["pais_educadores"]["perguntas"]) == count
    assert original == before


@pytest.mark.parametrize("bad", ["empty_questions", "wrong_reference", "missing_message", "non_json"])
def test_incomplete_complements_never_replace_saved_work(bad, complete_editorial_extras):
    state = {"cenas_texto": [{"texto": "Uma cena."}], "boas_vindas": "Original", "versiculo_referencia": "Efésios 4:32"}
    output = complete_editorial_extras()
    if bad == "empty_questions": output["pais_educadores"]["perguntas"] = []
    if bad == "wrong_reference": output["ficha_pedagogica"]["versiculo_referencia"] = "Outra referência"
    if bad == "missing_message": output["pais_educadores"].pop("mensagem")
    if bad == "non_json": output = "texto"
    before = deepcopy(state)
    with pytest.raises(ValueError):
        gerar_complementos_editoriais(state, lambda **kwargs: output)
    with pytest.raises(ValueError):
        aplicar_complementos(state, output)
    assert state == before


def _ideas():
    return [{"id": letter, "titulo": letter, "cenario": "jardim " + letter,
             "acao": "Mel escuta o vaso", "poses": {"Mel": "deitada"}, "emocao": "curiosidade",
             "psicologia_cores": "verde no ambiente", "iluminacao": "suave", "camera": "plano " + letter,
             "por_que_funciona": "Mostra a curiosidade"} for letter in "ABC"]


def test_scene_director_gets_age_context_and_identity_without_generating_images(monkeypatch):
    def llm(system, instruction):
        assert "Diretor de Cena" in system
        assert "9–12 anos" in system
        assert "MAGIC_STORY" in instruction and "MAGIC_STYLE" in instruction
        assert "olhos" in instruction
        return {"ideas": _ideas()}
    monkeypatch.setattr(guide, "chamar_llm", llm)
    characters = [{"nome": "Mel", "dna": {"campos_bloqueados": {"olhos": "verdes"}}}]
    result = guide.suggest_scene_concepts("Mel escutou o vaso.", characters,
        project_context={"faixa_etaria": "9-12", "cenas_texto": [{"texto": "MAGIC_STORY"}], "style_dna": "MAGIC_STYLE"})
    assert [x["id"] for x in result] == list("ABC")


@pytest.mark.parametrize("problem", ["empty", "duplicate", "missing_camera"])
def test_scene_director_rejects_incomplete_or_identical_proposals(problem):
    ideas = _ideas()
    if problem == "empty": ideas = []
    if problem == "duplicate": ideas[1] = deepcopy(ideas[0])
    if problem == "missing_camera": ideas[0]["camera"] = ""
    with pytest.raises(ValueError): guide.validate_scene_concepts(ideas)


@pytest.mark.parametrize("prompt", ["Jarvis, faça code review", "auditar agentes", "Erro no app de calendário", "Engenheiro SaaS, revise meu projeto"])
def test_jarvis_routes_engineering_without_editorial_or_llm_fallback(prompt, monkeypatch):
    import jarvis_voice
    monkeypatch.setattr(jarvis_voice, "build_natural_reply", lambda *a, **k: pytest.fail("Unexpected model call"))
    result = interpret_request(prompt)
    assert result["project_type"] == "engineering"
    assert (ROOT / result["next_page"]).exists()
    assert detect_safe_navigation(prompt)["id"] == "engineering"
    assert "diagnóstico" in build_spoken_reply(prompt, result=result, natural=True)
    assert result["code_modified"] is False


def test_fictional_engineer_stays_in_editorial_route():
    assert interpret_request("Crie uma história sobre um engenheiro e sua filha")["project_type"] == "children_story"


def test_operational_diagnostic_runs_real_audits_without_marking_fixed():
    result = eng.run_diagnostic("auditar agentes", context={"tests_pass_but_feature_broken": True})
    assert result["registry"]["ok"]
    assert result["audit"]["stats"]["python_files"] > 100
    assert result["deep_review_plan"]["role_id"] == "deep_code_review_engineer"
    assert result["status"] == "diagnosed_not_fixed"
    assert result["tests_executed"] is False and result["code_modified"] is False


def test_source_selection_rejects_paths_outside_shipped_code():
    for path in ("../outside.py", ".streamlit/secrets.toml", "tests/test_refinamento21.py"):
        with pytest.raises(ValueError): eng.collect_review_sources([path])


def test_deep_review_receives_contract_and_verifies_evidence():
    def llm(**kwargs):
        assert "line-by-line review" in kwargs["sistema"]
        return {"summary": "Revisão", "limitations": ["Sem execução"], "findings": [{
            "severity": "P2", "module": "sample.py", "line": 1, "evidence": "return 1",
            "problem": "Exemplo", "proposed_fix": "Revisar contrato", "regression_test": "Verificar resultado"}]}
    report = deep.review_sources("Revisar", {"sample.py": "def run(): return 1"}, llm)
    assert report["status"] == "reviewed_not_fixed"
    assert not report["tests_executed"] and not report["code_modified"]
    with pytest.raises(ValueError, match="evidência"):
        deep.review_sources("Revisar", {"sample.py": "def run(): return 2"}, llm)


def test_deep_review_rejects_empty_or_oversized_context_before_llm():
    for sources in ({}, {"large.py": "x" * 40001}):
        with pytest.raises(ValueError): deep.review_sources("Revisar", sources, lambda **k: pytest.fail("Unexpected model call"))


def test_repeated_autopilot_incident_escalates_without_patching_code(monkeypatch):
    import editorial_remaster_autopilot as autopilot
    monkeypatch.setattr(autopilot, "save_run", lambda project, run: None)
    run = {"stages": {"visual_preflight": {}}}
    first = autopilot.record_incident({}, run, "visual_preflight", RuntimeError("Streamlit render failed"))
    second = autopilot.record_incident({}, run, "visual_preflight", RuntimeError("Streamlit render failed"))
    assert "deep_review_plan" not in first["engineering_plan"]
    assert second["engineering_plan"]["deep_review_plan"]["role_id"] == "deep_code_review_engineer"
    assert second["self_code_patch"] is False

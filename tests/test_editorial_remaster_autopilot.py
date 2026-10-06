from pathlib import Path

import editorial_remaster_autopilot as autopilot


def _project(tmp_path: Path) -> dict:
    root = tmp_path / "book"
    root.mkdir(parents=True, exist_ok=True)
    return {
        "id": "book-1",
        "titulo": "Livro Teste",
        "colecao": "Coleção Teste",
        "tipo_projeto": "story",
        "status_publicacao": "publicado",
        "pasta": str(root),
    }


def test_run_completes_checkpoints_and_reuses_them(monkeypatch, tmp_path):
    project = _project(tmp_path)
    run = autopilot.new_run(project, settings={"max_transient_retries": 0})
    calls = []

    def fake_stage(stage, current, project_arg, chamar_llm):
        calls.append(stage)
        return {"state": current.get("remaster_state") or {}, "result": {"stage": stage}}

    monkeypatch.setattr(autopilot, "_execute_stage", fake_stage)
    finished = autopilot.run_autopilot(project, run, lambda **_: {})

    assert finished["status"] == "needs_author_review"
    assert calls == autopilot.STAGES
    assert all(finished["stages"][stage]["status"] == "completed" for stage in autopilot.STAGES)

    calls.clear()
    resumed = autopilot.run_autopilot(project, finished, lambda **_: {})
    assert resumed["status"] == "needs_author_review"
    assert calls == []


def test_transient_failure_retries_and_continues(monkeypatch, tmp_path):
    project = _project(tmp_path)
    run = autopilot.new_run(project, settings={"max_transient_retries": 1})
    attempts = {stage: 0 for stage in autopilot.STAGES}

    def fake_stage(stage, current, project_arg, chamar_llm):
        attempts[stage] += 1
        if stage == autopilot.STAGES[0] and attempts[stage] == 1:
            raise RuntimeError("provider timeout 503")
        return {"state": current.get("remaster_state") or {}, "result": {"ok": True}}

    monkeypatch.setattr(autopilot, "_execute_stage", fake_stage)
    finished = autopilot.run_autopilot(project, run, lambda **_: {}, sleep_fn=lambda _: None)

    assert finished["status"] == "needs_author_review"
    assert attempts[autopilot.STAGES[0]] == 2
    assert finished["incidents"][0]["action"] == "retry"
    assert finished["incidents"][0]["owner"] == "runtime_retry"


def test_engineering_failure_blocks_and_preserves_resume_checkpoint(monkeypatch, tmp_path):
    project = _project(tmp_path)
    run = autopilot.new_run(project, settings={"max_transient_retries": 0})

    def fake_stage(stage, current, project_arg, chamar_llm):
        if stage == "style_and_character_resolution":
            raise RuntimeError("storage state integration failed")
        return {"state": current.get("remaster_state") or {}, "result": {"ok": True}}

    monkeypatch.setattr(autopilot, "_execute_stage", fake_stage)
    blocked = autopilot.run_autopilot(project, run, lambda **_: {})

    assert blocked["status"] == "blocked"
    assert blocked["stages"]["style_and_character_resolution"]["status"] == "blocked"
    incident = blocked["incidents"][-1]
    assert incident["owner"] == "saas_automation_engineer"
    assert incident["resume_from"] == "style_and_character_resolution"
    assert incident["self_code_patch"] is False
    assert blocked["stages"]["final_review_package"]["status"] == "pending"


def test_fullstack_failure_is_routed_to_fullstack():
    failure = autopilot.classify_failure(RuntimeError("Streamlit session_state navigation failed"), "visual_handoff")
    assert failure["owner"] == "fullstack_developer"
    assert failure["action"] == "engineering_repair"


def test_editorial_failure_returns_to_editorial_specialist():
    failure = autopilot.classify_failure(RuntimeError("lição de moral não preservada"), "storyteller_enrichment")
    assert failure["owner"] == "editorial_specialist"
    assert failure["action"] == "editorial_remediation"


def test_final_approval_never_promotes_master_or_autopublishes(monkeypatch, tmp_path):
    project = _project(tmp_path)
    run = autopilot.new_run(project)
    run["status"] = "needs_author_review"
    run["final_review_package"] = {"ready": True}
    run = autopilot.save_run(project, run)

    approved = autopilot.approve_final_remaster(project, run, approved=True)

    assert approved["status"] == "completed"
    assert approved["author_final_approval"] is True
    assert approved["master_promotion_allowed"] is False
    assert approved["auto_publish"] is False

from final_prelaunch import build_prelaunch_test_plan, final_prelaunch_gate, final_stable_promotion_gate
from security_baseline import PRIVILEGED_REQUIRED, PRODUCTION_REQUIRED


def _evidence_all_done():
    return {
        x["id"]: {"done": True, "note": "evidência real registrada"}
        for x in build_prelaunch_test_plan()
        if x["id"] != "security_by_default"
    }


def _pilot_ready():
    return {
        "ready_for_next_candidate": True,
        "profiles_completed": ["mel_master", "mel_natal", "bolufinhas"],
        "profiles_required": ["mel_master", "mel_natal", "bolufinhas"],
        "open_blocking_bugs": [],
        "profiles_missing": [],
        "pilot_blockers": [],
    }


def _security_controls():
    controls = {name: True for name in PRODUCTION_REQUIRED}
    controls.update({name: True for name in PRIVILEGED_REQUIRED})
    return controls


def test_cloud_evidence_is_mandatory_for_rc4():
    gate = final_prelaunch_gate(
        {}, qa_ok=True, deployment_ready=True, pilot_status=_pilot_ready(),
        source_manifest={"source_fingerprint": "abc", "file_count": 10},
        security_controls=_security_controls(),
    )
    assert gate["status"] == "BLOCKED"
    assert any(x["id"] == "real_cloud_e2e" and not x["ok"] for x in gate["checks"])


def test_pilot_gate_is_mandatory_for_rc4():
    bad = _pilot_ready(); bad["ready_for_next_candidate"] = False; bad["profiles_missing"] = ["bolufinhas"]
    gate = final_prelaunch_gate(
        _evidence_all_done(), qa_ok=True, deployment_ready=True, pilot_status=bad,
        source_manifest={"source_fingerprint": "abc", "file_count": 10},
        security_controls=_security_controls(),
    )
    assert gate["status"] == "BLOCKED"
    assert any(x["id"] == "real_pilots" and not x["ok"] for x in gate["checks"])


def test_security_gate_is_mandatory_for_rc4():
    gate = final_prelaunch_gate(
        _evidence_all_done(), qa_ok=True, deployment_ready=True, pilot_status=_pilot_ready(),
        source_manifest={"source_fingerprint": "abc", "file_count": 10},
        security_controls={},
    )
    assert gate["status"] == "BLOCKED"
    assert gate["security_gate"]["status"] == "BLOCKED"
    assert any(x["id"] == "security_by_default" and not x["ok"] for x in gate["checks"])


def test_rc4_gate_can_pass_with_all_evidence_and_security():
    gate = final_prelaunch_gate(
        _evidence_all_done(), qa_ok=True, deployment_ready=True, pilot_status=_pilot_ready(),
        source_manifest={"source_fingerprint": "abc", "file_count": 10},
        security_controls=_security_controls(),
    )
    assert gate["status"] == "PASS"
    assert gate["ready_to_create_rc4"] is True
    assert gate["security_gate"]["status"] == "PASS"


def test_final_stable_gate_requires_security_manual_signoff_and_current_source():
    candidate = {
        "source_manifest": {"source_fingerprint": "abc"},
        "gate": {"status": "PASS", "security_gate": {"status": "PASS"}},
        "security_gate": {"status": "PASS"},
        "manual_signoff": {"approved": False, "actor": ""},
    }
    gate = final_stable_promotion_gate(candidate, current_manifest={"source_fingerprint": "abc", "file_count": 1})
    assert gate["status"] == "BLOCKED"
    candidate["manual_signoff"] = {"approved": True, "actor": "Erica"}
    gate = final_stable_promotion_gate(candidate, current_manifest={"source_fingerprint": "abc", "file_count": 1})
    assert gate["status"] == "PASS"


def test_final_stable_gate_blocks_candidate_without_security_evidence():
    candidate = {
        "source_manifest": {"source_fingerprint": "abc"},
        "gate": {"status": "PASS"},
        "manual_signoff": {"approved": True, "actor": "Erica"},
    }
    gate = final_stable_promotion_gate(candidate, current_manifest={"source_fingerprint": "abc", "file_count": 1})
    assert gate["status"] == "BLOCKED"
    assert any(x["id"] == "security_gate" and not x["ok"] for x in gate["checks"])

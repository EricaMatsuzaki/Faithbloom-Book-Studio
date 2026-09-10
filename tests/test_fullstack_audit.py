from pathlib import Path

import scripts_fullstack_audit as audit


def test_repository_audit_scans_every_python_file_and_is_read_only():
    report = audit.audit_repository()
    expected = [
        p for p in audit.ROOT.rglob("*.py")
        if not any(part in audit.EXCLUDED_DIRS for part in p.parts)
    ]
    assert report["stats"]["python_files"] == len(expected)
    assert report["policy"]["read_only_audit"] is True
    assert report["policy"]["no_ai_calls"] is True
    assert report["policy"]["no_credit_usage"] is True


def test_audit_has_no_objective_blockers_in_current_repository():
    report = audit.audit_repository()
    blockers = [x for x in report["issues"] if x.get("severity") == "blocker"]
    assert blockers == []


def test_duplicate_detection_never_auto_merges_or_deletes():
    report = audit.audit_repository()
    assert report["policy"]["warnings_do_not_auto_delete_or_merge"] is True
    assert report["policy"]["anti_duplication"] == ["verify", "reuse", "extend", "create_if_missing"]


def test_all_navigation_page_references_resolve():
    report = audit.audit_repository()
    broken = [x for x in report["issues"] if x.get("code") == "broken_page_reference"]
    assert broken == []


def test_report_path_is_repository_local_json():
    assert audit.REPORT_PATH.parent == audit.ROOT
    assert audit.REPORT_PATH.name == "FULLSTACK_AUDIT_REPORT.json"

import pytest

import orchestrator_editorial as oe


def test_all_official_project_types_are_registered():
    assert len(oe.PROJECT_TYPES) == 16
    assert "children_story" in oe.PROJECT_TYPES
    assert "study_book" in oe.PROJECT_TYPES
    assert "coloring_book" in oe.PROJECT_TYPES
    assert "comic" in oe.PROJECT_TYPES


def test_route_reuses_shared_localization_and_distribution_once():
    plan = oe.build_editorial_route(
        "children_story",
        origin="bible",
        audience="3_8",
        editorial_line="christian",
    )
    assert plan["route"].count("translation_localization") == 1
    assert plan["route"].count("publishing_platform_engine") == 1
    assert plan["route"].count("publishing_distribution_center") == 1
    assert plan["duplicate_capabilities"] is False


def test_bible_guard_is_added_for_christian_or_bible_projects():
    christian = oe.build_editorial_route("study_book", editorial_line="christian")
    bible_origin = oe.build_editorial_route(
        "children_story",
        origin="bible",
        editorial_line="universal_educational",
    )
    secular = oe.build_editorial_route(
        "study_book",
        origin="own_idea",
        editorial_line="universal_educational",
    )
    assert "bible_guard" in christian["route"]
    assert "bible_guard" in bible_origin["route"]
    assert "bible_guard" not in secular["route"]


def test_derived_media_extend_route_without_replacing_existing_studios():
    plan = oe.build_editorial_route(
        "comic",
        derived_outputs=["audiobook", "animation", "music"],
    )
    assert "audiobook_studio" in plan["route"]
    assert "animation_video" in plan["route"]
    assert "music" in plan["route"]
    assert plan["capabilities"]["animation_video"]["status"] == "provider_integration_pending"
    assert plan["capabilities"]["music"]["status"] == "provider_integration_pending"


def test_anti_duplication_report_flags_manual_duplicate_or_unknown():
    clean = oe.build_editorial_route("activity_book")
    assert oe.anti_duplication_report(clean)["ok"] is True

    bad = dict(clean)
    bad["route"] = clean["route"] + ["translation_localization", "invented_studio"]
    report = oe.anti_duplication_report(bad)
    assert report["ok"] is False
    assert "translation_localization" in report["duplicates"]
    assert "invented_studio" in report["unknown"]


def test_unknown_values_fail_loudly():
    with pytest.raises(KeyError):
        oe.build_editorial_route("not_a_project")
    with pytest.raises(KeyError):
        oe.build_editorial_route("children_story", origin="not_an_origin")
    with pytest.raises(KeyError):
        oe.build_editorial_route("children_story", derived_outputs=["not_an_output"])

import pytest

import creative_studios as cs


def test_registry_exposes_idea_animation_and_music_studios():
    ids = {item["id"] for item in cs.list_studios()}
    assert {"idea_vault", "animation_video", "music"}.issubset(ids)


def test_animation_and_music_are_not_claimed_as_provider_ready():
    for studio_id in ("animation_video", "music"):
        status = cs.provider_readiness(studio_id)
        assert status["architecture_ready"] is True
        assert status["provider_connected"] is False
        assert status["can_generate_final_media"] is False
        assert status["status"] == cs.STATUS_PROVIDER_PENDING


def test_derivative_plan_never_auto_publishes_or_promotes_master():
    plan = cs.build_derivative_plan(
        "book_to_animation",
        source_id="book-1",
        title="Filminho da Mel",
        approved_masters={"character": ["mel-master"], "world": ["jardim-master"]},
    )
    assert plan["auto_publish"] is False
    assert plan["auto_promote_master"] is False
    assert plan["requires_human_approval"] is True
    assert plan["provider_bound"] is False
    assert plan["approved_masters"]["character"] == ["mel-master"]


def test_music_studio_has_originality_guard_and_human_checkpoints():
    music = cs.get_studio("music")
    assert "music_originality_guard" in music["specialists"]
    assert "letra quando houver" in music["approval_gates"]
    assert any("não copiar" in rule for rule in music["shared_guardrails"])


def test_unknown_studio_and_path_fail_explicitly():
    with pytest.raises(KeyError):
        cs.get_studio("unknown")
    with pytest.raises(KeyError):
        cs.build_derivative_plan("unknown", source_id="x")

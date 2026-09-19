from jarvis_handoff_inbox import (
    capture_legacy_handoff,
    enqueue_handoff,
    infer_character_name,
    list_handoffs,
    update_handoff,
)


def _package(pid="handoff-1", request="melhore as imagens do Téo como a Mel"):
    return {
        "id": pid,
        "request": request,
        "route": {"id": "character_reference", "label": "Character Universe"},
        "files": [
            {"name": "Teo_1.jpg", "kind": "image", "data": b"one"},
            {"name": "Teo_2.jpg", "kind": "image", "data": b"two"},
        ],
    }


def test_infers_teo_from_request_without_confusing_mel_reference():
    assert infer_character_name(_package()) == "Téo"


def test_infers_manu_from_filenames_when_request_is_generic():
    package = _package(request="quero melhorar estas imagens como foi feito antes")
    package["files"] = [
        {"name": "Manu_1.jpg", "kind": "image", "data": b"one"},
        {"name": "Manu_2.jpg", "kind": "image", "data": b"two"},
    ]
    assert infer_character_name(package) == "Manu"


def test_enqueue_is_idempotent_and_preserves_multiple_requests():
    state = {}
    enqueue_handoff(state, _package("handoff-teo"))
    enqueue_handoff(state, _package("handoff-teo"))
    enqueue_handoff(state, _package("handoff-manu", "melhore as imagens da Manu"))
    items = list_handoffs(state, route_id="character_reference")
    assert len(items) == 2
    assert {item["id"] for item in items} == {"handoff-teo", "handoff-manu"}


def test_legacy_single_slot_is_migrated_into_inbox():
    state = {"jarvis_handoff_package": _package("handoff-old")}
    captured = capture_legacy_handoff(state, route_id="character_reference")
    assert captured["id"] == "handoff-old"
    assert "jarvis_handoff_package" not in state
    assert list_handoffs(state, route_id="character_reference")[0]["status"] == "received"


def test_completed_item_is_hidden_from_active_inbox_but_history_is_preserved():
    state = {}
    enqueue_handoff(state, _package("handoff-done"))
    update_handoff(state, "handoff-done", status="completed", character_id="char-123")
    assert list_handoffs(state, route_id="character_reference", include_done=False) == []
    history = list_handoffs(state, route_id="character_reference", include_done=True)
    assert history[0]["character_id"] == "char-123"

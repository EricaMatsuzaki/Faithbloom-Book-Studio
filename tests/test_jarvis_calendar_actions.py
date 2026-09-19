from datetime import datetime
from zoneinfo import ZoneInfo

import jarvis_daily_intelligence as daily


def test_calendar_write_is_fail_closed(monkeypatch):
    monkeypatch.delenv("JARVIS_CALENDAR_WRITE_ENABLED", raising=False)
    assert daily.calendar_write_is_enabled() is False


def test_prepare_create_calendar_action_never_executes_network(monkeypatch):
    called = {"network": False}
    monkeypatch.setattr(daily, "create_calendar_event", lambda *a, **k: called.__setitem__("network", True))
    now = datetime(2026, 9, 12, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    plan = daily.prepare_calendar_action("Agende compromisso dentista amanhã às 15h", now=now)
    assert plan is not None
    assert plan["action"] == "create"
    assert plan["ready"] is True
    assert plan["title"].casefold() == "dentista"
    assert plan["start"].day == 13
    assert plan["start"].hour == 15
    assert called["network"] is False


def test_prepare_update_requires_unique_event(monkeypatch):
    now = datetime(2026, 9, 12, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    monkeypatch.setattr(daily, "find_upcoming_events_by_title", lambda *a, **k: [
        {"id": "evt-1", "title": "Dentista", "start": now, "end": None, "all_day": False, "location": "", "description": ""}
    ])
    plan = daily.prepare_calendar_action("Mude o compromisso Dentista para amanhã às 16h", now=now)
    assert plan is not None
    assert plan["action"] == "update"
    assert plan["ready"] is True
    assert plan["event_id"] == "evt-1"
    assert plan["start"].hour == 16


def test_execute_create_only_after_explicit_caller_confirmation(monkeypatch):
    now = datetime(2026, 9, 13, 15, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    monkeypatch.setattr(daily, "create_calendar_event", lambda title, start, **kwargs: {"id": "evt-1", "title": title, "start": start})
    plan = {"action": "create", "ready": True, "title": "Dentista", "start": now}
    result = daily.execute_calendar_action(plan)
    assert result["id"] == "evt-1"
    assert result["title"] == "Dentista"


def test_execute_rejects_unready_plan():
    try:
        daily.execute_calendar_action({"action": "create", "ready": False})
    except ValueError as exc:
        assert "pronta" in str(exc)
    else:
        raise AssertionError("Unready calendar action must not execute")

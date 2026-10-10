from datetime import datetime
from zoneinfo import ZoneInfo

import jarvis_daily_intelligence as daily


def test_date_and_greeting_are_local_and_deterministic():
    now = datetime(2026, 9, 12, 11, 14, tzinfo=ZoneInfo("Asia/Tokyo"))
    assert daily.format_date_pt(now) == "sábado, 12 de setembro"
    assert daily.greeting_for(now) == "Bom dia"


def test_calendar_stays_read_only_and_not_configured_without_oauth(monkeypatch):
    monkeypatch.delenv("GOOGLE_CALENDAR_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CALENDAR_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_CALENDAR_REFRESH_TOKEN", raising=False)
    assert daily.calendar_is_configured() is False


def test_next_event_selects_future_event():
    tz = ZoneInfo("Asia/Tokyo")
    now = datetime(2026, 9, 12, 9, 0, tzinfo=tz)
    events = [
        {"title": "Passado", "start": datetime(2026, 9, 12, 8, 0, tzinfo=tz)},
        {"title": "Almoço", "start": datetime(2026, 9, 12, 12, 30, tzinfo=tz)},
        {"title": "Noite", "start": datetime(2026, 9, 12, 19, 0, tzinfo=tz)},
    ]
    assert daily.next_event(events, now)["title"] == "Almoço"


def test_daily_briefing_combines_date_weather_and_calendar_without_llm(monkeypatch):
    tz = ZoneInfo("Asia/Tokyo")
    now = datetime(2026, 9, 12, 11, 14, tzinfo=tz)
    monkeypatch.setattr(daily, "calendar_is_configured", lambda: True)
    monkeypatch.setattr(daily, "_weather_summary", lambda location: (
        "Em Toyohashi, agora faz 27 graus, com céu limpo.",
        "Em Toyohashi, agora faz 27 graus, com céu limpo.",
    ))
    monkeypatch.setattr(daily, "fetch_today_events", lambda **kwargs: [
        {"id": "1", "title": "Reunião", "start": datetime(2026, 9, 12, 14, 0, tzinfo=tz), "all_day": False, "location": ""}
    ])
    result = daily.build_daily_intelligence(location="Toyohashi, Japan", timezone_name="Asia/Tokyo", now=now)
    assert "sábado, 12 de setembro" in result["spoken"]
    assert "27 graus" in result["spoken"]
    assert "Reunião" in result["spoken"]
    assert result["calendar_connected"] is True
    assert result["next_event"]["title"] == "Reunião"
    assert "total_build_s" in result["timings"]

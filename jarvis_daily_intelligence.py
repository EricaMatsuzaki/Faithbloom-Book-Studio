"""Jarvis Daily Intelligence: data/hora, clima, agenda e briefing automático.

Reutiliza o módulo de clima existente e acessa Google Calendar somente em leitura.
Nenhuma credencial é persistida no código: a integração usa variáveis de ambiente
/ Streamlit Secrets configuradas no runtime.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests

from jarvis_weather import fetch_weather, WMO_PT

TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
DEFAULT_TIMEZONE = os.environ.get("JARVIS_TIMEZONE", "Asia/Tokyo")
DEFAULT_LOCATION = os.environ.get("JARVIS_BRIEFING_LOCATION", "Toyohashi, Japan")

WEEKDAYS_PT = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
MONTHS_PT = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


class JarvisCalendarError(RuntimeError):
    pass


def local_now(timezone_name: str = DEFAULT_TIMEZONE) -> datetime:
    try:
        return datetime.now(ZoneInfo(timezone_name))
    except Exception:
        return datetime.now().astimezone()


def format_date_pt(now: datetime) -> str:
    return f"{WEEKDAYS_PT[now.weekday()]}, {now.day} de {MONTHS_PT[now.month - 1]}"


def greeting_for(now: datetime) -> str:
    return "Bom dia" if now.hour < 12 else "Boa tarde" if now.hour < 18 else "Boa noite"


def _calendar_credentials() -> dict[str, str]:
    return {
        "client_id": os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET", "").strip(),
        "refresh_token": os.environ.get("GOOGLE_CALENDAR_REFRESH_TOKEN", "").strip(),
        "calendar_id": os.environ.get("GOOGLE_CALENDAR_ID", "primary").strip() or "primary",
    }


def calendar_is_configured() -> bool:
    creds = _calendar_credentials()
    return bool(creds["client_id"] and creds["client_secret"] and creds["refresh_token"])


def _refresh_access_token(*, poster: Callable = requests.post) -> str:
    creds = _calendar_credentials()
    if not calendar_is_configured():
        raise JarvisCalendarError("Google Calendar ainda não foi conectado ao FaithBloom.")
    try:
        response = poster(
            TOKEN_URL,
            data={
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "refresh_token": creds["refresh_token"],
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise JarvisCalendarError("Não consegui autenticar o Google Calendar agora.") from exc
    except ValueError as exc:
        raise JarvisCalendarError("O Google Calendar retornou uma resposta inválida.") from exc
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise JarvisCalendarError("O Google Calendar não retornou um token de acesso.")
    return token


def _event_start(event: dict[str, Any], timezone_name: str) -> tuple[datetime | None, bool]:
    start = event.get("start") or {}
    if start.get("dateTime"):
        value = str(start["dateTime"]).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
            return dt.astimezone(ZoneInfo(timezone_name)), False
        except Exception:
            return None, False
    if start.get("date"):
        try:
            dt = datetime.fromisoformat(str(start["date"]))
            return dt.replace(tzinfo=ZoneInfo(timezone_name)), True
        except Exception:
            return None, True
    return None, False


def fetch_today_events(
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    now: datetime | None = None,
    getter: Callable = requests.get,
    poster: Callable = requests.post,
) -> list[dict[str, Any]]:
    now = now or local_now(timezone_name)
    tz = ZoneInfo(timezone_name)
    now = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    start_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = start_day + timedelta(days=1)
    token = _refresh_access_token(poster=poster)
    creds = _calendar_credentials()
    url = CALENDAR_EVENTS_URL.format(calendar_id=requests.utils.quote(creds["calendar_id"], safe=""))
    try:
        response = getter(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={
                "timeMin": start_day.isoformat(),
                "timeMax": end_day.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 25,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise JarvisCalendarError("Não consegui consultar sua agenda do Google Calendar agora.") from exc
    except ValueError as exc:
        raise JarvisCalendarError("Sua agenda retornou uma resposta inválida.") from exc

    events: list[dict[str, Any]] = []
    for item in data.get("items") or []:
        if item.get("status") == "cancelled":
            continue
        start, all_day = _event_start(item, timezone_name)
        events.append({
            "id": item.get("id"),
            "title": str(item.get("summary") or "Compromisso sem título"),
            "start": start,
            "all_day": all_day,
            "location": str(item.get("location") or ""),
        })
    return events


def next_event(events: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    candidates = [e for e in events if e.get("start") is not None and e["start"] >= now]
    return min(candidates, key=lambda e: e["start"]) if candidates else None


def _weather_summary(location: str) -> tuple[str, str]:
    weather = fetch_weather(location)
    place = weather["place"]
    current = weather["current"]
    daily = weather["daily"]
    codes = daily.get("weather_code") or []
    maxs = daily.get("temperature_2m_max") or []
    mins = daily.get("temperature_2m_min") or []
    rain = daily.get("precipitation_probability_max") or []
    current_temp = round(float(current.get("temperature_2m", 0)))
    current_code = int(current.get("weather_code", -1))
    condition = WMO_PT.get(current_code, "condição variável")
    high = round(float(maxs[0])) if maxs else None
    low = round(float(mins[0])) if mins else None
    rain_chance = round(float(rain[0])) if rain else None
    city = str(place.get("name") or location)
    spoken = f"Em {city}, agora faz {current_temp} graus, com {condition}"
    if high is not None and low is not None:
        spoken += f"; hoje a máxima é {high} e a mínima {low} graus"
    if rain_chance is not None and rain_chance >= 30:
        spoken += f", com {rain_chance} por cento de chance de chuva"
    spoken += "."
    detail = spoken
    if codes:
        detail += f" Condição prevista para hoje: {WMO_PT.get(int(codes[0]), 'variável')}."
    return spoken, detail


def _calendar_summary(events: list[dict[str, Any]], now: datetime) -> tuple[str, str]:
    if not events:
        return "Você não tem compromissos no calendário hoje.", "Nenhum compromisso encontrado para hoje."
    upcoming = next_event(events, now)
    count = len(events)
    spoken = f"Você tem {count} compromisso{'s' if count != 1 else ''} hoje."
    if upcoming:
        if upcoming.get("all_day"):
            spoken += f" O próximo é {upcoming['title']}, durante o dia todo."
        else:
            spoken += f" O próximo é {upcoming['title']}, às {upcoming['start'].strftime('%H:%M')}."
    lines = []
    for event in events:
        when = "Dia todo" if event.get("all_day") else event["start"].strftime("%H:%M") if event.get("start") else "Horário não informado"
        line = f"{when} — {event['title']}"
        if event.get("location"):
            line += f" · {event['location']}"
        lines.append(line)
    return spoken, "\n".join(lines)


def build_daily_intelligence(
    *,
    location: str = DEFAULT_LOCATION,
    timezone_name: str = DEFAULT_TIMEZONE,
    now: datetime | None = None,
    include_calendar: bool = True,
) -> dict[str, Any]:
    """Build a short spoken briefing plus detailed screen data and latency metrics."""
    started = time.perf_counter()
    now = now or local_now(timezone_name)
    timings: dict[str, float] = {}
    weather_spoken = "Não consegui consultar o clima nesta abertura."
    weather_detail = weather_spoken
    calendar_spoken = ""
    calendar_detail = ""
    calendar_connected = calendar_is_configured()
    events: list[dict[str, Any]] = []

    def weather_job():
        t = time.perf_counter()
        result = _weather_summary(location)
        return result, time.perf_counter() - t

    def calendar_job():
        t = time.perf_counter()
        result = fetch_today_events(timezone_name=timezone_name, now=now)
        return result, time.perf_counter() - t

    with ThreadPoolExecutor(max_workers=2) as executor:
        wf = executor.submit(weather_job)
        cf = executor.submit(calendar_job) if include_calendar and calendar_connected else None
        try:
            (weather_spoken, weather_detail), timings["weather_s"] = wf.result()
        except Exception:
            timings["weather_s"] = time.perf_counter() - started
        if cf is not None:
            try:
                events, timings["calendar_s"] = cf.result()
                calendar_spoken, calendar_detail = _calendar_summary(events, now)
            except Exception as exc:
                calendar_spoken = "Sua agenda ficou indisponível nesta abertura."
                calendar_detail = str(exc)
        elif include_calendar:
            calendar_spoken = "Seu Google Calendar ainda precisa ser conectado ao FaithBloom."
            calendar_detail = "Integração de calendário aguardando configuração OAuth somente leitura."

    opening = greeting_for(now)
    date_text = format_date_pt(now)
    spoken_parts = [f"{opening}, Erica. Hoje é {date_text}.", weather_spoken]
    if calendar_spoken:
        spoken_parts.append(calendar_spoken)
    spoken = " ".join(p.strip() for p in spoken_parts if p.strip())
    timings["total_build_s"] = time.perf_counter() - started

    return {
        "spoken": spoken,
        "date": date_text,
        "local_time": now.strftime("%H:%M"),
        "timezone": timezone_name,
        "location": location,
        "weather_detail": weather_detail,
        "calendar_connected": calendar_connected,
        "calendar_detail": calendar_detail,
        "events": events,
        "next_event": next_event(events, now),
        "timings": timings,
    }

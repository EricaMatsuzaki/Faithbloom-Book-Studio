"""Jarvis Daily Intelligence: data/hora, clima, agenda e ações seguras no Google Calendar.

Reutiliza o módulo de clima existente e o mesmo OAuth do Google Calendar. Leitura
pode acontecer automaticamente; criação/alteração de eventos é fail-closed e só
é executada depois de confirmação explícita da usuária no Jarvis.
"""
from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests

from jarvis_weather import fetch_weather, WMO_PT

OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"
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


def calendar_write_is_enabled() -> bool:
    return os.environ.get("JARVIS_CALENDAR_WRITE_ENABLED", "").strip().casefold() in {"1", "true", "yes", "on"}


def _refresh_access_token(*, poster: Callable = requests.post) -> str:
    creds = _calendar_credentials()
    if not calendar_is_configured():
        raise JarvisCalendarError("Google Calendar ainda não foi conectado ao FaithBloom.")
    try:
        response = poster(
            OAUTH_ENDPOINT,
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


def _calendar_url(event_id: str | None = None) -> str:
    creds = _calendar_credentials()
    base = CALENDAR_EVENTS_URL.format(calendar_id=requests.utils.quote(creds["calendar_id"], safe=""))
    return f"{base}/{requests.utils.quote(event_id, safe='')}" if event_id else base


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


def _event_end(event: dict[str, Any], timezone_name: str) -> datetime | None:
    end = event.get("end") or {}
    raw = end.get("dateTime") or end.get("date")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
        return dt.astimezone(ZoneInfo(timezone_name))
    except Exception:
        return None


def _normalize_event(item: dict[str, Any], timezone_name: str) -> dict[str, Any]:
    start, all_day = _event_start(item, timezone_name)
    return {
        "id": item.get("id"),
        "title": str(item.get("summary") or "Compromisso sem título"),
        "start": start,
        "end": _event_end(item, timezone_name),
        "all_day": all_day,
        "location": str(item.get("location") or ""),
        "description": str(item.get("description") or ""),
    }


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
    try:
        response = getter(
            _calendar_url(),
            headers={"Authorization": f"Bearer {token}"},
            params={"timeMin": start_day.isoformat(), "timeMax": end_day.isoformat(), "singleEvents": "true", "orderBy": "startTime", "maxResults": 25},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise JarvisCalendarError("Não consegui consultar sua agenda do Google Calendar agora.") from exc
    except ValueError as exc:
        raise JarvisCalendarError("Sua agenda retornou uma resposta inválida.") from exc
    return [_normalize_event(item, timezone_name) for item in (data.get("items") or []) if item.get("status") != "cancelled"]


def find_upcoming_events_by_title(
    title: str,
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    now: datetime | None = None,
    getter: Callable = requests.get,
    poster: Callable = requests.post,
) -> list[dict[str, Any]]:
    query = (title or "").strip()
    if not query:
        return []
    now = now or local_now(timezone_name)
    token = _refresh_access_token(poster=poster)
    try:
        response = getter(
            _calendar_url(),
            headers={"Authorization": f"Bearer {token}"},
            params={"timeMin": now.isoformat(), "singleEvents": "true", "orderBy": "startTime", "q": query, "maxResults": 10},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise JarvisCalendarError("Não consegui localizar esse compromisso no Google Calendar agora.") from exc
    items = [_normalize_event(item, timezone_name) for item in (data.get("items") or []) if item.get("status") != "cancelled"]
    norm = query.casefold()
    exact = [item for item in items if item["title"].casefold() == norm]
    return exact or [item for item in items if norm in item["title"].casefold()]


def create_calendar_event(
    title: str,
    start: datetime,
    *,
    end: datetime | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
    location: str = "",
    description: str = "",
    poster: Callable = requests.post,
) -> dict[str, Any]:
    if not calendar_write_is_enabled():
        raise JarvisCalendarError("A escrita no Google Calendar ainda não está habilitada no FaithBloom.")
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("O compromisso precisa de um título.")
    tz = ZoneInfo(timezone_name)
    start = start.astimezone(tz) if start.tzinfo else start.replace(tzinfo=tz)
    end = end or (start + timedelta(hours=1))
    end = end.astimezone(tz) if end.tzinfo else end.replace(tzinfo=tz)
    token = _refresh_access_token(poster=poster)
    payload = {
        "summary": clean_title,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
    }
    if location:
        payload["location"] = location
    if description:
        payload["description"] = description
    try:
        response = poster(_calendar_url(), headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload, timeout=10)
        response.raise_for_status()
        return _normalize_event(response.json(), timezone_name)
    except requests.RequestException as exc:
        raise JarvisCalendarError("Não consegui adicionar o compromisso ao Google Calendar.") from exc


def update_calendar_event(
    event_id: str,
    *,
    new_start: datetime | None = None,
    new_title: str | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
    getter: Callable = requests.get,
    patcher: Callable = requests.patch,
    poster: Callable = requests.post,
) -> dict[str, Any]:
    if not calendar_write_is_enabled():
        raise JarvisCalendarError("A escrita no Google Calendar ainda não está habilitada no FaithBloom.")
    if not event_id:
        raise ValueError("Evento inválido para alteração.")
    token = _refresh_access_token(poster=poster)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = _calendar_url(event_id)
    try:
        current_response = getter(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        current_response.raise_for_status()
        current = current_response.json()
        payload: dict[str, Any] = {}
        if new_title:
            payload["summary"] = new_title.strip()
        if new_start:
            tz = ZoneInfo(timezone_name)
            old_start, _ = _event_start(current, timezone_name)
            old_end = _event_end(current, timezone_name)
            duration = (old_end - old_start) if old_start and old_end else timedelta(hours=1)
            start = new_start.astimezone(tz) if new_start.tzinfo else new_start.replace(tzinfo=tz)
            payload["start"] = {"dateTime": start.isoformat(), "timeZone": timezone_name}
            payload["end"] = {"dateTime": (start + duration).isoformat(), "timeZone": timezone_name}
        if not payload:
            raise ValueError("Nenhuma alteração foi informada.")
        response = patcher(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return _normalize_event(response.json(), timezone_name)
    except requests.RequestException as exc:
        raise JarvisCalendarError("Não consegui alterar esse compromisso no Google Calendar.") from exc


def _parse_clock(text: str) -> tuple[int, int] | None:
    match = re.search(r"\b(?:às|as|para|pelas)?\s*(\d{1,2})(?::|h)(\d{2})?\b", text, flags=re.I)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def _resolve_relative_date(text: str, now: datetime) -> datetime | None:
    value = text.casefold()
    base = now
    if "depois de amanhã" in value or "depois de amanha" in value:
        base = now + timedelta(days=2)
    elif "amanhã" in value or "amanha" in value:
        base = now + timedelta(days=1)
    elif "hoje" not in value:
        match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", value)
        if not match:
            return None
        year = int(match.group(3) or now.year)
        if year < 100:
            year += 2000
        try:
            base = now.replace(year=year, month=int(match.group(2)), day=int(match.group(1)))
        except ValueError:
            return None
    clock = _parse_clock(text)
    if not clock:
        return None
    return base.replace(hour=clock[0], minute=clock[1], second=0, microsecond=0)


def prepare_calendar_action(text: str, *, now: datetime | None = None, timezone_name: str = DEFAULT_TIMEZONE) -> dict[str, Any] | None:
    """Interpreta ações simples de calendário, mas nunca executa nada."""
    raw = (text or "").strip()
    value = raw.casefold()
    if not raw or not any(k in value for k in ("agenda", "calend", "compromisso", "evento")):
        return None
    now = now or local_now(timezone_name)
    create_verbs = ("adicione", "adicionar", "agende", "agendar", "marque", "marcar", "crie", "criar", "coloque", "colocar")
    update_verbs = ("altere", "alterar", "mude", "mudar", "remarque", "remarcar", "troque", "trocar")
    if any(v in value for v in create_verbs):
        when = _resolve_relative_date(raw, now)
        title = re.sub(r"^(?:jarvis[,: ]*)?(?:adicione|adicionar|agende|agendar|marque|marcar|crie|criar|coloque|colocar)\s+(?:um\s+)?(?:compromisso|evento)?\s*", "", raw, flags=re.I)
        title = re.split(r"\b(?:hoje|amanh[aã]|depois de amanh[aã]|às|as)\b", title, maxsplit=1, flags=re.I)[0].strip(" ,.-")
        if not title or not when:
            return {"action": "create", "ready": False, "message": "Para adicionar, me diga o título, o dia e o horário. Exemplo: agende compromisso dentista amanhã às 15h."}
        return {"action": "create", "ready": True, "title": title, "start": when, "summary": f"Adicionar '{title}' em {when.strftime('%d/%m às %H:%M')}"}
    if any(v in value for v in update_verbs):
        when = _resolve_relative_date(raw, now)
        match = re.search(r"(?:compromisso|evento)\s+(.+?)\s+(?:para|às|as)\b", raw, flags=re.I)
        title = match.group(1).strip(" ,.-") if match else ""
        if not title or not when:
            return {"action": "update", "ready": False, "message": "Para alterar, me diga qual compromisso e o novo dia/horário. Exemplo: mude o compromisso dentista para amanhã às 16h."}
        candidates = find_upcoming_events_by_title(title, timezone_name=timezone_name, now=now)
        if not candidates:
            return {"action": "update", "ready": False, "message": f"Não encontrei um compromisso futuro chamado '{title}'."}
        if len(candidates) > 1:
            return {"action": "update", "ready": False, "message": f"Encontrei mais de um compromisso parecido com '{title}'. Diga a data do que você quer alterar."}
        event = candidates[0]
        return {"action": "update", "ready": True, "event_id": event["id"], "title": event["title"], "start": when, "summary": f"Alterar '{event['title']}' para {when.strftime('%d/%m às %H:%M')}"}
    return None


def execute_calendar_action(plan: dict[str, Any], *, timezone_name: str = DEFAULT_TIMEZONE) -> dict[str, Any]:
    """Executa somente um plano já confirmado externamente pela interface."""
    if not plan or not plan.get("ready"):
        raise ValueError("Não existe uma ação de calendário pronta para executar.")
    action = plan.get("action")
    if action == "create":
        return create_calendar_event(str(plan.get("title") or ""), plan["start"], timezone_name=timezone_name)
    if action == "update":
        return update_calendar_event(str(plan.get("event_id") or ""), new_start=plan["start"], timezone_name=timezone_name)
    raise ValueError("Ação de calendário não suportada.")


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
            calendar_detail = "Integração de calendário aguardando configuração OAuth."

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
        "calendar_write_enabled": calendar_write_is_enabled(),
        "calendar_detail": calendar_detail,
        "events": events,
        "next_event": next_event(events, now),
        "timings": timings,
    }

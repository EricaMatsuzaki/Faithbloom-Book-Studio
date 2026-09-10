"""Clima em tempo real para o Jarvis usando Open-Meteo.

Camada independente de IA: não usa OpenRouter, não consome créditos de LLM e não
interfere no orquestrador editorial. Faz geocodificação por cidade e consulta a
previsão meteorológica pública via HTTP.
"""
from __future__ import annotations

import re
from typing import Any, Callable

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class JarvisWeatherError(RuntimeError):
    """Erro de clima apresentado de modo seguro ao usuário."""


WMO_PT = {
    0: "céu limpo",
    1: "predominantemente limpo",
    2: "parcialmente nublado",
    3: "nublado",
    45: "neblina",
    48: "neblina com geada",
    51: "garoa leve",
    53: "garoa moderada",
    55: "garoa forte",
    56: "garoa congelante leve",
    57: "garoa congelante forte",
    61: "chuva leve",
    63: "chuva moderada",
    65: "chuva forte",
    66: "chuva congelante leve",
    67: "chuva congelante forte",
    71: "neve leve",
    73: "neve moderada",
    75: "neve forte",
    77: "grãos de neve",
    80: "pancadas de chuva leves",
    81: "pancadas de chuva moderadas",
    82: "pancadas de chuva fortes",
    85: "pancadas de neve leves",
    86: "pancadas de neve fortes",
    95: "trovoadas",
    96: "trovoadas com granizo leve",
    99: "trovoadas com granizo forte",
}


def is_weather_request(text: str) -> bool:
    value = (text or "").casefold()
    hints = (
        "previsão do tempo", "previsao do tempo", "tempo hoje", "tempo amanhã",
        "tempo amanha", "tempo em ", "tempo no ", "tempo na ", "como está o tempo",
        "como esta o tempo", "vai chover", "chuva hoje", "chuva amanhã", "chuva amanha",
        "temperatura hoje", "temperatura amanhã", "temperatura amanha", "temperatura em ",
        "clima hoje", "clima amanhã", "clima amanha", "clima em ", "clima no ", "clima na ",
        "weather", "forecast",
    )
    return any(h in value for h in hints)


def extract_location(text: str) -> str | None:
    """Extrai uma cidade simples de pedidos como 'tempo em Toyohashi'."""
    raw = (text or "").strip()
    if not raw:
        return None
    patterns = (
        r"(?:tempo|clima|previs[aã]o(?:\s+do\s+tempo)?|temperatura|chuva)\s+(?:para|em|de|no|na)\s+([^?!.]+)",
        r"(?:vai\s+chover)\s+(?:em|no|na)\s+([^?!.]+)",
        r"(?:weather|forecast)\s+(?:in|for)\s+([^?!.]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I)
        if match:
            candidate = match.group(1).strip(" ,")
            candidate = re.sub(r"\b(?:hoje|amanh[aã]|agora|this morning|today|tomorrow)\b.*$", "", candidate, flags=re.I).strip(" ,")
            if len(candidate) >= 2:
                return candidate
    return None


def _get_json(url: str, params: dict[str, Any], *, timeout: int = 12, getter: Callable = requests.get) -> dict[str, Any]:
    try:
        response = getter(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise JarvisWeatherError("Não consegui acessar o serviço de clima agora. Tente novamente em instantes.") from exc
    except ValueError as exc:
        raise JarvisWeatherError("O serviço de clima retornou uma resposta inválida.") from exc
    if not isinstance(data, dict):
        raise JarvisWeatherError("O serviço de clima retornou um formato inesperado.")
    if data.get("error"):
        raise JarvisWeatherError(str(data.get("reason") or "O serviço de clima recusou a consulta."))
    return data


def geocode_location(location: str, *, getter: Callable = requests.get) -> dict[str, Any]:
    query = (location or "").strip()
    if not query:
        raise ValueError("Informe uma cidade para eu consultar o clima.")
    data = _get_json(
        GEOCODING_URL,
        {"name": query, "count": 1, "language": "pt", "format": "json"},
        getter=getter,
    )
    results = data.get("results") or []
    if not results:
        raise JarvisWeatherError(f"Não encontrei a localização '{query}'. Tente informar cidade e país.")
    first = results[0]
    return {
        "name": first.get("name") or query,
        "admin1": first.get("admin1") or "",
        "country": first.get("country") or "",
        "latitude": float(first["latitude"]),
        "longitude": float(first["longitude"]),
        "timezone": first.get("timezone") or "auto",
    }


def fetch_weather(location: str, *, getter: Callable = requests.get) -> dict[str, Any]:
    place = geocode_location(location, getter=getter)
    data = _get_json(
        FORECAST_URL,
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 3,
        },
        getter=getter,
    )
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    if not current or not daily:
        raise JarvisWeatherError("A previsão chegou incompleta. Tente novamente em instantes.")
    return {"place": place, "current": current, "daily": daily, "timezone": data.get("timezone") or place["timezone"]}


def _number(value: Any, digits: int = 0) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def build_weather_reply(location: str, *, getter: Callable = requests.get) -> str:
    weather = fetch_weather(location, getter=getter)
    place = weather["place"]
    current = weather["current"]
    daily = weather["daily"]
    name_parts = [place["name"], place.get("admin1"), place.get("country")]
    place_name = ", ".join(p for p in name_parts if p)

    code_now = int(current.get("weather_code", -1))
    condition_now = WMO_PT.get(code_now, "condição variável")
    temp = _number(current.get("temperature_2m"))
    apparent = _number(current.get("apparent_temperature"))
    wind = _number(current.get("wind_speed_10m"))

    maxs = daily.get("temperature_2m_max") or []
    mins = daily.get("temperature_2m_min") or []
    rain = daily.get("precipitation_probability_max") or []
    codes = daily.get("weather_code") or []
    today_max = _number(maxs[0] if maxs else None)
    today_min = _number(mins[0] if mins else None)
    rain_today = _number(rain[0] if rain else None)
    today_condition = WMO_PT.get(int(codes[0]), condition_now) if codes else condition_now

    return (
        f"Em {place_name}, agora está {temp} graus, sensação de {apparent} graus, com {condition_now}. "
        f"Hoje a previsão é de {today_condition}, mínima de {today_min} e máxima de {today_max} graus, "
        f"com até {rain_today} por cento de chance de precipitação. O vento agora está em torno de {wind} quilômetros por hora."
    )

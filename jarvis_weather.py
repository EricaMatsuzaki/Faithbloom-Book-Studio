"""Clima em tempo real para o Jarvis usando Open-Meteo."""
from __future__ import annotations

import re
from typing import Any, Callable

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class JarvisWeatherError(RuntimeError):
    """Erro de clima apresentado de modo seguro ao usuário."""


WMO_PT = {
    0: "céu limpo", 1: "predominantemente limpo", 2: "parcialmente nublado", 3: "nublado",
    45: "neblina", 48: "neblina com geada", 51: "garoa leve", 53: "garoa moderada",
    55: "garoa forte", 56: "garoa congelante leve", 57: "garoa congelante forte",
    61: "chuva leve", 63: "chuva moderada", 65: "chuva forte", 66: "chuva congelante leve",
    67: "chuva congelante forte", 71: "neve leve", 73: "neve moderada", 75: "neve forte",
    77: "grãos de neve", 80: "pancadas de chuva leves", 81: "pancadas de chuva moderadas",
    82: "pancadas de chuva fortes", 85: "pancadas de neve leves", 86: "pancadas de neve fortes",
    95: "trovoadas", 96: "trovoadas com granizo leve", 99: "trovoadas com granizo forte",
}


def is_weather_request(text: str) -> bool:
    """Reconhece pedidos naturais de clima, inclusive variações comuns do STT."""
    value = (text or "").casefold()
    hints = (
        "previsão do tempo", "previsao do tempo", "previsão de tempo", "previsao de tempo",
        "previsão aqui", "previsao aqui", "previsão para", "previsao para",
        "tempo hoje", "tempo amanhã", "tempo amanha", "tempo agora",
        "tempo em ", "tempo no ", "tempo na ", "tempo aqui",
        "como está o tempo", "como esta o tempo", "como fica o tempo",
        "vai chover", "chance de chuva", "chuva hoje", "chuva amanhã", "chuva amanha",
        "temperatura hoje", "temperatura amanhã", "temperatura amanha", "temperatura em ",
        "temperatura aqui", "clima hoje", "clima amanhã", "clima amanha", "clima agora",
        "clima em ", "clima no ", "clima na ", "clima aqui", "weather", "forecast",
    )
    return any(h in value for h in hints)


def requested_day_offset(text: str) -> int:
    value = (text or "").casefold()
    if any(x in value for x in ("depois de amanhã", "depois de amanha", "day after tomorrow")):
        return 2
    if any(x in value for x in ("amanhã", "amanha", "tomorrow")):
        return 1
    return 0


def _clean_location(candidate: str) -> str | None:
    value = (candidate or "").strip(" ,")
    if not value:
        return None
    # Remove uma segunda oração comum após a cidade, por exemplo:
    # "Toyohashi, vai chover amanhã" -> "Toyohashi".
    value = re.split(
        r"\s*,\s*(?=(?:vai\s+chover|vai\s+fazer|como\s+fica|qual\s+(?:a|é)\s+previs[aã]o|tempo|clima|temperatura)\b)",
        value,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" ,")
    # Remove termos de tempo/data que podem vir depois do nome da cidade.
    value = re.sub(
        r"\b(?:hoje|amanh[aã]|agora|neste momento|essa tarde|esta tarde|essa noite|esta noite|today|tomorrow)\b.*$",
        "",
        value,
        flags=re.I,
    ).strip(" ,")
    # STT costuma produzir 'aqui em Toyohashi'; queremos apenas Toyohashi.
    value = re.sub(r"^(?:aqui\s+)?(?:em|no|na|para)\s+", "", value, flags=re.I).strip(" ,")
    return value if len(value) >= 2 else None


def extract_location(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None

    patterns = (
        # Ex.: 'previsão do tempo para Nagoya', 'previsão de tempo em Toyohashi'.
        r"(?:tempo|clima|previs[aã]o(?:\s+(?:do|de)\s+tempo)?|temperatura|chuva)\s+(?:para|em|no|na)\s+([^?!.]+)",
        # Ex.: 'qual a previsão de tempo aqui em Toyohashi?'.
        r"(?:previs[aã]o(?:\s+(?:do|de)\s+tempo)?|tempo|clima|temperatura)[^?!.]{0,45}?\baqui\s+(?:em|no|na)\s+([^?!.]+)",
        # Ex.: 'aqui em Toyohashi, vai chover?'.
        r"\baqui\s+(?:em|no|na)\s+([^?!.]+)",
        r"(?:vai\s+chover|chance\s+de\s+chuva)\s+(?:em|no|na)\s+([^?!.]+)",
        r"(?:weather|forecast)\s+(?:in|for)\s+([^?!.]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I)
        if match:
            candidate = _clean_location(match.group(1))
            if candidate:
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
    data = _get_json(GEOCODING_URL, {"name": query, "count": 1, "language": "pt", "format": "json"}, getter=getter)
    results = data.get("results") or []
    if not results:
        raise JarvisWeatherError(f"Não encontrei a localização '{query}'. Tente informar cidade e país.")
    first = results[0]
    return {
        "name": first.get("name") or query, "admin1": first.get("admin1") or "", "country": first.get("country") or "",
        "latitude": float(first["latitude"]), "longitude": float(first["longitude"]), "timezone": first.get("timezone") or "auto",
    }


def fetch_weather(location: str, *, getter: Callable = requests.get) -> dict[str, Any]:
    place = geocode_location(location, getter=getter)
    data = _get_json(FORECAST_URL, {
        "latitude": place["latitude"], "longitude": place["longitude"],
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto", "forecast_days": 3,
    }, getter=getter)
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


def build_weather_reply(location: str, *, day_offset: int = 0, getter: Callable = requests.get) -> str:
    weather = fetch_weather(location, getter=getter)
    place, current, daily = weather["place"], weather["current"], weather["daily"]
    place_name = ", ".join(p for p in (place["name"], place.get("admin1"), place.get("country")) if p)
    maxs, mins, rain, codes = (daily.get("temperature_2m_max") or [], daily.get("temperature_2m_min") or [], daily.get("precipitation_probability_max") or [], daily.get("weather_code") or [])
    idx = max(0, min(int(day_offset), 2))
    label = "Hoje" if idx == 0 else "Amanhã" if idx == 1 else "Depois de amanhã"
    condition = WMO_PT.get(int(codes[idx]), "condição variável") if len(codes) > idx else "condição variável"
    high = _number(maxs[idx] if len(maxs) > idx else None)
    low = _number(mins[idx] if len(mins) > idx else None)
    rain_chance = _number(rain[idx] if len(rain) > idx else None)

    if idx > 0:
        return f"Em {place_name}, {label.lower()} a previsão é de {condition}, mínima de {low} e máxima de {high} graus, com até {rain_chance} por cento de chance de precipitação."

    code_now = int(current.get("weather_code", -1))
    condition_now = WMO_PT.get(code_now, "condição variável")
    temp = _number(current.get("temperature_2m"))
    apparent = _number(current.get("apparent_temperature"))
    wind = _number(current.get("wind_speed_10m"))
    return (
        f"Em {place_name}, agora está {temp} graus, sensação de {apparent} graus, com {condition_now}. "
        f"{label} a previsão é de {condition}, mínima de {low} e máxima de {high} graus, "
        f"com até {rain_chance} por cento de chance de precipitação. O vento agora está em torno de {wind} quilômetros por hora."
    )

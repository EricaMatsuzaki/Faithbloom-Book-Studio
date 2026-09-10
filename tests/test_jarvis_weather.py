import jarvis_weather as weather


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_detects_weather_request():
    assert weather.is_weather_request("Jarvis, vai chover hoje?") is True
    assert weather.is_weather_request("Crie uma história infantil") is False


def test_extracts_location_from_portuguese_request():
    assert weather.extract_location("Jarvis, como está o tempo em Toyohashi?") == "Toyohashi"
    assert weather.extract_location("Qual a previsão do tempo para Nagoya hoje?") == "Nagoya"


def test_missing_location_is_not_invented():
    assert weather.extract_location("Vai chover hoje?") is None


def test_weather_flow_geocodes_and_formats_current_forecast():
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params, timeout))
        if "geocoding-api" in url:
            return FakeResponse({
                "results": [{
                    "name": "Toyohashi",
                    "admin1": "Aichi",
                    "country": "Japan",
                    "latitude": 34.7692,
                    "longitude": 137.3915,
                    "timezone": "Asia/Tokyo",
                }]
            })
        return FakeResponse({
            "timezone": "Asia/Tokyo",
            "current": {
                "temperature_2m": 28.4,
                "apparent_temperature": 31.1,
                "weather_code": 2,
                "wind_speed_10m": 11.0,
            },
            "daily": {
                "weather_code": [61, 2, 1],
                "temperature_2m_max": [31.0, 30.0, 29.0],
                "temperature_2m_min": [24.0, 23.0, 22.0],
                "precipitation_probability_max": [70, 30, 10],
            },
        })

    reply = weather.build_weather_reply("Toyohashi", getter=fake_get)
    lower = reply.casefold()
    assert "toyohashi" in lower
    assert "28 graus" in lower
    assert "31 graus" in lower
    assert "70 por cento" in lower
    assert len(calls) == 2
    assert calls[1][1]["timezone"] == "auto"
    assert calls[1][1]["forecast_days"] == 3


def test_geocode_not_found_has_clear_error():
    def fake_get(url, params=None, timeout=None):
        return FakeResponse({"results": []})

    try:
        weather.geocode_location("Cidade Inexistente", getter=fake_get)
    except weather.JarvisWeatherError as exc:
        assert "não encontrei" in str(exc).casefold()
    else:
        raise AssertionError("Era esperado erro de localização não encontrada")

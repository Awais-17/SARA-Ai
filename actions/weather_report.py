# weather_report.py
import json
import sys
import time
import webbrowser
from urllib.parse import quote_plus, urlencode
from pathlib import Path

try:
    import requests as _requests
    _REQUESTS = True
except ImportError:
    _REQUESTS = False


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


# WMO weather-code → readable condition
_WMO_CODES: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


def _geocode(city: str) -> tuple[float, float, str] | None:
    """Return (lat, lon, display_name) for a city using Open-Meteo geocoding."""
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": city, "count": 1, "language": "en", "format": "json"}
        r = _requests.get(url, params=params, timeout=6)
        r.raise_for_status()
        data = r.json()
        results = data.get("results")
        if not results:
            return None
        top = results[0]
        name = top.get("name", city)
        country = top.get("country_code", "")
        display = f"{name}, {country}" if country else name
        return float(top["latitude"]), float(top["longitude"]), display
    except Exception as e:
        print(f"[Weather] Geocode failed: {e}")
        return None


def _fetch_weather(lat: float, lon: float) -> dict | None:
    """Fetch current conditions from Open-Meteo."""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "weathercode",
                "windspeed_10m",
                "precipitation",
            ],
            "wind_speed_unit": "kmh",
            "temperature_unit": "celsius",
            "timezone": "auto",
        }
        r = _requests.get(url, params=params, timeout=6)
        r.raise_for_status()
        return r.json().get("current", {})
    except Exception as e:
        print(f"[Weather] Fetch failed: {e}")
        return None


def _build_summary(city_display: str, data: dict) -> str:
    temp     = data.get("temperature_2m")
    feels    = data.get("apparent_temperature")
    humidity = data.get("relative_humidity_2m")
    wind     = data.get("windspeed_10m")
    code     = int(data.get("weathercode", -1))
    precip   = data.get("precipitation", 0)

    condition = _WMO_CODES.get(code, "Unknown conditions")

    parts = [f"In {city_display}: {condition}."]
    if temp is not None:
        parts.append(f"Temperature is {temp:.0f}°C")
        if feels is not None and abs(feels - temp) >= 2:
            parts.append(f"but feels like {feels:.0f}°C")
    if humidity is not None:
        parts.append(f"Humidity {humidity:.0f}%")
    if wind is not None:
        parts.append(f"Wind {wind:.0f} km/h")
    if precip and precip > 0:
        parts.append(f"Precipitation {precip:.1f} mm")

    return ", ".join(parts) + "."


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    city = (parameters or {}).get("city", "")
    when = (parameters or {}).get("time", "today")

    if not city or not isinstance(city, str) or not city.strip():
        msg = "Sir, the city is missing for the weather report."
        _log(msg, player)
        return msg

    city = city.strip()

    # ── Real API path ──────────────────────────────────────────────────────────
    if _REQUESTS:
        geo = _geocode(city)
        if geo:
            lat, lon, display = geo
            data = _fetch_weather(lat, lon)
            if data:
                summary = _build_summary(display, data)
                _log(summary, player)
                return summary
        # Geocode or fetch failed — fall through to browser
        _log(f"[Weather] API unavailable for '{city}', opening browser.", player)

    # ── Browser fallback ───────────────────────────────────────────────────────
    search_query = f"weather in {city} {when}".strip()
    url = f"https://www.google.com/search?q={quote_plus(search_query)}"
    try:
        webbrowser.open(url)
        msg = f"Showing the weather for {city}, {when}, sir."
    except Exception as e:
        msg = f"Sir, I couldn't open the browser for the weather report: {e}"

    _log(msg, player)
    return msg


def _log(message: str, player=None) -> None:
    print(f"[Weather] {message}")
    if player:
        try:
            player.write_log(f"SARA: {message}")
        except Exception:
            pass
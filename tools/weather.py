"""
JARVIS Local - Clima (Fase 4)
Clima de cualquier ciudad via Open-Meteo (gratis, sin API key).
"""
import requests
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Codigos WMO -> descripcion en espanol
_WMO = {
    0: "cielo despejado", 1: "mayormente despejado", 2: "parcialmente nublado",
    3: "nublado", 45: "niebla", 48: "niebla con escarcha",
    51: "llovizna ligera", 53: "llovizna moderada", 55: "llovizna intensa",
    61: "lluvia ligera", 63: "lluvia moderada", 65: "lluvia fuerte",
    66: "lluvia helada ligera", 67: "lluvia helada fuerte",
    71: "nevada ligera", 73: "nevada moderada", 75: "nevada fuerte",
    77: "granos de nieve", 80: "chubascos ligeros", 81: "chubascos moderados",
    82: "chubascos violentos", 85: "chubascos de nieve", 86: "chubascos de nieve fuertes",
    95: "tormenta electrica", 96: "tormenta con granizo", 99: "tormenta con granizo fuerte",
}


def geocode_city(city: str) -> dict | None:
    """Devuelve {name, country, latitude, longitude} o None."""
    r = requests.get(GEOCODE_URL, params={
        "name": city, "count": 1, "language": "es", "format": "json"}, timeout=15)
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        return None
    top = results[0]
    return {"name": top["name"], "country": top.get("country", ""),
            "latitude": top["latitude"], "longitude": top["longitude"]}


def get_weather(city: str) -> ActionPlan:
    """Clima actual de una ciudad."""
    plan = ActionPlan(action="clima", params={"ciudad": city},
                      risk=RiskLevel.READ, reason=f"Consultar clima de {city}")
    try:
        loc = geocode_city(city)
        if not loc:
            plan.status = ActionStatus.ERROR
            plan.result = f"No encontre la ciudad '{city}', senor."
            return plan
        r = requests.get(FORECAST_URL, params={
            "latitude": loc["latitude"], "longitude": loc["longitude"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "auto", "forecast_days": 1,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()
        cur = data["current"]
        daily = data.get("daily", {})
        desc = _WMO.get(cur.get("weather_code", -1), "condiciones variables")
        tmax = daily.get("temperature_2m_max", [None])[0]
        tmin = daily.get("temperature_2m_min", [None])[0]
        texto = (f"Clima en {loc['name']}, {loc['country']}: {desc}, "
                 f"{cur['temperature_2m']} grados (sensacion de {cur['apparent_temperature']}), "
                 f"humedad {cur['relative_humidity_2m']} por ciento, "
                 f"viento a {cur['wind_speed_10m']} km/h.")
        if tmax is not None and tmin is not None:
            texto += f" Hoy: minima {tmin} y maxima {tmax} grados."
        plan.result = texto
        plan.status = ActionStatus.EXECUTED
    except requests.RequestException as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = "No pude consultar el clima. Verifique su conexion a internet."
    return plan

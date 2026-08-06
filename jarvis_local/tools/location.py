"""
JARVIS Local - Ubicaciones y distancias (Fase 4)
Abre cualquier lugar en el mapa e indica la distancia desde tu ubicacion.
"""
import math
import webbrowser

import requests

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel
from jarvis_local.tools.weather import geocode_city

MY_LOCATION_URL = "http://ip-api.com/json/?fields=status,city,country,lat,lon"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km entre dos coordenadas (formula de haversine)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def my_location() -> dict | None:
    """Ubicacion aproximada por IP: {city, country, lat, lon} o None."""
    try:
        r = requests.get(MY_LOCATION_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            return None
        return {"city": data["city"], "country": data["country"],
                "lat": data["lat"], "lon": data["lon"]}
    except requests.RequestException:
        return None


def locate(place: str) -> ActionPlan:
    """Abre el lugar en Google Maps e indica la distancia desde tu ubicacion."""
    plan = ActionPlan(action="ubicar_lugar", params={"lugar": place},
                      risk=RiskLevel.EXECUTE, reason=f"Ubicar {place} en el mapa")
    try:
        dest = geocode_city(place)
        if not dest:
            plan.status = ActionStatus.ERROR
            plan.result = f"No encontre el lugar '{place}', senor."
            return plan
        url = f"https://www.google.com/maps/search/?api=1&query={dest['latitude']},{dest['longitude']}"
        webbrowser.open(url)
        texto = f"Abriendo {dest['name']}, {dest['country']} en el mapa."
        origin = my_location()
        if origin:
            km = haversine_km(origin["lat"], origin["lon"],
                              dest["latitude"], dest["longitude"])
            texto += (f" Distancia desde {origin['city']}: "
                      f"aproximadamente {km:,.0f} kilometros en linea recta.")
        plan.result = texto
        plan.status = ActionStatus.EXECUTED
    except requests.RequestException as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = "No pude consultar la ubicacion. Verifique su conexion a internet."
    return plan

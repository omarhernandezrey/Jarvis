"""
JARVIS Local - Ubicaciones y distancias (Fase 4)
Abre cualquier lugar en el mapa e indica la distancia desde tu ubicacion.
"""
import math
import urllib.parse
import webbrowser

import requests

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel
from jarvis_local.tools.weather import geocode_city

MY_LOCATION_URL = "http://ip-api.com/json/?fields=status,city,country,lat,lon"
_OSM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim EXIGE un User-Agent que identifique la app; sin el, 403.
_OSM_UA = "jarvis-local/6.0 (asistente personal offline)"


def geocode_osm(place: str) -> dict | None:
    """Geocodifica cualquier lugar (POI, monumento, direccion) con OpenStreetMap.
    Devuelve {name, country, latitude, longitude} o None. Uso puntual: 1 peticion.
    """
    try:
        r = requests.get(_OSM_URL, params={
            "q": place, "format": "json", "limit": 1, "addressdetails": 1,
        }, headers={"User-Agent": _OSM_UA}, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        hit = data[0]
        addr = hit.get("address", {})
        return {
            "name": hit.get("display_name", place).split(",")[0].strip() or place,
            "country": addr.get("country", ""),
            "latitude": float(hit["lat"]),
            "longitude": float(hit["lon"]),
        }
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


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
        # OpenStreetMap primero: resuelve tanto ciudades como POIs, monumentos y
        # direcciones. El geocoder de Open-Meteo (solo ciudades) queda de
        # respaldo si OSM no responde (rate-limit/red).
        dest = geocode_osm(place) or geocode_city(place)
        if not dest:
            # 3) ultimo recurso: abrir Google Maps con el texto crudo (Maps
            #    resuelve "Torre Eiffel" perfectamente); solo no hay distancia.
            q = urllib.parse.quote_plus(place)
            webbrowser.open(f"https://www.google.com/maps/search/?api=1&query={q}")
            plan.result = (f"Abri el mapa buscando '{place}', senor. "
                           "No pude calcular la distancia desde su ubicacion.")
            plan.status = ActionStatus.EXECUTED
            return plan
        url = f"https://www.google.com/maps/search/?api=1&query={dest['latitude']},{dest['longitude']}"
        webbrowser.open(url)
        nombre = dest["name"] + (f", {dest['country']}" if dest.get("country") else "")
        texto = f"Abriendo {nombre} en el mapa."
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
        plan.result = "No pude consultar la ubicacion, senor. Verifique su conexion a internet."
    return plan

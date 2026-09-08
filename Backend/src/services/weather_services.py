"""Clima real del autódromo.

Los datos salen de Open-Meteo, que no pide clave ni registro: una clave
más sería otra cosa que caduca a mitad de una transmisión.

    https://api.open-meteo.com/v1/forecast

La respuesta se cachea y, si el servicio no contesta, se devuelve el
último dato bueno marcado como viejo. Un gráfico con el clima de hace
veinte minutos es mucho mejor que un hueco al aire.
"""

import time
from datetime import datetime
from typing import Optional

import urllib.error
import urllib.parse
import urllib.request
import json

from config import settings

API = "https://api.open-meteo.com/v1/forecast"

# Códigos WMO que devuelve Open-Meteo. `condicion` es la que usa la
# plantilla para dibujar su icono; no se usan códigos de OpenWeatherMap
# para no depender de que CasparCG tenga salida a internet.
CODIGOS = {
    0:  ("Despejado",              "despejado"),
    1:  ("Mayormente despejado",   "despejado"),
    2:  ("Parcialmente nublado",   "parcial"),
    3:  ("Nublado",                "nublado"),
    45: ("Neblina",                "niebla"),
    48: ("Neblina con escarcha",   "niebla"),
    51: ("Llovizna ligera",        "llovizna"),
    53: ("Llovizna",               "llovizna"),
    55: ("Llovizna intensa",       "llovizna"),
    56: ("Llovizna helada",        "llovizna"),
    57: ("Llovizna helada fuerte", "llovizna"),
    61: ("Lluvia ligera",          "lluvia"),
    63: ("Lluvia",                 "lluvia"),
    65: ("Lluvia fuerte",          "lluvia"),
    66: ("Lluvia helada",          "lluvia"),
    67: ("Lluvia helada fuerte",   "lluvia"),
    71: ("Nevada ligera",          "nieve"),
    73: ("Nevada",                 "nieve"),
    75: ("Nevada fuerte",          "nieve"),
    77: ("Granos de nieve",        "nieve"),
    80: ("Chubascos ligeros",      "lluvia"),
    81: ("Chubascos",              "lluvia"),
    82: ("Chubascos fuertes",      "lluvia"),
    85: ("Chubascos de nieve",     "nieve"),
    86: ("Chubascos de nieve",     "nieve"),
    95: ("Tormenta eléctrica",     "tormenta"),
    96: ("Tormenta con granizo",   "tormenta"),
    99: ("Tormenta con granizo",   "tormenta"),
}

MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
         "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

# Último dato bueno y cuándo se obtuvo.
_cache: Optional[dict] = None
_cache_en: float = 0.0


def _fecha_es(momento: datetime) -> str:
    return f"{momento.day:02d} {MESES[momento.month - 1]} {momento.year}"


def _consultar(lat: float, lon: float) -> dict:
    parametros = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "precipitation", "weather_code", "wind_speed_10m", "is_day",
        ]),
        "timezone": "America/Panama",
        "wind_speed_unit": "kmh",
    }

    url = f"{API}?{urllib.parse.urlencode(parametros)}"

    with urllib.request.urlopen(url, timeout=settings.WEATHER_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


# Coordenadas y nombre del sitio, que el cliente puso en el asistente. Se
# guardan en memoria al arrancar (igual que la ruta del cronometraje) para
# no consultar la base cada vez que una plantilla pide el clima.
_ubicacion = {
    "lat": None, "lon": None, "lugar": "", "pais": "",
}


async def cargar_ubicacion() -> dict:
    """Trae de la base la ubicación del circuito. Se llama al arrancar."""
    from src.models.instalacion_model import Instalacion

    doc = await Instalacion.find_one({"clave": "instalacion"})
    if doc and doc.lat is not None and doc.lon is not None:
        _ubicacion.update({
            "lat": doc.lat, "lon": doc.lon,
            "lugar": doc.ciudad or doc.circuito or doc.organizacion,
            "pais": doc.pais.upper(),
        })

    return dict(_ubicacion)


def ubicacion() -> tuple[float, float, str, str]:
    """La del cliente si la configuró; si no, la de respaldo del .env."""
    if _ubicacion["lat"] is not None:
        return (_ubicacion["lat"], _ubicacion["lon"],
                _ubicacion["lugar"], _ubicacion["pais"])

    return (settings.WEATHER_LAT, settings.WEATHER_LON,
            settings.WEATHER_PLACE, settings.WEATHER_COUNTRY)


def obtener_clima(forzar: bool = False) -> dict:
    """Clima actual del autódromo, listo para la plantilla.

    Devuelve siempre algo: si la consulta falla y hay un dato guardado, se
    entrega ese marcado con `obsoleto`. Solo la primera consulta fallida
    de todas, sin nada en caché, devuelve error.
    """
    global _cache, _cache_en

    fresco = _cache and (time.time() - _cache_en) < settings.WEATHER_CACHE_SECONDS
    if fresco and not forzar:
        return {**_cache, "desde_cache": True}

    try:
        lat, lon, _lugar, _pais = ubicacion()
        crudo = _consultar(lat, lon)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
        if _cache:
            return {
                **_cache,
                "desde_cache": True,
                "obsoleto": True,
                "edad_segundos": int(time.time() - _cache_en),
                "error": f"{type(e).__name__}: {str(e)[:80]}",
            }
        return {
            "ok": False,
            "error": f"No se pudo consultar el clima: {type(e).__name__}",
            "detalle": str(e)[:120],
        }

    actual = crudo.get("current", {})
    codigo = int(actual.get("weather_code") or 0)
    descripcion, condicion = CODIGOS.get(codigo, ("Sin datos", "nublado"))

    ahora = datetime.now()

    datos = {
        "ok": True,
        # Nombres tal como los espera 65_weather.html.
        "temperature": round(actual.get("temperature_2m") or 0),
        "feels_like": round(actual.get("apparent_temperature") or 0),
        "humidity": round(actual.get("relative_humidity_2m") or 0),
        "wind_speed": round(actual.get("wind_speed_10m") or 0),
        "description": descripcion,
        "city": ubicacion()[2],
        "country": ubicacion()[3],
        "current_date": _fecha_es(ahora),

        # Para el icono que dibuja la propia plantilla.
        "condition": condicion,
        "is_day": bool(actual.get("is_day", 1)),

        "precipitation": actual.get("precipitation"),
        "weather_code": codigo,
        "lat": ubicacion()[0],
        "lon": ubicacion()[1],
        "consultado": ahora.strftime("%H:%M:%S"),
        "desde_cache": False,
    }

    _cache = datos
    _cache_en = time.time()
    return datos

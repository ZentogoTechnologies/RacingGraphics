"""Encontrar el circuito en el mapa.

Pedirle a un cliente la latitud y la longitud de su autódromo es pedirle
algo que no tiene a mano. Aquí se aceptan las tres formas en que una
persona real puede dar una ubicación:

  1. **Escribiendo el nombre del sitio.** Se busca contra el geocodificador
     de Open-Meteo, el mismo servicio que ya da el clima: sin clave de
     API, sin cuenta y sin coste. Google Maps habría obligado a facturar
     una clave y a meterla en cada instalación.

  2. **Pegando un enlace de Google Maps.** Es lo que la gente hace de
     verdad: abre el mapa, pone el pin en la recta de meta y comparte. Se
     sacan las coordenadas del propio enlace, sin llamar a Google.

  3. **Escribiendo las coordenadas**, en decimal o en grados y minutos.

Una advertencia sobre el punto 1: un geocodificador encuentra ciudades y
calles, no circuitos. Buscar «Autódromo Internacional del Norte» puede no
devolver nada, mientras que «Monterrey» sí. Para el clima eso da igual —
unos kilómetros no cambian si llueve— pero conviene que la interfaz lo
diga, para que nadie crea que el sistema está roto cuando el nombre de su
pista no aparece. Quien quiera precisión usa el enlace del mapa.
"""

import json
import re
import urllib.parse
import urllib.request

from config import settings

GEOCODIFICADOR = "https://geocoding-api.open-meteo.com/v1/search"

# Cabecera propia. Los servicios gratuitos piden identificarse para poder
# distinguir a un cliente legítimo de un script desbocado.
AGENTE = "RaceCoreStudio/1.0 (instalador)"


# ── Buscar por nombre ────────────────────────────────────────

def buscar(nombre: str, idioma: str = "es", limite: int = 8) -> list[dict]:
    """Lugares que coinciden con el texto, listos para enseñar en una lista."""
    nombre = (nombre or "").strip()

    if len(nombre) < 2:
        return []

    url = f"{GEOCODIFICADOR}?" + urllib.parse.urlencode({
        "name": nombre,
        "count": limite,
        "language": idioma,
        "format": "json",
    })

    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})

    try:
        with urllib.request.urlopen(peticion, timeout=settings.WEATHER_TIMEOUT) as r:
            datos = json.loads(r.read().decode("utf-8"))
    except Exception:
        # Sin conexión o servicio caído no es un error del asistente: se
        # devuelve vacío y el cliente escribe las coordenadas a mano, que
        # es la vía que nunca depende de nadie.
        return []

    salida = []
    for sitio in datos.get("results") or []:
        # admin1 es el estado o provincia. Ayuda a distinguir entre los
        # muchos sitios que se llaman igual en países distintos.
        partes = [sitio.get("admin1"), sitio.get("country")]
        salida.append({
            "nombre": sitio.get("name"),
            "detalle": ", ".join(p for p in partes if p),
            "pais": sitio.get("country") or "",
            "lat": sitio.get("latitude"),
            "lon": sitio.get("longitude"),
            # Open-Meteo devuelve además la zona horaria del sitio, así que
            # se aprovecha: es un dato menos que preguntar.
            "zona_horaria": sitio.get("timezone") or "UTC",
        })

    return salida


# ── Interpretar lo que el cliente pegue ──────────────────────

# "25.6866, -100.3161" y variantes con o sin espacios.
_DECIMAL = re.compile(
    r"^\s*(-?\d{1,3}(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$"
)

# Google Maps mete el punto de vista tras una arroba: /@25.6866,-100.3161,17z
_ARROBA = re.compile(r"@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)")

# Enlaces con la coordenada en el parámetro q= o query=
_PARAMETRO = re.compile(
    # El separador llega como coma o como %2C, según si el enlace venía
    # ya codificado. Se aceptan los dos.
    r"[?&](?:q|query|ll|center|destination)="
    r"(-?\d{1,3}\.\d+)(?:%2C|,)\s*(-?\d{1,3}\.\d+)",
    re.IGNORECASE,
)

# Grados, minutos y segundos: 25°41'11.8"N 100°18'57.9"W
_GMS = re.compile(
    r"(\d{1,3})\s*°\s*(\d{1,2})\s*'\s*([\d.]+)\s*\"?\s*([NSEOW])",
    re.IGNORECASE,
)


def _a_decimal(grados: str, minutos: str, segundos: str, punto: str) -> float:
    valor = int(grados) + int(minutos) / 60 + float(segundos) / 3600
    # Sur y Oeste son negativos. Se acepta O de "Oeste" además de W, porque
    # un Google Maps en español escribe O.
    return -valor if punto.upper() in ("S", "O", "W") else valor


def _resolver_enlace_corto(texto: str) -> str:
    """Sigue un maps.app.goo.gl hasta el enlace largo, que sí trae coordenadas.

    Es el formato que sale al compartir desde el móvil, así que es
    justamente el que más se va a pegar aquí.
    """
    if "goo.gl" not in texto and "maps.app" not in texto:
        return texto

    try:
        peticion = urllib.request.Request(
            texto.strip(), headers={"User-Agent": AGENTE}
        )
        with urllib.request.urlopen(peticion, timeout=settings.WEATHER_TIMEOUT) as r:
            return r.geturl()
    except Exception:
        return texto


def interpretar(texto: str) -> dict:
    """Saca latitud y longitud de lo que sea que hayan pegado.

    Devuelve `{"ok": False, "error": ...}` en vez de lanzar: esto responde
    a alguien escribiendo en un formulario, y un error legible vale más
    que una excepción.
    """
    crudo = (texto or "").strip()

    if not crudo:
        return {"ok": False, "error": "Escribe una ubicación o pega un enlace del mapa."}

    # 1. Coordenadas escritas tal cual.
    decimal = _DECIMAL.match(crudo)
    if decimal:
        lat = float(decimal.group(1).replace(",", "."))
        lon = float(decimal.group(2).replace(",", "."))
        return _validar(lat, lon, "coordenadas")

    # 2. Grados, minutos y segundos. Hacen falta las dos mitades.
    gms = _GMS.findall(crudo)
    if len(gms) >= 2:
        valores = [_a_decimal(*g) for g in gms[:2]]
        # El primero puede ser la longitud si escribieron al revés; se
        # ordena por la letra, que es la que no miente.
        if gms[0][3].upper() in ("E", "O", "W"):
            valores.reverse()
        return _validar(valores[0], valores[1], "grados y minutos")

    # 3. Un enlace de mapa.
    if crudo.startswith("http"):
        largo = _resolver_enlace_corto(crudo)

        for patron in (_ARROBA, _PARAMETRO):
            hallado = patron.search(largo)
            if hallado:
                return _validar(float(hallado.group(1)),
                                float(hallado.group(2)), "enlace del mapa")

        return {
            "ok": False,
            "error": "Ese enlace no lleva coordenadas. En Google Maps, haz clic "
                     "derecho sobre el circuito y copia los números que aparecen "
                     "arriba del menú.",
        }

    return {
        "ok": False,
        "error": "No se reconoce el formato. Usa «25.6866, -100.3161», pega un "
                 "enlace de Google Maps, o busca el lugar por su nombre.",
    }


def _validar(lat: float, lon: float, origen: str) -> dict:
    if not (-90 <= lat <= 90):
        return {"ok": False,
                "error": f"La latitud debe estar entre -90 y 90 (se leyó {lat})."}

    if not (-180 <= lon <= 180):
        return {"ok": False,
                "error": f"La longitud debe estar entre -180 y 180 (se leyó {lon})."}

    return {"ok": True, "lat": lat, "lon": lon, "origen": origen}

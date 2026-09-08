"""Interpretar la ubicación que pegue el cliente.

Aquí se prueba el parser y no la búsqueda por nombre: esa sale a internet
y no puede depender de que el servicio esté en pie para que las pruebas
pasen. El parser, en cambio, es el que decide si las coordenadas de un
circuito quedan bien puestas, y equivocarlo pone el clima en otro país.
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.services.ubicacion_services import interpretar     # noqa: E402

# Autódromo Internacional de Monterrey, más o menos.
LAT, LON = 25.6866, -100.3161


def cerca(valor, esperado, margen=0.001):
    return abs(valor - esperado) < margen


# ── Coordenadas escritas a mano ──────────────────────────────

@pytest.mark.parametrize("texto", [
    "25.6866, -100.3161",
    "25.6866,-100.3161",
    "25.6866 -100.3161",
    "  25.6866 , -100.3161  ",
])
def test_coordenadas_decimales(texto):
    r = interpretar(texto)
    assert r["ok"], r.get("error")
    assert cerca(r["lat"], LAT) and cerca(r["lon"], LON)


def test_coordenadas_con_coma_decimal():
    """Media Europa y toda Latinoamérica escriben 25,6866."""
    r = interpretar("25,6866; -100,3161")
    assert r["ok"]
    assert cerca(r["lat"], LAT) and cerca(r["lon"], LON)


# ── Grados, minutos y segundos ───────────────────────────────

def test_grados_minutos_segundos():
    """Es lo que enseña Google Maps en su propia interfaz."""
    r = interpretar('25°41\'11.8"N 100°18\'57.9"W')
    assert r["ok"], r.get("error")
    assert cerca(r["lat"], LAT, 0.01)
    assert cerca(r["lon"], LON, 0.01)


def test_grados_con_o_de_oeste():
    """Un Google Maps en español escribe O, no W."""
    r = interpretar('25°41\'11.8"N 100°18\'57.9"O')
    assert r["ok"]
    assert r["lon"] < 0, "Oeste tiene que salir negativo"


def test_hemisferio_sur_y_este():
    r = interpretar('37°50\'21.0"S 144°58\'6.0"E')
    assert r["ok"]
    assert r["lat"] < 0 and r["lon"] > 0


# ── Enlaces de Google Maps ───────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://www.google.com/maps/@25.6866,-100.3161,17z",
    "https://www.google.com/maps/place/Circuito/@25.6866,-100.3161,17z/data=!3m1",
    "https://maps.google.com/?q=25.6866,-100.3161",
    "https://www.google.com/maps?q=25.6866,-100.3161&z=15",
])
def test_enlaces_de_mapa(url):
    r = interpretar(url)
    assert r["ok"], r.get("error")
    assert cerca(r["lat"], LAT) and cerca(r["lon"], LON)


def test_enlace_sin_coordenadas_explica_como_sacarlas():
    r = interpretar("https://www.google.com/maps/search/autodromo")
    assert not r["ok"]
    assert "clic derecho" in r["error"]


# ── Rechazos ─────────────────────────────────────────────────

def test_vacio():
    assert not interpretar("")["ok"]
    assert not interpretar("   ")["ok"]


def test_texto_sin_sentido_explica_los_formatos():
    r = interpretar("el autodromo de por aqui")
    assert not r["ok"]
    assert "25.6866" in r["error"], "el error debe enseñar un ejemplo"


def test_latitud_imposible():
    r = interpretar("95.0, 10.0")
    assert not r["ok"]
    assert "latitud" in r["error"].lower()


def test_longitud_imposible():
    r = interpretar("10.0, 200.0")
    assert not r["ok"]
    assert "longitud" in r["error"].lower()


# ── Circuitos reales del mundo ───────────────────────────────

@pytest.mark.parametrize("nombre,lat,lon", [
    ("Autódromo de Panamá",       8.7016,  -79.8702),
    ("Circuit de Barcelona",     41.5700,    2.2611),
    ("Silverstone",              52.0733,   -1.0147),
    ("Suzuka",                   34.8431,  136.5411),
    ("Phillip Island",          -38.5000,  145.2333),
    ("Interlagos",              -23.7036,  -46.6997),
])
def test_circuitos_de_cualquier_parte(nombre, lat, lon):
    """El producto se vende fuera de Panamá: los cuatro cuadrantes del
    planeta tienen que interpretarse bien, con sus signos."""
    r = interpretar(f"{lat}, {lon}")
    assert r["ok"], f"{nombre}: {r.get('error')}"
    assert cerca(r["lat"], lat) and cerca(r["lon"], lon)


def test_el_clima_ya_no_fuerza_la_zona_horaria_de_panama():
    """Estaba fija en America/Panama: un cliente en España veía sus horas
    corridas siete husos."""
    fuente = (RAIZ / "src" / "services" / "weather_services.py").read_text(encoding="utf-8")

    # Se miran solo las líneas de código: el comentario que explica este
    # cambio nombra el huso viejo, y eso no es lo que se está buscando.
    codigo = [l for l in fuente.splitlines() if not l.strip().startswith("#")]

    assert not any("America/Panama" in l for l in codigo)
    assert any('"timezone": "auto"' in l for l in codigo)

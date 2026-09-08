"""El current.xml de demostración, leído por el parser de verdad.

Estas son las primeras pruebas de timing_services, que son 796 líneas de
interpretación del XML de MyLaps sin una sola prueba hasta ahora. No se
cubre todo el módulo —buena parte cruza contra la base de datos—, pero sí
la lectura pura, que es la que se rompe en silencio cuando MyLaps cambia
un campo de sitio.

El archivo de demostración sirve justo para esto: da un XML conocido, con
datos ficticios y sin depender de una unidad de red montada.
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.services.timing_services import (        # noqa: E402
    _del_xml, _segundos, _titulo_tanda, leer_xml,
)

DEMO = RAIZ / "src" / "public" / "demo" / "current.demo.xml"


@pytest.fixture(scope="module")
def datos():
    return leer_xml(str(DEMO))


def test_el_archivo_de_demostracion_existe():
    """Se distribuye con el producto: el asistente lo usa para comprobar
    que el cronometraje se lee antes de que haya una carrera de verdad."""
    assert DEMO.is_file()


def test_se_leen_las_etiquetas(datos):
    l = datos["labels"]

    for campo in ("eventname", "trackname", "groupname", "leader",
                  "bestlapby", "bestlaptime", "racetime", "laps", "flag"):
        assert campo in l, f"falta la etiqueta {campo}"
        assert l[campo] != "" or campo in ("flag",)


def test_los_datos_son_reconociblemente_falsos(datos):
    """Si esto saliera al aire por error en una carrera real, tiene que
    notarse en el primer segundo. Un dato falso que parece real es peor
    que no tener dato."""
    l = datos["labels"]

    assert "DEMO" in l["eventname"].upper()
    assert "DEMO" in l["trackname"].upper()

    for fila in datos["filas"]:
        assert "DEMO" in (fila.get("fullname") or "").upper()


def test_no_lleva_datos_personales_de_nadie(datos):
    """Los current.xml reales del repositorio traen 36 nombres de pilotos
    de verdad, sus transponders y un correo. Eso no se distribuye."""
    import xml.etree.ElementTree as ET

    raiz = ET.parse(DEMO).getroot()
    assert "autodromopanama" not in (raiz.get("user") or "")
    assert raiz.get("user") == "demo@racecorestudio.com"


def test_la_clasificacion_esta_ordenada(datos):
    posiciones = [int(f.get("position")) for f in datos["filas"]]

    assert posiciones == sorted(posiciones)
    assert posiciones[0] == 1
    assert len(posiciones) == len(set(posiciones)), "posiciones repetidas"


def test_el_lider_no_tiene_diferencia(datos):
    """Contra sí mismo no se mide nada, y la plantilla pinta el campo tal
    cual: un '0.000' ahí se vería al aire."""
    assert (datos["filas"][0].get("difference") or "") == ""


def test_las_diferencias_crecen_hacia_atras(datos):
    previa = 0.0

    for fila in datos["filas"][1:]:
        segundos = _segundos(fila.get("difference"))
        if segundos is None:      # doblado: "1 Lap", no es un tiempo
            continue
        assert segundos > previa, "una diferencia menor que la anterior"
        previa = segundos


def test_incluye_un_coche_doblado(datos):
    """El parser trata aparte a los doblados. Sin un caso en la demo, ese
    camino del código no se prueba nunca."""
    doblados = [f for f in datos["filas"]
                if "Lap" in (f.get("difference") or "")]

    assert doblados, "la demo debería incluir al menos un doblado"
    assert _segundos(doblados[0].get("difference")) is None


def test_incluye_un_carro_compartido(datos):
    """MyLaps parte el nombre por donde cae cuando dos pilotos comparten
    carro. Es la razón por la que el sistema cruza por número contra la
    base en vez de fiarse del XML, así que la demo lo reproduce."""
    compartidos = [f for f in datos["filas"] if (f.get("lastname") or "")]

    assert compartidos, "la demo debería incluir un carro compartido"


def test_formato_de_tiempos_como_mylaps(datos):
    """MyLaps escribe '0.885', no '00.885', y '1:16.364' pasado el minuto.
    Las plantillas pintan la cadena tal cual, así que un cero de más se ve
    al aire."""
    import re

    for fila in datos["filas"]:
        mejor = fila.get("besttime")
        assert re.fullmatch(r"\d+:\d{2}\.\d{3}|\d{1,2}\.\d{3}", mejor), mejor

        dif = fila.get("difference") or ""
        if dif and "Lap" not in dif:
            assert not dif.startswith("0") or dif[1] == ".", dif


def test_el_titulo_de_la_tanda_se_arma(datos):
    l = datos["labels"]
    assert _titulo_tanda(l["runtype"], l["runname"]) == "HEAT-1"


# ── Direcciones de red ───────────────────────────────────────

def test_se_anuncia_la_direccion_para_el_ipad():
    """El backend atiende en 0.0.0.0, que nadie puede escribir en un
    navegador. El asistente tiene que poder enseñar la dirección real."""
    from config import settings
    from src.services.red_services import direcciones

    d = direcciones()

    assert d["puerto"] == settings.API_PORT
    assert d["local"] == f"http://127.0.0.1:{settings.API_PORT}"
    assert d["abierto_a_la_red"] is True
    assert d["red"] is None or d["red"].startswith("http://")
    assert "0.0.0.0" not in (d["red"] or ""), "0.0.0.0 no es una dirección"

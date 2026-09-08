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

DEMO = RAIZ / "src" / "public" / "demo" / "current-demo.xml"


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


def test_el_evento_se_declara_de_demostracion(datos):
    """La salvaguarda está en el rótulo del evento, no en los nombres.

    Los pilotos son verosímiles a propósito: una tabla con «PILOTO 01» no
    sirve para enseñarle el producto a nadie ni para revisar cómo quedan
    las plantillas. Lo que canta que esto es de mentira es el evento, que
    sale al aire en su propio gráfico.
    """
    l = datos["labels"]

    assert "DEMOSTRACION" in l["eventname"].upper()
    assert "DEMO" in l["trackname"].upper()
    assert "DEMO" in l["groupname"].upper()


def test_todos_los_pilotos_llevan_la_ficha_completa(datos):
    """Una tabla a medias no sirve para revisar plantillas: la del piloto
    sin marca se vería bien por casualidad."""
    for fila in datos["filas"]:
        for campo in ("no", "fullname", "besttime", "lasttime", "laps",
                      "averagespeed", "bestspeed", "totaltime",
                      "transponder", "class", "position"):
            assert (fila.get(campo) or "").strip(), f"falta {campo} en {fila.get('no')}"

        # additional4 es el país y additional6 la marca, igual que en el
        # XML real del autódromo.
        assert (fila.get("additional4") or "").strip(), "falta el país"
        assert (fila.get("additional6") or "").strip(), "falta la marca"
        assert (fila.get("additional1") or "").strip(), "falta el equipo"


def test_hay_pilotos_de_varios_paises(datos):
    """El producto se vende fuera de Panamá y las banderas se pintan desde
    este campo: con un solo país no se ve si el resto funciona."""
    paises = {f.get("additional4") for f in datos["filas"]}
    assert len(paises) >= 4, paises


def test_las_marcas_no_se_repiten_todas(datos):
    marcas = {f.get("additional6") for f in datos["filas"]}
    assert len(marcas) >= 20, "muy pocas marcas distintas para revisar el arte"


def test_los_dorsales_son_unicos(datos):
    """Dos coches con el mismo dorsal romperían el cruce contra la base:
    es la llave que ata una fila del cronometraje con un vehículo."""
    dorsales = [f.get("no") for f in datos["filas"]]
    assert len(dorsales) == len(set(dorsales))


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


# ── La penalización ──────────────────────────────────────────
#
# MyLaps no manda ninguna marca de penalización: no existe un campo que
# la declare. Lo que hace es calcular `difference` contra el coche MÁS
# RÁPIDO y no contra quien va primero, y con una sanción esos dos dejan
# de ser el mismo. El sancionado queda como referencia con la diferencia
# VACÍA, y es al primero de la clasificación a quien MyLaps le pone un
# tiempo.
#
# Es la única forma de ejercitar `_reencuadrar_diferencias`, que es la
# función más delicada del módulo y no tenía ninguna prueba.

def test_la_firma_de_la_penalizacion_esta_en_el_archivo(datos):
    p1, p2 = datos["filas"][0], datos["filas"][1]

    assert (p1.get("difference") or "").strip(), \
        "el primero debería llevar diferencia: la referencia es otro"
    assert not (p2.get("difference") or "").strip(), \
        "el sancionado es la referencia de MyLaps: su diferencia va vacía"


def test_el_sancionado_tiene_mejor_tiempo_que_el_primero(datos):
    """Es lo que lo delata: va más rápido y sale detrás."""
    def a_segundos(t):
        minutos, _, resto = t.partition(":")
        return float(minutos) * 60 + float(resto) if resto else float(minutos)

    p1 = a_segundos(datos["filas"][0].get("totaltime"))
    p2 = a_segundos(datos["filas"][1].get("totaltime"))

    assert p2 < p1, "el sancionado debería tener mejor tiempo total"


def test_al_reencuadrar_el_sancionado_sale_en_negativo(datos):
    """Lo que de verdad se ve al aire.

    Tras reencuadrar contra el primero, quien va delante en pista y
    detrás en la clasificación queda con diferencia negativa. Sin eso los
    dos salían en blanco y no había forma de saber qué pasaba.
    """
    from src.services.timing_services import _reencuadrar_diferencias

    standings = [
        {"position": int(f.get("position")), "no": f.get("no"),
         "leader": f.get("difference"), "interval": f.get("gap")}
        for f in datos["filas"]
    ]
    _reencuadrar_diferencias(standings)

    assert (standings[0]["leader"] or "") == "", \
        "el primero queda en cero, y el tótem le escribe su etiqueta"

    negativos = [s for s in standings if (s["leader"] or "").startswith("-")]
    assert len(negativos) == 1, f"se esperaba un solo sancionado, hay {len(negativos)}"
    assert negativos[0]["position"] == 2


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

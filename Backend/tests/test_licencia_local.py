"""Validación de la clave de licencia sin servidor.

Es el sustituto provisional del servidor de licencias. Lo que se vigila
aquí es que perdone lo que da igual —mayúsculas, espacios, guiones— y no
perdone nada de lo que importa.
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "installer"))

from licencia_local import (                                  # noqa: E402
    CORREO_AUTORIZADO, HUELLA_CLAVE, normalizar, validar,
)

CLAVE = "RCS1-XEA8-EXXK-EUNH-8M63"


# ── Lo que tiene que pasar ───────────────────────────────────

def test_la_clave_buena_valida():
    r = validar(CORREO_AUTORIZADO, CLAVE)
    assert r["ok"]
    assert r["plan"] == "pro"
    assert r["dias"] > 0
    assert r["gracia_dias"] > 0


@pytest.mark.parametrize("escrito", [
    "RCS1-XEA8-EXXK-EUNH-8M63",
    "rcs1-xea8-exxk-eunh-8m63",
    "RCS1 XEA8 EXXK EUNH 8M63",
    "  rcs1-XEA8-exxk-EUNH-8m63  ",
    "RCS1XEA8EXXKEUNH8M63",
    "RCS1_XEA8_EXXK_EUNH_8M63",
])
def test_se_perdona_como_la_teclean(escrito):
    """La gente la copia de un correo, la dicta por teléfono o la escribe
    en minúsculas. Nada de eso debería ser un error de licencia."""
    assert validar(CORREO_AUTORIZADO, escrito)["ok"], escrito


@pytest.mark.parametrize("correo", [
    "zentogotech@gmail.com",
    "ZentogoTech@Gmail.com",
    "  zentogotech@gmail.com  ",
])
def test_el_correo_no_distingue_mayusculas(correo):
    assert validar(correo, CLAVE)["ok"]


# ── Lo que no ────────────────────────────────────────────────

def test_otro_correo_no_vale():
    assert not validar("otro@ejemplo.com", CLAVE)["ok"]


def test_otra_clave_no_vale():
    assert not validar(CORREO_AUTORIZADO, "RCS1-AAAA-AAAA-AAAA-AAAA")["ok"]


def test_un_caracter_cambiado_no_vale():
    """Un dígito mal copiado tiene que fallar, no colar por aproximación."""
    casi = CLAVE[:-1] + ("4" if CLAVE[-1] != "4" else "6")
    assert not validar(CORREO_AUTORIZADO, casi)["ok"]


@pytest.mark.parametrize("mala", ["", "hola", "RCS1-XXXX", "RCS2-XEA8-EXXK-EUNH-8M63",
                                  "RCS1-XEA8-EXXK-EUNH-8M6", "XEA8-EXXK-EUNH-8M63"])
def test_formatos_invalidos(mala):
    assert not validar(CORREO_AUTORIZADO, mala)["ok"]


def test_sin_correo_lo_dice():
    r = validar("", CLAVE)
    assert r["motivo"] == "falta_correo"


def test_correo_sin_arroba_lo_dice():
    r = validar("noesuncorreo", CLAVE)
    assert r["motivo"] == "correo_invalido"


def test_el_formato_malo_se_distingue_de_la_clave_que_no_corresponde():
    """Son dos problemas distintos para quien instala: uno se arregla
    mirando lo que tecleó, el otro llamando a soporte."""
    assert validar(CORREO_AUTORIZADO, "esto-no-es-una-clave")["motivo"] == "formato"
    assert validar(CORREO_AUTORIZADO, "RCS1-AAAA-AAAA-AAAA-AAAA")["motivo"] == "no_corresponde"


def test_el_error_no_dice_cual_de_los_dos_falla():
    """Decir si falló el correo o la clave le regala a quien prueba la
    mitad del problema."""
    por_correo = validar("otro@ejemplo.com", CLAVE)
    por_clave = validar(CORREO_AUTORIZADO, "RCS1-AAAA-AAAA-AAAA-AAAA")

    assert por_correo["error"] == por_clave["error"]
    assert por_correo["motivo"] == por_clave["motivo"]


# ── La clave no está en el código ────────────────────────────

def test_el_codigo_guarda_el_resumen_y_no_la_clave():
    """Quien lea el archivo ve un hash. De un hash no se saca la clave."""
    fuente = (RAIZ / "installer" / "licencia_local.py").read_text(encoding="utf-8")

    assert CLAVE not in fuente
    assert HUELLA_CLAVE in fuente
    assert len(HUELLA_CLAVE) == 64


def test_normalizar_deja_el_formato_canonico():
    assert normalizar("rcs1xea8exxkeunh8m63") == CLAVE
    assert normalizar("  RCS1 XEA8 EXXK EUNH 8M63 ") == CLAVE

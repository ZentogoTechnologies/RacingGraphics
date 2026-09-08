"""El asistente de instalación: token, validaciones y las tres cuentas.

Lo que se vigila aquí es sobre todo la puerta: el asistente es lo único
del backend que responde sin sesión, así que si su protección falla,
cualquiera en la red local se nombra dueño del sistema.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from config import settings                                      # noqa: E402
from src.schemas.instalacion_schemas import (                    # noqa: E402
    Clima, CuentaNueva, DatosUsuarios, Organizacion,
)
from src.services import instalacion_services as inst            # noqa: E402


@pytest.fixture
def token_en_disco(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETUP_TOKEN_FILE", str(tmp_path / "setup.token"))
    return inst.crear_token()


# ── El token que protege el asistente ────────────────────────

def test_el_token_se_crea_y_valida(token_en_disco):
    assert inst.token_valido(token_en_disco)


def test_un_token_equivocado_no_pasa(token_en_disco):
    assert not inst.token_valido("no-es-el-token")
    assert not inst.token_valido("")
    assert not inst.token_valido(None)


def test_un_prefijo_correcto_tampoco_pasa(token_en_disco):
    """Que empiece bien no vale: se compara entero y en tiempo constante."""
    assert not inst.token_valido(token_en_disco[:-1])
    assert not inst.token_valido(token_en_disco + "x")


def test_sin_archivo_no_hay_token_valido(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETUP_TOKEN_FILE", str(tmp_path / "no-existe"))
    assert not inst.token_valido("cualquier-cosa")


def test_al_borrarlo_el_asistente_se_cierra(token_en_disco):
    inst.borrar_token()
    assert not inst.token_valido(token_en_disco)


def test_el_token_es_largo_de_verdad(token_en_disco):
    """Corto se adivina a fuerza de intentos, y el asistente está expuesto
    a toda la red local mientras dura la instalación."""
    assert len(token_en_disco) >= 30


# ── Las tres cuentas ─────────────────────────────────────────

def cuentas(owner="dueno", admin="jefe", standard="operador",
            claves=("clave-owner-1", "clave-admin-2", "clave-oper-3")):
    return {
        "owner": {"username": owner, "password": claves[0]},
        "admin": {"username": admin, "password": claves[1]},
        "standard": {"username": standard, "password": claves[2]},
    }


def test_las_tres_cuentas_validas():
    d = DatosUsuarios(**cuentas())
    assert d.owner.username == "dueno"
    assert d.standard.username == "operador"


def test_no_se_permiten_nombres_repetidos():
    with pytest.raises(ValidationError, match="nombres distintos"):
        DatosUsuarios(**cuentas(owner="mismo", admin="mismo"))


def test_los_nombres_repetidos_se_detectan_sin_importar_mayusculas():
    with pytest.raises(ValidationError, match="nombres distintos"):
        DatosUsuarios(**cuentas(owner="Pablo", admin="pablo"))


def test_no_se_permite_repetir_contrasena():
    """Tres cuentas con la misma clave no separan nada: quien tiene una
    las tiene todas, y el reparto de roles queda de adorno."""
    with pytest.raises(ValidationError, match="propia contraseña"):
        DatosUsuarios(**cuentas(claves=("igual-para-todos",) * 3))


def test_contrasena_corta_rechazada():
    with pytest.raises(ValidationError):
        CuentaNueva(username="alguien", password="corta")


@pytest.mark.parametrize("malo", ["ab", "con espacio", "acentuadó", "a" * 33, "@raro"])
def test_nombres_de_usuario_invalidos(malo):
    with pytest.raises(ValidationError):
        CuentaNueva(username=malo, password="una-clave-larga")


# ── Datos del cliente ────────────────────────────────────────

def test_la_organizacion_exige_nombre_y_pais():
    o = Organizacion(organizacion="Autódromo de Ejemplo", pais="España")
    assert o.organizacion == "Autódromo de Ejemplo"
    assert o.circuito == ""       # opcional


def test_los_espacios_sobrantes_se_limpian():
    o = Organizacion(organizacion="  Circuito   del   Norte  ", pais=" Chile ")
    assert o.organizacion == "Circuito del Norte"
    assert o.pais == "Chile"


def test_sin_organizacion_no_hay_instalacion():
    with pytest.raises(ValidationError):
        Organizacion(organizacion="", pais="México")


def test_coordenadas_fuera_de_rango():
    with pytest.raises(ValidationError):
        Clima(lat=91, lon=0)
    with pytest.raises(ValidationError):
        Clima(lat=0, lon=181)


def test_coordenadas_de_cualquier_parte_del_mundo():
    """El producto se vende fuera de Panamá: cualquier circuito del mundo
    tiene que poder configurarse."""
    for lat, lon in [(41.57, 2.26), (-37.84, 144.96), (35.37, 138.93), (8.70, -79.87)]:
        assert Clima(lat=lat, lon=lon).lat == lat


# ── Nada del producto trae un cliente puesto ─────────────────

def test_el_clima_no_apunta_a_ningun_cliente():
    """Estas coordenadas estaban fijas en un autódromo concreto."""
    assert settings.WEATHER_LAT == 0.0
    assert settings.WEATHER_LON == 0.0
    assert settings.WEATHER_PLACE == ""
    assert settings.WEATHER_COUNTRY == ""


def test_la_instalacion_nace_vacia():
    """Se miran los valores por defecto declarados, no una instancia: un
    documento de Beanie no se puede crear sin haber conectado la base."""
    from src.models.instalacion_model import PASOS, Instalacion

    campos = Instalacion.model_fields

    assert campos["organizacion"].default == ""
    assert campos["pais"].default == ""
    assert campos["ciudad"].default == ""
    assert campos["circuito"].default == ""
    assert campos["lat"].default is None
    assert campos["lon"].default is None
    assert campos["completada"].default is False
    assert campos["paso"].default == PASOS[0]


def test_el_asistente_pide_las_cuentas_antes_de_lo_demas():
    """Sin cuentas no se puede entrar al panel, así que ese paso no puede
    quedar detrás de los ajustes técnicos."""
    from src.models.instalacion_model import PASOS

    assert PASOS.index("usuarios") < PASOS.index("cronometraje")
    assert PASOS[-1] == "listo"

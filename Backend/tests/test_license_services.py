"""Pruebas de la validación de licencia.

Se prueba con claves generadas al vuelo, no con la clave real de Zentogo:
las pruebas tienen que poder correr en cualquier máquina y en CI sin que
nadie tenga la privada de producción a mano.

Lo que se vigila aquí, por orden de gravedad si fallara:

  · Que una licencia vencida NO siga operando pasada la gracia. Es el
    dinero de la empresa.
  · Que una licencia válida SÍ opere. Es un cliente en vivo; un falso
    bloqueo aquí apaga una transmisión.
  · Que no se pueda falsificar: otra clave, otro equipo, otro producto,
    token retocado, o el clásico "alg": "none".
"""

import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings                                  # noqa: E402
from src.services import license_services as lic             # noqa: E402

EQUIPO = "a" * 64
OTRA_MAQUINA = "b" * 64


def par_de_claves() -> tuple[str, str]:
    privada = Ed25519PrivateKey.generate()
    pem_priv = privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pem_pub = privada.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return pem_priv, pem_pub


@pytest.fixture
def claves():
    return par_de_claves()


def token(
    privada: str,
    *,
    dias_para_vencer: float = 30,
    equipo: str = EQUIPO,
    producto: str = lic.PRODUCTO,
    gracia_dias: int = 15,
    emisor: str = lic.EMISOR,
    nbf_en_dias: float | None = None,
    plan: str = "pro",
) -> str:
    ahora = datetime.now(timezone.utc)
    carga = {
        "iss": emisor,
        "jti": str(uuid.uuid4()),
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(days=dias_para_vencer)).timestamp()),
        "producto": producto,
        "cliente": "Autódromo Panamá",
        "correo": "pablo@autodromopanama.com",
        "equipo": equipo,
        "plan": plan,
        "features": ["graficos", "pilotos"],
        "version_max": "1.2.0",
        "gracia_dias": gracia_dias,
        "revalidar_dias": 7,
    }
    if nbf_en_dias is not None:
        carga["nbf"] = int((ahora + timedelta(days=nbf_en_dias)).timestamp())

    return jwt.encode(carga, privada, algorithm="EdDSA")


# ── El camino feliz ──────────────────────────────────────────

def test_licencia_vigente_opera(claves):
    priv, pub = claves
    r = lic.verificar_token(token(priv), huella=EQUIPO, clave_publica=pub)

    assert r.estado is lic.Estado.ACTIVA
    assert r.opera
    assert r.cliente == "Autódromo Panamá"
    assert r.plan == "pro"
    assert 29 <= r.dias_restantes <= 30


def test_resumen_no_filtra_el_equipo_ni_el_token(claves):
    """El panel enseña el estado, no la huella cruda de la máquina."""
    priv, pub = claves
    resumen = lic.verificar_token(token(priv), huella=EQUIPO, clave_publica=pub).resumen()

    assert "equipo" not in resumen
    assert EQUIPO not in json.dumps(resumen)


# ── Vencimiento y gracia ─────────────────────────────────────

def test_recien_vencida_entra_en_gracia_y_sigue_operando(claves):
    """El caso que no puede fallar: venció ayer, hay carrera hoy."""
    priv, pub = claves
    r = lic.verificar_token(
        token(priv, dias_para_vencer=-1, gracia_dias=15),
        huella=EQUIPO, clave_publica=pub,
    )

    assert r.estado is lic.Estado.GRACIA
    assert r.opera, "una licencia dentro de la gracia tiene que seguir al aire"
    assert r.dias_de_gracia_restantes == 13


def test_pasada_la_gracia_se_bloquea(claves):
    priv, pub = claves
    r = lic.verificar_token(
        token(priv, dias_para_vencer=-20, gracia_dias=15),
        huella=EQUIPO, clave_publica=pub,
    )

    assert r.estado is lic.Estado.EXPIRADA
    assert not r.opera


def test_sin_gracia_el_bloqueo_es_inmediato(claves):
    priv, pub = claves
    r = lic.verificar_token(
        token(priv, dias_para_vencer=-0.5, gracia_dias=0),
        huella=EQUIPO, clave_publica=pub,
    )

    assert r.estado is lic.Estado.EXPIRADA


def test_el_limite_de_la_gracia_se_respeta_al_dia(claves):
    """Justo dentro opera; justo fuera, no."""
    priv, pub = claves

    dentro = lic.verificar_token(
        token(priv, dias_para_vencer=-14.9, gracia_dias=15),
        huella=EQUIPO, clave_publica=pub,
    )
    fuera = lic.verificar_token(
        token(priv, dias_para_vencer=-15.1, gracia_dias=15),
        huella=EQUIPO, clave_publica=pub,
    )

    assert dentro.estado is lic.Estado.GRACIA
    assert fuera.estado is lic.Estado.EXPIRADA


# ── Falsificación ────────────────────────────────────────────

def test_firmada_con_otra_clave_no_sirve(claves):
    """El ataque obvio: generarse un par propio y emitirse licencias."""
    _, pub = claves
    otra_privada, _ = par_de_claves()

    r = lic.verificar_token(token(otra_privada), huella=EQUIPO, clave_publica=pub)
    assert r.estado is lic.Estado.INVALIDA
    assert not r.opera


def test_token_retocado_no_sirve(claves):
    priv, pub = claves
    bueno = token(priv)

    cabecera, carga, firma = bueno.split(".")
    # Se cambia un carácter de la carga; la firma deja de cuadrar.
    roto = f"{cabecera}.{carga[:-4]}XXXX.{firma}"

    r = lic.verificar_token(roto, huella=EQUIPO, clave_publica=pub)
    assert r.estado is lic.Estado.INVALIDA


def test_alg_none_no_se_acepta(claves):
    """El clásico: quitar la firma declarando que no hace falta."""
    _, pub = claves
    sin_firma = jwt.encode(
        {"iss": lic.EMISOR, "exp": 9999999999, "iat": 1, "producto": lic.PRODUCTO,
         "equipo": EQUIPO, "gracia_dias": 9999},
        key="", algorithm="none",
    )

    r = lic.verificar_token(sin_firma, huella=EQUIPO, clave_publica=pub)
    assert r.estado is lic.Estado.INVALIDA


def test_emisor_ajeno_no_sirve(claves):
    priv, pub = claves
    r = lic.verificar_token(
        token(priv, emisor="otro-emisor"), huella=EQUIPO, clave_publica=pub
    )
    assert r.estado is lic.Estado.INVALIDA


def test_sin_exp_no_sirve(claves):
    """Una licencia sin vencimiento sería perpetua; se exige el campo."""
    priv, pub = claves
    perpetua = jwt.encode(
        {"iss": lic.EMISOR, "iat": 1, "producto": lic.PRODUCTO, "equipo": EQUIPO},
        priv, algorithm="EdDSA",
    )

    r = lic.verificar_token(perpetua, huella=EQUIPO, clave_publica=pub)
    assert r.estado is lic.Estado.INVALIDA


# ── Equipo y producto ────────────────────────────────────────

def test_licencia_de_otra_maquina(claves):
    priv, pub = claves
    r = lic.verificar_token(token(priv), huella=OTRA_MAQUINA, clave_publica=pub)

    assert r.estado is lic.Estado.OTRO_EQUIPO
    assert not r.opera


def test_licencia_de_otro_producto(claves):
    """Mañana habrá Race America en el mismo equipo."""
    priv, pub = claves
    r = lic.verificar_token(
        token(priv, producto="race-america"), huella=EQUIPO, clave_publica=pub
    )

    assert r.estado is lic.Estado.OTRO_PRODUCTO
    assert not r.opera


def test_el_equipo_se_revisa_antes_que_la_fecha(claves):
    """Una licencia vencida Y de otra máquina reporta la máquina.

    Si dijera «expiró», el cliente renovaría y seguiría sin funcionar.
    """
    priv, pub = claves
    r = lic.verificar_token(
        token(priv, dias_para_vencer=-100), huella=OTRA_MAQUINA, clave_publica=pub
    )

    assert r.estado is lic.Estado.OTRO_EQUIPO


def test_aun_no_vigente(claves):
    priv, pub = claves
    r = lic.verificar_token(
        token(priv, nbf_en_dias=10), huella=EQUIPO, clave_publica=pub
    )

    assert r.estado is lic.Estado.AUN_NO_VIGENTE
    assert not r.opera


# ── Archivo, reloj y modo desarrollo ─────────────────────────

@pytest.fixture
def entorno(tmp_path, monkeypatch, claves):
    """Aísla los archivos de licencia y la clave pública en un temporal."""
    priv, pub = claves
    monkeypatch.setattr(settings, "LICENSE_FILE", str(tmp_path / "licencia.lic"))
    monkeypatch.setattr(settings, "LICENSE_STATE_FILE", str(tmp_path / "estado.json"))
    monkeypatch.setattr(settings, "LICENSE_REQUIRED", False)
    monkeypatch.setattr(lic, "CLAVE_PUBLICA_PEM", pub)
    monkeypatch.setattr(lic, "huella_equipo", lambda: EQUIPO)
    lic.limpiar_cache()
    yield tmp_path, priv, pub
    lic.limpiar_cache()


def test_sin_archivo_y_sin_exigir_es_modo_desarrollo(entorno):
    assert lic.leer_licencia().estado is lic.Estado.DESARROLLO
    assert lic.leer_licencia().opera


def test_sin_archivo_pero_exigida_bloquea(entorno, monkeypatch):
    monkeypatch.setattr(settings, "LICENSE_REQUIRED", True)
    r = lic.leer_licencia()

    assert r.estado is lic.Estado.SIN_LICENCIA
    assert not r.opera


def test_guardar_licencia_valida_antes_de_escribir(entorno):
    """Una licencia inservible no debe quedar en el disco del cliente."""
    tmp, priv, _ = entorno
    mala = token(priv, equipo=OTRA_MAQUINA)

    r = lic.guardar_licencia(mala)

    assert r.estado is lic.Estado.OTRO_EQUIPO
    assert not Path(settings.LICENSE_FILE).exists()


def test_guardar_y_releer(entorno):
    tmp, priv, _ = entorno

    guardada = lic.guardar_licencia(token(priv))
    assert guardada.estado is lic.Estado.ACTIVA
    assert Path(settings.LICENSE_FILE).exists()

    assert lic.leer_licencia().estado is lic.Estado.ACTIVA


def test_atrasar_el_reloj_se_detecta(entorno, monkeypatch):
    """Atrasar la fecha del sistema es la forma fácil de estirar una
    licencia vencida. La marca de agua lo caza."""
    tmp, priv, _ = entorno
    lic.guardar_licencia(token(priv))

    # Una visita "hoy" deja la marca puesta.
    assert lic.leer_licencia().estado is lic.Estado.ACTIVA

    # Ahora el reloj aparece dos meses atrás.
    real = lic._ahora
    monkeypatch.setattr(lic, "_ahora", lambda: real() - timedelta(days=60))
    lic.limpiar_cache()

    assert lic.leer_licencia().estado is lic.Estado.RELOJ_ALTERADO


def test_un_desfase_pequeno_no_molesta(entorno, monkeypatch):
    """Un equipo que perdió la pila arranca con la fecha corrida. Eso no
    es hacer trampa y no puede dejar a nadie sin gráficos."""
    tmp, priv, _ = entorno
    lic.guardar_licencia(token(priv))
    lic.leer_licencia()

    real = lic._ahora
    monkeypatch.setattr(lic, "_ahora", lambda: real() - timedelta(hours=12))
    lic.limpiar_cache()

    assert lic.leer_licencia().estado is lic.Estado.ACTIVA


def test_la_cache_caduca(entorno, monkeypatch):
    tmp, priv, _ = entorno
    lic.guardar_licencia(token(priv))

    assert lic.estado_licencia().estado is lic.Estado.ACTIVA

    # Se borra el archivo y se exige licencia: con la caché todavía viva
    # el estado no debe cambiar; al caducar, sí.
    Path(settings.LICENSE_FILE).unlink()
    monkeypatch.setattr(settings, "LICENSE_REQUIRED", True)

    assert lic.estado_licencia().estado is lic.Estado.ACTIVA
    assert lic.estado_licencia(refrescar=True).estado is lic.Estado.SIN_LICENCIA

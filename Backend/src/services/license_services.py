"""Validación de la licencia.

Toda la autoridad sobre si el software puede operar vive aquí, en el
backend, y se resuelve **sin red**. La licencia es un JWT firmado con
Ed25519 por el servidor de Zentogo; el backend solo lleva la clave
pública, así que puede comprobar que un token es auténtico pero no puede
fabricar uno.

Por qué offline: el software se usa en autódromos, y en un autódromo la
red se cae. Un sistema que exigiera contactar al servidor en cada arranque
apagaría los gráficos de un cliente al día durante una transmisión en
vivo. Aquí la conexión hace falta para *instalar* y para *renovar*, nunca
para trabajar.

De ahí sale la regla que gobierna todo este módulo:

    Se bloquea por vencimiento comprobado, jamás por falta de conexión.

El vencimiento es un hecho que viaja firmado dentro del propio token y se
comprueba contra el reloj local. No saber si el cliente renovó no es
motivo para apagar nada: para eso está el periodo de gracia.

Estados posibles y qué significan para el usuario:

    DESARROLLO      No hay licencia y no se exige (equipo de trabajo).
    ACTIVA          Todo en orden.
    GRACIA          Venció, pero aún dentro del margen. Opera y avisa.
    EXPIRADA        Venció y se acabó el margen. Se bloquea.
    SIN_LICENCIA    Nunca se activó.
    INVALIDA        Firma que no cuadra, o archivo corrupto.
    OTRO_EQUIPO     Licencia legítima, pero de otra máquina.
    OTRO_PRODUCTO   Licencia legítima, pero de otro producto de Zentogo.
    AUN_NO_VIGENTE  Emitida con fecha de inicio futura.
    RELOJ_ALTERADO  El reloj del sistema retrocedió de forma sospechosa.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import jwt

from config import settings
from src.services.fingerprint_services import huella_equipo

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
#  CLAVE PÚBLICA
#
#  Va escrita en el código y NO en el .env a propósito. Si saliera de un
#  archivo de configuración, cualquiera podría sustituirla por una suya,
#  firmarse una licencia perpetua y saltarse todo esto. Escrita aquí,
#  cambiarla obliga a recompilar el backend.
#
#  La privada correspondiente vive únicamente en el servidor de licencias
#  de Zentogo y no aparece en este repositorio por ningún lado.
# ══════════════════════════════════════════════════════════════════════

CLAVE_PUBLICA_PEM = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAGb9ECWmEzf6FQbrBZ9w7lshQhqowtrbLDFw4rXAxZuE=
-----END PUBLIC KEY-----"""

# Ed25519. Se nombra el algoritmo explícitamente al verificar para que un
# token que llegue diciendo "alg": "none" no se acepte jamás.
ALGORITMO = "EdDSA"

EMISOR = "zentogo-licencias"

# Identificador de este producto. Cuando existan Race America o Race
# Motors, cada uno llevará el suyo y una licencia no servirá para otro.
PRODUCTO = "race-core-studio"


class Estado(str, Enum):
    DESARROLLO = "desarrollo"
    ACTIVA = "activa"
    GRACIA = "gracia"
    EXPIRADA = "expirada"
    SIN_LICENCIA = "sin_licencia"
    INVALIDA = "invalida"
    OTRO_EQUIPO = "otro_equipo"
    OTRO_PRODUCTO = "otro_producto"
    AUN_NO_VIGENTE = "aun_no_vigente"
    RELOJ_ALTERADO = "reloj_alterado"


# Los únicos estados con los que el software trabaja. Todo lo demás
# bloquea. Se declara como conjunto y no como una cadena de `if` para que
# la política se lea de un vistazo y no se pueda ampliar sin querer.
ESTADOS_QUE_OPERAN = {Estado.DESARROLLO, Estado.ACTIVA, Estado.GRACIA}


MENSAJES = {
    Estado.DESARROLLO: "Modo desarrollo: sin licencia instalada.",
    Estado.ACTIVA: "Licencia activa.",
    Estado.GRACIA: "La licencia venció. Renueva para no perder el servicio.",
    Estado.EXPIRADA: "La licencia expiró. Renueva para volver a operar.",
    Estado.SIN_LICENCIA: "No hay licencia instalada en este equipo.",
    Estado.INVALIDA: "La licencia no es válida o está dañada.",
    Estado.OTRO_EQUIPO: "Esta licencia pertenece a otro equipo.",
    Estado.OTRO_PRODUCTO: "Esta licencia es de otro producto de Zentogo.",
    Estado.AUN_NO_VIGENTE: "La licencia todavía no entra en vigencia.",
    Estado.RELOJ_ALTERADO: "El reloj del sistema no es confiable. Ajusta la fecha y hora.",
}


@dataclass
class Licencia:
    """El resultado de mirar la licencia: qué dice y qué se puede hacer."""

    estado: Estado
    mensaje: str = ""

    # Datos del token. Vacíos si no se pudo leer.
    licencia_id: Optional[str] = None
    cliente: Optional[str] = None
    correo: Optional[str] = None
    producto: Optional[str] = None
    plan: Optional[str] = None
    features: list[str] = field(default_factory=list)
    version_max: Optional[str] = None
    equipo: Optional[str] = None

    emitida: Optional[datetime] = None
    vence: Optional[datetime] = None
    gracia_dias: int = 0
    revalidar_dias: int = 0

    @property
    def opera(self) -> bool:
        return self.estado in ESTADOS_QUE_OPERAN

    @property
    def dias_restantes(self) -> Optional[int]:
        """Días hasta el vencimiento. Negativo si ya venció."""
        if self.vence is None:
            return None
        return (self.vence - _ahora()).days

    @property
    def fin_de_gracia(self) -> Optional[datetime]:
        if self.vence is None:
            return None
        return self.vence + timedelta(days=self.gracia_dias)

    @property
    def dias_de_gracia_restantes(self) -> Optional[int]:
        """Cuánto queda antes del bloqueo. Solo tiene sentido en GRACIA."""
        fin = self.fin_de_gracia
        if fin is None:
            return None
        return max(0, (fin - _ahora()).days)

    def resumen(self) -> dict:
        """Lo que se le enseña al panel. Sin el token ni la huella cruda."""
        return {
            "estado": self.estado.value,
            "opera": self.opera,
            "mensaje": self.mensaje or MENSAJES.get(self.estado, ""),
            "cliente": self.cliente,
            "correo": self.correo,
            "producto": self.producto,
            "plan": self.plan,
            "features": self.features,
            "version_max": self.version_max,
            "vence": self.vence.isoformat() if self.vence else None,
            "dias_restantes": self.dias_restantes,
            "gracia_dias": self.gracia_dias,
            "dias_de_gracia_restantes": (
                self.dias_de_gracia_restantes if self.estado is Estado.GRACIA else None
            ),
        }


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _sin_licencia(estado: Estado, mensaje: str = "") -> Licencia:
    return Licencia(estado=estado, mensaje=mensaje or MENSAJES.get(estado, ""))


# ── Dónde viven los archivos ─────────────────────────────────

def ruta_licencia() -> Path:
    """Archivo con el token. Lo escribe el instalador al activar."""
    return Path(settings.LICENSE_FILE).expanduser()


def ruta_estado() -> Path:
    """Marca de agua del reloj. Ver `_revisar_reloj`."""
    return Path(settings.LICENSE_STATE_FILE).expanduser()


# ── Reloj ────────────────────────────────────────────────────
#
# Atrasar la fecha del sistema es la forma más simple de estirar una
# licencia vencida. Contra eso se guarda la fecha más alta que se ha
# visto: si el reloj aparece por detrás de esa marca, algo se movió.
#
# La tolerancia es amplia a propósito. Un equipo que estuvo apagado y
# perdió la pila de la placa arranca con una fecha vieja sin que nadie
# haya hecho trampa, y castigar eso dejaría a un cliente honesto sin
# gráficos. Con margen de días, el error de buena fe pasa y el retroceso
# de meses —que es el que sirve para estirar una licencia— no.

def _revisar_reloj() -> bool:
    """True si el reloj es creíble. Actualiza la marca de agua."""
    archivo = ruta_estado()
    ahora = _ahora()
    visto = None

    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        visto = datetime.fromisoformat(datos["visto_max"])
    except (OSError, ValueError, KeyError, TypeError):
        # Sin marca previa no hay nada contra qué comparar. Puede ser la
        # primera vez, o que alguien la borrara; en ambos casos se vuelve
        # a empezar desde ahora en vez de bloquear.
        visto = None

    creible = True
    if visto is not None:
        if visto.tzinfo is None:
            visto = visto.replace(tzinfo=timezone.utc)
        if ahora < visto - timedelta(days=settings.LICENSE_CLOCK_TOLERANCE_DAYS):
            creible = False

    # La marca solo sube. Si el reloj está atrasado no se rebaja, porque
    # eso permitiría corregir la marca a base de arrancar con la fecha
    # cada vez un poco más atrás.
    tope = ahora if visto is None else max(ahora, visto)

    try:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(
            json.dumps({"visto_max": tope.isoformat()}, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        # No poder escribir la marca no puede tumbar el arranque: sería
        # apagar el software por un permiso de carpeta.
        logger.warning("No se pudo guardar la marca de reloj: %s", e)

    return creible


# ── Verificación ─────────────────────────────────────────────

def verificar_token(
    token: str,
    huella: Optional[str] = None,
    clave_publica: Optional[str] = None,
) -> Licencia:
    """Comprueba firma, producto, equipo y fechas de un token.

    `huella` y `clave_publica` se pueden inyectar para las pruebas; en
    producción salen del equipo y de la constante de este módulo.
    """
    huella = huella or huella_equipo()
    clave = clave_publica or CLAVE_PUBLICA_PEM

    try:
        # Las comprobaciones de fecha de PyJWT se desactivan a propósito, y
        # es la decisión central de todo el módulo. Por defecto, PyJWT
        # rechaza un token vencido (exp) o todavía no vigente (nbf) y no
        # devuelve nada de su contenido. Con eso no habría forma de saber
        # si estamos dentro del periodo de gracia o fuera de él, ni de
        # decirle al cliente cuándo venció, a nombre de quién estaba, ni
        # desde cuándo será válida una licencia adelantada: solo se sabría
        # "no sirve", que es justo el mensaje inútil que hace llamar a
        # soporte. Las dos fechas se evalúan más abajo, a mano.
        #
        # Lo que sí sigue verificando PyJWT es lo que no se negocia: la
        # firma y el algoritmo. Un token con la firma mala nunca llega a
        # la parte de las fechas.
        datos = jwt.decode(
            token,
            clave,
            algorithms=[ALGORITMO],
            issuer=EMISOR,
            options={
                "verify_exp": False,
                "verify_nbf": False,
                "require": ["exp", "iat", "iss"],
            },
        )
    except jwt.InvalidIssuerError:
        return _sin_licencia(Estado.INVALIDA, "La licencia no fue emitida por Zentogo.")
    except jwt.InvalidTokenError as e:
        logger.warning("Licencia rechazada: %s", e)
        return _sin_licencia(Estado.INVALIDA)

    def fecha(clave_: str) -> Optional[datetime]:
        valor = datos.get(clave_)
        if valor is None:
            return None
        return datetime.fromtimestamp(valor, tz=timezone.utc)

    lic = Licencia(
        estado=Estado.INVALIDA,
        licencia_id=datos.get("jti"),
        cliente=datos.get("cliente"),
        correo=datos.get("correo"),
        producto=datos.get("producto"),
        plan=datos.get("plan"),
        features=list(datos.get("features") or []),
        version_max=datos.get("version_max"),
        equipo=datos.get("equipo"),
        emitida=fecha("iat"),
        vence=fecha("exp"),
        gracia_dias=int(datos.get("gracia_dias", 0)),
        revalidar_dias=int(datos.get("revalidar_dias", 0)),
    )

    # El orden importa: primero se descarta que la licencia sea de otro
    # sitio, y solo después se miran las fechas. Decirle a alguien "tu
    # licencia venció" cuando en realidad es la del equipo de al lado
    # manda a revisar el problema equivocado.
    if lic.producto != PRODUCTO:
        lic.estado = Estado.OTRO_PRODUCTO
        lic.mensaje = (
            f"Esta licencia es de «{lic.producto}» y este software es «{PRODUCTO}»."
        )
        return lic

    if lic.equipo != huella:
        lic.estado = Estado.OTRO_EQUIPO
        lic.mensaje = MENSAJES[Estado.OTRO_EQUIPO]
        return lic

    ahora = _ahora()

    inicio = fecha("nbf")
    if inicio is not None and ahora < inicio:
        lic.estado = Estado.AUN_NO_VIGENTE
        lic.mensaje = f"La licencia entra en vigencia el {inicio:%d/%m/%Y}."
        return lic

    if lic.vence is None:
        lic.estado = Estado.INVALIDA
        return lic

    if ahora < lic.vence:
        lic.estado = Estado.ACTIVA
        lic.mensaje = MENSAJES[Estado.ACTIVA]
    elif ahora < lic.vence + timedelta(days=lic.gracia_dias):
        lic.estado = Estado.GRACIA
        quedan = lic.dias_de_gracia_restantes
        lic.mensaje = (
            f"La licencia venció el {lic.vence:%d/%m/%Y}. "
            f"Quedan {quedan} día(s) antes de que el sistema se bloquee."
        )
    else:
        lic.estado = Estado.EXPIRADA
        lic.mensaje = f"La licencia expiró el {lic.vence:%d/%m/%Y}."

    return lic


def leer_licencia() -> Licencia:
    """Lee el archivo de licencia del disco y lo evalúa. Sin caché."""
    if not settings.LICENSE_REQUIRED and not ruta_licencia().exists():
        # Equipo de trabajo: sin licencia y sin exigirla. Se avisa en el
        # log para que nadie confunda esto con una instalación de cliente.
        return _sin_licencia(Estado.DESARROLLO)

    try:
        token = ruta_licencia().read_text(encoding="utf-8").strip()
    except OSError:
        return _sin_licencia(Estado.SIN_LICENCIA)

    if not token:
        return _sin_licencia(Estado.SIN_LICENCIA)

    if not _revisar_reloj():
        return _sin_licencia(Estado.RELOJ_ALTERADO)

    return verificar_token(token)


# ── Caché ────────────────────────────────────────────────────
#
# El estado se consulta en cada petición protegida. Verificar una firma
# Ed25519 es barato, pero leer el archivo y el estado del reloj en cada
# llamada no lo es, y durante una transmisión las peticiones llegan
# seguidas. Se guarda un instante, lo bastante corto como para que el
# paso de ACTIVA a GRACIA o a EXPIRADA se note en el mismo minuto.

_cache: Optional[Licencia] = None
_cache_hasta: float = 0.0


def estado_licencia(refrescar: bool = False) -> Licencia:
    """El estado actual de la licencia, con caché de pocos segundos."""
    global _cache, _cache_hasta

    import time

    if refrescar or _cache is None or time.monotonic() >= _cache_hasta:
        _cache = leer_licencia()
        _cache_hasta = time.monotonic() + settings.LICENSE_CACHE_SECONDS

    return _cache


def limpiar_cache() -> None:
    """Olvida el estado guardado. Se llama al instalar una licencia nueva."""
    global _cache, _cache_hasta
    _cache = None
    _cache_hasta = 0.0


def guardar_licencia(token: str) -> Licencia:
    """Escribe el token en disco tras comprobar que sirve en este equipo.

    Se valida ANTES de escribir. Guardar primero y validar después dejaría
    una licencia inservible en el disco de un cliente que escribió mal la
    clave, y el siguiente arranque lo recibiría bloqueado en vez de con la
    pantalla de activación.
    """
    lic = verificar_token(token)

    if lic.estado not in (Estado.ACTIVA, Estado.GRACIA):
        return lic

    archivo = ruta_licencia()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(token, encoding="utf-8")

    limpiar_cache()
    logger.info(
        "Licencia instalada: %s (%s), vence %s",
        lic.cliente, lic.correo, lic.vence,
    )
    return lic


# ── Guarda ───────────────────────────────────────────────────

async def licencia_vigente() -> Licencia:
    """Dependencia que exige licencia para operar.

    Se pone sobre lo que saca gráficos al aire, que es lo que de verdad se
    está vendiendo. Deliberadamente NO se pone sobre el login ni sobre la
    consulta de la propia licencia: un cliente con la licencia vencida
    tiene que poder entrar al panel para ver qué pasa y activar la
    renovación. Bloquearle también la puerta lo dejaría sin forma de
    arreglarlo desde el propio software.

    Devuelve 402 (Payment Required) y no 403. Es el código que existe
    justo para esto, y le permite al frontend distinguir «tu usuario no
    tiene permiso» de «hay que renovar» sin mirar el texto del mensaje.
    """
    from fastapi import HTTPException, status

    estado = estado_licencia()

    if not estado.opera:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=estado.mensaje or MENSAJES.get(estado.estado, "Licencia no válida."),
        )

    return estado

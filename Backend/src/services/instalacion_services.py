"""El asistente de instalación.

Resuelve un huevo-y-la-gallina: para configurar el sistema hay que entrar,
pero el primer usuario todavía no existe, así que no hay con qué entrar.
Por eso las rutas del asistente son las únicas del backend que funcionan
sin sesión.

Eso abre un riesgo que antes no existía. El backend ahora atiende por toda
la red local, de modo que cualquiera conectado al mismo wifi podría llegar
al asistente antes que el técnico y nombrarse dueño del sistema.

La defensa es un token de un solo uso que el instalador escribe en un
archivo del disco al terminar de instalar. Para empezar el asistente hay
que presentarlo, y solo puede leerlo quien tenga acceso a la máquina, que
es exactamente quien acaba de instalar. Es el mismo mecanismo con el que
Jenkins protege su primer arranque.

Cuando la instalación se completa, el token se borra y las rutas del
asistente se cierran para siempre: a partir de ahí todo pasa por Ajustes,
con sesión y con rol.
"""

import logging
import secrets
from pathlib import Path
from typing import Optional

from config import ruta_del_backend, settings
from src.models.instalacion_model import PASOS, Instalacion
from src.models.users_model import User

logger = logging.getLogger(__name__)


def ruta_token() -> Path:
    return ruta_del_backend(settings.SETUP_TOKEN_FILE)


# ── Token de instalación ─────────────────────────────────────

def crear_token() -> str:
    """Genera el token y lo deja en disco. Lo llama el instalador.

    Se devuelve además del archivo para que el instalador pueda abrir el
    navegador ya con él puesto y el técnico no tenga que copiarlo a mano.
    """
    token = secrets.token_urlsafe(24)
    archivo = ruta_token()

    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(token, encoding="utf-8")

    try:
        # En Linux limita la lectura al dueño. En Windows no hace nada,
        # pero ahí el archivo ya está bajo una carpeta de programa.
        archivo.chmod(0o600)
    except OSError:
        pass

    return token


def token_valido(candidato: Optional[str]) -> bool:
    """Compara en tiempo constante.

    Con una comparación normal, el tiempo que tarda en fallar delata
    cuántos caracteres iniciales acertó, y eso permite adivinarlo carácter
    a carácter. Es barato defenderse y caro no hacerlo.
    """
    if not candidato:
        return False

    try:
        guardado = ruta_token().read_text(encoding="utf-8").strip()
    except OSError:
        return False

    return bool(guardado) and secrets.compare_digest(guardado, candidato)


def borrar_token() -> None:
    """Al terminar. El asistente no se vuelve a abrir."""
    try:
        ruta_token().unlink()
    except OSError:
        pass


# ── Estado ───────────────────────────────────────────────────

async def obtener() -> Instalacion:
    """El documento de instalación, creándolo la primera vez."""
    doc = await Instalacion.find_one({"clave": "instalacion"})

    if doc is None:
        doc = Instalacion()
        await doc.insert()

    return doc


async def hay_dueno() -> bool:
    """¿Existe ya alguien que administre el sistema?

    Es la otra mitad de la comprobación: una base con dueño pero sin
    documento de instalación es una instalación vieja, anterior al
    asistente, y no debe volver a pedirlo.
    """
    return await User.find_one({"role": "owner"}) is not None


async def esta_configurado() -> bool:
    """¿El sistema está listo para usarse?

    Es la pregunta que responde el frontend al arrancar para decidir entre
    el asistente y el login. NO es la que decide si el asistente sigue
    abierto: para eso está `asistente_cerrado`.
    """
    doc = await Instalacion.find_one({"clave": "instalacion"})

    if doc is not None and doc.completada:
        return True

    # Instalación anterior al asistente: si ya hay dueño, está configurada.
    return await hay_dueno()


async def asistente_cerrado() -> bool:
    """¿Se acabó el asistente para siempre?

    Solo lo cierra haberlo completado, y no que existan cuentas. Antes se
    usaba `esta_configurado`, y eso lo cerraba en cuanto se creaba el
    dueño —o sea, justo después del paso de las cuentas—: quien cerrara el
    navegador ahí se quedaba con la instalación a medias y sin forma de
    terminarla ni de volver a empezarla.

    La puerta la sigue guardando el token, que es lo que de verdad impide
    que alguien de la red local se cuele: se borra al completar, así que
    una instalación terminada no se puede reabrir aunque este método
    dijera que no.
    """
    doc = await Instalacion.find_one({"clave": "instalacion"})

    if doc is not None:
        return doc.completada

    # Sin documento pero con dueño: instalación anterior al asistente, que
    # nunca lo tuvo. No hay nada que retomar.
    return await hay_dueno()


async def estado() -> dict:
    """Lo que necesita saber el frontend para decidir qué enseñar."""
    doc = await Instalacion.find_one({"clave": "instalacion"})
    configurado = await esta_configurado()
    cerrado = await asistente_cerrado()

    return {
        "configurado": configurado,
        # Solo cuenta si además queda token: sin él no se puede empezar.
        # Va contra `cerrado` y no contra `configurado` para que una
        # instalación interrumpida tras crear las cuentas se pueda retomar.
        "asistente_disponible": not cerrado and ruta_token().is_file(),
        "paso": doc.paso if doc else PASOS[0],
        "pasos": PASOS,
        "organizacion": doc.organizacion if doc else "",
        "version": settings.APP_VERSION,
    }


async def guardar_paso(paso: str, datos: dict) -> Instalacion:
    """Guarda lo de un paso y avanza al siguiente.

    Se guarda paso a paso y no todo al final a propósito: la instalación
    se hace en un autódromo, con prisa, y cerrar el navegador sin querer
    no puede obligar a repetirlo todo.
    """
    doc = await obtener()

    for campo, valor in datos.items():
        if hasattr(doc, campo) and valor is not None:
            setattr(doc, campo, valor)

    if paso in PASOS:
        siguiente = PASOS.index(paso) + 1
        doc.paso = PASOS[min(siguiente, len(PASOS) - 1)]

    await doc.save()
    return doc


async def completar() -> Instalacion:
    """Cierra el asistente. No hay vuelta atrás."""
    from src.models.instalacion_model import ahora

    doc = await obtener()
    doc.completada = True
    doc.completada_en = ahora()
    doc.paso = "listo"
    await doc.save()

    borrar_token()
    logger.info("Instalación completada para «%s»", doc.organizacion)

    return doc

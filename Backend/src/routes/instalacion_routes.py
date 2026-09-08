"""Rutas del asistente de instalación.

Son las únicas del backend que funcionan sin sesión, porque cuando se usan
todavía no existe ningún usuario. A cambio exigen el token que el
instalador dejó en el disco, y dejan de existir en cuanto la instalación
se completa.

Solo `/estado` va sin token: el frontend la consulta al arrancar para
saber si tiene que enseñar el asistente o el login, y esa respuesta no
revela nada que no se vea igual en la pantalla de entrada.
"""

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from typing import Optional

from src.schemas.instalacion_schemas import (
    Clima, DatosUsuarios, Organizacion, RutaTiming, TextoUbicacion,
)
from src.services import instalacion_services as inst
from src.services.auth_services import hashear
from src.models.users_model import User

setup = APIRouter()


async def permitir(x_setup_token: Optional[str] = Header(None)) -> None:
    """Deja pasar solo mientras la instalación esté abierta y con token.

    Se comprueban las dos cosas por separado a propósito. Que la
    instalación esté sin completar no basta: sin token, cualquiera en la
    red local podría configurar el sistema. Y tener el token tampoco
    basta una vez terminada: el asistente no se reabre.

    Se pregunta por `asistente_cerrado` y no por `esta_configurado`: lo
    segundo pasa a ser cierto en cuanto existe el dueño, y eso cerraba el
    asistente en mitad de la instalación, justo tras crear las cuentas.
    """
    if await inst.asistente_cerrado():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El sistema ya está configurado. Los cambios se hacen desde Ajustes.",
        )

    if not inst.token_valido(x_setup_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de instalación inválido o ausente.",
        )


PROTEGIDO = [Depends(permitir)]


# ── Abierta ──────────────────────────────────────────────────

@setup.get("/estado", tags=["Setup"])
async def estado():
    """¿Hay que instalar o hay que entrar? La consulta el frontend al abrir."""
    return await inst.estado()


# ── Con token ────────────────────────────────────────────────

@setup.get("/red", tags=["Setup"], dependencies=PROTEGIDO)
async def red():
    """Direcciones por las que se llega a este equipo.

    Se enseña en la primera pantalla para que el técnico sepa qué escribir
    en el iPad antes de seguir: el backend atiende en 0.0.0.0, que no es
    algo que nadie pueda teclear.
    """
    from src.services.red_services import direcciones
    return direcciones()


@setup.get("/licencia", tags=["Setup"], dependencies=PROTEGIDO)
async def licencia():
    """Estado de la licencia de este equipo, para enseñarlo al empezar."""
    from src.services.fingerprint_services import huella_equipo
    from src.services import license_services as lic

    estado_lic = lic.estado_licencia(refrescar=True)
    return {**estado_lic.resumen(), "huella": huella_equipo()}


@setup.post("/organizacion", tags=["Setup"], dependencies=PROTEGIDO)
async def organizacion(datos: Organizacion):
    """Quién es el cliente.

    Nada de esto viene con un valor de fábrica: el producto no sale con el
    nombre de ningún autódromo puesto.
    """
    doc = await inst.guardar_paso("organizacion", datos.model_dump())
    return {"ok": True, "paso": doc.paso}


@setup.post("/logo", tags=["Setup"], dependencies=PROTEGIDO)
async def logo(archivo: UploadFile = File(...)):
    """El logo del cliente, que es lo que sale al aire en las plantillas."""
    from src.services.settings_services import guardar_logo_cliente, url_logo_cliente

    contenido = await archivo.read()

    # 4 MB de sobra para un logo. El límite está para que un archivo
    # enorme no se quede en memoria ni llene el disco del servidor.
    if len(contenido) > 4 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El logo no puede pasar de 4 MB.",
        )

    try:
        guardar_logo_cliente(contenido, archivo.filename or "logo.png")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"ok": True, "url": url_logo_cliente()}


@setup.post("/usuarios", tags=["Setup"], dependencies=PROTEGIDO)
async def usuarios(datos: DatosUsuarios):
    """Crea las tres cuentas del sistema, en una sola operación.

    No hay usuario de fábrica ni contraseña por defecto: se establecen
    aquí, en esta instalación. Una clave conocida que el cliente nunca
    cambia es la puerta abierta más común que existe.

    Se insertan las tres juntas y, si una falla, se deshacen las que ya
    entraron. Quedarse a medias dejaría el sistema con dueño pero sin
    operadores y el asistente ya cerrado para ese paso, que es la peor
    forma de fallar: parece que funcionó.
    """
    if await inst.hay_dueno():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario dueño en este sistema.",
        )

    cuentas = [
        (datos.owner, "owner"),
        (datos.admin, "admin"),
        (datos.standard, "standard"),
    ]

    creados = []
    try:
        for cuenta, rol in cuentas:
            usuario = User(
                username=cuenta.username,
                password=hashear(cuenta.password),
                role=rol,
            )
            await usuario.insert()
            creados.append(usuario)
    except Exception as e:
        for usuario in creados:
            try:
                await usuario.delete()
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudieron crear las cuentas: {e}",
        )

    await inst.guardar_paso("usuarios", {})
    return {
        "ok": True,
        "usuarios": [{"username": u.username, "role": u.role} for u in creados],
    }


@setup.post("/verificar-ruta", tags=["Setup"], dependencies=PROTEGIDO)
async def verificar_ruta(datos: RutaTiming):
    """Comprueba una ruta de current.xml sin guardarla todavía.

    Es lo que hace utilizable este paso: el técnico prueba, ve el
    resultado y corrige, en vez de guardar a ciegas y descubrir en la
    primera carrera que la ruta estaba mal.
    """
    from src.services.settings_services import revisar_ruta
    return revisar_ruta(datos.ruta)


@setup.post("/cronometraje", tags=["Setup"], dependencies=PROTEGIDO)
async def cronometraje(datos: RutaTiming):
    from src.services.settings_services import guardar_ruta_timing

    guardada = await guardar_ruta_timing(datos.ruta)
    await inst.guardar_paso("cronometraje", {})
    return {"ok": True, "ruta": guardada}


@setup.post("/probar-casparcg", tags=["Setup"], dependencies=PROTEGIDO)
async def probar_casparcg():
    """¿Contesta el servidor de gráficos?

    Se pregunta por su versión, que es el comando más inofensivo de AMCP:
    no toca nada de lo que pueda estar al aire.
    """
    from src.services.casparcg_client import CasparCGUnavailable, casparcg

    try:
        version = await casparcg.enviar("VERSION")
        return {"ok": True, "version": version}
    except CasparCGUnavailable as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@setup.post("/casparcg", tags=["Setup"], dependencies=PROTEGIDO)
async def guardar_casparcg():
    await inst.guardar_paso("casparcg", {})
    return {"ok": True}


@setup.get("/buscar-ubicacion", tags=["Setup"], dependencies=PROTEGIDO)
async def buscar_ubicacion(q: str, idioma: str = "es"):
    """Busca un lugar por su nombre.

    Usa el geocodificador de Open-Meteo, el mismo servicio que ya da el
    clima: sin clave de API y sin coste. Google Maps habría obligado a
    facturar una clave y a repartirla con cada instalación.
    """
    from src.services.ubicacion_services import buscar

    resultados = buscar(q, idioma=idioma)
    return {
        "resultados": resultados,
        # Un geocodificador encuentra ciudades, no circuitos. Que la
        # interfaz lo pueda decir evita que alguien crea que el sistema
        # falla cuando el nombre de su pista no aparece.
        "sugerencia": (
            "Si el circuito no aparece, busca la ciudad más cercana o pega el "
            "enlace de Google Maps. Para el clima, unos kilómetros no cambian nada."
            if not resultados else ""
        ),
    }


@setup.post("/interpretar-ubicacion", tags=["Setup"], dependencies=PROTEGIDO)
async def interpretar_ubicacion(datos: TextoUbicacion):
    """Saca las coordenadas de un enlace de mapa o de un texto pegado.

    Acepta un enlace de Google Maps —incluidos los cortos que salen al
    compartir desde el móvil—, coordenadas decimales y grados con minutos.
    """
    from src.services.ubicacion_services import interpretar

    return interpretar(datos.texto)


@setup.post("/clima", tags=["Setup"], dependencies=PROTEGIDO)
async def clima(datos: Clima):
    """Coordenadas del circuito.

    Estaban escritas en el código, apuntando a un cliente concreto. Aquí
    las pone cada autódromo, que es lo que permite venderlo en cualquier
    parte.
    """
    doc = await inst.guardar_paso("clima", datos.model_dump())
    return {"ok": True, "paso": doc.paso}


@setup.post("/completar", tags=["Setup"], dependencies=PROTEGIDO)
async def completar():
    """Cierra el asistente y borra el token. No se puede volver a abrir."""
    if not await inst.hay_dueno():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta crear el usuario dueño antes de terminar.",
        )

    doc = await inst.completar()
    return {"ok": True, "organizacion": doc.organizacion}

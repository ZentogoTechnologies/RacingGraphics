from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.services.auth_services import puede_escribir
from src.services.settings_services import (
    IDIOMAS, TIPOGRAFIAS, fuente_actual, guardar_fuente,
    guardar_idioma, idioma_actual, textos_de,
    guardar_logo_cliente, guardar_ruta_timing, logo_cliente_actual,
    explorar, marcar_logo_cliente, restaurar_logo_fabrica, revisar_ruta,
    ruta_timing,
    url_logo_cliente, xml_detectados,
)
from src.services.tracks_services import ruta_plantilla, trazados_service

ajustes = APIRouter()


class RutaTiming(BaseModel):
    # Vacío o None vuelve a la ruta del .env.
    timing_xml_path: Optional[str] = None


@ajustes.get("/", tags=["Settings"])
async def leer_ajustes():
    """
    Ajustes en vigor y los XML que el servidor alcanza
    """
    actual = ruta_timing()
    return {
        "timing_xml_path": actual,
        "estado": revisar_ruta(actual),
        "detectados": xml_detectados(),
        "client_logo": await logo_cliente_actual(),
        "client_logo_url": url_logo_cliente(),
    }


@ajustes.get("/timing/explorar", tags=["Settings"], dependencies=[Depends(puede_escribir)])
async def explorar_carpeta(ruta: Optional[str] = None):
    """
    Carpetas y XML del servidor, para llegar al current.xml navegando

    Sin `ruta` devuelve las unidades de disco. La ruta es la del servidor
    donde corre el backend, que es el que lee el archivo: el selector de
    archivos del navegador nunca entrega una ruta en disco, y es la ruta lo
    que hay que guardar.
    """
    return explorar(ruta)


@ajustes.post("/timing/probar", tags=["Settings"], dependencies=[Depends(puede_escribir)])
async def probar(datos: RutaTiming):
    """
    Comprueba una ruta sin aplicarla. Dice qué evento y tanda trae
    """
    return revisar_ruta(datos.timing_xml_path or "")


@ajustes.put("/timing", tags=["Settings"], dependencies=[Depends(puede_escribir)])
async def cambiar_ruta(datos: RutaTiming):
    """
    Cambia la ruta del current.xml. Se aplica de inmediato, sin reiniciar
    """
    aplicada = await guardar_ruta_timing(datos.timing_xml_path)
    actual = ruta_timing()
    return {
        "timing_xml_path": actual,
        "usando_env": aplicada is None,
        "estado": revisar_ruta(actual),
    }


# ======================================================================
#  TRAZADOS
#
#  La imagen de la pista no es un ajuste suelto sino una lista: el mismo
#  recinto se corre de varias formas —pista corta, pista larga, cuarto de
#  milla— y cada una tiene su dibujo. Se marca uno como activo y es el que
#  sale en el gráfico de Circuito.
# ======================================================================


class TrazadoIn(BaseModel):
    name: str
    variante: Optional[str] = None
    discipline: str = "circuito"
    length_km: Optional[float] = None


class TrazadoPatch(BaseModel):
    name: Optional[str] = None
    variante: Optional[str] = None
    discipline: Optional[str] = None
    length_km: Optional[float] = None


class RutaImagen(BaseModel):
    ruta: str


def _salida(doc) -> dict:
    """Se añade la ruta que entiende la plantilla, que es lo que consume
    la vista previa del navegador y el propio gráfico."""
    return {
        **doc.model_dump(exclude={"id"}),
        "image_url": ruta_plantilla(doc.image),
    }


@ajustes.get("/trazados", tags=["Settings"])
async def listar_trazados(discipline: Optional[str] = None):
    """
    Trazados dados de alta, con cuál está activo
    """
    docs = await trazados_service.listar(discipline)
    return {"items": [_salida(d) for d in docs], "total": len(docs)}


@ajustes.post("/trazados", tags=["Settings"], status_code=201,
              dependencies=[Depends(puede_escribir)])
async def crear_trazado(datos: TrazadoIn):
    """
    Da de alta un trazado. La imagen se sube después, por su id
    """
    doc = await trazados_service.crear(datos.model_dump())
    return _salida(doc)


@ajustes.put("/trazados/{trazado_id}", tags=["Settings"],
             dependencies=[Depends(puede_escribir)])
async def editar_trazado(trazado_id: int, datos: TrazadoPatch):
    """
    Cambia el nombre, la variante, la disciplina o la longitud
    """
    doc = await trazados_service.actualizar(
        trazado_id, datos.model_dump(exclude_unset=True))
    return _salida(doc)


@ajustes.put("/trazados/{trazado_id}/activar", tags=["Settings"],
             dependencies=[Depends(puede_escribir)])
async def activar_trazado(trazado_id: int):
    """
    Marca este trazado como el que sale en el gráfico de Circuito
    """
    doc = await trazados_service.activar(trazado_id)
    return _salida(doc)


@ajustes.post("/trazados/{trazado_id}/imagen", tags=["Settings"],
              dependencies=[Depends(puede_escribir)])
async def subir_imagen(trazado_id: int, archivo: UploadFile = File(...)):
    """
    Sube la imagen del trazado desde el navegador
    """
    contenido = await archivo.read()
    doc = await trazados_service.subir_imagen(
        trazado_id, archivo.filename or "", contenido)
    return _salida(doc)


@ajustes.put("/trazados/{trazado_id}/imagen", tags=["Settings"],
             dependencies=[Depends(puede_escribir)])
async def imagen_por_ruta(trazado_id: int, datos: RutaImagen):
    """
    Toma la imagen de una ruta del servidor y la copia a la plantilla
    """
    doc = await trazados_service.copiar_imagen(trazado_id, datos.ruta)
    return _salida(doc)


@ajustes.delete("/trazados/{trazado_id}", tags=["Settings"],
                dependencies=[Depends(puede_escribir)])
async def borrar_trazado(trazado_id: int):
    """
    Borra el trazado y su imagen, si no la usa ningún otro
    """
    return await trazados_service.borrar(trazado_id)


# ======================================================================
#  LOGO DEL CLIENTE
#
#  El del autódromo que usa el software. Las veintidós plantillas apuntan
#  al mismo archivo, así que cambiarlo aquí lo cambia en todos los
#  gráficos a la vez, sin tocar ninguna plantilla.
# ======================================================================


@ajustes.post("/logo", tags=["Settings"], dependencies=[Depends(puede_escribir)])
async def subir_logo_cliente(archivo: UploadFile = File(...)):
    """
    Sube el logo del autódromo. Sale en todos los gráficos
    """
    contenido = await archivo.read()

    guardar_logo_cliente(contenido, archivo.filename or "")
    await marcar_logo_cliente(archivo.filename or "logo")

    return {"ok": True, "client_logo_url": url_logo_cliente()}


@ajustes.delete("/logo", tags=["Settings"], dependencies=[Depends(puede_escribir)])
async def quitar_logo_cliente():
    """
    Vuelve al logo que trae el software
    """
    restaurar_logo_fabrica()
    await marcar_logo_cliente(None)

    return {"ok": True, "client_logo_url": url_logo_cliente()}


# ── Tipografía de los gráficos ────────────────────────────────────

@ajustes.get("/fuentes", tags=["Settings"])
async def listar_fuentes():
    """Las tipografías empaquetadas y cuál está puesta.

    Se manda el archivo de cada una para que el panel pueda enseñar cómo
    es la letra antes de elegirla: un nombre suelto no dice nada.
    """
    return {
        "actual": await fuente_actual(),
        "fuentes": [
            {**t, "url": f"/media/fonts/{t['nombre'].replace(' ', '')}-700.woff2"}
            for t in TIPOGRAFIAS
        ],
    }


@ajustes.put("/fuentes/{tipografia_id}", dependencies=[Depends(puede_escribir)], tags=["Settings"])
async def elegir_fuente(tipografia_id: str):
    """Cambia la letra de los veintidós gráficos de una vez."""
    try:
        elegida = await guardar_fuente(tipografia_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"ok": True, "actual": elegida}


# ── Idioma ────────────────────────────────────────────────────────

@ajustes.get("/idiomas", tags=["Settings"])
async def listar_idiomas():
    """Los idiomas y cuál está puesto."""
    return {"actual": await idioma_actual(), "idiomas": IDIOMAS}


@ajustes.get("/idiomas/{idioma}/textos", tags=["Settings"])
async def textos_del_idioma(idioma: str):
    """Las traducciones de la interfaz para ese idioma.

    El panel las pide al arrancar; los gráficos no pasan por aquí, que
    leen el archivo que el backend les deja escrito.
    """
    textos = textos_de(idioma)
    if not textos:
        raise HTTPException(status_code=404, detail=f"Sin traducción para {idioma}")
    return textos


@ajustes.put("/idiomas/{idioma}", dependencies=[Depends(puede_escribir)], tags=["Settings"])
async def elegir_idioma(idioma: str):
    """Cambia el idioma de la interfaz y del arte a la vez."""
    try:
        elegido = await guardar_idioma(idioma)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True, "actual": elegido}

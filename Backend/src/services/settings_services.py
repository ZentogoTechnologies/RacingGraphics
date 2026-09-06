"""Ajustes que se cambian sin reiniciar.

La ruta del current.xml se guarda en la base, pero `leer_xml` es síncrona
y se llama muchas veces por segundo desde las plantillas. Consultar Mongo
en cada lectura sería absurdo, así que el valor se mantiene en memoria y
se refresca al arrancar y cada vez que alguien lo cambia.
"""

import io
import json
import shutil
from pathlib import Path
from typing import Optional

from config import settings
from src.models.settings_model import Ajustes

# Valor vivo del proceso. None significa "usa el del .env".
_ruta_timing: Optional[str] = None

# Dónde se buscan XML para ofrecerlos en la lista. La carpeta public es la
# que ya se usa para material del proyecto.
CARPETAS_CANDIDATAS = [
    Path(__file__).resolve().parents[1] / "public",
]

# ── Logo del cliente ──────────────────────────────────────────────
#
# Todas las plantillas apuntan a este archivo, así que cambiarlo cambia el
# logo en los veintidós gráficos de una vez. Se escribe siempre en el mismo
# sitio y en PNG, sea cual sea el formato que suban: así la ruta de las
# plantillas es fija y no hay que tocarlas nunca más.

RAIZ = Path(__file__).resolve().parents[3]

LOGO_CLIENTE = RAIZ / "Casparcg" / "template" / "img" / "logo-cliente.png"

# El de fábrica, que no se toca: es a donde se vuelve al quitar el suyo.
LOGO_FABRICA = RAIZ / "Casparcg" / "template" / "img" / "logoap.png"


def url_logo_cliente() -> str:
    """Con qué versión pedirlo, para que el navegador no lo cachee."""
    if not LOGO_CLIENTE.is_file():
        return ""
    return f"/media/logo/logo-cliente.png?v={int(LOGO_CLIENTE.stat().st_mtime)}"


def guardar_logo_cliente(contenido: bytes, nombre: str) -> None:
    """Escribe el logo subido en el sitio que miran las plantillas.

    Se convierte a PNG con transparencia porque los gráficos lo ponen
    sobre paneles oscuros: un JPG llegaría con su fondo blanco recortado
    en un rectángulo y se vería como un parche.
    """
    from fastapi import HTTPException
    from PIL import Image, UnidentifiedImageError

    if not contenido:
        raise HTTPException(400, "El archivo llegó vacío")

    try:
        imagen = Image.open(io.BytesIO(contenido))
        imagen.load()
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(400, f"'{nombre}' no se pudo leer como imagen ({e})")

    LOGO_CLIENTE.parent.mkdir(parents=True, exist_ok=True)
    imagen.convert("RGBA").save(LOGO_CLIENTE, format="PNG")


def restaurar_logo_fabrica() -> None:
    """Vuelve al logo que trae el software."""
    from fastapi import HTTPException

    if not LOGO_FABRICA.is_file():
        raise HTTPException(500, "No encuentro el logo de fábrica para restaurarlo")

    shutil.copyfile(LOGO_FABRICA, LOGO_CLIENTE)


def ruta_timing() -> str:
    """La ruta que debe leerse ahora mismo."""
    return _ruta_timing or settings.TIMING_XML_PATH


async def cargar_ajustes():
    """Trae lo guardado a memoria. Se llama al arrancar el backend."""
    global _ruta_timing

    doc = await Ajustes.find_one({})
    _ruta_timing = doc.timing_xml_path if doc else None
    return _ruta_timing


async def marcar_logo_cliente(nombre: Optional[str]) -> None:
    """Deja constancia de si hay un logo propio puesto."""
    doc = await Ajustes.find_one({})
    if doc is None:
        doc = Ajustes(client_logo=nombre)
        await doc.insert()
    else:
        doc.client_logo = nombre
        await doc.save()


async def logo_cliente_actual() -> Optional[str]:
    doc = await Ajustes.find_one({})
    return doc.client_logo if doc else None


async def guardar_ruta_timing(ruta: Optional[str]) -> Optional[str]:
    """Cambia la ruta y la deja aplicada de inmediato."""
    global _ruta_timing

    limpia = (ruta or "").strip() or None

    doc = await Ajustes.find_one({})
    if doc is None:
        doc = Ajustes(timing_xml_path=limpia)
        await doc.insert()
    else:
        doc.timing_xml_path = limpia
        await doc.save()

    _ruta_timing = limpia
    return _ruta_timing


def revisar_ruta(ruta: str) -> dict:
    """Comprueba si esa ruta sirve, sin aplicarla.

    Se responde con detalle en vez de un sí o un no: el caso normal de
    fallo es una unidad de red caída, y saber si el problema es la unidad,
    la carpeta o el archivo ahorra media hora en pista.
    """
    if not ruta or not ruta.strip():
        return {"ok": False, "detalle": "La ruta está vacía"}

    archivo = Path(ruta.strip())

    if not archivo.exists():
        padre = archivo.parent
        if not padre.exists():
            return {
                "ok": False,
                "detalle": f"No existe la carpeta {padre}. ¿Está conectada la unidad de red?",
            }
        return {"ok": False, "detalle": f"La carpeta existe pero no está el archivo {archivo.name}"}

    if not archivo.is_file():
        return {"ok": False, "detalle": "Esa ruta es una carpeta, no un archivo"}

    # Se intenta leer de verdad: un archivo que existe pero está bloqueado
    # por MyLaps mientras escribe también falla, y conviene verlo aquí.
    try:
        from src.services.timing_services import leer_xml

        datos = leer_xml(str(archivo))
    except Exception as e:
        return {"ok": False, "detalle": f"No se pudo leer: {type(e).__name__}: {str(e)[:100]}"}

    etiquetas = datos.get("labels", {})
    return {
        "ok": True,
        "detalle": "Archivo leído correctamente",
        "evento": etiquetas.get("eventname"),
        "tanda": etiquetas.get("runname"),
        "grupo": etiquetas.get("groupname"),
        "filas": len(datos.get("filas", [])),
    }


def xml_detectados() -> list[dict]:
    """XML que el servidor alcanza, para ofrecerlos en una lista.

    Incluye siempre la ruta configurada aunque no exista: si la unidad de
    red está caída hay que poder verla en la lista y saber que sigue
    siendo la elegida.
    """
    vistos = []
    rutas = set()

    for carpeta in CARPETAS_CANDIDATAS:
        if not carpeta.exists():
            continue
        for archivo in sorted(carpeta.glob("*.xml")):
            rutas.add(str(archivo))
            vistos.append({
                "ruta": str(archivo),
                "nombre": archivo.name,
                "existe": True,
                "origen": "proyecto",
            })

    actual = ruta_timing()
    if actual not in rutas:
        vistos.insert(0, {
            "ruta": actual,
            "nombre": Path(actual).name,
            "existe": Path(actual).exists(),
            "origen": "configurada",
        })

    return vistos


# ── Tipografía de los gráficos ────────────────────────────────────
#
# Las fuentes van empaquetadas en Casparcg/template/fonts y no instaladas
# en Windows: el arte tiene que verse igual en cualquier máquina donde se
# instale el software, sin que nadie tenga que instalar tipografías a mano
# antes de una carrera.
#
# Elegir una reescribe tipografia_activa.css, que es lo único que leen las
# plantillas. No se toca el CSS de las caras, que es el pesado.

CSS_TIPOGRAFIA = RAIZ / "Casparcg" / "template" / "css" / "tipografia_activa.css"

# Donde viven los .woff2. Los sirve el backend en /media/fonts para que el
# panel pueda enseñar cada letra antes de elegirla.
CARPETA_FUENTES = RAIZ / "Casparcg" / "template" / "fonts"

# Las banderas de los paises. Viven junto a la plantilla porque es quien
# las pinta al aire —las lee por file://, sin pasar por el backend— y el
# panel las ve en /media/banderas. Un solo archivo por pais, no dos.
CARPETA_BANDERAS = RAIZ / "Casparcg" / "template" / "img" / "banderas"

# Los codigos que de verdad tienen bandera en disco. Se leen una vez al
# arrancar: son 255 archivos y preguntarselo al disco en cada alta de
# piloto seria pagar una lectura por tecleo.
PAISES_CON_BANDERA = frozenset(
    p.stem.lower() for p in CARPETA_BANDERAS.glob("*.svg")
)

# El respaldo no es decorativo: si la fuente no cargara, Segoe UI y Arial
# son lo único seguro en cualquier Windows.
RESPALDO = '"Segoe UI", Arial, sans-serif'

TIPOGRAFIAS = [
    {
        "id": "titillium",
        "nombre": "Titillium Web",
        "nota": "La que usa la Fórmula 1. Redonda y neutra; no es condensada, "
                "así que los apellidos largos encogen antes en el tótem.",
    },
    {
        "id": "barlow",
        "nombre": "Barlow Condensed",
        "nota": "Condensada de verdad: los apellidos largos caben sin encoger "
                "la letra. Cifras de ancho fijo para tiempos y posiciones.",
    },
    {
        "id": "saira",
        "nombre": "Saira Condensed",
        "nota": "Tan estrecha como Barlow pero con más carácter, de aire "
                "técnico y deportivo.",
    },
    {
        "id": "chakra",
        "nombre": "Chakra Petch",
        "nota": "La más de automovilismo, con cortes angulados. Muy buena en "
                "nombres y dorsales grandes; menos en textos largos.",
    },
    {
        "id": "archivo",
        "nombre": "Archivo",
        "nota": "La más segura. Pensada para leerse en tamaños pequeños y "
                "pantallas malas, que es el caso del tótem por televisión.",
    },
]

POR_ID = {t["id"]: t for t in TIPOGRAFIAS}


PLANTILLA_CSS = """@charset "UTF-8";

/* ==========================================================================
   LA TIPOGRAFIA ELEGIDA

   Lo reescribe el backend cada vez que se elige una fuente en
   Ajustes -> Generales. No se edita a mano: el cambio se perderia en
   cuanto alguien tocara el boton.
========================================================================== */

:root{{
    --fuente-graficos: "{familia}", {respaldo};
}}
"""


def _escribir_css(nombre: str) -> None:
    """Deja en el CSS la familia elegida, con su respaldo detrás."""
    CSS_TIPOGRAFIA.write_text(
        PLANTILLA_CSS.format(familia=nombre, respaldo=RESPALDO),
        encoding="utf-8",
    )


async def fuente_actual() -> str:
    """El id de la tipografía puesta; la primera de la lista si no hay."""
    ajustes = await Ajustes.find_one()
    elegida = ajustes.font_graficos if ajustes else None
    return elegida if elegida in POR_ID else TIPOGRAFIAS[0]["id"]


async def guardar_fuente(tipografia_id: str) -> str:
    """Guarda la elección y reescribe el CSS que leen las plantillas."""
    if tipografia_id not in POR_ID:
        raise ValueError(f"Tipografía desconocida: {tipografia_id}")

    _escribir_css(POR_ID[tipografia_id]["nombre"])

    ajustes = await Ajustes.find_one()
    if ajustes is None:
        ajustes = Ajustes()
    ajustes.font_graficos = tipografia_id
    await ajustes.save()

    return tipografia_id


# ── Idioma ────────────────────────────────────────────────────────
#
# Las traducciones del arte viven en Casparcg/template/i18n/*.json, que es
# lo que se edita. Pero CasparCG abre las plantillas con file://, donde
# fetch() de un JSON está bloqueado por CORS: la plantilla no puede leerlo
# por su cuenta. Así que al elegir idioma se vuelca el JSON en un .js, que
# sí se puede cargar con un <script src>. Mismo truco que con la
# tipografía, y por la misma razón.

CARPETA_TEXTOS = RAIZ / "Casparcg" / "template" / "i18n"

JS_IDIOMA = RAIZ / "Casparcg" / "template" / "js" / "idioma_activo.js"

# El ingles queda apagado a peticion del cliente. La traduccion esta hecha
# y se conserva entera —template/i18n/*.json y Frontend/src/i18n/en.json—:
# volver a encenderlo es poner "listo" en True, nada mas. Se deja listado y
# no se borra para que se vea que existe y no se rehaga desde cero.
IDIOMAS = [
    {"id": "es", "nombre": "Español", "listo": True},
    {"id": "en", "nombre": "English", "listo": False},
]

IDIOMAS_POR_ID = {i["id"]: i for i in IDIOMAS}

CABECERA_JS = """/* Lo reescribe el backend al cambiar el idioma en Ajustes. No se edita
   a mano: el cambio se perderia en cuanto alguien tocara el selector.
   Las traducciones se editan en template/i18n/*.json. */

"""


def textos_de(idioma: str) -> dict:
    """Las traducciones del arte para ese idioma."""
    archivo = CARPETA_TEXTOS / f"{idioma}.json"
    if not archivo.is_file():
        return {}
    return json.loads(archivo.read_text(encoding="utf-8"))


def _escribir_js(idioma: str) -> None:
    """Deja el idioma elegido donde las plantillas puedan cargarlo."""
    textos = json.dumps(textos_de(idioma), ensure_ascii=False, indent=4)
    JS_IDIOMA.write_text(
        CABECERA_JS + "window.TEXTOS = " + textos + ";" + chr(10),
        encoding="utf-8",
    )


async def idioma_actual() -> str:
    """El idioma puesto; español si no hay ninguno o el guardado ya no existe."""
    ajustes = await Ajustes.find_one()
    elegido = ajustes.idioma if ajustes else None
    listos = {i["id"] for i in IDIOMAS if i["listo"]}
    return elegido if elegido in listos else "es"


async def guardar_idioma(idioma: str) -> str:
    """Guarda el idioma y vuelca sus textos para las plantillas."""
    info = IDIOMAS_POR_ID.get(idioma)
    if info is None:
        raise ValueError(f"Idioma desconocido: {idioma}")
    if not info["listo"]:
        raise ValueError(f"El idioma {info['nombre']} está desactivado")

    _escribir_js(idioma)

    ajustes = await Ajustes.find_one()
    if ajustes is None:
        ajustes = Ajustes()
    ajustes.idioma = idioma
    await ajustes.save()

    return idioma

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pathlib import Path
from contextlib import asynccontextmanager
from pymongo import AsyncMongoClient
from beanie import init_beanie
from config import settings
from docs import tags_metadata

# Models
from src.models.categories_model import Category
from src.models.pilots_model import Pilot
from src.models.vehicles_model import Vehicle
from src.models.users_model import User
from src.models.events_model import Event
from src.models.settings_model import Ajustes
from src.models.tracks_model import Trazado

# Routes
from src.routes.categories_routes import categories
from src.routes.pilots_routes import pilots
from src.routes.vehicles_routes import vehicles
from src.routes.graphics_routes import graphics
from src.routes.timing_routes import timing
from src.routes.users_routes import users
from src.routes.login_routes import login
from src.routes.system_routes import system
from src.routes.events_routes import events
from src.routes.settings_routes import ajustes
from src.routes.weather_routes import weather
from src.routes.license_routes import license

# Auth
from src.services.auth_services import usuario_actual

# Licencia
from src.services.license_services import licencia_vigente

# CasparCG
from src.services.casparcg_client import casparcg

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncMongoClient(settings.MONGO_URI)
    await init_beanie(
        database=client[settings.DB_NAME],
        document_models=[Category, Pilot, Vehicle, User, Event, Ajustes, Trazado]
    )
    print("✅ Conectado a MongoDB")

    # Los ajustes que se cambian en caliente viven en la base; se traen a
    # memoria aquí para que leer_xml no consulte Mongo en cada lectura.
    from src.services.settings_services import cargar_ajustes

    ruta = await cargar_ajustes()
    if ruta:
        print(f"   current.xml: {ruta} (ajuste guardado)")

    yield
    await client.close()
    # La conexión con CasparCG se abre sola al primer comando; aquí solo
    # se cierra para no dejar el socket colgando al apagar el servidor.
    await casparcg.close()

app = FastAPI(
    title="Race Core Studio",
    description="Software de Gestión de Pilotos, Categorías, Vehículos, Eventos y Gráficos",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata
)

# El panel lo sirve este mismo backend, así que para la interfaz no hay
# cruce de origen y el navegador ni pregunta. Quien sí cruza es CasparCG:
# sus plantillas se cargan desde file://, cuyo origen es "null", y piden
# el cronometraje y las fotos por HTTP.
#
# allow_credentials va en falso, y es importante ahora que el backend
# atiende a toda la red local. La sesión viaja como token Bearer en la
# cabecera Authorization, no en una cookie, así que no hacen falta
# credenciales de origen cruzado. Dejarlo en verdadero junto a "*" es
# además una combinación que el estándar prohíbe: el navegador la
# rechaza, de modo que no estaba habilitando nada, solo aparentándolo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fotos de pilotos y logos de marcas. CasparCG los carga por HTTP desde
# aquí, así que el backend debe estar corriendo para que se vean al aire.
app.mount(
    "/public",
    StaticFiles(directory=Path(__file__).parent / "src" / "public"),
    name="public",
)

# Imágenes de los trazados. CasparCG las lee del disco por ruta relativa,
# pero la interfaz necesita verlas por HTTP para la vista previa, y una
# etiqueta <img> no puede mandar la cabecera del token. Son dibujos de
# pista, lo mismo que ya sale al aire, así que van abiertas igual que
# /public.
from src.services.tracks_services import CARPETA_IMAGENES

CARPETA_IMAGENES.mkdir(parents=True, exist_ok=True)

app.mount(
    "/media/circuits",
    StaticFiles(directory=CARPETA_IMAGENES),
    name="circuits",
)

# El logo del cliente vive dentro de la plantilla de CasparCG, que es
# quien lo pinta al aire. La interfaz lo sirve desde aquí para poder
# enseñarlo en Ajustes sin duplicar el archivo.
from src.services.settings_services import LOGO_CLIENTE

app.mount(
    "/media/logo",
    StaticFiles(directory=LOGO_CLIENTE.parent),
    name="logo",
)

# Las tipografías viven junto a las plantillas, que son quienes las pintan
# al aire. La interfaz las sirve desde aquí para poder enseñar en Ajustes
# cómo es cada letra antes de elegirla, sin duplicar los archivos.
from src.services.settings_services import CARPETA_FUENTES

app.mount(
    "/media/fonts",
    StaticFiles(directory=CARPETA_FUENTES),
    name="fonts",
)

# Las banderas de los paises. Mismo archivo que sale al aire: la plantilla
# lo lee del disco y el panel por HTTP, sin copiarlo dos veces. Abierto
# igual que /public: son banderas, no hay nada que proteger.
from src.services.settings_services import CARPETA_BANDERAS

app.mount(
    "/media/banderas",
    StaticFiles(directory=CARPETA_BANDERAS),
    name="banderas",
)

# Todo lo que toca la base o manda al aire exige un JWT válido. La
# dependencia se declara aquí y no dentro de cada router para que la
# política de acceso se lea de un vistazo en un solo lugar.
PROTEGIDO = [Depends(usuario_actual)]

app.include_router(login, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(users, prefix="/api/v1/users", tags=["Users"])

# Apagado del sistema. La guardia de rol va dentro del router.
app.include_router(system, prefix="/api/v1/system", tags=["System"])

# Licencia. La guardia de acceso va por ruta dentro del router: /salud
# es abierta porque la consultan el servicio de vigilancia y la pantalla
# de bloqueo, que corren fuera del panel y no tienen sesión.
app.include_router(license, prefix="/api/v1/license", tags=["License"])

app.include_router(categories, prefix="/api/v1/categories", tags=["Categories"], dependencies=PROTEGIDO)
app.include_router(pilots, prefix="/api/v1/pilots", tags=["Pilots"], dependencies=PROTEGIDO)
app.include_router(vehicles, prefix="/api/v1/vehicles", tags=["Vehicles"], dependencies=PROTEGIDO)
# Gráficos exige además licencia vigente. Va solo aquí y no en el resto
# de módulos a propósito: con la licencia vencida el cliente sigue
# entrando al panel y viendo sus datos, pero no saca nada al aire. Así
# conserva su información y puede renovar desde el propio software.
app.include_router(
    graphics,
    prefix="/api/v1/graphics",
    tags=["Graphics"],
    dependencies=PROTEGIDO + [Depends(licencia_vigente)],
)
app.include_router(events, prefix="/api/v1/events", tags=["Events"], dependencies=PROTEGIDO)
app.include_router(ajustes, prefix="/api/v1/settings", tags=["Settings"], dependencies=PROTEGIDO)
app.include_router(weather, prefix="/api/v1/weather", tags=["Weather"], dependencies=PROTEGIDO)

# Timing se protege por ruta, no en bloque: la única abierta es
# GET /timing/current, que es lo que consultan las plantillas de CasparCG
# desde file:// sin poder mandar cabeceras. La excepción se declara en
# timing_routes.py, al lado de las rutas. Lo mismo aplica a /public, que
# sirve las fotos con <img>, y un <img> tampoco manda Authorization.
app.include_router(timing, prefix="/api/v1/timing", tags=["Timing"])


# ======================================================================
#  EL FRONTEND, SERVIDO POR EL PROPIO BACKEND
#
#  Va al final a propósito: este montaje responde a todo lo que no haya
#  atendido ya una ruta del API, así que tiene que declararse el último.
#
#  Sirve para no depender de dos puertos. Con el frontend en 5173 y el
#  API en 8080 hay que decirle al navegador en qué host está el API, y esa
#  dirección cambia según desde dónde se entre: localhost aquí, otra IP en
#  la red local, otro nombre a través de un túnel. Sirviéndolo desde aquí
#  el navegador pide siempre a quien le dio la página.
# ======================================================================

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "Frontend" / "dist"


class FrontendSPA(StaticFiles):
    """Estáticos con vuelta a index.html.

    React Router maneja las rutas en el navegador, así que /pilotos no es
    un archivo. Sin esto, entrar directo a una dirección que no sea la
    raíz —o recargar la página— daría 404.
    """

    async def get_response(self, path: str, scope):
        try:
            respuesta = await super().get_response(path, scope)
        except StarletteHTTPException as e:
            # Starlette no devuelve un 404, lo lanza. Comprobar el código
            # de la respuesta no servía de nada: nunca llegaba a haberla.
            if e.status_code != 404:
                raise
            respuesta = await super().get_response("index.html", scope)
            path = "index.html"

        # El HTML no se cachea. index.html es el único archivo con nombre
        # fijo: los demás llevan el hash del contenido y pueden guardarse
        # para siempre. Sin esto el navegador se queda con el index viejo,
        # que apunta al bundle viejo, y la interfaz sigue mostrando la
        # versión anterior después de recompilar aunque el servidor ya
        # tenga la nueva.
        #
        # Se mira el tipo de contenido y no la ruta: para la raíz el path
        # que llega aquí no es "index.html" sino ".", y la comprobación
        # por nombre no se cumplía nunca.
        tipo = respuesta.headers.get("content-type", "")
        if tipo.startswith("text/html"):
            respuesta.headers["Cache-Control"] = "no-cache, must-revalidate"

        return respuesta


if FRONTEND_DIST.is_dir():
    app.mount("/", FrontendSPA(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    # No es un error: en desarrollo el frontend lo sirve Vite y esta
    # carpeta puede no existir hasta que alguien compile.
    print(f"Sin frontend compilado en {FRONTEND_DIST}; solo se sirve el API")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)

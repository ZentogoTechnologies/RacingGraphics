from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Carpeta del backend.
#
# Las rutas relativas de los ajustes se resuelven contra esto y NO contra
# el directorio actual. El instalador corre desde la raíz del repositorio
# y el backend desde Backend/, así que "licencia.lic" apuntaba a dos
# sitios distintos según quién la leyera: el instalador dejaba el token
# de instalación en la raíz y el backend lo buscaba en Backend/, no lo
# encontraba, y daba el asistente por no disponible.
BASE_DIR = Path(__file__).resolve().parent


def ruta_del_backend(valor: str) -> Path:
    """Una ruta de los ajustes, anclada a la carpeta del backend.

    Las absolutas se respetan tal cual: un cliente puede querer la
    licencia en otro disco.
    """
    ruta = Path(valor).expanduser()
    return ruta if ruta.is_absolute() else BASE_DIR / ruta

class Settings(BaseSettings):
    # Sin esto el archivo .env no se lee: los valores salian siempre
    # de los defaults de abajo o de variables de entorno sueltas.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "race-core-studio"

    # ── API ──────────────────────────────────────────────────
    # 0.0.0.0 significa "atiende por todas las interfaces de red", no una
    # dirección concreta. Es lo que convierte al equipo en servidor: la
    # máquina que tiene CasparCG se dedica solo a eso, y el panel se opera
    # desde el navegador de otro equipo, de un iPad o de la propia consola.
    # Con 127.0.0.1 el backend solo se dejaría alcanzar desde sí mismo.
    #
    # Para que otro dispositivo entre hace falta además abrir el puerto en
    # el Firewall de Windows; eso lo hace el instalador.
    API_HOST: str = "0.0.0.0"

    # El 8000 lo reserva el media-server de CasparCG (ver casparcg.config),
    # por eso el backend vive en el 8080.
    API_PORT: int = 8080

    # ── Archivos públicos ────────────────────────────────────
    # URL con la que CasparCG alcanza al backend para bajar las fotos
    # de los pilotos y los logos de las marcas. Tiene que ser absoluta:
    # la plantilla se carga desde file:// y no tiene contra qué resolver
    # una ruta relativa.
    # Se queda en 127.0.0.1 aunque el API atienda por todas las
    # interfaces: CasparCG corre en esta misma máquina, así que llega por
    # loopback. Poner aquí la IP de la red local ataría las plantillas a
    # una dirección que cambia sola cuando el router reparte otra.
    PUBLIC_BASE_URL: str = "http://127.0.0.1:8080"

    # ── Cronometraje (MyLaps) ────────────────────────────────
    # Archivo que MyLaps reescribe constantemente con la clasificación.
    TIMING_XML_PATH: str = "W:/current.xml"

    # Segundos que se reutiliza la última lectura antes de volver al
    # disco. Con las plantillas preguntando cada medio segundo, sin esto
    # se leería el archivo de red decenas de veces por segundo.
    TIMING_CACHE_SECONDS: float = 0.4

    # ── CasparCG ──────────────────────────────────────────────
    # Servidor AMCP. Por defecto la misma máquina que el backend.
    CASPARCG_HOST: str = "127.0.0.1"
    CASPARCG_PORT: int = 5250

    # Canal sobre el que se grafica. Las capas salen del catálogo.
    CASPARCG_CHANNEL: int = 1

    # Segundos de espera al conectar y al leer la respuesta AMCP.
    CASPARCG_TIMEOUT: float = 5.0

    # ── Autenticación (JWT) ──────────────────────────────────
    # La firma sale del .env. Si alguien levanta el backend sin definirla
    # se usa este default, que sirve para desarrollo pero NO para salir al
    # aire: cualquiera que conozca la cadena puede firmarse un token.
    JWT_SECRET: str = "cambiar-esta-clave-en-produccion"
    JWT_ALGORITHM: str = "HS256"

    # 12 horas cubren un día completo de carrera sin obligar a volver a
    # entrar a media transmisión.
    JWT_EXPIRE_HOURS: int = 12

    # ── Clima ────────────────────────────────────────────────
    # Las coordenadas del circuito las pone cada cliente en el asistente
    # de instalación y viven en la base, no aquí: estas líneas tenían las
    # de un autódromo concreto, y con eso el producto solo servía para él.
    #
    # Lo que queda son valores neutros de respaldo, para que una
    # instalación a medio configurar no reviente al pedir el clima. El
    # 0,0 es el Golfo de Guinea; si alguien ve ese dato al aire, sabrá al
    # instante que falta configurar la ubicación.
    WEATHER_LAT: float = 0.0
    WEATHER_LON: float = 0.0
    WEATHER_PLACE: str = ""
    WEATHER_COUNTRY: str = ""

    # Segundos que se reutiliza la última consulta. El clima no cambia de
    # un segundo a otro y la plantilla se puede sacar al aire muchas veces
    # en una tanda; sin esto se golpearía el servicio sin necesidad.
    WEATHER_CACHE_SECONDS: int = 600

    # Espera de la consulta. Corta a propósito: si el servicio no responde
    # se prefiere el último dato conocido antes que retrasar un gráfico.
    WEATHER_TIMEOUT: float = 6.0

    # ── Licencia ─────────────────────────────────────────────
    # Se valida offline contra la clave pública que lleva escrita
    # license_services.py. La conexión hace falta para activar y para
    # renovar, nunca para trabajar: en el autódromo la red se cae y el
    # software no puede dejar de funcionar por eso.

    # En falso, un equipo sin archivo de licencia arranca en modo
    # desarrollo. El instalador lo pone en verdadero, y a partir de ahí
    # la falta de licencia bloquea.
    LICENSE_REQUIRED: bool = False

    # Token emitido por Zentogo. Lo escribe el instalador al activar.
    LICENSE_FILE: str = "licencia.lic"

    # Marca de agua del reloj, para detectar que alguien atrasó la fecha
    # del sistema para estirar una licencia vencida.
    LICENSE_STATE_FILE: str = "licencia.estado.json"

    # Días que el reloj puede aparecer por detrás de lo ya visto sin que
    # se considere manipulación. Amplio a propósito: un equipo que perdió
    # la pila de la placa arranca con fecha vieja sin que nadie mienta.
    LICENSE_CLOCK_TOLERANCE_DAYS: int = 3

    # Segundos que se reutiliza el estado antes de releer el disco. Corto
    # para que el salto de ACTIVA a GRACIA se note en el mismo minuto.
    LICENSE_CACHE_SECONDS: float = 30.0

    # Servidor de licencias de Zentogo: activación, renovación y
    # manifiestos de versión.
    LICENSE_SERVER_URL: str = "https://licencias.zentogo.com"

    # ── Instalación ──────────────────────────────────────────
    # Versión del producto. Fuente única: la reportan /setup/estado y el
    # actualizador, y con ella el manifiesto decide si hay algo nuevo.
    APP_VERSION: str = "1.0.0"

    # Token de un solo uso que protege el asistente de instalación. Lo
    # escribe el instalador y se borra al terminar. Sin él, cualquiera en
    # la red local podría llegar antes que el técnico y nombrarse dueño.
    SETUP_TOKEN_FILE: str = "instalacion.token"

settings = Settings()

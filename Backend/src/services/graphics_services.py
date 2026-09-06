"""
Catálogo de plantillas y traducción a comandos AMCP.

El frontend nunca manda comandos crudos: manda el id del gráfico y este
servicio decide el canal, la capa y la ruta de la plantilla. Así el mapa
de capas vive en un solo lugar.
"""

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from config import settings
from src.models.categories_model import Category
from src.models.events_model import Event
from src.models.pilots_model import Pilot
from src.models.vehicles_model import Vehicle
from src.services.casparcg_client import casparcg


# ── Catálogo ──────────────────────────────────────────────────

@dataclass(frozen=True)
class Template:
    graphic_id: str      # el mismo id que usan los botones del frontend
    name: str
    group: str           # background | totem | flag | grid | pilot | misc
    layer: int           # capa AMCP dentro del canal
    path: str            # ruta de la plantilla en el template-path de CasparCG
    accepts_data: bool = False


# Cada grupo ocupa su propia capa: los fondos viven detrás y los gráficos
# encima, así se puede cambiar uno sin tocar el otro.
LAYERS = {
    "background": 10,
    "totem": 20,
    "flag": 30,
    "grid": 40,
    # El drag tiene capa propia y no comparte la de la grilla: no son lo
    # mismo y en una jornada de drag no hay parrilla que quitar de en medio.
    "drag": 45,
    "pilot": 50,
    "misc": 60,
    "results": 70,
}


TEMPLATES: dict[str, Template] = {
    t.graphic_id: t
    for t in [
        # ── Fondos (capa 10) ──────────────────────────────────
        Template("bg-none",    "Sin Fondo",      "background", 10, "html/10_no_background"),
        Template("bg-red",     "Fondo Rojo",     "background", 10, "html/11_red_background"),
        Template("bg-blue",    "Fondo Azul",     "background", 10, "html/12_blue_background"),
        Template("bg-yellow",  "Fondo Amarillo", "background", 10, "html/13_yellow_background"),
        Template("bg-green",   "Fondo Verde",    "background", 10, "html/14_green_background"),
        Template("bg-cyan",    "Fondo Cian",     "background", 10, "html/15_cian_background"),
        Template("bg-magenta", "Fondo Magenta",  "background", 10, "html/16_magenta_background"),
        Template("bg-orange",  "Fondo Naranja",  "background", 10, "html/17_orange_background"),

        # ── Tótems (capa 20) ──────────────────────────────────
        Template("totem-completo",  "Tótem Nombre Completo", "totem", 20, "html/20_totem_fullname",  accepts_data=True),
        # Al líder y al intervalo ya no cargan plantilla propia: son una
        # columna que el panel abre sobre el tótem completo que ya está al
        # aire, con un UPDATE. Se dejan declarados porque el panel los
        # sigue listando como botones, pero apuntan al mismo arte: si
        # alguien los saca por API, ve el tótem, no un gráfico roto.
        Template("totem-lider",     "Tótem al Líder",        "totem", 20, "html/20_totem_fullname",  accepts_data=True),
        Template("totem-intervalo", "Tótem Intervalo",       "totem", 20, "html/20_totem_fullname",  accepts_data=True),

        # ── Banderas (capa 30) ────────────────────────────────
        Template("bandera-verde",    "Bandera Verde",      "flag", 30, "html/30_green_flag"),
        Template("bandera-amarilla", "Bandera Amarilla",   "flag", 30, "html/31_yellow_flag"),
        Template("safety-car",       "Safety Car",         "flag", 30, "html/32_safety_car_flag"),
        Template("bandera-roja",     "Bandera Roja",       "flag", 30, "html/33_red_flag"),
        Template("bandera-cuadros",  "Bandera de Cuadros", "flag", 30, "html/34_finish_flag"),
        Template("bandera-blanca",   "Bandera Blanca",     "flag", 30, "html/35_white_flag"),
        Template("bandera-azul",     "Bandera Azul",       "flag", 30, "html/36_blue_flag"),
        Template("bandera-negra",    "Bandera Negra",      "flag", 30, "html/37_black_flag"),
        Template("bandera-mecanica", "Problema Mecánico",  "flag", 30, "html/38_meatball_flag"),
        Template("pista-resbaladiza","Pista Resbaladiza",  "flag", 30, "html/39_slippery_flag"),
        # La negra y blanca faltaba: es la llamada de atención previa a la
        # negra, y sin ella no se puede avisar sin descalificar.
        Template("bandera-advertencia","Llamada de Atención", "flag", 30, "html/3A_warning_flag"),

        # ── Grilla de partida (capa 40) ───────────────────────
        Template("grilla",      "Grilla de Partida",   "grid", 40, "html/40_starting_grid_names", accepts_data=True),
        Template("grilla-fotos", "Grilla con Fotos",    "grid", 40, "html/41_starting_grid_foto",  accepts_data=True),

        # ── Fichas de piloto (capa 50) ────────────────────────
        # ── Drag ──
        # Cada pasada se cuenta sola: no hay clasificación que actualizar
        # ni vueltas que contar, así que estos gráficos no derivan de los
        # del circuito.
        Template("drag-resultado", "Resultado de la Pasada", "drag", 45, "html/80_drag_result", accepts_data=True),

        Template("ficha-corta",    "Carta",          "pilot", 50, "html/51_pilot_card_short",    accepts_data=True),
        # Dos pilotos frente a frente: nombre, dorsal y foto, nada más.
        Template("carta-vs",       "Carta VS",       "pilot", 50, "html/52_pilot_vs",            accepts_data=True),

        # ── Misceláneos (capa 60) ─────────────────────────────
        Template("circuito", "Circuito",       "misc", 60, "html/60_circuit_track", accepts_data=True),
        Template("evento",   "Evento",         "misc", 60, "html/61_event",         accepts_data=True),
        Template("categoria", "Categoría",     "misc", 60, "html/68_category",      accepts_data=True),
        Template("narrador", "Narrador",       "misc", 60, "html/62_narrator",      accepts_data=True),
        Template("redes",    "Redes Sociales", "misc", 60, "html/63_social_media",  accepts_data=True),
        Template("clima",       "Clima",        "misc", 60, "html/65_weather",      accepts_data=True),
        Template("comentarista", "Comentarista", "misc", 60, "html/66_comentarist", accepts_data=True),
        Template("reportero",    "Reportero",    "misc", 60, "html/67_reporter",    accepts_data=True),

        # ── 1-70 RESULTADOS ──
        # Capa propia: el cuadro ocupa la pantalla y no debe compartir capa
        # con nada, ni tumbar los misceláneos al salir.
        Template("resultados", "Cuadro de Resultados", "results", 70, "html/70_results", accepts_data=True),
    ]
}


# ── Escapado AMCP ─────────────────────────────────────────────

def quote(value: str) -> str:
    """
    Envuelve un valor entre comillas escapando lo que AMCP interpreta.

    El orden importa: primero las barras invertidas, si no se escaparían
    también las que agrega el escape de las comillas.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def serialize_data(data: dict) -> str:
    """
    Convierte el diccionario en el literal que CasparCG le pasará a la
    función update() de la plantilla.

    ensure_ascii deja los acentos escapados como secuencias unicode, así
    el comando viaja en ASCII puro y no depende de la codificación del
    socket; el navegador los reconstruye al evaluar el literal.
    """
    return json.dumps(data, ensure_ascii=True, separators=(",", ":"))


# ── Fotos de pilotos y logos de marcas ────────────────────────

PUBLIC_DIR = Path(__file__).resolve().parents[2] / "src" / "public"

# Formatos que CEF (el navegador de CasparCG) sabe pintar.
EXTENSIONES = (".png", ".jpg", ".jpeg", ".webp", ".avif")


def _slug(value: str) -> str:
    """'Mini Cooper' -> 'mini-cooper'. Sin acentos, para nombrar archivos."""
    limpio = unicodedata.normalize("NFD", value.strip().lower())
    limpio = "".join(c for c in limpio if unicodedata.category(c) != "Mn")
    return "-".join(limpio.replace("_", " ").replace("-", " ").split())


def _url(ruta: Path) -> str:
    """
    URL absoluta del archivo, con la fecha de modificación como versión.

    Sin eso CEF se queda con la imagen cacheada y no se vería el cambio
    al reemplazar una foto sin reiniciar CasparCG.
    """
    relativa = ruta.relative_to(PUBLIC_DIR).as_posix()
    return f"{settings.PUBLIC_BASE_URL}/public/{relativa}?v={int(ruta.stat().st_mtime)}"


def _buscar(carpeta: Path, nombre: str) -> Path | None:
    for ext in EXTENSIONES:
        candidato = carpeta / f"{nombre}{ext}"
        if candidato.is_file():
            return candidato
    return None


def pilot_photo_url(pilot_id: int, photo: str | None = None) -> str:
    """
    Foto del piloto.

    Manda el campo `photo` del piloto si lo tiene: es una ruta dentro de
    public/ y permite cualquier nombre de archivo. Si está vacío se busca
    <pilot_id>.<ext> en cualquier subcarpeta de pilotos/, así la
    organización por categorías es libre.
    """
    if photo:
        archivo = PUBLIC_DIR / photo.lstrip("/")
        if archivo.is_file():
            return _url(archivo)

    raiz = PUBLIC_DIR / "pilotos"
    if raiz.is_dir():
        for carpeta in [raiz, *(d for d in raiz.iterdir() if d.is_dir())]:
            hallado = _buscar(carpeta, str(pilot_id))
            if hallado:
                return _url(hallado)

    # Transparente: mejor un hueco vacío que la foto del piloto anterior.
    reserva = _buscar(raiz, "_sin-foto")
    return _url(reserva) if reserva else ""


def event_image_url(archivo: str | None) -> str:
    """
    Imagen del evento, absoluta y con versión.

    Va por el mismo camino que la foto del piloto y el logo de marca: la
    plantilla se abre desde file:// y una ruta relativa no resolvería.
    """
    if not archivo:
        return ""

    ruta = PUBLIC_DIR / "eventos" / archivo
    return _url(ruta) if ruta.is_file() else ""


def category_logo_url(archivo: str | None) -> str:
    """
    Logo de la categoría, absoluto y con versión.

    Lo usa el gráfico de Evento cuando el evento no tiene imagen propia:
    "GT Challenge de las Américas" corre la categoría GT Challenge, y su
    logo es el que se espera ver en el banner.
    """
    if not archivo:
        return ""

    ruta = PUBLIC_DIR / "categorias" / archivo
    return _url(ruta) if ruta.is_file() else ""


def brand_logo_url(brand: str | None) -> str:
    """
    Logo de la marca, tolerante con el nombre del archivo.

    Se compara el slug del archivo contra el de la marca, así da igual
    si el archivo se llama "mini cooper.jpg", "Mini-Cooper.PNG" o
    "mini_cooper.webp": todos resuelven a mini-cooper.
    """
    raiz = PUBLIC_DIR / "marcas"

    if brand and raiz.is_dir():
        buscado = _slug(brand)
        for archivo in sorted(raiz.iterdir()):
            if not archivo.is_file() or archivo.suffix.lower() not in EXTENSIONES:
                continue
            if _slug(archivo.stem) == buscado:
                return _url(archivo)

    reserva = _buscar(raiz, "_sin-logo")
    return _url(reserva) if reserva else ""


# ── Datos de un piloto para las plantillas ────────────────────

# Cada plantilla nombra sus campos a su manera, asi que se arma el
# payload segun el destino. La logica vive aqui, en el backend, no en
# el frontend: el boton solo manda el pilot_id.

async def build_pilot_payload(
    graphic_id: str,
    pilot_id: int,
    category_id: int | None = None,
) -> dict:
    pilot = await Pilot.find_one(Pilot.pilot_id == pilot_id)
    if pilot is None:
        raise HTTPException(status_code=404, detail=f"Piloto {pilot_id} no encontrado")

    # El vehiculo guarda la relacion, asi que se busca por el DBRef.
    #
    # Con `category_id` se acota a esa categoria. Hace falta porque hay
    # pilotos que corren en varias: Dean Paquette esta en Prospec Series y
    # en GT Challenge con carros distintos, y sin acotar salia el primero
    # que devolviera Mongo, que no tiene por que ser el que se esta
    # graficando.
    filtro: dict = {"pilots.$id": pilot.id}
    if category_id is not None:
        filtro["category_id"] = category_id

    vehicle = await Vehicle.find_one(filtro)

    # Pedida una categoria en la que no tiene carro, se dice: mostrar el de
    # otra categoria seria peor que no mostrar ninguno.
    if vehicle is None and category_id is not None:
        vehicle = None

    category = None
    if vehicle is not None:
        category = await Category.find_one(Category.category_id == vehicle.category_id)
    elif category_id is not None:
        # Sin carro, la categoria pedida se muestra igual: el piloto si
        # pertenece a ella aunque no tenga maquina asignada.
        category = await Category.find_one(Category.category_id == category_id)

    nombre = " ".join(x for x in (pilot.name, pilot.last_name) if x)

    # Sin dorsal se manda vacio, no "None": en drag hay carros sin numero
    # y la carta esconde el hueco en vez de escribir la palabra.
    numero = str(vehicle.number) if vehicle and vehicle.number is not None else ""
    carro = " ".join(x for x in ((vehicle.brand if vehicle else None),
                                 (vehicle.model if vehicle else None)) if x)

    # Categoria y subcategoria por separado. Antes la subcategoria pisaba a
    # la categoria y solo se veia una de las dos, asi que en pantalla ponia
    # "Gran Turismo 2" sin decir nunca que eso es GT Challenge.
    categoria = category.category_name if category else ""

    subcategoria = ""
    if category and vehicle and vehicle.sub_category_id:
        sub = next((sc for sc in category.sub_categories
                    if sc.sub_category_id == vehicle.sub_category_id), None)
        if sub:
            subcategoria = sub.sub_category_name

    # Siempre se mandan foto y logo, aunque sea el transparente: si se
    # omitieran, update() dejaría los del gráfico anterior en pantalla.
    foto = pilot_photo_url(pilot.pilot_id, pilot.photo)
    logo = brand_logo_url(vehicle.brand if vehicle else None)

    if graphic_id == "ficha-corta":
        return {
            "pilot_name": nombre,
            "car_number": numero,
            "category": categoria,
            "sub_category": subcategoria,
            "vehicle": carro,
            "team": pilot.team_brand or "",
            "country": pilot.nationality or "",
            "pilot_photo": foto,
            "brand_logo": logo,
        }

    raise HTTPException(
        status_code=400,
        detail=f"La plantilla '{graphic_id}' no se alimenta con un pilot_id",
    )


# ── Servicio ──────────────────────────────────────────────────

class GraphicsService:
    def __init__(self):
        self.channel = settings.CASPARCG_CHANNEL
        # Qué gráfico quedó al aire en cada capa: {layer: graphic_id}
        self._on_air: dict[int, str] = {}

    # ── Consultas ─────────────────────────────────────────────

    def get_template(self, graphic_id: str) -> Template | None:
        return TEMPLATES.get(graphic_id)

    def list_templates(self, group: str | None = None) -> list[Template]:
        items = list(TEMPLATES.values())
        if group:
            items = [t for t in items if t.group == group]
        return sorted(items, key=lambda t: (t.layer, t.path))

    def on_air(self) -> dict[str, str]:
        """Lo que está al aire, indexado por grupo, para que lo lea el frontend."""
        return {
            TEMPLATES[gid].group: gid
            for gid in self._on_air.values()
            if gid in TEMPLATES
        }

    def _target(self, layer: int) -> str:
        return f"{self.channel}-{layer}"

    # ── Comandos ──────────────────────────────────────────────

    async def play(self, template: Template, data: dict | None = None) -> dict:
        """
        CG <canal>-<capa> ADD 1 "<plantilla>" 1 ["<datos>"]

        El último 1 es play-on-load: CasparCG llama a play() apenas carga
        la plantilla, que es como están escritas todas las nuestras.
        """
        command = f"CG {self._target(template.layer)} ADD 1 {quote(template.path)} 1"

        if data:
            command += f" {quote(serialize_data(data))}"

        result = await casparcg.send(command)

        # Una capa solo sostiene un gráfico: el nuevo reemplaza al anterior.
        self._on_air[template.layer] = template.graphic_id

        return result

    async def update(self, template: Template, data: dict) -> dict:
        """CG <canal>-<capa> UPDATE 1 "<datos>" — refresca sin recargar."""
        command = (
            f"CG {self._target(template.layer)} UPDATE 1 "
            f"{quote(serialize_data(data))}"
        )
        return await casparcg.send(command)

    async def clear_layer(self, layer: int) -> dict:
        """CLEAR <canal>-<capa> — saca de aire todo lo que haya en esa capa."""
        result = await casparcg.send(f"CLEAR {self._target(layer)}")
        self._on_air.pop(layer, None)
        return result

    async def clear_all(self) -> dict:
        """CLEAR <canal> — vacía el canal completo."""
        result = await casparcg.send(f"CLEAR {self.channel}")
        self._on_air.clear()
        return result


service = GraphicsService()


async def build_grid_payload(limite: int = 30, event_id: int | None = None) -> dict:
    """
    La parrilla de largada, sacada del cronometraje.

    El orden de la grilla es el de la clasificación: en la práctica la
    tanda de clasificación deja el XML ordenado por posición, que es lo
    que se pinta. Cada fila lleva posición, dorsal, apellido y la marca
    del carro.

    El apellido y la marca vienen ya cruzados con la base por
    obtener_clasificacion(): MyLaps manda los nombres sin acentos y a
    veces abreviados, y la marca no la manda en absoluto.
    """

    # Igual que en la carta VS: el import va aquí dentro porque
    # timing_services ya importa este módulo para el logo de la marca.
    from src.services.timing_services import obtener_clasificacion

    datos = await obtener_clasificacion(limite=limite)

    pilotos = [
        {
            "position": fila.get("position"),
            "number": fila.get("number", ""),
            "name": fila.get("name", ""),
            "last_name": fila.get("last_name", ""),
            "full_name": fila.get("full_name", ""),
            "brand": fila.get("brand") or "",
            "brand_logo": fila.get("brand_logo") or "",
            # La de nombres no los usa, pero la de fotos sí: la cara y el
            # tiempo de clasificación con el que se ganó el sitio. Se
            # mandan en el mismo payload porque las dos salen de la misma
            # tanda y no compensa un armador aparte para dos campos.
            "photo": (pilot_photo_url(fila["pilot_id"])
                      if fila.get("pilot_id") else ""),
            "best_time": fila.get("best_time", ""),
        }
        for fila in datos.get("standings", [])
    ]

    # El logo no viaja en el payload. url_logo_cliente() devuelve una ruta
    # relativa a la raíz ("/media/logo/..."), y CasparCG abre las
    # plantillas con file://, donde eso apunta a la raíz del disco y la
    # imagen no carga nunca. La plantilla apunta directamente a
    # img/logo-cliente.png, que es el archivo que Ajustes sobrescribe al
    # subir uno nuevo: es como lo resuelven el evento y el narrador.
    # El nombre del evento sale del que se eligió en el panel, no del XML.
    # MyLaps escribe ahí la tanda que tenga cargada, que puede ser la
    # anterior: se graficaba Prospec Series y en pantalla salía Street
    # Legal. Si no hay evento elegido se cae al del XML, que es mejor que
    # dejar el título en blanco.
    nombre_evento = datos.get("event", "")
    if event_id is not None:
        evento = await Event.find_one(Event.event_id == event_id)
        if evento is not None and evento.name:
            nombre_evento = evento.name

    return {
        "title": "Grilla de Partida",
        "subtitle": nombre_evento,
        # group_name y no group: MyLaps antepone el número de grupo
        # ("5 - STREET LEGAL") y en el arte solo interesa el nombre.
        "category": datos.get("group_name", ""),
        "drivers": pilotos,
    }


async def build_vs_payload(pilot_a: int, pilot_b: int) -> dict:
    """
    Los dos pilotos de la carta VS.

    Nombre, apellido, dorsal y foto de cada uno, más su carro y sus dos
    tiempos: la mejor vuelta y la última. El nombre dice quiénes son y los
    tiempos dicen cómo van, que es para lo que sirve enfrentarlos.

    El dorsal y el carro salen del vehículo, que es donde viven; si el
    piloto no tiene carro asignado se manda vacío en vez de inventarlo.
    """

    # Los tiempos vienen del cronometraje en vivo, no de la base. Se piden
    # una sola vez para los dos: obtener_clasificacion() lee y parsea el
    # XML entero, y hacerlo dos veces por carta es leerlo de más.
    # El import va aquí dentro y no arriba a propósito: timing_services ya
    # importa este módulo para el logo de la marca, y hacerlo al revés en
    # la cabecera cierra el círculo y revienta el arranque.
    from src.services.timing_services import obtener_clasificacion

    try:
        # Un límite alto y no el de la torre: los dos pilotos de la carta
        # pueden ir en mitad de la tabla, y con el límite corto no
        # aparecerían en la lista y se quedarían sin tiempos.
        clasificacion = await obtener_clasificacion(limite=500)
        vueltas = {f["number"]: f for f in clasificacion.get("standings", [])}
    except Exception:
        # Sin MyLaps la carta sale igual, solo que sin tiempos: es un
        # gráfico de presentación y tiene que poder usarse en seco.
        vueltas = {}

    async def uno(pilot_id: int, sufijo: str) -> dict:
        pilot = await Pilot.find_one(Pilot.pilot_id == pilot_id)
        if pilot is None:
            raise HTTPException(404, f"Piloto {pilot_id} no encontrado")

        vehicle = await Vehicle.find_one({"pilots.$id": pilot.id})

        dorsal = str(vehicle.number) if vehicle and vehicle.number is not None else ""

        # Se cruza por dorsal y no por piloto: cuando dos pilotos comparten
        # carro, MyLaps cronometra el carro, así que el dorsal es lo único
        # que ata una fila del XML con esta carta.
        fila = vueltas.get(dorsal, {})

        return {
            f"name_{sufijo}": pilot.name or "",
            f"last_name_{sufijo}": pilot.last_name or "",
            f"number_{sufijo}": dorsal,
            f"brand_{sufijo}": (vehicle.brand or "") if vehicle else "",
            f"model_{sufijo}": (vehicle.model or "") if vehicle else "",
            # Siempre se mandan, vacíos incluidos: omitirlos dejaría en
            # pantalla los datos del piloto anterior.
            f"best_time_{sufijo}": fila.get("best_time", ""),
            f"last_time_{sufijo}": fila.get("last_time", ""),
            f"photo_{sufijo}": pilot_photo_url(pilot.pilot_id, pilot.photo),
        }

    return {**await uno(pilot_a, "a"), **await uno(pilot_b, "b")}

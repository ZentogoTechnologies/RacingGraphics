from typing import Optional

from fastapi import HTTPException

from src.models.categories_model import Category
from pathlib import Path

from src.services.imagenes_services import (
    borrar_si_sobra, copiar_de_ruta, guardar_bytes,
)
from src.models.events_model import Event, Inscrito, Sesion
from src.models.pilots_model import Pilot
from src.models.vehicles_model import Vehicle
from src.schemas.common_schemas import Page
from src.schemas.events_schemas import (
    ETIQUETAS, EventCreate, EventResponse, EventUpdate,
    InscritoIn, InscritoOut, SesionIn, SesionOut,
)
from src.services.pagination import campo_orden, combinar, direccion, filtro_busqueda


# Backend/src/public/eventos, mirando desde Backend/src/services.
CARPETA_IMAGENES = Path(__file__).resolve().parents[1] / "public" / "eventos"

RUTA_RELATIVA = "eventos"


def url_imagen_evento(archivo):
    """La ruta con la que el navegador y CasparCG piden la imagen."""
    return f"/public/{RUTA_RELATIVA}/{archivo}" if archivo else None


class EventService:
    ORDENABLES = {"event_id", "name", "start_date", "end_date"}
    BUSCABLES = ["name", "location"]

    # ── Resolución de nombres ────────────────────────────────

    async def _catalogo_categorias(self, ids: list[int]) -> dict:
        if not ids:
            return {}
        cats = await Category.find({"category_id": {"$in": ids}}).to_list()
        return {c.category_id: c for c in cats}

    async def _to_response(self, evento: Event) -> EventResponse:
        cats = await self._catalogo_categorias(
            list({*evento.category_ids, *(i.category_id for i in evento.inscritos)})
        )

        # Los vehículos y pilotos se traen de una para no hacer una consulta
        # por fila: una parrilla de cincuenta carros son cien viajes.
        ids_veh = [i.vehicle_id for i in evento.inscritos]
        vehiculos = {}
        if ids_veh:
            vehiculos = {
                v.vehicle_id: v
                for v in await Vehicle.find({"vehicle_id": {"$in": ids_veh}}).to_list()
            }

        ids_pil = sorted({p for i in evento.inscritos for p in i.pilot_ids})
        pilotos = {}
        if ids_pil:
            pilotos = {
                p.pilot_id: p
                for p in await Pilot.find({"pilot_id": {"$in": ids_pil}}).to_list()
            }

        inscritos = []
        for i in evento.inscritos:
            v = vehiculos.get(i.vehicle_id)
            cat = cats.get(i.category_id)
            sub = None
            if cat and i.sub_category_id is not None:
                sub = next(
                    (s.sub_category_name for s in cat.sub_categories
                     if s.sub_category_id == i.sub_category_id),
                    None,
                )

            inscritos.append(InscritoOut(
                vehicle_id=i.vehicle_id,
                pilot_ids=i.pilot_ids,
                category_id=i.category_id,
                sub_category_id=i.sub_category_id,
                numero=v.number if v else None,
                display_number=(
                    (v.display_number or (str(v.number) if v.number is not None else None))
                    if v else None
                ),
                brand=v.brand if v else None,
                model=v.model if v else None,
                category_name=cat.category_name if cat else None,
                sub_category_name=sub,
                pilotos=[
                    {"pilot_id": pid,
                     "name": pilotos[pid].name,
                     "last_name": pilotos[pid].last_name}
                    for pid in i.pilot_ids if pid in pilotos
                ],
            ))

        sesiones = [
            SesionOut(
                **s.model_dump(),
                categorias=[cats[c].category_name for c in s.category_ids if c in cats],
            )
            for s in sorted(evento.sesiones, key=lambda s: (s.dia, s.numero_orden))
        ]

        return EventResponse(
            event_id=evento.event_id,
            name=evento.name,
            start_date=evento.start_date,
            end_date=evento.end_date,
            discipline=evento.discipline,
            location=evento.location,
            image=evento.image,
            image_url=url_imagen_evento(evento.image),
            category_ids=evento.category_ids,
            categorias=[cats[c].category_name for c in evento.category_ids if c in cats],
            inscritos=inscritos,
            sesiones=sesiones,
            dias=evento.dias,
            total_dias=len(evento.dias),
            total_inscritos=len(evento.inscritos),
            total_sesiones=len(evento.sesiones),
            is_active=evento.is_active,
        )

    # ── Validaciones compartidas ─────────────────────────────

    async def _resolver_inscritos(
        self, entradas: list[InscritoIn], category_ids: list[int]
    ) -> list[Inscrito]:
        """Convierte la selección en inscritos, copiando categoría y
        subcategoría del vehículo."""
        if not entradas:
            return []

        ids = [e.vehicle_id for e in entradas]
        if len(ids) != len(set(ids)):
            raise HTTPException(
                status_code=400, detail="Hay vehículos repetidos en la lista de inscritos"
            )

        # fetch_links resuelve los pilotos en la misma consulta. Sin esto
        # `v.pilots` son objetos Link sin abrir y no se les puede leer el
        # pilot_id para comprobar que el piloto es de ese carro.
        vehiculos = {
            v.vehicle_id: v
            for v in await Vehicle.find(
                {"vehicle_id": {"$in": ids}}, fetch_links=True
            ).to_list()
        }

        faltan = set(ids) - set(vehiculos)
        if faltan:
            raise HTTPException(
                status_code=404, detail=f"Vehículos no encontrados: {sorted(faltan)}"
            )

        inscritos = []
        for e in entradas:
            v = vehiculos[e.vehicle_id]

            if v.category_id not in category_ids:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"El vehículo {v.display_number or v.number or v.vehicle_id} "
                        "corre en una categoría que no está "
                        "entre las del evento"
                    ),
                )

            # Los pilotos tienen que ser de ese carro. Sin esto se podría
            # inscribir a alguien en un vehículo que no conduce, y al aire
            # saldría un nombre que no corresponde al dorsal.
            del_carro = {p.pilot_id for p in v.pilots} if v.pilots else set()
            ajenos = set(e.pilot_ids) - del_carro
            if ajenos:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Los pilotos {sorted(ajenos)} no están asignados al "
                        f"vehículo {v.display_number or v.number or v.vehicle_id}"
                    ),
                )

            inscritos.append(Inscrito(
                vehicle_id=v.vehicle_id,
                pilot_ids=e.pilot_ids,
                category_id=v.category_id,
                sub_category_id=v.sub_category_id,
            ))

        return inscritos

    async def _validar_categorias(self, ids: list[int]):
        if not ids:
            return
        existen = await Category.find({"category_id": {"$in": ids}}).count()
        if existen != len(set(ids)):
            raise HTTPException(
                status_code=404, detail="Alguna de las categorías no existe"
            )

    async def _siguiente_id(self) -> int:
        ultimo = await Event.find_all().sort(("event_id", -1)).limit(1).to_list()
        return (ultimo[0].event_id + 1) if ultimo else 1

    # ── CRUD ─────────────────────────────────────────────────

    async def get_events(
        self,
        discipline: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: Optional[str] = None,
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> Page[EventResponse]:
        query = combinar(
            {"discipline": discipline} if discipline else None,
            filtro_busqueda(search, self.BUSCABLES),
        )

        total = await Event.find(query).count()

        consulta = Event.find(query).sort(
            (campo_orden(sort_by, self.ORDENABLES, "start_date"), direccion(sort_dir))
        ).skip(skip)

        if limit is not None:
            consulta = consulta.limit(limit)

        eventos = await consulta.to_list()
        return Page(
            items=[await self._to_response(e) for e in eventos],
            total=total, skip=skip, limit=limit,
        )

    async def get_event_by_id(self, event_id: str) -> Optional[EventResponse]:
        evento = await Event.find_one(Event.event_id == int(event_id))
        return await self._to_response(evento) if evento else None

    async def create_event(self, data: EventCreate) -> EventResponse:
        if data.event_id is None:
            event_id = await self._siguiente_id()
        else:
            event_id = data.event_id
            if await Event.find_one(Event.event_id == event_id):
                raise HTTPException(status_code=400, detail="event_id ya existe")

        await self._validar_categorias(data.category_ids)
        inscritos = await self._resolver_inscritos(data.inscritos, data.category_ids)

        evento = Event(
            event_id=event_id,
            name=data.name,
            start_date=data.start_date,
            end_date=data.end_date,
            discipline=data.discipline,
            location=data.location,
            category_ids=data.category_ids,
            inscritos=inscritos,
        )
        await evento.insert()
        return await self._to_response(evento)

    async def update_event(self, event_id: str, data: EventUpdate) -> Optional[EventResponse]:
        evento = await Event.find_one(Event.event_id == int(event_id))
        if not evento:
            return None

        cambios = data.model_dump(exclude_unset=True)

        inicio = cambios.get("start_date", evento.start_date)
        fin = cambios.get("end_date", evento.end_date)
        if fin < inicio:
            raise HTTPException(
                status_code=400, detail="La fecha final no puede ser anterior a la inicial"
            )

        # Recortar el rango puede dejar sesiones fuera del evento. Se avisa
        # en vez de borrarlas en silencio.
        if "start_date" in cambios or "end_date" in cambios:
            huerfanas = [s.nombre for s in evento.sesiones if not (inicio <= s.dia <= fin)]
            if huerfanas:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Estas sesiones quedarían fuera del nuevo rango de fechas: "
                        + ", ".join(huerfanas)
                    ),
                )

        if "category_ids" in cambios:
            await self._validar_categorias(cambios["category_ids"])

        categorias = cambios.get("category_ids", evento.category_ids)

        if "inscritos" in cambios:
            cambios["inscritos"] = await self._resolver_inscritos(
                [InscritoIn(**i) for i in cambios["inscritos"]], categorias
            )
        elif "category_ids" in cambios:
            # Al quitar una categoría, sus inscritos dejan de tener sentido.
            fuera = [i for i in evento.inscritos if i.category_id not in categorias]
            if fuera:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Hay {len(fuera)} vehículo(s) inscritos en categorías que "
                        "estás quitando. Sácalos de la lista primero."
                    ),
                )

        for campo, valor in cambios.items():
            setattr(evento, campo, valor)

        await evento.save()
        return await self._to_response(evento)

    async def delete_event(self, event_id: str) -> bool:
        evento = await Event.find_one(Event.event_id == int(event_id))
        if not evento:
            return False
        await evento.delete()
        return True

    # ── Sesiones ─────────────────────────────────────────────

    def _numerar(self, evento: Event, datos: SesionIn) -> int:
        """Qué número le toca a la sesión.

        Se cuenta por evento y categoría, no por día: si el sábado hubo
        Practice 1 de TCR, la del domingo es la 2. Las prácticas libres se
        numeran entre ellas, porque son otra cosa: no son la práctica de
        una categoría concreta.
        """
        if datos.libre:
            previas = [s for s in evento.sesiones if s.libre and s.tipo == datos.tipo]
            return len(previas) + 1

        categoria = datos.category_ids[0]
        previas = [
            s for s in evento.sesiones
            if not s.libre and s.tipo == datos.tipo and categoria in s.category_ids
        ]
        return len(previas) + 1

    def _nombrar(self, datos: SesionIn, numero: int, nombres: list[str]) -> str:
        if datos.libre:
            return f"Práctica Libre {numero} · {', '.join(nombres)}"
        return f"{ETIQUETAS[datos.tipo]} {numero} · {nombres[0] if nombres else ''}".strip(" ·")

    async def add_session(self, event_id: str, datos: SesionIn) -> Optional[EventResponse]:
        evento = await Event.find_one(Event.event_id == int(event_id))
        if not evento:
            return None

        if datos.dia not in evento.dias:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El día {datos.dia} está fuera del evento "
                    f"({evento.start_date} a {evento.end_date})"
                ),
            )

        ajenas = set(datos.category_ids) - set(evento.category_ids)
        if ajenas:
            raise HTTPException(
                status_code=400,
                detail=f"Las categorías {sorted(ajenas)} no corren en este evento",
            )

        inscritos_validos = {i.vehicle_id for i in evento.inscritos
                             if i.category_id in datos.category_ids}
        fuera = set(datos.vehicle_ids) - inscritos_validos
        if fuera:
            raise HTTPException(
                status_code=400,
                detail=f"Los vehículos {sorted(fuera)} no están inscritos en esa categoría",
            )

        cats = await self._catalogo_categorias(datos.category_ids)
        nombres = [cats[c].category_name for c in datos.category_ids if c in cats]

        numero = self._numerar(evento, datos)

        evento.sesiones.append(Sesion(
            numero_orden=len(evento.sesiones) + 1,
            dia=datos.dia,
            tipo=datos.tipo,
            category_ids=datos.category_ids,
            libre=datos.libre,
            numero=numero,
            nombre=self._nombrar(datos, numero, nombres),
            vehicle_ids=datos.vehicle_ids,
        ))

        await evento.save()
        return await self._to_response(evento)

    async def delete_session(self, event_id: str, numero_orden: int) -> Optional[EventResponse]:
        evento = await Event.find_one(Event.event_id == int(event_id))
        if not evento:
            return None

        antes = len(evento.sesiones)
        evento.sesiones = [s for s in evento.sesiones if s.numero_orden != numero_orden]

        if len(evento.sesiones) == antes:
            raise HTTPException(status_code=404, detail="Esa sesión no existe")

        # Los números no se recalculan a propósito. Si se borra Practice 1
        # de TCR, la que era Practice 2 sigue siéndolo: renumerarla haría
        # que un gráfico ya emitido dejara de corresponder con la lista.

        await evento.save()
        return await self._to_response(evento)

    # ── Imagen del evento ─────────────────────────────────────────────

    async def _evento(self, event_id: int) -> Event:
        evento = await Event.find_one(Event.event_id == event_id)
        if evento is None:
            raise HTTPException(404, f"No existe el evento {event_id}")
        return evento

    async def _asignar_imagen(self, evento: Event, destino: Path) -> EventResponse:
        anterior = (CARPETA_IMAGENES / evento.image) if evento.image else None

        evento.image = destino.name
        await evento.save()

        borrar_si_sobra(anterior, destino)

        return await self._to_response(evento)

    async def subir_imagen(self, event_id: int, nombre: str, contenido: bytes) -> EventResponse:
        """La que llega desde el navegador."""
        evento = await self._evento(event_id)

        # El archivo se llama como el id y no como el evento: renombrar un
        # evento no debe dejar la imagen huérfana.
        destino = guardar_bytes(contenido, nombre, CARPETA_IMAGENES / str(event_id))

        return await self._asignar_imagen(evento, destino)

    async def imagen_por_ruta(self, event_id: int, ruta: str) -> EventResponse:
        """La que ya está en el disco del servidor."""
        evento = await self._evento(event_id)

        destino = copiar_de_ruta(ruta, CARPETA_IMAGENES / str(event_id))

        return await self._asignar_imagen(evento, destino)

    async def borrar_imagen(self, event_id: int) -> EventResponse:
        evento = await self._evento(event_id)

        if evento.image:
            fichero = CARPETA_IMAGENES / evento.image
            evento.image = None
            await evento.save()
            borrar_si_sobra(fichero, CARPETA_IMAGENES / "__ninguno__")

        return await self._to_response(evento)

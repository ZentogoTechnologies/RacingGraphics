from typing import Optional

from beanie.operators import In
from src.models.vehicles_model import Vehicle
from src.models.pilots_model import Pilot
from pathlib import Path

from src.models.categories_model import Category
from src.services.imagenes_services import (
    borrar_si_sobra, copiar_de_ruta, guardar_bytes,
)
from src.schemas.vehicles_schemas import VehicleCreate, VehicleUpdate, VehicleResponse
from src.schemas.common_schemas import Page
from src.services.pagination import (
    campo_orden, combinar, direccion, filtro_busqueda,
)
from fastapi import HTTPException

# Backend/src/public/vehiculos, mirando desde Backend/src/services.
CARPETA_FOTOS = Path(__file__).resolve().parents[1] / "public" / "vehiculos"

RUTA_RELATIVA = "vehiculos"

# Cuántas caben por carro. Dos: una de frente y una de perfil, que es lo
# que usan los gráficos. Dejarlo abierto solo llenaba la carpeta de fotos
# que nadie llega a sacar al aire.
TOPE_FOTOS = 2


def url_foto_vehiculo(archivo: str) -> str:
    """La ruta con la que el navegador y CasparCG piden la imagen."""
    return f"/public/{RUTA_RELATIVA}/{archivo}"


class VehicleService:
    async def _build_response(self, vehicle: Vehicle) -> VehicleResponse:
        await vehicle.fetch_all_links() # resuelve pilots
        category = await Category.find_one(Category.category_id == vehicle.category_id)

        pilots_data = []
        for p in vehicle.pilots:
            pilots_data.append({
                "pilot_id": p.pilot_id,
                "name": f"{p.name} {p.last_name}",
                "team_brand": p.team_brand
            })

        sub_name = None
        cat_name = category.category_name if category else None
        if category and vehicle.sub_category_id:
            sub = next((sc for sc in category.sub_categories if sc.sub_category_id == vehicle.sub_category_id), None)
            sub_name = sub.sub_category_name if sub else None

        return VehicleResponse(
            id=str(vehicle.id),
            vehicle_id=vehicle.vehicle_id,
            number=vehicle.number,
            # Sin dorsal en pantalla se usa el numero; sin ninguno de los
            # dos se queda vacio en vez de poner "None" al aire.
            display_number=(
                vehicle.display_number
                or (str(vehicle.number) if vehicle.number is not None else None)
            ),
            brand=vehicle.brand,
            model=vehicle.model,
            color=vehicle.color,
            photos=vehicle.photos or [],
            photo_urls=[url_foto_vehiculo(f) for f in (vehicle.photos or [])],
            pilots=pilots_data,
            active_pilot_id=vehicle.active_pilot_id,
            category_id=vehicle.category_id,
            category_name=cat_name,
            sub_category_id=vehicle.sub_category_id,
            sub_category_name=sub_name,
            is_active=vehicle.is_active
        )

    async def _siguiente_id(self) -> int:
        """El id más alto que hay, más uno. Mismo motivo que en pilotos:
        dos altas a la vez verían el mismo hueco libre."""
        ultimo = await Vehicle.find_all().sort(("vehicle_id", -1)).limit(1).to_list()
        return (ultimo[0].vehicle_id + 1) if ultimo else 1

    async def create_vehicle(self, data: VehicleCreate) -> VehicleResponse:
        # 0. El id lo pone el servicio salvo que venga escrito.
        if data.vehicle_id is None:
            data.vehicle_id = await self._siguiente_id()
        else:
            existe = await Vehicle.find_one(Vehicle.vehicle_id == data.vehicle_id)
            if existe:
                raise HTTPException(status_code=400, detail="vehicle_id ya existe")

        # 1. Validar max 2 pilotos
        if len(data.pilot_ids) > 2:
            raise HTTPException(status_code=400, detail="Un vehículo solo puede tener máximo 2 pilotos")

        # 2. Validar que la categoría exista
        category = await Category.find_one(Category.category_id == data.category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")

        # 3. Validar que la sub_category exista dentro de esa category
        if data.sub_category_id:
            sub_exists = any(sc.sub_category_id == data.sub_category_id for sc in category.sub_categories)
            if not sub_exists:
                raise HTTPException(status_code=400, detail=f"sub_category_id {data.sub_category_id} no pertenece a category {data.category_id}")

        # 4. Buscar los pilotos y convertirlos a Link
        pilots_links = []
        for pid in data.pilot_ids:
            pilot = await Pilot.find_one(Pilot.pilot_id == pid)
            if not pilot:
                raise HTTPException(status_code=404, detail=f"Piloto con id {pid} no encontrado")
            pilots_links.append(pilot)

        campos = data.model_dump(exclude={"pilot_ids"})
        # Sin dorsal escrito se asume que es el entero. Solo se separa
        # cuando el carro lleva ceros a la izquierda ('044' != '44').
        if not campos.get("display_number"):
            campos["display_number"] = str(campos["number"])

        vehicle = Vehicle(**campos, pilots=pilots_links)
        await vehicle.insert()
        return await self._build_response(vehicle)

    ORDENABLES = {"vehicle_id", "number", "brand", "model", "category_id"}
    BUSCABLES = ["brand", "model", "display_number", "color"]

    async def get_all_vehicles(
        self,
        discipline: Optional[str] = None,
        category_id: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: Optional[str] = None,
        skip: int = 0,
        limit: Optional[int] = None,
        sub_category_id: Optional[str] = None,
        pilot: Optional[str] = None,
        pilot_id: Optional[int] = None,
    ) -> Page[VehicleResponse]:
        filtros = [filtro_busqueda(search, self.BUSCABLES)]

        # La disciplina vive en la categoría, no en el vehículo, así que se
        # resuelve a la lista de categorías que le pertenecen.
        ids_disciplina = None
        if discipline:
            categorias = await Category.find(Category.discipline == discipline).to_list()
            ids_disciplina = [c.category_id for c in categorias]

        # Antes esto era un elif de la disciplina, y como el frontend manda
        # siempre la disciplina, elegir una categoría no filtraba nada: la
        # rama no llegaba a ejecutarse. Ahora se aplican los dos.
        if category_id:
            cid = int(category_id)

            # Una categoría que no es de esta disciplina no puede tener
            # vehículos que cumplan las dos condiciones.
            if ids_disciplina is not None and cid not in ids_disciplina:
                return Page(items=[], total=0, skip=skip, limit=limit)

            filtros.append({"category_id": cid})

        elif ids_disciplina is not None:
            filtros.append({"category_id": {"$in": ids_disciplina}})

        if sub_category_id:
            filtros.append({"sub_category_id": int(sub_category_id)})

        # Por nombre de piloto. Se resuelven primero los pilotos que
        # coinciden y se filtra por sus referencias: el vehículo guarda
        # DBRefs, no nombres, así que no se puede buscar en él directamente.
        if pilot and pilot.strip():
            encontrados = await Pilot.find(
                filtro_busqueda(pilot, ["name", "last_name"])
            ).to_list()

            if not encontrados:
                return Page(items=[], total=0, skip=skip, limit=limit)

            filtros.append({"pilots.$id": {"$in": [p.id for p in encontrados]}})

        # Por id, exacto. El filtro `pilot` de arriba busca por nombre y
        # sirve para la caja de búsqueda, pero para la ficha de un piloto
        # concreto no vale: dos corredores pueden compartir apellido y
        # saldrían los carros de los dos.
        if pilot_id is not None:
            corredor = await Pilot.find_one(Pilot.pilot_id == int(pilot_id))
            if corredor is None:
                return Page(items=[], total=0, skip=skip, limit=limit)
            filtros.append({"pilots.$id": corredor.id})

        query = combinar(*filtros)

        total = await Vehicle.find(query).count()

        consulta = Vehicle.find(query).sort(
            (campo_orden(sort_by, self.ORDENABLES, "number"), direccion(sort_dir))
        ).skip(skip)

        if limit is not None:
            consulta = consulta.limit(limit)

        vehicles = await consulta.to_list()

        return Page(
            items=[await self._build_response(v) for v in vehicles],
            total=total,
            skip=skip,
            limit=limit,
        )

    async def get_vehicle_by_id(self, vehicle_id: str) -> VehicleResponse: # <- str
        vehicle = await Vehicle.find_one(Vehicle.vehicle_id == int(vehicle_id)) # <- int
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")
        return await self._build_response(vehicle)

    async def update_vehicle(self, vehicle_id: str, data: VehicleUpdate) -> VehicleResponse: # <- FALTABA ESTE MÉTODO
        vehicle = await Vehicle.find_one(Vehicle.vehicle_id == int(vehicle_id))
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")

        update_data = data.model_dump(exclude_unset=True)

        # Si cambian pilotos
        if "pilot_ids" in update_data:
            if len(update_data["pilot_ids"]) > 2:
                raise HTTPException(status_code=400, detail="Un vehículo solo puede tener máximo 2 pilotos")
            pilots_links = []
            for pid in update_data["pilot_ids"]:
                pilot = await Pilot.find_one(Pilot.pilot_id == pid)
                if not pilot:
                    raise HTTPException(status_code=404, detail=f"Piloto con id {pid} no encontrado")
                pilots_links.append(pilot)
            update_data["pilots"] = pilots_links
            del update_data["pilot_ids"]

        # Si cambian category o sub_category validar
        if "category_id" in update_data or "sub_category_id" in update_data:
            cat_id = update_data.get("category_id", vehicle.category_id)
            sub_id = update_data.get("sub_category_id", vehicle.sub_category_id)
            category = await Category.find_one(Category.category_id == cat_id)
            if not category:
                raise HTTPException(status_code=404, detail="Categoría no encontrada")
            if sub_id:
                sub_exists = any(sc.sub_category_id == sub_id for sc in category.sub_categories)
                if not sub_exists:
                    raise HTTPException(status_code=400, detail=f"sub_category_id {sub_id} no pertenece a category {cat_id}")

        for campo, valor in update_data.items():
            setattr(vehicle, campo, valor)

        # save() y no update({"$set": ...}): solo al guardar el documento
        # Beanie convierte los Document en Link. Con $set se incrustaba el
        # documento completo y la relacion se perdia.
        await vehicle.save()
        return await self._build_response(vehicle)

    async def delete_vehicle(self, vehicle_id: str) -> dict: # <- FALTABA ESTE MÉTODO
        vehicle = await Vehicle.find_one(Vehicle.vehicle_id == int(vehicle_id))
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")
        await vehicle.delete()
        return {"detail": "Vehículo eliminado"}

    # ── Fotos ─────────────────────────────────────────────────────────

    async def _obtener(self, vehicle_id: str) -> Vehicle:
        vehicle = await Vehicle.find_one(Vehicle.vehicle_id == int(vehicle_id))
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehículo no encontrado")
        return vehicle

    def _hueco_libre(self, vehicle: Vehicle) -> int:
        """El primer número de foto que no está ocupado.

        Se busca hueco en vez de contar: al borrar la primera de dos, la
        siguiente que suba debe volver a ocupar ese sitio y no llamarse
        como la que ya existe.
        """
        usados = set()
        for archivo in vehicle.photos or []:
            trozo = Path(archivo).stem.rsplit("-", 1)[-1]
            if trozo.isdigit():
                usados.add(int(trozo))

        for n in range(1, TOPE_FOTOS + 1):
            if n not in usados:
                return n

        raise HTTPException(
            400, f"Un vehículo admite hasta {TOPE_FOTOS} fotos. Borra una antes.")

    async def _añadir(self, vehicle: Vehicle, destino: Path) -> VehicleResponse:
        if destino.name not in (vehicle.photos or []):
            vehicle.photos = [*(vehicle.photos or []), destino.name]
            await vehicle.save()
        return await self._build_response(vehicle)

    async def subir_foto(self, vehicle_id: str, nombre: str, contenido: bytes) -> VehicleResponse:
        vehicle = await self._obtener(vehicle_id)

        if len(vehicle.photos or []) >= TOPE_FOTOS:
            raise HTTPException(
                400, f"Un vehículo admite hasta {TOPE_FOTOS} fotos. Borra una antes.")

        base = CARPETA_FOTOS / f"{vehicle.vehicle_id}-{self._hueco_libre(vehicle)}"
        destino = guardar_bytes(contenido, nombre, base)

        return await self._añadir(vehicle, destino)

    async def foto_por_ruta(self, vehicle_id: str, ruta: str) -> VehicleResponse:
        vehicle = await self._obtener(vehicle_id)

        if len(vehicle.photos or []) >= TOPE_FOTOS:
            raise HTTPException(
                400, f"Un vehículo admite hasta {TOPE_FOTOS} fotos. Borra una antes.")

        base = CARPETA_FOTOS / f"{vehicle.vehicle_id}-{self._hueco_libre(vehicle)}"
        destino = copiar_de_ruta(ruta, base)

        return await self._añadir(vehicle, destino)

    async def quitar_fondo(self, vehicle_id: str, archivo: str) -> VehicleResponse:
        """Recorta el carro de su fondo y reemplaza esa foto.

        Se le pasa cuál de las dos, porque un carro tiene varias y hay que
        decir a cuál. Por lo demás funciona igual que en pilotos: trabaja
        sobre el archivo ya guardado y devuelve PNG, que es lo único que
        admite transparencia.
        """
        vehicle = await self._obtener(vehicle_id)

        if archivo not in (vehicle.photos or []):
            raise HTTPException(404, "Esa foto no es de este vehículo")

        actual = CARPETA_FOTOS / archivo
        if not actual.is_file():
            raise HTTPException(400, "El archivo de la foto no está en el disco")

        from src.services.recorte_services import quitar_fondo as recortar

        try:
            # El modelo general y no el de personas: delante de un carro,
            # el entrenado con gente no sabe qué mirar.
            recortada = recortar(actual.read_bytes(), sujeto="objeto")
        except Exception as e:
            raise HTTPException(422, f"No se pudo quitar el fondo: {e}")

        # Se conserva el hueco que ocupaba —el "-1" o el "-2"— para que la
        # foto siga siendo la misma de la lista y no salte de sitio.
        base = CARPETA_FOTOS / Path(archivo).stem
        destino = guardar_bytes(recortada, "foto.png", base)

        vehicle.photos = [destino.name if f == archivo else f
                          for f in (vehicle.photos or [])]
        await vehicle.save()

        # El original solo se borra si el recorte quedó en otro archivo:
        # con la misma extensión se acaba de sobrescribir.
        if destino.name != archivo and actual.is_file():
            actual.unlink()

        return await self._build_response(vehicle)

    async def borrar_foto(self, vehicle_id: str, archivo: str) -> VehicleResponse:
        vehicle = await self._obtener(vehicle_id)

        if archivo not in (vehicle.photos or []):
            raise HTTPException(404, f"El vehículo no tiene la foto {archivo}")

        vehicle.photos = [f for f in vehicle.photos if f != archivo]
        await vehicle.save()

        borrar_si_sobra(CARPETA_FOTOS / archivo, CARPETA_FOTOS / "__ninguno__")

        return await self._build_response(vehicle)

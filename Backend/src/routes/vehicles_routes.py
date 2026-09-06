from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from typing import Optional
from src.services.vehicles_services import VehicleService
from src.schemas.vehicles_schemas import VehicleCreate, VehicleUpdate, VehicleResponse
from src.schemas.common_schemas import Page
from src.services.auth_services import puede_escribir

vehicles = APIRouter()
service = VehicleService()

@vehicles.get("/", tags=["Vehicles"], response_model=Page[VehicleResponse])
async def get_vehicles(
    discipline: Optional[str] = Query(None, description="Filtrar por disciplina: circuito o drag"),
    sub_category_id: Optional[str] = Query(None, description="Filtrar por subcategoría dentro de la categoría"),
    pilot: Optional[str] = Query(None, description="Nombre o apellido del piloto, parcial"),
    pilot_id: Optional[int] = Query(None, description="Los carros de ese piloto, exacto"),
    category_id: Optional[str] = Query(None, description="Filtrar por category_id"), # <- str no int
    search: Optional[str] = Query(None, description="Búsqueda parcial, sin distinguir mayúsculas"),
    sort_by: Optional[str] = Query(None, description="Campo por el que ordenar"),
    sort_dir: Optional[str] = Query("asc", description="asc o desc"),
    skip: int = Query(0, ge=0, description="Cuántos registros saltar"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Tamaño de página. Sin valor devuelve todo"),
):
    """
    Obtiene los vehículos paginados.
    Devuelve pilotos, category_name y sub_category_name resueltos.
    Ordena por: vehicle_id, number, brand, model, category_id
    """
    return await service.get_all_vehicles(
        discipline=discipline, category_id=category_id, search=search,
        sort_by=sort_by, sort_dir=sort_dir, skip=skip, limit=limit,
        sub_category_id=sub_category_id, pilot=pilot, pilot_id=pilot_id,
    )

@vehicles.post("/", tags=["Vehicles"], response_model=VehicleResponse, status_code=201, dependencies=[Depends(puede_escribir)])
async def create_vehicle(data: VehicleCreate):
    """
    Crea un vehículo nuevo.
    Valida: max 2 pilotos, category existe, sub_category pertenece a category
    """
    return await service.create_vehicle(data)

@vehicles.get("/{vehicle_id}", tags=["Vehicles"], response_model=VehicleResponse)
async def get_vehicle_by_id(vehicle_id: str): # <- str no int
    """
    Obtiene un vehículo por vehicle_id con toda la info resuelta
    """
    vehicle = await service.get_vehicle_by_id(vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return vehicle

@vehicles.put("/{vehicle_id}", tags=["Vehicles"], response_model=VehicleResponse, dependencies=[Depends(puede_escribir)])
async def update_vehicle(vehicle_id: str, data: VehicleUpdate): # <- str no int
    """
    Actualiza un vehículo.
    Si cambias pilotos o category, vuelve a validar todo
    """
    vehicle = await service.update_vehicle(vehicle_id, data)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return vehicle

@vehicles.delete("/{vehicle_id}", tags=["Vehicles"], dependencies=[Depends(puede_escribir)])
async def delete_vehicle(vehicle_id: str): # <- str no int
    """
    Elimina un vehículo
    """
    deleted = await service.delete_vehicle(vehicle_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return {"message": "Vehículo eliminado"}


# ======================================================================
#  FOTOS
#
#  Hasta cuatro por carro, en orden. Cuál sale al aire se decide al
#  graficar —la grilla puede querer una y la ficha del piloto otra—, así
#  que aquí solo se guardan y se listan.
# ======================================================================


class RutaFotoVehiculo(BaseModel):
    ruta: str


@vehicles.post("/{vehicle_id}/fotos", tags=["Vehicles"], response_model=VehicleResponse,
               dependencies=[Depends(puede_escribir)])
async def subir_foto_vehiculo(vehicle_id: str, archivo: UploadFile = File(...)):
    """
    Añade una foto del vehículo desde el navegador
    """
    contenido = await archivo.read()
    return await service.subir_foto(vehicle_id, archivo.filename or "", contenido)


@vehicles.put("/{vehicle_id}/fotos", tags=["Vehicles"], response_model=VehicleResponse,
              dependencies=[Depends(puede_escribir)])
async def foto_vehiculo_por_ruta(vehicle_id: str, datos: RutaFotoVehiculo):
    """
    Toma una foto de una ruta del servidor y la copia a public/vehiculos
    """
    return await service.foto_por_ruta(vehicle_id, datos.ruta)


@vehicles.post("/{vehicle_id}/fotos/{archivo}/sin-fondo", tags=["Vehicles"],
               response_model=VehicleResponse,
               dependencies=[Depends(puede_escribir)])
async def quitar_fondo_vehiculo(vehicle_id: str, archivo: str):
    """
    Recorta el carro de su fondo y reemplaza esa foto.

    Hay que decir cuál de las dos: se pasa el nombre del archivo.
    """
    return await service.quitar_fondo(vehicle_id, archivo)


@vehicles.delete("/{vehicle_id}/fotos/{archivo}", tags=["Vehicles"], response_model=VehicleResponse,
                 dependencies=[Depends(puede_escribir)])
async def borrar_foto_vehiculo(vehicle_id: str, archivo: str):
    """
    Quita una de las fotos del vehículo
    """
    return await service.borrar_foto(vehicle_id, archivo)

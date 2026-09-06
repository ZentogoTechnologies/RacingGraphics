from pydantic import BaseModel, Field, validator
from typing import Optional, List

class VehicleCreate(BaseModel):
    # Opcional: lo pone el servicio. `number` es el dorsal de carrera y ese
    # sí lo escribe quien inscribe; este es solo la clave interna.
    vehicle_id: Optional[int] = None
    # Sin dorsal se puede: en drag no todos los carros llevan numero.
    number: Optional[int] = None
    display_number: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None

    pilot_ids: List[int] = [] # Recibimos hasta 2 IDs. En service validamos max 2
    category_id: int
    sub_category_id: Optional[int] = None

    @validator('pilot_ids')
    def max_two_pilots(cls, v):
        if len(v) > 2:
            raise ValueError('Un vehículo no puede tener más de 2 pilotos')
        return v

class VehicleUpdate(BaseModel):
    number: Optional[int] = None
    display_number: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    pilot_ids: Optional[List[int]] = None
    category_id: Optional[int] = None
    sub_category_id: Optional[int] = None

class VehicleResponse(BaseModel):
    id: str = Field(alias="_id")
    vehicle_id: int
    number: Optional[int] = None
    display_number: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None

    photos: List[str] = []        # nombres de archivo, en orden
    photo_urls: List[str] = []    # las mismas, ya resueltas para <img>

    pilots: List[dict] = [] # [{"pilot_id": 1, "name": "Juan", "team_brand": "Zentogo"}]
    active_pilot_id: Optional[int] = None
    category_id: int
    category_name: Optional[str] = None
    sub_category_id: Optional[int] = None
    sub_category_name: Optional[str] = None

    is_active: bool

    class Config:
        populate_by_name = True
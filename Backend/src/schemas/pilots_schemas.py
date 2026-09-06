from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

from src.services.settings_services import PAISES_CON_BANDERA


def _pais(valor: Optional[str]) -> Optional[str]:
    """La nacionalidad es un codigo ISO 3166-1 alfa-2, en minusculas.

    Se guarda el codigo y no el nombre porque el nombre cambia con el
    idioma y se escribe de varias maneras —"Panama", "Panama", "PANAMA"—,
    y asi cada variante era un pais distinto. El codigo ademas es el
    nombre del archivo de la bandera.

    Se valida contra las banderas que hay en disco: un codigo sin bandera
    saldria al aire como una imagen rota.
    """
    if valor is None or valor == "":
        return None

    codigo = valor.strip().lower()
    if codigo not in PAISES_CON_BANDERA:
        raise ValueError(
            f"'{valor}' no es un pais reconocido. Se espera el codigo de dos "
            "letras, por ejemplo 'pa'."
        )
    return codigo

class PilotCreate(BaseModel):
    # Opcional: lo normal es que lo ponga el servicio. Se sigue aceptando
    # escrito para poder importar datos conservando su numeración.
    pilot_id: Optional[int] = None
    name: str
    last_name: str
    nationality: Optional[str] = None
    team_brand: Optional[str] = None # "Zentogo Racing"
    photo: Optional[str] = None # ruta dentro de public/, ej "pilotos/prospec-series/1.png"
    category_ids: List[int] = [] # Recibimos IDs. En el service buscamos Category y hacemos Link
    discipline: List[str] = [] # ["circuito", "drag"]

    _valida_pais = field_validator("nationality")(_pais)

class PilotUpdate(BaseModel):
    name: Optional[str] = None
    last_name: Optional[str] = None
    nationality: Optional[str] = None
    team_brand: Optional[str] = None
    photo: Optional[str] = None
    category_ids: Optional[List[int]] = None
    discipline: Optional[List[str]] = None

    # Se da de baja en vez de borrarlo: un piloto que dejó de correr sigue
    # apareciendo en los resultados de las tandas que ya se disputaron.
    is_active: Optional[bool] = None

    _valida_pais = field_validator("nationality")(_pais)

class PilotResponse(BaseModel):
    id: str = Field(alias="_id")
    pilot_id: int
    name: str
    last_name: str
    nationality: Optional[str] = None
    team_brand: Optional[str] = None
    photo: Optional[str] = None
    categories: List[int] = [] # Aquí devolvemos solo los category_id para no hacer fetch pesado
    discipline: List[str] = []
    is_active: bool

    class Config:
        populate_by_name = True
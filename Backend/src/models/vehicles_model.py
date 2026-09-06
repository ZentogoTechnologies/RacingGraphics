from beanie import Document, Link
from typing import Optional, List
from src.models.pilots_model import Pilot

class Vehicle(Document):
    vehicle_id: int
    # Opcional: en drag no siempre hay dorsal. Se corre por parejas, el
    # cronometraje va por carril y muchos carros no llevan numero pintado.
    # En circuito si lo hay siempre, y es el formulario quien lo exige.
    number: Optional[int] = None # dorsal, como numero: 44
    display_number: Optional[str] = None
    # El dorsal tal cual esta pintado en el carro. No es cosmetico: los
    # ceros a la izquierda distinguen carros distintos ('44' es K. King y
    # '044' es Obed Barrios), y MyLaps los manda asi. Sin esto los dos
    # colapsan en el mismo entero y sale el nombre equivocado al aire.
    brand: Optional[str] = None # Marca del carro/moto: "Porsche", "Yamaha"
    model: Optional[str] = None # "911 GT3 Cup", "R1"
    color: Optional[str] = None

    # Fotos del carro, en orden. Solo el nombre del archivo; viven en
    # public/vehiculos. Es una lista y no dos campos con nombre porque
    # cuál se saca al aire se decide al graficar, no al subirla: la grilla
    # puede querer una y la ficha del piloto otra.
    photos: List[str] = []

    pilots: List[Link[Pilot]] = [] # Hasta 2 pilotos. Sin principal
    active_pilot_id: Optional[int] = None # Cuál de los dos va manejando ahora mismo.
                                          # MyLaps no lo distingue: manda los dos nombres pegados.
    category_id: int
    sub_category_id: Optional[int] = None

    is_active: bool = True

    class Settings:
        name = "vehicles"
        indexes = [
            "vehicle_id",
            "number",
            "display_number",
            "category_id"
        ]
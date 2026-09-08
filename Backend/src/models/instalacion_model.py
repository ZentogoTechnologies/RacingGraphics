"""Datos de esta instalación concreta.

Race Core Studio se vende a autódromos de cualquier parte, así que nada
de lo que identifica a un cliente puede estar escrito en el código: ni el
nombre, ni el logo, ni el país, ni las coordenadas del circuito. Todo eso
vive aquí y lo llena el asistente web al instalar.

Es un documento único: solo existe una instalación por base de datos.
"""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

# El asistente en orden. El estado guarda en cuál se quedó, para que
# cerrar el navegador a media instalación no obligue a empezar de nuevo.
PASOS = [
    "bienvenida",
    "organizacion",
    "logo",
    "usuarios",
    "cronometraje",
    "casparcg",
    "clima",
    "listo",
]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Instalacion(Document):
    # Solo hay una. El id fijo evita que dos peticiones a la vez creen
    # dos documentos y el sistema acabe con dos configuraciones.
    clave: str = "instalacion"

    completada: bool = False
    paso: str = "bienvenida"
    creada: str = Field(default_factory=ahora)
    completada_en: Optional[str] = None

    # ── Quién es el cliente ──────────────────────────────────
    # Lo que sale al aire y lo que se ve en el panel. Vacío de fábrica:
    # el producto no viene con el nombre de nadie puesto.
    organizacion: str = ""
    pais: str = ""
    ciudad: str = ""

    # Nombre del circuito, que puede no coincidir con el de la
    # organización: un autódromo con varios trazados los nombra distinto.
    circuito: str = ""

    # ── Clima ────────────────────────────────────────────────
    # Coordenadas del circuito. Sin esto la plantilla de clima no puede
    # decir nada, y con esto puesto a mano en el código solo servía para
    # un cliente.
    lat: Optional[float] = None
    lon: Optional[float] = None

    # ── Preferencias ─────────────────────────────────────────
    idioma: str = "es"
    zona_horaria: str = "UTC"

    class Settings:
        name = "instalacion"
        indexes = [IndexModel([("clave", ASCENDING)], unique=True)]

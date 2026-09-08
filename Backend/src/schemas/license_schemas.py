from typing import Optional

from pydantic import BaseModel, Field


class EstadoLicencia(BaseModel):
    """Lo que el panel enseña en Ajustes → Licencia."""

    estado: str
    opera: bool
    mensaje: str
    cliente: Optional[str] = None
    correo: Optional[str] = None
    producto: Optional[str] = None
    plan: Optional[str] = None
    features: list[str] = Field(default_factory=list)
    version_max: Optional[str] = None
    vence: Optional[str] = None
    dias_restantes: Optional[int] = None
    gracia_dias: int = 0
    dias_de_gracia_restantes: Optional[int] = None


class SaludLicencia(BaseModel):
    """Versión mínima del estado, sin datos del cliente.

    La consulta el servicio de vigilancia y la pantalla de bloqueo, que
    necesitan saber si se puede operar pero no tienen por qué conocer a
    nombre de quién está la licencia.
    """

    estado: str
    opera: bool


class Equipo(BaseModel):
    """La huella de esta máquina, que es lo que se manda a Zentogo para
    que emita o reasigne una licencia."""

    huella: str
    producto: str


class ActivarLicencia(BaseModel):
    token: str = Field(..., min_length=32, description="Token emitido por Zentogo")

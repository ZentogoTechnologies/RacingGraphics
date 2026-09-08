import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Nombre de usuario: letras, números, punto, guion y guion bajo. Sin
# espacios ni acentos, porque se teclea a diario en una consola y en
# medio de una transmisión.
PATRON_USUARIO = re.compile(r"^[A-Za-z0-9._-]{3,32}$")


class Organizacion(BaseModel):
    """Quién es el cliente. Nada de esto trae valor de fábrica."""

    organizacion: str = Field(..., min_length=2, max_length=120,
                              description="Autódromo, club o promotora")
    circuito: str = Field("", max_length=120,
                          description="Nombre de la pista, si difiere")
    pais: str = Field(..., min_length=2, max_length=60)
    ciudad: str = Field("", max_length=80)
    idioma: str = Field("es", pattern="^(es|en)$")
    zona_horaria: str = Field("UTC", max_length=64)

    @field_validator("organizacion", "circuito", "pais", "ciudad")
    @classmethod
    def limpiar(cls, v: str) -> str:
        return " ".join(v.split())


class CuentaNueva(BaseModel):
    username: str
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def usuario_valido(cls, v: str) -> str:
        v = v.strip()
        if not PATRON_USUARIO.match(v):
            raise ValueError(
                "El usuario admite letras, números, punto, guion y guion bajo, "
                "entre 3 y 32 caracteres, sin espacios."
            )
        return v


class DatosUsuarios(BaseModel):
    """Las tres cuentas, obligatorias en la instalación.

    Se exigen las tres a propósito. Con solo el dueño creado, todo el
    mundo acabaría operando con esa cuenta —es la única que hay— y la
    separación de roles quedaría de adorno: el operador que solo debe
    sacar gráficos podría borrar pilotos, y no habría forma de saber quién
    hizo qué. Creándolas aquí, el reparto existe desde el primer día y no
    depende de que alguien se acuerde después.

        owner     administra cuentas. Uno solo, y no se crea desde el panel.
        admin     escribe en la base: pilotos, vehículos, eventos.
        standard  opera los gráficos, pero no modifica registros.
    """

    owner: CuentaNueva
    admin: CuentaNueva
    standard: CuentaNueva

    @model_validator(mode="after")
    def distintos(self) -> "DatosUsuarios":
        nombres = [self.owner.username.lower(),
                   self.admin.username.lower(),
                   self.standard.username.lower()]

        if len(set(nombres)) != 3:
            raise ValueError("Los tres usuarios deben tener nombres distintos.")

        claves = {self.owner.password, self.admin.password, self.standard.password}
        if len(claves) != 3:
            raise ValueError(
                "Cada cuenta necesita su propia contraseña. Repetirlas hace "
                "que los roles no separen nada."
            )

        return self


class RutaTiming(BaseModel):
    ruta: str = Field(..., min_length=1, max_length=500,
                      description=r"Ruta del current.xml. UNC: \\servidor\recurso")


class TextoUbicacion(BaseModel):
    """Lo que el cliente escriba o pegue: coordenadas, o un enlace de mapa."""

    texto: str = Field(..., min_length=1, max_length=600)


class Clima(BaseModel):
    """Coordenadas del circuito, para la plantilla del clima."""

    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)

    # Los devuelve el buscador junto con las coordenadas, así que se
    # aprovechan en vez de volver a preguntarlos.
    ciudad: Optional[str] = Field(None, max_length=80)
    zona_horaria: Optional[str] = Field(None, max_length=64)


class EstadoInstalacion(BaseModel):
    configurado: bool
    asistente_disponible: bool
    paso: str
    pasos: list[str]
    organizacion: str
    version: str

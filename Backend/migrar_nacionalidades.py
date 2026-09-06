"""
Pasa la nacionalidad de los pilotos de nombre escrito a mano a código ISO.

Antes el campo era texto libre y en la base convivían "Panama", "Panamá" y
"PANAMA" como si fueran tres países. Con el código guardado hay uno solo, y
además tiene bandera: el archivo se llama igual que el código.

Se ejecuta una vez y es idempotente: lo que ya es un código de dos letras
se deja como está.

    python migrar_nacionalidades.py            # dice qué haría
    python migrar_nacionalidades.py --aplicar  # lo hace

Lo que no sepa traducir lo deja intacto y lo lista al final, para revisarlo
a mano en vez de perderlo.
"""

import asyncio
import json
import re
import sys
import unicodedata
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

from config import settings

# La tabla de países vive en el panel, que es quien la enseña. Se lee de
# ahí en vez de copiarla: dos listas se separan en cuanto se toca una.
TABLA = Path(__file__).parent.parent / "Frontend" / "src" / "data" / "paises.js"

# Nacionalidades escritas de una manera que ninguna tabla recoge.
ALIAS = {
    "eeuu": "us",
    "usa": "us",
    "estados unidos de america": "us",
    "inglaterra": "gb",
    "rusia": "ru",
}


def sin_tildes(texto: str) -> str:
    limpio = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in limpio if unicodedata.category(c) != "Mn").lower().strip()


def cargar_tabla() -> dict:
    """Los pares [codigo, nombre_es, nombre_en] del módulo del panel."""
    fuente = TABLA.read_text(encoding="utf-8")
    indice = {}
    for codigo, es, en in json.loads(
        "[" + ",".join(re.findall(r'\["[a-z]{2}",".*?",".*?"\]', fuente)) + "]"
    ):
        indice[sin_tildes(es)] = codigo
        indice[sin_tildes(en)] = codigo
    indice.update(ALIAS)
    return indice


def codigo_de(valor: str, indice: dict):
    """El código de un país escrito a mano, o None si no se reconoce."""
    if not valor:
        return None

    crudo = sin_tildes(valor)
    if len(crudo) == 2 and crudo in {c for c in indice.values()}:
        return crudo  # ya migrado

    if crudo in indice:
        return indice[crudo]

    # "Panama-España", "China-Panama": se queda la primera. Son dos casos
    # en toda la base y quedan listados para que alguien decida.
    primera = sin_tildes(re.split(r"[-/]", valor)[0])
    return indice.get(primera)


async def main(aplicar: bool):
    indice = cargar_tabla()
    cliente = AsyncIOMotorClient(settings.MONGO_URI)
    pilotos = cliente[settings.DB_NAME]["pilots"]

    cambios, dobles, sin_mapa, ya_estaban = [], [], [], 0

    async for p in pilotos.find({}, {"pilot_id": 1, "name": 1, "last_name": 1, "nationality": 1}):
        valor = p.get("nationality")
        if not valor:
            continue

        codigo = codigo_de(valor, indice)
        if codigo is None:
            sin_mapa.append((p.get("pilot_id"), valor))
            continue
        if codigo == valor:
            ya_estaban += 1
            continue

        if re.search(r"[-/]", valor):
            dobles.append((p.get("pilot_id"), f"{p.get('name')} {p.get('last_name')}", valor, codigo))

        cambios.append((p["_id"], codigo))

    print(f"{len(cambios)} por cambiar, {ya_estaban} ya en código, {len(sin_mapa)} sin traducir")

    if dobles:
        print("\nDoble nacionalidad, se queda la primera. Revísalos:")
        for pid, nombre, valor, codigo in dobles:
            print(f"  #{pid} {nombre}: {valor} -> {codigo}")

    if sin_mapa:
        print("\nSin traducir, se dejan como estaban:")
        for pid, valor in sin_mapa:
            print(f"  #{pid} {valor!r}")

    if not aplicar:
        print("\nEn seco. Vuelve a llamarlo con --aplicar para escribir.")
        return

    for _id, codigo in cambios:
        await pilotos.update_one({"_id": _id}, {"$set": {"nationality": codigo}})
    print(f"\n{len(cambios)} pilotos actualizados.")


if __name__ == "__main__":
    asyncio.run(main("--aplicar" in sys.argv))

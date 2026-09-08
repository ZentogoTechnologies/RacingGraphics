"""Trazados de pista: alta, imagen y cuál está activo.

La imagen acaba siempre dentro de la plantilla de CasparCG, se haya subido
desde el navegador o escrito su ruta en el servidor. Es a propósito: la
plantilla se abre con file:// y una imagen suelta en otro disco puede no
resolverse, además de perderse si alguien mueve la carpeta.
"""

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from src.models.tracks_model import Trazado

# Backend/src/public/circuit-image, mirando desde Backend/src/services.
# Las imágenes viven con el resto del material del cliente —fotos de
# pilotos, logos de marcas— y no dentro de la carpeta de CasparCG.
RAIZ = Path(__file__).resolve().parents[3]
CARPETA_IMAGENES = RAIZ / "Backend" / "src" / "public" / "circuit-image"

EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

# Un trazado no llega ni de lejos a esto; el tope está para que un fichero
# equivocado no llene el disco.
TOPE_BYTES = 12 * 1024 * 1024


def _sanear(texto: str) -> str:
    """Un nombre de fichero seguro a partir del nombre del trazado."""
    limpio = unicodedata.normalize("NFD", texto or "")
    limpio = "".join(c for c in limpio if unicodedata.category(c) != "Mn")
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", limpio).strip("-").lower()
    return limpio or "trazado"


def ruta_plantilla(imagen: Optional[str]) -> Optional[str]:
    """La URL con la que CasparCG carga la imagen del trazado.

    Absoluta y por HTTP, no una ruta de disco. La plantilla se abre desde
    file://, que no tiene contra qué resolver una ruta relativa, así que
    tiene que apuntar al backend igual que ya hacen las fotos de pilotos
    y los logos de marcas.

    La consecuencia es que el backend debe estar corriendo para que el
    trazado salga al aire. No añade una dependencia nueva: sin backend
    tampoco saldrían las fotos ni los logos, ni habría de dónde sacar el
    cronometraje.
    """
    from config import settings

    if not imagen:
        return None

    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/public/circuit-image/{imagen}"




class TrazadosService:

    async def _siguiente_id(self) -> int:
        ultimo = await Trazado.find_all().sort(-Trazado.trazado_id).first_or_none()
        return (ultimo.trazado_id + 1) if ultimo else 1

    async def listar(self, discipline: Optional[str] = None) -> list[Trazado]:
        filtro = {"discipline": discipline} if discipline else {}
        return await Trazado.find(filtro).sort(Trazado.trazado_id).to_list()

    async def obtener(self, trazado_id: int) -> Trazado:
        doc = await Trazado.find_one({"trazado_id": trazado_id})
        if doc is None:
            raise HTTPException(404, f"No existe el trazado {trazado_id}")
        return doc

    async def activo(self) -> Optional[Trazado]:
        return await Trazado.find_one({"activo": True})

    async def crear(self, datos: dict) -> Trazado:
        # Se mira antes de insertar: después siempre habría al menos uno.
        primero = await Trazado.find_one({}) is None

        doc = Trazado(trazado_id=await self._siguiente_id(), **datos)

        # El primero que se da de alta queda activo. Si no, habría un
        # trazado guardado y el gráfico seguiría sin imagen hasta que
        # alguien cayera en pulsar "usar este".
        if primero:
            doc.activo = True

        await doc.insert()
        return doc

    async def actualizar(self, trazado_id: int, datos: dict) -> Trazado:
        doc = await self.obtener(trazado_id)

        for campo, valor in datos.items():
            if valor is not None:
                setattr(doc, campo, valor)

        await doc.save()
        return doc

    async def activar(self, trazado_id: int) -> Trazado:
        doc = await self.obtener(trazado_id)

        # Solo uno a la vez. Se apagan todos y se enciende este, en vez de
        # apagar "el que estuviera": si dos quedaron activos por lo que sea,
        # esto lo deja bien igualmente.
        await Trazado.find({"activo": True}).update({"$set": {"activo": False}})

        doc.activo = True
        await doc.save()
        return doc

    async def borrar(self, trazado_id: int) -> dict:
        doc = await self.obtener(trazado_id)

        imagen = doc.image
        era_activo = doc.activo

        await doc.delete()

        # La imagen se va con el trazado, pero solo si no la comparte otro.
        if imagen:
            en_uso = await Trazado.find_one({"image": imagen})
            if en_uso is None:
                fichero = CARPETA_IMAGENES / imagen
                if fichero.is_file():
                    try:
                        fichero.unlink()
                    except OSError:
                        # Que no se pueda borrar el fichero no invalida el
                        # borrado del trazado, que ya está hecho.
                        pass

        # Sin activo el gráfico se quedaría con la imagen de fábrica; se
        # pasa el testigo al primero que quede.
        if era_activo:
            siguiente = await Trazado.find_all().sort(Trazado.trazado_id).first_or_none()
            if siguiente is not None:
                siguiente.activo = True
                await siguiente.save()

        return {"ok": True, "trazado_id": trazado_id}

    # ── Imagen ────────────────────────────────────────────────────────

    def _destino(self, doc: Trazado, extension: str) -> Path:
        CARPETA_IMAGENES.mkdir(parents=True, exist_ok=True)
        return CARPETA_IMAGENES / f"{doc.trazado_id}-{_sanear(doc.name)}{extension}"

    async def _asignar(self, doc: Trazado, destino: Path) -> Trazado:
        anterior = doc.image

        doc.image = destino.name
        await doc.save()

        # La de antes se borra si nadie más la usa y no es la que se acaba
        # de escribir (al repetir extensión, destino y anterior coinciden).
        if anterior and anterior != destino.name:
            en_uso = await Trazado.find_one({"image": anterior})
            if en_uso is None:
                viejo = CARPETA_IMAGENES / anterior
                if viejo.is_file():
                    try:
                        viejo.unlink()
                    except OSError:
                        pass

        return doc

    def _revisar_extension(self, nombre: str) -> str:
        extension = Path(nombre or "").suffix.lower()

        if extension not in EXTENSIONES:
            raise HTTPException(
                400,
                f"'{extension or nombre}' no es una imagen. Se aceptan: "
                + ", ".join(sorted(EXTENSIONES)),
            )

        return extension

    async def subir_imagen(self, trazado_id: int, nombre: str, contenido: bytes) -> Trazado:
        """La que llega desde el navegador."""
        doc = await self.obtener(trazado_id)

        extension = self._revisar_extension(nombre)

        if not contenido:
            raise HTTPException(400, "El fichero llegó vacío")

        if len(contenido) > TOPE_BYTES:
            raise HTTPException(
                400,
                f"La imagen pesa {len(contenido) / 1048576:.1f} MB y el tope son "
                f"{TOPE_BYTES // 1048576} MB",
            )

        destino = self._destino(doc, extension)
        destino.write_bytes(contenido)

        return await self._asignar(doc, destino)

    async def copiar_imagen(self, trazado_id: int, ruta: str) -> Trazado:
        """La que ya está en el disco del servidor, escrita a mano."""
        doc = await self.obtener(trazado_id)

        origen = Path((ruta or "").strip().strip('"'))

        if not origen.is_absolute():
            raise HTTPException(
                400, "Escribe la ruta completa, del tipo C:\\imagenes\\pista.jpg")

        if not origen.exists():
            raise HTTPException(404, f"No existe: {origen}")

        if not origen.is_file():
            raise HTTPException(400, f"{origen} no es un fichero")

        extension = self._revisar_extension(origen.name)

        if origen.stat().st_size > TOPE_BYTES:
            raise HTTPException(
                400, f"La imagen supera los {TOPE_BYTES // 1048576} MB")

        destino = self._destino(doc, extension)

        try:
            shutil.copyfile(origen, destino)
        except OSError as e:
            raise HTTPException(400, f"No se pudo leer la imagen: {e}")

        return await self._asignar(doc, destino)


trazados_service = TrazadosService()

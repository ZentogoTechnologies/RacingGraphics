from pathlib import Path

from src.services.imagenes_services import (
    borrar_si_sobra, copiar_de_ruta, guardar_bytes,
)
from src.models.categories_model import Category, SubCategoryEmbedded
from src.models.vehicles_model import Vehicle
from typing import Optional

from src.schemas.categories_schemas import CategoryCreate, CategoryUpdate, CategoryResponse
from src.schemas.common_schemas import Page
from src.services.pagination import (
    campo_orden, combinar, direccion, filtro_busqueda,
)
from fastapi import HTTPException

# Backend/src/public/categorias, mirando desde Backend/src/services.
CARPETA_LOGOS = Path(__file__).resolve().parents[1] / "public" / "categorias"

RUTA_RELATIVA = "categorias"


def url_logo_categoria(archivo):
    """La ruta con la que el navegador y CasparCG piden el logo."""
    return f"/public/{RUTA_RELATIVA}/{archivo}" if archivo else None


class CategoryService:
    def _to_response(self, category: Category) -> CategoryResponse:
        # Convertir los SubCategoryEmbedded a dict para que Pydantic los valide bien
        sub_cats_data = [
            {"sub_category_id": sc.sub_category_id, "sub_category_name": sc.sub_category_name}
            for sc in category.sub_categories
        ]

        return CategoryResponse(
            _id=str(category.id), # usa _id y que Pydantic lo mapee a id con alias
            category_id=category.category_id,
            category_name=category.category_name,
            discipline=category.discipline,
            sub_categories=sub_cats_data, # <- ya son dicts
            description=category.description,
            logo=category.logo,
            logo_url=url_logo_categoria(category.logo),
        )

    async def _siguiente_id(self) -> int:
        """El id más alto que hay, más uno.

        Se calcula aquí y no en el navegador: si dos personas abren el
        formulario a la vez, las dos verían el mismo número libre y la
        segunda chocaría al guardar.
        """
        ultima = await Category.find_all().sort(("category_id", -1)).limit(1).to_list()
        return (ultima[0].category_id + 1) if ultima else 1

    async def create_category(self, data: CategoryCreate) -> CategoryResponse:
        if data.category_id is None:
            category_id = await self._siguiente_id()
        else:
            category_id = data.category_id
            exists = await Category.find_one(Category.category_id == category_id)
            if exists:
                raise HTTPException(status_code=400, detail="category_id ya existe")

        # Misma regla que en el update: dos subcategorías con el mismo id
        # dentro de una categoría dejan al vehículo apuntando a cualquiera.
        ids = [sc.sub_category_id for sc in data.sub_categories]
        if len(ids) != len(set(ids)):
            raise HTTPException(
                status_code=400,
                detail="Hay sub_category_id repetidos en la categoría",
            )

        category = Category(
            category_id=category_id,
            category_name=data.category_name,
            discipline=data.discipline,
            sub_categories=[SubCategoryEmbedded(**sc.model_dump()) for sc in data.sub_categories],
            description=data.description
        )
        await category.insert()
        return self._to_response(category)

    ORDENABLES = {"category_id", "category_name", "discipline"}
    BUSCABLES = ["category_name", "description"]

    async def get_categories(
        self,
        discipline: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: Optional[str] = None,
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> Page[CategoryResponse]:
        query = combinar(
            {"discipline": discipline} if discipline else None,
            filtro_busqueda(search, self.BUSCABLES),
        )

        total = await Category.find(query).count()

        consulta = Category.find(query).sort(
            (campo_orden(sort_by, self.ORDENABLES, "category_name"), direccion(sort_dir))
        ).skip(skip)

        if limit is not None:
            consulta = consulta.limit(limit)

        categories = await consulta.to_list()

        return Page(
            items=[self._to_response(c) for c in categories],
            total=total,
            skip=skip,
            limit=limit,
        )

    async def get_category_by_id(self, category_id: str) -> CategoryResponse:
        category = await Category.find_one(Category.category_id == int(category_id))
        if not category:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")
        return self._to_response(category)

    async def update_category(self, category_id: str, data: CategoryUpdate) -> CategoryResponse:
        category = await Category.find_one(Category.category_id == int(category_id))
        if not category:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")

        update_data = data.model_dump(exclude_unset=True)

        if "sub_categories" in update_data:
            subs = update_data["sub_categories"] or []

            # No se vuelven a construir como SubCategoryEmbedded: model_dump()
            # ya bajó los modelos anidados a diccionarios, y llamar
            # sc.model_dump() sobre un diccionario reventaba con un 500.
            # Mongo guarda diccionarios, así que van tal cual.

            # Dos subcategorías con el mismo id dentro de la misma categoría
            # dejarían al vehículo apuntando a cualquiera de las dos.
            ids = [sc["sub_category_id"] for sc in subs]
            if len(ids) != len(set(ids)):
                raise HTTPException(
                    status_code=400,
                    detail="Hay sub_category_id repetidos en la categoría",
                )

            # Quitar una subcategoría que algún vehículo usa lo deja
            # apuntando a un id que ya no existe, y al aire la ficha sale
            # sin subcategoría. Se avisa con cuántos carros están en juego
            # en vez de romper los datos en silencio.
            quedan = {sc["sub_category_id"] for sc in subs}
            eliminadas = [
                s.sub_category_id
                for s in category.sub_categories
                if s.sub_category_id not in quedan
            ]

            if eliminadas:
                en_uso = await Vehicle.find({
                    "category_id": category.category_id,
                    "sub_category_id": {"$in": eliminadas},
                }).count()

                if en_uso:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"No se puede quitar: {en_uso} vehículo(s) usan esa "
                            "subcategoría. Cámbialos de subcategoría primero."
                        ),
                    )

            update_data["sub_categories"] = subs

        await category.update({"$set": update_data})

        # Beanie viejo no tiene reload. Hacemos un find de nuevo
        updated_category = await Category.find_one(Category.category_id == int(category_id))
        return self._to_response(updated_category)

    async def delete_category(self, category_id: str) -> dict:
        category = await Category.find_one(Category.category_id == int(category_id))
        if not category:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")
        await category.delete()
        return {"detail": "Categoría eliminada"}

    # ── Logo de la categoría ──────────────────────────────────────────

    async def _categoria(self, category_id: int) -> Category:
        doc = await Category.find_one(Category.category_id == category_id)
        if doc is None:
            raise HTTPException(404, f"No existe la categoría {category_id}")
        return doc

    async def _asignar_logo(self, categoria: Category, destino: Path) -> CategoryResponse:
        anterior = (CARPETA_LOGOS / categoria.logo) if categoria.logo else None

        categoria.logo = destino.name
        await categoria.save()

        borrar_si_sobra(anterior, destino)

        return self._to_response(categoria)

    async def subir_logo(self, category_id: int, nombre: str, contenido: bytes) -> CategoryResponse:
        """El que llega desde el navegador."""
        categoria = await self._categoria(category_id)

        # El archivo se llama como el id y no como la categoría: renombrar
        # "TCR" a "TCR Panamá" no debe dejar el logo huérfano.
        destino = guardar_bytes(contenido, nombre, CARPETA_LOGOS / str(category_id))

        return await self._asignar_logo(categoria, destino)

    async def logo_por_ruta(self, category_id: int, ruta: str) -> CategoryResponse:
        """El que ya está en el disco del servidor."""
        categoria = await self._categoria(category_id)

        destino = copiar_de_ruta(ruta, CARPETA_LOGOS / str(category_id))

        return await self._asignar_logo(categoria, destino)

    async def quitar_fondo_logo(self, category_id: int) -> CategoryResponse:
        """Deja transparente el fondo del logo de la categoría.

        Usa el recorte por color y no el de las fotos. Los modelos de
        segmentación están entrenados con fotografías: delante de un
        logotipo con letras y destellos no distinguen figura de fondo.
        Un logo, en cambio, casi siempre viene sobre un plano uniforme, y
        eso sí se puede reconocer y quitar.
        """
        categoria = await self._obtener(category_id)

        if not categoria.logo:
            raise HTTPException(
                400, "La categoría no tiene logo: sube uno antes de quitarle el fondo")

        actual = CARPETA_LOGOS / categoria.logo
        if not actual.is_file():
            raise HTTPException(400, "El archivo del logo no está en el disco")

        from src.services.recorte_services import quitar_fondo_plano

        try:
            recortado = quitar_fondo_plano(actual.read_bytes())
        except ValueError as e:
            # El fondo no era plano. Se dice en claro: es un caso normal,
            # no un fallo del servidor.
            raise HTTPException(422, str(e))
        except Exception as e:
            raise HTTPException(422, f"No se pudo quitar el fondo: {e}")

        # Siempre PNG: la transparencia no cabe en un JPG ni en un WEBP
        # guardado como opaco.
        destino = guardar_bytes(recortado, "logo.png", CARPETA_LOGOS / str(category_id))
        return await self._asignar_logo(categoria, destino)

    async def borrar_logo(self, category_id: int) -> CategoryResponse:
        categoria = await self._categoria(category_id)

        if categoria.logo:
            fichero = CARPETA_LOGOS / categoria.logo
            categoria.logo = None
            await categoria.save()
            borrar_si_sobra(fichero, CARPETA_LOGOS / "__ninguno__")

        return self._to_response(categoria)

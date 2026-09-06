from pydantic import BaseModel
from fastapi import UploadFile, File, APIRouter, Depends, HTTPException, Query
from typing import Optional
from src.services.categories_services import CategoryService
from src.schemas.categories_schemas import CategoryCreate, CategoryUpdate, CategoryResponse
from src.schemas.common_schemas import Page
from src.services.auth_services import puede_escribir

categories = APIRouter()
service = CategoryService()

@categories.get("/", tags=["Categories"], response_model=Page[CategoryResponse])
async def get_categories(
    discipline: Optional[str] = Query(None, description="Filter by discipline: circuit o drag"),
    search: Optional[str] = Query(None, description="Búsqueda parcial, sin distinguir mayúsculas"),
    sort_by: Optional[str] = Query(None, description="Campo por el que ordenar"),
    sort_dir: Optional[str] = Query("asc", description="asc o desc"),
    skip: int = Query(0, ge=0, description="Cuántos registros saltar"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Tamaño de página. Sin valor devuelve todo"),
):
    """
    Obtiene las categorías paginadas. Puedes filtrar por disciplina o texto.
    Ordena por: category_id, category_name, discipline
    """
    return await service.get_categories(
        discipline=discipline, search=search,
        sort_by=sort_by, sort_dir=sort_dir, skip=skip, limit=limit,
    )

@categories.post("/", tags=["Categories"], response_model=CategoryResponse, status_code=201, dependencies=[Depends(puede_escribir)])
async def create_category(data: CategoryCreate):
    """
    Crea una nueva categoría con sus subcategorías
    """
    return await service.create_category(data)

@categories.get("/{category_id}", tags=["Categories"], response_model=CategoryResponse)
async def get_category_by_id(category_id: str):
    """
    Obtiene una categoría por su category_id
    """
    category = await service.get_category_by_id(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category Not Found!")
    return category

@categories.put("/{category_id}", tags=["Categories"], response_model=CategoryResponse, dependencies=[Depends(puede_escribir)])
async def update_category(category_id: str, data: CategoryUpdate):
    """
    Actualiza una categoría
    """
    category = await service.update_category(category_id, data)
    if not category:
        raise HTTPException(status_code=404, detail="Category Not Found!")
    return category

@categories.delete("/{category_id}", tags=["Categories"], dependencies=[Depends(puede_escribir)])
async def delete_category(category_id: str):
    """
    Elimina una categoría
    """
    deleted = await service.delete_category(category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Category Not Found!")
    return {"message": "Category deleted"}


# ======================================================================
#  LOGO DE LA CATEGORÍA
#
#  El del campeonato: TCR, GT Challenge, Fórmula 1. El archivo va al disco
#  y en la base queda solo su nombre, igual que las fotos de pilotos y las
#  imágenes de eventos y trazados.
# ======================================================================


class RutaLogoCategoria(BaseModel):
    ruta: str


@categories.post("/{category_id}/logo", tags=["Categories"], response_model=CategoryResponse,
                 dependencies=[Depends(puede_escribir)])
async def subir_logo_categoria(category_id: int, archivo: UploadFile = File(...)):
    """
    Sube el logo de la categoría desde el navegador
    """
    contenido = await archivo.read()
    return await service.subir_logo(category_id, archivo.filename or "", contenido)


@categories.put("/{category_id}/logo", tags=["Categories"], response_model=CategoryResponse,
                dependencies=[Depends(puede_escribir)])
async def logo_categoria_por_ruta(category_id: int, datos: RutaLogoCategoria):
    """
    Toma el logo de una ruta del servidor y lo copia a public/categorias
    """
    return await service.logo_por_ruta(category_id, datos.ruta)


@categories.post("/{category_id}/logo/sin-fondo", tags=["Categories"],
                 response_model=CategoryResponse,
                 dependencies=[Depends(puede_escribir)])
async def quitar_fondo_logo_categoria(category_id: int):
    """
    Deja transparente el fondo del logo, si es de un solo color.
    """
    return await service.quitar_fondo_logo(category_id)


@categories.delete("/{category_id}/logo", tags=["Categories"], response_model=CategoryResponse,
                   dependencies=[Depends(puede_escribir)])
async def borrar_logo_categoria(category_id: int):
    """
    Quita el logo de la categoría
    """
    return await service.borrar_logo(category_id)

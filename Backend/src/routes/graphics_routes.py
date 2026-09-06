from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from config import settings
from src.schemas.graphics_schemas import (
    ClearRequest,
    GraphicResponse,
    PlayRequest,
    StateResponse,
    TemplateResponse,
    UpdateRequest,
)
from src.services.casparcg_client import (
    CasparCGError,
    CasparCGUnavailable,
    casparcg,
)
from src.services.auth_services import puede_escribir
from src.services.graphics_services import LAYERS, build_pilot_payload, service

graphics = APIRouter()


# ── Ayudas ────────────────────────────────────────────────────

def _resolve(graphic_id: str):
    template = service.get_template(graphic_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Gráfico '{graphic_id}' no existe")
    return template


async def _payload(template, pilot_id: Optional[int], data: Optional[dict],
                   category_id: Optional[int] = None,
                   event_id: Optional[int] = None,
                   pilot_id_2: Optional[int] = None) -> Optional[dict]:
    """
    Arma los datos que recibirá la plantilla.

    Si viene un pilot_id, el backend los saca de la base; lo que llegue en
    `data` se aplica encima, para poder corregir un campo puntual sin
    tener que mandar el resto.
    """
    # El clima se resuelve solo: pulsar el botón tiene que sacar el dato
    # real sin que nadie lo escriba a mano. Lo que venga en `data` manda
    # encima, por si hay que corregir algo puntual al aire.
    if template.graphic_id == "clima":
        from src.services.weather_services import obtener_clima

        clima = obtener_clima()
        if clima.get("ok"):
            return {**clima, **(data or {})}
        # Sin clima disponible se sigue adelante con lo que haya llegado:
        # la plantilla tiene sus propios valores por defecto.
        return data

    # El circuito sale del trazado marcado como activo en Ajustes. Igual
    # que el clima: pulsar el botón tiene que sacar lo que corresponde sin
    # que nadie escriba nada, y lo que venga en `data` manda encima.
    if template.graphic_id == "circuito":
        from src.services.tracks_services import ruta_plantilla, trazados_service

        trazado = await trazados_service.activo()
        if trazado is not None:
            base = {"circuit_name": trazado.name}

            if trazado.variante:
                base["label"] = trazado.variante
            elif trazado.length_km:
                base["label"] = f"{trazado.length_km:g} km"

            imagen = ruta_plantilla(trazado.image)
            if imagen:
                base["circuit_image"] = imagen

            return {**base, **(data or {})}

        # Sin trazado dado de alta la plantilla se queda con lo suyo.
        return data

    # El evento saca su nombre y su imagen de la base, igual que el clima
    # y el circuito. La imagen no puede armarla el navegador: CasparCG abre
    # la plantilla desde file:// y necesita una URL absoluta.
    if template.graphic_id == "evento" and event_id is not None:
        from src.models.events_model import Event
        from src.services.graphics_services import event_image_url

        evento = await Event.find_one(Event.event_id == event_id)
        if evento is not None:
            # Solo la imagen del propio evento. No se cae al logo de la
            # categoría: esa tiene su propio gráfico, y mezclarlas hacía
            # que un evento sin arte propio saliera con el del campeonato
            # sin que nadie lo hubiera decidido.
            base = {
                "event": evento.name,
                # Se manda siempre, vacía incluida: omitirla dejaría en
                # pantalla el logo del evento anterior.
                "event_image": event_image_url(evento.image),
            }
            return {**base, **(data or {})}

    # La carta de categoría: el nombre, las subcategorías que están
    # corriendo en ese evento y el logo del campeonato.
    if template.graphic_id == "categoria" and category_id is not None:
        from src.models.categories_model import Category
        from src.models.events_model import Event
        from src.services.graphics_services import category_logo_url

        categoria = await Category.find_one(Category.category_id == category_id)
        if categoria is None:
            raise HTTPException(404, f"No existe la categoría {category_id}")

        # Las que de verdad tienen carros inscritos en este evento, no
        # todas las declaradas: si en esta fecha no corre "Equipos por
        # color", ponerla en el arte sería mentir.
        nombres = []
        if event_id is not None:
            evento = await Event.find_one(Event.event_id == event_id)
            if evento is not None:
                ids = []
                for ins in (evento.inscritos or []):
                    if ins.category_id == category_id and ins.sub_category_id is not None:
                        if ins.sub_category_id not in ids:
                            ids.append(ins.sub_category_id)

                # Se ordenan como están declaradas en la categoría, no por
                # el orden en que alguien inscribió los carros.
                nombres = [sc.sub_category_name
                           for sc in categoria.sub_categories
                           if sc.sub_category_id in ids]

        # Sin evento o sin inscritos se muestran las declaradas: es lo que
        # esa categoría corre normalmente.
        if not nombres:
            nombres = [sc.sub_category_name for sc in categoria.sub_categories]

        base = {
            "category": categoria.category_name,
            "subcategories": nombres,
            # Se manda siempre, vacío incluido, o al cambiar de categoría
            # quedaría el logo de la anterior.
            "category_logo": category_logo_url(categoria.logo),
        }
        return {**base, **(data or {})}

    # Las dos grillas se arman solas: no se elige nada en el panel, sale la
    # parrilla de la tanda que esté cargada en el cronometraje. Comparten
    # armador porque son los mismos datos contados de dos formas: una lista
    # para buscarse, y las caras de los que salen juntos.
    if template.graphic_id in ("grilla", "grilla-fotos"):
        from src.services.graphics_services import build_grid_payload

        # El evento elegido en el panel manda sobre el que traiga el XML.
        base = await build_grid_payload(event_id=event_id)
        return {**base, **(data or {})}

    # La carta VS necesita dos pilotos, así que tiene su propio armador.
    if template.graphic_id == "carta-vs":
        if pilot_id is None or pilot_id_2 is None:
            raise HTTPException(400, "La carta VS necesita dos pilotos")

        from src.services.graphics_services import build_vs_payload

        base = await build_vs_payload(pilot_id, pilot_id_2)
        return {**base, **(data or {})}

    # El duelo de drag: dos pilotos, uno por carril. DragWar y competencia
    # comparten armador porque comparten arte; lo que las distingue —la
    # cabecera, la ronda— lo escribe el panel y llega en `data`, igual que
    # las cifras de la pasada, que hasta que Race America esté conectado se
    # teclean a mano.
    if template.graphic_id in ("dragwar", "competencia"):
        if pilot_id is None or pilot_id_2 is None:
            raise HTTPException(400, "El duelo necesita los dos carriles")

        from src.services.graphics_services import build_drag_payload

        base = await build_drag_payload(pilot_id, pilot_id_2)
        return {**base, **(data or {})}

    if pilot_id is None:
        return data

    payload = await build_pilot_payload(template.graphic_id, pilot_id, category_id)
    if data:
        payload.update(data)
    return payload


async def _run(coro, graphic_id: str = None, layer: int = None) -> GraphicResponse:
    """
    Ejecuta un comando traduciendo los fallos de CasparCG a HTTP.

    503 si el servidor de video no responde (apagado o sin red) y 502 si
    responde pero rechaza el comando. Así el frontend puede distinguir
    "no hay servidor" de "el comando estaba mal".
    """
    try:
        result = await coro

    except CasparCGUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    except CasparCGError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"CasparCG rechazó el comando: {exc.status} ({exc.command})",
        ) from exc

    return GraphicResponse(
        ok=True,
        graphic_id=graphic_id,
        layer=layer,
        command=result["command"],
        code=result["code"],
        status=result["status"],
        on_air=service.on_air(),
    )


# ── Catálogo y estado ─────────────────────────────────────────

@graphics.get("/templates", tags=["Graphics"], response_model=list[TemplateResponse])
async def list_templates(
    group: Optional[str] = Query(None, description="Filtrar por grupo: background, totem, flag, grid, pilot, misc")
):
    """
    Devuelve el catálogo de plantillas con su capa y su ruta.

    El frontend puede usarlo para validar que sus botones coinciden con
    lo que el backend sabe graficar.
    """
    return [TemplateResponse(**t.__dict__) for t in service.list_templates(group)]


@graphics.get("/state", tags=["Graphics"], response_model=StateResponse)
async def get_state():
    """Qué gráfico hay al aire en cada capa y si la conexión sigue viva."""
    return StateResponse(
        connected=casparcg.is_connected,
        host=casparcg.host,
        port=casparcg.port,
        channel=settings.CASPARCG_CHANNEL,
        on_air=service.on_air(),
    )


@graphics.post("/reconnect", tags=["Graphics"], dependencies=[Depends(puede_escribir)])
async def reconnect():
    """
    Fuerza la reconexión con CasparCG. Útil si se cerró y se volvió a abrir
    """
    resultado = await casparcg.reconectar()

    return {
        **resultado,
        "connected": casparcg.is_connected,
        "host": casparcg.host,
        "port": casparcg.port,
    }


# ── Comandos ──────────────────────────────────────────────────

@graphics.post("/play", tags=["Graphics"], response_model=GraphicResponse)
async def play_graphic(request: PlayRequest):
    """
    Saca un gráfico al aire: CG <canal>-<capa> ADD 1 "<plantilla>" 1.

    Espera la respuesta de CasparCG antes de contestar, así el frontend
    solo marca el botón como activo cuando el gráfico salió de verdad.
    """
    template = _resolve(request.graphic_id)

    data = await _payload(template, request.pilot_id, request.data,
                          request.category_id, request.event_id,
                          request.pilot_id_2)

    if data and not template.accepts_data:
        raise HTTPException(
            status_code=400,
            detail=f"La plantilla '{template.graphic_id}' no recibe datos",
        )

    return await _run(
        service.play(template, data),
        graphic_id=template.graphic_id,
        layer=template.layer,
    )


@graphics.post("/update", tags=["Graphics"], response_model=GraphicResponse)
async def update_graphic(request: UpdateRequest):
    """
    Refresca los datos de un gráfico ya al aire sin recargar la plantilla:
    CG <canal>-<capa> UPDATE 1 "<datos>".
    """
    template = _resolve(request.graphic_id)

    if not template.accepts_data:
        raise HTTPException(
            status_code=400,
            detail=f"La plantilla '{template.graphic_id}' no recibe datos",
        )

    data = await _payload(template, request.pilot_id, request.data,
                          request.category_id, request.event_id,
                          request.pilot_id_2)

    return await _run(
        service.update(template, data),
        graphic_id=template.graphic_id,
        layer=template.layer,
    )


@graphics.post("/clear", tags=["Graphics"], response_model=GraphicResponse)
async def clear_layer(request: ClearRequest):
    """
    Limpia una capa: CLEAR <canal>-<capa>.

    Se puede pedir por gráfico ("saca esto de aire") o por grupo
    ("limpia los fondos"); en los dos casos se limpia la capa completa.
    """
    if request.graphic_id:
        layer = _resolve(request.graphic_id).layer
    else:
        layer = LAYERS.get(request.group)
        if layer is None:
            raise HTTPException(
                status_code=404,
                detail=f"Grupo '{request.group}' no existe. Válidos: {', '.join(LAYERS)}",
            )

    return await _run(service.clear_layer(layer), layer=layer)


@graphics.post("/clear-all", tags=["Graphics"], response_model=GraphicResponse)
async def clear_all():
    """Saca todo de aire: CLEAR <canal>."""
    return await _run(service.clear_all())

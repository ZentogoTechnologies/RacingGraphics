"""Quita el fondo de una foto y deja al piloto recortado.

Se hace en el servidor y no en el navegador ni en una nube. En el
autódromo la red se cae o está aislada, y una foto que no se puede
recortar porque no hay internet es una foto que se queda con el fondo del
taller. El modelo va en disco y funciona sin conexión.

El modelo se carga una sola vez y se guarda: la primera llamada tarda unos
segundos y las siguientes son inmediatas.
"""

import io
from typing import Optional

from PIL import Image, ImageOps

# Un modelo por tipo de sujeto. u2net_human_seg está entrenado solo con
# personas y acierta mucho más en gorras y pelo, que es donde se nota un
# recorte malo; pero delante de un carro no sabe qué mirar. El general sí,
# y a cambio es peor con el pelo.
#
# Da igual que la foto de catálogo del BMW saliera bien con el de personas:
# venía con el fondo ya blanco. La prueba de verdad es un carro en boxes,
# con gente y carpas detrás.
MODELOS = {
    "persona": "u2net_human_seg",
    "objeto":  "u2net",
}

# Las fotos llegan de un iPad a 4000px de ancho y el arte no las necesita:
# el retrato más grande que se pinta es el de la grilla, que ocupa media
# pantalla. Reducir antes de recortar baja el trabajo del modelo de
# segundos a décimas y el PNG resultante de cinco megas a menos de uno.
LADO_MAXIMO = 1400

# Una sesión por modelo, cargada la primera vez que se pide. Son unos
# segundos y 176 MB en memoria cada una, así que no se cargan las dos si
# solo se usa una.
_sesiones = {}


def _obtener_sesion(sujeto: str):
    if sujeto not in _sesiones:
        from rembg import new_session
        _sesiones[sujeto] = new_session(MODELOS.get(sujeto, MODELOS["persona"]))
    return _sesiones[sujeto]


def quitar_fondo(contenido: bytes, sujeto: str = "persona") -> bytes:
    """Devuelve la foto en PNG con el fondo transparente.

    Se normaliza la orientación antes de recortar. Las fotos de móvil
    traen la rotación en los datos EXIF en vez de en los píxeles, y el PNG
    de salida no lleva EXIF: sin enderezarla primero, un retrato tomado en
    vertical se guardaría tumbado para siempre.
    """
    from rembg import remove

    imagen = Image.open(io.BytesIO(contenido))
    imagen = ImageOps.exif_transpose(imagen)

    if max(imagen.size) > LADO_MAXIMO:
        imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)

    recortada = remove(imagen.convert("RGB"), session=_obtener_sesion(sujeto))

    salida = io.BytesIO()
    recortada.save(salida, format="PNG", optimize=True)
    return salida.getvalue()


# ── Logotipos ─────────────────────────────────────────────────────
#
# Un logo no se recorta con los modelos de arriba. Estan entrenados con
# fotografias de personas y de objetos, y delante de unas letras con
# destellos no saben que es figura y que es fondo: devuelven cualquier
# cosa o la imagen entera.
#
# Lo que sirve es quitar el fondo por color. Los logos vienen sobre un
# plano uniforme —casi siempre negro o blanco— y ese plano se puede
# reconocer mirando las esquinas.

# Hasta donde se considera fondo. Por debajo el pixel se va del todo, y
# entre este valor y el doble se difumina: sin esa franja el borde de las
# letras queda dentado.
TOLERANCIA = 42


def _color_del_fondo(imagen):
    """El color de las cuatro esquinas, si coinciden entre si.

    Se miran las esquinas y no un pixel suelto: una mota o el filo de un
    destello darian un color equivocado para toda la imagen.
    """
    ancho, alto = imagen.size
    m = max(2, min(ancho, alto) // 40)

    esquinas = []
    for x0, y0 in ((0, 0), (ancho - m, 0), (0, alto - m), (ancho - m, alto - m)):
        trozo = imagen.crop((x0, y0, x0 + m, y0 + m))
        pixeles = list(trozo.getdata())
        esquinas.append(tuple(sum(c[i] for c in pixeles) // len(pixeles)
                              for i in range(3)))

    # Si las esquinas no se parecen, el fondo no es plano y esto no aplica.
    for c in esquinas[1:]:
        if sum(abs(a - b) for a, b in zip(c, esquinas[0])) > TOLERANCIA * 3:
            return None

    return tuple(sum(c[i] for c in esquinas) // 4 for i in range(3))


def quitar_fondo_plano(contenido: bytes, tolerancia: int = TOLERANCIA) -> bytes:
    """Deja transparente el fondo plano de un logotipo.

    Devuelve PNG. Si el fondo no es plano se levanta un error en vez de
    devolver una imagen destrozada: es mejor decirlo que entregar un logo
    con agujeros.
    """
    from PIL import Image, ImageOps

    imagen = Image.open(io.BytesIO(contenido))
    imagen = ImageOps.exif_transpose(imagen).convert("RGBA")

    fondo = _color_del_fondo(imagen.convert("RGB"))
    if fondo is None:
        raise ValueError(
            "El fondo no es de un solo color: este recorte solo sirve para "
            "logos sobre un plano uniforme"
        )

    fr, fg, fb = fondo
    pixeles = imagen.load()
    ancho, alto = imagen.size

    for y in range(alto):
        for x in range(ancho):
            r, g, b, a = pixeles[x, y]
            if a == 0:
                continue

            # Distancia al color del fondo. Se difumina en una franja para
            # que el filo de las letras no quede dentado.
            d = abs(r - fr) + abs(g - fg) + abs(b - fb)
            if d <= tolerancia:
                pixeles[x, y] = (r, g, b, 0)
            elif d <= tolerancia * 2:
                suave = int(255 * (d - tolerancia) / tolerancia)
                pixeles[x, y] = (r, g, b, min(a, suave))

    salida = io.BytesIO()
    imagen.save(salida, format="PNG", optimize=True)
    return salida.getvalue()

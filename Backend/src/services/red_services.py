"""Direcciones por las que se llega a este equipo.

El backend atiende en 0.0.0.0, que no es una dirección: significa «por
todas las interfaces». Así que nadie puede escribir eso en un navegador.

Quien opera desde un iPad o desde otra computadora necesita la dirección
real de este equipo en la red local, y esa dirección la reparte el router:
cambia de una sala a otra, y puede cambiar al reiniciar. Por eso se
calcula en caliente y se enseña en el asistente de instalación y en
Ajustes, en vez de escribirla en un manual que quedará desactualizado.
"""

import socket

from config import settings


def _ip_de_salida() -> str | None:
    """La IP que este equipo usa para hablar con la red local.

    Se abre un socket UDP hacia una dirección externa y se pregunta qué
    interfaz eligió el sistema. No se manda ni un byte —UDP no conecta de
    verdad— así que funciona igual sin internet, que es justo el caso del
    autódromo.

    Se hace así y no con gethostbyname(hostname) porque eso, en Windows
    con varias tarjetas de red, suele devolver la equivocada: la del
    adaptador virtual de una VM en vez de la de la red donde está el iPad.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def _todas_las_ipv4() -> list[str]:
    """Cualquier otra IPv4 del equipo, por si tiene más de una tarjeta."""
    encontradas = []

    try:
        for familia, _, _, _, direccion in socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET
        ):
            ip = direccion[0]
            if ip not in encontradas and not ip.startswith("127."):
                encontradas.append(ip)
    except (OSError, socket.gaierror):
        pass

    return encontradas


def direcciones() -> dict:
    """Cómo entrar al panel, desde aquí y desde fuera.

    `principal` es la que hay que escribir en el iPad. El resto se ofrece
    porque un equipo con varias tarjetas —cableada y wifi, o una VPN—
    puede tener la buena en la segunda posición, y probar es más rápido
    que explicarle a alguien por teléfono cómo mirar su configuración.
    """
    puerto = settings.API_PORT
    principal = _ip_de_salida()

    otras = [ip for ip in _todas_las_ipv4() if ip != principal]

    return {
        "puerto": puerto,
        "hostname": socket.gethostname(),
        # Desde el propio equipo servidor.
        "local": f"http://127.0.0.1:{puerto}",
        # Desde el iPad, o desde cualquier otra computadora de la red.
        "red": f"http://{principal}:{puerto}" if principal else None,
        "alternativas": [f"http://{ip}:{puerto}" for ip in otras],
        # Cuando el backend escucha solo en loopback no hay nada que
        # anunciar: desde fuera no se llega aunque se sepa la IP.
        "abierto_a_la_red": settings.API_HOST in ("0.0.0.0", "::"),
    }

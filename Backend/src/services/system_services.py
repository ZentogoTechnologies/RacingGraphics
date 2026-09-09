"""Apagado ordenado del sistema.

Detiene CasparCG, el frontend y el propio backend. MongoDB no se toca:
corre como servicio de Windows, lo comparten otros programas y volver a
levantarlo exige permisos de administrador.

Los procesos se buscan por el puerto en el que escuchan, no por el
archivo de PIDs del lanzador. Así funciona igual si alguien arrancó todo
a mano, y no se queda apuntando a un PID viejo que el sistema ya reasignó
a otro programa.
"""

import asyncio
import os
import re
import subprocess

# Puerto -> nombre legible. El orden importa: CasparCG primero para sacar
# los gráficos del aire antes de que se caiga nada más.
#
# Aquí solo va CasparCG. El panel lo sirve el propio backend, así que no
# hay un proceso de frontend aparte que matar —antes se buscaba uno en el
# 5173, que era el servidor de desarrollo— y el backend se apaga solo al
# final, después de haber respondido.
OBJETIVOS = [
    (5250, "CasparCG"),
]

# MongoDB (27017) nunca entra aquí.

_PATRON_NETSTAT = re.compile(
    r"^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$", re.MULTILINE
)


def pids_escuchando(puerto: int) -> set[int]:
    """PIDs que tienen ese puerto en LISTENING.

    Puede haber más de uno: un servidor puede abrir IPv4 e IPv6 por
    separado, y a veces son entradas distintas del mismo proceso.
    """
    try:
        # Sin "-p TCP" a propósito: ese filtro deja fuera lo que escucha
        # en IPv6, y un proceso atado a [::1] parecía apagado, de modo que
        # el apagado lo daba por "no estaba corriendo".
        salida = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return set()

    encontrados = set()
    for p, pid in _PATRON_NETSTAT.findall(salida):
        if int(p) == puerto:
            encontrados.add(int(pid))

    # El propio backend no se mata desde aquí: se apaga solo al final,
    # después de haber respondido.
    encontrados.discard(os.getpid())
    return encontrados


def matar(pid: int) -> bool:
    """Cierra el proceso y su descendencia.

    /T arrastra a los hijos: matar solo al padre puede dejar el puerto
    ocupado y el servidor sirviendo.
    """
    try:
        r = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def detener_servicios() -> list[dict]:
    """Apaga todo menos el backend. Devuelve qué pasó con cada cosa."""
    resultados = []

    for puerto, nombre in OBJETIVOS:
        pids = pids_escuchando(puerto)

        if not pids:
            resultados.append({
                "servicio": nombre, "puerto": puerto,
                "estado": "no_estaba", "detalle": "no estaba corriendo",
            })
            continue

        detenidos = [pid for pid in pids if matar(pid)]

        resultados.append({
            "servicio": nombre,
            "puerto": puerto,
            "estado": "detenido" if detenidos else "fallo",
            "detalle": (
                f"PID {', '.join(str(p) for p in detenidos)}" if detenidos
                else "no se pudo cerrar; ciérralo desde su ventana"
            ),
        })

    return resultados


async def apagar_backend(retraso: float = 1.5):
    """Se apaga a sí mismo, pero no antes de que la respuesta salga.

    El retraso da tiempo a que uvicorn termine de escribir el JSON en el
    socket. Sin él, el navegador recibe una conexión cortada y muestra un
    error de red en vez del resumen del apagado.

    Se usa os._exit y no sys.exit porque este código corre dentro de una
    tarea del bucle de asyncio: un SystemExit ahí lo captura el servidor y
    el proceso sigue vivo.
    """
    await asyncio.sleep(retraso)
    os._exit(0)

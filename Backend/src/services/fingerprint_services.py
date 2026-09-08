"""Huella del equipo.

Una licencia de Race Core Studio vale para una sola máquina. Para poder
atarla hace falta un identificador que cumpla dos cosas a la vez:

  · Que sobreviva a lo cotidiano. Reinstalar el software, cambiar el
    nombre del equipo, actualizar Windows o mover el cable de red no
    pueden invalidar la licencia de un cliente en plena temporada.

  · Que no se copie de un equipo a otro sin querer. Clonar el disco a una
    máquina nueva tiene que dar una huella distinta; si no, una licencia
    se multiplicaría sola.

Se combinan dos fuentes de Windows que cumplen ambas:

    MachineGuid   El identificador que Windows escribe al instalarse. No
                  cambia en toda la vida del sistema operativo.
    Volumen C:    Número de serie del volumen del sistema. Cambia si el
                  disco se reformatea.

Se mezclan y se resumen con SHA-256. Lo que sale es un texto opaco de 64
caracteres: identifica al equipo, pero no revela nada sobre él, así que
puede viajar al servidor de licencias sin exponer datos de la máquina del
cliente.

Fuera de Windows se usa lo que haya (machine-id de systemd, o el nombre
del equipo como último recurso). Eso es solo para poder desarrollar y
correr las pruebas en Linux o macOS: en producción esto siempre es
Windows.
"""

import hashlib
import platform
import subprocess
import uuid
from pathlib import Path

# Prefijo del resumen. Va dentro del hash para que la misma máquina dé
# huellas distintas en dos productos distintos: si mañana Race America
# corre en el mismo equipo, su licencia no debe ser intercambiable con la
# de Race Core Studio.
_SAL = "zentogo-fingerprint-v1"


def _machine_guid() -> str:
    """MachineGuid del registro de Windows.

    Se lee con winreg y no invocando reg.exe para no depender de que el
    PATH esté sano ni abrir una consola en mitad del arranque.
    """
    try:
        import winreg
    except ImportError:
        return ""

    try:
        # KEY_WOW64_64KEY es obligatorio: si el backend corre como proceso
        # de 32 bits, sin esa bandera Windows lo manda a la vista
        # redirigida del registro y la clave sencillamente no aparece.
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as clave:
            valor, _ = winreg.QueryValueEx(clave, "MachineGuid")
            return str(valor).strip()
    except OSError:
        return ""


def _serial_volumen_sistema() -> str:
    """Número de serie del volumen donde está Windows.

    Se pide por API (GetVolumeInformationW) en vez de parsear la salida de
    `vol` o `wmic`: wmic ya no viene en las versiones nuevas de Windows, y
    la salida de `vol` cambia con el idioma del sistema.
    """
    if platform.system() != "Windows":
        return ""

    try:
        import ctypes

        numero = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p("C:\\"),
            None, 0,
            ctypes.byref(numero),
            None, None, None, 0,
        )
        return f"{numero.value:08X}" if ok else ""
    except Exception:
        return ""


def _respaldo_no_windows() -> str:
    """Identificador estable fuera de Windows, solo para desarrollo."""
    for ruta in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            texto = Path(ruta).read_text(encoding="utf-8").strip()
            if texto:
                return texto
        except OSError:
            continue

    if platform.system() == "Darwin":
        try:
            salida = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=10,
            ).stdout
            for linea in salida.splitlines():
                if "IOPlatformUUID" in linea:
                    return linea.split('"')[-2]
        except (OSError, subprocess.SubprocessError, IndexError):
            pass

    # Último recurso. uuid.getnode() puede ser aleatorio si no encuentra
    # una MAC, pero a estas alturas ya estamos fuera de producción.
    return f"{platform.node()}:{uuid.getnode():012x}"


def partes() -> dict:
    """Las piezas en crudo, sin resumir. Solo para diagnóstico.

    Cuando un cliente dice «me cambió la huella», esto dice cuál de las
    dos piezas se movió, que es la diferencia entre un disco reformateado
    y un Windows reinstalado.
    """
    if platform.system() == "Windows":
        return {
            "machine_guid": _machine_guid(),
            "volumen_sistema": _serial_volumen_sistema(),
        }
    return {"respaldo": _respaldo_no_windows()}


def huella_equipo() -> str:
    """SHA-256 en hexadecimal de las señas del equipo.

    Si en Windows no se pudiera leer ninguna de las dos fuentes se cae al
    respaldo en vez de devolver una huella vacía: una huella vacía sería
    igual en todas las máquinas del mundo y ataría la licencia a nada.
    """
    piezas = [v for v in partes().values() if v]

    if not piezas:
        piezas = [_respaldo_no_windows()]

    crudo = _SAL + "|" + "|".join(sorted(piezas))
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()

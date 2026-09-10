"""Instalador de Race Core Studio — el que se ejecuta con doble clic.

Esto es lo que acaba siendo `rcs-setup.exe`. Parte de un Windows recién
formateado y deja el sistema funcionando, sin que nadie tenga que teclear
comandos:

    1. Licencia         se pide ANTES de descargar nada
    2. Requisitos       Python, Node, Git LFS y MongoDB, con winget
    3. Descarga         clona el repositorio con LFS
    4. Backend          entorno virtual y dependencias
    5. Panel            npm install y compilado
    6. Configuración    se lo pasa a instalar.py, que ya sabe hacerlo

La licencia va primero a propósito. Bajar medio giga y compilar durante
quince minutos para después decirle a alguien que su clave no vale es la
peor forma de gastarle la mañana.

    ⚠ Versión de PRUEBAS. La licencia se valida contra un resumen escrito
    en el propio programa, no contra el servidor de Zentogo, que todavía
    no existe. Ver installer/LEEME.md.
"""

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# El módulo de licencia viaja dentro del ejecutable: la clave se comprueba
# antes de que exista el repositorio, así que no puede salir de él.
sys.path.insert(0, str(Path(__file__).resolve().parent))

REPOSITORIO = "https://github.com/ZentogoTechnologies/Race-Core-Studio.git"
RAMA = "test-production-1.0"
DESTINO_POR_DEFECTO = Path("C:/Race-Core-Studio") if os.name == "nt" \
    else Path.home() / "Race-Core-Studio"

TOTAL = 6

ROJO, VERDE, AMARILLO, AZUL, GRIS, NEGRITA, FIN = (
    "\033[91m", "\033[92m", "\033[93m", "\033[94m", "\033[90m", "\033[1m", "\033[0m",
)


# ─── Presentación ────────────────────────────────────────────

def preparar_consola():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if os.name == "nt":
        try:
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
            k.SetConsoleOutputCP(65001)
        except Exception:
            pass


def paso(n, texto):
    print(f"\n{NEGRITA}[{n}/{TOTAL}]{FIN} {texto}")


def ok(t):      print(f"      {VERDE}OK{FIN}    {t}")
def aviso(t):   print(f"      {AMARILLO}··{FIN}    {t}")
def error(t):   print(f"      {ROJO}FALLO{FIN} {t}")
def detalle(t): print(f"            {GRIS}{t}{FIN}")


def esperar_enter(mensaje="Pulsa Enter para cerrar..."):
    """Con doble clic la ventana se cerraría de golpe sin dar tiempo a leer."""
    try:
        input(f"\n{mensaje}")
    except (EOFError, KeyboardInterrupt):
        pass


# Lo último que escribió un comando que falló. Se guarda para poder
# enseñarlo: un instalador que dice «falló» sin decir qué deja a quien lo
# ejecuta sin nada que hacer, y es justo cuando más falta hace saberlo.
_ULTIMO_ERROR = ""


def correr(comando, cwd=None, silencioso=True) -> bool:
    """Ejecuta y devuelve si salió bien. No lanza: quien llama decide."""
    global _ULTIMO_ERROR

    try:
        r = subprocess.run(
            comando, cwd=cwd, shell=isinstance(comando, str),
            capture_output=silencioso, text=True, timeout=3600,
        )
        if r.returncode != 0 and silencioso:
            _ULTIMO_ERROR = ((r.stderr or "") + (r.stdout or "")).strip()
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        _ULTIMO_ERROR = f"{type(e).__name__}: {e}"
        return False


def mostrar_error(lineas=6) -> None:
    """Las últimas líneas de lo que falló, que es donde está el motivo."""
    if not _ULTIMO_ERROR:
        return
    for linea in _ULTIMO_ERROR.splitlines()[-lineas:]:
        detalle(linea[:150])


def hay(programa: str) -> bool:
    return shutil.which(programa) is not None


# ─── 1 · Licencia ────────────────────────────────────────────

def paso_licencia(correo=None, clave=None) -> dict:
    paso(1, "Licencia")

    from licencia_local import validar

    if correo and clave:
        r = validar(correo, clave)
        if r["ok"]:
            ok(f"licencia válida para {r['correo']}")
            return r
        error(r["error"])
        raise SystemExit(1)

    print()
    for intento in range(1, 4):
        try:
            correo = input("      Correo de la licencia: ").strip()
            clave = input("      Clave (RCS1-XXXX-XXXX-XXXX-XXXX): ").strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(130)

        r = validar(correo, clave)
        if r["ok"]:
            ok(f"licencia válida para {r['correo']}")
            return r

        error(r["error"])
        if intento < 3:
            detalle(f"intento {intento} de 3")

    error("No se pudo validar la licencia. No se descarga nada.")
    raise SystemExit(1)


# ─── 2 · Requisitos ──────────────────────────────────────────

# Lo que hace falta y cómo instalarlo. winget viene de serie en Windows 11.
REQUISITOS = [
    ("git",    "Git.Git",                "Git y Git LFS"),
    ("python", "Python.Python.3.12",     "Python 3.12"),
    ("node",   "OpenJS.NodeJS.LTS",      "Node.js LTS"),
    ("mongod", "MongoDB.Server",         "MongoDB"),
]


def instalar_con_winget(paquete: str, nombre: str) -> bool:
    print(f"      instalando {nombre}…", flush=True)
    return correr(
        ["winget", "install", "--id", paquete, "--silent",
         "--accept-package-agreements", "--accept-source-agreements"],
    )


def paso_requisitos(saltar: bool) -> bool:
    paso(2, "Requisitos del sistema")

    if saltar:
        aviso("comprobación saltada por --sin-requisitos")
        return True

    if os.name != "nt":
        aviso("fuera de Windows no se instala nada solo")
        detalle("hacen falta: git+lfs, python 3.10+, node 20+, mongodb")
        return all(hay(p) for p, _, _ in REQUISITOS)

    if not hay("winget"):
        error("no encuentro winget")
        detalle("viene de serie en Windows 11. En Windows 10 se instala")
        detalle("desde la Microsoft Store, buscando «Instalador de aplicaciones»")
        return False

    faltan = []
    for programa, paquete, nombre in REQUISITOS:
        if hay(programa):
            ok(nombre)
        else:
            faltan.append((programa, paquete, nombre))

    for programa, paquete, nombre in faltan:
        if instalar_con_winget(paquete, nombre):
            ok(f"{nombre} instalado")
        else:
            error(f"no se pudo instalar {nombre}")
            detalle(f"pruébalo a mano:  winget install --id {paquete}")
            return False

    if faltan:
        # winget mete los programas nuevos en el PATH del sistema, pero
        # esta ventana ya tenía el suyo cargado desde antes: los comandos
        # nuevos no aparecen hasta abrir otra. Se recarga a mano.
        recargar_path()

    # Git LFS es aparte de Git y no se instala solo. Sin él, los binarios
    # de CasparCG llegan como punteros de texto de 132 bytes.
    if not correr(["git", "lfs", "install"]):
        error("no se pudo activar Git LFS")
        detalle("sin él, CasparCG llega como un archivo de texto y no arranca")
        return False
    ok("Git LFS activado")

    return True


def recargar_path() -> None:
    """Trae al proceso el PATH que winget acaba de cambiar.

    Sin esto habría que cerrar y reabrir la ventana, y en un instalador de
    doble clic eso significa que el cliente lo dé por roto a mitad.
    """
    if os.name != "nt":
        return

    try:
        import winreg

        partes = []
        for raiz, ruta in (
            (winreg.HKEY_LOCAL_MACHINE,
             r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, "Environment"),
        ):
            try:
                with winreg.OpenKey(raiz, ruta) as k:
                    partes.append(winreg.QueryValueEx(k, "Path")[0])
            except OSError:
                pass

        if partes:
            os.environ["PATH"] = os.pathsep.join(partes + [os.environ.get("PATH", "")])
    except Exception:
        pass


def arrancar_mongo() -> bool:
    """MongoDB tiene que estar vivo antes de instalar: el backend lo pide."""
    import socket

    def responde():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                return s.connect_ex(("127.0.0.1", 27017)) == 0
        except OSError:
            return False

    if responde():
        return True

    if os.name == "nt":
        correr(["net", "start", "MongoDB"])
        for _ in range(15):
            if responde():
                return True
            time.sleep(1)

    return responde()


# ─── 3 · Descarga ────────────────────────────────────────────

def paso_descarga(destino: Path, sin_casparcg=False) -> bool:
    paso(3, "Descargando Race Core Studio")
    detalle(f"destino: {destino}")

    if (destino / ".git").is_dir():
        ok("ya estaba descargado")
        print("      actualizando…", flush=True)
        correr(["git", "fetch", "origin", RAMA], cwd=destino)
        correr(["git", "checkout", RAMA], cwd=destino)
        correr(["git", "pull", "origin", RAMA], cwd=destino)
        correr(["git", "lfs", "pull"], cwd=destino)
        ok("actualizado")
        return verificar_casparcg(destino, sin_casparcg)

    destino.parent.mkdir(parents=True, exist_ok=True)
    print("      clonando (unos 200 MB, tarda un rato)…", flush=True)

    if not correr(["git", "clone", "-b", RAMA, REPOSITORIO, str(destino)]):
        error("no se pudo clonar el repositorio")
        detalle("comprueba la conexión, y que tengas acceso al repositorio")
        return False

    ok("descargado")

    return verificar_casparcg(destino, sin_casparcg)


def hay_git_lfs() -> bool:
    """Git LFS es una extensión aparte: `git` puede estar y `git lfs` no."""
    return correr(["git", "lfs", "version"])


def verificar_casparcg(destino: Path, permitir_sin=False) -> bool:
    """Comprueba que los binarios llegaron de verdad y no como punteros.

    Sin Git LFS, `git clone` trae los .exe y .dll de CasparCG como
    ficheros de texto de 132 bytes con un puntero dentro. Se detecta por
    el tamaño porque el error de Windows al lanzarlos no menciona LFS por
    ningún lado, y es el fallo más común de una instalación nueva.
    """
    caspar = destino / "Casparcg" / "casparcg.exe"

    if not caspar.is_file():
        aviso("no hay casparcg.exe en la descarga")
        return permitir_sin

    if caspar.stat().st_size < 100_000:
        aviso("CasparCG llegó como puntero de LFS; recuperándolo")
        correr(["git", "lfs", "pull"], cwd=destino)

    tamano = caspar.stat().st_size
    if tamano >= 100_000:
        ok(f"binarios de CasparCG verificados ({tamano / 1e6:.1f} MB)")
        return True

    # Sigue siendo un puntero. Se distingue el motivo: no es lo mismo que
    # falte la extensión que que esté y no haya traído los archivos.
    if not hay_git_lfs():
        error("Git LFS no está instalado, así que CasparCG no se descargó")
        detalle("los binarios llegaron como punteros de texto de 132 bytes")
        detalle("instálalo y vuelve a ejecutar:   winget install Git.Git")
        detalle("                                 git lfs install")
    else:
        error(f"casparcg.exe pesa {tamano} bytes: sigue siendo un puntero")
        detalle("Git LFS está pero no trajo los archivos. Prueba:")
        detalle(f"   cd {destino} && git lfs install --force && git lfs pull")

    if permitir_sin:
        aviso("se continúa sin CasparCG por --sin-casparcg")
        detalle("el panel funcionará, pero no habrá gráficos al aire")
        return True

    return False


# ─── 4 · Backend ─────────────────────────────────────────────

def python_del_entorno(raiz: Path) -> Path:
    sub = "Scripts" if os.name == "nt" else "bin"
    exe = "python.exe" if os.name == "nt" else "python"
    return raiz / "Backend" / "venv" / sub / exe


# numpy 2.5 y pandas 3.0, que están fijados en requirements.txt, exigen
# 3.12. Se comprueba antes de crear el entorno: si no, pip falla al final
# de varios minutos con un error largo que no dice que el problema sea la
# versión de Python.
PYTHON_MINIMO = (3, 12)


def _version_de(ejecutable) -> tuple | None:
    """La versión de un Python, preguntándosela a él mismo.

    Se ejecuta en vez de mirar el nombre del archivo porque en Windows
    `python` suele ser el stub de la Microsoft Store: existe, está en el
    PATH, y al llamarlo abre la tienda en vez de hacer nada. Solo cuenta
    el que sabe decir su propia versión.
    """
    orden = ejecutable if isinstance(ejecutable, list) else [ejecutable]

    try:
        r = subprocess.run(
            [*orden, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
            capture_output=True, text=True, timeout=25,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if r.returncode != 0:
        return None

    try:
        return tuple(int(n) for n in r.stdout.strip().split("."))
    except ValueError:
        return None


def python_del_sistema() -> list | None:
    """Un Python del sistema que sirva para crear el entorno virtual.

    Sin congelar es el que está ejecutando esto. Congelado no hay ninguno
    —el ejecutable lleva el suyo dentro y no sabe crear entornos— así que
    hay que encontrar el que instaló winget.

    Se prueban varios candidatos por orden. `py` es el lanzador oficial de
    Windows y es el más fiable: sabe qué versiones hay instaladas aunque
    ninguna esté en el PATH.
    """
    if not getattr(sys, "frozen", False):
        return [sys.executable]

    candidatos = [
        ["py", "-3.13"], ["py", "-3.12"], ["py", "-3"],
        ["python3"], ["python"],
    ]

    # Donde winget deja Python, por si el PATH de esta ventana no lo tiene.
    for version in ("313", "312"):
        candidatos.append([str(Path(os.environ.get("LOCALAPPDATA", "")) /
                               "Programs" / "Python" / f"Python{version}" / "python.exe")])
        candidatos.append([f"C:/Python{version}/python.exe"])

    for candidato in candidatos:
        version = _version_de(candidato)
        if version and version >= PYTHON_MINIMO:
            return candidato

    return None


def paso_backend(raiz: Path, con_recorte: bool) -> bool:
    paso(4, "Instalando el backend")

    minimo = ".".join(str(n) for n in PYTHON_MINIMO)
    base = python_del_sistema()

    if base is None:
        error(f"no encuentro un Python {minimo} o superior")
        detalle("lo exigen numpy y pandas, que van fijados en requirements.txt")
        detalle("instálalo con:  winget install Python.Python.3.12")
        detalle("y vuelve a ejecutar este instalador")
        return False

    ok(f"Python {'.'.join(str(n) for n in _version_de(base))}")

    venv = raiz / "Backend" / "venv"
    py = python_del_entorno(raiz)

    if not py.exists():
        print("      creando el entorno virtual…", flush=True)
        if not correr([*base, "-m", "venv", str(venv)]):
            error("no se pudo crear el entorno virtual")
            mostrar_error()
            return False
    ok("entorno virtual listo")

    print("      instalando dependencias (varios minutos)…", flush=True)
    correr([str(py), "-m", "pip", "install", "--upgrade", "pip", "-q"])

    requisitos = raiz / "Backend" / "requirements.txt"

    if con_recorte:
        exito = correr([str(py), "-m", "pip", "install", "-q", "-r", str(requisitos)])
    else:
        # rembg y onnxruntime son unos 200 MB y solo hacen falta para
        # recortar el fondo de las fotos. Se importan solo al usarlos, así
        # que el sistema arranca igual sin ellos.
        lineas = [l.strip() for l in requisitos.read_text(encoding="utf-8").splitlines()
                  if l.strip() and not l.startswith("#") and "rembg" not in l]
        exito = correr([str(py), "-m", "pip", "install", "-q", *lineas])

    if not exito:
        error("falló la instalación de dependencias")
        mostrar_error()
        detalle("")
        detalle(f"pruébalo a mano:  {py} -m pip install -r {requisitos}")
        return False

    ok("dependencias instaladas")
    if not con_recorte:
        detalle("sin el recorte de fondos: se añade luego con  pip install rembg[cpu]")
    return True


# ─── 5 · Panel ───────────────────────────────────────────────

def paso_panel(raiz: Path) -> bool:
    paso(5, "Compilando el panel")

    frontend = raiz / "Frontend"

    if (frontend / "dist" / "index.html").is_file():
        ok("ya estaba compilado")
        return True

    # npm es un .cmd en Windows: se invoca por cmd para que lo resuelva.
    npm = ["cmd", "/c", "npm"] if os.name == "nt" else ["npm"]

    print("      instalando dependencias del panel…", flush=True)
    if not correr([*npm, "install"], cwd=frontend):
        error("falló npm install")
        mostrar_error()
        return False

    print("      compilando…", flush=True)
    if not correr([*npm, "run", "build"], cwd=frontend):
        error("falló la compilación del panel")
        mostrar_error()
        return False

    if not (frontend / "dist" / "index.html").is_file():
        error("la compilación terminó pero no dejó el panel")
        return False

    ok("panel compilado")
    return True


# ─── 6 · Configuración ───────────────────────────────────────

def paso_configurar(raiz: Path, lic: dict, dias, abrir: bool) -> bool:
    paso(6, "Configurando")

    if not arrancar_mongo():
        error("MongoDB no responde en el 27017")
        detalle("arráncalo con:  net start MongoDB")
        return False
    ok("MongoDB respondiendo")

    py = python_del_entorno(raiz)
    orden = [str(py), str(raiz / "installer" / "instalar.py"),
             "--correo", lic["correo"], "--clave", lic["clave"]]
    if dias is not None:
        orden += ["--dias", str(dias)]
    if not abrir:
        orden.append("--no-abrir")

    print()
    # Sin capturar: instalar.py imprime su propio progreso y sus enlaces,
    # y esconderlos aquí solo dejaría la pantalla en blanco un minuto.
    return subprocess.run(orden, cwd=raiz).returncode == 0


# ─── Principal ───────────────────────────────────────────────

def main() -> int:
    preparar_consola()

    p = argparse.ArgumentParser(description="Instalador de Race Core Studio.")
    p.add_argument("--destino", type=Path, default=DESTINO_POR_DEFECTO)
    p.add_argument("--correo")
    p.add_argument("--clave")
    p.add_argument("--dias", type=int)
    p.add_argument("--con-recorte", action="store_true",
                   help="Instala rembg (+200 MB) para recortar fondos de fotos")
    p.add_argument("--sin-requisitos", action="store_true",
                   help="No comprueba ni instala Python, Node ni MongoDB")
    p.add_argument("--sin-casparcg", action="store_true",
                   help="Continúa aunque CasparCG no se haya descargado. "
                        "El panel funciona; no habrá gráficos al aire")
    p.add_argument("--no-abrir", action="store_true")
    args = p.parse_args()

    print(f"\n{NEGRITA}  RACE CORE STUDIO · INSTALADOR{FIN}")
    print(f"{GRIS}  Zentogo Technologies{FIN}")
    print(f"{AMARILLO}  Versión de pruebas: la licencia no se valida contra "
          f"el servidor todavía.{FIN}")

    try:
        lic = paso_licencia(args.correo, args.clave)

        if not paso_requisitos(args.sin_requisitos):
            raise SystemExit(1)

        destino = args.destino.resolve()

        if not paso_descarga(destino, args.sin_casparcg):
            raise SystemExit(1)
        if not paso_backend(destino, args.con_recorte):
            raise SystemExit(1)
        if not paso_panel(destino):
            raise SystemExit(1)
        if not paso_configurar(destino, lic, args.dias, not args.no_abrir):
            raise SystemExit(1)

    except SystemExit as e:
        if e.code:
            print(f"\n{ROJO}{NEGRITA}  La instalación no pudo terminar.{FIN}")
            print("  Corrige lo de arriba y vuelve a ejecutar este archivo.")
            esperar_enter()
            return e.code
        raise

    print(f"\n{VERDE}{NEGRITA}  Race Core Studio quedó instalado.{FIN}")
    print(f"""
  Carpeta    {args.destino}
  Arrancar   {NEGRITA}race-core-studio.exe{FIN}   (en esa carpeta)
""")
    esperar_enter()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        raise SystemExit(130)

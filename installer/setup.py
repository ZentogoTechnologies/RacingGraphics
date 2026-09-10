"""Instalador de Race Core Studio — el que se ejecuta con doble clic.

Esto es lo que acaba siendo `rcs-setup.exe`. Parte de un Windows recién
formateado y deja el sistema funcionando, sin que nadie tenga que teclear
comandos:

    1. Licencia         se pide ANTES de descargar nada
    2. Requisitos       Python, Node, Git LFS y MongoDB, con winget
    3. Descarga         clona el repositorio con LFS
    4. Backend          entorno virtual y dependencias
    5. Panel            npm install y compilado
    6. Lanzador         crea race-core-studio.exe
    7. Configuración    se lo pasa a instalar.py, que ya sabe hacerlo

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
import socket
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

TOTAL = 7

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
            # winget escribe en UTF-8 aunque la consola española esté en
            # cp850. Sin decirlo, sus mensajes salen como «Se encontrÃ³».
            encoding="utf-8", errors="replace",
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


# ─── Buscar un Python que sirva ──────────────────────────────

# numpy 2.5 y pandas 3.0, que están fijados en requirements.txt, exigen
# 3.12. Se comprueba en el paso 2, con todo lo demás: si se dejara para
# cuando toca instalar el backend, pip fallaría al final de varios
# minutos de descarga con un error largo que no menciona la versión.
PYTHON_MINIMO = (3, 12)


def texto_version(version) -> str:
    return ".".join(str(n) for n in version)


MINIMO_TEXTO = texto_version(PYTHON_MINIMO)


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


def candidatos_python() -> list:
    """Por dónde buscar, en orden de preferencia.

    `py` es el lanzador oficial de Windows y el más fiable: sabe qué
    versiones hay instaladas aunque ninguna esté en el PATH. Se pide 3.12
    primero por ser la que instala este mismo instalador, y por tanto
    contra la que están probadas las dependencias.
    """
    candidatos = []

    # Sin congelar, el que está ejecutando esto es el candidato natural.
    # Congelado no vale: el ejecutable lleva su Python dentro, recortado,
    # y ese no sabe crear entornos virtuales.
    if not getattr(sys, "frozen", False):
        candidatos.append([sys.executable])

    candidatos += [
        ["py", "-3.12"], ["py", "-3.13"], ["py", "-3"],
        ["python3"], ["python"],
    ]

    # Donde winget deja Python, por si el PATH de esta ventana no lo tiene.
    # Son varios sitios porque depende de si instaló para este usuario o
    # para todo el equipo, y eso cambia según se ejecute como
    # administrador o no.
    carpetas = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
        Path("C:/"),
    ]

    for version in ("312", "313"):
        for carpeta in carpetas:
            candidatos.append([str(carpeta / f"Python{version}" / "python.exe")])

    return candidatos


def revisar_python() -> tuple:
    """(intérprete que sirve, su versión). Si ninguno sirve, (None, la mejor).

    Devuelve también la versión cuando no llega al mínimo, para poder
    decir «tienes 3.11» en vez de «no tienes Python»: no es lo mismo, y
    lo segundo manda a buscar donde no es.
    """
    mejor = None

    for candidato in candidatos_python():
        version = _version_de(candidato)
        if version is None:
            continue
        if version >= PYTHON_MINIMO:
            return candidato, version
        if mejor is None or version > mejor:
            mejor = version

    return None, mejor


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
    ("python", "Python.Python.3.12",     f"Python {MINIMO_TEXTO} o superior"),
    ("node",   "OpenJS.NodeJS.LTS",      "Node.js LTS"),
    ("mongod", "MongoDB.Server",         "MongoDB"),
]


def mongod_instalado() -> Path | None:
    """Busca mongod.exe donde lo deja su instalador.

    MongoDB no se añade al PATH, así que `where mongod` no lo encuentra
    aunque esté instalado y funcionando. Buscarlo solo ahí llevaba a
    pedirle a winget que lo instalara otra vez, y winget contestaba —con
    razón, y con código de error— que ya estaba puesto.
    """
    en_path = shutil.which("mongod")
    if en_path:
        return Path(en_path)

    for base in {Path(os.environ.get("ProgramFiles", "C:/Program Files")),
                 Path("C:/Program Files")}:
        servidor = base / "MongoDB" / "Server"
        if not servidor.is_dir():
            continue
        # Pueden convivir varias versiones; vale la más nueva.
        for carpeta in sorted(servidor.iterdir(), reverse=True):
            candidato = carpeta / "bin" / "mongod.exe"
            if candidato.is_file():
                return candidato

    return None


def hay_servicio(nombre: str) -> bool:
    """Si Windows tiene registrado ese servicio, esté arrancado o no."""
    return os.name == "nt" and correr(["sc", "query", nombre])


def estado_mongodb() -> str | None:
    """MongoDB sirve si responde, o si está puesto para poder arrancarlo."""
    if mongo_responde():
        return "MongoDB en marcha"

    ruta = mongod_instalado()
    if ruta is not None:
        # Su carpeta al PATH, para que el resto lo tenga a mano.
        os.environ["PATH"] = str(ruta.parent) + os.pathsep + os.environ.get("PATH", "")
        return "MongoDB"

    # Aunque no aparezca el ejecutable, con el servicio registrado basta:
    # el paso 6 lo arranca con «net start», que es todo lo que hace falta.
    if hay_servicio("MongoDB"):
        return "MongoDB (servicio registrado)"

    return None


def estado_requisito(programa: str, nombre: str) -> str | None:
    """Lo que hay instalado y sirve, o None si hay que instalarlo.

    Cada requisito se comprueba como toca, no todos con `which`: que un
    nombre esté en el PATH no quiere decir que sirva, y que no esté no
    quiere decir que falte.
    """
    if programa == "mongod":
        return estado_mongodb()

    if programa != "python":
        return nombre if hay(programa) else None

    interprete, version = revisar_python()
    if interprete:
        return f"Python {texto_version(version)}"

    if version:
        aviso(f"hay Python {texto_version(version)}, y hace falta "
              f"{MINIMO_TEXTO} o superior")
        detalle("lo exigen numpy y pandas, que van fijados en requirements.txt")
        detalle("el 3.12 se instala al lado del que ya tienes, sin quitarlo")

    return None


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
        detalle(f"hacen falta: git+lfs, python {MINIMO_TEXTO}+, node 20+, mongodb")
        return all(estado_requisito(p, n) for p, _, n in REQUISITOS)

    if not hay("winget"):
        error("no encuentro winget")
        detalle("viene de serie en Windows 11. En Windows 10 se instala")
        detalle("desde la Microsoft Store, buscando «Instalador de aplicaciones»")
        return False

    faltan = []
    for programa, paquete, nombre in REQUISITOS:
        etiqueta = estado_requisito(programa, nombre)
        if etiqueta:
            ok(etiqueta)
        else:
            faltan.append((programa, paquete, nombre))

    for programa, paquete, nombre in faltan:
        instalado = instalar_con_winget(paquete, nombre)

        # winget mete los programas nuevos en el PATH del sistema, pero
        # esta ventana ya tenía el suyo cargado desde antes: los comandos
        # nuevos no aparecen hasta abrir otra. Se recarga a mano.
        recargar_path()

        # Manda lo que se encuentra, no lo que diga winget: unas veces
        # sale con error porque «ya estaba instalado», y otras sale bien
        # sin dejar nada que se pueda usar.
        etiqueta = estado_requisito(programa, nombre)
        if etiqueta:
            ok(f"{etiqueta} · instalado")
            continue

        error(f"no se pudo instalar {nombre}")
        if not instalado:
            mostrar_error(4)
        detalle(f"pruébalo a mano:  winget install --id {paquete}")
        detalle("si winget dice que ya estaba instalado, es que está en un")
        detalle("sitio donde este instalador no lo encuentra: manda esta")
        detalle("pantalla a soporte y lo añadimos a donde se busca")
        return False

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


def mongo_responde() -> bool:
    """Si hay algo escuchando en el puerto de MongoDB."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex(("127.0.0.1", 27017)) == 0
    except OSError:
        return False


def arrancar_mongo() -> bool:
    """MongoDB tiene que estar vivo antes de instalar: el backend lo pide."""
    if mongo_responde():
        return True

    if os.name == "nt":
        correr(["net", "start", "MongoDB"])
        for _ in range(15):
            if mongo_responde():
                return True
            time.sleep(1)

    return mongo_responde()


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


def paso_backend(raiz: Path, con_recorte: bool) -> bool:
    paso(4, "Instalando el backend")

    base, version = revisar_python()

    if base is None:
        # No debería llegarse aquí: el paso 2 lo instala. Si pasa, es que
        # winget lo dejó donde esta ventana no lo ve, y abrir otra basta.
        error(f"no encuentro un Python {MINIMO_TEXTO} o superior")
        detalle("lo exigen numpy y pandas, que van fijados en requirements.txt")
        detalle("instálalo con:  winget install Python.Python.3.12")
        detalle("y vuelve a ejecutar este instalador")
        return False

    ok(f"Python {texto_version(version)}")

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


# ─── 6 · Lanzador ────────────────────────────────────────────

def paso_lanzador(raiz: Path) -> bool:
    """Crea race-core-studio.exe, que es con lo que se usa a diario.

    El lanzador es un script de Python, y pedirle a nadie que arranque
    su sistema tecleando la ruta de un intérprete no es una opción: lo
    que tiene que haber en la carpeta es un icono que se abre con doble
    clic. Se empaqueta aquí, en el equipo, contra la copia recién
    descargada, así que siempre corresponde al código instalado.
    """
    paso(6, "Creando race-core-studio.exe")

    if os.name != "nt":
        aviso("fuera de Windows no hay .exe que crear")
        return True

    lanzador = raiz / "launcher"
    fuente = lanzador / "race_core_studio.py"
    destino = raiz / "race-core-studio.exe"

    # Se rehace cuando el lanzador ha cambiado: si no, una actualización
    # dejaría el .exe viejo arrancando código nuevo.
    if destino.is_file() and destino.stat().st_mtime >= fuente.stat().st_mtime:
        ok("ya estaba creado y al día")
        return True

    py = python_del_entorno(raiz)

    print("      preparando el empaquetador…", flush=True)
    if not correr([str(py), "-m", "pip", "install", "-q", "pyinstaller"]):
        error("no se pudo instalar PyInstaller")
        mostrar_error()
        return False

    print("      empaquetando el lanzador (un par de minutos)…", flush=True)
    if not correr([
        str(py), "-m", "PyInstaller",
        # --noupx: si UPX está en el equipo, PyInstaller comprime con él
        # sin preguntar, y un binario empaquetado con UPX es de lo que
        # más dispara a los antivirus.
        "--onefile", "--console", "--clean", "--noconfirm", "--noupx",
        "--name", "race-core-studio",
        "--icon", str(lanzador / "race-core-studio.ico"),
        "--version-file", str(lanzador / "version-info.txt"),
        "--hidden-import", "pymongo",
        "--distpath", str(lanzador / "dist"),
        "--workpath", str(lanzador / "build"),
        "--specpath", str(lanzador),
        str(fuente),
    ], cwd=raiz):
        error("falló el empaquetado del lanzador")
        mostrar_error()
        return False

    recien = lanzador / "dist" / "race-core-studio.exe"
    if not recien.is_file():
        error("el empaquetado terminó pero no dejó el ejecutable")
        return False

    # Windows bloquea el archivo mientras el lanzador esté abierto.
    correr(["taskkill", "/IM", "race-core-studio.exe", "/F"])

    try:
        shutil.copy2(recien, destino)
    except OSError as e:
        error("no se pudo dejar el ejecutable en su sitio")
        detalle(f"{type(e).__name__}: {e}")
        detalle("si Race Core Studio está abierto, ciérralo y repite")
        return False

    ok(f"race-core-studio.exe creado ({destino.stat().st_size / 1e6:.0f} MB)")
    detalle(f"está en {destino}")
    return True


# ─── 7 · Configuración ───────────────────────────────────────

def paso_configurar(raiz: Path, lic: dict, dias, abrir: bool) -> bool:
    paso(7, "Configurando")

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
        if not paso_lanzador(destino):
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

"""Instalador de Race Core Studio.

    python installer/instalar.py

Hace, en este orden:

    1. Pide correo y clave de licencia, y los valida.
    2. Calcula la huella de este equipo y emite la licencia atada a ella.
    3. Comprueba que estén MongoDB, CasparCG y el resto de piezas.
    4. Escribe la configuración: firma de sesiones propia y licencia exigida.
    5. Genera el token del asistente y abre el navegador.

    ⚠ Esta es la versión de PRUEBAS. La licencia se valida contra un
    resumen escrito en el propio programa, no contra el servidor de
    Zentogo, y la firma la pone una clave de desarrollo que viaja con el
    repositorio. Sirve para recorrer el flujo entero de punta a punta;
    no para vender.

    Lo que ya es definitivo es todo lo que va por debajo: la licencia que
    se emite aquí es la misma que emitirá el servidor, con el mismo
    formato y la misma firma Ed25519, así que la validación del backend,
    el periodo de gracia y el bloqueo al expirar se prueban de verdad.

Opciones:

    --origen local     Instala desde esta copia del repositorio (por
                       defecto, y lo único que funciona hasta que exista
                       el servidor de descargas).
    --dias N           Vigencia de la licencia. Negativo para probar el
                       vencimiento: -1 deja el sistema en gracia, -30 lo
                       deja bloqueado.
    --no-abrir         No abre el navegador al terminar.
"""

import argparse
import os
import secrets
import socket
import sys
import time
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "Backend"))
sys.path.insert(0, str(RAIZ / "tools" / "licencias"))
sys.path.insert(0, str(Path(__file__).parent))

ROJO, VERDE, AMARILLO, AZUL, GRIS, NEGRITA, FIN = (
    "\033[91m", "\033[92m", "\033[93m", "\033[94m", "\033[90m", "\033[1m", "\033[0m",
)

TOTAL_PASOS = 5


# ─── Presentación ────────────────────────────────────────────

def preparar_consola():
    """Acentos y colores en la consola de Windows."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
            k.SetConsoleOutputCP(65001)
        except Exception:
            pass


def paso(n, texto):
    print(f"\n{NEGRITA}[{n}/{TOTAL_PASOS}]{FIN} {texto}")


def ok(t):      print(f"      {VERDE}OK{FIN}    {t}")
def aviso(t):   print(f"      {AMARILLO}··{FIN}    {t}")
def error(t):   print(f"      {ROJO}FALLO{FIN} {t}")
def detalle(t): print(f"            {GRIS}{t}{FIN}")


def preguntar(etiqueta, por_defecto=""):
    sufijo = f" [{por_defecto}]" if por_defecto else ""
    try:
        valor = input(f"      {etiqueta}{sufijo}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(130)
    return valor or por_defecto


# ─── 1. Licencia ─────────────────────────────────────────────

def paso_licencia(dias_forzados=None) -> dict:
    paso(1, "Licencia")

    from licencia_local import validar

    # Tres intentos y no infinitos: si la clave no entra, el problema no
    # se arregla tecleando más veces, y dejar el instalador colgado en un
    # bucle no ayuda a nadie.
    for intento in range(1, 4):
        correo = preguntar("Correo de la licencia")
        clave = preguntar("Clave (RCS1-XXXX-XXXX-XXXX-XXXX)")

        resultado = validar(correo, clave)

        if resultado["ok"]:
            ok(f"licencia válida para {resultado['correo']}")
            if dias_forzados is not None:
                resultado["dias"] = dias_forzados
                aviso(f"vigencia forzada a {dias_forzados} días (modo prueba)")
            return resultado

        error(resultado["error"])
        if intento < 3:
            detalle(f"intento {intento} de 3")

    error("No se pudo validar la licencia.")
    raise SystemExit(1)


# ─── 2. Emitir para este equipo ──────────────────────────────

def paso_emitir(lic: dict) -> str:
    paso(2, "Atando la licencia a este equipo")

    from src.services.fingerprint_services import huella_equipo, partes

    huella = huella_equipo()
    ok(f"huella {huella[:24]}…")
    for nombre, valor in partes().items():
        detalle(f"{nombre}: {valor}")

    claves = RAIZ / "claves-desarrollo"
    privada = claves / "licencias-privada.pem"

    if not privada.is_file():
        aviso("no hay claves de desarrollo; generándolas")
        import subprocess
        subprocess.run(
            [sys.executable, str(RAIZ / "tools" / "licencias" / "claves.py"),
             "--salida", str(claves), "--nombre", "licencias"],
            check=True, capture_output=True,
        )
        # La pública tiene que quedar dentro del backend, que es de donde
        # la lee para verificar.
        subprocess.run(
            [sys.executable, str(RAIZ / "tools" / "licencias" / "licencia_de_prueba.py"),
             "--dias", "1"],
            check=True, capture_output=True,
        )

    from emitir import emitir

    token, _ = emitir(
        privada_pem=privada.read_text(encoding="utf-8"),
        producto="race-core-studio",
        cliente="Instalación de prueba",
        correo=lic["correo"],
        equipo=huella,
        dias=lic["dias"],
        plan=lic["plan"],
        version_max="1.0.0",
        gracia_dias=lic["gracia_dias"],
        revalidar_dias=7,
    )

    destino = RAIZ / "Backend" / "licencia.lic"
    destino.write_text(token, encoding="utf-8")

    from src.services import license_services as slic

    slic.limpiar_cache()
    estado = slic.verificar_token(token)

    color = VERDE if estado.opera else ROJO
    ok(f"licencia emitida · estado {color}{estado.estado.value}{FIN}")
    detalle(f"vence {estado.vence:%d/%m/%Y} · {estado.dias_restantes} días")
    if estado.estado.value == "gracia":
        detalle(f"en gracia: quedan {estado.dias_de_gracia_restantes} días")

    return token


# ─── 3. Comprobaciones ───────────────────────────────────────

def puerto_abierto(puerto, host="127.0.0.1", espera=0.6) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(espera)
            return s.connect_ex((host, puerto)) == 0
    except OSError:
        return False


def paso_comprobar(origen: str) -> bool:
    paso(3, "Comprobando lo que hace falta")

    todo_bien = True

    piezas = [
        ("Backend", RAIZ / "Backend" / "main.py", True),
        ("CasparCG", RAIZ / "Casparcg" / "casparcg.exe", os.name == "nt"),
        ("Plantillas", RAIZ / "Casparcg" / "template" / "html", True),
        ("XML de demostración",
         RAIZ / "Backend" / "src" / "public" / "demo" / "current.demo.xml", True),
    ]

    for nombre, ruta, obligatorio in piezas:
        if ruta.exists():
            ok(nombre)
        elif obligatorio:
            error(f"falta {nombre}")
            detalle(f"esperaba: {ruta}")
            todo_bien = False
        else:
            aviso(f"{nombre} no está (solo hace falta en Windows)")

    # El frontend compilado. Sin él el backend sirve solo el API, así que
    # es un aviso y no un fallo: se puede compilar después.
    if (RAIZ / "Frontend" / "dist" / "index.html").is_file():
        ok("Frontend compilado")
    else:
        aviso("Frontend sin compilar")
        detalle("compílalo con:  npm install --prefix Frontend && npm run build --prefix Frontend")

    # MongoDB tiene que estar vivo: el backend lo necesita al arrancar.
    if puerto_abierto(27017):
        ok("MongoDB respondiendo en el 27017")
    else:
        error("MongoDB no responde en el 27017")
        detalle("si está instalado como servicio:  net start MongoDB")
        todo_bien = False

    if puerto_abierto(5250):
        ok("CasparCG respondiendo en el 5250")
    else:
        aviso("CasparCG no responde todavía (se arranca aparte)")

    return todo_bien


# ─── 4. Configuración ────────────────────────────────────────

def paso_configurar() -> None:
    paso(4, "Escribiendo la configuración")

    env = RAIZ / "Backend" / ".env"
    lineas = {}

    if env.is_file():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                clave, _, valor = linea.partition("=")
                lineas[clave.strip()] = valor.strip()
        aviso(".env ya existía: se conservan los valores puestos a mano")

    # La firma de sesiones se genera por instalación. Si todas
    # compartieran la misma, cualquiera que conociera la cadena podría
    # firmarse un token válido para el sistema de cualquier cliente.
    if not lineas.get("JWT_SECRET") or "cambiar" in lineas.get("JWT_SECRET", ""):
        lineas["JWT_SECRET"] = secrets.token_urlsafe(48)
        ok("firma de sesiones generada al azar")
    else:
        detalle("firma de sesiones: se conserva la que ya había")

    lineas.setdefault("MONGO_URI", "mongodb://localhost:27017")
    lineas.setdefault("DB_NAME", "race-core-studio")

    # 0.0.0.0 para poder operar el panel desde otro equipo o un iPad.
    lineas["API_HOST"] = "0.0.0.0"
    lineas["API_PORT"] = "8080"

    # A partir de aquí, sin licencia no se opera.
    lineas["LICENSE_REQUIRED"] = "true"

    # Hasta que se configure la ruta real de MyLaps, el XML de
    # demostración deja el sistema utilizable desde el primer arranque.
    lineas.setdefault(
        "TIMING_XML_PATH",
        str(RAIZ / "Backend" / "src" / "public" / "demo" / "current.demo.xml"),
    )

    env.write_text(
        "# Escrito por el instalador de Race Core Studio.\n"
        "# La firma de los tokens es de esta instalación: no se comparte.\n\n"
        + "\n".join(f"{k}={v}" for k, v in lineas.items()) + "\n",
        encoding="utf-8",
    )
    ok(f"{env}")
    detalle("licencia exigida · API en 0.0.0.0:8080")


# ─── 5. Asistente ────────────────────────────────────────────

def paso_asistente(abrir: bool) -> None:
    paso(5, "Asistente de instalación")

    from src.services.instalacion_services import crear_token

    token = crear_token()
    ok("token del asistente generado")
    detalle("protege el asistente mientras dure la instalación: sin él,")
    detalle("cualquiera de la red local podría nombrarse dueño del sistema")

    from src.services.red_services import direcciones

    d = direcciones()
    url = f"{d['local']}/instalacion?token={token}"

    print()
    print(f"  {NEGRITA}Abre el asistente en:{FIN}")
    print(f"    {AZUL}{url}{FIN}")
    if d["red"]:
        print(f"\n  Desde otro equipo o un iPad de la misma red:")
        print(f"    {AZUL}{d['red']}/instalacion?token={token}{FIN}")

    if abrir:
        try:
            webbrowser.open(url)
        except Exception:
            aviso("no se pudo abrir el navegador solo; entra a mano")


# ─── Principal ───────────────────────────────────────────────

def main() -> int:
    preparar_consola()

    p = argparse.ArgumentParser(description="Instalador de Race Core Studio.")
    p.add_argument("--origen", default="local", choices=["local"],
                   help="De dónde salen los componentes. Solo 'local' hasta "
                        "que exista el servidor de descargas.")
    p.add_argument("--dias", type=int, default=None,
                   help="Vigencia. Negativo para probar el vencimiento.")
    p.add_argument("--no-abrir", action="store_true")
    args = p.parse_args()

    print(f"\n{NEGRITA}  RACE CORE STUDIO · INSTALADOR{FIN}")
    print(f"{GRIS}  {RAIZ}{FIN}")
    print(f"{AMARILLO}  Versión de pruebas: la licencia no se valida contra el "
          f"servidor todavía.{FIN}")

    lic = paso_licencia(args.dias)
    paso_emitir(lic)

    if not paso_comprobar(args.origen):
        print(f"\n{ROJO}{NEGRITA}  Faltan piezas.{FIN} Resuelve lo de arriba y "
              f"vuelve a ejecutar.\n")
        return 1

    paso_configurar()
    paso_asistente(not args.no_abrir)

    print(f"\n{VERDE}{NEGRITA}  Instalación lista.{FIN}")
    print(f"""
  Arranca el sistema con:   {NEGRITA}race-core-studio.exe{FIN}
  o a mano:                 {GRIS}Backend\\venv\\Scripts\\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8080{FIN}
""")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        raise SystemExit(130)

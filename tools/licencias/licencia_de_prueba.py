"""Emite una licencia de prueba para ESTE equipo, en un solo comando.

    python tools/licencias/licencia_de_prueba.py

Hace todo lo que hace falta para poder probar el sistema con licencia:

    1. Genera un par de claves de desarrollo, si no existe ya.
    2. Escribe la clave pública dentro de license_services.py.
    3. Calcula la huella de este equipo.
    4. Emite una licencia a su nombre y la guarda en Backend/licencia.lic

Después de esto, poner LICENSE_REQUIRED=true en el .env hace que el
backend arranque exigiendo licencia, y la de prueba la satisface.

Para ver cómo se comporta al vencer, que es lo que más conviene probar:

    --dias -1     ya venció, pero dentro de la gracia: sigue operando
    --dias -30    pasada la gracia: bloquea los gráficos

⚠ Las claves que genera esto son de DESARROLLO. No sirven para vender:
antes de la primera venta hay que generar el par de producción con
claves.py, guardarlo donde solo esté el servidor de licencias, y poner
esa pública en license_services.py.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CLAVES = RAIZ / "claves-desarrollo"
PRIVADA = CLAVES / "licencias-privada.pem"
PUBLICA = CLAVES / "licencias-publica.pem"
SERVICIO = RAIZ / "Backend" / "src" / "services" / "license_services.py"
LICENCIA = RAIZ / "Backend" / "licencia.lic"

sys.path.insert(0, str(RAIZ / "Backend"))
sys.path.insert(0, str(Path(__file__).parent))


def paso(n, texto):
    print(f"\n[{n}/4] {texto}")


def generar_claves() -> None:
    paso(1, "Claves de desarrollo")

    if PRIVADA.is_file():
        print(f"      ya existían en {CLAVES}")
        return

    subprocess.run(
        [sys.executable, str(Path(__file__).parent / "claves.py"),
         "--salida", str(CLAVES), "--nombre", "licencias"],
        check=True, capture_output=True,
    )
    print(f"      generadas en {CLAVES}")


def instalar_publica() -> None:
    """Mete la pública en el código, que es de donde la lee el backend."""
    paso(2, "Clave pública dentro de license_services.py")

    pem = PUBLICA.read_text(encoding="utf-8").strip()
    texto = SERVICIO.read_text(encoding="utf-8")

    actual = re.search(
        r'CLAVE_PUBLICA_PEM = """(.*?)"""', texto, re.DOTALL
    )
    if actual and actual.group(1).strip() == pem:
        print("      ya estaba puesta")
        return

    SERVICIO.write_text(
        re.sub(r'CLAVE_PUBLICA_PEM = """.*?"""',
               f'CLAVE_PUBLICA_PEM = """{pem}"""',
               texto, flags=re.DOTALL),
        encoding="utf-8",
    )
    print("      instalada (clave de DESARROLLO, no de producción)")


def main() -> int:
    p = argparse.ArgumentParser(description="Licencia de prueba de este equipo.")
    p.add_argument("--dias", type=int, default=365,
                   help="Días de vigencia. Negativo = ya vencida.")
    p.add_argument("--plan", default="pro")
    p.add_argument("--cliente", default="Instalación de prueba")
    p.add_argument("--correo", default="prueba@racecorestudio.com")
    p.add_argument("--gracia-dias", type=int, default=15)
    args = p.parse_args()

    generar_claves()
    instalar_publica()

    paso(3, "Huella de este equipo")
    # Se importa aquí y no arriba: instalar_publica() reescribe el módulo,
    # y hay que leerlo después de haberlo cambiado.
    from src.services.fingerprint_services import huella_equipo, partes

    huella = huella_equipo()
    print(f"      {huella}")
    for nombre, valor in partes().items():
        print(f"        {nombre}: {valor}")

    paso(4, "Emitiendo la licencia")
    from emitir import emitir

    token, carga = emitir(
        privada_pem=PRIVADA.read_text(encoding="utf-8"),
        producto="race-core-studio",
        cliente=args.cliente,
        correo=args.correo,
        equipo=huella,
        dias=args.dias,
        plan=args.plan,
        version_max="1.0.0",
        gracia_dias=args.gracia_dias,
        revalidar_dias=7,
    )

    LICENCIA.write_text(token, encoding="utf-8")
    print(f"      escrita en {LICENCIA}")

    from src.services import license_services as lic

    lic.limpiar_cache()
    estado = lic.verificar_token(token)

    print(f"\n  Estado : {estado.estado.value}")
    print(f"  Opera  : {'sí' if estado.opera else 'NO'}")
    print(f"  Cliente: {estado.cliente}")
    print(f"  Vence  : {estado.vence:%d/%m/%Y}  ({estado.dias_restantes} días)")
    if estado.estado is lic.Estado.GRACIA:
        print(f"  Gracia : quedan {estado.dias_de_gracia_restantes} días")

    print("\n  Para que el backend la exija, en Backend/.env:")
    print("      LICENSE_REQUIRED=true\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

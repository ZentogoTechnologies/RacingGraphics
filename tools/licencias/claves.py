"""Genera el par de claves Ed25519 de Zentogo.

    python tools/licencias/claves.py --salida claves/

Produce dos archivos:

    privada.pem   Firma las licencias. Vive SOLO en el servidor de
                  licencias. No se sube al repositorio, no se manda por
                  correo y no se guarda en la máquina de nadie.
    publica.pem   Se copia dentro de license_services.py, en el backend.

Quien tenga la privada puede emitir licencias perpetuas para cualquier
equipo. Si alguna vez se filtra, hay que generar un par nuevo y sacar una
versión del backend con la clave pública nueva: las licencias viejas
dejan de verificar, así que habría que reemitirlas todas.

Se usan dos pares distintos, uno para licencias y otro para releases
(ver manifiesto.py). Así, comprometer el que firma las descargas no
permite además fabricar licencias, ni al revés.
"""

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def generar(destino: Path, nombre: str) -> None:
    destino.mkdir(parents=True, exist_ok=True)

    privada = Ed25519PrivateKey.generate()

    pem_privada = privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_publica = privada.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    archivo_privada = destino / f"{nombre}-privada.pem"
    archivo_publica = destino / f"{nombre}-publica.pem"

    archivo_privada.write_bytes(pem_privada)
    archivo_publica.write_bytes(pem_publica)

    # Solo el dueño puede leer la privada. En Windows esto no hace nada,
    # pero el servidor de licencias corre en Linux y ahí sí cuenta.
    try:
        archivo_privada.chmod(0o600)
    except OSError:
        pass

    print(f"Privada : {archivo_privada}   ← NO se comparte, no va a git")
    print(f"Pública : {archivo_publica}")
    print()
    print("Copia esto dentro de license_services.py (CLAVE_PUBLICA_PEM):")
    print()
    print(pem_publica.decode("utf-8").strip())


def main() -> int:
    p = argparse.ArgumentParser(description="Genera el par Ed25519 de Zentogo.")
    p.add_argument("--salida", type=Path, default=Path("claves"))
    p.add_argument(
        "--nombre",
        default="licencias",
        help="licencias | releases (pares distintos, ver el docstring)",
    )
    args = p.parse_args()

    generar(args.salida, args.nombre)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

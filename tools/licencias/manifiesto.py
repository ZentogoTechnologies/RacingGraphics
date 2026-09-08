"""Construye y firma el manifiesto de una versión.

El manifiesto es la única fuente de verdad sobre qué compone una versión
de un producto: qué archivos, de dónde se bajan, cuánto pesan y qué hash
tienen. El instalador lo lee para instalar, y también para actualizar; no
hay una segunda lista en ningún otro sitio que se pueda desincronizar.

    # Construir a partir de una carpeta de artefactos ya subidos
    python tools/licencias/manifiesto.py construir \
        --producto race-core-studio --version 1.2.0 \
        --base-url https://descargas.zentogo.com/race-core-studio/1.2.0 \
        --artefactos dist/1.2.0 \
        --privada claves/releases-privada.pem \
        --salida dist/1.2.0/manifiesto.json

    # Verificar (lo mismo que hace el instalador antes de fiarse)
    python tools/licencias/manifiesto.py verificar \
        --manifiesto dist/1.2.0/manifiesto.json \
        --publica claves/releases-publica.pem

La firma va en un archivo aparte (`manifiesto.sig`) y no envuelta en un
JWT. El motivo es práctico: el instalador de Windows puede acabar escrito
en C#, en Pascal de Inno Setup o en Python, y comprobar una firma Ed25519
sobre unos bytes es de una línea en cualquiera de los tres, mientras que
interpretar un JWT obliga a arrastrar una librería. Además, así el
manifiesto se puede abrir y leer con cualquier editor.

Se firma sobre JSON canónico —claves ordenadas, sin espacios— para que
los bytes firmados sean siempre los mismos. Sin eso, volver a serializar
el mismo contenido con otra librería cambiaría un espacio y la firma
dejaría de cuadrar.
"""

import argparse
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# Orden en que el instalador tiene que poner las cosas. CasparCG y
# MongoDB van primero porque el backend, al arrancar por primera vez,
# necesita la base viva; y el frontend va al final porque se compila
# contra un backend que ya debe existir.
ORDEN = ["casparcg", "mongodb", "backend", "frontend"]


def canonico(datos: dict) -> bytes:
    """Los bytes exactos que se firman y se verifican."""
    return json.dumps(
        datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_archivo(ruta: Path) -> tuple[str, int]:
    """Hash y tamaño, leyendo por trozos.

    Por trozos y no de una vez porque el paquete de CasparCG ronda los
    80 MB y no tiene sentido cargarlo entero en memoria para resumirlo.
    """
    h = hashlib.sha256()
    total = 0

    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
            total += len(bloque)

    return h.hexdigest(), total


def construir(
    producto: str,
    version: str,
    base_url: str,
    artefactos: Path,
    minimo_actualizable: str,
    notas: str,
) -> dict:
    componentes = []

    for archivo in sorted(artefactos.iterdir()):
        if not archivo.is_file() or archivo.name.startswith("manifiesto"):
            continue

        # El id sale del nombre del archivo: casparcg-2.4.3.zip -> casparcg
        ident = archivo.stem.split("-")[0].lower()
        digest, bytes_ = sha256_archivo(archivo)

        componentes.append({
            "id": ident,
            "archivo": archivo.name,
            "url": f"{base_url.rstrip('/')}/{archivo.name}",
            "sha256": digest,
            "bytes": bytes_,
            "orden": ORDEN.index(ident) if ident in ORDEN else len(ORDEN),
        })

    componentes.sort(key=lambda c: (c["orden"], c["id"]))

    return {
        "producto": producto,
        "version": version,
        "publicado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Por debajo de esta versión no se actualiza en el sitio: hay que
        # reinstalar. Sirve para poder hacer un cambio incompatible sin
        # dejar a nadie con una instalación a medias.
        "minimo_actualizable": minimo_actualizable,
        "notas": notas,
        "componentes": componentes,
    }


def firmar(manifiesto: dict, privada_pem: bytes) -> str:
    clave = serialization.load_pem_private_key(privada_pem, password=None)
    if not isinstance(clave, Ed25519PrivateKey):
        raise SystemExit("La clave privada no es Ed25519.")

    return base64.b64encode(clave.sign(canonico(manifiesto))).decode("ascii")


def verificar(manifiesto: dict, firma_b64: str, publica_pem: bytes) -> bool:
    clave = serialization.load_pem_public_key(publica_pem)
    if not isinstance(clave, Ed25519PublicKey):
        raise SystemExit("La clave pública no es Ed25519.")

    try:
        clave.verify(base64.b64decode(firma_b64), canonico(manifiesto))
        return True
    except (InvalidSignature, ValueError):
        return False


def _construir(args) -> int:
    manifiesto = construir(
        producto=args.producto,
        version=args.version,
        base_url=args.base_url,
        artefactos=args.artefactos,
        minimo_actualizable=args.minimo_actualizable,
        notas=args.notas or "",
    )

    if not manifiesto["componentes"]:
        raise SystemExit(f"No hay artefactos en {args.artefactos}")

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    # Se escribe legible para poder revisarlo, pero la firma va sobre la
    # forma canónica, no sobre estos bytes con sangrías.
    args.salida.write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    firma = firmar(manifiesto, args.privada.read_bytes())
    archivo_firma = args.salida.with_suffix(".sig")
    archivo_firma.write_text(firma + "\n", encoding="utf-8")

    peso = sum(c["bytes"] for c in manifiesto["componentes"])
    print(f"{args.producto} {args.version}")
    for c in manifiesto["componentes"]:
        print(f"  {c['orden']}. {c['id']:<10} {c['bytes'] / 1e6:8.1f} MB  {c['sha256'][:16]}…")
    print(f"  {'total':<13} {peso / 1e6:8.1f} MB")
    print()
    print(f"Manifiesto : {args.salida}")
    print(f"Firma      : {archivo_firma}")
    return 0


def _verificar(args) -> int:
    manifiesto = json.loads(args.manifiesto.read_text(encoding="utf-8"))
    firma = args.manifiesto.with_suffix(".sig").read_text(encoding="utf-8").strip()

    if verificar(manifiesto, firma, args.publica.read_bytes()):
        print(f"Firma válida: {manifiesto['producto']} {manifiesto['version']}")
        return 0

    print("FIRMA INVÁLIDA. No instalar nada de este manifiesto.")
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description="Manifiestos de versión de Zentogo.")
    sub = p.add_subparsers(dest="comando", required=True)

    c = sub.add_parser("construir")
    c.add_argument("--producto", default="race-core-studio")
    c.add_argument("--version", required=True)
    c.add_argument("--base-url", required=True)
    c.add_argument("--artefactos", type=Path, required=True)
    c.add_argument("--privada", type=Path, required=True)
    c.add_argument("--salida", type=Path, required=True)
    c.add_argument("--minimo-actualizable", default="1.0.0")
    c.add_argument("--notas", default="")
    c.set_defaults(func=_construir)

    v = sub.add_parser("verificar")
    v.add_argument("--manifiesto", type=Path, required=True)
    v.add_argument("--publica", type=Path, required=True)
    v.set_defaults(func=_verificar)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

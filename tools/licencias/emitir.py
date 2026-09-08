"""Emite una licencia de un producto de Zentogo para un equipo.

    python tools/licencias/emitir.py \
        --privada claves/licencias-privada.pem \
        --producto race-core-studio \
        --cliente "Autódromo Panamá" \
        --correo pablo@autodromopanama.com \
        --equipo e56a66e9...  \
        --meses 12

El `--equipo` es la huella que reporta la máquina del cliente. La calcula
el instalador y la manda al servidor al activar; también se puede leer en
el panel, en Ajustes → Licencia.

Esto es la referencia del formato. El servidor de licencias hará lo mismo
desde su API, pero teniendo el script se puede emitir a mano cuando haga
falta —una demo, una prórroga de urgencia un domingo de carrera— sin
depender de que el servidor esté en pie.
"""

import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

EMISOR = "zentogo-licencias"
ALGORITMO = "EdDSA"

# Planes y qué habilita cada uno. Las features viajan dentro del token
# firmado, así que el cliente no las puede ampliar editando un archivo.
PLANES = {
    "basico": ["graficos", "pilotos", "vehiculos", "categorias"],
    "pro": ["graficos", "pilotos", "vehiculos", "categorias", "eventos", "clima", "drag"],
    "demo": ["graficos", "pilotos", "vehiculos", "categorias"],
}


def emitir(
    privada_pem: str,
    producto: str,
    cliente: str,
    correo: str,
    equipo: str,
    dias: int,
    plan: str,
    version_max: str,
    gracia_dias: int,
    revalidar_dias: int,
) -> tuple[str, dict]:
    ahora = datetime.now(timezone.utc)
    vence = ahora + timedelta(days=dias)

    payload = {
        # Estándar
        "iss": EMISOR,
        "jti": str(uuid.uuid4()),
        "iat": int(ahora.timestamp()),
        "nbf": int(ahora.timestamp()),
        "exp": int(vence.timestamp()),

        # De Zentogo
        "producto": producto,
        "cliente": cliente,
        "correo": correo,
        "equipo": equipo,
        "plan": plan,
        "features": PLANES.get(plan, PLANES["basico"]),
        "version_max": version_max,

        # Cuánto aguanta después de vencer antes de bloquear, y cada
        # cuánto conviene que el software intente revalidar en línea.
        # Revalidar nunca es obligatorio: si no hay red, no pasa nada.
        "gracia_dias": gracia_dias,
        "revalidar_dias": revalidar_dias,
    }

    token = jwt.encode(payload, privada_pem, algorithm=ALGORITMO)
    return token, payload


def main() -> int:
    p = argparse.ArgumentParser(description="Emite una licencia de Zentogo.")
    p.add_argument("--privada", type=Path, required=True)
    p.add_argument("--producto", default="race-core-studio")
    p.add_argument("--cliente", required=True)
    p.add_argument("--correo", required=True)
    p.add_argument("--equipo", required=True, help="Huella SHA-256 del equipo")
    p.add_argument("--plan", default="pro", choices=sorted(PLANES))
    p.add_argument("--version-max", default="1.2.0")
    p.add_argument("--gracia-dias", type=int, default=15)
    p.add_argument("--revalidar-dias", type=int, default=7)
    p.add_argument("--salida", type=Path, help="Archivo .lic a escribir")

    grupo = p.add_mutually_exclusive_group()
    grupo.add_argument("--dias", type=int)
    grupo.add_argument("--meses", type=int)

    args = p.parse_args()

    dias = args.dias if args.dias else (args.meses or 12) * 30

    token, payload = emitir(
        privada_pem=args.privada.read_text(encoding="utf-8"),
        producto=args.producto,
        cliente=args.cliente,
        correo=args.correo,
        equipo=args.equipo,
        dias=dias,
        plan=args.plan,
        version_max=args.version_max,
        gracia_dias=args.gracia_dias,
        revalidar_dias=args.revalidar_dias,
    )

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print()

    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(token, encoding="utf-8")
        print(f"Licencia escrita en {args.salida}")
    else:
        print(token)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

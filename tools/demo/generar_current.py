"""Genera un current.xml de demostración, con datos ficticios.

MyLaps reescribe constantemente un `current.xml` con la clasificación en
vivo. Sin ese archivo no hay gráficos, y eso deja tres situaciones
incómodas donde hace falta uno de mentira:

  · **Instalando.** El asistente pide la ruta del current.xml del equipo
    de cronometraje. Para poder decir «esta ruta funciona» hay que tener
    algo con qué comparar, y el día de la instalación puede que MyLaps ni
    esté encendido.

  · **Demostrando.** Enseñar el producto, entrenar a un operador o
    revisar una plantilla nueva no puede depender de que haya carrera.

  · **Desarrollando y probando.** Hoy la ruta por defecto apunta a una
    unidad de red; quien no la tenga montada no puede tocar el módulo de
    cronometraje ni correr una prueba.

Los nombres son deliberadamente inconfundibles —PILOTO DEMO 01— y no
nombres plausibles. Si este archivo llegara a salir al aire por error en
una carrera de verdad, tiene que notarse en el primer segundo. Un dato
falso que parece real es peor que no tener dato.

    # El archivo que se distribuye
    python tools/demo/generar_current.py --salida Backend/src/public/demo/current.demo.xml

    # Una carrera que avanza sola, para probar plantillas y gráficos
    python tools/demo/generar_current.py --salida /tmp/current.xml --vivo
"""

import argparse
import random
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# Se marca en todos lados. Si esto sale al aire, que no haya duda.
EVENTO = "EVENTO DE DEMOSTRACION - RACE CORE STUDIO"
PISTA = "CIRCUITO DEMO"
CATEGORIA = "9 - CATEGORIA DEMO"
CLASE = "DEMO A"

# Vuelta de referencia, en segundos. Alrededor de esto se reparten los
# tiempos de cada piloto para que la tabla se parezca a una tanda real.
VUELTA_BASE = 76.0


def crono(segundos: float) -> str:
    """Formato de MyLaps: 1:16.364 y, por debajo del minuto, 47.221."""
    # Sin relleno de ceros por delante: MyLaps escribe "0.885", no
    # "00.885". La diferencia importa porque las plantillas pintan esta
    # cadena tal cual sale, y un cero de más se ve al aire.
    if segundos < 60:
        return f"{segundos:.3f}"

    minutos = int(segundos // 60)
    return f"{minutos}:{segundos - minutos * 60:06.3f}"


def reloj(segundos: float) -> str:
    """mm:ss, como el racetime del XML."""
    return f"{int(segundos // 60)}:{int(segundos % 60):02d}"


def diferencia(segundos: float | None, vueltas_abajo: int) -> str:
    """La diferencia contra el líder.

    A un coche doblado MyLaps no le pone segundos, le pone "1 Lap". El
    parser trata ese caso aparte, así que la demo tiene que incluirlo:
    si no, ese camino del código no se ejercita nunca.
    """
    if vueltas_abajo == 1:
        return "1 Lap"
    if vueltas_abajo > 1:
        return f"{vueltas_abajo} Laps"
    if segundos is None or segundos <= 0:
        return ""
    return crono(segundos)


def pilotos(cuantos: int, vuelta_actual: int, semilla: int) -> list[dict]:
    """Arma la clasificación. Determinista para una semilla dada."""
    rnd = random.Random(semilla)
    filas = []
    acumulado = 0.0

    for i in range(cuantos):
        # Cada piloto es un poco más lento que el anterior, con ruido.
        ritmo = VUELTA_BASE + i * 0.42 + rnd.uniform(-0.18, 0.18)
        mejor = ritmo - rnd.uniform(0.3, 1.1)

        # Los últimos van doblados, como en cualquier tanda real.
        vueltas_abajo = 0
        if cuantos > 8 and i >= cuantos - 2:
            vueltas_abajo = 1

        if i > 0:
            acumulado += rnd.uniform(0.4, 2.6) + i * 0.05

        filas.append({
            "pos": i + 1,
            "no": str(11 + i * 3),
            "nombre": f"PILOTO DEMO {i + 1:02d}",
            "ritmo": ritmo,
            "mejor": mejor,
            "ultima": ritmo + rnd.uniform(-0.25, 0.25),
            "dif": None if i == 0 else acumulado,
            "gap": None if i == 0 else rnd.uniform(0.3, 2.2),
            "vueltas": vuelta_actual - vueltas_abajo,
            "vueltas_abajo": vueltas_abajo,
            "mejor_en": rnd.randint(2, max(2, vuelta_actual)),
            "vel": 3600 * 2.5 / ritmo,
        })

    return filas


def construir(cuantos: int, vuelta_actual: int, total_vueltas: int,
              semilla: int, tanda: str, tipo: str) -> ET.Element:
    filas = pilotos(cuantos, vuelta_actual, semilla)
    lider = filas[0]

    # El más rápido de la tanda, que puede no ser el líder.
    rapido = min(filas, key=lambda f: f["mejor"])

    raiz = ET.Element("resultspage", {
        # En el XML real aquí va el correo del usuario de MyLaps. En la
        # demo va una dirección de ejemplo: no se distribuye la de nadie.
        "user": "demo@racecorestudio.com",
        "view": "lgView_RunInfo",
    })

    etiquetas = {
        "bestlapby": f"{rapido['no']} - {rapido['nombre']}",
        "bestlaptime": crono(rapido["mejor"]),
        "eventname": EVENTO,
        "flag": "none",
        "groupname": CATEGORIA,
        "laps": str(vuelta_actual),
        "lapstogo": str(max(0, total_vueltas - vuelta_actual)),
        "leader": f"{lider['no']} - {lider['nombre']}",
        "leaderavgspeed": f"{lider['vel']:.3f}",
        "leadermargin": crono(filas[1]["gap"]) if len(filas) > 1 else "",
        "racetime": reloj(vuelta_actual * VUELTA_BASE),
        "runname": tanda,
        "runtype": tipo,
        "timeofday": time.strftime("%H:%M:%S"),
        "timetogo": "",
        "tracklength": "2.500",
        "trackname": PISTA,
    }

    for tipo_etiqueta, valor in etiquetas.items():
        ET.SubElement(raiz, "label", {"type": tipo_etiqueta}).text = valor

    resultados = ET.SubElement(raiz, "results")
    ET.SubElement(resultados, "columns", {
        "marker": "", "position": "", "no": "", "transponder": "",
        "firstname": "", "lastname": "", "fullname": "", "class": "",
    })

    for i, f in enumerate(filas):
        # MyLaps mete el nombre completo en firstname y deja lastname
        # vacío. En los carros compartidos parte la cadena por donde cae,
        # y el parser tiene código para eso. La demo reproduce ese caso en
        # un piloto para que ese camino se ejercite.
        if i == 5 and cuantos > 6:
            nombre, apellido = f"{f['nombre']} /PILOTO", "DEMO COMPARTIDO"
            completo = f"{f['nombre']} /PILOTO DEMO COMPARTIDO"
        else:
            nombre, apellido, completo = f["nombre"], "", f["nombre"]

        ET.SubElement(resultados, "result", {
            "marker": str(i + 1),
            "position": str(f["pos"]),
            "positioninclass": str(f["pos"]),
            "no": f["no"],
            "transponder": f"9{900000 + i * 137:06d}",
            "regnumber": f"demo{i:04d}",
            "firstname": nombre,
            "lastname": apellido,
            "fullname": completo,
            "class": CLASE,
            "laps": str(f["vueltas"]),
            "difference": diferencia(f["dif"], f["vueltas_abajo"]),
            "gap": diferencia(f["gap"], f["vueltas_abajo"]),
            "lasttime": crono(f["ultima"]),
            "besttime": crono(f["mejor"]),
            "bestinlap": str(f["mejor_en"]),
            "bestspeed": f"{3600 * 2.5 / f['mejor']:.3f}",
            "lastspeed": f"{3600 * 2.5 / f['ultima']:.3f}",
            "averagespeed": f"{f['vel']:.3f}",
            "averagetime": crono(f["ritmo"]),
            "totaltime": crono(f["vueltas"] * f["ritmo"]),
            "lasttimeline": "Start/Finish",
            "lasttimeofday": time.strftime("%H:%M:%S.000"),
            "lastpitstop": "0",
            "nopitstops": "",
            "sincepit": str(f["vueltas"]),
            "secondbesttime": crono(f["mejor"] + 0.31),
            "secondbestinlap": str(max(1, f["mejor_en"] - 1)),
            "secondbestspeed": f"{3600 * 2.5 / (f['mejor'] + 0.31):.3f}",
            "secondlasttime": crono(f["ultima"] + 0.22),
            "thirdlasttime": crono(f["ultima"] + 0.44),
            # additional4 lleva el país, igual que en el XML real.
            "additional1": "", "additional2": "", "additional3": "",
            "additional4": "PAN",
            "additional5": "", "additional6": "", "additional7": "",
            "additional8": "",
            **{f"section{n}": "" for n in range(10)},
            **{f"bestsection{n}": "" for n in range(10)},
        })

    return raiz


def escribir(raiz: ET.Element, salida: Path) -> None:
    """Escritura atómica.

    MyLaps reescribe el archivo constantemente y el backend lo lee a la
    vez; el parser ya contempla pillarlo a medias. Aquí se escribe a un
    temporal y se reemplaza de golpe para que la demo no reproduzca ese
    problema encima de los que se estén buscando.
    """
    salida.parent.mkdir(parents=True, exist_ok=True)
    temporal = salida.with_suffix(salida.suffix + ".tmp")

    ET.ElementTree(raiz).write(temporal, encoding="utf-8", xml_declaration=True)
    temporal.replace(salida)


def main() -> int:
    p = argparse.ArgumentParser(description="current.xml de demostración.")
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--pilotos", type=int, default=12)
    p.add_argument("--vuelta", type=int, default=7, help="Vuelta en curso")
    p.add_argument("--total-vueltas", type=int, default=12)
    p.add_argument("--tanda", default="Heat 1")
    p.add_argument("--tipo", default="R", help="R heat · Q qualy · P práctica")
    p.add_argument("--semilla", type=int, default=7)
    p.add_argument(
        "--vivo", action="store_true",
        help="Reescribe el archivo cada pocos segundos simulando una carrera "
             "en marcha. Sirve para probar plantillas y gráficos de verdad.",
    )
    p.add_argument("--intervalo", type=float, default=3.0)
    args = p.parse_args()

    if not args.vivo:
        escribir(construir(args.pilotos, args.vuelta, args.total_vueltas,
                           args.semilla, args.tanda, args.tipo), args.salida)
        print(f"{args.salida}  ·  {args.pilotos} pilotos, vuelta "
              f"{args.vuelta}/{args.total_vueltas}")
        return 0

    print(f"Carrera de demostración en {args.salida}")
    print(f"{args.pilotos} pilotos · una vuelta cada {args.intervalo}s · Ctrl+C para parar\n")

    vuelta = 1
    try:
        while vuelta <= args.total_vueltas:
            escribir(construir(args.pilotos, vuelta, args.total_vueltas,
                               args.semilla + vuelta, args.tanda, args.tipo),
                     args.salida)
            print(f"  vuelta {vuelta}/{args.total_vueltas}")
            vuelta += 1
            time.sleep(args.intervalo)
        print("\nCarrera terminada.")
    except KeyboardInterrupt:
        print("\nDetenida.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

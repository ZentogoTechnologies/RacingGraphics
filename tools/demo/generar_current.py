"""Genera el current-demo.xml, con datos inventados pero completos.

MyLaps reescribe constantemente un `current.xml` con la clasificación en
vivo. Sin ese archivo no hay gráficos, y eso deja tres situaciones donde
hace falta uno de mentira:

  · **Instalando.** El asistente pide la ruta del current.xml del equipo
    de cronometraje. Para poder decir «esta ruta funciona» hay que tener
    algo con qué comparar, y el día de la instalación puede que MyLaps ni
    esté encendido.

  · **Demostrando.** Enseñar el producto, entrenar a un operador o
    revisar una plantilla nueva no puede depender de que haya carrera.

  · **Desarrollando y probando.** Sin esto, quien no tenga montada la
    unidad de red del cronometraje no puede tocar el módulo ni correr una
    prueba.

Los pilotos son inventados. Los nombres son verosímiles a propósito —una
tabla con «PILOTO 01» no sirve para enseñarle el producto a nadie— pero
**el evento se llama EVENTO DE DEMOSTRACION**, y esa es la salvaguarda:
si esto llegara a salir al aire por error, el rótulo del evento lo canta
aunque los nombres parezcan reales.

Reproduce el esquema completo de MyLaps y, a propósito, los casos raros
que el parser trata aparte:

    · Una **penalización**, que es el más sutil (ver abajo).
    · Un **coche doblado**, con "1 Lap" en vez de un tiempo.
    · Un **carro compartido**, con el nombre partido entre firstname y
      lastname por donde cayó.
    · El **líder sin diferencia**, con el campo vacío.

    # El archivo que se distribuye
    python tools/demo/generar_current.py

    # Una carrera que avanza sola, para probar plantillas y gráficos
    python tools/demo/generar_current.py --salida C:/timing/current.xml --vivo
"""

import argparse
import random
import time
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "Backend" / "src" / "public" / "demo" / "current-demo.xml"

# Se marca el evento, no a los pilotos. Ver el docstring.
EVENTO = "EVENTO DE DEMOSTRACION - RACE CORE STUDIO"
PISTA = "CIRCUITO DEMO"
CATEGORIA = "9 - CATEGORIA DEMO"
CLASE = "DEMO A"

VUELTA_BASE = 76.0
LARGO_PISTA = 2.500     # km, para las velocidades

# ── Los pilotos ───────────────────────────────────────────────
# Inventados: nombre, dorsal, marca y modelo, país y equipo. Todos con la
# ficha completa, porque una tabla a medias no sirve para revisar cómo
# quedan las plantillas.
#
# El orden de esta lista es el ritmo, no la clasificación: quien va
# primero aquí es el más rápido en pista. La clasificación sale después,
# y en ella la penalización mueve a uno de sitio.
PILOTOS = [
    ("MATIAS OLIVARES",    "29", "HONDA CIVIC TYPE R",   "PAN", "OLIVARES RACING"),
    ("BRUNO SALCEDO",      "14", "SUBARU WRX STI",       "PAN", "SALCEDO MOTORSPORT"),
    ("IGNACIO REVILLA",    "07", "MITSUBISHI EVO X",     "CRI", "REVILLA COMPETICION"),
    ("TOMAS ECHENIQUE",    "23", "TOYOTA SUPRA MK4",     "PAN", "ECHENIQUE RACING"),
    ("JAVIER ARISMENDI",   "41", "NISSAN SILVIA S15",    "COL", "ARISMENDI TEAM"),
    ("RODRIGO VALLEJO",    "88", "BMW M3 E46",           "PAN", "VALLEJO SPORT"),
    ("SEBASTIAN QUIROGA",  "52", "HONDA INTEGRA TYPE R", "MEX", "QUIROGA RACING"),
    ("ANDRES LINARES",     "16", "VOLKSWAGEN GOLF GTI",  "PAN", "LINARES MOTORS"),
    ("FELIPE ZAMBRANO",    "33", "MAZDA RX-7 FD",        "VEN", "ZAMBRANO RACING"),
    ("GONZALO PERALTA",    "05", "AUDI S3 8V",           "ESP", "PERALTA COMPETICION"),
    ("MARTIN CASTELLANOS", "77", "SUBARU IMPREZA GC8",   "PAN", "CASTELLANOS TEAM"),
    ("EMILIO BARRANTES",   "62", "HONDA CIVIC EK9",      "CRI", "BARRANTES RACING"),
    ("NICOLAS ARRIAGA",    "11", "FORD FOCUS RS",        "PAN", "ARRIAGA MOTORSPORT"),
    ("DIEGO MONTALVO",     "45", "MITSUBISHI EVO IX",    "MEX", "MONTALVO RACING"),
    ("PABLO ITURBE",       "19", "TOYOTA COROLLA AE86",  "PAN", "ITURBE CLASSIC"),
    ("SANTIAGO REBOLLEDO", "08", "NISSAN 350Z",          "COL", "REBOLLEDO SPORT"),
    ("LEANDRO VILLAGRA",   "27", "BMW 328i E36",         "PAN", "VILLAGRA RACING"),
    ("CRISTOBAL AMADOR",   "36", "HONDA S2000",          "USA", "AMADOR MOTORS"),
    ("ALEJANDRO PONCE",    "54", "SEAT LEON CUPRA",      "ESP", "PONCE COMPETICION"),
    ("MAURICIO ESQUIVEL",  "12", "HYUNDAI VELOSTER N",   "CRI", "ESQUIVEL RACING"),
    ("VALENTIN OYARZUN",   "71", "SUBARU BRZ",           "PAN", "OYARZUN TEAM"),
    ("HERNAN CALDERON",    "03", "MAZDA MX-5 NC",        "PAN", "CALDERON SPORT"),
    ("JULIAN MENDIETA",    "49", "VOLKSWAGEN JETTA GLI", "MEX", "MENDIETA RACING"),
    ("RAMIRO ASTUDILLO",   "66", "HONDA ACCORD CL7",     "VEN", "ASTUDILLO MOTORS"),
    ("BENJAMIN URRUTIA",   "21", "TOYOTA CELICA GT4",    "PAN", "URRUTIA RACING"),
    ("FACUNDO LARREA",     "58", "NISSAN 240SX",         "COL", "LARREA SPORT"),
    ("ESTEBAN GAMBOA",     "94", "FORD FIESTA ST",       "CRI", "GAMBOA TEAM"),
    ("LUCAS MIRAMONTES",   "37", "PEUGEOT 208 GTI",      "PAN", "MIRAMONTES RACING"),
    ("ADRIAN CEBALLOS",    "82", "RENAULT MEGANE RS",    "ESP", "CEBALLOS MOTORS"),
    ("IVAN PORTOCARRERO",  "09", "CHEVROLET CAMARO SS",  "PAN", "PORTOCARRERO SPORT"),
]

# ── La penalización ───────────────────────────────────────────
#
# MyLaps NO manda ninguna marca de penalización: no existe un campo que
# diga «a este le cayeron diez segundos». Lo que pasa es esto:
#
#   MyLaps calcula `difference` contra el coche MÁS RÁPIDO, no contra
#   quien va primero en la clasificación. Con una sanción esos dos dejan
#   de ser el mismo. Entonces el sancionado —que es el más rápido— queda
#   como referencia con la diferencia VACÍA, y es al primero de la
#   clasificación a quien MyLaps le pone un tiempo.
#
# Reproducirlo aquí es lo único que ejercita `_reencuadrar_diferencias`,
# que es la función más delicada del módulo de cronometraje. Sin este
# caso en la demo, ese camino no se prueba nunca.
#
# Diez segundos, que es una sanción de las corrientes. Se la lleva el
# MÁS RÁPIDO, y para que la firma aparezca tiene que caer exactamente al
# puesto 2: si cayera al 5º ya no sería la referencia de MyLaps y el
# efecto se perdería. Por eso los tres de cabeza llevan hueco propio (ver
# HUECO_CABEZA): con seis segundos entre ellos, diez de sanción dejan al
# sancionado justo entre el primero y el tercero.
SANCION_SEGUNDOS = 10.0

# Segundos por vuelta que separan a los tres primeros entre sí. Un líder
# destacado no es raro en una tanda de club, y aquí además hace falta
# para que la sanción caiga donde tiene que caer.
HUECO_CABEZA = 0.90


def crono(segundos: float) -> str:
    """Formato de MyLaps: 1:16.364 y, por debajo del minuto, 0.885.

    Sin cero a la izquierda: MyLaps escribe 0.885, no 00.885, y las
    plantillas pintan la cadena tal cual.
    """
    if segundos < 60:
        return f"{segundos:.3f}"

    minutos = int(segundos // 60)
    return f"{minutos}:{segundos - minutos * 60:06.3f}"


def reloj(segundos: float) -> str:
    return f"{int(segundos // 60)}:{int(segundos % 60):02d}"


def velocidad(tiempo_vuelta: float) -> str:
    return f"{LARGO_PISTA / tiempo_vuelta * 3600:.3f}"


def clasificacion(vuelta: int, semilla: int) -> list[dict]:
    """Arma la tanda. Determinista para una semilla dada."""
    rnd = random.Random(semilla)
    filas = []

    for i, (nombre, dorsal, coche, pais, equipo) in enumerate(PILOTOS):
        # Cada uno un poco más lento que el anterior, con ruido. Los tres
        # de cabeza van más separados a propósito, para que la sanción
        # mueva al primero un solo puesto y no cinco.
        if i < 3:
            ritmo = VUELTA_BASE + i * HUECO_CABEZA
        else:
            ritmo = VUELTA_BASE + 2 * HUECO_CABEZA + (i - 2) * 0.34
        ritmo += rnd.uniform(-0.06, 0.06)
        mejor = ritmo - rnd.uniform(0.25, 0.95)
        ultima = ritmo + rnd.uniform(-0.20, 0.20)

        # Los tres últimos van doblados, como en cualquier tanda real.
        abajo = 1 if i >= len(PILOTOS) - 3 else 0

        filas.append({
            "nombre": nombre, "dorsal": dorsal, "coche": coche,
            "pais": pais, "equipo": equipo,
            "ritmo": ritmo, "mejor": mejor, "ultima": ultima,
            "vueltas": vuelta - abajo, "abajo": abajo,
            "mejor_en": rnd.randint(2, max(2, vuelta)),
            "total": (vuelta - abajo) * ritmo,
        })

    # La sanción se le aplica al más rápido: es lo que hace que el primero
    # de la clasificación y la referencia de MyLaps dejen de ser el mismo,
    # que es exactamente la situación que produce la firma.
    sancionado = filas[0]
    sancionado["sancionado"] = True
    sancionado["total_con_sancion"] = sancionado["total"] + SANCION_SEGUNDOS

    # La clasificación ordena por el tiempo con sanción aplicada.
    orden = sorted(
        filas,
        key=lambda f: (-f["vueltas"], f.get("total_con_sancion", f["total"])),
    )

    # ── Las diferencias, como las escribiría MyLaps ──
    # La referencia es el MÁS RÁPIDO por tiempo real, no el primero.
    referencia = min(orden, key=lambda f: f["total"] / max(1, f["vueltas"]))

    for puesto, f in enumerate(orden, start=1):
        f["posicion"] = puesto

        if f["abajo"]:
            f["difference"] = f"{f['abajo']} Lap" + ("s" if f["abajo"] > 1 else "")
            f["gap"] = f["difference"]
            continue

        if f is referencia:
            # El sancionado es la referencia: MyLaps le deja el campo
            # vacío. Es justo lo que hace que la penalización se note.
            f["difference"] = ""
        else:
            f["difference"] = crono(f["total"] - referencia["total"])

    # El intervalo de MyLaps es contra quien va delante en SU orden.
    anterior = None
    for f in orden:
        if f["abajo"]:
            anterior = f
            continue
        if anterior is None or anterior["abajo"]:
            f["gap"] = ""
        else:
            f["gap"] = crono(abs(f["total"] - anterior["total"]))
        anterior = f

    return orden


def construir(vuelta: int, total_vueltas: int, semilla: int,
              tanda: str, tipo: str, bandera: str) -> ET.Element:
    filas = clasificacion(vuelta, semilla)
    lider = filas[0]
    rapido = min(filas, key=lambda f: f["mejor"])

    raiz = ET.Element("resultspage", {
        # En el XML real aquí va el correo del usuario de MyLaps. Aquí una
        # dirección de ejemplo: no se distribuye la de nadie.
        "user": "demo@racecorestudio.com",
        "view": "lgView_RunInfo",
    })

    etiquetas = {
        "bestlapby": f"{rapido['dorsal']} - {rapido['nombre']}",
        "bestlaptime": crono(rapido["mejor"]),
        "eventname": EVENTO,
        "flag": bandera,
        "groupname": CATEGORIA,
        "laps": str(vuelta),
        "lapstogo": str(max(0, total_vueltas - vuelta)),
        "leader": f"{lider['dorsal']} - {lider['nombre']}",
        "leaderavgspeed": velocidad(lider["ritmo"]),
        "leadermargin": filas[1]["gap"] if len(filas) > 1 else "",
        "racetime": reloj(vuelta * VUELTA_BASE),
        "runname": tanda,
        "runtype": tipo,
        "timeofday": time.strftime("%H:%M:%S"),
        "timetogo": "",
        "tracklength": f"{LARGO_PISTA:.3f}",
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
        # y el parser tiene código para eso: la demo lo reproduce en uno.
        if f["posicion"] == 6:
            nombre = f"{f['nombre']} /LUCIANO"
            apellido = "FERREYRA"
            completo = f"{f['nombre']} /LUCIANO FERREYRA"
        else:
            nombre, apellido, completo = f["nombre"], "", f["nombre"]

        ET.SubElement(resultados, "result", {
            "marker": str(i + 1),
            "position": str(f["posicion"]),
            "positioninclass": str(f["posicion"]),
            "no": f["dorsal"],
            "transponder": f"{9100000 + i * 4177:07d}",
            "regnumber": f"{abs(hash(f['nombre'])) % 0xFFFFFFFF:08x}",
            "firstname": nombre,
            "lastname": apellido,
            "fullname": completo,
            "class": CLASE,
            "laps": str(f["vueltas"]),
            "difference": f["difference"],
            "gap": f["gap"],
            "lasttime": crono(f["ultima"]),
            "besttime": crono(f["mejor"]),
            "bestinlap": str(f["mejor_en"]),
            "bestspeed": velocidad(f["mejor"]),
            "lastspeed": velocidad(f["ultima"]),
            "averagespeed": velocidad(f["ritmo"]),
            "averagetime": crono(f["ritmo"]),
            "totaltime": crono(f["total"]),
            "lasttimeline": "Start/Finish",
            "lasttimeofday": time.strftime("%H:%M:%S.000"),
            "lastpitstop": "0",
            "nopitstops": "",
            "sincepit": str(f["vueltas"]),
            "secondbesttime": crono(f["mejor"] + 0.287),
            "secondbestinlap": str(max(1, f["mejor_en"] - 1)),
            "secondbestspeed": velocidad(f["mejor"] + 0.287),
            "secondlasttime": crono(f["ultima"] + 0.194),
            "thirdlasttime": crono(f["ultima"] + 0.371),
            # additional4 es el país y additional6 la marca y modelo,
            # igual que en el XML real del autódromo.
            "additional1": f["equipo"],
            "additional2": "", "additional3": "",
            "additional4": f["pais"],
            "additional5": "",
            "additional6": f["coche"],
            "additional7": "", "additional8": "",
            **{f"section{n}": "" for n in range(10)},
            **{f"bestsection{n}": "" for n in range(10)},
        })

    return raiz


def escribir(raiz: ET.Element, salida: Path) -> None:
    """Escritura atómica.

    MyLaps reescribe el archivo constantemente y el backend lo lee a la
    vez; el parser ya contempla pillarlo a medias. Aquí se escribe a un
    temporal y se reemplaza de golpe, para que la demo no reproduzca ese
    problema encima de los que se estén buscando.
    """
    salida.parent.mkdir(parents=True, exist_ok=True)
    temporal = salida.with_suffix(salida.suffix + ".tmp")

    ET.ElementTree(raiz).write(temporal, encoding="utf-8", xml_declaration=True)
    temporal.replace(salida)


def main() -> int:
    p = argparse.ArgumentParser(description="current-demo.xml de demostración.")
    p.add_argument("--salida", type=Path, default=DESTINO)
    p.add_argument("--vuelta", type=int, default=7, help="Vuelta en curso")
    p.add_argument("--total-vueltas", type=int, default=12)
    p.add_argument("--tanda", default="Heat 1")
    p.add_argument("--tipo", default="R", help="R heat · Q qualy · P práctica")
    p.add_argument("--bandera", default="none",
                   help="none · green · yellow · red · finish")
    p.add_argument("--semilla", type=int, default=7)
    p.add_argument("--vivo", action="store_true",
                   help="Reescribe el archivo simulando una carrera en marcha.")
    p.add_argument("--intervalo", type=float, default=3.0)
    args = p.parse_args()

    if not args.vivo:
        escribir(construir(args.vuelta, args.total_vueltas, args.semilla,
                           args.tanda, args.tipo, args.bandera), args.salida)
        print(f"{args.salida}")
        print(f"  {len(PILOTOS)} pilotos · vuelta {args.vuelta}/{args.total_vueltas}")
        return 0

    print(f"Carrera de demostración en {args.salida}")
    print(f"{len(PILOTOS)} pilotos · una vuelta cada {args.intervalo}s · Ctrl+C para parar\n")

    vuelta = 1
    try:
        while vuelta <= args.total_vueltas:
            escribir(construir(vuelta, args.total_vueltas, args.semilla + vuelta,
                               args.tanda, args.tipo, args.bandera), args.salida)
            print(f"  vuelta {vuelta}/{args.total_vueltas}")
            vuelta += 1
            time.sleep(args.intervalo)
        print("\nCarrera terminada.")
    except KeyboardInterrupt:
        print("\nDetenida.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Validación de la clave de licencia, sin servidor.

Esto es el sustituto provisional del servidor de licencias, para poder
probar el instalador de punta a punta antes de que ese servidor exista.

Cómo funciona: la clave que compra el cliente NO está en el código. Lo
que está es el SHA-256 de la combinación correo + clave. Al escribirlas,
se vuelve a calcular el resumen y se compara. Quien lea este archivo ve
un hash, y de un hash no se saca la clave.

    ⚠ Esto NO es protección contra alguien decidido. Quien tenga el
    ejecutable puede parchear la comprobación y saltársela. Sirve para
    que la clave no viaje en claro y para probar el flujo completo; la
    protección de verdad llega cuando el servidor emita las licencias y
    firme cada una contra la huella del equipo que la pidió.

Lo que sí es definitivo es lo que viene después: validada la clave, se
emite la MISMA licencia firmada en Ed25519 que emitirá el servidor, atada
a este equipo. Todo lo que va por debajo —la validación offline del
backend, el periodo de gracia, el bloqueo al expirar— funciona ya igual
que en producción. Cuando exista el servidor, solo cambia quién firma.
"""

import hashlib
import hmac
import re

# Sal del resumen. No es un secreto: está para que dos productos de
# Zentogo con la misma clave den huellas distintas.
SAL = "race-core-studio-licencia-v1"

# Correo autorizado. Provisional: cuando el servidor emita licencias, el
# correo saldrá de la compra y no de aquí.
CORREO_AUTORIZADO = "zentogotech@gmail.com"

# SHA-256 de  SAL|correo|clave.  La clave no aparece por ningún lado.
HUELLA_CLAVE = "6d34afa3d7b7b664613b44a4fa288115009ec37911cd9b35f2503db9190db5c2"

# Formato de la clave: RCS1 y cuatro grupos de cuatro. El alfabeto omite
# los caracteres que se confunden al dictar por teléfono: nada de 0 y O,
# ni 1 con I o L, ni 5 con S, ni 8 con B.
ALFABETO = "ACDEFGHJKMNPQRTUVWXY2346789"
FORMATO = re.compile(rf"^RCS1(-[{ALFABETO}]{{4}}){{4}}$")

# Vigencia que se le da a la licencia emitida en local.
DIAS = 365
GRACIA_DIAS = 15


def normalizar(clave: str) -> str:
    """Deja la clave como se guardó, perdonando lo que no importa.

    La gente la teclea en minúsculas, con espacios en vez de guiones o
    pegada de un correo con saltos de línea. Nada de eso debería ser un
    error de licencia.
    """
    limpia = re.sub(r"[\s\-_]+", "", (clave or "").upper())

    if limpia.startswith("RCS1"):
        cuerpo = limpia[4:]
        grupos = [cuerpo[i:i + 4] for i in range(0, len(cuerpo), 4)]
        return "RCS1-" + "-".join(g for g in grupos if g)

    return limpia


def normalizar_correo(correo: str) -> str:
    return (correo or "").strip().lower()


def validar(correo: str, clave: str) -> dict:
    """Comprueba correo y clave. Devuelve el motivo exacto si falla.

    Los mensajes distinguen entre formato equivocado y clave que no
    corresponde, porque son dos problemas distintos para quien instala:
    uno se arregla mirando lo que tecleó, el otro llamando a soporte.
    """
    correo = normalizar_correo(correo)
    clave = normalizar(clave)

    if not correo:
        return {"ok": False, "motivo": "falta_correo",
                "error": "Escribe el correo con el que compraste la licencia."}

    if "@" not in correo or "." not in correo.split("@")[-1]:
        return {"ok": False, "motivo": "correo_invalido",
                "error": "Ese correo no parece válido."}

    if not clave:
        return {"ok": False, "motivo": "falta_clave",
                "error": "Escribe la clave de licencia."}

    if not FORMATO.match(clave):
        return {"ok": False, "motivo": "formato",
                "error": "La clave tiene el formato RCS1-XXXX-XXXX-XXXX-XXXX. "
                         "Revisa lo que escribiste."}

    calculada = hashlib.sha256(f"{SAL}|{correo}|{clave}".encode()).hexdigest()

    # compare_digest y no ==, para que el tiempo que tarda en fallar no
    # delate cuántos caracteres se acertaron.
    if not hmac.compare_digest(calculada, HUELLA_CLAVE):
        # Se responde lo mismo tanto si el correo no cuadra como si la
        # clave no cuadra: decir cuál de los dos falló le regala a quien
        # prueba la mitad del problema.
        return {"ok": False, "motivo": "no_corresponde",
                "error": "El correo y la clave no corresponden a una licencia "
                         "válida. Revísalos o escribe a soporte."}

    return {
        "ok": True,
        "correo": correo,
        "clave": clave,
        "dias": DIAS,
        "gracia_dias": GRACIA_DIAS,
        "plan": "pro",
    }

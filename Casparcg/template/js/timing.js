/* ==========================================================================
   CRONOMETRAJE EN VIVO

   Las plantillas no leen el current.xml: lo lee el backend y lo sirve ya
   limpio en /api/v1/timing/current. Dos motivos:

     - CEF bloquea que una pagina file:// lea otro archivo local, y la
       plantilla se carga como file://. En cambio si puede pedir http://.
     - MyLaps manda los nombres sin separar ("IAN SEBASTIAN LEON" entero
       en firstname) y los carros compartidos vienen partidos por donde
       cae. El backend los cruza por numero de carro contra la base y
       devuelve el nombre bien escrito, con acentos.

   Uso desde una plantilla:

       arrancarTiming({
           limite: 10,
           alRecibir: (datos) => { ... pintar ... }
       });
========================================================================== */

var TIMING_API = "http://127.0.0.1:8080/api/v1";

/* Cada cuanto se le pregunta al backend. El reloj de carrera avanza por
   segundos, asi que medio segundo va sobrado y no satura nada: el backend
   cachea la lectura del archivo de red. */
var TIMING_INTERVALO_MS = 500;

var _timingTimer = null;
var _timingUltimo = null;


/* CasparCG puede cambiar la direccion del backend con
   CG ... UPDATE 1 "{\"api\":\"http://otra-maquina:8080/api/v1\"}" */
function configurarTiming(api) {
    if (api) TIMING_API = api;
}


function timingUltimo() {
    return _timingUltimo;
}


async function _pedir(limite) {
    const url = TIMING_API + "/timing/current?limit=" + limite;

    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);

    return r.json();
}


/**
 * Arranca el bucle de consulta.
 *
 * Se encadena con setTimeout en vez de setInterval para que una respuesta
 * lenta no acumule peticiones encima. Si el backend falla se conserva lo
 * ultimo bueno en pantalla: en directo es preferible un dato de hace un
 * segundo a un totem en blanco.
 */
function arrancarTiming(opciones) {
    const limite = opciones.limite || 10;
    const cada = opciones.cada || TIMING_INTERVALO_MS;

    detenerTiming();

    let vivo = true;

    async function ciclo() {
        if (!vivo) return;

        try {
            const datos = await _pedir(limite);
            _timingUltimo = datos;
            if (opciones.alRecibir) opciones.alRecibir(datos);
        } catch (e) {
            if (opciones.alFallar) opciones.alFallar(e);
        }

        if (vivo) _timingTimer = setTimeout(ciclo, cada);
    }

    ciclo();

    _timingTimer = _timingTimer || true;
    detenerTiming._parar = function () { vivo = false; };
}


function detenerTiming() {
    if (detenerTiming._parar) {
        detenerTiming._parar();
        detenerTiming._parar = null;
    }
    if (_timingTimer && _timingTimer !== true) clearTimeout(_timingTimer);
    _timingTimer = null;
}


/* ==========================================================================
   AYUDAS DE PINTADO
========================================================================== */

/* Comparar antes de tocar el DOM: el bucle corre dos veces por segundo y
   rehacer las filas cada vez provoca parpadeo y tira el render de CEF. */
function timingFirma(standings, campos) {
    return standings.map(function (s) {
        return campos.map(function (c) { return s[c]; }).join("|");
    }).join("~");
}

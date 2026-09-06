/* ==========================================================================
   TORRE DE CLASIFICACIÓN

   Los cuatro tótems —nombre completo, nombre corto, al líder e intervalo—
   son la misma torre con distinta configuración. Antes cada uno llevaba su
   copia del mismo código, y por eso el rediseño se quedó a medias: se hizo
   en el de nombre completo y los otros tres siguieron con el diseño viejo.

   Aquí vive todo lo común. Cada plantilla solo declara en qué se diferencia:

       arrancarTorre({
           columna: "leader",       // qué diferencia se muestra, si alguna
           etiqueta: "LÍDER",       // qué pone en la fila del primero
           marca: false,            // logo de la marca del carro
           dorsalIzquierda: true,   // el dorsal ocupa el sitio del logo
           retraso: 0,              // segundos de nombre completo; 0 = corto
       });

   Depende de timing.js, que es quien consulta al backend.
========================================================================== */


/* Las banderas de MyLaps al color de la banda superior. */
const TORRE_BANDERAS = {
    red:        { clase: "roja",     texto: "BANDERA ROJA · SESIÓN DETENIDA" },
    yellow:     { clase: "amarilla", texto: "BANDERA AMARILLA" },
    green:      { clase: "verde",    texto: "PISTA VERDE" },
    white:      { clase: "blanca",   texto: "ÚLTIMA VUELTA" },
    checkered:  { clase: "cuadros",  texto: "BANDERA A CUADROS" },
    finish:     { clase: "cuadros",  texto: "FIN DE CARRERA" },
};


let torreConfig = {
    limite: 20,
    retraso: 6,
    columna: null,
    etiqueta: "",
    marca: true,
    dorsalIzquierda: false,

    // Si el desplegable de la vuelta rápida está abierto. Lo manda la
    // interfaz con un UPDATE; no se abre solo.
    mejorVuelta: false,

    /* El recuadro morado de la vuelta rápida, pegado al canto derecho.
       Encendido de fábrica: es un dato de la tanda y estaba siempre. Se
       apaga desde el panel cuando el arte de al lado estorba. */
    crono: true,

    // Dorsal de un segundo piloto del que también se abre su franja, en
    // verde. Sirve para comparar dos tiempos en pantalla a la vez.
    comparar: null,
};

let torreCuerpo = null;
let torreElemento = null;
let torreTemporizador = null;
let torreFirma = null;

/* Se levanta cuando la comparación la acaba de cambiar alguien desde el
   panel, para que el repintado abra la franja verde con animación en vez
   de dejarla puesta ya abierta. */
let torreAnimarComparar = false;

/* La entrada por fases solo corre una vez, al sacar el totem al aire. Los
   repintados posteriores —entra un piloto, cambia el orden— no vuelven a
   armarlo: seria un parpadeo cada vez que se mueve la clasificacion. */
let torreEntrada = { hecha: false, corriendo: false, relojes: [] };


function torreEscapar(texto){

    /* Los nombres salen de la base y del XML de MyLaps. Un apellido con un
       & o un < rompería el innerHTML de la fila. */

    return String(texto == null ? "" : texto)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}


function torreLetra(caracter, fuera){

    /* Cada letra va en su propia caja para poder quitarle el ancho sin
       tocar a las demás: al encogerse, las que quedan se corren solas
       hacia la izquierda. */

    return `<span class="tf-ch${fuera ? " tf-fuera" : ""}">${torreEscapar(caracter)}</span>`;
}


function torreNombre(piloto){

    /* ENRIQUE NORIEGA -> E. NOR

       Se conservan la inicial del nombre, un punto que aparece al abreviar,
       el espacio y las tres primeras letras del apellido. El resto se marca
       para desaparecer.

       Se usan `name` y `last_name` por separado y no `full_name`: partir la
       cadena entera fallaría con apellidos compuestos como DE GRACIA, donde
       el espacio del medio no separa nombre de apellido. */

    const nombre   = String(piloto.name || "").toUpperCase();
    const apellido = String(piloto.last_name || "").toUpperCase();

    /* Sin apellido no hay nada que abreviar: se deja el texto tal cual. */
    if (!apellido) {
        return [...(piloto.full_name || "")].map(c => torreLetra(c, false)).join("");
    }

    let html = "";

    /* Inicial del nombre, y detrás el punto oculto. */
    if (nombre) {
        html += torreLetra(nombre[0], false);
        html += `<span class="tf-ch tf-punto">.</span>`;
        html += [...nombre.slice(1)].map(c => torreLetra(c, true)).join("");
    }

    html += torreLetra(" ", false);

    /* Un apellido compuesto se deja entero: ALAN DE GRACIA abreviado a las
       tres primeras letras daba "A. DE", que no dice quién es. La partícula
       sola no identifica a nadie, y hay varios "DE" en la parrilla.

       Se detecta por el espacio y no por una lista de partículas: así vale
       igual para DE GRACIA que para JEAN FRANCOIS, donde lo que sigue no es
       una partícula sino otro apellido. */
    if (apellido.includes(" ")) {
        html += [...apellido].map(c => torreLetra(c, false)).join("");
        return html;
    }

    /* Tres primeras del apellido, igual que el abbr_name del backend, para
       que todos los tótems digan exactamente lo mismo. */
    html += [...apellido.slice(0, 3)].map(c => torreLetra(c, false)).join("");
    html += [...apellido.slice(3)].map(c => torreLetra(c, true)).join("");

    return html;
}


/* Cronómetro al final del nombre del que tiene la vuelta rápida.

   Va dibujado y no como carácter: los emojis de reloj se ven distintos en
   cada máquina y no se pueden teñir. Este hereda el morado del CSS. */
/* ==========================================================================
   EL CRONÓMETRO DE LA VUELTA RÁPIDA

   Un recuadro morado pegado al borde derecho de la torre, a la altura de
   quien tiene la vuelta rápida. Como en la torre de televisión: se ve de
   quién es sin leer nada, solo por dónde está.

   Va FUERA de la torre y no dentro de la fila. Dentro se comía 18px de
   ancho en las veinte filas para adornar una sola, y el tótem va encima
   de la carrera: cada pixel de ancho tapa pista.

   No puede colgar de la torre porque la torre recorta lo que se sale
   —de eso vive su entrada, el arte bajando desde arriba—, así que vive
   suelto en el documento y se coloca midiendo dónde ha quedado la fila.
   Medir es más fiable que calcular: entre medias se abren las franjas de
   la vuelta rápida y del piloto comparado, que empujan las filas hacia
   abajo, y el número de fila ya no dice a qué altura está.
========================================================================== */

let torreCronoCaja   = null;
let torreCronoTemp   = null;
let torreCronoDonde  = "";   /* donde se dejo, para saber si se movio */
let torreCronoQuieto = 0;    /* vueltas seguidas sin moverse */


function torreCronoElemento(){

    if (torreCronoCaja) return torreCronoCaja;

    torreCronoCaja = document.createElement("div");
    torreCronoCaja.className = "tf-crono-fuera";
    torreCronoCaja.innerHTML = torreCronometro();

    document.body.appendChild(torreCronoCaja);

    return torreCronoCaja;
}


function torreColocarCrono(){

    const caja = torreCronoElemento();

    const fila = torreCuerpo && torreCuerpo.querySelector(".tf-fila.vuelta-rapida");
    const torre = torreElemento;

    /* Sin vuelta rápida marcada, con la torre fuera del aire, o apagado
       desde el panel, no hay nada que señalar. Se esconde en vez de
       dejarlo donde estaba. */
    if (!fila || !torre || !torreConfig.crono) {
        caja.classList.remove("visible");
        torreCronoDonde = "";
        return false;
    }

    const f = fila.getBoundingClientRect();
    const t = torre.getBoundingClientRect();

    /* Con la torre a medio entrar la fila todavía no tiene alto: pintar
       el recuadro ahí lo deja como una raya en el aire. */
    if (f.height <= 0 || t.width <= 0) {
        caja.classList.remove("visible");
        torreCronoDonde = "";
        return false;
    }

    caja.style.left   = `${t.right}px`;
    caja.style.top    = `${f.top}px`;
    caja.style.height = `${f.height}px`;

    caja.classList.add("visible");

    const donde = `${t.right}|${f.top}|${f.height}`;
    const movido = donde !== torreCronoDonde;
    torreCronoDonde = donde;

    return movido;
}


/* Se coloca ya y ademas se sigue mientras se mueva.

   Lo primero es colocarlo de una vez, sin esperar a ningun fotograma. El
   seguimiento va con setTimeout y no con requestAnimationFrame porque rAF
   solo corre si la pagina se esta pintando, y estas plantillas viven en
   un navegador sin ventana; con rAF el recuadro no llegaba a aparecer.

   Se para cuando la fila lleva un rato quieta, no al cabo de un tiempo
   fijo. Encima de la torre se mueven varias cosas con duraciones
   distintas —la entrada escalonada, las franjas que se abren, los nombres
   al abreviarse— y cualquier plazo que se eligiera se quedaria corto para
   alguna. Asi no hay que conocerlas: se sigue a la fila hasta que para. */
function torreSeguirCrono(){

    torreColocarCrono();

    torreCronoQuieto = 0;

    if (torreCronoTemp !== null) return;

    const paso = () => {
        const movido = torreColocarCrono();

        torreCronoQuieto = movido ? 0 : torreCronoQuieto + 1;

        /* Un segundo quieto y se deja de mirar. Vuelve a arrancar solo
           cuando algo la mueva otra vez. */
        if (torreCronoQuieto > 25) {
            torreCronoTemp = null;
            return;
        }
        torreCronoTemp = setTimeout(paso, 40);
    };

    torreCronoTemp = setTimeout(paso, 40);
}


function torreEsconderCrono(){

    if (torreCronoTemp !== null) {
        clearTimeout(torreCronoTemp);
        torreCronoTemp = null;
    }
    torreCronoDonde = "";

    if (torreCronoCaja) torreCronoCaja.classList.remove("visible");
}


function torreCronometro(){

    return '<span class="tf-crono">'
        + '<svg viewBox="0 0 24 24">'
        + '<circle cx="12" cy="14" r="7.5"/>'
        + '<path d="M12 14V9.5"/>'
        + '<path d="M12 14l3.4 2"/>'
        + '<path d="M9.6 2.5h4.8"/>'
        + '<path d="M12 2.5v4"/>'
        + '</svg>'
        + '</span>';
}


/* La franja que se abre bajo la fila de un piloto: su mejor vuelta y la
   última, nada más. Se quitaron el número de vuelta y la velocidad porque
   lo que se compara en pantalla son los dos tiempos.

   `verde` la pinta en el color del segundo piloto, el que se elige a mano
   para comparar contra el de la vuelta rápida. */
function torreFranja(piloto, verde){

    const clase = verde ? "tf-franja verde" : "tf-franja";

    let html = `<div class="${clase}"><div class="tf-franja-caja">`;

    html += `<span class="tf-franja-dorsal">${torreEscapar(piloto.number)}</span>`;

    html += `<span class="tf-franja-rotulo">${T("totem.mejor", "Mejor")}</span>`;
    html += `<span class="tf-franja-tiempo">${torreEscapar(piloto.best_time || "--")}</span>`;

    html += `<span class="tf-franja-rotulo derecha">${T("totem.ultima", "Última")}</span>`;
    html += `<span class="tf-franja-tiempo tenue">${torreEscapar(piloto.last_time || "--")}</span>`;

    html += '</div></div>';

    return html;
}


/* ==========================================================================
   ENTRADA POR FASES

   El totem se arma delante del espectador y en el orden en que se lee:
   de quien es, que se corre, donde van a caber los nombres, y los nombres.

   Los tiempos van aqui y no en el CSS porque la ultima fase depende de
   cuantas filas se hayan pintado, y eso solo se sabe al terminar.
========================================================================== */

/* Lo que dura cada fase, en milisegundos. Tienen que ser los mismos
   numeros que las variables --tf-ent-* del CSS: alli mandan la duracion de
   la transicion y aqui el momento en que arranca la siguiente. */
const TF_DURACION = {
    logo:     1500,
    cabecera: 1000,
    cuerpo:   1500,
    nombres:  1000,
};

/* Cada fase empieza cuando termina la anterior. Se calcula y no se
   escribe a mano para que cambiar una duracion no obligue a recalcular
   las tres siguientes. */
const TF_FASES = {
    logo:     0,
    cabecera: TF_DURACION.logo,
    cuerpo:   TF_DURACION.logo + TF_DURACION.cabecera,
    nombres:  TF_DURACION.logo + TF_DURACION.cabecera + TF_DURACION.cuerpo,
};

/* Lo que tarda una fila en seguir a la anterior. No es fijo: el reparto
   sale de que todas esten dentro del segundo que dura la fase, sean cinco
   o sean veinte. */
const TF_FILA_ANIM = 280;

function tfPasoFila(filas){
    if (filas <= 1) return 0;
    return Math.max(0, (TF_DURACION.nombres - TF_FILA_ANIM) / (filas - 1));
}


function torreCancelarEntrada(){
    torreEntrada.relojes.forEach(clearTimeout);
    torreEntrada.relojes = [];
}


function torreEscalonarFilas(){

    /* El retraso se pone aqui y no en el CSS porque depende de la posicion
       de cada fila, y las filas las pinta el script. */
    const filas = torreCuerpo.querySelectorAll(".tf-fila");
    const paso = tfPasoFila(filas.length);

    filas.forEach((fila, i) => {
        Array.from(fila.children).forEach(hijo => {
            hijo.style.animationDelay = Math.round(i * paso) + "ms";
        });
    });
}


function torreArrancarEntrada(){

    if (torreEntrada.hecha || torreEntrada.corriendo) return;

    torreEntrada.corriendo = true;

    torreElemento.classList.add("entrando");
    torreEscalonarFilas();

    const paso = (clase, ms) => {
        torreEntrada.relojes.push(setTimeout(() => {
            torreElemento.classList.add(clase);
        }, ms));
    };

    paso("fase-logo",     TF_FASES.logo);
    paso("fase-cabecera", TF_FASES.cabecera);
    paso("fase-cuerpo",   TF_FASES.cuerpo);
    paso("fase-nombres",  TF_FASES.nombres);

    /* Al terminar se retiran todas las clases: la entrada deja de existir
       y el totem queda como estaba, sin transiciones colgando que le
       compliquen la vida a los repintados. */
    const total = TF_FASES.nombres + TF_DURACION.nombres + 150;

    torreEntrada.relojes.push(setTimeout(() => {
        torreElemento.classList.remove(
            "entrando", "fase-logo", "fase-cabecera", "fase-cuerpo", "fase-nombres");
        torreEntrada.corriendo = false;
        torreEntrada.hecha = true;

        /* La cuenta para encoger los nombres empieza aqui y no al sacar el
           grafico: los siete segundos son para leerlos, y hasta este
           momento no habia nada que leer. */
        /* La primera vez que hay filas se arma la entrada; la cuenta para
       encoger los nombres la arranca ella al terminar. Despues, cada
       repintado la reprograma como siempre. */
    if (torreEntrada.corriendo) {
        /* Las filas acaban de nacer en mitad de la entrada: se les reparte
           el retraso para que entren escalonadas como el resto. */
        torreEscalonarFilas();
    } else if (!torreEntrada.hecha) {
        torreArrancarEntrada();
    } else {
        torreProgramarCorto();
    }
    }, total));
}


function torreProgramarCorto(){

    /* Se reprograma en cada repintado: si entra un piloto nuevo mientras
       corre la cuenta, la animación no se dispara a medias. */

    clearTimeout(torreTemporizador);

    /* Con la columna de tiempos abierta los nombres van cortos y se quedan
       cortos. Volver a estirarlos cada vez que se pulsa al lider o al
       intervalo obligaba a esperar otros siete segundos para leer lo que
       se acababa de pedir, que es justo el tiempo. */
    if (torreConfig.retraso <= 0 || torreConfig.columna) {
        torreElemento.classList.add("corto");
        return;
    }

    torreElemento.classList.remove("corto");

    torreTemporizador = setTimeout(() => {
        torreElemento.classList.add("corto");
    }, torreConfig.retraso * 1000);
}


function torreDiferencia(piloto, indice){

    /* El primero no tiene contra quién medirse: en su fila la columna dice
       de qué diferencia se está hablando. */

    if (indice === 0) return torreConfig.etiqueta;

    return piloto[torreConfig.columna] || "";
}


function torrePintarFilas(standings){

    /* Se redibuja solo si cambió algo. Repintar diez veces por segundo hace
       parpadear los logos, que son peticiones al backend. */

    const campos = ["position", "full_name", "number", "is_best_lap",
                    "best_time", "last_time"];
    if (torreConfig.marca)   campos.push("brand_logo");
    if (torreConfig.columna) campos.push(torreConfig.columna);

    const firma = timingFirma(standings, campos);
    if (firma === torreFirma) return;
    torreFirma = firma;

    torreCuerpo.innerHTML = "";

    standings.forEach((piloto, index) => {

        const fila = document.createElement("div");

        const clases = ["tf-fila"];
        if (index === 0) clases.push("lider");
        /* El backend marca quién tiene la vuelta rápida comparando el
           dorsal de la cabecera del XML con el de cada fila. */
        if (piloto.is_best_lap) clases.push("vuelta-rapida");

        fila.className = clases.join(" ");

        let columnas = `
            <div class="tf-pos">${torreEscapar(piloto.position)}</div>
            <div class="tf-barra"></div>
        `;

        if (torreConfig.marca) {
            /* Sin logo se deja el hueco vacío en vez de un roto: la columna
               tiene que seguir alineada aunque falte una marca. */
            const logo = piloto.brand_logo
                ? `<img src="${torreEscapar(piloto.brand_logo)}" alt="${torreEscapar(piloto.brand || "")}">`
                : "";
            columnas += `<div class="tf-marca">${logo}</div>`;
        }

        /* Con la columna de tiempos abierta el dorsal se adelanta: queda
           posicion, logo, dorsal, nombre y tiempos. Asi el dato que se
           busca —el tiempo— cae al final de la fila y no en medio, y el
           dorsal sigue pegado al nombre al que pertenece. */
        if (torreConfig.dorsalIzquierda || torreConfig.columna) {
            columnas += `<div class="tf-dorsal izquierda">${torreEscapar(piloto.number)}</div>`;
        }

        columnas += `<div class="tf-nombre">${torreNombre(piloto)}</div>`;

        if (!torreConfig.dorsalIzquierda && !torreConfig.columna) {
            columnas += `<div class="tf-dorsal">${torreEscapar(piloto.number)}</div>`;
        }

        if (torreConfig.columna) {

            const dif = torreDiferencia(piloto, index);

            /* En ambar cuando sale negativa: este va por delante en tiempo
               del que figura primero, que es lo que deja una sancion. El
               color solo avisa de que la cifra no es normal; no dice que
               haya sancion porque MyLaps no lo manda en ninguna parte. */
            const negativa = String(dif).trim().charAt(0) === "-";

            columnas += `<div class="tf-dif${negativa ? " negativa" : ""}">`
                      + torreEscapar(dif)
                      + `</div>`;
        }

        fila.innerHTML = columnas;

        torreCuerpo.appendChild(fila);

        /* Las franjas se pintan siempre cerradas, justo debajo de su fila.
           Al abrirse empujan al resto hacia abajo, que es el efecto
           buscado: no tapan a nadie, hacen sitio.

           Un mismo piloto puede llevar las dos —tiene la vuelta rápida y
           además se eligió para comparar—; se dibujan una tras otra. */
        const caja = document.createElement("div");

        if (piloto.is_best_lap) {
            caja.innerHTML = torreFranja(piloto, false);
            torreCuerpo.appendChild(caja.firstChild);
        }

        if (torreConfig.comparar && String(piloto.number) === String(torreConfig.comparar)) {
            caja.innerHTML = torreFranja(piloto, true);
            torreCuerpo.appendChild(caja.firstChild);
        }
    });

    /* Las letras nacen enteras y se encogen después; si se pintaran ya
       encogidas no habría animación que ver. */
    torreProgramarCorto();

    /* La franja se acaba de recrear, así que se le repone el estado: si
       estaba abierta y entra un piloto nuevo, no debe cerrarse sola. */
    torreElemento.classList.toggle("mejor-vuelta", torreConfig.mejorVuelta);
    torreElemento.classList.toggle("con-diferencia", Boolean(torreConfig.columna));

    /* Las filas acaban de cambiar de sitio: el recuadro de la vuelta
       rápida las sigue mientras se asientan. */
    torreSeguirCrono();

    const comparando = Boolean(torreConfig.comparar);

    if (torreAnimarComparar) {
        /* Dos fotogramas y no uno: con uno solo el navegador puede juntar
           el pintado y el cambio de clase en el mismo reflow, y la
           transición vuelve a perderse. */
        torreAnimarComparar = false;
        torreElemento.classList.remove("comparando");
        requestAnimationFrame(() => requestAnimationFrame(() => {
            torreElemento.classList.toggle("comparando", comparando);
        }));
    } else {
        /* Repintado de rutina —entró un piloto nuevo, cambió el orden—:
           se repone tal cual estaba. Animarla aquí la cerraría y la
           volvería a abrir sola cada vez que se mueve la clasificación. */
        torreElemento.classList.toggle("comparando", comparando);
    }
}


function torrePintarCabecera(datos){

    const poner = (id, texto) => {
        const el = document.getElementById(id);
        if (el) el.textContent = texto;
    };

    poner("grupo", datos.group_name || datos.group || "");
    poner("heat", datos.heat || datos.run_name || "");

    /* El backend decide si manda el reloj de carrera o la cuenta atrás, y
       manda también la etiqueta que corresponde. */
    poner("relojEtiqueta", datos.time_label || "TIME");
    poner("reloj", datos.time || "0:00");

    /* Banda de estado: solo cuando hay bandera. */
    const estado = document.getElementById("estado");
    const bandera = TORRE_BANDERAS[(datos.flag || "none").toLowerCase()];

    if (estado && bandera) {
        estado.className = "tf-estado " + bandera.clase;
        estado.textContent = bandera.texto;
        torreElemento.classList.add("con-estado");
    } else {
        torreElemento.classList.remove("con-estado");
    }
}


function torrePintar(datos){

    if (!datos) return;

    torrePintarCabecera(datos);
    torrePintarFilas(datos.standings || []);
}


/* ─── Lo que usan las plantillas ─────────────────────────────── */

function arrancarTorre(opciones){

    torreConfig = Object.assign({}, torreConfig, opciones || {});

    torreCuerpo   = document.getElementById("cuerpo");
    torreElemento = document.getElementById("torre");

    /* Sin logo la fila cambia de reparto, y eso lo decide el CSS. */
    if (!torreConfig.marca) torreElemento.classList.add("sin-marca");

    arrancarTiming({ limite: torreConfig.limite, alRecibir: torrePintar });

    /* La entrada empieza al salir al aire y no al llegar los datos: el
       logo y la cabecera no dependen del cronometraje, y hacerlos esperar
       dejaba un hueco muerto entre pulsar el boton y ver algo. Va aquí,
       con torreElemento ya resuelto. */
    torreArrancarEntrada();
}


function detenerTorre(){
    /* El recuadro vive fuera de la torre, asi que no se lo lleva por
       delante el CLEAR de la capa: hay que retirarlo a mano o se queda
       flotando sobre la carrera. */
    torreEsconderCrono();

    torreCancelarEntrada();
    torreEntrada.hecha = false;
    torreEntrada.corriendo = false;
    torreElemento.classList.remove(
        "entrando", "fase-logo", "fase-cabecera", "fase-cuerpo", "fase-nombres");


    clearTimeout(torreTemporizador);
    detenerTiming();
}


function actualizarTorre(data){

    /* Acepta {"limite":15}, {"retraso":10}, {"modo":"corto"|"completo"} y
       {"api":"http://otra-maquina:8080/api/v1"} */

    try {
        const d = typeof data === "string" ? JSON.parse(data) : (data || {});

        if (d.api) configurarTiming(d.api);

        if (d.retraso !== undefined) {
            torreConfig.retraso = parseInt(d.retraso, 10);
            torreProgramarCorto();
        }

        if (d.modo === "corto") {
            clearTimeout(torreTemporizador);
            torreElemento.classList.add("corto");
        } else if (d.modo === "completo") {
            clearTimeout(torreTemporizador);
            torreElemento.classList.remove("corto");
        }

        /* Abre o cierra la franja de la vuelta rápida. Es un interruptor:
           la interfaz manda true o false, no se cierra sola. */
        if (d.mejor_vuelta !== undefined) {
            torreConfig.mejorVuelta = Boolean(d.mejor_vuelta);
            torreElemento.classList.toggle("mejor-vuelta", torreConfig.mejorVuelta);
            /* La franja empuja las filas de abajo mientras se abre. */
            torreSeguirCrono();
        }

        /* El recuadro morado de la vuelta rápida. Es un interruptor
           aparte de la franja: son dos cosas distintas —uno dice de quién
           es, la otra enseña los tiempos— y se quieren por separado. */
        if (d.crono !== undefined) {
            torreConfig.crono = Boolean(d.crono);
            torreSeguirCrono();
        }

        /* El segundo piloto. Llega su dorsal para abrirla, o null para
           cerrarla. Hay que repintar: la franja verde cuelga de una fila
           distinta según a quién se haya elegido. */
        if (d.comparar !== undefined) {
            torreConfig.comparar = d.comparar || null;

            /* La clase no se pone aquí. La franja verde no existe hasta el
               repintado, y si al nacer ya está dentro de .comparando el
               navegador la dibuja abierta en el primer fotograma: no hay
               estado de partida desde el que animar y aparece de golpe. La
               de la vuelta rápida no tenía el problema porque ya estaba en
               el DOM, cerrada, y solo se le marcaba la clase.

               Se avisa al repintado para que la abra un fotograma después,
               con la franja ya puesta y cerrada. */
            torreAnimarComparar = true;

            torreFirma = null;
            torrePintar(timingUltimo());
        }

        /* Al lider o al de adelante. Llega desde el panel con el totem ya
           al aire: no carga otra plantilla, solo abre o cierra la columna
           de la derecha. null la cierra.

           No toca la cabecera ni reescribe los nombres: el reloj, el grupo
           y la tanda siguen donde estaban, y los nombres con la letra que
           tuvieran. Lo unico que cambia es que aparece una columna. */
        if (d.columna !== undefined) {
            const cual = d.columna || null;

            torreConfig.columna = cual;
            torreConfig.etiqueta = cual === "leader"    ? T("totem.lider", "LÍDER")
                                 : cual === "interval"  ? T("totem.intervalo", "INTERVALO")
                                 : "";

            /* El totem se ensancha para hacerle sitio: metiendola dentro
               del ancho de siempre, el nombre perdia la mitad de su hueco
               y se cortaba justo cuando mas se mira. */
            torreElemento.classList.toggle("con-diferencia", Boolean(cual));

            torreFirma = null;
            torrePintar(timingUltimo());

            /* Se reevalua aqui: al abrir la columna deja los nombres
               cortos, y al cerrarla vuelve a regir el retraso de siempre. */
            torreProgramarCorto();
        }

        if (d.limite) {
            torreConfig.limite = parseInt(d.limite, 10) || torreConfig.limite;
            torreFirma = null;          // fuerza el repintado
            arrancarTiming({ limite: torreConfig.limite, alRecibir: torrePintar });
        }
    } catch (e) {
        /* Un UPDATE con basura no puede tumbar el gráfico al aire. */
    }
}

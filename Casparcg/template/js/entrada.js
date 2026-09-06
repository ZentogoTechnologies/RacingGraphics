/* ==========================================================================
   ESPERAR A ESTAR LISTO ANTES DE ENTRAR

   Las barras de abajo —evento, categoría, redes, narrador, comentarista y
   reportero— se desplegaban en cuanto CasparCG llamaba a play(), sin
   esperar a nada. El resultado era un despliegue a trompicones: la barra
   se abría vacía, el logo aparecía de golpe a mitad de la animación y, en
   las que se miden solas, el ancho salía calculado con la letra de
   respaldo y luego cambiaba al llegar la de verdad.

   El clima no tenía ese problema y por eso se veía bien: es la única que
   no lleva ni una imagen —su icono es un SVG escrito en el propio HTML— y
   cuando entra ya está todo dibujado.

   Aquí se espera a lo mismo que el clima tiene gratis: a que la tipografía
   esté cargada y a que las imágenes que haya estén completas. Entonces se
   entra, y se entra con todo puesto.

   El tope es lo que hace que esto sea seguro al aire: si una imagen no
   llega —el backend caído, una URL mala— la barra sale igual al cumplirse
   el plazo, sin su logo pero a tiempo. Un gráfico que no sale nunca es
   peor que uno al que le falta una pieza.
========================================================================== */

/* Cuánto se espera como mucho. Segundo y medio: por debajo no da tiempo a
   una tipografía y un logo en una máquina cargada, y por encima se nota el
   retraso entre pulsar el botón y ver algo. */
var ENTRADA_TOPE = 1500;


function entradaCuandoListo(raiz, seguir, tope){

    var hecho = false;

    var listo = function(){
        if (hecho) return;
        hecho = true;
        seguir();
    };

    /* El plazo se arma primero. Si algo de lo de abajo fallara —una
       promesa que no resuelve, una imagen que ni carga ni da error—, esto
       es lo único que garantiza que el gráfico salga. */
    setTimeout(listo, tope || ENTRADA_TOPE);

    /* Empieza en uno y ese uno se suelta al final. Es un fiador: sin él,
       una tipografía ya cargada dejaría el contador en cero antes de
       haber contado las imágenes, y la barra entraría sin esperarlas. */
    var pendientes = 1;

    var menos = function(){
        pendientes -= 1;
        if (pendientes <= 0) listo();
    };

    /* La tipografía. Importa más de lo que parece en las barras que se
       miden solas: con la letra de respaldo el texto ocupa otra cosa, y el
       ancho calculado se queda mal en cuanto llega la buena. */
    if (typeof document !== "undefined" && document.fonts && document.fonts.ready) {
        pendientes += 1;
        document.fonts.ready.then(menos, menos);
    }

    var imagenes = (raiz || document).querySelectorAll("img");

    for (var i = 0; i < imagenes.length; i++) {

        var im = imagenes[i];

        /* Sin src no hay nada que esperar: son los huecos que la plantilla
           deja para un logo que este gráfico no lleva. */
        if (!im.getAttribute("src")) continue;
        if (im.complete) continue;

        pendientes += 1;

        /* `error` cuenta igual que `load`: una imagen que no está no puede
           dejar la barra a medio entrar para siempre. */
        im.addEventListener("load", menos, { once: true });
        im.addEventListener("error", menos, { once: true });
    }

    /* Se suelta el fiador. Si no quedaba nada que esperar, esto es lo que
       hace entrar la barra ya mismo. */
    menos();
}


/* ==========================================================================
   EL ARRANQUE AUTOMÁTICO DEL NAVEGADOR

   Las plantillas se abren también a mano en un navegador, para verlas sin
   levantar CasparCG. Ahí no hay quien llame a play(), así que arrancaban
   solas con `window.onload = play`.

   Eso es lo que producía el amague. Dentro de CasparCG el CG ADD trae los
   datos y llama él mismo a update() y a play(), pero la página termina de
   cargar ANTES de que llegue ese comando: el arranque automático se
   adelantaba, la barra salía con el texto de relleno —"Nombre del
   evento"— y volvía a entrar un instante después con los datos de verdad.
   Dos entradas seguidas, la primera en falso.

   Ahora el arranque automático espera, y la primera llamada a play() lo
   cancela. Dentro de CasparCG nunca llega a dispararse; en un navegador,
   donde nadie llama a play(), salta al cumplirse el plazo y la plantilla
   se ve igual que antes.
========================================================================== */

/* Margen que se le da a CasparCG para mandar su CG ADD. Tres cuartos de
   segundo: de sobra para un comando local, y en un navegador no se hace
   esperar. */
var ENTRADA_AUTO = 750;

var entradaTemporizador = null;


function entradaAutoNavegador(arrancar){

    entradaTemporizador = setTimeout(arrancar, ENTRADA_AUTO);
}


/* Lo llama play() en su primera línea: si el arranque viene de fuera, el
   automático sobra. */
function entradaCancelarAuto(){

    if (entradaTemporizador !== null) {
        clearTimeout(entradaTemporizador);
        entradaTemporizador = null;
    }
}

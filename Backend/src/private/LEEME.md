# private

Material de la marca **Race Core Studio**: el software, no el autódromo.

| archivo | para qué |
|---|---|
| `Icono.ico` | El icono de la carpeta en el Explorador de Windows. Lo apunta `desktop.ini`, en la raíz del proyecto. Es el mismo archivo que el panel usa de favicon, que vive aparte en `Frontend/public/`. |
| `Logo.jpeg` | El logo del producto. Para documentación, el instalador y material de presentación. |

## Por qué "private" y no "public"

La carpeta de al lado, `public/`, la sirve el backend en `/public` para que
CasparCG y el panel puedan bajarse las fotos de los pilotos y los logos de
las marcas. Todo lo que se deje ahí queda accesible por HTTP a cualquiera
que alcance el servidor.

Esta no se sirve, y no debe servirse. Aquí va lo que el sistema no necesita
entregar por la red: identidad del producto y material que no forma parte
de lo que sale al aire.

## Ojo con el icono

No es el favicon del panel. El del panel es `Frontend/public/Icono.ico`, que
Vite copia a `dist/` al construir, y de ahí lo toma `index.html`. Eran dos
copias idénticas del mismo archivo; esta se dejó como la de la marca y
aquella sigue siendo la del panel, que tiene que existir dentro del
frontend para que funcione también con `npm run dev`, sin backend delante.

Si alguna vez se cambia el icono, hay que cambiar los dos.

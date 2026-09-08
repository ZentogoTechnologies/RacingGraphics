# current-demo.xml

Copia ficticia del archivo que MyLaps reescribe en vivo con la
clasificación. Se distribuye con el producto.

## Para qué está

**Instalando.** El asistente pide la ruta del `current.xml` del equipo de
cronometraje. Para decir «esta ruta funciona» hace falta algo con qué
comparar, y el día de la instalación puede que MyLaps ni esté encendido.

**Demostrando.** Enseñar el producto, entrenar a un operador o revisar
una plantilla nueva no puede depender de que haya carrera ese día.

**Probando.** Es lo que permite correr las pruebas de `timing_services`
sin una unidad de red montada.

## Nunca como respaldo automático

Este archivo **se elige a mano**. El sistema no debe caer a él cuando la
ruta real falla: salir al aire con una clasificación falsa en una carrera
de verdad es peor que no mostrar nada. Si el `current.xml` real no se
puede leer, lo correcto es avisar, no sustituir.

## La salvaguarda está en el evento, no en los nombres

Los 30 pilotos son inventados pero **verosímiles a propósito**: una tabla
con «PILOTO 01» no sirve para enseñarle el producto a nadie ni para ver
cómo quedan las plantillas con nombres largos.

Lo que canta que esto es de mentira es el rótulo del evento —**EVENTO DE
DEMOSTRACION**— junto con la pista y la categoría. Ese rótulo sale al
aire en su propio gráfico, así que si el archivo se colara en una carrera
real, se vería.

## Qué reproduce

Sigue el esquema completo de MyLaps —las mismas etiquetas y los mismos
atributos por fila que los `current (1).xml` y `current (2).xml` reales—
con la ficha completa de cada piloto: dorsal, marca y modelo
(`additional6`), país (`additional4`), equipo (`additional1`),
transponder, mejores tiempos, velocidades y vueltas.

Incluye a propósito los casos raros que el parser trata aparte:

### Una penalización

El más sutil, y la razón de la mitad del cuidado que lleva este archivo.

**MyLaps no manda ninguna marca de penalización.** No existe un campo que
diga «a este le cayeron diez segundos». Lo que pasa es que MyLaps calcula
`difference` contra el coche **más rápido**, no contra quien va primero
en la clasificación, y con una sanción esos dos dejan de ser el mismo:

- El sancionado, que sigue siendo el más rápido, queda como **referencia**
  y MyLaps le deja la diferencia **vacía**.
- Al primero de la clasificación sí le pone un tiempo.

`_reencuadrar_diferencias` lo detecta y reencuadra todo contra el primero.
El sancionado sale entonces con diferencia **negativa**: va delante en la
pista y detrás en la clasificación.

En este archivo son diez segundos al `#29`, que cae al puesto 2 y aparece
al aire con `-6.718`.

### Los demás casos

- Tres **coches doblados**, con `difference="1 Lap"` en vez de un tiempo.
- Un **carro compartido**, donde MyLaps parte el nombre por donde cae
  entre `firstname` y `lastname`.
- Tiempos con el formato exacto de MyLaps: `0.885`, no `00.885`.
- Pilotos de **siete países**, para que se vea si las banderas funcionan.

## Regenerarlo

```bash
python tools/demo/generar_current.py
```

Para probar gráficos y plantillas con una carrera que avanza sola:

```bash
python tools/demo/generar_current.py --salida C:/timing/current.xml --vivo
```

Otras opciones: `--vuelta`, `--total-vueltas`, `--tanda`, `--tipo`
(R heat, Q qualy, P práctica) y `--bandera`.

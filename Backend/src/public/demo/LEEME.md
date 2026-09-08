# current.xml de demostración

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

Por eso los nombres son `PILOTO DEMO 01` y el evento se llama
`EVENTO DE DEMOSTRACION`: si esto llegara a salir al aire por error,
tiene que notarse en el primer segundo.

## Qué reproduce

Sigue el esquema real de MyLaps —las mismas etiquetas y los mismos
atributos por fila— e incluye a propósito los casos raros que el parser
trata aparte:

- Un **coche doblado**, con `difference="1 Lap"` en vez de un tiempo.
- Un **carro compartido**, donde MyLaps parte el nombre por donde cae
  entre `firstname` y `lastname`.
- El **líder sin diferencia**, con el campo vacío.
- Tiempos con el formato exacto de MyLaps: `0.885`, no `00.885`.

## Regenerarlo

```bash
python tools/demo/generar_current.py \
    --salida Backend/src/public/demo/current.demo.xml
```

Para probar gráficos y plantillas con una carrera que avanza sola:

```bash
python tools/demo/generar_current.py --salida C:\timing\current.xml --vivo
```

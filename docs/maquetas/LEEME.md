# Maquetas del asistente de instalación

Ocho pantallas numeradas, para revisar antes de programar el frontend.
Cada imagen lleva su número arriba a la izquierda: basta con decir
«en la 04, cambia X» para saber de cuál se habla.

| # | Pantalla | Paso |
|---|---|---|
| 01 | Bienvenida — licencia y direcciones de red | 1 de 6 |
| 02 | Datos del cliente | 2 de 6 |
| 03 | Logo del cliente | 3 de 6 |
| 04 | Las tres cuentas | 4 de 6 |
| 05 | Cronometraje — ruta correcta | 5 de 6 |
| 06 | Cronometraje — ruta equivocada | 5 de 6 |
| 07 | Gráficos y ubicación del circuito | 6 de 6 |
| 08 | Instalación completada | — |

La 06 no es un paso aparte: es la 05 cuando la ruta falla. Se incluye
porque el error de la unidad mapeada es el que más va a aparecer en
instalaciones reales, y conviene decidir cómo se explica.

## Regenerarlas

Salen de `pantallas.html`, que es la fuente. Se corrige el HTML y se
vuelve a renderizar; no se retocan los PNG a mano.

```bash
node docs/flujos/renderizar.mjs   # ver el script de pantallas en scratchpad
```

Son maquetas, no la interfaz construida: sirven para acordar textos,
orden y qué se pide en cada paso antes de escribir React.

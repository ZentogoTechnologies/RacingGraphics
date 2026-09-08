# Maquetas del asistente de instalación

Diez pantallas numeradas, para revisar antes de programar el frontend.
Cada imagen lleva su número arriba a la izquierda: basta con decir
«en la 04, cambia X» para saber de cuál se habla.

| # | Pantalla | Paso |
|---|---|---|
| 01 | Bienvenida — licencia y direcciones de red | 1 de 7 |
| 02 | Datos del cliente | 2 de 7 |
| 03 | Logo del cliente | 3 de 7 |
| 04 | Las tres cuentas | 4 de 7 |
| 05 | Cronometraje — ruta correcta | 5 de 7 |
| 06 | Cronometraje — ruta equivocada | 5 de 7 |
| 07 | Servidor de gráficos (CasparCG) | 6 de 7 |
| 08 | Ubicación — buscar por nombre | 7 de 7 |
| 09 | Ubicación — pegar enlace del mapa | 7 de 7 |
| 10 | Instalación completada | — |

Tres pares comparten paso porque son estados de la misma pantalla, no
pasos distintos:

- **06** es la **05** cuando la ruta falla. Se incluye porque el error de
  la unidad de red mapeada va a ser el más común en instalaciones reales,
  y conviene decidir cómo se explica.
- **09** es la **08** con otra pestaña abierta.

El orden es el mismo que `PASOS` en `Backend/src/models/instalacion_model.py`.
Si uno cambia, el otro también.

## La ubicación admite tres entradas

Ninguna necesita clave de API ni cuesta dinero:

1. **Buscar por nombre** — contra el geocodificador de Open-Meteo, el
   mismo servicio que ya da el clima. Devuelve además la zona horaria, así
   que es un dato menos que preguntar.
2. **Pegar un enlace de Google Maps** — enlaces cortos de compartir desde
   el móvil incluidos. Las coordenadas salen del propio enlace, sin llamar
   a Google.
3. **Escribir las coordenadas** — en decimal o en grados y minutos.

La tercera es la que nunca depende de nadie: si no hay red o el servicio
está caído, siempre se puede escribir la latitud y la longitud.

## Regenerarlas

Salen de `pantallas.html`, que es la fuente. Se corrige el HTML y se
vuelve a renderizar; no se retocan los PNG a mano.

```bash
node docs/maquetas/renderizar.mjs \
     docs/maquetas/pantallas.html \
     docs/maquetas
```

Son maquetas, no la interfaz construida: sirven para acordar textos,
orden y qué se pide en cada paso antes de escribir React.

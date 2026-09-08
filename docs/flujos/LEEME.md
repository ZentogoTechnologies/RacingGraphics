# Diagramas de flujo

## Flujo de instalación

![Flujo de instalación](flujo-instalacion.png)

Los doce pasos que sigue un cliente desde que descarga el instalador hasta
que tiene Race Core Studio operativo, en Windows Server o Windows 11.

El diagrama distingue tres cosas que conviene no mezclar al leerlo:

- **Acción del usuario** — lo que la persona hace con sus manos.
- **Automático** — lo que el instalador resuelve solo.
- **Necesita conexión** — los únicos dos momentos que exigen internet.

### Regenerar la imagen

El PNG se genera desde `flujo-instalacion.html`, que es la fuente. Si hay
que corregir un paso se edita el HTML y se vuelve a renderizar; no se
retoca el PNG a mano.

```bash
node docs/flujos/renderizar.mjs \
     docs/flujos/flujo-instalacion.html \
     docs/flujos/flujo-instalacion.png
```

Requiere Playwright con Chromium. Se renderiza a escala 2x para que el
texto se lea nítido al ampliar en un teléfono.

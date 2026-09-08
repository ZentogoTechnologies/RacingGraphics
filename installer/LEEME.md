# Instalador de Race Core Studio

```bash
python installer/instalar.py
```

Pide correo y clave de licencia, la ata a este equipo, comprueba que esté
todo, escribe la configuración y abre el asistente web.

## ⚠ Esta es la versión de pruebas

La licencia **no se valida contra el servidor de Zentogo**, porque ese
servidor todavía no existe. Se valida contra un resumen SHA-256 escrito
en `licencia_local.py`, y la firma la pone una clave de desarrollo que
viaja con el repositorio.

Sirve para recorrer el flujo entero de punta a punta. **No para vender.**
Quien tenga el ejecutable puede parchear la comprobación y saltársela.

Lo que **sí es definitivo** es todo lo que va por debajo: la licencia que
se emite aquí es la misma que emitirá el servidor —mismo formato, misma
firma Ed25519, atada a la huella del equipo—, así que la validación del
backend, el periodo de gracia y el bloqueo al expirar se prueban de
verdad. Cuando exista el servidor, solo cambia quién firma.

## Los cinco pasos

| # | Qué hace |
|---|---|
| 1 | Valida correo y clave. Tres intentos |
| 2 | Calcula la huella del equipo y emite la licencia atada a ella |
| 3 | Comprueba backend, CasparCG, plantillas, MongoDB y el XML de demostración |
| 4 | Escribe el `.env`: firma de sesiones al azar y `LICENSE_REQUIRED=true` |
| 5 | Genera el token del asistente y abre el navegador |

## Probar el vencimiento

La parte que más conviene probar es qué pasa cuando la licencia caduca,
porque es la que no se puede ensayar esperando un año:

```bash
python installer/instalar.py --dias 365   # normal
python installer/instalar.py --dias -1    # vencida, dentro de la gracia: SIGUE operando
python installer/instalar.py --dias -30   # pasada la gracia: bloquea los gráficos
```

Con `--dias -1` el sistema debe seguir sacando gráficos al aire y avisar
en el panel. Con `--dias -30` las rutas de gráficos responden **402**,
pero el login y los datos siguen accesibles para poder renovar.

## Requisitos antes de ejecutarlo

- **MongoDB corriendo** en el 27017. Es lo único que el instalador exige;
  sin base, el backend no arranca.
- CasparCG en `Casparcg/` (ya está en el repositorio).
- Frontend compilado, si se quiere el panel y no solo el API:
  `npm install --prefix Frontend && npm run build --prefix Frontend`

## Lo que queda pendiente

- [ ] Servidor de licencias real (emisión, renovación, reasignación)
- [ ] Descarga de componentes desde el manifiesto firmado (`--origen remoto`)
- [ ] Empaquetado con Inno Setup y firma Authenticode
- [ ] Servicio de vigilancia y pantalla de licencia expirada

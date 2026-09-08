# Licenciamiento de los productos de Zentogo

Este documento fija el **contrato**: el formato de la licencia, el del
manifiesto de versión, y cómo se comporta el software en cada situación.
Todo lo que se construya después —servidor de licencias, instalador,
servicio de vigilancia— tiene que respetar lo que está aquí.

## La regla que gobierna todo

> Se bloquea por **vencimiento comprobado**, nunca por **falta de conexión**.

El software se usa en autódromos, y en un autódromo la red se cae. Un
sistema que exigiera contactar al servidor para arrancar apagaría los
gráficos de un cliente al día en plena transmisión en vivo.

Por eso la licencia es un token **firmado** que se valida **offline**: el
vencimiento viaja dentro del propio token y se comprueba contra el reloj
local. Internet hace falta para **activar** y para **renovar**. Nunca para
trabajar.

## Las claves

Dos pares Ed25519 distintos, y es importante que sean dos:

| Par | Firma | Vive en |
|---|---|---|
| `licencias` | Los tokens de licencia | Servidor de licencias |
| `releases` | Los manifiestos de versión | Sistema de publicación |

Separarlos significa que comprometer el que firma las descargas no
permite además fabricar licencias, ni al revés.

La **clave pública de licencias va escrita en el código**, en
`CLAVE_PUBLICA_PEM` de `Backend/src/services/license_services.py`, y no en
un archivo de configuración. Si saliera del `.env`, cualquiera podría
sustituirla por una suya, firmarse una licencia perpetua y saltarse todo
el sistema. Escrita en el código, cambiarla obliga a recompilar.

```bash
python tools/licencias/claves.py --salida claves/ --nombre licencias
python tools/licencias/claves.py --salida claves/ --nombre releases
```

Las privadas **no entran nunca al repositorio**. El `.gitignore` bloquea
`claves/` y `*.pem`, pero eso es una red de seguridad, no una excusa para
descuidarlas.

## La licencia

JWT firmado con Ed25519 (`alg: EdDSA`). Se eligió JWT porque el backend ya
usa PyJWT para las sesiones, así que no agrega una dependencia nueva.

```json
{
  "iss": "zentogo-licencias",
  "jti": "9f2c…",
  "iat": 1757280000,
  "nbf": 1757280000,
  "exp": 1788816000,

  "producto": "race-core-studio",
  "cliente": "Autódromo Panamá",
  "correo": "pablo@autodromopanama.com",
  "equipo": "e56a66e9…",
  "plan": "pro",
  "features": ["graficos", "pilotos", "vehiculos", "categorias", "eventos", "clima", "drag"],
  "version_max": "1.2.0",

  "gracia_dias": 15,
  "revalidar_dias": 7
}
```

| Campo | Para qué |
|---|---|
| `producto` | Una licencia de Race America no sirve para Race Core Studio |
| `equipo` | Huella SHA-256 de la máquina. Una licencia, un equipo |
| `version_max` | Hasta qué versión tiene derecho a actualizar |
| `features` | Van firmadas: el cliente no las amplía editando un archivo |
| `gracia_dias` | Margen después de vencer antes de bloquear |
| `revalidar_dias` | Cada cuánto conviene revalidar. **Nunca obligatorio** |

### La huella del equipo

SHA-256 de `MachineGuid` (registro de Windows) + número de serie del
volumen del sistema. Sobrevive a reinstalar el software y a renombrar el
equipo; cambia si se reformatea el disco o se clona a otra máquina.

Es opaca: identifica al equipo pero no revela nada de él, así que puede
viajar al servidor sin exponer datos del cliente.

**La licencia se ata a un equipo y solo Zentogo la reasigna.** Cuando un
cliente cambia de computadora, pasa por soporte.

## Estados

| Estado | ¿Opera? | Cuándo |
|---|---|---|
| `DESARROLLO` | Sí | Sin licencia y sin exigirla (equipo de trabajo) |
| `ACTIVA` | Sí | Todo en orden |
| `GRACIA` | **Sí** | Venció, pero dentro del margen. Opera y avisa |
| `EXPIRADA` | No | Venció y se acabó el margen |
| `SIN_LICENCIA` | No | Nunca se activó |
| `INVALIDA` | No | Firma que no cuadra, o archivo corrupto |
| `OTRO_EQUIPO` | No | Legítima, pero de otra máquina |
| `OTRO_PRODUCTO` | No | Legítima, pero de otro producto |
| `AUN_NO_VIGENTE` | No | Emitida con fecha de inicio futura |
| `RELOJ_ALTERADO` | No | El reloj retrocedió de forma sospechosa |

El orden de comprobación importa: **primero equipo y producto, después
las fechas**. Una licencia vencida *y* de otra máquina reporta la máquina;
si dijera "expiró", el cliente renovaría y seguiría sin funcionar.

### Qué se bloquea, y qué no

Con la licencia caída se bloquea **solo `/api/v1/graphics`**, que es lo que
saca gráficos al aire y es lo que se está vendiendo.

El login, los pilotos, los vehículos y los ajustes **siguen abiertos** a
propósito: un cliente con la licencia vencida tiene que poder entrar,
ver qué pasa y activar la renovación desde el propio software. Bloquearle
la puerta lo dejaría sin forma de arreglarlo.

Se responde **402 Payment Required**, no 403, para que el frontend
distinga "tu usuario no tiene permiso" de "hay que renovar" sin tener
que leer el texto del mensaje.

### El reloj

Atrasar la fecha del sistema es la forma más simple de estirar una
licencia vencida. Contra eso se guarda la fecha más alta vista
(`licencia.estado.json`); si el reloj aparece por detrás de esa marca más
de `LICENSE_CLOCK_TOLERANCE_DAYS`, el estado pasa a `RELOJ_ALTERADO`.

La tolerancia es de días a propósito: un equipo que estuvo apagado y
perdió la pila de la placa arranca con la fecha corrida sin que nadie
haya hecho trampa, y castigar eso dejaría a un cliente honesto sin
gráficos. Un retroceso de meses —el que sirve para estirar una
licencia— no pasa.

## El manifiesto de versión

Única fuente de verdad sobre qué compone una versión. El instalador lo lee
para instalar **y** para actualizar; no hay una segunda lista en otro
sitio que se pueda desincronizar.

```json
{
  "producto": "race-core-studio",
  "version": "1.2.0",
  "publicado": "2026-09-08T00:00:00+00:00",
  "minimo_actualizable": "1.0.0",
  "notas": "",
  "componentes": [
    {
      "id": "casparcg",
      "archivo": "casparcg-2.4.3.zip",
      "url": "https://descargas.zentogo.com/race-core-studio/1.2.0/casparcg-2.4.3.zip",
      "sha256": "87e4c7fd…",
      "bytes": 86000000,
      "orden": 0
    }
  ]
}
```

El campo `orden` fija la secuencia de instalación: **CasparCG (0) →
MongoDB (1) → Backend (2) → Frontend (3)**. CasparCG y MongoDB van
primero porque el backend, al arrancar por primera vez, necesita la base
viva; el frontend va al final porque se compila contra un backend que ya
debe existir.

La firma va **aparte**, en `manifiesto.sig` (Ed25519 en base64), y no
envuelta en un JWT. Motivo práctico: el instalador de Windows puede acabar
escrito en C#, en Pascal de Inno Setup o en Python, y verificar una firma
Ed25519 sobre unos bytes es de una línea en los tres, mientras que
interpretar un JWT obliga a arrastrar una librería. Además el manifiesto
se puede abrir y leer con cualquier editor.

Se firma sobre **JSON canónico** — claves ordenadas, sin espacios,
UTF-8 — para que los bytes firmados sean siempre los mismos.

```bash
# Publicar una versión
python tools/licencias/manifiesto.py construir \
    --version 1.2.0 \
    --base-url https://descargas.zentogo.com/race-core-studio/1.2.0 \
    --artefactos dist/1.2.0 \
    --privada claves/releases-privada.pem \
    --salida dist/1.2.0/manifiesto.json

# Lo que hace el instalador antes de fiarse de nada
python tools/licencias/manifiesto.py verificar \
    --manifiesto dist/1.2.0/manifiesto.json \
    --publica claves/releases-publica.pem
```

**El instalador verifica la firma del manifiesto antes de descargar nada,
y el SHA-256 de cada componente después de bajarlo.** Sin las dos cosas,
quien controle la red del cliente decide qué se instala en su máquina.

## Endpoints

| Ruta | Acceso | Para qué |
|---|---|---|
| `GET /api/v1/license/salud` | Abierto | ¿Se puede operar? Sin datos del cliente |
| `GET /api/v1/license/estado` | Sesión | Detalle completo, para el panel |
| `GET /api/v1/license/equipo` | Sesión | La huella, para pedir o reasignar licencia |
| `POST /api/v1/license/activar` | Dueño | Instala un token en este equipo |

`/salud` va abierta porque la consultan el servicio de vigilancia y la
pantalla de bloqueo, que corren fuera del panel y no tienen sesión. Solo
dice si se puede operar.

## Emitir una licencia a mano

El servidor hará esto desde su API, pero tener el script permite emitir
cuando haga falta —una demo, una prórroga de urgencia un domingo de
carrera— sin depender de que el servidor esté en pie.

```bash
python tools/licencias/emitir.py \
    --privada claves/licencias-privada.pem \
    --producto race-core-studio \
    --cliente "Autódromo Panamá" \
    --correo pablo@autodromopanama.com \
    --equipo <huella del panel: Ajustes → Licencia> \
    --plan pro --meses 12 \
    --salida licencia.lic
```

## Pruebas

```bash
cd Backend && python -m pytest tests/ -q
```

Cubren el camino feliz, el vencimiento y la gracia al día, la
falsificación (otra clave, token retocado, `alg: none`, emisor ajeno,
licencia sin `exp`), el equipo y producto equivocados, y la manipulación
del reloj.

## Pendiente

- [ ] Servidor de licencias (emisión, renovación, reasignación por admin)
- [ ] Servicio de vigilancia en Windows + pantalla de "licencia expirada"
- [ ] Instalador y actualizador
- [ ] Aviso de vencimiento próximo en el panel
- [ ] Revalidación en línea periódica (`revalidar_dias`), siempre opcional

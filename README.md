<div align="center">

# Race Core Studio

**Gráficos en vivo para automovilismo.**
Cronometraje de MyLaps, base de datos de pilotos y vehículos, y salida al aire por CasparCG.

Windows Server · Windows 11 — se opera desde el navegador de cualquier equipo de la red.

</div>

---

## ⚠ ¿Dónde está el `.exe`?

**Todavía no existe.** Es lo que falta por hacer, y conviene decirlo claro
antes que buscarlo por el repositorio.

Hoy el instalador es un script de Python, `installer/instalar.py`, que ya
hace el flujo completo: pide la licencia, la ata al equipo, comprueba las
piezas, escribe la configuración y abre el asistente web.

Para convertirlo en `RaceCoreStudio-Setup.exe` hay un script listo, pero
**tiene que ejecutarse en Windows**: PyInstaller genera un binario de la
máquina donde corre, así que un `.exe` de Windows solo sale de un Windows.

```bat
installer\construir.bat
```

Deja el ejecutable en `installer\dist\RaceCoreStudio-Setup.exe`. No se
versiona: se reconstruye cuando hace falta.

> **El `.exe` no irá firmado.** Sin un certificado Authenticode, SmartScreen
> lo marcará como «editor desconocido» en cada equipo. Para vender hace
> falta comprar el certificado; es un trámite con semanas de por medio, así
> que conviene empezarlo antes de la primera venta.

El `.msi` y el instalador que descarga los componentes de un servidor son
la fase siguiente, y dependen de que exista el servidor de licencias.

---

## Probarlo hoy

### Requisito previo

**MongoDB corriendo en el 27017.** Es lo único que el instalador exige;
sin base de datos el backend no arranca.

```bat
net start MongoDB
```

### 1 · Preparar el entorno

```bat
python -m venv Backend\venv
Backend\venv\Scripts\python.exe -m pip install -r Backend\requirements.txt

npm install --prefix Frontend
npm run build --prefix Frontend
```

### 2 · Instalar

```bat
Backend\venv\Scripts\python.exe installer\instalar.py
```

Pide correo y clave de licencia. Para las pruebas:

```
Correo:  zentogotech@gmail.com
Clave:   RCS1-XEA8-EXXK-EUNH-8M63
```

Al terminar abre el asistente web en el navegador, que es donde se
configuran el autódromo, el logo, las tres cuentas, el cronometraje y la
ubicación del circuito.

### 3 · Arrancar

```bat
race-core-studio.exe
```

O a mano, si aún no se ha construido el lanzador:

```bat
cd Backend
venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8080
```

El panel queda en `http://127.0.0.1:8080` desde el propio equipo, y en
`http://<IP-del-servidor>:8080` desde un iPad o cualquier otra máquina de
la red. **El instalador enseña esa dirección al terminar.**

---

## ¿Cómo sé que la instalación funcionó?

Cinco comprobaciones, en orden. Si las cinco pasan, funcionó.

**1 · El instalador termina con los cinco pasos en OK** y te da una
dirección con `?token=…`

**2 · El backend arranca y dice que falta configurar**

```bat
cd Backend
venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8080
```

Tiene que imprimir `Conectado a MongoDB` y
`Sin configurar: el asistente de instalación está abierto`.

**3 · El asistente abre y rechaza a quien no traiga el token**

Abre la dirección que dio el instalador: debe salir «Todo quedó
instalado» con la licencia en verde. Sin el `?token=…`, debe decir que
falta el token.

**4 · Completas los siete pasos.** Al terminar te deja en el login. Ahí
entra con la cuenta `owner` que acabas de crear.

**5 · Compruebas que quedó guardado**

```bat
curl http://127.0.0.1:8080/api/v1/setup/estado
```

Tiene que responder `"configurado": true` y `"asistente_disponible": false`.
El archivo `Backend\instalacion.token` ya no debe existir: se borra al
completar, y con él se cierra el asistente para siempre.

### Si algo falla

| Síntoma | Causa casi siempre |
|---|---|
| El instalador se para en el paso 3 | MongoDB no está corriendo: `net start MongoDB` |
| El asistente dice «falta el token» | Abriste la dirección sin el `?token=…` que dio el instalador |
| El asistente dice «ya está configurado» | Ya se completó antes. Para repetir: borra la base y `Backend\.env` |
| El panel no carga, solo el API | Falta compilar el frontend: `npm run build --prefix Frontend` |
| La ruta del cronometraje no verifica | Es unidad mapeada (`W:\`). Usa la ruta UNC completa |

> **¿Primera vez en un Windows nuevo?** La guía completa, desde instalar
> Python hasta ver el panel, está en
> **[docs/PRIMEROS-PASOS.md](docs/PRIMEROS-PASOS.md)**.

## Probar el vencimiento de la licencia

Es lo que no se puede ensayar esperando un año, y lo que más conviene
revisar antes de vender:

```bat
installer\instalar.py --dias 365   :: normal
installer\instalar.py --dias -1    :: vencida, dentro de la gracia
installer\instalar.py --dias -30   :: pasada la gracia
```

| | Qué debe pasar |
|---|---|
| `--dias 365` | Todo normal |
| `--dias -1` | **Sigue sacando gráficos** y avisa en el panel |
| `--dias -30` | `/graficos` responde **402**. El login y los datos siguen accesibles, para que el cliente pueda renovar |

La licencia se valida **offline** en cada arranque: la vigencia viaja
firmada dentro del propio token. En el autódromo la red se cae, y el
software no puede dejar de funcionar por eso.

---

## Cómo está armado

```
┌─────────────┐   AMCP 5250    ┌──────────────┐
│  CasparCG   │◄───────────────│              │
│  (gráficos) │                │              │
└─────────────┘                │              │
                               │   Backend    │      Navegador
┌─────────────┐   27017        │   FastAPI    │◄──── (panel, iPad,
│  MongoDB    │◄───────────────│   :8080      │       otro equipo)
└─────────────┘                │              │
                               │              │
┌─────────────┐   current.xml  │              │
│   MyLaps    │───────────────►│              │
│(cronometraje)│               └──────────────┘
└─────────────┘
```

Un solo equipo hace de servidor: ejecuta CasparCG, MongoDB y el backend.
No se trabaja sentado frente a él — el panel se abre desde el navegador de
cualquier dispositivo de la red, y un iPad es el formato recomendado.

El backend sirve también el frontend compilado, así que **todo va por un
solo puerto**.

| Carpeta | Qué es |
|---|---|
| `Backend/` | API FastAPI + MongoDB (Beanie) |
| `Frontend/` | Panel React + Vite |
| `Casparcg/` | Servidor de gráficos y las 36 plantillas |
| `installer/` | Instalador y validación de licencia |
| `launcher/` | Arranque del sistema en Windows |
| `tools/` | Herramientas de Zentogo — **no se distribuyen** |
| `docs/` | Manual, diagramas y maquetas |

El árbol completo está en [`docs/estructura.txt`](docs/estructura.txt).

---

## Las dos disciplinas

|  | Circuito | Drag |
|---|---|---|
| Formato | Carreras en pista | Aceleración por parejas |
| Datos | **Llegan de MyLaps** | **Se escriben en el panel** |
| Transponder | Obligatorio | No hace falta |
| Gráficos propios | 11 banderas, 3 tótems, cuadro de resultados, grilla | Duelo DragWar, Duelo de Competencia |
| Grilla de partida | Sí | No existe: se corre por llaves |

Pilotos y vehículos son compartidos. Un piloto es una persona, no una
inscripción: el mismo corre en las dos sin duplicar su ficha ni su foto.

---

## Documentación

| Documento | Para qué |
|---|---|
| [Manual del sistema (PDF)](docs/manual/Manual-Race-Core-Studio.pdf) | 33 páginas: instalación, módulos y disciplinas |
| [Flujo de instalación](docs/flujos/flujo-instalacion.png) | Los 12 pasos, de un vistazo |
| [Maquetas del asistente](docs/maquetas/) | Las 10 pantallas de instalación |
| [Licenciamiento](docs/licenciamiento.md) | El contrato: token, manifiesto y estados |
| [Instalador](installer/LEEME.md) | Qué hace cada paso y sus límites |
| [XML de demostración](Backend/src/public/demo/LEEME.md) | Los datos de prueba del cronometraje |

---

## Desarrollo

```bash
cd Backend && python -m pytest tests/ -q      # 113 pruebas
```

Sin MongoDB ni unidad de red montada: las pruebas usan el
`current-demo.xml` que viene con el producto.

```bash
# Backend en modo desarrollo
cd Backend && venv/Scripts/python.exe -m uvicorn main:app --reload

# Frontend con recarga en caliente
npm run dev --prefix Frontend

# Una carrera de demostración que avanza sola, para probar plantillas
python tools/demo/generar_current.py --salida C:/timing/current.xml --vivo
```

En desarrollo, `LICENSE_REQUIRED=false` en `Backend/.env` deja arrancar sin
licencia. El instalador lo pone en `true`.

---

## Estado

**Listo**

- [x] Backend: pilotos, vehículos, categorías, eventos, gráficos, cronometraje, clima
- [x] Panel React con sesión, roles y dos idiomas
- [x] 36 plantillas de CasparCG
- [x] Validación de licencia offline, con gracia y bloqueo
- [x] Asistente de instalación (14 endpoints)
- [x] Instalador con licencia validada sin servidor
- [x] Asistente de instalación en React, los siete pasos

**Pendiente**

- [ ] Empaquetar el instalador como `.exe` firmado
- [ ] Servidor de licencias (emisión, renovación, reasignación)
- [ ] Descarga de componentes desde el manifiesto firmado
- [ ] Servicio de vigilancia y pantalla de licencia expirada

---

<div align="center">
<sub>

**Zentogo Technologies** · Race Core Studio 1.0

</sub>
</div>

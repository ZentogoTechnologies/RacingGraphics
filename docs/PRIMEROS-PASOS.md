# Ver Race Core Studio corriendo en Windows 11

Guía de la primera vez, de cero a tener el panel abierto. Unos 30–40
minutos, casi todos de descargas.

---

## La forma corta

Baja **`rcs-setup.exe`** de la
[página de releases](../../releases/tag/instalador-pruebas) y ejecútalo.

Un solo archivo. No hace falta clonar nada antes: el propio instalador se
encarga.

Si prefieres no bajar un ejecutable, clona el repositorio y haz doble clic
en `installer\rcs-setup.bat`, que hace exactamente lo mismo.

Eso es todo. Pide la licencia y se encarga del resto: instala Python,
Node, Git LFS y MongoDB si faltan, descarga el software, lo compila y
abre el asistente en el navegador.

```
Correo:  zentogotech@gmail.com
Clave:   RCS1-XEA8-EXXK-EUNH-8M63
```

Tarda entre 20 y 40 minutos, casi todo descargas. Pide permisos de
administrador porque instala programas y registra servicios.

Cuando `rcs-setup.exe` esté empaquetado será el mismo proceso con un solo
archivo, sin necesidad de clonar nada primero.

### Opciones

```bat
rcs-setup.bat --destino D:\RaceCore     :: otra carpeta
rcs-setup.bat --con-recorte             :: incluye rembg (+200 MB)
rcs-setup.bat --sin-casparcg            :: sin gráficos, solo el panel
```

---

El resto de esta guía es **la forma larga**: los mismos pasos a mano, por
si algo falla o quieres entender qué hace cada uno.

---

## Antes de nada: Git LFS

**Este es el paso que rompe la instalación si se salta**, y no da un error
claro cuando pasa.

El repositorio guarda 27 archivos `.exe` y `.dll` de CasparCG con Git LFS.
Si clonas sin tener LFS instalado, esos archivos llegan como **ficheros de
texto de 130 bytes** con un puntero dentro, no como los binarios. CasparCG
no arranca y el error no dice nada de LFS.

```bat
winget install Git.Git
git lfs install
```

Comprueba después de clonar que `Casparcg\casparcg.exe` pese **megabytes**
y no bytes. Si pesa 130 bytes, faltó el `git lfs install`: bórralo todo y
vuelve a clonar.

---

## 1 · Instalar lo que hace falta

```bat
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install MongoDB.Server
```

| | Versión mínima | Por qué |
|---|---|---|
| Python | **3.12** | Lo exigen numpy 2.5 y pandas 3.0, fijados en `requirements.txt` |
| Node | **20.19** o 22+ | Lo exige Vite 8 |
| MongoDB | 6 o superior | La base del sistema |

CasparCG necesita además el **Visual C++ Redistributable 2015-2022**, que
suele venir ya con Windows 11. Si `casparcg.exe` no abre y no dice por qué,
instálalo:

```bat
winget install Microsoft.VCRedist.2015+.x64
```

**Cierra y vuelve a abrir la terminal** después de instalar: si no, Windows
no ve los comandos nuevos en el PATH.

Comprueba:

```bat
python --version
node --version
git lfs version
```

---

## 2 · Clonar

```bat
cd C:\
git clone -b test-production-1.0 https://github.com/ZentogoTechnologies/Race-Core-Studio.git
cd Race-Core-Studio
dir Casparcg\casparcg.exe
```

Ese último comando tiene que mostrar **varios MB**. Si muestra ~130 bytes,
vuelve al aviso de LFS de arriba.

---

## 3 · Arrancar MongoDB

```bat
net start MongoDB
```

Si dice que el servicio no existe, MongoDB se instaló sin registrarse como
servicio. Arráncalo a mano:

```bat
mkdir C:\data\db
"C:\Program Files\MongoDB\Server\8.0\bin\mongod.exe" --dbpath C:\data\db
```

Déjalo en esa ventana. Todo lo demás va en otra.

---

## 4 · Preparar el backend

```bat
python -m venv Backend\venv
Backend\venv\Scripts\python.exe -m pip install --upgrade pip
Backend\venv\Scripts\python.exe -m pip install -r Backend\requirements.txt
```

Tarda: `rembg` arrastra unos 200 MB. Es lo que recorta el fondo de las
fotos de pilotos sin salir a internet.

---

## 5 · Compilar el panel

```bat
npm install --prefix Frontend
npm run build --prefix Frontend
```

Deja el panel compilado en `Frontend\dist`, que es lo que sirve el backend.

---

## 6 · Instalar

```bat
Backend\venv\Scripts\python.exe installer\instalar.py
```

Pide la licencia:

```
Correo:  zentogotech@gmail.com
Clave:   RCS1-XEA8-EXXK-EUNH-8M63
```

Los cinco pasos tienen que salir en **OK**. Al terminar imprime una
dirección con `?token=…`: **cópiala**, hace falta en el paso 8.

---

## 7 · Arrancar el sistema

En una ventana aparte, y **déjala abierta**:

```bat
cd Backend
venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8080
```

Tiene que imprimir:

```
✅ Conectado a MongoDB
   ⚠ Sin configurar: el asistente de instalación está abierto
INFO:     Uvicorn running on http://0.0.0.0:8080
```

Para ver también los gráficos, arranca CasparCG en otra ventana:

```bat
cd Casparcg
casparcg.exe
```

### O todo de una vez

Si ya construiste el lanzador, hace estos dos pasos y abre el navegador
solo:

```bat
race-core-studio.exe
```

Arranca CasparCG, verifica MongoDB, levanta el backend con el panel y abre
`http://127.0.0.1:8080`. Para apagarlo todo: `race-core-studio.exe --detener`

Comprueba antes que `casparcg.exe` no sea un puntero de LFS: el lanzador lo
detecta y te lo dice, pero es mejor saberlo de entrada.

---

## 8 · Configurar desde el navegador

Pega la dirección con el token que dio el instalador. Son siete pasos:

1. **Bienvenida** — la licencia en verde y las direcciones de acceso
2. **Datos del cliente** — nombre del autódromo, país, ciudad
3. **Logo** — se puede omitir
4. **Las tres cuentas** — owner, admin y estándar. **Anota las contraseñas**
5. **Cronometraje** — pulsa «Usar el XML de demostración» si MyLaps no está
6. **Servidor de gráficos** — comprueba CasparCG
7. **Ubicación** — busca tu ciudad o escribe las coordenadas

Al terminar te deja en el login. Entra con la cuenta **owner**.

---

## 9 · Ya está corriendo

Elige disciplina (**Circuito** o **Drag**) y verás el panel.

Para ver datos de verdad moviéndose, en otra ventana:

```bat
python tools\demo\generar_current.py --salida C:\timing\current.xml --vivo
```

Y en Ajustes → Conexiones, apunta el cronometraje a `C:\timing\current.xml`.
Verás la clasificación avanzar vuelta a vuelta, con la penalización
incluida.

---

## Desde un iPad u otro equipo

El backend atiende en `0.0.0.0`, así que el panel se abre desde cualquier
dispositivo de la red:

```
http://<IP-del-servidor>:8080
```

La IP la muestra el instalador al terminar, y también Ajustes. Para que
otro equipo llegue hay que **abrir el puerto 8080 en el Firewall**:

```bat
netsh advfirewall firewall add rule name="Race Core Studio" dir=in action=allow protocol=TCP localport=8080
```

Ese comando necesita una terminal **como administrador**.

---

## Si algo falla

| Síntoma | Causa |
|---|---|
| `casparcg.exe` no abre, o pesa 130 bytes | Faltó `git lfs install` antes de clonar |
| El instalador se para en el paso 3 | MongoDB no está corriendo |
| «Falta el token de instalación» | Abriste la dirección sin el `?token=…` |
| «El sistema ya está configurado» | Ya se instaló. Ver «volver a empezar» abajo |
| El panel no carga, solo el API | Falta `npm run build --prefix Frontend` |
| La ruta de MyLaps no verifica | Es unidad mapeada (`W:\`). Usa `\\EQUIPO\carpeta\current.xml` |
| `python` no se reconoce | No reiniciaste la terminal tras instalarlo |

### Volver a empezar de cero

```bat
del Backend\.env Backend\licencia.lic Backend\licencia.estado.json Backend\instalacion.token
mongosh --eval "db.getSiblingDB('race-core-studio').dropDatabase()"
```

Y repite desde el paso 6.

---

## Los dos ejecutables

Cuando se empaqueten, serán dos, y hacen cosas distintas:

| Ejecutable | Cuándo | Qué hace |
|---|---|---|
| **`rcs-setup.exe`** | Una vez, al instalar | Pide la licencia, la ata al equipo, comprueba las piezas y abre el asistente |
| **`race-core-studio.exe`** | Cada día de carrera | Arranca CasparCG, MongoDB, el backend y el navegador |

El instalador no es el programa: se usa una vez y se olvida. El lanzador
es el que va al escritorio y el que se pulsa cada domingo.

Se construyen así, **en Windows** —PyInstaller genera un binario de la
máquina donde corre, así que un `.exe` solo sale de un Windows—:

```bat
installer\construir.bat     :: deja installer\dist\rcs-setup.exe
launcher\construir.bat      :: deja race-core-studio.exe en la raíz
```

Mientras no estén construidos, los pasos 6 y 7 de esta guía hacen lo
mismo llamando a Python directamente.

## Probar el vencimiento de la licencia

Lo que no se puede ensayar esperando un año:

```bat
Backend\venv\Scripts\python.exe installer\instalar.py --dias -1
```

Vencida ayer, dentro de la gracia: **sigue sacando gráficos** y avisa en el
panel.

```bat
Backend\venv\Scripts\python.exe installer\instalar.py --dias -30
```

Pasada la gracia: los gráficos responden **402**, pero el login y los datos
siguen accesibles para poder renovar.

Reinicia el backend después de cada cambio de licencia.

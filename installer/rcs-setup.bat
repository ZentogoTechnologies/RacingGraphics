@echo off
setlocal EnableDelayedExpansion

REM ======================================================================
REM  RACE CORE STUDIO - Instalador
REM
REM  Doble clic y ya. Instala Python, Node, Git LFS y MongoDB si faltan,
REM  descarga el software, lo compila y lo deja funcionando.
REM
REM  Es lo mismo que hara rcs-setup.exe cuando este empaquetado. Este .bat
REM  existe para poder instalar sin haber compilado nada todavia.
REM ======================================================================

title Race Core Studio - Instalador
cd /d "%~dp0"

echo.
echo   RACE CORE STUDIO
echo   Instalador de Zentogo Technologies
echo   ==================================
echo.

REM ── Permisos de administrador ─────────────────────────────
REM  Hacen falta para instalar programas con winget, registrar MongoDB
REM  como servicio y abrir el puerto en el Firewall. Si no los tiene, se
REM  relanza pidiendolos en vez de fallar a mitad.
net session >nul 2>&1
if errorlevel 1 (
    echo   Se necesitan permisos de administrador.
    echo   Windows va a pedir confirmacion...
    echo.
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM ── Python ────────────────────────────────────────────────
REM  El instalador esta escrito en Python, asi que es lo unico que hay
REM  que resolver aqui: el resto lo instala el propio setup.py.
where python >nul 2>&1
if errorlevel 1 (
    echo   [1/2] Python no esta instalado. Instalandolo...
    echo.

    where winget >nul 2>&1
    if errorlevel 1 (
        echo   [X] No encuentro winget.
        echo.
        echo       Viene de serie en Windows 11. En Windows 10 se instala
        echo       desde la Microsoft Store, buscando:
        echo         "Instalador de aplicaciones"
        echo.
        pause
        exit /b 1
    )

    winget install --id Python.Python.3.12 --silent ^
        --accept-package-agreements --accept-source-agreements

    REM  winget deja Python en el PATH del sistema, pero esta ventana ya
    REM  tenia cargado el suyo de antes. Hay que volver a leerlo.
    for /f "tokens=2,*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul ^| find "Path"') do set "RUTA_SIS=%%b"
    for /f "tokens=2,*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul ^| find "Path"') do set "RUTA_USR=%%b"
    set "PATH=!RUTA_SIS!;!RUTA_USR!;!PATH!"

    where python >nul 2>&1
    if errorlevel 1 (
        echo.
        echo   [!] Python se instalo, pero esta ventana no lo ve todavia.
        echo.
        echo       Cierra esta ventana y vuelve a ejecutar el instalador.
        echo       La segunda vez ya lo encontrara.
        echo.
        pause
        exit /b 1
    )

    echo   [OK] Python instalado.
    echo.
)

REM ── El instalador de verdad ───────────────────────────────
echo   [2/2] Arrancando el instalador...
echo.

python "%~dp0setup.py" %*

if errorlevel 1 (
    echo.
    echo   La instalacion no termino. Revisa los mensajes de arriba.
    pause
    exit /b 1
)

endlocal

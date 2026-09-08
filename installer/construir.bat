@echo off
REM ======================================================================
REM  Construye RaceCoreStudio-Setup.exe a partir de instalar.py
REM
REM  Ejecutar desde cualquier sitio:   installer\construir.bat
REM
REM  Tiene que correr EN WINDOWS. PyInstaller no cruza plataformas: genera
REM  un binario de la maquina donde se ejecuta, asi que un .exe de Windows
REM  solo sale de un Windows.
REM ======================================================================

set "AQUI=%~dp0"
cd /d "%AQUI%.."

echo.
echo  RACE CORE STUDIO - Construyendo el instalador
echo  =============================================
echo.

if not exist "Backend\venv\Scripts\python.exe" (
    echo  [X] No encuentro el entorno virtual del backend.
    echo.
    echo      Crealo con:
    echo        python -m venv Backend\venv
    echo        Backend\venv\Scripts\python.exe -m pip install -r Backend\requirements.txt
    echo        Backend\venv\Scripts\python.exe -m pip install pyinstaller
    echo.
    pause
    exit /b 1
)

REM El icono se pasa con ruta absoluta a proposito: PyInstaller resuelve
REM --icon contra --specpath, no contra el directorio actual, y una ruta
REM relativa acaba duplicando la carpeta (installer\installer\...).
echo  Empaquetando...
Backend\venv\Scripts\python.exe -m PyInstaller ^
  --onefile --console --clean --noconfirm ^
  --name RaceCoreStudio-Setup ^
  --icon "%AQUI%..\launcher\race-core-studio.ico" ^
  --paths "Backend" ^
  --paths "tools\licencias" ^
  --paths "installer" ^
  --hidden-import pymongo ^
  --hidden-import jwt ^
  --hidden-import cryptography ^
  --hidden-import licencia_local ^
  --hidden-import emitir ^
  --collect-submodules cryptography ^
  --distpath "%AQUI%dist" --workpath "%AQUI%build" --specpath "%AQUI%." ^
  "%AQUI%instalar.py"

if errorlevel 1 (
  echo.
  echo  [X] FALLO el empaquetado.
  echo.
  echo      Si falta PyInstaller:
  echo        Backend\venv\Scripts\python.exe -m pip install pyinstaller
  echo.
  pause
  exit /b 1
)

echo.
echo  [OK] Listo:  installer\dist\RaceCoreStudio-Setup.exe
echo.
echo  AVISO: el .exe NO va firmado. Windows SmartScreen lo va a marcar
echo  como "editor desconocido" en cada equipo donde se ejecute. Para
echo  venderlo hace falta un certificado Authenticode.
echo.
pause

@echo off
REM Reconstruye race-core-studio.exe a partir del script del lanzador.
REM Ejecutar desde cualquier sitio:  launcher\construir.bat

REM %~dp0 es la carpeta launcher\ con ruta absoluta. El icono se pasa
REM asi a proposito: PyInstaller resuelve --icon contra --specpath, no
REM contra el directorio actual, y una ruta relativa acaba duplicando
REM la carpeta (launcher\launcher\...).
set "AQUI=%~dp0"
cd /d "%AQUI%.."

echo Empaquetando el lanzador...
Backend\venv\Scripts\python.exe -m PyInstaller ^
  --onefile --console --clean --noconfirm --noupx ^
  --name race-core-studio ^
  --icon "%AQUI%race-core-studio.ico" ^
  --version-file "%AQUI%version-info.txt" ^
  --hidden-import pymongo ^
  --distpath "%AQUI%dist" --workpath "%AQUI%build" --specpath "%AQUI%." ^
  "%AQUI%race_core_studio.py"

if errorlevel 1 (
  echo.
  echo FALLO el empaquetado. Si falta PyInstaller:
  echo   Backend\venv\Scripts\python.exe -m pip install pyinstaller
  pause
  exit /b 1
)

REM El .exe queda bloqueado mientras el lanzador este abierto.
taskkill /IM race-core-studio.exe /F >nul 2>&1

copy /Y "%AQUI%dist\race-core-studio.exe" race-core-studio.exe
echo.
echo Listo: race-core-studio.exe
pause

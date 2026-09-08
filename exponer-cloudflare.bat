@echo off
setlocal

REM ======================================================================
REM  Expone Race Core Studio en internet con un tunel de Cloudflare.
REM
REM  El tunel apunta al 8080, donde el backend sirve el API y tambien el
REM  frontend compilado. Por eso basta con una direccion: si el frontend
REM  fuera por su propio puerto habria que exponer dos y decirle al
REM  navegador cual es cual.
REM
REM  Requiere cloudflared:   winget install --id Cloudflare.cloudflared
REM
REM  Al arrancar imprime una direccion terminada en trycloudflare.com.
REM  Esa es la que se comparte. Vive mientras esta ventana este abierta:
REM  al cerrarla el tunel muere y la direccion deja de existir.
REM ======================================================================

echo.
echo  RACE CORE STUDIO - Tunel de Cloudflare
echo  ======================================
echo.

where cloudflared >nul 2>nul
if errorlevel 1 (
    echo  [X] cloudflared no esta instalado.
    echo.
    echo      Instalalo con:
    echo      winget install --id Cloudflare.cloudflared
    echo.
    pause
    exit /b 1
)

REM Sin backend no hay nada que exponer, y el tunel levantaria igual
REM dando error 502 a quien entre.
curl -s -o nul -m 5 http://127.0.0.1:8080/
if errorlevel 1 (
    echo  [X] El backend no responde en el puerto 8080.
    echo.
    echo      Arranca Race Core Studio primero, con race-core-studio.exe
    echo      o levantando el backend a mano.
    echo.
    pause
    exit /b 1
)

echo  [OK] Backend respondiendo en el 8080.
echo.
echo  Abriendo el tunel. La direccion aparece abajo en unos segundos,
echo  en el recuadro, terminada en trycloudflare.com
echo.
echo  Deja esta ventana abierta. Al cerrarla se cae el tunel.
echo.

cloudflared tunnel --url http://localhost:8080

endlocal

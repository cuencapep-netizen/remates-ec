@echo off
rem Instala las dependencias dentro de .\vendor (no toca el Python del sistema)
setlocal
cd /d "%~dp0"

set "PY="
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo No se encontro Python 3. Instalalo desde https://www.python.org/downloads/
  pause
  exit /b 1
)

echo Descargando dependencias en .\vendor ...
%PY% -m pip install --no-cache-dir --target "%~dp0vendor" -r requirements.txt
if errorlevel 1 (
  echo.
  echo No se pudieron descargar las dependencias. Revisa tu conexion o el proxy.
  pause
  exit /b 1
)

echo.
echo Listo. Ya puedes abrir iniciar.bat
pause

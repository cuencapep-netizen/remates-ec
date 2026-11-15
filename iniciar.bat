@echo off
rem Lanzador de Remates Judiciales EC
rem Uso: doble clic. Si falla, la ventana se queda abierta mostrando el error.
setlocal
cd /d "%~dp0"

rem Dependencias locales (lxml, Pillow, openpyxl) empaquetadas en .\vendor
if exist "%~dp0vendor" set "PYTHONPATH=%~dp0vendor"

set "PY="

rem 1) Lanzador oficial de Python
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY=py -3"

rem 2) Python en el PATH
if not defined PY (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)

rem 3) Python del entorno de desarrollo (ultimo recurso)
if not defined PY (
  if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" (
    set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
  )
)

if not defined PY (
  echo.
  echo   No se encontro Python 3 en este equipo.
  echo   Instala Python 3.10 o superior desde https://www.python.org/downloads/
  echo   y marca la casilla "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

rem Comprueba que esten las librerias necesarias
%PY% -c "import lxml, PIL" >nul 2>nul
if errorlevel 1 (
  echo.
  echo   Faltan dependencias de Python ^(lxml, Pillow, openpyxl^).
  echo   Ejecuta una sola vez:  instalar_dependencias.bat
  echo.
  pause
  exit /b 1
)

echo Iniciando Remates Judiciales EC...
%PY% -m app.main
if errorlevel 1 (
  echo.
  echo   La app se cerro con un error ^(ver mensaje arriba^).
  echo.
  pause
)

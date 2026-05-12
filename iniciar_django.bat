@echo off
REM Script para iniciar Django con Waitress al arrancar Windows
REM Ajusta las rutas según tu instalación

REM Ruta al entorno virtual
set VENV_PATH=C:\ruta\a\tu\proyecto\.venv
REM Ruta al proyecto
set PROJECT_PATH=C:\ruta\a\tu\proyecto
REM Puerto
set PORT=8000

cd /d %PROJECT_PATH%
call %VENV_PATH%\Scripts\activate.bat
waitress-serve --listen=*:%%PORT%% config.wsgi:application

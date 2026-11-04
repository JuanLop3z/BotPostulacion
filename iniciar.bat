@echo off
setlocal
cd /d "%~dp0" || exit /b 1

if /i "%~1"=="--backend" goto backend
if /i "%~1"=="--frontend" goto frontend
if not "%~1"=="" if /i not "%~1"=="--check" goto usage

echo AutoJob AI - Inicio local
echo.
if not exist ".venv\Scripts\python.exe" (
    echo Falta el entorno Python. Ejecuta primero: python scripts\setup.py
    goto failed
)
where node.exe >nul 2>&1
if errorlevel 1 (
    echo Falta Node.js. Instala Node.js 22 o superior y ejecuta python scripts\setup.py
    goto failed
)
where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo No se encuentra npm.cmd en PATH. Revisa la instalacion de Node.js.
    goto failed
)
if not exist "frontend\node_modules\.bin\next.cmd" (
    echo Faltan las dependencias del frontend. Ejecuta: python scripts\setup.py
    goto failed
)
".venv\Scripts\python.exe" -c "import uvicorn, alembic" >nul 2>&1
if errorlevel 1 (
    echo Faltan las dependencias del backend. Ejecuta: python scripts\setup.py
    goto failed
)
if /i "%~1"=="--check" (
    echo Requisitos de inicio disponibles.
    exit /b 0
)

echo Preparando configuracion y migraciones...
".venv\Scripts\python.exe" scripts\setup.py --skip-install
if errorlevel 1 goto failed

start "AutoJob AI - Backend" "%ComSpec%" /d /k call "%~f0" --backend
if errorlevel 1 goto failed
start "AutoJob AI - Frontend" "%ComSpec%" /d /k call "%~f0" --frontend
if errorlevel 1 goto failed

echo.
echo Backend y frontend iniciandose en dos ventanas.
echo Dashboard: http://localhost:3000
echo API:       http://localhost:8000/docs
echo Espera a que ambas ventanas indiquen que el servidor esta listo.
echo Para detenerlos, pulsa Ctrl+C en cada ventana.
exit /b 0

:backend
title AutoJob AI - Backend
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
exit /b %errorlevel%

:frontend
title AutoJob AI - Frontend
cd frontend || exit /b 1
call npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
exit /b %errorlevel%

:usage
echo Uso: iniciar.bat [--check]
exit /b 2

:failed
echo.
echo No se pudo iniciar AutoJob AI. Revisa el mensaje anterior.
if /i not "%~1"=="--check" pause
exit /b 1

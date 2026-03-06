@echo off
setlocal

REM CoPaw launcher for this repository (Windows)
REM Usage:
REM   start_copaw.bat
REM   start_copaw.bat 127.0.0.1 8088

set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

set "PYTHON_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe"
set "USERPROFILE=%PROJECT_DIR%\.home"
set "HOMEDRIVE="
set "HOMEPATH="

if not exist "%PYTHON_EXE%" (
  echo [copaw] .venv Python not found: %PYTHON_EXE%
  echo [copaw] Please ensure .venv exists in project root.
  exit /b 1
)

if not exist "%USERPROFILE%" mkdir "%USERPROFILE%"

set "HOST=127.0.0.1"
set "PORT=8088"
if not "%~1"=="" set "HOST=%~1"
if not "%~2"=="" set "PORT=%~2"

set "COPAW_CFG=%USERPROFILE%\.copaw\config.json"
if not exist "%COPAW_CFG%" (
  echo [copaw] First run detected, running init...
  "%PYTHON_EXE%" -m copaw init --defaults
  if errorlevel 1 (
    echo [copaw] Init failed.
    exit /b 1
  )
)

echo [copaw] Starting on http://%HOST%:%PORT%/
"%PYTHON_EXE%" -m copaw app --host %HOST% --port %PORT%
exit /b %ERRORLEVEL%

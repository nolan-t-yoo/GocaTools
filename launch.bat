@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo  GocaTools - Pokemon GO redemption card generator
echo ============================================================
echo.

rem ── 1. Locate a Python 3.9+ interpreter ────────────────────────────────────
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"
if not defined PY (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%~fD\python.exe" set "PY=%%~fD\python.exe"
    )
)
if not defined PY (
    echo [ERROR] Python 3 was not found on this computer.
    echo         Easiest fix: right-click _quickstart.ps1 and choose
    echo         "Run with PowerShell" - it installs Python for you.
    echo         Or install it from https://www.python.org/downloads/ and tick
    echo         "Add python.exe to PATH" during setup, then run this again.
    goto :fail
)

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.9 or newer is required.
    goto :fail
)

rem ── 2. Create (or reuse) a virtual environment inside this folder ──────────
set "VPY=%CD%\.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo Creating a private Python environment in .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        goto :fail
    )
)

if not exist "%VPY%" (
    echo [ERROR] %VPY% is missing.
    goto :fail
)

rem ── 3. Install the two small dependencies on first run ─────────────────────
"%VPY%" -c "import qrcode, reportlab" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies ^(qrcode, pillow, reportlab^) - first run only ...
    "%VPY%" -m pip install --upgrade pip >nul 2>&1
    "%VPY%" -m pip install "qrcode[pil]" reportlab
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed. Check your internet connection.
        goto :fail
    )
)

rem ── 4. Start the UI ────────────────────────────────────────────────────────
"%VPY%" -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] This Python build has no tkinter, so the UI cannot start.
    echo         Re-install Python from python.org with the default options.
    goto :fail
)

echo Starting GocaTools ...
"%VPY%" -m goca
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo GocaTools could not start (see the messages above).
pause
exit /b 1

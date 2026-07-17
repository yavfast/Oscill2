@echo off
setlocal enabledelayedexpansion

rem ===========================================================================
rem web_oscill.bat - Windows launcher for the web_oscill server
rem (counterpart of web_oscill.sh; see that file for the Linux version)
rem
rem Features:
rem  - Find Python, create the .venv if missing
rem  - Install dependencies from requirements.txt
rem  - Stop any instance already listening on the port
rem  - Start the uvicorn server
rem  - Open the browser at the web page
rem
rem USB (CP210x): install the Silicon Labs CP210x VCP driver so the scope shows
rem   up as a COMx port; auto-detect then finds it by VID/PID (10C4:840E).
rem BLUETOOTH on Windows: the native Linux RFCOMM path is not available here.
rem   Instead pair the scope in Windows Bluetooth settings (PIN 0000); Windows
rem   then creates an OUTGOING COM port for it (see Bluetooth Settings ->
rem   "More Bluetooth options" -> "COM Ports"). Connect to that COMx from the
rem   web UI as a normal serial device (transport = USB/serial).
rem ===========================================================================

rem --- Configuration ---
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "VENV_DIR=%SCRIPT_DIR%\.venv"
set "REQUIREMENTS_FILE=%SCRIPT_DIR%\requirements.txt"
set "HOST=127.0.0.1"
set "PORT=8000"
set "URL=http://%HOST%:%PORT%"

echo [INFO] === Web Oscill Launcher (Windows) ===
echo [INFO] Script directory: %SCRIPT_DIR%

rem --- Find Python ---
rem Prefer the `py` launcher: `python` on PATH is often the Microsoft Store
rem App-Execution-Alias stub, which opens the Store instead of running Python.
set "PYTHON_CMD="
where py >nul 2>&1 && set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
    where python >nul 2>&1 && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo [ERROR] Python not found. Install Python 3.8+ and add it to PATH.
    exit /b 1
)
for /f "tokens=2" %%v in ('%PYTHON_CMD% --version 2^>^&1') do set "PYVER=%%v"
echo [INFO] Found Python %PYVER%

rem --- Create venv if missing ---
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Creating...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
    echo [INFO] Virtual environment created at %VENV_DIR%
) else (
    echo [INFO] Virtual environment found at %VENV_DIR%
)

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

rem --- Install / update dependencies ---
if exist "%REQUIREMENTS_FILE%" (
    echo [INFO] Installing/updating dependencies from requirements.txt...
    "%VENV_PY%" -m pip install --upgrade pip --quiet
    "%VENV_PY%" -m pip install -r "%REQUIREMENTS_FILE%" --quiet
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        exit /b 1
    )
    echo [INFO] Dependencies installed successfully
) else (
    echo [WARN] requirements.txt not found; installing minimal set...
    "%VENV_PY%" -m pip install fastapi "uvicorn[standard]" pyserial --quiet
)

rem --- Stop any instance already listening on the port ---
echo [INFO] Checking for a running instance on port %PORT%...
set "FOUND_PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
    set "FOUND_PID=%%p"
)
if defined FOUND_PID (
    echo [WARN] Stopping process !FOUND_PID! on port %PORT%...
    taskkill /F /PID !FOUND_PID! >nul 2>&1
    timeout /t 2 /nobreak >nul
) else (
    echo [INFO] No running instance found
)

rem --- Open the browser (before the server takes over the console) ---
echo [INFO] Opening browser at %URL%
start "" "%URL%"

rem --- Start the server in the foreground (Ctrl+C to stop) ---
echo [INFO] Starting web_oscill server at %URL%
echo [INFO] Press Ctrl+C to stop.
cd /d "%SCRIPT_DIR%"
"%VENV_PY%" -m uvicorn web_oscill.main:app --host %HOST% --port %PORT% --log-level info

endlocal

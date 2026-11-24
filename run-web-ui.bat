@echo off
setlocal
title yt-dlp Web UI

cd /d "%~dp0"
echo.
echo ==========================================
echo          yt-dlp Web UI - Launcher
echo ==========================================
echo.

REM Detect Python (Python 3.10 or newer is recommended).
set "PYTHON_CMD=py -3"
py -3 --version >nul 2>&1
if errorlevel 1 (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python was not found.
        echo Install Python 3.10+ from https://www.python.org/downloads/
        echo During setup, enable "Add Python to PATH".
        goto :failed
    )
    set "PYTHON_CMD=python"
)

REM Create an isolated virtual environment on first launch.
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating Python virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        goto :failed
    )
) else (
    echo [1/4] Python environment found.
)

echo [2/4] Installing or checking application dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "web-ui\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check your internet connection.
    goto :failed
)

echo [3/4] Checking FFmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg was not found in PATH.
    echo MP3 extraction and some MP4 merges may fail until FFmpeg is installed.
    echo See https://ffmpeg.org/download.html
) else (
    echo FFmpeg found.
)

echo [4/4] Starting Web UI at http://127.0.0.1:8080
echo.
echo Keep this window open while using the application.
echo Press Ctrl+C to stop the server.
echo.

REM Open the browser after the server has had time to start.
start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8080'"

".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "web-ui" --host 127.0.0.1 --port 8080
if errorlevel 1 (
    echo.
    echo [ERROR] The Web UI stopped unexpectedly.
    goto :failed
)

echo.
echo Web UI stopped.
pause
exit /b 0

:failed
echo.
echo Setup or startup did not complete. Read the messages above.
pause
exit /b 1

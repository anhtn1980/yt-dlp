@echo off
setlocal EnableExtensions
title yt-dlp Web UI

cd /d "%~dp0"
echo.
echo ==========================================
echo       yt-dlp Web UI - Update and Run
echo ==========================================
echo.

REM Require Git so this launcher can keep the local app in sync with origin/dev.
where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git was not found in PATH.
    echo Install Git for Windows, then run this file again.
    goto :failed
)

for /f "delims=" %%B in ('git branch --show-current') do set "CURRENT_BRANCH=%%B"
if /i not "%CURRENT_BRANCH%"=="dev" (
    echo [ERROR] Current branch is "%CURRENT_BRANCH%", not "dev".
    echo Switch to dev before running this development launcher:
    echo     git switch dev
    goto :failed
)

REM Never overwrite local edits when updating.
set "DIRTY="
for /f "delims=" %%S in ('git status --porcelain') do set "DIRTY=1"
if defined DIRTY (
    echo [ERROR] Your working tree has local changes.
    echo Commit or safely back up those changes before updating.
    git status --short
    goto :failed
)

echo [1/5] Updating branch dev from GitHub...
git pull --ff-only origin dev
if errorlevel 1 (
    echo [ERROR] Git update failed. No application files were changed by this launcher.
    goto :failed
)

for /f %%H in ('git rev-parse --short HEAD') do set "BUILD_REVISION=%%H"
set "YT_DLP_WEB_UI_REVISION=%BUILD_REVISION%"
echo Running source revision: %BUILD_REVISION%
echo Verify at http://127.0.0.1:8080/api/health
echo.

REM Detect an existing listener so the user does not accidentally keep using an old server.
set "PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8080 .*LISTENING"') do set "PORT_PID=%%P"
if defined PORT_PID (
    echo [NOTICE] Port 8080 is already used by PID %PORT_PID%.
    tasklist /FI "PID eq %PORT_PID%"
    choice /C YN /M "Stop this process so the updated Web UI can start"
    if errorlevel 2 (
        echo [CANCELLED] Existing process was left untouched.
        goto :failed
    )
    taskkill /PID %PORT_PID% /T /F
    if errorlevel 1 (
        echo [ERROR] Could not stop PID %PORT_PID%. Close its server window manually.
        goto :failed
    )
)

REM Detect Python.
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
    echo [2/5] Creating Python virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        goto :failed
    )
) else (
    echo [2/5] Python environment found.
)

echo [3/5] Installing or checking application dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "web-ui\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check your internet connection.
    goto :failed
)

echo [4/5] Checking FFmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg was not found in PATH.
    echo MP3 extraction and some MP4 merges may fail until FFmpeg is installed.
    echo See https://ffmpeg.org/download.html
) else (
    echo FFmpeg found.
)

echo [5/5] Starting Web UI at http://127.0.0.1:8080
echo Keep this window open while using the application.
echo Press Ctrl+C to stop the server.
echo.

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
echo Startup did not complete. Read the messages above.
pause
exit /b 1

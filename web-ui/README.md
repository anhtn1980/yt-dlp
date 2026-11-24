# yt-dlp Web UI

A responsive browser interface for the yt-dlp engine. The initial target is Windows desktop, with optional access from a phone or other device on the same trusted LAN.

## Requirements

- Python 3.10 or newer
- FFmpeg (needed for MP4 merging and MP3 extraction in later milestones)

## Windows quick start

From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r web-ui\requirements.txt
python -m uvicorn app.main:app --app-dir web-ui --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:8080/api/health to verify the M0 backend scaffold.

If PowerShell blocks virtual-environment activation, use the Python executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r web-ui\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir web-ui --host 127.0.0.1 --port 8080
```

## LAN mode

LAN mode is not enabled by default and should not be exposed until authentication and access controls are implemented and reviewed. Binding to `0.0.0.0` alone is not a secure remote-access solution. See [the architecture](../docs/WEB-UI-ARCHITECTURE.md).

## Current status

M0 only provides the backend scaffold and health check. The URL form, GET MP4/GET MP3 actions, task progress and file delivery are planned for M1.

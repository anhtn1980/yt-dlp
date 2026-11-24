# yt-dlp Web UI

Responsive web interface for yt-dlp. M1 includes URL inspection, GET MP4, GET MP3, task progress and completed-file delivery.

## Requirements

- Python 3.10+
- FFmpeg installed and available on PATH (required for audio extraction and format merging)

## Windows — local mode

From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r web-ui\requirements.txt
python -m uvicorn app.main:app --app-dir web-ui --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:8080. The health endpoint is http://127.0.0.1:8080/api/health.

## YouTube sign-in with Cốc Cốc

On Windows, the backend automatically tries to read cookies from the default Cốc Cốc profile:

`%LOCALAPPDATA%\CocCoc\Browser\User Data\Default`

Sign in to YouTube in Cốc Cốc first. If your profile is stored elsewhere, set `COCCOC_PROFILE_PATH` to the full profile directory before starting the server. For example:

```powershell
$env:COCCOC_PROFILE_PATH = "$env:LOCALAPPDATA\CocCoc\Browser\User Data\Profile 1"
run-web-ui.bat
```

If cookie extraction reports a database lock/copy error, fully exit Cốc Cốc (including background processes) and retry. Open the local Web UI in another browser such as Edge while Cốc Cốc is closed. Cookies are read locally by yt-dlp and are not uploaded by this application. Treat browser cookies as credentials: do not export, share, commit or log them. Cookie access may not resolve every YouTube bot challenge; use only your own signed-in session and respect YouTube's terms.

## LAN mode — not enabled by default

The application currently binds to localhost in the documented command. Do not expose it to a LAN or the public internet until authentication, authorization, rate limits and network controls have been implemented and reviewed. Binding to `0.0.0.0` by itself is not safe. LAN access is a planned deployment milestone, not a supported secure mode in this M1 build.

## Notes

- Downloads are saved in `web-ui/downloads/`.
- The application accepts HTTP(S) URLs and rejects URLs resolving to non-public IP addresses as a basic SSRF mitigation. This is defense-in-depth, not a substitute for network egress controls.
- The task store is in memory and is reset when the server restarts.
- Download only content you are authorized to save. The application does not attempt to bypass DRM or access controls.

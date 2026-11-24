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

On Windows, the backend reads the local Cốc Cốc Chromium profile. The default profile is:

`%LOCALAPPDATA%\CocCoc\Browser\User Data\Default`

The cookie database is detected at `Default\Network\Cookies` first, then `Default\Cookies`. If your profile is stored elsewhere, set `COCCOC_PROFILE_PATH` to the full profile directory before starting the server:

```powershell
$env:COCCOC_PROFILE_PATH = "$env:LOCALAPPDATA\CocCoc\Browser\User Data\Profile 1"
.\run-web-ui.bat
```

### Cookie snapshot behavior

The app no longer asks yt-dlp to copy the live browser database directly. Before each metadata or download operation, it creates a temporary SQLite backup of the cookie database using SQLite's backup API (so committed WAL data is included), and copies the profile's `Local State` encryption metadata alongside it. yt-dlp reads from that temporary profile snapshot. The temporary directory is removed when the operation finishes.

This is designed to avoid the Windows file-copy failure that can happen while Cốc Cốc is running. It does not bypass YouTube sign-in, bot checks, DRM or other access controls. If Windows or the browser prevents SQLite from opening the database even for a read-only snapshot, the app returns an actionable error; close Cốc Cốc completely and retry.

Cookies and the copied `Local State` are credentials-related data. They remain on this computer, are used only in a temporary directory, and must never be exported, shared, committed or logged. Use only your own signed-in browser profile.

## LAN mode — not enabled by default

The application currently binds to localhost in the documented command. Do not expose it to a LAN or the public internet until authentication, authorization, rate limits and network controls have been implemented and reviewed. Binding to `0.0.0.0` by itself is not safe. LAN access is a planned deployment milestone, not a supported secure mode in this M1 build.

## Developer tests

From the repository root, run the Cốc Cốc snapshot unit tests with:

```powershell
.\\.venv\\Scripts\\python.exe -m unittest discover -s web-ui\\tests -v
```

These tests use a synthetic SQLite database and do not read or expose the real browser cookies.

## Notes

- Downloads are saved in `web-ui/downloads/`.
- The application accepts HTTP(S) URLs and rejects URLs resolving to non-public IP addresses as a basic SSRF mitigation. This is defense-in-depth, not a substitute for network egress controls.
- The task store is in memory and is reset when the server restarts.
- Download only content you are authorized to save. The application does not attempt to bypass DRM or access controls.

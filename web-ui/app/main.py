"""Minimal FastAPI application scaffold for the yt-dlp Web UI (M0)."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="yt-dlp Web UI",
    version="0.1.0",
    description="A minimal browser interface for the yt-dlp engine.",
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Return a lightweight health response for local diagnostics."""
    return {"status": "ok", "service": "yt-dlp-web-ui", "milestone": "M0"}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Expose a small placeholder until the M1 browser interface is added."""
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>yt-dlp Web UI</title>
  <style>
    :root { color-scheme: light dark; font-family: Inter, system-ui, sans-serif; }
    body { min-height: 100vh; margin: 0; display: grid; place-items: center;
           background: Canvas; color: CanvasText; }
    main { width: min( min(92vw, 34rem), 34rem); padding: 2rem; }
    h1 { letter-spacing: -.04em; margin-bottom: .5rem; }
    p { line-height: 1.6; opacity: .72; }
    code { padding: .2rem .4rem; border-radius: .4rem; background: color-mix(in srgb, CanvasText 10%, Canvas); }
  </style>
</head>
<body>
  <main>
    <h1>yt-dlp Web UI</h1>
    <p>Foundation is ready. The URL field and GET MP4 / GET MP3 workflow are scheduled for M1.</p>
    <p>Health: <code>/api/health</code></p>
  </main>
</body>
</html>"""

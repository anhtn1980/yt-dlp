"""FastAPI backend for the yt-dlp Web UI (M1)."""
from __future__ import annotations

import ipaddress
import logging
import os
import shutil
import socket
import sqlite3
import tempfile
import threading
import uuid
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT_DIR / "static"
DOWNLOAD_DIR = ROOT_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Cốc Cốc stores its Chromium profile under this default Windows location.
# Override COCCOC_PROFILE_PATH if the browser uses a different profile folder.
COCCOC_PROFILE_DIR = Path(
    os.environ.get(
        "COCCOC_PROFILE_PATH",
        str(Path.home() / "AppData/Local/CocCoc/Browser/User Data/Default"),
    )
).expanduser()
COCCOC_USER_DATA_DIR = COCCOC_PROFILE_DIR.parent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yt-dlp-web-ui")
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="yt-dlp")
tasks: dict[str, dict[str, Any]] = {}
tasks_lock = threading.Lock()

app = FastAPI(
    title="yt-dlp Web UI",
    version="0.2.0",
    description="A responsive browser interface for the yt-dlp engine.",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class URLRequest(BaseModel):
    url: str = Field(min_length=8, max_length=4096)


def validate_public_http_url(raw_url: str) -> str:
    """Accept HTTP(S) URLs and reject obvious local/private network targets."""
    parsed = urlparse(raw_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Please enter a valid HTTP or HTTPS URL.")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="URLs containing embedded credentials are not accepted.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        for item in addresses:
            address = ipaddress.ip_address(item[4][0])
            if not address.is_global:
                raise HTTPException(status_code=400, detail="Links to local or private network addresses are not allowed.")
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="The URL host could not be resolved.") from None
    except ValueError:
        raise HTTPException(status_code=400, detail="The URL host or port is invalid.") from None
    return raw_url.strip()


def _find_coccoc_cookie_db(profile_dir: Path) -> Path:
    """Find the active Chromium cookie DB without scanning extension storage."""
    candidates = (
        profile_dir / "Network" / "Cookies",
        profile_dir / "Cookies",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Cốc Cốc cookie database was not found in profile: {profile_dir}"
    )


def _sqlite_snapshot(source: Path, destination: Path) -> None:
    """Create a transactionally consistent SQLite snapshot, including WAL data."""
    # Open the live browser database in SQLite read-only mode from the
    # start. PRAGMA query_only alone is not equivalent: sqlite3.connect()
    # otherwise first requests a read-write connection, which can fail for
    # Chromium's live Cookies database even when read-only access is allowed.
    # Path.as_uri() safely quotes Windows drive letters and spaces.
    src = None
    dst = None
    stage = "opening source database in read-only mode"
    try:
        source_uri = source.resolve().as_uri() + "?mode=ro"
        src = sqlite3.connect(source_uri, uri=True, timeout=15)
        src.execute("PRAGMA query_only = ON")
        stage = "opening destination snapshot database"
        dst = sqlite3.connect(str(destination.resolve()), timeout=15)
        stage = "copying SQLite database with backup API"
        src.backup(dst, pages=256, sleep=0.1)
        dst.commit()
    except (sqlite3.Error, OSError) as exc:
        raise RuntimeError(
            f"SQLite snapshot failed while {stage}; "
            f"source={source.resolve()}; destination={destination.resolve()}; "
            f"destination_parent_exists={destination.parent.is_dir()}; "
            f"destination_parent_writable={os.access(destination.parent, os.W_OK)}; "
            f"cause={type(exc).__name__}: {exc}"
        ) from exc
    finally:
        if dst is not None:
            dst.close()
        if src is not None:
            src.close()


@contextmanager
def coccoc_cookie_options(options: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Give yt-dlp a private snapshot of Cốc Cốc cookies.

    yt-dlp's Chromium reader copies the live Cookies DB with shutil.copy().
    On Windows that copy can fail while Cốc Cốc has the database open. SQLite's
    backup API reads a consistent snapshot instead, including committed WAL
    pages. Local State is copied so yt-dlp can use the browser's local
    encryption metadata. Temporary sensitive files are removed on exit.
    """
    configured = dict(options)
    if not COCCOC_PROFILE_DIR.is_dir():
        yield configured
        return

    cookie_db = _find_coccoc_cookie_db(COCCOC_PROFILE_DIR)
    with tempfile.TemporaryDirectory(prefix="yt-dlp-coccoc-") as temp_root:
        snapshot_user_data = Path(temp_root) / "User Data"
        snapshot_profile = snapshot_user_data / COCCOC_PROFILE_DIR.name
        snapshot_cookie_db = snapshot_profile / cookie_db.relative_to(COCCOC_PROFILE_DIR)
        snapshot_cookie_db.parent.mkdir(parents=True, exist_ok=True)

        try:
            _sqlite_snapshot(cookie_db, snapshot_cookie_db)
            local_state = COCCOC_USER_DATA_DIR / "Local State"
            if local_state.is_file():
                shutil.copy2(local_state, snapshot_user_data / "Local State")
        except (sqlite3.Error, PermissionError, OSError) as exc:
            raise RuntimeError(
                "Cannot create a safe snapshot of the Cốc Cốc cookie database. "
                "Check Windows file permissions; if Cốc Cốc is updating or holding "
                "an exclusive lock, close it completely and retry. "
                f"Cookie DB path: {cookie_db}. "
                f"Underlying error: {type(exc).__name__}: {exc}"
            ) from exc

        configured["cookiesfrombrowser"] = (
            "chrome",
            str(snapshot_profile),
            None,
            None,
        )
        yield configured


def update_task(task_id: str, **changes: Any) -> None:
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id].update(changes)


def progress_hook(task_id: str):
    def hook(data: dict[str, Any]) -> None:
        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes", 0)
            percent = round(downloaded * 100 / total, 1) if total else None
            update_task(
                task_id,
                state="downloading",
                percent=percent,
                downloaded_bytes=downloaded,
                total_bytes=total,
                speed=data.get("速度") or data.get("speed"),
                eta=data.get("eta"),
            )
        elif status == "finished":
            update_task(task_id, state="processing", percent=100, message="Finalizing media…")
    return hook


def run_download(task_id: str, url: str, media_type: str) -> None:
    prefix = f"{task_id}-"
    options: dict[str, Any] = {
        "outtmpl": str(DOWNLOAD_DIR / (prefix + "%(title).160B.%(ext)s")),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook(task_id)],
        "restrictfilenames": True,
        "windowsfilenames": True,
    }
    if media_type == "mp3":
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        options.update({
            "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
            "merge_output_format": "mp4",
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }],
        })

    try:
        update_task(task_id, state="starting", message="Reading local Cốc Cốc cookies…")
        with coccoc_cookie_options(options) as cookie_options:
            with yt_dlp.YoutubeDL(cookie_options) as ydl:
                ydl.download([url])
        matches = sorted(DOWNLOAD_DIR.glob(prefix + "*"), key=lambda p: p.stat().st_mtime, reverse=True)
        matches = [p for p in matches if p.is_file() and p.suffix.lower() not in {".part", ".ytdl"}]
        if not matches:
            raise RuntimeError("Download finished but the output file could not be located.")
        output = matches[0].resolve()
        if DOWNLOAD_DIR.resolve() not in output.parents:
            raise RuntimeError("Output path validation failed.")
        update_task(
            task_id,
            state="completed",
            percent=100,
            filename=output.name,
            message="Your file is ready.",
        )
    except Exception as exc:  # yt-dlp raises several extractor/postprocessor exception types
        logger.exception("Download task %s failed", task_id)
        update_task(task_id, state="error", error=str(exc)[:500], message="Download failed.")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "yt-dlp-web-ui",
        "milestone": "M1",
        "revision": os.environ.get("YT_DLP_WEB_UI_REVISION", "unknown"),
    }


@app.post("/api/video/info")
async def video_info(request: URLRequest) -> dict[str, Any]:
    url = validate_public_http_url(request.url)
    options = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}
    try:
        info = await __import__("asyncio").to_thread(_extract_info_with_coccoc_cookies, url, options)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read video information: {type(exc).__name__}: {str(exc)[:900]}") from None
    return {
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader"),
        "webpage_url": info.get("webpage_url"),
    }


def _extract_info_with_coccoc_cookies(url: str, options: dict[str, Any]) -> dict[str, Any]:
    with coccoc_cookie_options(options) as cookie_options:
        with yt_dlp.YoutubeDL(cookie_options) as ydl:
            return ydl.extract_info(url, download=False)


@app.post("/api/download/{media_type}")
async def create_download(media_type: str, request: URLRequest) -> dict[str, str]:
    if media_type not in {"mp4", "mp3"}:
        raise HTTPException(status_code=404, detail="Unknown download format.")
    url = validate_public_http_url(request.url)
    task_id = uuid.uuid4().hex
    with tasks_lock:
        tasks[task_id] = {
            "task_id": task_id,
            "media_type": media_type,
            "state": "queued",
            "percent": 0,
            "message": "Queued",
            "filename": None,
            "error": None,
        }
    executor.submit(run_download, task_id, url, media_type)
    return {"task_id": task_id, "state": "queued"}


@app.get("/api/download/status/{task_id}")
async def download_status(task_id: str) -> dict[str, Any]:
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found.")
        return dict(task)


@app.get("/api/download/file/{task_id}")
async def download_file(task_id: str) -> FileResponse:
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found.")
        if task.get("state") != "completed" or not task.get("filename"):
            raise HTTPException(status_code=409, detail="The file is not ready yet.")
        filename = task["filename"]
    path = (DOWNLOAD_DIR / filename).resolve()
    if DOWNLOAD_DIR.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="The output file is no longer available.")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@app.get("/api/download/history")
async def download_history() -> dict[str, list[dict[str, Any]]]:
    with tasks_lock:
        recent = sorted(tasks.values(), key=lambda item: item["task_id"], reverse=True)[:20]
        return {"items": [dict(item) for item in recent]}

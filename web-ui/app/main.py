"""FastAPI backend for the yt-dlp Web UI (M1)."""
from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
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
        update_task(task_id, state="starting", message="Starting download…")
        with yt_dlp.YoutubeDL(options) as ydl:
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
    return {"status": "ok", "service": "yt-dlp-web-ui", "milestone": "M1"}


@app.post("/api/video/info")
async def video_info(request: URLRequest) -> dict[str, Any]:
    url = validate_public_http_url(request.url)
    options = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}
    try:
        info = await __import__("asyncio").to_thread(_extract_info, url, options)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read video information: {str(exc)[:300]}") from None
    return {
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader"),
        "webpage_url": info.get("webpage_url"),
    }


def _extract_info(url: str, options: dict[str, Any]) -> dict[str, Any]:
    with yt_dlp.YoutubeDL(options) as ydl:
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

# yt-dlp Web UI — Architecture (M0)

## Product goal

Provide a small, responsive web interface around the existing yt-dlp project. A user pastes a media URL and chooses **GET MP4** or **GET MP3**. The same application should work on the Windows host and, when deliberately enabled, from a phone or another device on the trusted local network.

## M0 decisions

- Keep the upstream yt-dlp engine intact; application code lives in the separate `web-ui/` directory.
- Backend: Python 3.10+ and FastAPI. Use yt-dlp as a Python library rather than shelling out to an unrelated binary.
- Frontend: semantic HTML, modern CSS and vanilla JavaScript for the first release; no frontend build chain is required.
- Default bind address: `127.0.0.1`; default port: `8080`.
- LAN access is an explicit opt-in, not the default. A LAN deployment must be restricted to a trusted network and protected by an access token before download endpoints are exposed.
- Download output is stored under a configurable `downloads/` directory. Never accept an arbitrary output path from the browser.
- FFmpeg is required for reliable MP4 merging and MP3 extraction. Detect and report its absence clearly.

## Logical components

1. **Browser UI** — URL input, MP4/MP3 actions, media details, task progress, result download.
2. **FastAPI application** — validates requests, creates task IDs, reports task state and serves completed files.
3. **Download service** — wraps yt-dlp options, progress hooks, output templates and post-processing.
4. **Task store** — initially in-memory for a single-process MVP; persistence and queueing are later work.
5. **Storage** — controlled download directory with safe filenames and cleanup policy.

## API contract (planned)

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Service health |
| POST | `/api/video/info` | Inspect supported URL and return title, duration and thumbnail metadata |
| POST | `/api/download/mp4` | Create an MP4 download task |
| POST | `/api/download/mp3` | Create an MP3 extraction task |
| GET | `/api/download/status/{task_id}` | Read progress and task state |
| GET | `/api/download/file/{task_id}` | Download a completed result |
| GET | `/api/download/history` | List recent tasks |

The download and metadata routes are intentionally not implemented in M0. Their request/response schemas should be documented and tested before implementation.

## Security and operational requirements

- Accept only HTTP(S) URLs; reject malformed input and unsupported schemes.
- Treat URLs and metadata as untrusted input. Do not expose arbitrary filesystem paths or arbitrary yt-dlp options to clients.
- Protect LAN mode with authentication/token validation and restrict access to trusted interfaces/firewall rules.
- Prevent access to local/private network resources through URL validation and network egress controls where practical.
- Use generated task IDs and sanitized output names; resolve output paths and verify they remain inside the configured download directory.
- Limit concurrent jobs, request sizes and maximum task duration; provide cancellation and cleanup in a later milestone.
- Do not attempt to bypass DRM, paywalls, authentication controls or platform restrictions. Users are responsible for having permission to download the content.
- Keep logs free of access tokens and other secrets.

## Runtime modes

- Local: `127.0.0.1:8080` — recommended default.
- LAN: explicit opt-in to bind to a LAN interface or `0.0.0.0`; require authentication before enabling remote task operations.

## Out of scope for M0

Actual media downloads, progress streaming, authentication implementation, persistent history, packaging/installer, public internet exposure and changes to yt-dlp's core engine.

# yt-dlp Web UI — Roadmap

## Product direction

A modern, minimal, responsive interface for the existing yt-dlp engine. The first user workflow is intentionally simple: paste a URL, choose **GET MP4** or **GET MP3**, follow progress and retrieve the result.

## M0 — Foundation (current)

- [x] Create isolated `dev` branch from `master`.
- [x] Record architecture and security boundaries.
- [x] Add a minimal FastAPI application scaffold and dependency list.
- [x] Document local and LAN runtime modes.
- [ ] Run the scaffold locally and verify the health endpoint.
- [ ] Add automated tests and CI for the web-ui package.

Acceptance criteria:
- Existing yt-dlp CLI behavior and core files remain unchanged.
- The web UI has a clearly isolated directory.
- The backend starts with documented commands and exposes `GET /api/health`.
- Localhost is the default bind address; LAN mode is opt-in.
- Setup and security assumptions are documented.

## M1 — Basic download workflow

- Responsive page with URL input and two clear actions: GET MP4 and GET MP3.
- URL inspection and useful title/thumbnail/duration preview.
- Backend task creation, status polling and completed-file download.
- yt-dlp progress hooks; FFmpeg detection and actionable error messages.
- Safe output naming and controlled downloads directory.

Acceptance criteria:
- A permitted, supported test URL can be downloaded as MP4 and MP3.
- Invalid URLs, missing FFmpeg and unsupported formats produce understandable errors.
- The browser never chooses a filesystem path or raw yt-dlp options.

## M2 — Better user experience

- Format/quality selection with sensible defaults.
- Progress, speed, ETA, status and error display.
- Task history, cancellation and bounded concurrency.
- Configurable download directory and retention policy.
- LAN access token, clear LAN-mode warning and access controls.

## M3 — Distribution and operations

- Windows launch scripts and optional packaged distribution.
- LAN setup guide and firewall guidance.
- Optional service/container deployment after security review.
- Logging, diagnostics, upgrade and backup guidance.

## Release principles

- Keep application code separate from yt-dlp's extraction engine.
- Rebase/merge upstream updates deliberately; never overwrite local application files.
- Validate every release against a small set of legally downloadable test media.
- Never implement DRM or access-control circumvention.

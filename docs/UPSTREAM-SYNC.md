# Upstream synchronization policy

This repository is a fork of `yt-dlp/yt-dlp`. The upstream project remains the source of truth for the downloader engine.

## Branch policy

- `master`: fork's upstream-tracking branch; keep changes here minimal.
- `dev`: integration branch for the Web UI and project-specific work.
- `feature/*`: short-lived branches for individual changes, based on `dev`.

## Add the upstream remote

```bash
git remote add upstream https://github.com/yt-dlp/yt-dlp.git
git fetch upstream
git remote -v
```

If the remote already exists, do not add it again; use `git remote set-url upstream https://github.com/yt-dlp/yt-dlp.git`.

## Update the tracking branch

Review upstream changes before updating the local tracking branch:

```bash
git fetch upstream
git switch master
git merge --ff-only upstream/master
git push origin master
```

If fast-forward is not possible, stop and inspect the divergence rather than force-pushing.

## Bring upstream changes into development

```bash
git switch dev
git merge master
```

Resolve conflicts carefully, run the upstream and Web UI test suites, then push `dev`. Do not blindly merge or overwrite files.

## Rules

- Do not commit Web UI changes directly to upstream-owned engine files unless a change is genuinely required and separately reviewed.
- Keep Web UI source and docs under their own paths (initially `web-ui/` and `docs/WEB-UI-*`).
- Preserve upstream license and copyright notices.
- Review dependency licenses and security advisories when adding packages.
- Never force-push shared branches as a routine synchronization method.

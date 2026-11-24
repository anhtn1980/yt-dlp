# Handoff: yt-dlp Web UI — Cốc Cốc / YouTube cookie snapshot

**Status:** unresolved; do not describe the Cốc Cốc sign-in/download path as working yet.  
**Repository:** `anhtn1980/yt-dlp`  
**Working branch:** `dev`  
**Last inspected branch HEAD:** `5d84a097d317b33891d72638873e9332491ded38` (2026-11-24; verify current HEAD before continuing)  
**Scope:** local Windows Web UI, URL input, GET MP4 / GET MP3, using the user's local yt-dlp installation and (where needed) the user's own Cốc Cốc signed-in profile.

## 1. Product goal and current scope

The user wants a modern, minimal local web interface:
- one text field for a video URL and a Paste control;
- separate **GET MP4** and **GET MP3** actions;
- visible task state/progress and a way to retrieve the finished file;
- work locally on the user's Windows PC (currently using Cốc Cốc; the app has been opened at `http://127.0.0.1:8080`).

The visible UI is already running and visually close to the intended design. The unresolved blocker is obtaining video metadata/downloads for YouTube URLs when YouTube requires the user's signed-in browser session. The app must not upload browser data to a cloud service.

## 2. Latest observed failure (from user's screenshot)

The latest screenshot, after pulling the read-only-URI change, displays:

```text
Could not read video information: RuntimeError:
SQLite snapshot failed while opening source database in read-only mode;
source=C:\Users\Admin\AppData\Local\CocCoc\Browser\User Data\Default\Network\Cookies;
destination=C:\Users\Admin\AppData\Local\Temp\yt-dlp-coccoc-...\User Data\Default\Network\Cookies;
destination_parent_exists=True;
destination_parent_writable=True;
cause=OperationalError: unable to open database file
```

Interpretation:
- The failure occurs while opening the source database, before SQLite Backup API starts.
- The destination parent exists and is writable, so the current error is not explained by a missing/unwritable destination directory.
- This screenshot is evidence that the current `Path.as_uri() + '?mode=ro'` connection approach fails on the user's Windows setup. It is **not** evidence that the live Cốc Cốc DB is corrupt.

## 3. Evidence gathered so far — verified vs. unknown

### Verified from user's PowerShell screenshots
- Cốc Cốc profile directory exists at:
  `C:\Users\Admin\AppData\Local\CocCoc\Browser\User Data\Default`
- Cookie DB exists at:
  `...\Default\Network\Cookies`
- Reported size: `294912 bytes`.
- A plain Python binary read-only file open succeeded.
- An earlier diagnostic reported:
  - `File open (read-only): OK`
  - `SQLite header present: True`
  - `SQLite read-only open: OK`
  - `SQLite quick_check: ok`
  - `Local State readable: True`
  - `SQLite backup API snapshot: OK (294912 bytes)`
- That successful snapshot was observed **before** the backend was changed to use `Path.as_uri() + '?mode=ro'`. The diagnostic script was subsequently changed to use the same URI technique, so rerun/current diagnostic results must be checked rather than assuming it still passes.
- Earlier, when the backend used a normal native-path SQLite connection, the Web UI reported `OperationalError: unable to open database file` during source open. The user's diagnostic at that time had separately succeeded with a read-only SQLite open and backup API snapshot using the diagnostic's then-current implementation.
- Cốc Cốc browser processes were closed during one troubleshooting attempt; later screenshots show Cốc Cốc running again. The user also tried opening the local UI in Microsoft Edge, but the cookie source remains Cốc Cốc.

### Current code state (last inspected)
- `web-ui/app/main.py` defines `_sqlite_snapshot(source, destination)`.
- It currently uses:
  `source.resolve().as_uri() + "?mode=ro"`
  and `sqlite3.connect(source_uri, uri=True, timeout=15)`.
- It creates the destination with a native path and uses `src.backup(dst, pages=256, sleep=0.1)`.
- `coccoc_cookie_options()` creates a temporary profile structure:
  `<temp>\\User Data\\Default\\Network\\Cookies`
  and copies `Local State` into the temp User Data directory.
- The wrapper catches SQLite/OS exceptions and emits a user-facing error.
- `web-ui/diagnose_coccoc.py` currently uses the same URI-based read-only open and imports the app helper to exercise a nested temp destination.
- `web-ui/tests/test_coccoc_snapshot.py` has synthetic DB tests for path-with-spaces, snapshot profile layout and detailed error propagation.
- `run-web-ui.bat` pulls `origin/dev`, refuses a dirty worktree, checks/stops an existing listener on port 8080 only after asking, creates/uses `.venv`, installs Web UI requirements, checks FFmpeg and starts uvicorn. It exposes the running revision through `/api/health` when the environment variable is set by the launcher.

## 4. Attempts made and what they establish

1. **Direct use of yt-dlp `--cookies-from-browser` against Cốc Cốc/Chromium profile**  
   Earlier error indicated inability to copy/open the Chromium cookie database while browser is running. Do not assume the exact failure mode is only a browser lock.

2. **Close Cốc Cốc and retry**  
   Did not resolve the user's Web UI issue. Do not keep asking the user to repeat this without a new reason.

3. **Read-only file access diagnostic**  
   Python could open the DB as a binary file. This only proves OS-level read access; it does not prove SQLite can open it.

4. **SQLite read-only open + quick_check**  
   At one point succeeded when using the diagnostic's then-current connection approach. It is evidence that a SQLite read-only connection can work under at least one tested configuration.

5. **SQLite Backup API snapshot**  
   At one point succeeded and produced a 294,912-byte snapshot in a simple temp destination. A later diagnostic was changed to reproduce the nested Web UI directory layout. Do not conflate the old success with the current URI connection code.

6. **Stage-specific error reporting**  
   Added to `_sqlite_snapshot` so the UI shows which step fails and source/destination paths. This correctly established that the current failure is source open, not destination creation.

7. **Read-only URI change**  
   Changed source open to `Path.as_uri() + '?mode=ro'`. This is the current failing code according to the latest user screenshot. Hypothesis: Windows SQLite URI parsing/escaping/URI mode or URI construction is not behaving as expected for this path. Verify before choosing a replacement.

8. **Windows CI tests**  
   A Web UI test workflow was added. A previous Windows run failed during TemporaryDirectory cleanup with `PermissionError: [WinError 32]` because a synthetic SQLite file remained open. The test helper was amended to explicitly close SQLite connections. Linux job had passed on that earlier run; the later Windows run was still in progress when last checked. Recheck latest Actions state. The repository's existing unrelated core/lint workflows also showed failures on the inspected commit; do not attribute those automatically to this Web UI change.

## 5. Priority investigation plan for next session

Do not immediately ask the user to run more ad-hoc PowerShell. First inspect the current code and reproduce with synthetic Windows CI tests.

### A. Resolve the source connection failure
1. Build a tiny isolated test on Windows that creates a SQLite DB under a path containing spaces and a drive letter, then tests all of:
   - native path + `sqlite3.connect(path, timeout=...)`;
   - native path + `sqlite3.connect(path, timeout=..., uri=False)`;
   - URI generated by `Path.as_uri()`, with query constructed using `urllib.parse` correctly;
   - SQLite URI using `file:/C:/...` vs `file:///C:/...` as supported by Python's SQLite build.
2. Test both the synthetic DB and, only in the user's local diagnostic, the live Cốc Cốc DB. Never log cookie values.
3. Verify `sqlite3.sqlite_version`, Python version, source URI with credentials omitted (there are no credentials in path), and the exact exception.
4. Avoid assuming `PRAGMA query_only=ON` is equivalent to opening with `mode=ro`. Conversely, do not assume URI is necessary if native path read-only connection works.
5. If the SQLite URI route remains unreliable on Windows, prefer a tested native-path read-only connection if supported, or another explicitly tested safe approach.

### B. Validate the snapshot destination lifecycle
1. Confirm destination parent is created before connect.
2. Ensure destination connection is always closed even if backup fails.
3. Ensure source connection is always closed.
4. On Windows, verify the snapshot DB file can be deleted after context exit (no leaked handles).
5. Test backup includes WAL-committed rows using a synthetic WAL-mode database.
6. Do not copy browser DB with raw `shutil.copy` as a fallback while browser is live unless its consistency/locking behavior is explicitly addressed.

### C. Re-evaluate whether SQLite snapshot is the right design
SQLite snapshot is only one possible approach; evaluate options and record tradeoffs before committing to it as the sole design:

| Option | Potential benefit | Risks / limitations | Suggested position |
|---|---|---|---|
| Native-path SQLite read-only + Backup API | Consistent DB snapshot; can include committed WAL state | Must work with Windows file sharing/locks; needs tests | Keep as preferred only if reproduced and validated on Windows |
| SQLite URI `mode=ro` + Backup API | Explicitly read-only open | Current implementation fails on user's Windows path; URI parsing/build differences possible | Investigate, do not assume |
| Copy full browser profile to temp | Familiar Chromium profile layout | Raw copy can be inconsistent; sensitive data copied; browser locks remain | Not preferred without a robust snapshot method |
| Cốc Cốc/Chromium cookie export to Netscape cookies.txt | Avoid SQLite profile parsing in yt-dlp | Export mechanism/format, expiry, secure cookies, and encryption constraints; manual handling | Possible user-controlled fallback; never export automatically without consent |
| Browser extension or Cốc Cốc-supported export | Could export only relevant site cookies | Extension permissions and user trust; Cốc Cốc support/compatibility unknown | Research feasibility, require explicit consent |
| Chrome DevTools Protocol / remote debugging | Browser can expose session/network context | Sensitive debugging endpoint; may not export cookies in yt-dlp-compatible way; security risk if exposed | Experimental only; bind loopback, never enable by default |
| User-selected cookies.txt file | Simple explicit user-controlled input; easy to diagnose | User must create/refresh it; file contains credentials | Practical fallback if user agrees; local-only, restrictive ACL, never log or commit |
| No-cookie mode for public videos | No browser integration needed | Fails for private, age-restricted, region/login gated or bot-challenged videos | Always offer as first/simple path for public accessible content |
| Browser/profile-specific yt-dlp support | Could avoid custom code if supported upstream | Verify yt-dlp's actual supported browser names and Cốc Cốc compatibility | Check current upstream docs/code before implementing custom reader |

Do not bypass DRM, bot protections, authentication or access controls. The goal is to use the user's own authorized browser session, not circumvent restrictions.

### D. Keep UI and backend concerns separate
- First validate metadata extraction independently of download.
- Then validate MP4 format selection/merge and FFmpeg.
- Then validate MP3 extraction and FFmpeg.
- Ensure UI surfaces the original actionable exception, not a generic wrapper that hides it.
- Add a health endpoint revision field or another reliable way to prove which process is serving port 8080.
- Ensure the launcher cannot leave an old server silently serving stale code.

## 6. Security and privacy constraints

- Never print, log, display, commit, upload or send cookie values, authorization headers, or contents of `Local State`.
- Do not modify, delete, or overwrite the real Cốc Cốc profile or cookie DB.
- Never run SQL UPDATE/DELETE against the browser profile.
- Use temporary files with restrictive access where possible; clean them up after each operation.
- Copy `Local State` only if proven necessary for yt-dlp's Chromium cookie decryption. Treat it as sensitive credential metadata.
- Do not disable Cốc Cốc security, antivirus, Windows Defender, browser sandboxing or file protections.
- Do not ask the user to upload the real Cookies database or Local State file.
- Keep Web UI bound to `127.0.0.1`; do not expose it to LAN/public internet without authentication and security review.
- Only use the user's own browser profile and content they are authorized to download.

## 7. Suggested next-session acceptance criteria

Before asking the user to pull another fix:
1. Windows CI passes all Web UI snapshot tests.
2. Tests cover Windows drive paths and spaces, read-only source open, SQLite backup, WAL behavior, exception propagation, and deletion of snapshot temp files.
3. A local diagnostic reports success for source open and snapshot without printing cookie contents.
4. Web UI can read metadata from a public video without cookies (where available).
5. With user-approved Cốc Cốc session access, Web UI can read metadata for a video requiring sign-in.
6. GET MP4 completes and delivers a file.
7. GET MP3 completes when FFmpeg is installed.
8. Health endpoint revision matches the commit being tested.

## 8. Useful commands after a verified fix exists

Do not ask the user to run these until the next developer has fixed the code and confirmed CI:

```powershell
cd D:\dev\yt-dlp
git status --short
git pull --ff-only origin dev
.\.venv\Scripts\python.exe -m unittest discover -s web-ui\tests -v
.\.venv\Scripts\python.exe web-ui\diagnose_coccoc.py
.\run-web-ui.bat
```

Then check `http://127.0.0.1:8080/api/health` and verify its `revision` matches the checked-out commit before trying GET MP4/GET MP3.

## 9. Handoff note to the next developer

The user has already spent substantial time following diagnostic instructions and is understandably frustrated. Do not restart the conversation by asking them to repeat steps already shown above. Start by reading this document, inspecting current `dev` HEAD and CI, and reproducing the exact failure on Windows. Be explicit about what is verified vs. hypothesized. If SQLite snapshot remains unreliable, present a genuinely viable alternative (for example, an opt-in local cookies.txt workflow or no-cookie public-video mode) rather than continuing speculative changes.

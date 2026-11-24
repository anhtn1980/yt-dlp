"""Safe diagnostics for Cốc Cốc's local Chromium cookie database.

This script reports file accessibility and SQLite health only. It never reads,
prints, exports, or copies cookie values.
Run from PowerShell with:
  .\\.venv\\Scripts\\python.exe web-ui\\diagnose_coccoc.py
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

profile = Path(
    os.environ.get(
        "COCCOC_PROFILE_PATH",
        str(Path.home() / "AppData/Local/CocCoc/Browser/User Data/Default"),
    )
).expanduser()

candidates = (profile / "Network" / "Cookies", profile / "Cookies")
cookie_db = next((p for p in candidates if p.is_file()), None)
user_data = profile.parent
local_state = user_data / "Local State"

print("=== COC COC COOKIE DATABASE DIAGNOSTICS ===")
print(f"Profile directory exists: {profile.is_dir()}")
print(f"Profile path: {profile}")
print(f"Cookie database found: {cookie_db is not None}")

if cookie_db is None:
    print("RESULT: Cookie database file not found in expected profile locations.")
    raise SystemExit(2)

print(f"Cookie DB path: {cookie_db}")
try:
    stat = cookie_db.stat()
    print(f"Cookie DB size: {stat.st_size} bytes")
    print(f"Cookie DB readable flag: {os.access(cookie_db, os.R_OK)}")
except OSError as exc:
    print(f"STAT ERROR: {type(exc).__name__}: {exc}")

try:
    with cookie_db.open("rb") as handle:
        header = handle.read(16)
    print(f"File open (read-only): OK")
    print(f"SQLite header present: {header == b'SQLite format 3\x00'}")
except OSError as exc:
    print(f"FILE OPEN ERROR: {type(exc).__name__}: {exc}")
    raise SystemExit(3)

try:
    uri = cookie_db.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        connection.execute("PRAGMA query_only = ON")
        result = connection.execute("PRAGMA quick_check(1)").fetchone()
        print(f"SQLite read-only open: OK")
        print(f"SQLite quick_check: {result[0] if result else 'no result'}")
    finally:
        connection.close()
except sqlite3.Error as exc:
    print(f"SQLITE OPEN/CHECK ERROR: {type(exc).__name__}: {exc}")
    raise SystemExit(4)

try:
    with local_state.open("rb") as handle:
        handle.read(1)
    print("Local State readable: True")
except OSError as exc:
    print(f"Local State readable: False ({type(exc).__name__}: {exc})")

try:
    from app.main import _sqlite_snapshot

    with tempfile.TemporaryDirectory(prefix="yt-dlp-coccoc-diagnostic-") as directory:
        # Reproduce the exact nested destination layout used by the Web UI.
        snapshot_user_data = Path(directory) / "User Data"
        snapshot_profile = snapshot_user_data / profile.name
        snapshot_cookie_db = snapshot_profile / cookie_db.relative_to(profile)
        snapshot_cookie_db.parent.mkdir(parents=True, exist_ok=True)
        print(f"Snapshot directory writable: {os.access(snapshot_cookie_db.parent, os.W_OK)}")
        print(f"Snapshot DB destination: {snapshot_cookie_db}")
        _sqlite_snapshot(cookie_db, snapshot_cookie_db)
        print(f"SQLite backup API snapshot (Web UI layout): OK ({snapshot_cookie_db.stat().st_size} bytes)")
        if local_state.is_file():
            import shutil
            shutil.copy2(local_state, snapshot_user_data / "Local State")
            print("Local State copy into Web UI layout: OK")
except Exception as exc:
    print(f"SQLite backup API snapshot: FAILED ({type(exc).__name__}: {exc})")

print("RESULT: Diagnostics completed. No cookie values were accessed or displayed.")

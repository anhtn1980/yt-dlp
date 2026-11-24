"""Unit tests for the Cốc Cốc cookie snapshot helper."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main  # noqa: E402


class CocCocCookieSnapshotTests(unittest.TestCase):
    def _make_cookie_db(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE sample (value TEXT)")
            connection.execute("INSERT INTO sample(value) VALUES ('snapshot-ok')")
            connection.commit()
        finally:
            connection.close()

    def test_find_prefers_network_cookie_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "Default"
            network_db = profile / "Network" / "Cookies"
            legacy_db = profile / "Cookies"
            self._make_cookie_db(network_db)
            self._make_cookie_db(legacy_db)

            self.assertEqual(main._find_coccoc_cookie_db(profile), network_db)

    def test_sqlite_snapshot_supports_windows_style_paths_with_spaces(self) -> None:
        # Windows profile paths commonly contain "User Data"; use a space in
        # the temporary root as well to catch URI/path quoting regressions.
        with tempfile.TemporaryDirectory(prefix="yt-dlp test ") as directory:
            source = Path(directory) / "User Data" / "Default" / "Network" / "Cookies"
            destination = Path(directory) / "private snapshot" / "Cookies"
            self._make_cookie_db(source)
            destination.parent.mkdir(parents=True)

            main._sqlite_snapshot(source, destination)

            connection = sqlite3.connect(destination)
            try:
                value = connection.execute("SELECT value FROM sample").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(value, "snapshot-ok")


    def test_cookie_options_preserve_detailed_snapshot_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            user_data = Path(directory) / "User Data"
            profile = user_data / "Default"
            cookie_db = profile / "Network" / "Cookies"
            self._make_cookie_db(cookie_db)

            with (
                patch.object(main, "COCCOC_PROFILE_DIR", profile),
                patch.object(main, "COCCOC_USER_DATA_DIR", user_data),
                patch.object(
                    main,
                    "_sqlite_snapshot",
                    side_effect=RuntimeError(
                        "SQLite snapshot failed while opening source database; "
                        "cause=OperationalError: unable to open database file"
                    ),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "SQLite snapshot failed while opening source database",
                ):
                    with main.coccoc_cookie_options({"quiet": True}):
                        self.fail("cookie options should not be yielded after snapshot failure")

    def test_cookie_options_point_to_temporary_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            user_data = Path(directory) / "User Data"
            profile = user_data / "Default"
            cookie_db = profile / "Network" / "Cookies"
            self._make_cookie_db(cookie_db)
            (user_data / "Local State").write_text("{}", encoding="utf-8")

            with (
                patch.object(main, "COCCOC_PROFILE_DIR", profile),
                patch.object(main, "COCCOC_USER_DATA_DIR", user_data),
            ):
                with main.coccoc_cookie_options({"quiet": True}) as options:
                    browser, snapshot_profile, keyring, container = options["cookiesfrombrowser"]
                    snapshot_profile = Path(snapshot_profile)
                    self.assertEqual(browser, "chrome")
                    self.assertTrue((snapshot_profile / "Network" / "Cookies").is_file())
                    self.assertTrue((snapshot_profile.parent / "Local State").is_file())
                    self.assertIsNone(keyring)
                    self.assertIsNone(container)
                    temporary_profile = snapshot_profile

                self.assertFalse(temporary_profile.exists())


if __name__ == "__main__":
    unittest.main()

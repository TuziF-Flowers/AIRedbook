from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path


def main() -> int:
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        print("LOCALAPPDATA is not available.")
        return 1

    cookie_db = (
        Path(local_app_data)
        / "Google"
        / "Chrome"
        / "User Data"
        / "Default"
        / "Network"
        / "Cookies"
    )
    if not cookie_db.is_file():
        print(f"Chrome cookie database not found: {cookie_db}")
        return 1

    with tempfile.TemporaryDirectory(prefix="redbook-cookie-check-") as temp_dir:
        copied_db = Path(temp_dir) / "Cookies"
        try:
            shutil.copy2(cookie_db, copied_db)
        except PermissionError:
            print("Chrome cookie database is still locked by another process.")
            print("Close Chrome/background Chrome processes, or use the manual save script.")
            return 3
        connection = sqlite3.connect(str(copied_db))
        try:
            connection.execute("PRAGMA query_only = ON")
            rows = connection.execute(
                """
                SELECT host_key, name
                FROM cookies
                WHERE host_key LIKE ?
                ORDER BY host_key, name
                """,
                ("%xiaohongshu.com%",),
            ).fetchall()
        finally:
            connection.close()

    names = {name for _, name in rows}
    print("Chrome profile: Default")
    print(f"Xiaohongshu cookie records: {len(rows)}")
    print(f"Cookie names: {', '.join(sorted(names)) or '(none)'}")
    print(f"Required a1: {'yes' if 'a1' in names else 'no'}")
    print(f"Required web_session: {'yes' if 'web_session' in names else 'no'}")
    return 0 if {"a1", "web_session"} <= names else 2


if __name__ == "__main__":
    raise SystemExit(main())

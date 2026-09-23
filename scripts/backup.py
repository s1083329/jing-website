"""Create a consistent SQLite snapshot, including committed WAL changes."""
import datetime
import os
from pathlib import Path
import sqlite3
import sys

source = Path(sys.argv[1] if len(sys.argv) > 1 else "instance/database.db")
if not source.is_file():
    raise SystemExit(f"Database does not exist: {source}")
os.umask(0o077)
directory = Path("backups")
directory.mkdir(exist_ok=True)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
target = directory / f"database-{stamp}.db"
with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise SystemExit("Backup integrity check failed")
print(target)

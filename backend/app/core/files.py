"""Owner-only file permissions for anything that holds financial data.

The SQLite database, its -wal/-shm files and backups contain every transaction in plain form, so
they're created readable and writable by the app's own user only (0600, folders 0700). Existing
files from older versions are tightened too. This complements, not replaces, full-disk encryption.
"""

import os
from pathlib import Path

PRIVATE_FILE = 0o600
PRIVATE_DIR = 0o700


def private_dir(path: Path) -> Path:
    """Create `path` (and parents) owner-only if it doesn't exist.

    An existing folder is left alone: it may be shared (a home directory, a mounted volume), and
    the files inside are protected by their own 0600 permissions.
    """
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, PRIVATE_DIR)
    return path


def private_file(path: Path) -> Path:
    """Create `path` empty with 0600 if it doesn't exist, or tighten it to 0600 if it does."""
    if path.exists():
        os.chmod(path, PRIVATE_FILE)
    else:
        os.close(os.open(path, os.O_CREAT | os.O_WRONLY, PRIVATE_FILE))
    return path


def secure_sqlite_files(db_path: Path) -> None:
    """Owner-only permissions for a SQLite database and its WAL/shared-memory files.

    SQLite creates -wal and -shm files with the database file's permissions, so tightening the
    main file first covers new ones too; existing ones are tightened here.
    """
    private_dir(db_path.parent)
    private_file(db_path)
    for suffix in ("-wal", "-shm", "-journal"):
        side = db_path.with_name(db_path.name + suffix)
        if side.exists():
            os.chmod(side, PRIVATE_FILE)

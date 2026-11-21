"""`fintrack` command-line tools.

Installed as the `fintrack` command by pyproject.toml ([project.scripts]). Run it from backend/
with the venv active, or in Docker: `docker compose run --rm backend fintrack <command>`.
"""

import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

import typer
from cryptography.fernet import InvalidToken
from sqlalchemy.engine import make_url

from app.core import security
from app.core.config import get_settings
from app.core.errors import ConfigError
from app.core.files import private_dir, private_file
from app.core.security import generate_encryption_key

app = typer.Typer(help="FinTrack command-line tools.", no_args_is_help=True)


@app.command("gen-keys")
def gen_keys() -> None:
    """Print fresh SECRET_KEY and ENCRYPTION_KEY values for your .env file."""
    typer.echo(f"SECRET_KEY={secrets.token_urlsafe(48)}")
    typer.echo(f"ENCRYPTION_KEY={generate_encryption_key()}")
    typer.echo(
        "# Keep ENCRYPTION_KEY safe: changing it makes saved connections unreadable.", err=True
    )


@app.command()
def sync() -> None:
    """Sync every connection now (ignores the cooldown)."""
    from app.db.session import SessionLocal, get_engine
    from app.repositories import connection_repo
    from app.services import sync_service

    get_engine()
    with SessionLocal() as db:
        for connection in connection_repo.list_all(db):
            run = sync_service.sync_connection(db, connection, trigger="manual")
            status = run.status if run else "skipped (already running)"
            typer.echo(f"Connection {connection.id} ({connection.label}): {status}")


@app.command("reset-password")
def reset_password(email: str = typer.Argument(..., help="The account's email address")) -> None:
    """Set a new password for an account (e.g. someone forgot theirs) and sign it out everywhere."""
    from app.core.errors import AppError
    from app.db.session import SessionLocal, get_engine
    from app.services import auth_service

    password = typer.prompt("New password", hide_input=True, confirmation_prompt=True)
    if not 8 <= len(password) <= 128:
        typer.echo("The password must be 8 to 128 characters long.", err=True)
        raise typer.Exit(1)
    get_engine()
    with SessionLocal() as db:
        try:
            auth_service.reset_password(db, email, password)
        except AppError as exc:
            typer.echo(exc.message, err=True)
            raise typer.Exit(1) from exc
    typer.echo(f"Password updated for {email}; all of its sessions were signed out.")


def _sqlite_db_path() -> Path:
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        typer.echo("Backups via this command only support SQLite; use pg_dump for Postgres.")
        raise typer.Exit(1)
    return Path(url.database)


def _rollback_journal_header(data: bytes) -> bytes:
    """Mark a database image as rollback-journal instead of WAL (header bytes 18-19 = 1).

    The live database runs in WAL mode and a snapshot keeps that flag, but SQLite can't open a
    WAL-flagged image in memory. The app switches the file back to WAL when it next connects.
    """
    if len(data) < 20 or not data.startswith(b"SQLite format 3\x00"):
        return data
    image = bytearray(data)
    image[18] = image[19] = 1
    return bytes(image)


def _write_private(path: Path, data: bytes) -> None:
    """Write a file readable by this user only, atomically (no half-written backups)."""
    tmp = path.with_name(path.name + ".tmp")
    private_file(tmp)
    tmp.write_bytes(data)
    tmp.replace(path)


@app.command()
def backup(
    dest: Path = typer.Option(None, help="Backup folder (default: <db folder>/backups)"),
    keep: int = typer.Option(14, help="How many backups to keep"),
    plaintext: bool = typer.Option(
        False,
        "--plaintext",
        help="Don't encrypt. Only for tools that encrypt on their own (e.g. restic).",
    ),
) -> None:
    """Make a consistent, encrypted copy of the SQLite database and prune old copies.

    Backups are encrypted with ENCRYPTION_KEY (Fernet: AES + HMAC, so tampering is detected),
    and the unencrypted snapshot only ever exists in memory. Restore with `fintrack
    restore-backup`. Without ENCRYPTION_KEY a backup can't be opened, so keep it safe and
    separate from the backups themselves.
    """
    db_path = _sqlite_db_path()
    folder = private_dir(dest or db_path.parent / "backups")
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"

    # sqlite3's backup API copies a consistent snapshot even while the app is writing. Copy into
    # memory, so the plaintext never touches the disk.
    with sqlite3.connect(db_path) as src, sqlite3.connect(":memory:") as snapshot:
        src.backup(snapshot)
        data = _rollback_journal_header(snapshot.serialize())

    if plaintext:
        target = folder / f"fintrack-{stamp}.db"
        _write_private(target, data)
        typer.echo(f"Unencrypted backup written to {target} (readable by this user only).")
    else:
        try:
            cipher = security.fernet()
        except ConfigError as exc:
            typer.echo(f"{exc.message} Or pass --plaintext if another tool encrypts the backups.")
            raise typer.Exit(1) from exc
        target = folder / f"fintrack-{stamp}.db.enc"
        _write_private(target, cipher.encrypt(data))
        typer.echo(f"Encrypted backup written to {target}")

    backups = sorted(
        [*folder.glob("fintrack-*.db"), *folder.glob("fintrack-*.db.enc")],
        key=lambda p: p.name,
        reverse=True,
    )
    for old in backups[keep:]:
        old.unlink()


@app.command("restore-backup")
def restore_backup(
    backup_file: Path = typer.Argument(..., exists=True, dir_okay=False, help="A .db.enc backup"),
    to: Path = typer.Option(..., "--to", help="Where to write the restored database"),
    force: bool = typer.Option(False, help="Overwrite --to if it exists"),
) -> None:
    """Decrypt an encrypted backup into a database file (readable by this user only).

    Stop FinTrack first, restore to a new path, then point DATABASE_URL at it (or move it over
    the old database). Needs the ENCRYPTION_KEY that was set when the backup was made.
    """
    if to.exists() and not force:
        typer.echo(f"{to} already exists; pass --force to overwrite it.")
        raise typer.Exit(1)
    try:
        data = security.fernet().decrypt(backup_file.read_bytes())
    except ConfigError as exc:
        typer.echo(exc.message)
        raise typer.Exit(1) from exc
    except InvalidToken as exc:
        typer.echo(
            "Can't decrypt this backup: it was made with a different ENCRYPTION_KEY, or the file "
            "is damaged or was modified."
        )
        raise typer.Exit(1) from exc

    data = _rollback_journal_header(data)
    with sqlite3.connect(":memory:") as check:
        try:
            check.deserialize(data)
            ok = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        except sqlite3.DatabaseError:
            ok = False
        if not ok:
            typer.echo("The decrypted database failed SQLite's integrity check; not restoring it.")
            raise typer.Exit(1)
    private_dir(to.parent)
    _write_private(to, data)
    typer.echo(f"Restored to {to}. Point DATABASE_URL at it (or move it into place), then start.")


if __name__ == "__main__":
    app()

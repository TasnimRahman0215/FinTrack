"""`fintrack` command-line tools.

Installed as the `fintrack` command by pyproject.toml ([project.scripts]). Run it from backend/
with the venv active, or in Docker: `docker compose run --rm backend fintrack <command>`.
"""

import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

import typer
from sqlalchemy.engine import make_url

from app.core.config import get_settings
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


@app.command()
def backup(
    dest: Path = typer.Option(None, help="Backup folder (default: <db folder>/backups)"),
    keep: int = typer.Option(14, help="How many backups to keep"),
) -> None:
    """Make a consistent copy of the SQLite database and prune old copies."""
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        typer.echo("Backups via this command only support SQLite; use pg_dump for Postgres.")
        raise typer.Exit(1)

    db_path = Path(url.database)
    folder = dest or db_path.parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"fintrack-{datetime.now():%Y%m%d-%H%M%S}.db"

    # sqlite3's backup API copies a consistent snapshot even while the app is writing.
    with sqlite3.connect(db_path) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    typer.echo(f"Backup written to {target}")

    for old in sorted(folder.glob("fintrack-*.db"), reverse=True)[keep:]:
        old.unlink()


if __name__ == "__main__":
    app()

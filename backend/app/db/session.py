"""Engine and session factory. Works with SQLite (default) or any SQLAlchemy-supported database.

The API gets a session per request through `get_db` (a FastAPI dependency). Background jobs and
the CLI open their own with `SessionLocal()`. Tests call `init_engine` to point at a temp DB.
"""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# expire_on_commit=False lets services return objects after committing without extra queries.
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)
_engine: Engine | None = None


def make_engine(url: str) -> Engine:
    """Create an engine, applying SQLite-specific settings when the URL is SQLite."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True)

    if parsed.database and parsed.database != ":memory:":
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    # FastAPI runs sync endpoints in a thread pool, so connections cross threads.
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")  # readers don't block the sync writer
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def init_engine(url: str | None = None) -> Engine:
    """(Re)create the global engine. Defaults to DATABASE_URL from settings."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = make_engine(url or get_settings().database_url)
    SessionLocal.configure(bind=_engine)
    return _engine


def get_engine() -> Engine:
    return _engine if _engine is not None else init_engine()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

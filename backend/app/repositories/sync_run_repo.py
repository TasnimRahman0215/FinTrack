"""Sync history reads, for GET /api/v1/sync/runs. Runs are written by services/sync_service.py."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Connection, SyncRun


def recent_for_household(db: Session, household_id: int, limit: int = 20) -> list[SyncRun]:
    """Newest sync runs across all of a household's connections."""
    stmt = (
        select(SyncRun)
        .join(Connection, Connection.id == SyncRun.connection_id)
        .where(Connection.household_id == household_id)
        .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())

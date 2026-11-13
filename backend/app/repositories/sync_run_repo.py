"""Sync history reads, for GET /api/v1/sync/runs. Runs are written by services/sync_service.py."""

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Connection, SyncRun


def recent_for_household(
    db: Session, household_id: int, connection_ids: Collection[int], limit: int = 20
) -> list[SyncRun]:
    """Newest sync runs for these connections of a household (the ones the viewer manages)."""
    if not connection_ids:
        return []
    stmt = (
        select(SyncRun)
        .join(Connection, Connection.id == SyncRun.connection_id)
        .where(Connection.household_id == household_id, SyncRun.connection_id.in_(connection_ids))
        .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())

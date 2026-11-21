"""Sync history reads, for GET /api/v1/sync/runs. Runs are written by services/sync_service.py."""

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Connection, SyncRun


def count_since(db: Session, connection_id: int, *, trigger: str, since: datetime) -> int:
    """How many runs of this kind a connection started since `since` (daily "Sync now" cap)."""
    return (
        db.scalar(
            select(func.count(SyncRun.id)).where(
                SyncRun.connection_id == connection_id,
                SyncRun.trigger == trigger,
                SyncRun.started_at >= since,
            )
        )
        or 0
    )


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

"""Security event rows. Written by services/audit_service.py, read for "Recent activity"."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import SecurityEvent


def add(db: Session, event: SecurityEvent) -> None:
    db.add(event)


def recent_for_user(db: Session, user_id: int, limit: int = 20) -> list[SecurityEvent]:
    stmt = (
        select(SecurityEvent)
        .where(SecurityEvent.user_id == user_id)
        .order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def delete_older_than(db: Session, cutoff: datetime) -> None:
    db.execute(delete(SecurityEvent).where(SecurityEvent.created_at < cutoff))

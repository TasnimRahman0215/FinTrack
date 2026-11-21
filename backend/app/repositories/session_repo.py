"""Login session rows. Used only by services/auth_service.py."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.models import UserSession


def create(
    db: Session,
    *,
    user_id: int,
    household_id: int | None,
    token_hash: str,
    expires_at: datetime,
    user_agent: str | None,
) -> UserSession:
    session = UserSession(
        user_id=user_id,
        active_household_id=household_id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    db.flush()
    return session


def get_by_token_hash(db: Session, token_hash: str) -> UserSession | None:
    return db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))


def delete_by_token_hash(db: Session, token_hash: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == token_hash))


def delete_for_user(db: Session, user_id: int, *, keep_session_id: int | None = None) -> None:
    """End every session of a user (except `keep_session_id`): password change, sign out all."""
    stmt = delete(UserSession).where(UserSession.user_id == user_id)
    if keep_session_id is not None:
        stmt = stmt.where(UserSession.id != keep_session_id)
    db.execute(stmt)


def delete_expired(db: Session) -> None:
    """Housekeeping, run on each login so the table doesn't grow forever."""
    db.execute(delete(UserSession).where(UserSession.expires_at < utcnow()))

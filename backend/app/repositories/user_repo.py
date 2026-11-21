"""User queries. Emails are stored lower-cased so lookups are case-insensitive."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


def get(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def count(db: Session) -> int:
    """Number of users; 0 means the next signup is always allowed (the first owner)."""
    return db.scalar(select(func.count(User.id))) or 0


def create(db: Session, *, email: str, display_name: str, password_hash: str) -> User:
    user = User(email=email.lower(), display_name=display_name, password_hash=password_hash)
    db.add(user)
    db.flush()
    return user

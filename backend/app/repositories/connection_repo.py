"""Connection queries. Used by connection_service, sync_service, summary_service and the CLI."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.scope import visible_to
from app.models import Account, Connection


def get(db: Session, *, household_id: int, connection_id: int) -> Connection | None:
    return db.scalar(
        select(Connection).where(
            Connection.id == connection_id, Connection.household_id == household_id
        )
    )


def list_for_household(db: Session, household_id: int) -> list[tuple[Connection, int]]:
    """Connections with their total account counts (all members' accounts)."""
    counts = (
        select(Account.connection_id, func.count(Account.id).label("n"))
        .where(Account.household_id == household_id)
        .group_by(Account.connection_id)
        .subquery()
    )
    rows = db.execute(
        select(Connection, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.connection_id == Connection.id)
        .where(Connection.household_id == household_id)
        .order_by(Connection.id)
    ).all()
    return [(c, n) for c, n in rows]


def visible_accounts_by_connection(
    db: Session, *, household_id: int, user_id: int
) -> dict[int, list[Account]]:
    """Synced accounts `user_id` may see (hidden ones included), grouped by connection ID."""
    rows = db.scalars(
        select(Account).where(
            Account.household_id == household_id,
            Account.connection_id.is_not(None),
            visible_to(user_id),
        )
    ).all()
    grouped: dict[int, list[Account]] = {}
    for account in rows:
        grouped.setdefault(account.connection_id, []).append(account)
    return grouped


def list_all(db: Session) -> list[Connection]:
    """Every connection in every household (scheduler and `fintrack sync`)."""
    return list(db.scalars(select(Connection).order_by(Connection.id)).all())


def last_synced_at(db: Session, household_id: int) -> datetime | None:
    """Most recent successful sync across the household (shown on the dashboard)."""
    return db.scalar(
        select(func.max(Connection.last_synced_at)).where(Connection.household_id == household_id)
    )

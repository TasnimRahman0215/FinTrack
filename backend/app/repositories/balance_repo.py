"""Daily balance snapshots, written after each sync and manual-balance change (future charts)."""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BalanceSnapshot


def upsert_snapshot(db: Session, *, account_id: int, date: dt.date, balance_cents: int) -> None:
    """Insert or overwrite the snapshot for that day, so the last balance of the day wins."""
    snap = db.scalar(
        select(BalanceSnapshot).where(
            BalanceSnapshot.account_id == account_id, BalanceSnapshot.date == date
        )
    )
    if snap:
        snap.balance_cents = balance_cents
    else:
        db.add(BalanceSnapshot(account_id=account_id, date=date, balance_cents=balance_cents))
    db.flush()

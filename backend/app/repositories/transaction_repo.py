"""Transaction queries: the paginated list, sync matching and pending cleanup.

Used by transaction_service, sync_service and api/v1/transactions.py.
"""

import base64
import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Account, Transaction
from app.schemas.common import MAX_DB_ID

_CHUNK = 500  # keep IN (...) lists well under database parameter limits


@dataclass
class TransactionFilters:
    """Optional filters from the transactions list query string."""

    account_id: int | None = None
    start: dt.date | None = None
    end: dt.date | None = None
    q: str | None = None


# The cursor is an opaque string to clients: the (date, id) of the last row on the page.
def encode_cursor(date: dt.date, txn_id: int) -> str:
    return base64.urlsafe_b64encode(f"{date.isoformat()}|{txn_id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[dt.date, int]:
    try:
        date_s, id_s = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        date, txn_id = dt.date.fromisoformat(date_s), int(id_s)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError("Invalid cursor", code="invalid_cursor") from exc
    if not 0 <= txn_id <= MAX_DB_ID:
        raise AppError("Invalid cursor", code="invalid_cursor")
    return date, txn_id


def _escape_like(value: str) -> str:
    """Make % and _ in a search term match literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_page(
    db: Session,
    account_ids: Sequence[int],
    filters: TransactionFilters,
    *,
    cursor: str | None,
    limit: int,
) -> tuple[list[tuple[Transaction, Account]], str | None]:
    """Newest first, keyset-paginated on (date, id) so deep pages stay fast."""
    ids = list(account_ids)
    # Filtering within the scope's IDs means an out-of-scope account_id simply returns nothing.
    if filters.account_id is not None:
        ids = [i for i in ids if i == filters.account_id]
    if not ids:
        return [], None

    stmt = (
        select(Transaction, Account)
        .join(Account, Account.id == Transaction.account_id)
        .where(Transaction.account_id.in_(ids))
    )
    if filters.start:
        stmt = stmt.where(Transaction.date >= filters.start)
    if filters.end:
        stmt = stmt.where(Transaction.date <= filters.end)
    if filters.q:
        pattern = f"%{_escape_like(filters.q.strip())}%"
        stmt = stmt.where(
            or_(
                Transaction.description.ilike(pattern, escape="\\"),
                Transaction.payee.ilike(pattern, escape="\\"),
                Transaction.memo.ilike(pattern, escape="\\"),
                Transaction.notes.ilike(pattern, escape="\\"),
            )
        )
    if cursor:
        # Rows strictly "after" the cursor in (date desc, id desc) order.
        c_date, c_id = decode_cursor(cursor)
        stmt = stmt.where(
            or_(Transaction.date < c_date, and_(Transaction.date == c_date, Transaction.id < c_id))
        )

    # Fetch one extra row to know whether another page exists.
    rows = db.execute(
        stmt.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit + 1)
    ).all()
    items = [(t, a) for t, a in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        last = items[-1][0]
        next_cursor = encode_cursor(last.date, last.id)
    return items, next_cursor


def get(db: Session, txn_id: int) -> Transaction | None:
    return db.get(Transaction, txn_id)


def existing_by_provider_ids(
    db: Session, account_id: int, provider_ids: Iterable[str]
) -> dict[str, Transaction]:
    """Already-stored transactions for these provider IDs, so sync can update instead of insert."""
    ids = list(provider_ids)
    found: dict[str, Transaction] = {}
    for i in range(0, len(ids), _CHUNK):
        chunk = ids[i : i + _CHUNK]
        for txn in db.scalars(
            select(Transaction).where(
                Transaction.account_id == account_id, Transaction.provider_txn_id.in_(chunk)
            )
        ):
            found[txn.provider_txn_id] = txn
    return found


def delete_stale_pending(
    db: Session, *, account_id: int, since: dt.date, keep_provider_ids: set[str]
) -> int:
    """Pending transactions often reappear with a new ID once posted. Remove pending rows
    from the fetched window that the provider no longer returns."""
    stale_ids = [
        t.id
        for t in db.scalars(
            select(Transaction).where(
                Transaction.account_id == account_id,
                Transaction.provider_txn_id.is_not(None),  # synced rows, from any provider
                Transaction.pending.is_(True),
                Transaction.date >= since,
            )
        )
        if t.provider_txn_id not in keep_provider_ids
    ]
    if stale_ids:
        db.execute(delete(Transaction).where(Transaction.id.in_(stale_ids)))
    return len(stale_ids)

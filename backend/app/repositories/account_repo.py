"""Account queries. Used by account_service, summary_service and sync_service."""

from collections.abc import Iterable

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.scope import visible_to
from app.models import Account, Transaction
from app.models.enums import AccountKind

# Display order for account groups (checking first, other last), matching the frontend.
KIND_ORDER = [k.value for k in AccountKind]


def get(db: Session, *, household_id: int, account_id: int) -> Account | None:
    return db.scalar(
        select(Account).where(Account.id == account_id, Account.household_id == household_id)
    )


def get_visible(db: Session, *, household_id: int, account_id: int, user_id: int) -> Account | None:
    """One account, only if `user_id` may see it (core/scope.py rules), in a single query."""
    return db.scalar(
        select(Account).where(
            Account.id == account_id, Account.household_id == household_id, visible_to(user_id)
        )
    )


def list_by_ids(db: Session, account_ids: Iterable[int]) -> list[Account]:
    """Accounts sorted by kind, then name. Pass `scope.account_ids`."""
    ids = list(account_ids)
    if not ids:
        return []
    kind_rank = case({k: i for i, k in enumerate(KIND_ORDER)}, value=Account.kind, else_=99)
    stmt = (
        select(Account)
        .where(Account.id.in_(ids))
        .order_by(kind_rank, func.lower(func.coalesce(Account.display_name, Account.name)))
    )
    return list(db.scalars(stmt).all())


def by_provider_ids(db: Session, connection_id: int) -> dict[str, Account]:
    """A connection's accounts keyed by the provider's account ID, for matching during sync."""
    accounts = db.scalars(select(Account).where(Account.connection_id == connection_id)).all()
    return {a.provider_account_id: a for a in accounts if a.provider_account_id}


def add(db: Session, account: Account) -> Account:
    db.add(account)
    db.flush()
    return account


def transaction_total(db: Session, account_id: int) -> int:
    """Sum of all transactions in an account (a manual account's balance is opening + this)."""
    return db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.account_id == account_id
        )
    )

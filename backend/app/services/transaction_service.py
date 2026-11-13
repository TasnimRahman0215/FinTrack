"""Transactions: the scoped list, and create/edit/delete for manual transactions.

Used by api/v1/transactions.py. Synced transactions are read-only here; later features will
let users edit their own fields (category, notes) on them.
"""

from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFound
from app.core.scope import Scope
from app.models import Account, Transaction
from app.models.enums import Source
from app.repositories import transaction_repo
from app.repositories.transaction_repo import TransactionFilters
from app.schemas.common import Page
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate
from app.services import account_service
from app.services.auth_service import AuthContext


def to_out(txn: Transaction, account: Account, ctx: AuthContext) -> TransactionOut:
    """API shape of a transaction, including its account's name for display."""
    return TransactionOut(
        id=txn.id,
        account_id=txn.account_id,
        account_name=account.display_name or account.name,
        source=txn.source,
        date=txn.date,
        posted_at=txn.posted_at,
        amount_cents=txn.amount_cents,
        description=txn.description,
        payee=txn.payee,
        memo=txn.memo,
        notes=txn.notes,
        pending=txn.pending,
        editable=txn.source == Source.MANUAL and account_service.permissions(ctx, account)[0],
    )


def list_transactions(
    db: Session,
    ctx: AuthContext,
    scope: Scope,
    filters: TransactionFilters,
    *,
    cursor: str | None,
    limit: int,
) -> Page[TransactionOut]:
    rows, next_cursor = transaction_repo.list_page(
        db, scope.account_ids, filters, cursor=cursor, limit=limit
    )
    return Page[TransactionOut](items=[to_out(t, a, ctx) for t, a in rows], next_cursor=next_cursor)


def create_manual(db: Session, ctx: AuthContext, data: TransactionCreate) -> TransactionOut:
    account = _manual_account(db, ctx, data.account_id)
    _check_amount(data.amount_cents)
    txn = Transaction(
        account_id=account.id,
        source=Source.MANUAL,
        date=data.date,
        amount_cents=data.amount_cents,
        description=data.description,
        payee=data.payee or None,
        notes=data.notes or None,
        pending=False,
        created_by_user_id=ctx.user.id,
    )
    db.add(txn)
    db.flush()
    account_service.recompute_manual_balance(db, account)
    db.commit()
    return to_out(txn, account, ctx)


def update(db: Session, ctx: AuthContext, txn_id: int, data: TransactionUpdate) -> TransactionOut:
    """Partial update. Moving a transaction recomputes both the old and new account balances."""
    txn, account = _get_editable(db, ctx, txn_id)
    fields = data.model_fields_set
    old_account = account

    if "account_id" in fields and data.account_id is not None and data.account_id != account.id:
        account = _manual_account(db, ctx, data.account_id)
        txn.account_id = account.id
    if "date" in fields and data.date is not None:
        txn.date = data.date
    if "amount_cents" in fields and data.amount_cents is not None:
        _check_amount(data.amount_cents)
        txn.amount_cents = data.amount_cents
    if "description" in fields and data.description:
        txn.description = data.description
    if "payee" in fields:
        txn.payee = data.payee or None
    if "notes" in fields:
        txn.notes = data.notes or None

    db.flush()
    account_service.recompute_manual_balance(db, account)
    if old_account.id != account.id:
        account_service.recompute_manual_balance(db, old_account)
    db.commit()
    return to_out(txn, account, ctx)


def delete(db: Session, ctx: AuthContext, txn_id: int) -> None:
    txn, account = _get_editable(db, ctx, txn_id)
    db.delete(txn)
    db.flush()
    account_service.recompute_manual_balance(db, account)
    db.commit()


def _manual_account(db: Session, ctx: AuthContext, account_id: int) -> Account:
    account = account_service.get_editable_account(db, ctx, account_id)
    if account.source != Source.MANUAL:
        # Manual entries in synced accounts would double-count once the bank syncs them.
        raise AppError(
            "Manual transactions can only be added to manual accounts.", code="not_manual_account"
        )
    return account


def _get_editable(db: Session, ctx: AuthContext, txn_id: int) -> tuple[Transaction, Account]:
    """A manual transaction in an account the user can see, or an error."""
    txn = transaction_repo.get(db, txn_id)
    if txn is None:
        raise NotFound("Transaction not found.")
    account = account_service.get_editable_account(db, ctx, txn.account_id)
    if txn.source != Source.MANUAL:
        raise AppError("Synced transactions can't be edited or deleted.", code="not_editable")
    return txn, account


def _check_amount(amount_cents: int) -> None:
    # The size limit is part of the schema (schemas/common.py Cents).
    if amount_cents == 0:
        raise AppError("Amount can't be zero.")

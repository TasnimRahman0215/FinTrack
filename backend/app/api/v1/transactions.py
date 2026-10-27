"""/api/v1/transactions: the scoped, filterable list and manual transaction CRUD.

Called by frontend/src/api/transactions.js.
"""

import datetime as dt

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_scope, require_role
from app.core.scope import Scope
from app.models.enums import Role
from app.repositories.transaction_repo import TransactionFilters
from app.schemas.common import Page
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate
from app.services import transaction_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=Page[TransactionOut])
def list_transactions(
    scope: Scope = Depends(get_scope),
    account_id: int | None = None,
    start: dt.date | None = Query(None, description="Inclusive, YYYY-MM-DD"),
    end: dt.date | None = Query(None, description="Inclusive, YYYY-MM-DD"),
    q: str | None = Query(None, max_length=200, description="Search description/payee/notes"),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Page[TransactionOut]:
    """Newest first. Pass `next_cursor` from one page as `cursor` to get the next."""
    filters = TransactionFilters(account_id=account_id, start=start, end=end, q=q or None)
    return transaction_service.list_transactions(db, scope, filters, cursor=cursor, limit=limit)


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: TransactionCreate,
    ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR)),
    db: Session = Depends(get_db),
) -> TransactionOut:
    """Add a transaction to a manual account."""
    return transaction_service.create_manual(db, ctx, data)


@router.patch("/{txn_id}", response_model=TransactionOut)
def update_transaction(
    txn_id: int,
    data: TransactionUpdate,
    ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR)),
    db: Session = Depends(get_db),
) -> TransactionOut:
    """Edit a manual transaction."""
    return transaction_service.update(db, ctx, txn_id, data)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    txn_id: int,
    ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR)),
    db: Session = Depends(get_db),
) -> None:
    """Delete a manual transaction."""
    transaction_service.delete(db, ctx, txn_id)

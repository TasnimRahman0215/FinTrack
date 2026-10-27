"""/api/v1/accounts: list accounts in a scope, edit them, and manage manual accounts.

Called by frontend/src/api/accounts.js.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_auth, get_db, require_role
from app.core.scope import resolve_scope
from app.models.enums import Role
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.services import account_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(
    scope: str = Query("me", description="me | household | member:<user_id>"),
    include_hidden: bool = False,
    ctx: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> list[AccountOut]:
    """Accounts in the scope. `include_hidden` lets the Accounts page show hidden ones too."""
    # Resolved here (not via get_scope) because this is the only endpoint with include_hidden.
    resolved = resolve_scope(
        db,
        household_id=ctx.household_id,
        user_id=ctx.user.id,
        raw=scope,
        include_hidden=include_hidden,
    )
    return account_service.list_accounts(db, resolved)


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_manual_account(
    data: AccountCreate,
    ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR)),
    db: Session = Depends(get_db),
) -> AccountOut:
    """Create a manual account (cash, Venmo, ...)."""
    return account_service.create_manual(db, ctx, data)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int,
    data: AccountUpdate,
    ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR)),
    db: Session = Depends(get_db),
) -> AccountOut:
    """Rename, re-type, re-assign, hide, or change visibility of an account."""
    return account_service.update(db, ctx, account_id, data)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_manual_account(
    account_id: int,
    ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR)),
    db: Session = Depends(get_db),
) -> None:
    """Delete a manual account and its transactions. Synced accounts can only be hidden."""
    account_service.delete_manual(db, ctx, account_id)

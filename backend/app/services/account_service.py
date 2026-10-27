"""Accounts: listing, editing owner/visibility/kind, and manual accounts.

Used by api/v1/accounts.py, by transaction_service (manual balances) and by sync_service
(guess_kind for newly synced accounts).
"""

from sqlalchemy.orm import Session

from app.core.clock import utcnow, utctoday
from app.core.errors import AppError, Forbidden, NotFound
from app.core.scope import Scope, visible_account_ids
from app.models import Account
from app.models.enums import AccountKind, Role, Source
from app.repositories import account_repo, balance_repo, household_repo
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.services.auth_service import AuthContext

# Words in an account or institution name that suggest its kind. Checked in order, first match wins.
_KIND_HINTS: list[tuple[AccountKind, tuple[str, ...]]] = [
    (
        AccountKind.INVESTMENT,
        (
            "robinhood",
            "brokerage",
            "invest",
            "401k",
            "401(k)",
            "ira",
            "roth",
            "hsa",
            "stock",
            "fidelity",
            "schwab",
            "vanguard",
            "etrade",
            "e*trade",
            "webull",
            "crypto",
        ),
    ),
    (AccountKind.CHECKING, ("checking", "chequing", "debit")),
    (AccountKind.SAVINGS, ("saving", "money market")),
    (AccountKind.CREDIT, ("credit", "card", "visa", "mastercard", "amex", "discover", "sapphire")),
    (AccountKind.LOAN, ("loan", "mortgage")),
]


def guess_kind(name: str, org_name: str | None, balance_cents: int) -> AccountKind:
    """SimpleFIN doesn't report account types, so make a best guess the user can correct."""
    text = f"{name} {org_name or ''}".lower()
    for kind, hints in _KIND_HINTS:
        if any(h in text for h in hints):
            return kind
    return AccountKind.CREDIT if balance_cents < 0 else AccountKind.OTHER


def list_accounts(db: Session, scope: Scope) -> list[AccountOut]:
    return [AccountOut.model_validate(a) for a in account_repo.list_by_ids(db, scope.account_ids)]


def get_visible_account(db: Session, ctx: AuthContext, account_id: int) -> Account:
    """Load an account the user may see, or 404 (also for other members' private accounts)."""
    account = account_repo.get(db, household_id=ctx.household_id, account_id=account_id)
    visible = visible_account_ids(db, household_id=ctx.household_id, user_id=ctx.user.id)
    if account is None or account.id not in visible:
        raise NotFound("Account not found.")
    return account


def create_manual(db: Session, ctx: AuthContext, data: AccountCreate) -> AccountOut:
    # An omitted owner means "me"; an explicit null means a joint account.
    owner_id = data.owner_user_id if "owner_user_id" in data.model_fields_set else ctx.user.id
    _check_owner(db, ctx, owner_id)
    account = account_repo.add(
        db,
        Account(
            household_id=ctx.household_id,
            source=Source.MANUAL,
            name=data.name,
            kind=data.kind,
            currency=data.currency.upper(),
            owner_user_id=owner_id,
            visibility=data.visibility,
            opening_balance_cents=data.opening_balance_cents,
        ),
    )
    recompute_manual_balance(db, account)
    db.commit()
    return AccountOut.model_validate(account)


def update(db: Session, ctx: AuthContext, account_id: int, data: AccountUpdate) -> AccountOut:
    """Partial update: only fields present in the request body are changed."""
    account = get_visible_account(db, ctx, account_id)
    fields = data.model_fields_set

    # Only the account's owner (or the household owner) can re-assign or hide it from others.
    can_reassign = account.owner_user_id in (ctx.user.id, None) or ctx.role == Role.OWNER
    if ({"owner_user_id", "visibility"} & fields) and not can_reassign:
        raise Forbidden("Only the account's owner can change who owns it or who can see it.")
    if "owner_user_id" in fields:
        _check_owner(db, ctx, data.owner_user_id)
        account.owner_user_id = data.owner_user_id
    if "visibility" in fields and data.visibility is not None:
        account.visibility = data.visibility
    if "display_name" in fields:
        account.display_name = data.display_name or None
    if "kind" in fields and data.kind is not None:
        account.kind = data.kind
    if "is_hidden" in fields and data.is_hidden is not None:
        account.is_hidden = data.is_hidden

    manual_only = {"name", "opening_balance_cents"} & fields
    if manual_only and account.source != Source.MANUAL:
        raise AppError("Name and opening balance can only be changed on manual accounts.")
    if "name" in fields and data.name:
        account.name = data.name
    if "opening_balance_cents" in fields and data.opening_balance_cents is not None:
        account.opening_balance_cents = data.opening_balance_cents
        recompute_manual_balance(db, account)

    db.commit()
    return AccountOut.model_validate(account)


def delete_manual(db: Session, ctx: AuthContext, account_id: int) -> None:
    account = get_visible_account(db, ctx, account_id)
    if account.source != Source.MANUAL:
        raise AppError("Synced accounts can't be deleted; hide them or remove the connection.")
    db.delete(account)
    db.commit()


def recompute_manual_balance(db: Session, account: Account) -> None:
    """A manual account's balance = opening balance + sum of its transactions."""
    account.balance_cents = account.opening_balance_cents + account_repo.transaction_total(
        db, account.id
    )
    account.balance_as_of = utcnow()
    balance_repo.upsert_snapshot(
        db, account_id=account.id, date=utctoday(), balance_cents=account.balance_cents
    )


def _check_owner(db: Session, ctx: AuthContext, owner_user_id: int | None) -> None:
    """An account can only be owned by someone in the same household (None = joint)."""
    if owner_user_id is not None and not household_repo.is_member(
        db, household_id=ctx.household_id, user_id=owner_user_id
    ):
        raise AppError("The owner must be a member of this household.")

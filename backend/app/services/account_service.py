"""Accounts: listing, editing owner/visibility/kind, manual accounts, and who may edit what.

Used by api/v1/accounts.py, by transaction_service (manual balances) and by sync_service
(guess_kind for newly synced accounts).
"""

from sqlalchemy.orm import Session

from app.core.clock import utcnow, utctoday
from app.core.errors import AppError, Forbidden, NotFound
from app.core.scope import Scope
from app.models import Account
from app.models.enums import AccountKind, Role, Source, Visibility
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


def permissions(ctx: AuthContext, account: Account) -> tuple[bool, bool]:
    """(can_edit, can_reassign) for the signed-in user on an account they can already see.

    - Edit (rename, type, hide, manual transactions, delete a manual account): contributors and
      owners, on their own accounts and joint ones. The household owner may edit any visible one.
    - Reassign (change owner or visibility): only the account's owner or the household owner.
      Joint accounts belong to everyone, so only the household owner can take one away from the
      household by giving it an owner or making it private.
    """
    if not ctx.has_role(Role.CONTRIBUTOR):
        return False, False
    if ctx.role == Role.OWNER:
        return True, True
    mine = account.owner_user_id == ctx.user.id
    return mine or account.owner_user_id is None, mine


def to_out(account: Account, ctx: AuthContext) -> AccountOut:
    can_edit, can_reassign = permissions(ctx, account)
    out = AccountOut.model_validate(account)
    out.can_edit, out.can_reassign = can_edit, can_reassign
    return out


def list_accounts(db: Session, ctx: AuthContext, scope: Scope) -> list[AccountOut]:
    return [to_out(a, ctx) for a in account_repo.list_by_ids(db, scope.account_ids)]


def get_visible_account(db: Session, ctx: AuthContext, account_id: int) -> Account:
    """Load an account the user may see, or 404 (also for other members' private accounts)."""
    account = account_repo.get_visible(
        db, household_id=ctx.household_id, account_id=account_id, user_id=ctx.user.id
    )
    if account is None:
        raise NotFound("Account not found.")
    return account


def get_editable_account(db: Session, ctx: AuthContext, account_id: int) -> Account:
    """Like get_visible_account, but 403 unless the user may edit it (see `permissions`)."""
    account = get_visible_account(db, ctx, account_id)
    if not permissions(ctx, account)[0]:
        raise Forbidden("Only the account's owner or the household owner can change this account.")
    return account


def create_manual(db: Session, ctx: AuthContext, data: AccountCreate) -> AccountOut:
    # An omitted owner means "me"; an explicit null means a joint account.
    owner_id = data.owner_user_id if "owner_user_id" in data.model_fields_set else ctx.user.id
    if owner_id not in (ctx.user.id, None) and ctx.role != Role.OWNER:
        raise Forbidden("Only the household owner can create an account for someone else.")
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
            visibility=Visibility.SHARED if owner_id is None else data.visibility,
            opening_balance_cents=data.opening_balance_cents,
        ),
    )
    recompute_manual_balance(db, account)
    db.commit()
    return to_out(account, ctx)


def update(db: Session, ctx: AuthContext, account_id: int, data: AccountUpdate) -> AccountOut:
    """Partial update: only fields present in the request body are changed."""
    account = get_editable_account(db, ctx, account_id)
    fields = data.model_fields_set

    if ({"owner_user_id", "visibility"} & fields) and not permissions(ctx, account)[1]:
        raise Forbidden("Only the account's owner can change who owns it or who can see it.")
    if "owner_user_id" in fields:
        _check_owner(db, ctx, data.owner_user_id)
        account.owner_user_id = data.owner_user_id
    if "visibility" in fields and data.visibility is not None:
        account.visibility = data.visibility
    if account.owner_user_id is None:
        account.visibility = Visibility.SHARED  # joint accounts are always shared
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
    return to_out(account, ctx)


def delete_manual(db: Session, ctx: AuthContext, account_id: int) -> None:
    account = get_editable_account(db, ctx, account_id)
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

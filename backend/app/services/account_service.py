"""Accounts: listing, editing owner/visibility/kind, manual accounts, and who may edit what.

Used by api/v1/accounts.py, by transaction_service (manual balances) and by sync_service
(guess_kind for newly synced accounts).
"""

from collections.abc import Collection
from dataclasses import dataclass

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


@dataclass(frozen=True)
class Permissions:
    can_edit: bool  # everyday edits: names, type, opening balance, manual transactions
    can_manage: bool  # owner, visibility, hiding (for everyone) and deleting


def permissions(ctx: AuthContext, account: Account, member_ids: Collection[int]) -> Permissions:
    """What the signed-in user may do with an account they can already see.

    - Your own account: everything.
    - A joint account: any contributor makes everyday edits; only the household owner manages it
      (gives it an owner, makes it private, hides it for everyone or deletes it), since those
      take it away from the whole household.
    - Another member's account: theirs alone. Not even the household owner can edit, reassign,
      hide or delete it.
    - The account of someone who has left the household: the household owner looks after it.
    Readers can't change anything.
    """
    if not ctx.has_role(Role.CONTRIBUTOR):
        return Permissions(False, False)
    owner = account.owner_user_id
    if owner == ctx.user.id:
        return Permissions(True, True)
    household_owner = ctx.role == Role.OWNER
    if owner is None:
        return Permissions(True, household_owner)
    if owner not in member_ids:
        return Permissions(household_owner, household_owner)
    return Permissions(False, False)


def member_ids(db: Session, ctx: AuthContext) -> set[int]:
    return household_repo.member_ids(db, ctx.household_id)


def to_out(account: Account, ctx: AuthContext, members: Collection[int]) -> AccountOut:
    perms = permissions(ctx, account, members)
    out = AccountOut.model_validate(account)
    out.can_edit, out.can_manage = perms.can_edit, perms.can_manage
    return out


def list_accounts(db: Session, ctx: AuthContext, scope: Scope) -> list[AccountOut]:
    members = member_ids(db, ctx)
    return [to_out(a, ctx, members) for a in account_repo.list_by_ids(db, scope.account_ids)]


def get_visible_account(db: Session, ctx: AuthContext, account_id: int) -> Account:
    """Load an account the user may see, or 404 (also for other members' private accounts)."""
    account = account_repo.get_visible(
        db, household_id=ctx.household_id, account_id=account_id, user_id=ctx.user.id
    )
    if account is None:
        raise NotFound("Account not found.")
    return account


def get_editable_account(db: Session, ctx: AuthContext, account_id: int) -> Account:
    """Like get_visible_account, but 403 unless the user may make everyday edits to it."""
    account = get_visible_account(db, ctx, account_id)
    if not permissions(ctx, account, member_ids(db, ctx)).can_edit:
        raise Forbidden(_NOT_YOURS)
    return account


_NOT_YOURS = "Only the account's owner can change this account."
_MANAGE_ONLY = (
    "Only the account's owner can change who owns it, who can see it, hide it or delete it "
    "(for a joint account, only the household owner)."
)


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
    return to_out(account, ctx, member_ids(db, ctx))


def update(db: Session, ctx: AuthContext, account_id: int, data: AccountUpdate) -> AccountOut:
    """Partial update: only fields present in the request body are changed.

    Owner, visibility and hidden need `can_manage`, but only when they actually change, so a
    form that re-sends the current values doesn't need extra rights.
    """
    account = get_visible_account(db, ctx, account_id)
    members = member_ids(db, ctx)
    perms = permissions(ctx, account, members)
    if not (perms.can_edit or perms.can_manage):
        raise Forbidden(_NOT_YOURS)
    fields = data.model_fields_set

    changes_owner = "owner_user_id" in fields and data.owner_user_id != account.owner_user_id
    changes_visibility = data.visibility is not None and data.visibility != account.visibility
    changes_hidden = data.is_hidden is not None and data.is_hidden != account.is_hidden
    if (changes_owner or changes_visibility or changes_hidden) and not perms.can_manage:
        raise Forbidden(_MANAGE_ONLY)
    edits = {"display_name", "kind", "name", "opening_balance_cents"} & fields
    if edits and not perms.can_edit:
        raise Forbidden(_NOT_YOURS)

    if changes_owner:
        _check_owner(db, ctx, data.owner_user_id)
        account.owner_user_id = data.owner_user_id
    if changes_visibility:
        account.visibility = data.visibility
    if account.owner_user_id is None:
        account.visibility = Visibility.SHARED  # joint accounts are always shared
    if changes_hidden:
        account.is_hidden = data.is_hidden
    if "display_name" in fields:
        account.display_name = data.display_name or None
    if "kind" in fields and data.kind is not None:
        account.kind = data.kind

    manual_only = {"name", "opening_balance_cents"} & fields
    if manual_only and account.source != Source.MANUAL:
        raise AppError("Name and opening balance can only be changed on manual accounts.")
    if "name" in fields and data.name:
        account.name = data.name
    if "opening_balance_cents" in fields and data.opening_balance_cents is not None:
        account.opening_balance_cents = data.opening_balance_cents
        recompute_manual_balance(db, account)

    db.commit()
    return to_out(account, ctx, members)


def delete_manual(db: Session, ctx: AuthContext, account_id: int) -> None:
    account = get_visible_account(db, ctx, account_id)
    if not permissions(ctx, account, member_ids(db, ctx)).can_manage:
        raise Forbidden(_MANAGE_ONLY)
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

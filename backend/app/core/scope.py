"""Scope resolution: the ONE place where "who can see which accounts" is decided.

Every data endpoint takes `?scope=` and receives the allowed account IDs from here:

- `me`              accounts I own (shared or private) + joint accounts
- `member:<id>`     that member's *shared* accounts + joint accounts
- `household`       every member's shared accounts + joint accounts

A joint account has no owner (owner_user_id IS NULL) *and* is shared; the services keep joint
accounts shared. An account with no owner that is still marked private (its owner's user row was
deleted) is visible to nobody: it must never turn into a joint account by accident. Private
accounts are only ever visible to their owner, through `me`.

Used by app/api/deps.py (`get_scope`) for list endpoints, and by services through
`visible_account_ids` before reading or editing a single account or transaction.
"""

from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFound
from app.models import Account, HouseholdMembership
from app.models.enums import Visibility
from app.schemas.common import MAX_DB_ID


@dataclass(frozen=True)
class Scope:
    """The resolved view: which accounts the current request may read."""

    kind: str  # "me" | "member" | "household"
    member_user_id: int | None
    account_ids: tuple[int, ...]

    @property
    def key(self) -> str:
        """The normalized scope string, echoed back in API responses."""
        return f"member:{self.member_user_id}" if self.kind == "member" else self.kind


def parse_scope(raw: str) -> tuple[str, int | None]:
    """Turn "me" / "household" / "member:<id>" into (kind, member_id); reject anything else."""
    raw = (raw or "me").strip().lower()
    if raw in ("me", "household"):
        return raw, None
    if raw.startswith("member:"):
        try:
            member_id = int(raw.split(":", 1)[1])
        except ValueError:
            pass
        else:
            if 1 <= member_id <= MAX_DB_ID:
                return "member", member_id
    raise AppError("scope must be 'me', 'household' or 'member:<user_id>'", code="invalid_scope")


def _joint() -> ColumnElement[bool]:
    return and_(Account.owner_user_id.is_(None), Account.visibility == Visibility.SHARED)


def _shared() -> ColumnElement[bool]:
    return Account.visibility == Visibility.SHARED


def resolve_scope(
    db: Session, *, household_id: int, user_id: int, raw: str, include_hidden: bool = False
) -> Scope:
    """Return the account IDs this user may see under `raw` (hidden ones only if asked)."""
    kind, member_id = parse_scope(raw)
    # Viewing yourself as a "member" would hide your private accounts; treat it as `me`.
    if kind == "member" and member_id == user_id:
        kind, member_id = "me", None

    if kind == "me":
        condition = or_(Account.owner_user_id == user_id, _joint())
    elif kind == "member":
        is_member = db.scalar(
            select(HouseholdMembership.id).where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.user_id == member_id,
            )
        )
        if not is_member:
            raise NotFound("That person isn't a member of this household.")
        condition = or_(and_(Account.owner_user_id == member_id, _shared()), _joint())
    else:
        condition = or_(_shared(), _joint())

    stmt = select(Account.id).where(Account.household_id == household_id, condition)
    if not include_hidden:
        stmt = stmt.where(Account.is_hidden.is_(False))
    ids = tuple(db.scalars(stmt.order_by(Account.id)).all())
    return Scope(kind=kind, member_user_id=member_id, account_ids=ids)


def visible_to(user_id: int) -> ColumnElement[bool]:
    """SQL condition: accounts this user may see in some scope (own, shared or joint).

    Combine it with a household filter. Used for single-account lookups and connection details.
    """
    return or_(Account.owner_user_id == user_id, _shared())


def visible_account_ids(db: Session, *, household_id: int, user_id: int) -> set[int]:
    """Every account this user may see in any scope (including hidden ones)."""
    stmt = select(Account.id).where(Account.household_id == household_id, visible_to(user_id))
    return set(db.scalars(stmt).all())

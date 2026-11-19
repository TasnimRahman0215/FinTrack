"""Account request/response bodies for api/v1/accounts.py."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.enums import AccountKind, Visibility
from app.schemas.common import Cents, ORMModel

AccountName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class AccountOut(ORMModel):
    id: int
    source: str
    connection_id: int | None
    name: str
    display_name: str | None
    org_name: str | None
    kind: AccountKind
    currency: str
    owner_user_id: int | None
    visibility: Visibility
    is_hidden: bool
    balance_cents: int
    available_cents: int | None
    balance_as_of: datetime | None
    opening_balance_cents: int
    # What the signed-in user may do with this account (see account_service.permissions).
    can_edit: bool = False  # names, type, opening balance, manual transactions
    can_manage: bool = False  # owner, visibility, hidden, delete


class AccountCreate(BaseModel):
    """A manual account. Omit owner_user_id to own it yourself; send null for a joint account
    (joint accounts are always shared)."""

    name: AccountName
    kind: AccountKind = AccountKind.OTHER
    owner_user_id: int | None = None
    visibility: Visibility = Visibility.SHARED
    opening_balance_cents: Cents = 0
    currency: Annotated[str, StringConstraints(min_length=3, max_length=16)] = "USD"


class AccountUpdate(BaseModel):
    """Only the fields that are sent are changed. owner_user_id = null makes it joint (and
    therefore shared)."""

    display_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None
    ) = None
    kind: AccountKind | None = None
    owner_user_id: int | None = None
    visibility: Visibility | None = None
    is_hidden: bool | None = None
    name: AccountName | None = None  # manual accounts only
    opening_balance_cents: Cents | None = None  # manual accounts only

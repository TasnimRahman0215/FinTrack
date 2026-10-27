"""Dashboard summary response for api/v1/summary.py."""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AccountKind


class KindTotal(BaseModel):
    kind: AccountKind
    total_cents: int
    account_count: int


class OwnerTotal(BaseModel):
    owner_user_id: int | None  # None = joint
    name: str
    total_cents: int


class SummaryOut(BaseModel):
    scope: str
    net_worth_cents: int
    assets_cents: int
    liabilities_cents: int  # negative number
    account_count: int
    by_kind: list[KindTotal]
    by_owner: list[OwnerTotal]
    last_synced_at: datetime | None

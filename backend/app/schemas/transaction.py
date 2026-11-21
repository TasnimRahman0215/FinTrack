"""Transaction request/response bodies for api/v1/transactions.py."""

import datetime as dt
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.common import Cents, DbId, ORMModel

Text255 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]


class TransactionOut(ORMModel):
    id: int
    account_id: int
    account_name: str
    source: str
    date: dt.date
    posted_at: dt.datetime | None
    amount_cents: int
    description: str
    payee: str | None
    memo: str | None
    notes: str | None
    pending: bool
    editable: bool  # a manual transaction in an account the signed-in user may edit


class TransactionCreate(BaseModel):
    account_id: DbId
    date: dt.date
    amount_cents: Annotated[Cents, Field(description="Negative = money out, positive = money in")]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    payee: Text255 | None = None
    notes: Annotated[str, StringConstraints(max_length=2000)] | None = None


class TransactionUpdate(BaseModel):
    """Only the fields that are sent are changed."""

    account_id: DbId | None = None
    date: dt.date | None = None
    amount_cents: Cents | None = None
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
        | None
    ) = None
    payee: Text255 | None = None
    notes: Annotated[str, StringConstraints(max_length=2000)] | None = None

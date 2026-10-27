"""Transaction request/response bodies for api/v1/transactions.py."""

import datetime as dt
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.common import ORMModel

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
    editable: bool  # manual transactions can be edited/deleted


class TransactionCreate(BaseModel):
    account_id: int
    date: dt.date
    amount_cents: Annotated[int, Field(description="Negative = money out, positive = money in")]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    payee: Text255 | None = None
    notes: Annotated[str, StringConstraints(max_length=2000)] | None = None


class TransactionUpdate(BaseModel):
    """Only the fields that are sent are changed."""

    account_id: int | None = None
    date: dt.date | None = None
    amount_cents: int | None = None
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
        | None
    ) = None
    payee: Text255 | None = None
    notes: Annotated[str, StringConstraints(max_length=2000)] | None = None

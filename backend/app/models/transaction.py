import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Transaction(IdMixin, TimestampMixin, Base):
    """A single money movement. `amount_cents` < 0 is money out, > 0 is money in.

    Provider columns are refreshed by sync; `notes` (and later category/transfer flags) are
    user-owned and never overwritten by sync.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "provider_txn_id"),
        Index("ix_transactions_account_id_date", "account_id", "date"),
        Index("ix_transactions_date", "date"),
    )

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(20))
    provider_txn_id: Mapped[str | None] = mapped_column(String(255))  # NULL for manual

    # Provider fields
    date: Mapped[dt.date] = mapped_column(Date)  # the day shown to the user
    posted_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    transacted_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(500), default="")
    payee: Mapped[str | None] = mapped_column(String(255))
    memo: Mapped[str | None] = mapped_column(String(500))
    pending: Mapped[bool] = mapped_column(Boolean, default=False)
    # The provider's original payload, kept so future features can re-derive data without
    # re-fetching. Never returned by the API.
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # User fields
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

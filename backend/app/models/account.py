from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.enums import AccountKind, Visibility


class Account(IdMixin, TimestampMixin, Base):
    """A bank/card/investment account, either synced from a provider or created manually.

    Provider columns (name, org_name, balance...) are overwritten by sync. User columns
    (display_name, kind, owner_user_id, visibility, is_hidden) are never touched by sync.
    """

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("connection_id", "provider_account_id"),)

    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(20))  # simplefin | manual (enums.Source)
    connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), index=True
    )
    provider_account_id: Mapped[str | None] = mapped_column(String(255))  # the provider's ID

    # Provider fields
    name: Mapped[str] = mapped_column(String(200))
    org_name: Mapped[str | None] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(16), default="USD")
    balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    available_cents: Mapped[int | None] = mapped_column(BigInteger)
    balance_as_of: Mapped[datetime | None] = mapped_column(DateTime)

    # User fields
    display_name: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default=AccountKind.OTHER)
    owner_user_id: Mapped[int | None] = mapped_column(  # NULL = joint account
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    visibility: Mapped[str] = mapped_column(String(20), default=Visibility.SHARED)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    opening_balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)  # manual only

    connection: Mapped["Connection | None"] = relationship(back_populates="accounts")  # noqa: F821

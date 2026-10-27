from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.enums import ConnectionStatus


class Connection(IdMixin, TimestampMixin, Base):
    """A linked data source, e.g. one SimpleFIN access URL. A household can have many."""

    __tablename__ = "connections"

    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    added_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(200), default="SimpleFIN")
    credentials_enc: Mapped[str] = mapped_column(Text)  # Fernet-encrypted (core/security.py)
    status: Mapped[str] = mapped_column(String(32), default=ConnectionStatus.ACTIVE)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)  # last successful sync
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime)  # drives the cooldown
    last_error: Mapped[str | None] = mapped_column(Text)  # shown in Settings; never secrets

    accounts: Mapped[list["Account"]] = relationship(  # noqa: F821
        back_populates="connection", cascade="all, delete-orphan", passive_deletes=True
    )

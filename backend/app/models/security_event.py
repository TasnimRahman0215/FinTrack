from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base, IdMixin


class SecurityEvent(IdMixin, Base):
    """Who did something security-relevant, when and from where (services/audit_service.py).

    Holds IDs, IP addresses and browsers only: never names, amounts or other financial data.
    """

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_user_id_created_at", "user_id", "created_at"),
        Index("ix_security_events_created_at", "created_at"),
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    event: Mapped[str] = mapped_column(String(40))  # e.g. login, login_failed, password_changed
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    household_id: Mapped[int | None] = mapped_column(
        ForeignKey("households.id", ondelete="SET NULL"), index=True
    )
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # IDs only

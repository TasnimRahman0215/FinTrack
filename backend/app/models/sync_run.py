from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base, IdMixin
from app.models.enums import SyncStatus


class SyncRun(IdMixin, Base):
    """History of each sync attempt, including errors the provider reported."""

    __tablename__ = "sync_runs"

    connection_id: Mapped[int] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), index=True
    )
    # manual | scheduled | initial
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
    status: Mapped[str] = mapped_column(String(20), default=SyncStatus.RUNNING)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    accounts_seen: Mapped[int] = mapped_column(Integer, default=0)
    txns_new: Mapped[int] = mapped_column(Integer, default=0)
    txns_updated: Mapped[int] = mapped_column(Integer, default=0)
    txns_removed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list)

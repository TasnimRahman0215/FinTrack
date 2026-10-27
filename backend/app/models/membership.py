from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utcnow
from app.db.base import Base, IdMixin


class HouseholdMembership(IdMixin, Base):
    """Links a user to a household with a role (owner / contributor / reader)."""

    __tablename__ = "household_memberships"
    __table_args__ = (UniqueConstraint("household_id", "user_id"),)

    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    household: Mapped["Household"] = relationship(back_populates="memberships")  # noqa: F821
    user: Mapped["User"] = relationship(back_populates="memberships")  # noqa: F821

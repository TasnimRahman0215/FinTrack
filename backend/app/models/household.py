from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin


class Household(IdMixin, TimestampMixin, Base):
    """The tenant boundary: every connection, account and transaction belongs to one household."""

    __tablename__ = "households"

    name: Mapped[str] = mapped_column(String(120))
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    memberships: Mapped[list["HouseholdMembership"]] = relationship(  # noqa: F821
        back_populates="household", cascade="all, delete-orphan"
    )

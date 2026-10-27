"""Household and membership queries. Used by the auth, household, account and summary services."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Household, HouseholdMembership, User
from app.models.enums import Role


def get(db: Session, household_id: int) -> Household | None:
    return db.get(Household, household_id)


def create(db: Session, *, name: str, created_by_user_id: int) -> Household:
    household = Household(name=name, created_by_user_id=created_by_user_id)
    db.add(household)
    db.flush()
    return household


def add_member(db: Session, *, household_id: int, user_id: int, role: Role) -> HouseholdMembership:
    membership = HouseholdMembership(household_id=household_id, user_id=user_id, role=role)
    db.add(membership)
    db.flush()
    return membership


def get_membership(db: Session, *, household_id: int, user_id: int) -> HouseholdMembership | None:
    return db.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == user_id,
        )
    )


def first_membership(db: Session, user_id: int) -> HouseholdMembership | None:
    """The household a user joined first: the default active household at login."""
    return db.scalar(
        select(HouseholdMembership)
        .where(HouseholdMembership.user_id == user_id)
        .order_by(HouseholdMembership.joined_at, HouseholdMembership.id)
        .limit(1)
    )


def list_members(db: Session, household_id: int) -> list[tuple[HouseholdMembership, User]]:
    rows = db.execute(
        select(HouseholdMembership, User)
        .join(User, User.id == HouseholdMembership.user_id)
        .where(HouseholdMembership.household_id == household_id)
        .order_by(HouseholdMembership.joined_at, HouseholdMembership.id)
    ).all()
    return [(m, u) for m, u in rows]


def is_member(db: Session, *, household_id: int, user_id: int) -> bool:
    return get_membership(db, household_id=household_id, user_id=user_id) is not None
